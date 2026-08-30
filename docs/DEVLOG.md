# 开发日志（DEVLOG）

> 按PROJECT_SPEC 第四十节要求：每个 Phase 记录已实现内容、修改文件、数据库变化、测试结果、未实现功能。未实现的功能不会被描述为已完成。

---

## Phase 1 — Foundation（2026-08-30 完成）

### 已实现

- 仓库初始化（git，main 分支），`docs/PROJECT_SPEC.md` 保存原始规格。
- 后端：FastAPI 应用骨架、SQLAlchemy 2 数据模型、Pydantic v2 Schema、Alembic 迁移、配置层（`.env` + `config/*.yaml`）、AI Provider 抽象（OpenAI-compatible，未配置时显式降级）。
- 前端：Vite + React 18 + TypeScript + Tailwind CSS v4 应用骨架，侧边栏布局、明暗主题切换、基础 UI 组件（shadcn 风格手写，未引入 Radix）。
- 数据库：SQLite（`data/phd_career_radar.db`），首次迁移已生成并执行。

### 关键文件

- 后端：`backend/app/{main.py, core/{config.py,fingerprint.py}, db/{base.py,session.py}, models/*, schemas/*, ai/{provider.py,schemas.py,prompts.py}, ai/prompts/*.md}`
- 前端：`frontend/{package.json,vite.config.ts,tsconfig.json}, frontend/src/{main.tsx,App.tsx,index.css}, frontend/src/components/{Layout.tsx,ui.tsx}`
- 配置：`config/{profile,scoring,regions,sources}.yaml`、`.env.example`、`README.md`

### 数据库变化

- 迁移 `e2bcd6b51463_initial_schema`：创建 `organizations`、`jobs`、`job_evaluations`、`evidence`、`applications`、`job_versions` 共 6 张业务表。

### 测试与检查

- `pytest`：43 passed（指纹/去重、评分、硬性过滤、AI JSON 解析、状态流转、API 接口、版本捕获）。
- `ruff check`：All checks passed。
- `uvicorn` 启动冒烟：health / 创建岗位 / 列表 / dashboard / 重复提交 409 均通过（中文内容正常）。

### 未实现（按计划属于后续 Phase）

- AI 粘贴解析（Phase 3）、AI 评估（Phase 4）、申请 CRM（Phase 5）、Evidence UI 与风评聚合（Phase 6）、设置页可视化编辑（Phase 7）、Collector 爬虫架构（Phase 7+）、Docker 部署配置。

---

## Phase 2 — Job CRUD（2026-08-30 完成）

### 已实现

- **单位 CRUD**：`/api/organizations` 列表（搜索）/ 新建 / 详情 / 更新 / 删除（有岗位时 409 保护）。
- **岗位 CRUD**：`/api/jobs` 列表（关键词、类别、状态、省/市、单位、推荐等级、风险、可信度、分数区间筛选；综合分/最新发现/截止/地区/风评排序；分页）、新建、详情（聚合最新评估/版本历史）、部分更新、删除。
- **去重**：创建时计算指纹（单位+院系+职位+城市归一化，城市去"市"后缀）+ 同单位公告文本相似度（≥0.92）双通道检测；冲突返回 409 并指出疑似重复对象，用户确认后可强制创建。
- **版本监控**：`description_raw / salary_text / salary_min / salary_max / deadline` 变更自动保存 `JobVersion`（旧内容快照 + 变更清单），详情页 History 展示"旧值 → 新值"。
- **用户决策字段**：`user_rating / user_priority / user_notes` 独立于 AI 评估，详情页可直接编辑。
- **Dashboard API**：今日新增 / 待查看 / 高匹配（S/A）/ 重点关注 / 准备投递 / 已投递 / 面试中 / Offer 计数 + Top Jobs（按综合分 Top 5）。
- **前端页面**：Dashboard、岗位库（筛选/排序/分页）、新增岗位（含重复确认交互）、岗位详情（九个 Tab + 我的判断区）、单位库、设置占位页。

### 关键文件

- 后端：`app/api/routes/{jobs.py,organizations.py,dashboard.py}`、`app/services/{jobs.py,scoring.py,hard_filters.py,regions.py,dashboard.py}`、`app/schemas/{job.py,organization.py,evaluation.py,dashboard.py,evidence.py}`
- 前端：`src/pages/{DashboardPage,JobsPage,JobNewPage,JobDetailPage,OrganizationsPage,SettingsPage}.tsx`、`src/services/api.ts`、`src/types.ts`、`src/lib/utils.ts`
- 测试：`tests/{test_fingerprint,test_dedup,test_scoring,test_hard_filters,test_jobs_api,test_organizations_api,test_job_versions,test_ai_schemas,test_job_status}.py`

