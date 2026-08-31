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

## 招聘发现（V0.2 Collector）

- 「招聘发现」页：点击“立即检查招聘更新”→ 逐 source 抓取（source 级状态可见）→ 新材料进入 Inbox；
- 确定性去重：同 source_job_id / 同 canonical URL（含 utm 清理）/ 同指纹自动去重并更新 last_seen；
- 疑似重复（同单位+标题高度相似+URL 不同）只标记不合并，由你决定；
- 关键词过滤（sources.yaml filters）为确定性 pre-filter，命中计数保留在运行摘要；
- Inbox → “AI 解析” → 现有 Preview → 确认 → 正式 Job（Collector 从不直接创建正式 Job）；
- 每个 source 独立事务：一个失败不影响其他 source 已落库数据；
- SSRF 边界沿用 Phase 3 的同一套安全策略（仅公网 IP、逐跳重定向校验、大小限制、Content-Type 验证）；collectors/http.py 为独立实现，策略与 Phase 3 web.py 一致。

## 运行方式（两种模式）

### 日常使用（推荐）：Launcher

```text
双击 dist/PhD Career Radar/PhD Career Radar.exe
```

- Tkinter 启动器：后端状态 / PID / 实时日志 / 启动停止重启 / 自动打开浏览器；
- 后端以**无 --reload** 模式启动，前端由 FastAPI 直接托管构建产物（`frontend/dist`），
  **日常运行不需要 Vite/Node 进程**；
- 关闭启动器 → 优雅终止 → 强制清理整个子进程树（`taskkill /T /F`），不残留进程；
- 启动时自动检测上次异常残留的 PID 并清理；PID 文件含进程创建时间戳，
  **PID 被系统重用时只删文件、绝不误杀无辜进程**；
- 程序资源（前端、默认配置、Prompts）随 exe 内置；**用户配置、.env、SQLite、PID 文件
  都在 exe 同目录**（config/ 与 data/，首次运行自动从内置默认配置种子化；
  更新程序不会覆盖个人权重/地区偏好）。
- 双击 exe 即自动启动后端并打开浏览器；关闭 Launcher 无条件清理进程树，绝不残留。
- **打包版 AI 配置**：把 `.env` 放在 `dist/PhD Career Radar/.env`（exe 同目录）——
  开发模式读项目根 `.env`，打包模式读 exe 旁 `.env`，两者互不影响。

重新打包（全新 clone 可复现的完整流程；`launcher.spec` 已入库，`frontend/dist` 不入库需先构建）：

```bash
cd frontend
npm ci
npm run build

cd ../backend
.venv/Scripts/python -m pip install pyinstaller
.venv/Scripts/python -m PyInstaller launcher.spec --noconfirm --distpath ../dist --workpath ../build
```

### 开发模式（完整保留）

```text
后端：cd backend && .venv/Scripts/python -m uvicorn app.main:app --reload
前端：cd frontend && npm run dev        # http://localhost:5173，/api 代理到 8000
```

日常模式与开发模式互不影响：前端 `npm run build` 后日常模式自动生效。

## 安装与开发运行（依赖准备）

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
- Phase 3 的「AI 解析导入」页在 AI 未配置时会明确提示；URL 抓取失败时提示改用粘贴模式，不做任何反爬对抗。
- URL 抓取安全边界：仅允许公网可路由地址（逐跳重定向校验，拒绝内网/回环），正文/下载均有大小上限；每次导入的 AI 原始输出与用户确认后的 payload 会保存为导入审计记录（job_import_records）。
- 所有 AI 评价保留 `model`、`prompt_version`、`evaluated_at` 与原始 JD（审计性），Prompt 在 `backend/app/ai/prompts/` 按版本管理。

## 配置 Profile / 权重 / 地区

| 文件 | 作用 |
| --- | --- |
| `config/profile.yaml` | 研究方向、技能、Hard Filters（触发即推荐等级 X） |
| `config/scoring.yaml` | 8 维评分权重、推荐等级阈值/封顶规则、地区子权重 |
| `config/regions.yaml` | 地区偏好分层（preferred/acceptable/neutral/avoid） |
| `config/sources.yaml` | V0.2 Collector 来源配置（enabled/type/selector/mapping/关键词过滤；schema_version 2） |

