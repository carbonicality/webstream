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



