import asyncio
import fractions
import logging
import threading
import time
from typing import Optional
import av
import numpy as np 
from aiortc.mediastreams import VideoStreamTrack, VIDEO_CLOCK_RATE, VIDEO_TIME_BASE

log=logging.getLogger("pipeline")
_gst=None
_GstApp=None
def _import_gst():
    global _gst, _GstApp
    if _gst is not None:
        return
    import gi
    gi.require_version("Gst","1.0")
    gi.require_version("GstApp","1.0")
    from gi.repository import Gst, GstApp, GLib
    Gst.init(None)
    _gst=(Gst, GLib)
    _GstApp=GstApp

def _detect_encoder()->str:
    _import_gst()
    Gst, _=_gst
    registry=Gst.Registry.get()
    if registry.find_plugin("nvcodec"):
        log.info("encoder nvenc")
        return "nvenc"
    if registry.find_plugin("vaapi"):
        log.info("encoder vaapi")
        return "vaapi"
    log.info("encoder x264")
    return "software"

def _build_pipeline_string(width:int,height:int,fps:int,encoder:str,display:str)->str:
    caps=(
        f"video/x-raw,format=RGB,width={width},height={height},"
        f"framerate={fps}/1"
    )
    pipeline=(
        f"ximagesrc display-name={display} use-damage=false ! "
        f"video/x-raw,framerate={fps}/1 ! "
        f"videoscale ! videorate ! "
        f"videoconvert ! "
        f"{caps} ! "
        f"appsink name=sink emit-signals=true max-buffers=2 drop=true sync=false"
    )
    return pipeline

class ScreenCaptureTrack(VideoStreamTrack):
    kind="video"
    def __init__(
        self,
        width:int=1920,
        height:int=1080,
        fps:int=60,
        display:str=":0",
    ):
        super().__init__()
        self.width=width
        self.height=height
        self.fps=fps
        self.display=display
        self._queue:asyncio.Queue=asyncio.Queue(maxsize=4)
        self._loop:Optional[asyncio.AbstractEventLoop]=None
        self._pipeline=None 
        self._gst_thread:Optional[threading.Thread]=None
        self._running=False 
        self._start_time:Optional[float]=None
        self._timestamp:int=0
    
    def start(self):
        if self._running:
            return
        _import_gst()
        self._running=True 
        self._loop=asyncio.get_event_loop()
        self._gst_thread=threading.Thread(target=self._gst_main,daemon=True)
        self._gst_thread.start()
        log.info("capture pipeline started (%dx%d ^ %dfps, display=%s)",self.width,self.height,self.fps,self.display)
    
    def stop(self):
        self._running=False
        if self._pipeline:
            self._pipeline.set_state(_gst[0].State.NULL)
        log.info("capture pipeline stopped")
        self._pipeline=Gst.parse_launch(pipeline_str)
        sink=self._pipeline.get_by_name("sink")
        sink.connect("new-sample",self.on_new_sample)
        self._pipeline.set_state(Gst.State.PLAYING)
        mainloop=GLib.MainLoop()
        bus=self._pipeline.get_bus()
        bus.add_signal_watch()
        def on_message(bus,message):
            t=message.type
            if t==Gst.MessageType.ERROR:
                err,debug=message.parse.error()
                log.error("gstreamer error %s - %s",err,debug)
                mainloop.quit()
            elif t==Gst.MessageType.EOS:
                log.info("gstreamer eos")
                mainloop.quit()
        bus.connect("message",on_message)
        try:
            mainloop.run()
        except Exception as e:
            log.error("gstreamer mainloop error %s",e)
        finally:
            self._pipeline.set_state(Gst.State.NULL)
    
    def _on_new_sample(self,sink):
        Gst, _=_gst
        sample=sink.emit("pull-sample")
        if sample is None:
            return Gst.FlowReturn.ERROR
        buf=sample.get_buffer()
        caps=sample.get_caps()
        structure=caps.get_structure(0)
        w=structure.get_value("width").value
        h=structure.get_value("height").value
        success,map_info=buf.map(Gst.MapFlags.READ)
        if not success:
            return Gst.FlowReturn.ERROR
        try:
            arr=np.frombuffer(map_info.data,dtype=np.uint8).reshape((h,w,3)).copy()
        finally:
            buf.unmap(map_info)
        if self._loop and self._running:
            try:
                asyncio.run_coroutine_threadsafe(self._push_frame(arr),self.loop)
            except Exception as e:
                log.warning("failed to push frame %s",e)
        return Gst.FlowReturn.OK
    
    async def _push_frame(self,arr:np.ndarray):
        try:
            self._queue.put_nowait(arr)
        except asyncio.QueueFull:
            pass
    
    async def recv(self)->av.VideoFrame:
        arr=await self._queue.get()
        if self._start_time is None:
            self._start_time=time.time()
        else:
            self._timestamp+=int((1/self.fps)*VIDEO_CLOCK_RATE)
        pts=self._timestamp
        time_base=VIDEO_TIME_BASE
        frame=av.VideoFrame.from_ndarray(arr,format="rgb24")
        frame=frame.reformat(format="yuv240p")
        frame.pts=pts
        frame.time_base=time_base
        return frame
    
    def _gst_main(self):
        Gst,GLib=_gst
        encoder=_detect_encoder()
        pipeline_str=_build_pipeline_string(self.width,self.height,self.fps,encoder,self.display)
        log.info("streamer pipeline %s",pipeline_str)
        self._pipeline=Gst.parse_launch(pipeline_str)
        sink=self._pipeline.get_by_name("sink")
        sink.connect("new-sample",self._on_new_sample)
        self._pipeline.set_state(Gst.State.PLAYING)
        mainloop=GLib.MainLoop()
        bus=self._pipeline.get_bus()
        bus.add_signal_watch()
        def on_message(bus,message):
            t=message.type
            if t==Gst.MessageType.ERROR:
                err,debug=message.parse.error()
                log.error("gstreamer error %s %s",err,debug)
                mainloop.quit()
            elif t==Gst.MessageType.EOS:
                mainloop.quit()
        bus.connect("message",on_message)
        try:
            mainloop.run()
        except Exception as e:
            log.error("gstreamer mainloop error %s",e)
        finally:
            self.pipeline.set_state(Gst.State.NULL)
    
    def _on_new_sample(self,sink):
        Gst,_=_gst
        sample=sink.emit("pull-sample")
        if sample is None:
            return Gst.FlowReturn.ERROR
        buf=sample.get_buffer()
        caps=sample.get_caps()
        structure=caps.get_structure(0)
        w=structure.get_int("width").value
        h=structure.get_int("height").value
        success,map_info=buf.map(Gst.MapFlags.READ)
        if not success:
            return Gst.FlowReturn.ERROR
        try:
            arr=np.frombuffer(map_info.data,dtype=np.uint8).reshape((h,w,3)).copy()
        finally:
            buf.unmap(map_info)
        if self._loop and self._running:
            try:
                asyncio.run_coroutine_threadsafe(self._push_frame(arr),self._loop)
            except Exception as e:
                log.warning("failed to push frame %s",e)
        return Gst.FlowReturn.OK