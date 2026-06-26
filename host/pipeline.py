import asyncio
import fractions
import logging
import threading
import time
from typing import Optional
import av
import numpy as np 
from aiortc.mediastreams import VideoStreamTrack, VIDEO_CLOCK_RATE, VIDEO_TIME_BASE
import os

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

def _is_wayland()->bool:
    return os.environ.get("XDG_SESSION_TYPE","").lower()=="wayland"

def _get_pipewire_node_id()->int:
    import dbus
    import dbus.mainloop.glib
    from gi.repository import GLib
    dbus.mainloop.glib.DBusGMainLoop(set_as_default=True)
    bus=dbus.SessionBus()
    portal=bus.get_object("org.freedesktop.portal.Desktop","/org/freedesktop/portal/desktop")
    screencast=dbus.Interface(portal,"org.freedesktop.portal.ScreenCast")
    loop=GLib.MainLoop()
    node_id_result=[None]
    session_path_result=[None]
    create_opts=dbus.Dictionary({"handle_token":dbus.String("webstream1"),"session_handle_token":dbus.String("webstreamsess1")},signature="sv")
    request_path=screencast.CreateSession(create_opts)
    request_obj=bus.get_object("org.freedesktop.portal.Desktop",request_path)
    request_iface=dbus.Interface(request_obj,"org.freedesktop.portal.Request")
    def on_create(response,results):
        if response!=0:
            loop.quit()
            return
        session_path_result[0]=str(results["session_handle"])
        select_opts=dbus.Dictionary({"handle_token":dbus.String("webstream2"),"types":dbus.UInt32(1),"multiple":dbus.Boolean(False),"cursor_mode":dbus.UInt32(2)},signature="sv")
        req2_path=screencast.SelectSources(session_path_result[0],select_opts)
        req2_obj=bus.get_object("org.freedesktop.portal.Desktop",req2_path)
        req2_iface=dbus.Interface(req2_obj,"org.freedesktop.portal.Request")
        def on_select(response,results):
            if response!=0:
                loop.quit()
                return
            start_opts=dbus.Dictionary({"handle_token":dbus.String("webstream3")},signature="sv")
            req3_path=screencast.Start(session_path_result[0],"",start_opts)
            req3_obj=bus.get_object("org.freedesktop.portal.Desktop",req3_path)
            req3_iface=dbus.Interface(req3_obj,"org.freedesktop.portal.Request")
            def on_start(response,results):
                if response!=0:
                    loop.quit()
                    return
                streams=results.get("streams",[])
                if streams:
                    node_id_result[0]=int(streams[0][0])
                    log.info("pipewire node id %d",node_id_result[0])
                loop.quit()
            req3_iface.connect_to_signal("Response",on_start)
        req2_iface.connect_to_signal("Response",on_select)
    request_iface.connect_to_signal("Response",on_create)
    loop.run()
    if node_id_result[0] is None:
        raise RuntimeError("failed to get pipewire rid")
    return node_id_result[0]

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
            _gst[0].State
            self._pipeline.set_state(_gst[0].State.NULL)
        log.info("capture pipeline stopped")
    
    async def _push_frame(self,arr:np.ndarray):
        try:
            self._queue.put_nowait(arr)
        except asyncio.QueueFull:
            pass
    
    async def recv(self)->av.VideoFrame:
        log.info("recv called %d",self._queue.qsize())
        arr=await self._queue.get()
        log.info("got frame %s",arr.shape)
        if self._start_time is None:
            self._start_time=time.time()
        else:
            self._timestamp+=int((1/self.fps)*VIDEO_CLOCK_RATE)
        pts=self._timestamp
        time_base=VIDEO_TIME_BASE
        frame=av.VideoFrame.from_ndarray(arr,format="rgb24")
        frame=frame.reformat(format="yuv420p")
        frame.pts=pts
        frame.time_base=time_base
        return frame
    
    def _gst_main(self):
        Gst,GLib=_gst
        encoder=_detect_encoder()
        if _is_wayland():
            log.info("session is wayland, using pipewire")
            node_id=_get_pipewire_node_id()
            caps=f"video/x-raw,format=RGB,width={self.width},height={self.height},framerate={self.fps}/1"
            pipeline_str=(
                f"pipewiresrc path={node_id} do-timestamp=true ! "
                f"videoconvert ! videoscale ! videorate ! "
                f"{caps} ! "
                f"appsink name=sink emit-signals=true max-buffers=2 drop=true sync=false"
            )
        else:
            log.info("session is x11, using ximagesrc")
            pipeline_str=_build_pipeline_string(self.width,self.height,self.fps,_detect_encoder(),self.display)
        log.info("pipeline %s",pipeline_str)
        self._pipeline=Gst.parse_launch(pipeline_str)
        sink=self._pipeline.get_by_name("sink")
        sink.set_property("emit-signals",True)
        sink.set_property("sync",False)
        sink.set_property("max-buffers",2)
        sink.set_property("drop",True)
        sink.connect("new-sample",self._on_new_sample)
        self._pipeline.set_state(Gst.State.PLAYING)
        mainloop=GLib.MainLoop()
        bus=self._pipeline.get_bus()
        bus.add_signal_watch()
        def on_message(bus,message):
            t=message.type
            if t==Gst.MessageType.ERROR:
                err,debug=message.parse_error()
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
            self._pipeline.set_state(Gst.State.NULL)
    
    def _on_new_sample(self,sink):
        Gst,_=_gst
        sample=sink.emit("pull-sample")
        if sample is None:
            return Gst.FlowReturn.ERROR
        buf=sample.get_buffer()
        caps=sample.get_caps()
        structure=caps.get_structure(0)
        w=self.width
        h=self.height
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