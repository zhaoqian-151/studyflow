import json
from concurrent.futures import ThreadPoolExecutor

import httpx
from sqlalchemy import select

from app.config import settings
from app.database import SessionLocal
from app.models import AIUsage
from app.services import ai


def test_concurrent_quota_reservation(client, user, monkeypatch):
    monkeypatch.setattr(settings, "ai_daily_request_limit", 1)
    with ThreadPoolExecutor(max_workers=2) as executor:
        futures = [executor.submit(client.post, "/api/agent/runs", json={"goal": "并发规划测试"}) for _ in range(2)]
        statuses = sorted(item.result().status_code for item in futures)
    assert statuses == [201, 429]
    assert client.get("/api/capabilities").json()["requests_today"] == 1


def test_concurrent_plan_approval(client, user):
    run = client.post("/api/agent/runs", json={"goal": "验证事务与并发确认"}).json()
    with ThreadPoolExecutor(max_workers=2) as executor:
        futures = [executor.submit(client.post, "/api/agent/runs/" + run["id"] + "/approve") for _ in range(2)]
        statuses = [item.result().status_code for item in futures]
    assert 200 in statuses
    assert all(status in {200, 409} for status in statuses)
    assert len(client.get("/api/plans").json()) == 1


def test_real_provider_stream_adapter_and_usage(client, user, monkeypatch):
    client.post("/api/documents", json={"title": "事务", "content": "数据库 transaction 事务保证原子性。"})
    monkeypatch.setattr(settings, "ai_api_key", "fake-secret")
    real_client = httpx.AsyncClient

    def handle(request):
        assert request.headers["authorization"] == "Bearer fake-secret"
        payload = json.loads(request.content)
        assert payload["stream"] is True
        chunks = [
            {"choices": [{"delta": {"content": "事务保证"}}]},
            {"choices": [{"delta": {"content": "原子性。[1]"}}]},
            {"choices": [], "usage": {"total_tokens": 73}},
        ]
        content = (
            "".join("data: " + json.dumps(chunk, ensure_ascii=False) + "\n\n" for chunk in chunks) + "data: [DONE]\n\n"
        )
        return httpx.Response(200, text=content, headers={"content-type": "text/event-stream"})

    transport = httpx.MockTransport(handle)
    monkeypatch.setattr(ai.httpx, "AsyncClient", lambda **kwargs: real_client(transport=transport, **kwargs))
    response = client.post("/api/knowledge/ask", json={"question": "transaction"})
    assert "事务保证" in response.text and "原子性。[1]" in response.text
    assert "event: done" in response.text
    with SessionLocal() as db:
        assert db.scalar(select(AIUsage).where(AIUsage.kind == "knowledge")).tokens == 73


def test_stream_provider_failure_keeps_sources(client, user, monkeypatch):
    client.post("/api/documents", json={"title": "资料", "content": "transaction 原子性"})
    monkeypatch.setattr(settings, "ai_api_key", "fake-secret")
    real_client = httpx.AsyncClient
    transport = httpx.MockTransport(lambda request: httpx.Response(503))
    monkeypatch.setattr(ai.httpx, "AsyncClient", lambda **kwargs: real_client(transport=transport, **kwargs))
    response = client.post("/api/knowledge/ask", json={"question": "transaction"})
    assert "event: sources" in response.text
    assert "event: error" in response.text
    assert "event: done" not in response.text
    assert "fake-secret" not in response.text


def test_chunked_body_limit(client, user):
    def pieces():
        for _ in range(7):
            yield b"x" * 1024 * 1024

    response = client.post(
        "/api/documents/upload", content=pieces(), headers={"content-type": "application/octet-stream"}
    )
    assert response.status_code == 413


def test_task_order_is_preserved(client, user):
    titles = ["先学习依赖注入", "然后实现鉴权", "最后写测试"]
    response = client.post(
        "/api/plans", json={"title": "有序计划", "tasks": [{"title": title} for title in titles]}
    ).json()
    assert [task["title"] for task in response["tasks"]] == titles


def test_embedding_batches_fit_dashscope_limit(monkeypatch):
    import asyncio

    real_client = httpx.AsyncClient
    batches = []

    def handle(request):
        inputs = json.loads(request.content)["input"]
        batches.append(inputs)
        assert len(inputs) <= 10
        # Return reversed items to verify ordering is recovered from index.
        return httpx.Response(
            200,
            json={
                "data": [
                    {"index": index, "embedding": [float(text), 1.0] + [0.0] * 1022}
                    for index, text in reversed(list(enumerate(inputs)))
                ]
            },
        )

    transport = httpx.MockTransport(handle)
    monkeypatch.setattr(ai.httpx, "AsyncClient", lambda **kwargs: real_client(transport=transport, **kwargs))
    vectors = asyncio.run(ai.embed([str(i) for i in range(23)]))
    assert [len(batch) for batch in batches] == [10, 10, 3]
    assert [vector[0] for vector in vectors] == [float(i) for i in range(23)]
