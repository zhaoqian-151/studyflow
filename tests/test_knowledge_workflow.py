import httpx
from fastapi.testclient import TestClient
from sqlalchemy import select

from app.config import settings
from app.database import SessionLocal
from app.main import app
from app.models import Chunk
from app.services import rag


def add_document(client, title, content):
    response = client.post("/api/documents", json={"title": title, "content": content})
    assert response.status_code == 201
    return response.json()["id"]


def test_document_scope_filters_search_and_answer(client, user):
    first = add_document(client, "数据库", "transaction rollback 数据库事务回滚")
    second = add_document(client, "WebSocket", "WebSocket 是双向通信协议。")
    result = client.post("/api/knowledge/search", json={"question": "transaction", "document_id": first}).json()
    assert {item["document_id"] for item in result["sources"]} == {first}
    result = client.post("/api/knowledge/search", json={"question": "transaction", "document_id": second}).json()
    assert result["sources"] == []
    response = client.post("/api/knowledge/ask", json={"question": "transaction", "document_id": second})
    assert "没有检索到相关资料" in response.text
    assert "rollback" not in response.text


def test_scope_and_reindex_enforce_ownership(client, user):
    document_id = add_document(client, "私有资料", "只能由当前用户读取")
    with TestClient(app) as other:
        other.post(
            "/api/auth/register", json={"name": "其他用户", "email": "scope@example.com", "password": "other-pass-123"}
        )
        for route in ["/api/knowledge/search", "/api/knowledge/ask"]:
            assert other.post(route, json={"question": "资料", "document_id": document_id}).status_code == 404
        assert other.post("/api/documents/" + document_id + "/reindex").status_code == 404
    assert client.post("/api/documents/" + document_id + "/reindex").status_code == 409


def test_reindex_keeps_document_and_supports_scoped_vectors(client, user, monkeypatch):
    first = add_document(client, "事务", "数据库事务原子性")
    second = add_document(client, "协议", "WebSocket 双向通信")
    assert client.get("/api/documents").json()[0]["index_status"] == "needs_index"

    async def embeddings(texts):
        return [[1.0] + [0.0] * 1023 for _ in texts]

    monkeypatch.setattr(settings, "embedding_api_key", "fake-key")
    monkeypatch.setattr(rag, "embed", embeddings)
    for identifier in [first, second]:
        response = client.post("/api/documents/" + identifier + "/reindex")
        assert response.status_code == 200
        assert response.json()["index_status"] == "ready"
    documents = client.get("/api/documents").json()
    assert {item["id"] for item in documents} == {first, second}
    assert all(item["index_status"] == "ready" and item["indexed_chunks"] == item["chunks"] for item in documents)
    response = client.post("/api/knowledge/search", json={"question": "语义查询", "document_id": second}).json()
    assert response["retrieval_mode"] == "hybrid"
    assert {item["document_id"] for item in response["sources"]} == {second}
    monkeypatch.setattr(settings, "embedding_model", "new-model")
    assert all(item["index_status"] == "needs_index" for item in client.get("/api/documents").json())


def test_reindex_failure_preserves_existing_index(client, user, monkeypatch):
    identifier = add_document(client, "保留资料", "数据库事务不能因索引错误而丢失")

    async def embeddings(texts):
        return [[1.0] + [0.0] * 1023 for _ in texts]

    monkeypatch.setattr(settings, "embedding_api_key", "fake-key")
    monkeypatch.setattr(rag, "embed", embeddings)
    assert client.post("/api/documents/" + identifier + "/reindex").status_code == 200
    with SessionLocal() as db:
        original_ids = list(db.scalars(select(Chunk.id).where(Chunk.document_id == identifier)))

    async def unavailable(_texts):
        raise httpx.ConnectError("provider unavailable")

    monkeypatch.setattr(rag, "embed", unavailable)
    response = client.post("/api/documents/" + identifier + "/reindex")
    assert response.status_code == 502
    assert "已保留" in response.json()["detail"]
    with SessionLocal() as db:
        assert list(db.scalars(select(Chunk.id).where(Chunk.document_id == identifier))) == original_ids
    assert client.get("/api/documents/" + identifier).json()["content"] == "数据库事务不能因索引错误而丢失"
    assert client.get("/api/documents").json()[0]["index_status"] == "ready"
