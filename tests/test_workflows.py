from datetime import timedelta

from fastapi.testclient import TestClient
from sqlalchemy import select

from app.config import settings
from app.database import SessionLocal
from app.main import app
from app.models import Focus, now


def plan(client):
    return client.post(
        "/api/plans", json={"title": "FastAPI 实战", "tasks": [{"title": "实现鉴权", "minutes": 25}]}
    ).json()


def test_auth_and_logout_revokes_session(client, user):
    assert client.get("/api/auth/me").json()["id"] == user["id"]
    cookie = client.cookies.get("studyflow_session")
    assert client.post("/api/auth/logout").status_code == 204
    assert client.get("/api/auth/me").status_code == 401
    client.cookies.set("studyflow_session", cookie)
    assert client.get("/api/auth/me").status_code == 401
    assert client.post("/api/auth/login", json={"email": user["email"], "password": "wrong-pass"}).status_code == 401
    assert (
        client.post("/api/auth/login", json={"email": user["email"], "password": "strong-pass-123"}).status_code == 200
    )


def test_cross_user_isolation_and_public_room(client, user):
    p = plan(client)
    doc = client.post("/api/documents", json={"title": "私有笔记", "content": "数据库会话应当按请求隔离。"}).json()
    run = client.post("/api/agent/runs", json={"goal": "学习 FastAPI"}).json()
    with TestClient(app) as other:
        assert (
            other.post(
                "/api/auth/register",
                json={"name": "另一个用户", "email": "other@example.com", "password": "strong-pass-456"},
            ).status_code
            == 201
        )
        assert other.get("/api/plans").json() == []
        assert other.patch("/api/tasks/" + p["tasks"][0]["id"], json={"done": True}).status_code == 404
        assert other.delete("/api/plans/" + p["id"]).status_code == 404
        assert other.get("/api/documents/" + doc["id"]).status_code == 404
        assert other.post("/api/agent/runs/" + run["id"] + "/approve").status_code == 404
        assert other.post("/api/knowledge/search", json={"question": "数据库"}).json()["sources"] == []


def test_plan_task_and_checkin_lifecycle(client, user):
    p = plan(client)
    assert p["progress"] == 0
    client.patch("/api/tasks/" + p["tasks"][0]["id"], json={"done": True})
    assert client.get("/api/plans").json()[0]["progress"] == 100
    assert client.post("/api/checkins", json={"note": "今天学习了鉴权"}).json()["duplicate"] is False
    assert client.post("/api/checkins", json={}).json()["duplicate"] is True
    result = client.get("/api/stats").json()
    assert result["checkin_count"] == result["streak"] == result["completed_tasks"] == 1
    assert client.delete("/api/plans/" + p["id"]).status_code == 204
    assert client.get("/api/stats").json()["task_count"] == 0


def test_focus_server_time_idempotency_and_restore(client, user):
    body = {"minutes": 1, "request_id": "test-focus-12345"}
    focus = client.post("/api/focus/start", json=body).json()
    assert client.post("/api/focus/start", json=body).json()["id"] == focus["id"]
    assert client.get("/api/focus/active").json()["id"] == focus["id"]
    assert client.post("/api/focus/start", json={**body, "request_id": "another-focus"}).status_code == 409
    assert client.post("/api/focus/" + focus["id"] + "/complete").status_code == 409
    assert client.get("/api/stats").json()["total_minutes"] == 0
    with SessionLocal() as db:
        row = db.get(Focus, focus["id"])
        row.started_at = now() - timedelta(minutes=2)
        db.commit()
    assert client.post("/api/focus/" + focus["id"] + "/complete").json()["duplicate"] is False
    assert client.post("/api/focus/" + focus["id"] + "/complete").json()["duplicate"] is True
    assert client.get("/api/stats").json()["total_minutes"] == 1
    assert client.get("/api/focus/active").json() is None
    with SessionLocal() as db:
        assert len(db.scalars(select(Focus)).all()) == 1


