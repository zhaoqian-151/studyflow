# Summer Checkin 原项目分析

分析对象：`D:\github\summer-checkin-master`。阅读了 README、Prisma schema、路由与组件目录，并重点查看 `src/lib/agent/runtime.ts`、`src/lib/rag/retriever.ts`、`src/lib/rag/chunk.ts`、`src/app/api/focus/sessions/route.ts`。未读取或复制原项目真实 `.env`，不复用原数据库和凭据。

## 原项目业务结构

原项目是 Next.js 全栈学习成长平台，主线包括每日打卡、学习计划、计划任务、番茄钟、文档阅读、学习统计。AI 围绕这些学习数据工作，提供个性化计划、文档拆任务、知识库问答、用户记忆与学习报告。多人聊天室通过独立 WebSocket sidecar 实现。

数据模型分组：

| 领域 | 原模型 |
| --- | --- |
| 身份与会话 | User / Session / Account |
| 学习管理 | Plan / PlanTask / Todo / Checkin / StudyRecord |
| 文档与检索 | Document / KnowledgeDoc / DocumentChunk |
| AI 上下文与执行 | Conversation / ConversationMessage / UserMemory / AgentRun / AgentStep |
| 社交与运营 | ChatMessage / Notification / Announcement / AvatarChange |
| 成本与引导 | TokenUsage / PlanTemplate / DocumentTemplate |

原项目的 `Agent runtime` 采用 Observe → Analyze → Plan → Execute；RAG 通过 PostgreSQL pgvector 执行向量检索；番茄钟使用客户端会话标识去重。

## 新实现的重构方向

1. **保留主业务闭环。** 打卡与专注是两件不同的事：打卡记录坚持，专注记录真实完成的时长。计划进度按任务计算，不把时长当作任务进度。
2. **后端切换到 FastAPI / Python。** 使用依赖注入管理鉴权与 Session，将路由、数据模型、输入模型、服务逻辑拆开。
3. **AI 采用明确可解释的工作流。** 学习数据与用户偏好作为上下文；模型输出经过结构校验，用户确认后再写计划，状态和工具步骤落库。
4. **数据库逐步演进。** 初版使用 SQLite 降低启动成本；当前已升级 PostgreSQL + pgvector，并以 Alembic 管理结构，SQLite 保留为轻量测试与旧数据回退选项。
5. **增加服务端业务约束。** 服务端计时、活动专注唯一索引、每日打卡唯一约束、条件更新确认计划、防止跨用户修改。
6. **重新设计界面。** 使用浅色学习工作台与响应式布局，强调信息清晰和操作闭环。未迁移原 Next.js 组件与 3D 资源。

## 与原项目的对应关系

| 原项目 | StudyFlow |
| --- | --- |
| 小岛与打卡 | 打卡、连续天数、52 周学习日历 |
| 计划与 Todo / PlanTask | Plan / Task，统一任务来源 |
| 番茄钟自动写学习记录 | Focus 状态流转，服务端确认完成 |
| AI Agent + AgentStep | AgentRun + JSON 工具步骤与用户确认 |
| RAG 向量检索 | 可选向量 + BM25 + RRF，默认 BM25 |
| 自动用户记忆 | 用户主动保存偏好并注入上下文 |
| WebSocket sidecar | 同一 FastAPI 进程的 WebSocket 路由 |
| Prisma + PostgreSQL | SQLAlchemy + PostgreSQL / pgvector + Alembic |
| 头像 / 通知 / 公告 / 复杂工作室 | 当前不包含 |

这是一份业务参考基础上的 Python 独立实现，不是把原 Next.js 项目逐文件翻译或宣称原项目全部能力已迁移。
