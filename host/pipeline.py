import logging
import os
import threading
from typing import Optional, Callable
import gi 
gi.require_version("Gst","1.0")
gi.require_version("GstWebRTC","1.0")
gi.require_version("GstSdp","1.0")
from gi.repository import Gst,GstWebRTC,GstSdp,GLib

log=logging.getLogger("pipeline")
Gst.init(None)

def _detect_encoder()->str:
    for element,name in [("nvh264enc","nvenc"),("vaapih264enc","vaapi")]:
        if Gst.ElementFactory.find(element):
            log.info("encoder %s",name)
            return name
    log.info("encoder software")
    return "software"

def _is_wayland()->bool:
    return os.environ.get("XDG_SESSION_TYPE","").lower()=="wayland"

def _get_pipewire_node_id()->int:
    import dbus
    import dbus.mainloop.glib 
    dbus.mainloop.glib.DBusGMainLoop(set_as_default=True)
    bus=dbus.SessionBus()
    portal=bus.get_object("org.freedesktop.portal.Desktop","/org/freedesktop/portal/desktop")
    screencast=dbus.Interface(portal,"org.freedesktop.portal.ScreenCast")
    loop=GLib.MainLoop()
    node_id_result=[None]
    session_path_result=[None]
    create_opts=dbus.Dictionary({
        "handle_token":dbus.String("webstream1"),
        "session_handle_token":dbus.String("webstreamsess1")
    },signature="sv")
    request_path=screencast.CreateSession(create_opts)
    request_obj=bus.get_object("org.freedesktop.portal.Desktop",request_path)
    request_iface=dbus.Interface(request_obj,"org.freedesktop.portal.Request")
    def on_create(response,results):
        if response!=0:
            loop.quit()
            return
        session_path_result[0]=str(results["session_handle"])
        select_opts=dbus.Dictionary({
            "handle_token":dbus.String("webstream2"),
            "types":dbus.UInt32(1),
            "multiple":dbus.Boolean(False),
            "cursor_mode":dbus.UInt32(2)
        },signature="sv")
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
        raise RuntimeError("failed to get pipewire node id")
    return node_id_result[0]