def test_agent_approval_only_writes_once(client, user):
    run = client.post("/api/agent/runs", json={"goal": "掌握 SQLAlchemy 事务"}).json()
    assert run["status"] == "awaiting_approval"
    assert run["mode"] == "rules"
    assert client.get("/api/plans").json() == []
    first = client.post("/api/agent/runs/" + run["id"] + "/approve").json()
    second = client.post("/api/agent/runs/" + run["id"] + "/approve").json()
    assert first["plan_id"] == second["plan_id"]
    assert second["duplicate"] is True
    assert len(client.get("/api/plans").json()) == 1
    assert client.post("/api/agent/runs/" + run["id"] + "/reject").status_code == 409
    cancelled = client.post("/api/agent/runs", json={"goal": "学习数据库"}).json()
    assert client.post("/api/agent/runs/" + cancelled["id"] + "/reject").status_code == 200
    assert client.post("/api/agent/runs/" + cancelled["id"] + "/approve").status_code == 409


def test_knowledge_search_citations_deletion_and_empty(client, user):
    body = {"title": "事务说明", "content": "事务 transaction 的原子性保证多个写入同时成功或者同时回滚。"}
    doc = client.post("/api/documents", json=body).json()
    assert client.post("/api/documents", json=body).json()["duplicate"] is True
    sources = client.post("/api/knowledge/search", json={"question": "transaction"}).json()["sources"]
    assert sources[0]["document_id"] == doc["id"]
    answer = client.post("/api/knowledge/ask", json={"question": "transaction 是什么"})
    assert "text/event-stream" in answer.headers["content-type"]
    assert "event: sources" in answer.text and "event: done" in answer.text
    assert "未调用语言模型" in answer.text and "[1]" in answer.text
    assert client.delete("/api/documents/" + doc["id"]).status_code == 204
    answer = client.post("/api/knowledge/ask", json={"question": "transaction"})
    assert "没有检索到相关资料" in answer.text
    with SessionLocal() as db:
        from app.models import Chunk

        assert db.scalars(select(Chunk)).all() == []


def test_file_validation_and_upload(client, user):
    assert (
        client.post(
            "/api/documents/upload",
            files={"file": ("sample.md", "# FastAPI\n依赖注入与会话。".encode(), "text/markdown")},
        ).status_code
        == 201
    )
    assert (
        client.post("/api/documents/upload", files={"file": ("image.png", b"not-an-image", "image/png")}).status_code
        == 415
    )
    assert (
        client.post("/api/documents/upload", files={"file": ("bad.pdf", b"not-a-pdf", "application/pdf")}).status_code
        == 422
    )
    assert client.post("/api/documents", json={"title": "空白", "content": "  "}).status_code == 422


def test_csrf_and_input_validation(client, user):
    assert client.post("/api/checkins", json={}, headers={"origin": "https://attacker.example"}).status_code == 403
    assert client.post("/api/plans", json={"title": " ", "tasks": []}).status_code == 422
    assert client.get("/").status_code == 200
    assert client.get("/static/app.js").status_code == 200
    assert client.get("/openapi.json").status_code == 200
    assert client.get("/health").json()["status"] == "ok"


def test_daily_quota(client, user, monkeypatch):
    monkeypatch.setattr(settings, "ai_daily_request_limit", 1)
    assert client.post("/api/agent/runs", json={"goal": "学 Python"}).status_code == 201
    assert client.post("/api/agent/runs", json={"goal": "学 FastAPI"}).status_code == 429


def test_websocket_auth_origin_broadcast_and_limits(client, user):
    import pytest
    from starlette.websockets import WebSocketDisconnect

    with (
        pytest.raises(WebSocketDisconnect),
        client.websocket_connect("/ws/chat", headers={"origin": "https://attacker.example"}),
    ):
        pass
    with client.websocket_connect("/ws/chat") as ws:
        assert ws.receive_json()["type"] == "presence"
        ws.send_json({"content": "今天完成了 FastAPI 学习！"})
        message = ws.receive_json()
        assert message["name"] == user["name"]
        assert message["content"] == "今天完成了 FastAPI 学习！"
        for _ in range(4):
            ws.send_json({"content": "测试消息"})
            assert ws.receive_json()["type"] == "message"
        ws.send_json({"content": "限流验证"})
        assert ws.receive_json()["type"] == "error"
    assert len(client.get("/api/chat/messages").json()) == 5
    client.post("/api/auth/logout")
    with pytest.raises(WebSocketDisconnect), client.websocket_connect("/ws/chat"):
        pass
