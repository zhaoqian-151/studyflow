# 开发说明

需要 Python 3.12+。本地使用 Docker Desktop / Docker Engine 运行 PostgreSQL + pgvector，开发启动见 README。

提交修改前运行：

```powershell
.\.venv\Scripts\ruff check app tests scripts migrations
.\.venv\Scripts\ruff format --check app tests scripts migrations
.\.venv\Scripts\python -m pytest -q
.\.venv\Scripts\python scripts/test_postgres.py
node --check app/static/app.js
```

数据库结构修改应新增 Alembic revision，不修改已使用的迁移。运行 `python -m alembic check` 检查模型和结构是否存在差异。

不要提交 `.env`、密钥、数据库、备份、真实文档或会话信息。示例数据使用虚构内容。测试中用替身响应验证模型协议，避免自动测试调用真实付费服务。

涉及 RAG、权限或状态写入的修改，应验证跨用户隔离、模型失败路径、事务回滚与重复提交。轻量布局修改可直接用浏览器验证。

公开发布前可执行 `python scripts/check_public_files.py` 检查源文件集合是否包含当前环境中的密钥，以及常见令牌格式。此检查不能替代人工检查图片和其他附件。