### 数据库变化

- 无（沿用 Phase 1 迁移；本阶段只新增 API 与服务层）。

### 测试与检查

- `pytest`：43 passed。
- `ruff check`：All checks passed。
- 前端 `npm run build`（tsc 类型检查 + vite 构建）：通过（见本次提交记录）。

### 明确未实现

- 粘贴公告 → AI 解析 → 用户确认保存（Phase 3，接口预留 `POST /jobs/{id}/evaluate` 当前返回 503 明确提示）。
- 申请状态 Kanban / Evidence UI / 风评聚合 / 设置可视化（Phase 5-7）。
- 数据模型已包含 `applications`、`evidence`、`job_evaluations` 表，供后续 Phase 直接使用。

---

## 环境说明

- 开发机 Python 为 3.11.6（D:\Python\python.exe），规格推荐 3.12+；所用依赖均兼容 3.11，`pyproject.toml` target-version=py311。后续升级 3.12 无需改代码。
- PATH 中的默认 `python` 是 MinGW 构建（32 位，POSIX 布局 venv），已改用官方 Windows Python 创建 `backend/.venv`；README 中的命令均基于 `.venv/Scripts/`。
- `alembic.ini` 保持 ASCII（中文 Windows 下 configparser 以 GBK 读取，含中文会报 UnicodeDecodeError）。

---

## Phase 2.1 — Domain Model Hardening（2026-08-30 完成）

依据用户对 main 分支的代码审查意见执行，只修正领域模型/评分语义/AI 审计/Evidence provenance/状态边界，**未开始 Phase 3**。

### 已实现（8 项）

1. **AcademicJobDetails**（一对一扩展表）：高校专用事实正式持久化 —— 编制/长聘/合同/经费四根正交轴 + 聘期考核 + 论文/基金/教学/行政要求 + 职业身份 + 科研资源 + 硕博招生 + 收入住房（原文保存）。bool 字段一律允许 null（未知）。
2. **PositionNature 重构**：降级为 legacy/派生展示字段（保留读取兼容）；新增 EstablishmentStatus / TenureStatus / ContractType / FundingSource 四个独立枚举。"预聘 + 固定期限合同"等组合事实可同时表达。
3. **JobEvaluation 审计增强**：新增 provider、profile/scoring/region 三组配置快照+SHA-256 哈希（stable_json_hash）、input_snapshot_json、risk_items_json；新增 EvaluationEvidence 关联表（UNIQUE(evaluation_id, evidence_id)）记录"当时用了哪些证据"。
4. **评分语义修正**：新增 score_coverage（0-100，已评分维度权重占比）；compute_total 明确为 provisional score；未知地区 unrated → None（不再自动 50）；移除 confidence cap 默认逻辑（信息不足不降级，confidence 独立展示）。
5. **推荐等级单一权威**：AI Schema 删除 recommendation_level/total_score/score_coverage；新增 risk_level + 结构化 risk_items（type/severity/reason/evidence_ids）；最终等级只由后端规则引擎（services/evaluation.py finalize_evaluation）计算。
6. **Evidence provenance**：新增 source_author / is_firsthand / independence_key / repost_of_evidence_id（自引用 FK）/ stance / scope_level / scope_name。
7. **状态拆分**：Job 只保留信息筛选状态（new/reviewing/shortlisted/ignored/closed，JobDisposition）；applied/interviewing/offer 等求职流程状态归 Application 唯一负责；Dashboard 的投递/面试/Offer 改查 Application（面试中 = 笔试+两轮面试）。
8. **薪资标准化**：新增 salary_currency / salary_period / guaranteed_salary_min/max / variable_salary_min/max / advertised_total_min/max；legacy salary_min/max 保留兼容。Hard Filter 薪资规则改为仅当 currency=CNY 且 period=year 且有 guaranteed_salary_max 时触发，单位不明不触发。

### 数据库变化 / Migration

- Revision `4a48e7786118_phase_2_1_domain_model_hardening`（前驱 e2bcd6b51463）：
  - 新表 `academic_job_details`（job_id UNIQUE FK）、`evaluation_evidence`（组合唯一）
  - `job_evaluations` +10 列（审计快照/哈希/coverage/risk_items）
  - `evidence` +7 列（provenance/scope/stance，stance/scope_level 带 unknown 默认值）
  - `jobs` +8 列（薪资标准化）
  - 全程 batch_alter_table 兼容 SQLite；已验证 upgrade → downgrade → upgrade roundtrip。
