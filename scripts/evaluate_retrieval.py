"""Small reproducible lexical retrieval smoke set; not a production benchmark."""

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from app.services.rag import bm25_scores  # noqa: E402

CORPUS = [
    "数据库事务的原子性保证多个写入操作全部提交或全部回滚，transaction rollback。",
    "RAG 将文档切分为带重叠的 chunk，检索后提供来源引用 citation。",
    "FastAPI 通过 Depends 注入请求级数据库 Session 与当前用户。",
    "SSE 使用 text/event-stream，服务端通过 data 事件逐步输出模型回答。",
    "WebSocket 适合双向实时聊天，需要握手鉴权以及消息限流。",
    "用户隔离要求每次查询都按 user_id 过滤，禁止越权访问他人数据。",
    "番茄钟以服务端时间校验时长，幂等 request_id 避免重复计时。",
    "BM25 是关键词检索，向量支持语义匹配，RRF 融合两个结果排名。",
]
QUESTIONS = [
    ("事务原子性与回滚", 0),
    ("RAG chunk citation", 1),
    ("Depends 注入数据库会话", 2),
    ("SSE 流式回答", 3),
    ("WebSocket 聊天鉴权", 4),
    ("user_id 用户隔离", 5),
    ("番茄钟 request_id 幂等", 6),
    ("BM25 RRF 混合检索", 7),
]
ranks = []
for query, expected in QUESTIONS:
    scores = bm25_scores(query, CORPUS)
    ranking = sorted(range(len(CORPUS)), key=lambda index: scores[index], reverse=True)
    ranks.append(ranking.index(expected) + 1)
print(
    json.dumps(
        {
            "dataset": "8 hand-written smoke questions",
            "corpus_size": len(CORPUS),
            "hit_at_1": sum(rank == 1 for rank in ranks) / len(ranks),
            "hit_at_3": sum(rank <= 3 for rank in ranks) / len(ranks),
            "mrr": sum(1 / rank for rank in ranks) / len(ranks),
            "warning": "小样本检索冒烟测试；不代表真实业务集效果，不评测生成质量。",
        },
        ensure_ascii=False,
        indent=2,
    )
)
