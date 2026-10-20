"""Print secret-free configuration; --probe makes small synthetic provider calls."""

import argparse
import asyncio
import json
import sys
from pathlib import Path
from urllib.parse import urlsplit

import httpx

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from app.config import VECTOR_DIMENSIONS, Settings  # noqa: E402
from app.schemas import AgentDraft  # noqa: E402


def safe_endpoint(value):
    parsed = urlsplit(value)
    return {"host": parsed.hostname, "path": parsed.path}


async def probe(settings):
    results = []
    if not settings.ai_api_key.strip():
        return [{"check": "chat", "status": "missing_key"}]
    headers = {"Authorization": f"Bearer {settings.ai_api_key}"}
    endpoint = settings.ai_base_url.rstrip("/") + "/chat/completions"
    async with httpx.AsyncClient(timeout=45) as client:
        try:
            response = await client.post(
                endpoint,
                headers=headers,
                json={
                    "model": settings.ai_model,
                    "temperature": 0,
                    "max_tokens": 256,
                    "response_format": {"type": "json_object"},
                    "messages": [
                        {
                            "role": "user",
                            "content": 'Return ONLY a JSON object with title="Python", '
                            'summary="Study Python", tasks=[{"title":"Read a Python tutorial","minutes":25}].',
                        }
                    ],
                },
            )
            response.raise_for_status()
            body = response.json()
            AgentDraft.model_validate_json(body["choices"][0]["message"]["content"])
            results.append(
                {"check": "structured_plan", "status": "ok", "tokens": body.get("usage", {}).get("total_tokens", 0)}
            )
        except httpx.HTTPStatusError as error:
            results.append(
                {"check": "structured_plan", "status": "http_error", "http_status": error.response.status_code}
            )
        except Exception as error:
            results.append({"check": "structured_plan", "status": type(error).__name__})
        try:
            received = False
            async with client.stream(
                "POST",
                endpoint,
                headers=headers,
                json={
                    "model": settings.ai_model,
                    "messages": [{"role": "user", "content": "Reply only OK"}],
                    "max_tokens": 16,
                    "stream": True,
                    "stream_options": {"include_usage": True},
                },
            ) as response:
                response.raise_for_status()
                async for line in response.aiter_lines():
                    if line.startswith("data: ") and line[6:] != "[DONE]":
                        payload = json.loads(line[6:])
                        choices = payload.get("choices", [])
                        if choices and choices[0].get("delta", {}).get("content"):
                            received = True
            results.append({"check": "streaming_answer", "status": "ok" if received else "no_content"})
        except httpx.HTTPStatusError as error:
            results.append(
                {"check": "streaming_answer", "status": "http_error", "http_status": error.response.status_code}
            )
        except Exception as error:
            results.append({"check": "streaming_answer", "status": type(error).__name__})
        if settings.embedding_api_key.strip():
            try:
                response = await client.post(
                    settings.embedding_base_url.rstrip("/") + "/embeddings",
                    headers={"Authorization": f"Bearer {settings.embedding_api_key}"},
                    json={
                        "model": settings.embedding_model,
                        "input": ["Connection test"],
                        "dimensions": VECTOR_DIMENSIONS,
                    },
                )
                response.raise_for_status()
                vector = response.json()["data"][0]["embedding"]
                if len(vector) != VECTOR_DIMENSIONS:
                    raise ValueError("Embedding dimensions do not match the database schema.")
                results.append({"check": "embedding", "status": "ok", "dimensions": len(vector)})
            except httpx.HTTPStatusError as error:
                results.append(
                    {"check": "embedding", "status": "http_error", "http_status": error.response.status_code}
                )
            except Exception as error:
                results.append({"check": "embedding", "status": type(error).__name__})
        else:
            results.append({"check": "embedding", "status": "not_configured_optional"})
    return results


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--probe", action="store_true", help="Make small model calls; provider may charge tokens.")
    args = parser.parse_args()
    settings = Settings(_env_file=ROOT / ".env")
    report = {
        "env_file": str(ROOT / ".env"),
        "ai_key_configured": bool(settings.ai_api_key.strip()),
        "chat_endpoint": safe_endpoint(settings.ai_base_url),
        "chat_model": settings.ai_model,
        "embedding_key_configured": bool(settings.embedding_api_key.strip()),
        "embedding_endpoint": safe_endpoint(settings.embedding_base_url),
        "embedding_model": settings.embedding_model,
    }
    if args.probe:
        report["checks"] = asyncio.run(probe(settings))
    print(json.dumps(report, ensure_ascii=False, indent=2))
    if args.probe and any(item["status"] not in {"ok", "not_configured_optional"} for item in report["checks"]):
        raise SystemExit(1)


if __name__ == "__main__":
    main()