- Job.status 旧值兼容说明：当前数据库无存量数据（开发库已重建），API 层已限制新写入只接受 JobDisposition 五值；DB 列保持字符串，旧值可读。未做业务含义猜测式回填。

### 修改的核心文件

- 模型：`models/{enums,academic_job_details,evaluation_evidence,job,evidence,evaluation}.py`
- Schema：`schemas/{academic,job,evidence,evaluation}.py`、`ai/schemas.py`（含 ReputationTopicOut 严格化、RiskItem、mutable defaults → default_factory）
- 服务：`services/{scoring,regions,hard_filters,jobs,dashboard}.py`、新增 `services/evaluation.py`（规则引擎）、`core/hash.py`
- API：`api/routes/jobs.py`（academic-details GET/PATCH upsert、删除走服务层保留证据）
- Prompt：三个 prompt 文件移除 {{xxx}} 假占位符，改为"用户消息为 JSON 对象"契约；评估 prompt 输出 risk_items 并禁止输出推荐等级
- 前端：`types.ts`、`lib/utils.ts`（状态枚举/学术标签）、`JobDetailPage.tsx`（覆盖度展示+信息覆盖不足提示、结构化风险条目、高校字段卡片，未知统一"未知 / 待确认"）

### 测试 / lint / build

- pytest：**83 passed**（新增 test_academic_details_api / test_evaluation_audit / test_evidence_provenance / test_regions，更新 scoring/hard_filters/job_status/ai_schemas/jobs_api）
- ruff：All checks passed
- 前端 npm run build（tsc + vite）：通过
- alembic upgrade head + API 冒烟（创建/academic-details upsert/非法枚举 422/dashboard）：通过

### 明确未实现

- **Phase 3 AI Extraction 未实现**（无粘贴解析 API、无 URL 抓取）
- **Phase 4 AI Evaluation 流程未实现**（finalize_evaluation 规则引擎已就绪并有测试，但不存在任何真实 AI 调用路径）
- **Phase 5 CRM UI 未实现**（Dashboard 已按 Application 统计，但无 Application API/UI）
- **Phase 6 风评聚合未实现**（Evidence provenance 字段与 Reputation 严格 Schema 已就绪，无聚合服务）
- AcademicJobDetails 的前端编辑 UI（当前仅 API 维护 + 详情页展示）

---

## Phase 2.1.1 — Consistency Fixes（2026-08-30 完成）

依据第二轮代码审查执行的小补丁：3 个 P0 一致性问题 + 6 个 P1/P2。**未开始 Phase 3。**

### P0 修复

1. **四轴 null → unknown（P0-1）**：`PATCH /academic-details` 对 establishment/tenure/contract/funding 显式传 null 时归一化为 `"unknown"`（数据库列 NOT NULL，不再存在 null/unknown 两套未知）；`JobExtractionOut` 四轴改为默认 `"unknown"` 的非空 Literal。测试 `test_axis_null_coerced_to_unknown`。
2. **Risk 证据引用强一致（P0-2）**：`finalize_evaluation()` 强制校验 `risk_items.evidence_ids ⊆ 本次 evaluation evidence_ids ⊆ 数据库真实存在的 Evidence`，任一脱链引用抛 ValueError 拒绝保存，保证结论可追溯到本次评估实际使用的证据。测试 2 个（拒绝 + 正常追溯）。
3. **risk_level 与 risk_items 一致（P0-3）**：新增 `compute_effective_risk()` —— 有效风险 = max(AI 声明 risk_level, 各 risk_items.severity)，由后端派生；推荐封顶与存储的 risk_level 均使用有效值。"条目 critical + overall medium" 无法再绕过封顶。测试 2 个。

### P1 修复

4. **reject_high_risk_tenure_track 真正执行**：`check_hard_filters()` 新增 risk_level 参数；开关开启 + `tenure_status=tenure_track` + 有效风险 high/critical → X。测试覆盖 5 种边界。
5. **position_nature 完全退休**：从 `JobCreate`/`JobUpdate` 移除（API 不再接受写入，旧数据读取兼容保留）；Hard Filter 不再读取该字段（PI 经费只看 `funding_source`，postdoc 只看 `job_category`）；前端新增岗位表单移除该输入。
6. **input_snapshot 强制**：`finalize_evaluation()` 的 input_snapshot 改为必填参数，忘传直接报错而非静默入库（审计复现强约束）。

### P2 修复

