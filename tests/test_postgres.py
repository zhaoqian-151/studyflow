import pytest
from sqlalchemy import event, text

from app.config import settings
from app.database import Base, SessionLocal, engine, make_engine
from app.models import Chunk, Document, User
from app.services.rag import semantic_candidates, vector_statement

postgres_only = pytest.mark.skipif(
    engine.dialect.name != "postgresql", reason="Requires isolated PostgreSQL test database"
)


@postgres_only
def test_native_vector_index_and_schema_revision(client, user):
    with engine.connect() as connection:
        assert connection.scalar(text("SELECT extversion FROM pg_extension WHERE extname='vector'"))
        assert connection.scalar(text("SELECT version_num FROM alembic_version")) == "0001_pgvector"
        column_type = connection.scalar(
            text(
                "SELECT format_type(atttypid, atttypmod) FROM pg_attribute "
                "WHERE attrelid='chunks'::regclass AND attname='embedding'"
            )
        )
        assert column_type == "vector(1024)"
        definition = connection.scalar(
            text("SELECT indexdef FROM pg_indexes WHERE indexname='ix_chunks_embedding_hnsw'")
        )
        assert "USING hnsw" in definition and "vector_cosine_ops" in definition


@postgres_only
def test_pgvector_search_isolated_and_vectors_not_selected(client, user, monkeypatch):
    monkeypatch.setattr(settings, "embedding_model", "test-model")
    vector = [1.0] + [0.0] * 1023
    with SessionLocal() as db:
        other = User(email="vector-other@example.com", name="Other", password_hash="not-used")
        db.add(other)
        db.flush()
        for owner in [user["id"], other.id]:
            document = Document(user_id=owner, title="vector doc", content="sample", digest=owner)
            db.add(document)
            db.flush()
            db.add(
                Chunk(
                    user_id=owner,
                    document_id=document.id,
                    position=0,
                    content="sample",
                    embedding=vector,
                    embedding_model="test-model",
                )
            )
        db.commit()
    statements = []

    def capture(_connection, _cursor, statement, _parameters, _context, _many):
        statements.append(statement)

    event.listen(engine, "before_cursor_execute", capture)
    try:
        with SessionLocal() as db:
            result = semantic_candidates(db, user["id"], vector)
            assert len(result) == 1
            assert result[0][1] == pytest.approx(1)
            assert db.get(Chunk, result[0][0]).user_id == user["id"]
    finally:
        event.remove(engine, "before_cursor_execute", capture)
    query = next(statement for statement in statements if "<=>" in statement)
    assert "chunks.embedding," not in query.split("FROM")[0]
    assert "chunks.user_id =" in query and "embedding_model =" in query
    # On tiny corpora the planner may prefer a sequential scan. Verify index eligibility explicitly.
    with engine.connect() as connection:
        connection.execute(text("SET LOCAL enable_seqscan = off"))
        connection.execute(text("SET LOCAL enable_sort = off"))
        query = vector_statement(user["id"], vector).compile(engine, compile_kwargs={"literal_binds": True})
        explanation = "\n".join(connection.execute(text("EXPLAIN " + str(query))).scalars())
        assert "ix_chunks_embedding_hnsw" in explanation


@postgres_only
def test_sqlite_copy_preserves_rows_sessions_json_and_vectors(client, tmp_path):
    from datetime import timedelta

    from app.models import AgentRun, LoginSession, now
    from scripts.migrate_sqlite import copy_and_verify

    source = make_engine("sqlite:///" + (tmp_path / "source.db").as_posix())
    Base.metadata.create_all(source)
    from sqlalchemy.orm import Session

    with Session(source) as db:
        owner = User(
            id="migration-owner", email="migration@example.com", name="迁移用户", password_hash="preserve-hash"
        )
        db.add(owner)
        db.flush()
        db.add(LoginSession(token_hash="x" * 64, user_id=owner.id, expires_at=now() + timedelta(days=1)))
        db.add(AgentRun(user_id=owner.id, goal="测试迁移", steps=[{"tool": "read", "count": 3}], result={"ok": True}))
        doc = Document(id="migration-doc", user_id=owner.id, title="迁移文档", content="保留内容", digest="y" * 64)
        db.add(doc)
        db.flush()
        db.add(
            Chunk(
                id="migration-chunk",
                user_id=owner.id,
                document_id=doc.id,
                position=0,
                content="保留向量",
                embedding=[0.123456789] * 1024,
                embedding_model="test-model",
            )
        )
        db.commit()
    try:
        report = copy_and_verify(source, engine)
        assert all(item["verified"] for item in report.values())
        assert report["users"]["target_rows"] == report["sessions"]["target_rows"] == 1
        with SessionLocal() as db:
            assert db.get(User, "migration-owner").password_hash == "preserve-hash"
            assert len(db.get(Chunk, "migration-chunk").embedding) == 1024
        with pytest.raises(RuntimeError, match="Target has business data"):
            copy_and_verify(source, engine)
    finally:
        source.dispose()
