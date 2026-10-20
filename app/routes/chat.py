import asyncio
import time
from collections import defaultdict, deque
from urllib.parse import urlsplit

from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from sqlalchemy import select

from app.database import SessionLocal
from app.models import ChatMessage, LoginSession, User, now
from app.security import COOKIE, DB, CurrentUser, token_hash

router = APIRouter(tags=["学习广场"])
peers: dict[WebSocket, str] = {}
recent: dict[str, deque] = defaultdict(deque)


def authenticated(socket):
    with SessionLocal() as db:
        session = db.get(LoginSession, token_hash(socket.cookies.get(COOKIE, "")))
        if not session or session.expires_at.replace(tzinfo=now().tzinfo) <= now():
            return None
        user = db.get(User, session.user_id)
        return {"id": user.id, "name": user.name} if user else None


async def broadcast(data):
    async def send(socket):
        try:
            await asyncio.wait_for(socket.send_json(data), timeout=3)
        except Exception:
            peers.pop(socket, None)

    await asyncio.gather(*(send(socket) for socket in list(peers)))


@router.get("/api/chat/messages")
def messages(user: CurrentUser, db: DB):
    rows = db.execute(select(ChatMessage, User.name).join(User).order_by(ChatMessage.created_at.desc()).limit(50)).all()
    return [
        {"id": m.id, "user_id": m.user_id, "name": name, "content": m.content, "created_at": m.created_at.isoformat()}
        for m, name in reversed(rows)
    ]


@router.websocket("/ws/chat")
async def chat(socket: WebSocket):
    origin = socket.headers.get("origin")
    if origin and urlsplit(origin).netloc != socket.headers.get("host"):
        await socket.close(code=1008)
        return
    user = authenticated(socket)
    if not user:
        await socket.close(code=1008)
        return
    await socket.accept()
    peers[socket] = user["id"]
    await broadcast({"type": "presence", "online": len(set(peers.values()))})
    try:
        while True:
            data = await socket.receive_json()
            if not authenticated(socket):
                await socket.close(code=1008)
                break
            if not isinstance(data, dict):
                continue
            content = data.get("content", "")
            if not isinstance(content, str) or not 1 <= len(content.strip()) <= 2000:
                await socket.send_json({"type": "error", "message": "消息需为 1-2000 字"})
                continue
            timestamps = recent[user["id"]]
            while timestamps and timestamps[0] < time.monotonic() - 10:
                timestamps.popleft()
            if len(timestamps) >= 5:
                await socket.send_json({"type": "error", "message": "发送过快，请稍后再试"})
                continue
            timestamps.append(time.monotonic())
            with SessionLocal() as db:
                message = ChatMessage(user_id=user["id"], content=content.strip())
                db.add(message)
                db.commit()
                payload = {
                    "type": "message",
                    "id": message.id,
                    "user_id": user["id"],
                    "name": user["name"],
                    "content": message.content,
                    "created_at": message.created_at.isoformat(),
                }
            await broadcast(payload)
    except (WebSocketDisconnect, RuntimeError, ValueError):
        pass
    finally:
        peers.pop(socket, None)
        if user["id"] not in peers.values():
            recent.pop(user["id"], None)
        await broadcast({"type": "presence", "online": len(set(peers.values()))})