7. 删除岗位确认文案改为"评估、申请记录与历史版本会一并删除；风评证据会保留（与岗位解绑）"。
8. Dashboard 面试中口径加入 `hr`（written_test/interview_1/interview_2/hr）。
9. Dashboard Top Jobs 综合分下方显示覆盖度（<40% 显示 ⚠ 提示），不再隐藏信息完整度。
10. 前端 tenure_track 文案改为"预聘 / Tenure-track"，不再与非升即走（独立字段）混用。

### 测试 / lint / build

- pytest：**90 passed**（新增/调整 7 个测试：四轴归一、证据脱链拒绝、不存在证据拒绝、effective risk、危险条目不可藏于 medium、开关生效、HR 口径等）
- ruff：All checks passed
- 前端 npm run build：通过

### 明确未实现

- **Phase 3 AI Extraction 未实现；Phase 4 AI Evaluation 流程未实现；Phase 5 CRM UI 未实现；Phase 6 风评聚合未实现。**
- Evaluation Audit 详情接口（暴露 config hash / input snapshot / evidence links）未做 —— 审计数据已完整入库，接口留给下一阶段。
- 本阶段无数据库 Schema 变化，无新 migration。

---

## Phase 3 — AI Extraction（2026-08-30 完成）

含审查要求的 Step 0 三项清理。完整链路：**粘贴公告/URL → AI 结构化解析 → 结构化预览（逐项可编辑 + 信息缺口标注）→ 用户确认 → Job + AcademicJobDetails 原子入库**。

### Step 0 清理（审查意见落实）

1. `position_nature` 从 `JobExtractionOut` 与 extraction Prompt 彻底删除 —— 新 AI 流程不再产生 legacy 信息；前端 `JobCreateInput` 同步移除。
2. 写入 Schema `extra="forbid"`（JobCreate / JobUpdate / AcademicJobDetailsUpdate）：未知字段显式 422，不再静默忽略。测试 `test_unknown_field_rejected_with_422`。
3. 详情页顶部 legacy "岗位性质" Badge 替换为四轴聘用摘要（`employmentSummary`：非事业编 · 预聘 / Tenure-track · 固定期限 · 学校经费 · 非升即走）；列表页删除"性质"列；`POSITION_NATURE_LABELS` 从前端删除。

### 已实现

- **`POST /api/jobs/extract-preview`**：粘贴文本或 URL →（URL 时 `services/web.py` 抓取公开网页并粗提取正文，失败/正文过短 → 422 提示改用粘贴，不做反爬对抗）→ 调用 `provider.extract_job()`（Pydantic 校验 + 失败重试一次）→ 返回结构化预览 + provider/model/prompt_version + source_text。**不写数据库**。
- **Provider 依赖注入**：新增 `api/deps.py get_ai_provider`，测试可注入 FakeProvider；未配置 → 503 明确提示。
- **原子保存**：`JobCreate` 支持嵌套 `academic_details`（`extra="forbid"`、四轴显式 null 归一 unknown）；`create_job` 一次事务写 Job + AcademicJobDetails，去重/版本逻辑不变。
- 错误语义分层：请求校验 422 → AI 未配置 503 → AI 调用失败 502。
- **前端 `/jobs/import`**：粘贴/URL 双模式 → 解析后分组预览（基本信息 / 聘用体系四轴 / 考核与发展 / 科研资源 / 学生资源 / 收入与住房），全部字段可编辑确认；AI 标记的 unknowns 以警示卡显示；409 重复确认交互；保存后跳转详情页。
- 岗位库页提供「手工新增 / AI 解析导入」双入口。

### 数据库变化

- 无（沿用 Phase 2.1 Schema，无新 migration）。

### 测试 / lint / build

- pytest：**101 passed**（新增 test_extraction_api：503/422/502 路径、FakeProvider 注入、URL 抓取成功/失败、嵌套 academic_details 入库与 null 归一、html_to_text；另加 extra=forbid 测试）
- ruff：All checks passed
- 前端 npm run build：通过
- 浏览器端到端验证：导入页渲染、粘贴解析触发、AI 未配置透明报错。

### 明确未实现

- **Phase 4 AI Evaluation 流程未实现**（规则引擎已就绪）。
- URL 导入为最简公开网页抓取，未针对任何具体招聘平台做适配（ Collector 属 Phase 7）。
- 预览暂不逐字段展示"原文依据"高亮（unknowns 已标注；原文始终保留在 description_raw 与预览页）。
- input_snapshot 的键结构强校验（profile/job/evidence/hard_filters/region 键）与"由评估服务自动构造快照"按审查意见归入 Phase 4。
