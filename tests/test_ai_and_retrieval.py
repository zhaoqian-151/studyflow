import json

import httpx
import pytest

from app.config import settings
from app.services import agent, rag
from app.services.rag import bm25_scores, cosine, split_text


def test_chunking_terminates_and_preserves_content():
    text = "".join(chr(0x4E00 + i) for i in range(1200))
    chunks = split_text(text, size=100, overlap=15)
    assert len(chunks) < 20
    assert all(len(item) <= 100 for item in chunks)
    assert set("".join(chunks)) == set(text)
    assert chunks[0][-15:] == chunks[1][:15]
    assert split_text("   ") == []
    with pytest.raises(ValueError):
        split_text("abc", 10, 10)


def test_bm25_chinese_and_english():
    scores = bm25_scores("数据库事务 transaction", ["数据库事务 transaction 保证一致性", "雨天适合读书"])
    assert scores[0] > scores[1] == 0
    assert cosine([1, 0], [1, 0]) == 1
    assert cosine([1], [1, 2]) == 0


def test_invalid_model_output_falls_back_without_writing_plan(client, user, monkeypatch):
    async def invalid(*args, **kwargs):
        return '{"tasks": [{"title": "bad", "minutes": -10}]}', 20

    monkeypatch.setattr(settings, "ai_api_key", "test-key")
    monkeypatch.setattr(agent, "complete", invalid)
    response = client.post("/api/agent/runs", json={"goal": "学习 RAG"}).json()
    assert response["mode"] == "rules"
    assert response["result"]["warning"]
    assert client.get("/api/plans").json() == []


def test_valid_structured_plan(client, user, monkeypatch):
    async def valid(*args, **kwargs):
        return json.dumps(
            {"title": "RAG 计划", "summary": "先构建检索链路", "tasks": [{"title": "实现 BM25", "minutes": 30}]}
        ), 42

    monkeypatch.setattr(settings, "ai_api_key", "test-key")
    monkeypatch.setattr(agent, "complete", valid)
    response = client.post("/api/agent/runs", json={"goal": "学习 RAG"}).json()
    assert response["mode"] == "llm"
    assert response["result"]["tasks"][0]["minutes"] == 30


def test_embedding_failure_does_not_save_partial_document(client, user, monkeypatch):
    async def failing(texts):
        raise httpx.ConnectError("unavailable")

    monkeypatch.setattr(settings, "embedding_api_key", "test-key")
    monkeypatch.setattr(rag, "embed", failing)
    assert (
        client.post("/api/documents", json={"title": "测试", "content": "向量服务失败时不可保存半份索引"}).status_code
        == 502
    )
    assert client.get("/api/documents").json() == []


def test_hybrid_search_and_embedding_model_mismatch(client, user, monkeypatch):
    async def embed(texts):
        return [[1.0] + [0.0] * 1023 for _ in texts]

    monkeypatch.setattr(settings, "embedding_api_key", "test-key")
    monkeypatch.setattr(rag, "embed", embed)
    client.post("/api/documents", json={"title": "事务", "content": "事务保证数据库一致性"})
    result = client.post("/api/knowledge/search", json={"question": "原子操作"}).json()
    assert result["retrieval_mode"] == "hybrid"
    assert result["sources"]
    monkeypatch.setattr(settings, "embedding_model", "different-model")
    result = client.post("/api/knowledge/search", json={"question": "原子操作"}).json()
    assert result["retrieval_mode"] == "bm25"
    assert result["sources"] == []