class GSTWebRTCPipeline:
    def __init__(self,width=1920,height=1080,fps=60,display=":0"):
        self.width=width
        self.height=height
        self.fps=fps
        self.display=display
        self._pipeline:Optional[Gst.Pipeline]=None
        self._webrtcbin=None
        self._mainloop:Optional[GLib.MainLoop]=None
        self._thread:Optional[threading.thread]=None
        self._on_offer_cb:Optional[Callable]=None
        self._on_ice_cb:Optional[Callable]=None
    
    def set_on_offer(self,cb:Callable):
        self._on_offer_cb=cb
    
    def set_on_ice(self,cb:Callable):
        self._on_ice_cb=cb
    
    def start(self):
        self._thread=threading.Thread(target=self._run,daemon=True)
        self._thread.start()
    
    def stop(self):
        if self._pipeline:
            self._pipeline.set_state(Gst.State.NULL)
        if self._mainloop:
            self._mainloop.quit()
    
    def set_remote_description(self,sdp:str):
        _,sdpmsg=GstSdp.SDPMessage.new_from_text(sdp)
        answer=GstWebRTC.WebRTCSessionDescription.new(
            GstWebRTC.WebRTCSDPType.ANSWER,sdpmsg
        )
        promise=Gst.Promise.new()
        self._webrtcbin.emit("set-remote-description",answer,promise)
        promise.interrupt()
    
    def add_ice_candidate(self,candidate:str,sdp_mline_index:int):
        self._webrtcbin.emit("add-ice-candidate",sdp_mline_index,candidate)
    
    def _build_pipeline_str(self,encoder:str)->str:
        if _is_wayland():
            node_id=_get_pipewire_node_id()
            src=(
                f"pipewiresrc path={node_id} do-timestamp=true copy-mode=true ! "
                f"videoconvert ! videoscale ! videorate"
            )
        else:
            src=(
                f"ximagesrc display-name={self.display} use-damage=false ! "
                f"video/x-raw,framerate={self.fps}/1 ! "
                f"videoscale ! videorate ! videoconvert"
            )
        if encoder=="nvenc":
            enc=(
                f"video/x-raw,format=NV12,width={self.width},height={self.height},framerate={self.fps}/1 ! "
                f"nvh264enc preset=low-latency-hq rc-mode=cbr bitrate=8000 gop-size=60 ! "
                f"video/x-h264,profile=high,stream-format=byte-stream,alignment=au"
            )
        elif encoder=="vaapi":
            enc=(
                f"video/x-raw,format=NV12,width={self.width},height={self.height},framerate={self.fps}/1 ! "
                f"vaapih264enc rate-control=cbr bitrate=8000 keyframe-period=60 quality-level=7 ! "
                f"video/x-h264,profile=high,stream-format=byte-stream,alignment=au"
            )
        else:
            enc=(
                f"video/x-raw,format=I420,width={self.width},height={self.height},framerate={self.fps}/1 ! "
                f"x264enc tune=zerolatency bitrate=8000 speed-preset=superfast key-int-max=60 ! "
                f"video/x-h264,profile=high,stream-format=byte-stream,alignment=au"
            )
        return=(
            f"{src} ! "
            f"{enc} ! "
            f"h264parse ! "
            f"rtph264pay config-interval=-1 aggregate-mode=zero-latency ! "
            f"application/x-rtp,media=video,encoding-name=H264,payload=96 ! "
            f"webrtcbin name=webrtc stun-server=stun://stun.l.google.com:19302"
        )
    
    def _run(self):
        encoder=_detect_encoder()
        pipeline_str=self._build_pipeline_str(encoder)
        log.info("pipeline %s",pipeline_str)
        self._pipeline=Gst.parse_launch(pipeline_str)
        self._webrtcbin=self._pipeline.get_by_name("webrtc")
        self._webrtcbin.connect("on-negotiation-needed",self._on_negotiation_needed)
        self._webrtcbin.connect("on-ice-candidate",self._on_ice_candidate)
        self._webrtcbin.connect("notify::ice-connection-state",self._on_ice_state)
        self._webrtcbin.connect("notify::connection-state",self.on_conn_state)
        #set sendonly conn
        trans=self._webrtcbin.emit("get-transceiver",0)
        if trans:
            trans.set_property("direction",GstWebRTC.WebRTCRTPTransceiverDirection.SENDONLY)
        bus=self._pipeline.get_bus()
        bus.add_signal_watch()
        bus.connect("message",self._on_bus_message)
        self._pipeline.set_state(Gst.State.PLAYING)
        log.info("gstreamer pipeline playing")
        self._mainloop=GLib.MainLoop()
        self._mainloop.run()
    
    def _on_negotiation_needed(self,webrtcbin):
        log.info("negotiation needed, creating offer")
        promise=Gst.Promise.new_with_change_func(self._on_offer_created)
        webrtcbin.emit("create-offer",None,promise)
    
    def _on_offer_created(self,promise):
        promise.wait()
        reply=promise.get_reply()
        offer=reply.get_value("offer")
        set_promise=Gst.Promise.new()
        self._webrtcbin.emit("set-local-description",offer,set_promise)
        set_promise.interrupt()
        sdp_text=offer.sdp.as_text()
        log.info("offer created")
        if self._on_offer_cb:
            self._on_offer_cb(sdp_text)
    
    def _on_ice_candidate(self,webrtcbin,sdp_mline_index,candidate):
        if self._on_ice_cb:
            self._on_ice_cb(candidate,sdp_mline_index)
    
    def _on_ice_state(self,webrtcbin,pspec):
        state=webrtcbin.get_property("ice-connection-state")
        log.info("ice state %s",state)
    
    def _on_conn_state(self,webrtcbin,pspec):
        state=webrtcbin.get_property("connection-state")
        log.info("connection state %s",state)
    
    def _on_bus_message(self,bus,message):
        t=message.type
        if t==Gst.MessageType.ERROR:
            err,debug=message.parse_error()
            log.error("gstreamer error %s %s",err,debug)
            self._mainloop.quit()
        elif t==Gst.MessageType.EOS:
            log.info("eos")
            self._mainloop.quit()
        elif t==Gst.MessageType.WARNING:
            warn,debug=message.parse_warning()
            log.warning("gstreamer warning %s %s",warn,debug)