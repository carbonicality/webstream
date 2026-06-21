require("dotenv").config();
const {WebSocketServer, WebSocket}=require("ws");

const PORT=process.env.PORT;
const SHARED_SECRET=process.env.SHARED_SECRET;
const wss=new WebSocketServer({port:PORT});

const rooms=new Map(); //roomId->{host:ws,client:ws}

function log(msg,...args) {
    console.log(`[${new Date().toISOString()}] ${msg}`,...args);
}

function send(ws,msg) {
    if (ws && ws.readyState===WebSocket.OPEN) {
        ws.send(JSON.stringify(msg));
    }
}

function sanRID(id) {
    //only allow alphanumeric, hyphens, max 64 chars
    return typeof id==="string" && /^[a-zA-Z0-9\-]{1,64}$/.test(id);
}

wss.on("connection",(ws,req)=>{
    const ip=req.socket.remoteAddress;
    log(`new connection from ${ip}`);
    ws.peer={role:null,roomId:null,authenticated:false};
    ws.on("message",(raw)=>{
        let msg;
        try {
            msg=JSON.parse(raw);
        } catch {
            send(ws,{type:"error",message:"invalid json"});
            return;
        }
        handle(ws,msg);
    });
    
    ws.on("close",()=>{
        handleDisconnect(ws);
    });

    ws.on("error",(err)=>{
        log(`socket error: ${err.message}`);
    });

    ws._authTimeout=setTimeout(()=>{
        if (!ws.peer.authenticated) {
            log(`dropping unauth connection from ${ip}`);
            ws.terminate();
        }
    },5000);
});

function handle(ws,msg) {
    const {type}=msg;
    if (type==="join") {
        const {role,roomId,secret}=msg;
        if (secret!==SHARED_SECRET) {
            send(ws,{type:"error",message:"bad secret"});
            ws.terminate();
            return;
        }
        if (!sanRID(roomId)) {
            send(ws,{type:"error",message:"invalid room id"});
            return;
        }
        if (role!=="host"&&role!=="client") {
            send(ws,{type:"error",message:"role must be host or client"});
            return;
        }
        clearTimeout(ws._authTimeout);
        ws.peer.authenticated=true;
        ws.peer.role=role;
        ws.peer.roomId=roomId;
        if (!rooms.has(roomId)) {
            rooms.set(roomId,{host:null,client:null});
        }
        const room=rooms.get(roomId);
        if (role==="host") {
            if (room.host) {
                send(room.host,{type:"error",message:"replaced by new host"});
                room.host.terminate();
            }
            room.host=ws;
            log(`host joined room ${roomId}`);
            send(ws,{type:"joined",role:"host",roomId});
            if (room.client) {
                send(ws,{type:"client-ready"});
            }
        } else {
            if (room.client) {
                send(ws,{type:"error",message:"room already has a client"});
                return;
            }
            room.client=ws;
            log(`client joined room ${roomId}`);
            send(ws,{type:"joined",role:"client",roomId});
            if (room.host) {
                send(room.host,{type:"client-ready"});
            }
        }
        return;
    }
    if (!ws.peer.authenticated) {
        send(ws,{type:"error",message:"not authenticated"});
        return;
    }
    const room=rooms.get(ws.peer.roomId);
    if (!room) {
        send(ws,{type:"error",message:"room not found"});
        return;
    }

    //offer host->client
    if (type==="offer") {
        if (ws.peer.role!=="host") {
            send(ws,{type:"error",message:"only host can send offer"});
            return;
        }
        if (!room.client) {
            send(ws,{type:"error",message:"no client connected"});
            return;
        }
        log(`relaying offer in ${ws.peer.roomId}`);
        send(room.client,{type:"offer",sdp:msg.sdp});
        return;
    }

    //answer client->host
    if (type==="answer") {
        if (ws.peer.role!=="client") {
            send(ws,{type:"error",message:"only client can send answer"});
            return;
        }
        if (!room.host) {
            send(ws,{type:"error",message:"no host connected"});
            return;
        }
        log(`relaying server in ${ws.peer.roomId}`);
        send(room.host,{type:"answer",sdp:msg.sdp});
        return;
    }

    //ice both dir
    if (type==="ice") {
        const peer=ws.peer.role==="host"?room.client:room.host;
        if (!peer) return;
        send(peer,{type:"ice",candidate:msg.candidate});
        return;
    }
    send(ws,{type:"error",message:`unknown msg type ${type}`});
}

function handleDisconnect(ws) {
    if (!ws.peer.roomId) return;
    const room=rooms.get(ws.peer.roomId);
    if (!room) return;
    if (ws.peer.role==="host") {
        log(`host disconnected from ${ws.peer.roomId}`);
        room.host=null;
        if (room.client) {
            send(room.client,{type:"host-disconnected"});
        }
    } else if (ws.peer.role==="client") {
        log(`client disconnected from ${ws.peer.roomId}`);
        room.client=null;
        if (room.host) {
            send(room.host,{type:"client-disconnected"});
        }
    }
    if (!room.host&&!room.client) {
        rooms.delete(ws.peer.roomId);
        log(`room ${ws.peer.roomId} cleaned`);
    }
}

log(`signaling server running on ws://0.0.0.0:${PORT}`)