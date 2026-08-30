# PhD Career Radar

面向博士生的个人求职监控与决策工作台。核心目标**不是自动海投**，而是：

> 自动收集、整理和评估招聘信息，减少人工刷招聘网站的时间，把真正值得关注的岗位筛选出来，最终由用户本人决定是否申请。

原则：**AI 负责搜集、结构化、比较、发现风险和辅助判断；用户负责最终职业选择和投递决策。** AI 不编造未知信息（显示 `未知/待确认`），事实与网络风评分级（Evidence A/B/C/D）保存。

## 功能截图

（占位：V0.1 Dashboard / 岗位列表 / 岗位详情截图，待 UI 稳定后补充）

## 架构

```text
前端 React + TypeScript + Vite + Tailwind（localhost:5173）
        │  /api（Vite 代理）
        ▼
后端 FastAPI + SQLAlchemy 2 + Pydantic v2（localhost:8000）
        │
        ├── SQLite（data/phd_career_radar.db，可切换 PostgreSQL）
        ├── 配置层 config/*.yaml（Profile / 评分权重 / 地区偏好 / 来源）
        └── AI Provider 抽象（OpenAI-compatible API，可替换）
```

目录结构：

```text
phd-career-radar/
├── backend/
│   ├── app/
│   │   ├── main.py            # FastAPI 入口
│   │   ├── api/routes/        # jobs / organizations / dashboard
│   │   ├── core/              # 配置加载、指纹/去重
│   │   ├── db/                # engine、session、Base
│   │   ├── models/            # Job / Organization / JobEvaluation / Evidence / Application / JobVersion
│   │   ├── schemas/           # Pydantic 请求/响应模型
│   │   ├── services/          # 业务逻辑（岗位服务、评分、硬性过滤、地区）
│   │   └── ai/                # LLM Provider 抽象 + Prompt 版本管理 + AI 输出 Schema
│   ├── alembic/               # 数据库迁移
│   ├── tests/                 # pytest
│   ├── requirements.txt
│   └── pyproject.toml         # ruff/pytest/mypy 配置
├── frontend/
│   └── src/                   # pages / components / services / types
├── config/                    # profile.yaml / scoring.yaml / regions.yaml / sources.yaml
├── data/                      # SQLite 数据库（不入库）
├── docs/PROJECT_SPEC.md       # 原始需求规格
└── README.md
```

## 安装与开发运行

要求：Python 3.11+（推荐 3.12）、Node 18+。

### 后端

```bash
cd backend
python -m venv .venv
.venv/Scripts/pip install -r requirements.txt          # Windows
# Linux/macOS: .venv/bin/pip install -r requirements.txt

# 数据库迁移（首次必须执行；数据库默认落在 ../data/ 下）
.venv/Scripts/python -m alembic upgrade head

# 启动开发服务器（http://localhost:8000，API 文档 /docs）
.venv/Scripts/python -m uvicorn app.main:app --reload
```

### 前端

```bash
cd frontend
npm install
npm run dev        # http://localhost:5173，/api 自动代理到 8000
```

### 测试与检查

```bash
cd backend
.venv/Scripts/python -m pytest          # 单元/接口测试
.venv/Scripts/python -m ruff check app tests

cd frontend
npm run build                            # tsc 类型检查 + 产物构建
```

## 配置 AI

复制 `.env.example` 为 `.env`，填写 OpenAI-compatible API 信息：

```env
LLM_PROVIDER=openai_compatible
LLM_API_KEY=sk-xxx
LLM_BASE_URL=https://api.openai.com/v1
LLM_MODEL=gpt-4o-mini
```

- AI 未配置时系统仍可正常使用手工功能，AI 相关操作返回明确错误，不会伪造评估结果。
- 所有 AI 评价保留 `model`、`prompt_version`、`evaluated_at` 与原始 JD（审计性），Prompt 在 `backend/app/ai/prompts/` 按版本管理。

## 配置 Profile / 权重 / 地区

| 文件 | 作用 |
| --- | --- |
| `config/profile.yaml` | 研究方向、技能、Hard Filters（触发即推荐等级 X） |
| `config/scoring.yaml` | 8 维评分权重、推荐等级阈值/封顶规则、地区子权重 |
| `config/regions.yaml` | 地区偏好分层（preferred/acceptable/neutral/avoid） |
| `config/sources.yaml` | 未来 Collector 来源（V0.1 未启用） |

修改权重/偏好后，可在设置中触发“重新评估全部岗位”（Phase 4+ 提供 UI）。

## 数据库迁移

```bash
# 修改 backend/app/models/ 后生成迁移
python -m alembic revision --autogenerate -m "describe change"
python -m alembic upgrade head
python -m alembic downgrade -1     # 回退一步
```

## Roadmap（开发阶段状态）

| Phase | 内容 | 状态 |
| --- | --- | --- |
| 1 | 基础设施：仓库、后端、前端、数据库、迁移、基础 UI | ✅ 完成 |
| 2 | Job/Organization CRUD、岗位列表/详情、手工导入、去重、版本监控、Dashboard API | ✅ 完成 |
| 3 | AI 结构化提取（粘贴 JD → 结构化岗位 → 用户确认 → 保存） | ⬜ 未实现 |
| 4 | AI 评估（Profile + Job + Evidence → 结构化评估、推荐等级、风险/可信度） | ⬜ 未实现（Provider/Schema 已就绪） |
| 5 | Career CRM（Shortlist、申请状态 Kanban、next action） | ⬜ 未实现（数据模型已建） |
| 6 | Evidence CRUD UI 与风评聚合、可信度呈现 | ⬜ 未实现（数据模型已建） |
| 7 | 设置页、筛选增强、测试补全、文档完善、Collector 架构 | ⬜ 未实现 |

明确不做（V0.1）：自动投递、绕过反爬、自动联系 HR、多用户 SaaS、Redis/Kafka/微服务。

## 核心文档

- `docs/PROJECT_SPEC.md` — V0.1 完整需求规格（含数据模型、评分体系、风评规则、验收标准）
- `docs/DEVLOG.md` — 各阶段开发记录（实现内容/文件/数据库变化/测试/未实现项）