修改权重/偏好后，可在设置页点击“用当前配置重新评估全部岗位”一键批量重评（也可在岗位详情页逐个“重新评估”）。设置保存后配置缓存立即失效，立即生效。

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
| 全部阶段 | **V0.1 完成**：领域模型 / AI 提取 / AI 评估 / 申请 CRM / 风评系统 / 收尾 | ✅ FROZEN |
| V0.2 | Collector MVP：sources.yaml 驱动（JsonApiCollector + HtmlListCollector）、CollectorRun 审计、DiscoveredJob Inbox、确定性去重（source_job_id/canonical URL/fingerprint）与 possible-duplicate 标记、逐 source 事务隔离、AI Extraction bridge（用户确认后才创建正式 Job） | ✅ 完成（8 个真实公开来源接入，二次运行数据库级去重验证） |
| 1 | 基础设施：仓库、后端、前端、数据库、迁移、基础 UI | ✅ 完成 |
| 2 | Job/Organization CRUD、岗位列表/详情、手工导入、去重、版本监控、Dashboard API | ✅ 完成 |
| 2.1 | Domain Model Hardening：高校领域模型加固（AcademicJobDetails、正交聘用维度）、AI 审计快照（配置哈希 + Evidence 关联）、评分覆盖度 score_coverage、Evidence provenance（独立来源/作用域/转载）、Job/Application 状态拆分、薪资标准化字段 | ✅ 完成 |
| 2.1.1 | Consistency fixes：四轴 null→unknown 归一、Risk 证据引用强一致（⊆ 本次评估 ⊆ 真实存在）、effective_risk 由后端派生、reject_high_risk_tenure_track 真正执行、position_nature 完全退休、input_snapshot 强制 | ✅ 完成 |
| 3 | AI 结构化提取：粘贴公告/URL → AI 解析 → 结构化预览（含信息缺口标注）→ 用户逐项确认/修正 → 岗位+高校字段原子入库 | ✅ 完成（Phase 3.1 完整性加固：Preview→Save 字段映射纯函数化并有逐字段测试、provenance 随预览返回、SSRF 边界、大小限制、JobImportRecord 导入审计） |
| 4 | AI 评估：后端自动构造输入快照（Profile+岗位含 JD 正文+地区+分层 Evidence+Hard Filters）→ 同一份内容发给模型并存档 → AI 输出七个维度分（region 由地区引擎独占）/结构化风险/信息缺口/置信度 → 规则引擎计算总分/覆盖度/推荐等级 → 可审计入库；地区分只由用户配置决定、无证据强制风评=null、Evidence 按 job/单位/院系/实验室分层过滤（Phase 4.1/4.1.1 完整性加固：finalize 以 input_snapshot 为唯一事实源——region/reputation/Profile/Hard Filters 均由快照强制，任何调用方无法制造矛盾评估；snapshot 与审计关联强一致、首聘周期入 context、department scope 双非空匹配） | ✅ 完成（需配置 AI；AI 未配置时明确 503，评估数据不一致时 409 拒绝保存） |
| 5 | Career CRM：详情页一键加入 CRM、申请状态流转 API（14 态流转表约束、非法流转 409、applied_at 仅在真正投递时记录、status 显式 null/非法查询参数 422）、看板拖拽改状态 + 列表视图（加载失败透明显示）、next action 本地日期逾期提醒、Dashboard 流程计数联动 | ✅ 完成（时间戳契约：无时区标记的 datetime 一律按 UTC 解析，前端转本地日历日展示） |
| 6 | Evidence & Reputation：Evidence CRUD UI、确定性风评聚合（独立性去重/计数/eligibility）、AI 主题综合、评估集成（eligibility 唯一权威） | ✅ 完成（Phase 6.1/6.1.1 完整性加固详见 DEVLOG） |
| 7 | Polish：设置页可视化（评分权重/地区偏好/Hard Filters 写回 config/*.yaml、备份 .bak）、批量重评（改权重后一键重评全部岗位）、Collector 架构定义（JobCollector 接口 + registry，不实现真实爬虫）、prompt v2 标题修正 | ✅ 完成 |

Phase 2.1 关键设计约定（详见 docs/DEVLOG.md）：

- 高校聘用事实由四根正交轴表达（`establishment_status` / `tenure_status` / `contract_type` / `funding_source`），`position_nature` 降级为 legacy 展示字段。
- 推荐等级（S/A/B/C/D/X）只由后端规则引擎计算；AI 不输出推荐等级/总分/覆盖度。
- 综合评分为 provisional score，必须与 `score_coverage`（评分覆盖度）一起展示；信息不足不压分。
- `confidence` 不封顶推荐等级：信息不足影响"判断有多可信"，不影响岗位价值判断。
- 地区未评价（unrated）返回 null，与"用户中立"（neutral=50）区分。
- 删除岗位保留组织级风评 Evidence（job_id 置空）。

明确不做（V0.1）：自动投递、绕过反爬、自动联系 HR、多用户 SaaS、Redis/Kafka/微服务。

## 核心文档

- `docs/PROJECT_SPEC.md` — V0.1 完整需求规格（含数据模型、评分体系、风评规则、验收标准）
- `docs/DEVLOG.md` — 各阶段开发记录（实现内容/文件/数据库变化/测试/未实现项）
