# PostgreSQL + pgvector 数据库

## 当前运行方式

- 连接类型：`postgresql+psycopg`，业务库 `studyflow`，用户 `studyflow`。
- 本机地址：`127.0.0.1:5433`，Docker 内端口 5432。
- 容器：`studyflow-postgres-1`，数据卷：`studyflow_studyflow-postgres-data`。
- 密码：随机生成并保存在 `.env` 的 `POSTGRES_PASSWORD`；应用使用 `DATABASE_URL`，不在文档或日志展示密码。
- 向量列：`chunks.embedding vector(1024)`；索引：`ix_chunks_embedding_hnsw`，`vector_cosine_ops`。
- 结构版本：`0001_pgvector`，迁移文件位于 `migrations/versions/`。

访问 `/health` 可确认 `database=postgresql` 和 `vector_store=pgvector`。这会实际执行数据库查询，不只是检查 Python 进程。

本地启动仍使用 `start.ps1`。它会定位 Docker CLI、等待 PostgreSQL 健康、执行 Alembic，然后运行应用。关闭 Python 应用不会删除数据库容器或数据卷。不要使用 `docker compose down -v`，其中 `-v` 会删除持久化数据卷。

## 从旧 SQLite 迁移

迁移前停止应用，确保没有新消息、任务修改等写入，然后执行：

```powershell
.\.venv\Scripts\python scripts/setup_postgres.py
docker compose up -d --wait postgres
.\.venv\Scripts\python scripts/migrate_sqlite.py --activate
.\start.ps1
```

工具执行以下步骤：

1. 通过 SQLite backup API 创建一致性快照，保存到 `data/backups/studyflow-sqlite-<UTC时间>.db`。
2. 创建 PostgreSQL vector 扩展与 Alembic 表结构。
3. 拒绝向已有业务数据的目标库合并或覆盖。
4. 按外键依赖顺序，在一个事务中复制全部业务表，保留 ID、密码散列、登录会话和模型执行记录。
5. SQLite 的无时区时间按原应用的 UTC 存储口径恢复为 UTC timestamptz。
6. 逐表核对行数与非向量字段的 SHA-256 校验和；向量按 float32 存储精度逐元素比较。
7. 任一数据校验失败则回滚数据事务；只有全部成功，才将 `.env` 的 `DATABASE_URL` 切换为 PostgreSQL。
8. 在备份旁生成不含业务正文和密钥的 `.json` 校验报告，保留原 SQLite 文件。

迁移只搬运已有向量，不会调用模型服务或产生向量化费用。没有向量的旧文档仍能 BM25 检索；配置向量服务后，可在知识库对该文档点击「重建向量索引」，保留文档 ID、原文与创建时间，成功后替换索引。重建属于真实向量服务请求并占用当日额度，失败保留旧索引。

## 备份与恢复

升级前的 SQLite 原文件与 `data/backups/` 快照均保留，均被 Git 忽略。备份包含账户和会话等私有数据，不应上传公开仓库。

PostgreSQL 备份可以从本机 Python 执行以下命令（先确保 Docker CLI 位于 PATH；`pg_dump` 不需要本机安装）：

```powershell
docker compose exec -T postgres pg_dump -U studyflow -d studyflow --format=custom --file=/tmp/studyflow.dump
docker compose cp postgres:/tmp/studyflow.dump ./data/backups/studyflow-postgres.dump
```

恢复时先停止应用、备份当前数据库，再在明确指定的恢复目标中使用 `pg_restore`；不要将未审查的恢复命令直接指向现有业务库。

如果刚切换就需要回退，且 PostgreSQL 还没有新增业务写入，可停止应用，将 `.env` 的 `DATABASE_URL` 改回 `sqlite:///./data/studyflow.db` 再启动。PostgreSQL 已产生新写入时，直接回退旧 SQLite 会遗漏新数据，需先做反向数据迁移。不能把旧快照当作双向同步机制。

## 结构迁移与测试

```powershell
.\.venv\Scripts\python -m alembic current
.\.venv\Scripts\python -m alembic upgrade head
.\.venv\Scripts\python -m alembic check
.\.venv\Scripts\python scripts/test_postgres.py
.\.venv\Scripts\python scripts/test_postgres.py --browser
```

测试工具创建独立的随机 `studyflow_test_*` 数据库；只清理它自己创建的数据库，不对业务库执行 drop_all。测试验证原生向量、HNSW 索引、用户隔离、结构迁移、SQLite 数据复制、并发确认和额度约束，以及浏览器业务闭环。

向量检索遵循 [pgvector SQLAlchemy 接口](https://github.com/pgvector/pgvector-python#sqlalchemy)，近似索引与迭代扫描行为参考 [pgvector 官方说明](https://github.com/pgvector/pgvector#iterative-index-scans)。HNSW 不保证精确召回；小数据量时数据库可能选择更便宜的普通索引或顺序扫描，因此不以「每条查询都使用 HNSW」作为正确性标准。词法 BM25 目前仍由 Python 计算。
