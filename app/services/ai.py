import json
import logging
import math

import httpx
from fastapi import HTTPException
from sqlalchemy import update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.config import VECTOR_DIMENSIONS, settings
from app.models import AIQuota, AIUsage
from app.services.learning import today

logger = logging.getLogger(__name__)


def reserve_usage(db: Session, user_id: str, kind: str) -> AIUsage:
    day = today()
    # The conditional UPDATE is the concurrency boundary, not an in-process lock.
    if not db.get(AIQuota, (user_id, day)):
        db.add(AIQuota(user_id=user_id, day=day, requests=0))
        try:
            db.flush()
        except IntegrityError:
            db.rollback()
    result = db.execute(
        update(AIQuota)
        .where(AIQuota.user_id == user_id, AIQuota.day == day, AIQuota.requests < settings.ai_daily_request_limit)
        .values(requests=AIQuota.requests + 1)
    )
    if result.rowcount != 1:
        db.rollback()
        raise HTTPException(429, "今日 AI 请求额度已用完，请明天再试")
    usage = AIUsage(
        user_id=user_id, day=today(), kind=kind, model=settings.ai_model if settings.ai_api_key else "local-rules"
    )
    db.add(usage)
    db.commit()
    return usage


def headers(key: str):
    return {"Authorization": f"Bearer {key}", "Content-Type": "application/json"}


async def complete(messages: list, structured=False):
    payload = {"model": settings.ai_model, "messages": messages, "temperature": 0.3, "max_tokens": 1800}
    if structured:
        payload["response_format"] = {"type": "json_object"}
    async with httpx.AsyncClient(timeout=45) as client:
        response = await client.post(
            settings.ai_base_url.rstrip("/") + "/chat/completions", headers=headers(settings.ai_api_key), json=payload
        )
        response.raise_for_status()
        body = response.json()
        return body["choices"][0]["message"]["content"], body.get("usage", {}).get("total_tokens", 0)


async def stream_answer(messages: list):
    async with httpx.AsyncClient(timeout=httpx.Timeout(45, connect=10)) as client:
        async with client.stream(
            "POST",
            settings.ai_base_url.rstrip("/") + "/chat/completions",
            headers=headers(settings.ai_api_key),
            json={
                "model": settings.ai_model,
                "messages": messages,
                "stream": True,
                "temperature": 0.2,
                "max_tokens": 1800,
                "stream_options": {"include_usage": True},
            },
        ) as response:
            response.raise_for_status()
            async for line in response.aiter_lines():
                if not line.startswith("data: "):
                    continue
                if line[6:] == "[DONE]":
                    break
                body = json.loads(line[6:])
                if body.get("usage"):
                    yield {"tokens": body["usage"].get("total_tokens", 0)}
                if body.get("choices"):
                    content = body["choices"][0].get("delta", {}).get("content")
                    if content:
                        yield {"delta": content}


async def embed(texts: list[str]):
    vectors = []
    # DashScope text-embedding-v4 accepts at most 10 texts per request.
    batch_size = 10
    async with httpx.AsyncClient(timeout=45) as client:
        for offset in range(0, len(texts), batch_size):
            batch = texts[offset : offset + batch_size]
            response = await client.post(
                settings.embedding_base_url.rstrip("/") + "/embeddings",
                headers=headers(settings.embedding_api_key),
                json={"model": settings.embedding_model, "input": batch, "dimensions": VECTOR_DIMENSIONS},
            )
            response.raise_for_status()
            data = sorted(response.json()["data"], key=lambda x: x["index"])
            if len(data) != len(batch):
                raise ValueError("Embedding response count mismatch")
            vectors.extend(item["embedding"] for item in data)
    if any(
        len(vector) != VECTOR_DIMENSIONS or not all(isinstance(x, (float, int)) and math.isfinite(x) for x in vector)
        for vector in vectors
    ):
        raise ValueError("Invalid embedding response")
    return vectors
