import asyncio
import json
import logging
import os
import websockets
from aiortc import RTCPeerConnection, RTCSessionDescription, RTCIceCandidate, RTCConfiguration, RTCIceServer
from aiortc.contrib.signaling import object_from_string, object_to_string

logging.basicConfig(level=logging.INFO)
log=logging.getLogger("agent")

SURL=os.environ.get("SURL","wss://signal.classroom.lat")
ROOM_ID=os.environ.get("ROOM_ID","placeholder")
SHARED_SECRET=os.environ.get("SHARED_SECRET")
ICE_SERVERS=[
    RTCIceServer(urls="stun:stun.l.google.com:19302"),
]

class HostAgent:
    def __init__(self):
        self.ws=None
        self.pc=None
        self.data_channel=None
    
    async def run(self):
        async with websockets.connect(SURL) as ws:
            self.ws=ws
            await self._join()
            async for raw in ws:
                msg=json.loads(raw)
                await self._handle(msg)
    
    async def _join(self):
        await self.ws.send(json.dumps({
            "type":"join",
            "role":"host",
            "roomId":ROOM_ID,
            "secret":SHARED_SECRET
        }))
        log.info("sent join request for room %s",ROOM_ID);
    
    async def _handle(self,msg):
        msg_type=msg.get("type")
        if msg_type=="joined":
            log.info("joined room as host")
        elif msg_type=="client-ready":
            log.info("client is ready, creating offer")
            await self._create_offer()
        elif msg_type=="answer":
            log.info("received answer from client")
            answer=RTCSessionDescription(sdp=msg["sdp"],type="answer")
            await self.pc.setRemoteDescription(answer)
        elif msg_type=="ice":
            if msg.get("candidate") and self.pc:
                cand=msg["candidate"]
                try:
                    await self.pc.addIceCandidate(_ice_from_dict(cand))
                except Exception as e:
                    log.warning("failing to add ice cand %s",e)
        elif msg_type=="client-disconnected":
            log.info("client disconnected")
            await self._cleanup()
        elif msg_type=="error":
            log.error("signaling error %s",msg.get("message"))
    
    