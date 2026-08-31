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

---

## Phase 3.1 — Extraction Integrity Fixes（2026-08-30 完成）

依据第三轮审查执行：修复"AI 预览里已正确解析的信息，在用户确认保存后丢失或串错"的三个 P0，以及 SSRF 边界、导入审计等。**Phase 3 由此冻结。**

### P0 修复

1. **Preview → Save 字段映射纯函数化（P0-1/P0-2）**：新增 `frontend/src/lib/extraction.ts` —— `seedValuesFromPreview()` 与 `buildSavePayload()` 共用同一张字段映射表（CORE_TEXT / DATE / AXIS / BOOL / NUMBER / ACADEMIC_TEXT 六组确定性键），按 Schema 逐字段类型转换（contract_years 保持 number、纯数字文本保持 string、四轴默认 unknown）。此前丢失的六个基本字段（country / posted_at / deadline / employment_type / degree_requirement / experience_requirement）全部进入 预览 UI → 保存 payload → 数据库。vitest 9 个测试覆盖"完整样例 → 不修改 → 保存 payload 逐字段核对"，并验证用户修改可覆盖 AI 结果。`npm test` 已加入 package.json。
2. **URL provenance 串单修复（P0-3）**：`ExtractionPreviewOut` 新增 `source_type` / `source_url`，前端删除 `usedUrl` 状态 —— 保存时来源信息取自 Preview 本身，文本模式绝不可能残留上一次的 URL。配套 `import_audit.ingestion_method` 也由 preview 派生。

### P1 修复

3. **SSRF 边界**：`services/web.py` 重写 —— 目标主机必须解析到公网可路由 IP（`assert_public_host` 拒绝 loopback/私网/链路本地/保留地址），**每跳重定向都重新校验**（手动跟随，最多 5 跳）；流式下载限制 5MB。测试覆盖 6 类内网地址 + 3 个内网 URL。
4. **大小限制**：粘贴正文与解析正文上限 100k 字符（`MAX_TEXT_CHARS`，超限 422"请缩小到具体招聘公告"）；网页下载上限 5MB。
5. **JobImportRecord 导入审计**（新表 + migration `d281b97059b5`，roundtrip 已验证）：每次 AI 导入保存 ingestion_method / source_url / provider / model / prompt_version / **AI 原始解析输出（extraction_json）** / **用户确认后的最终 payload（confirmed_payload_json）** / source_text_hash。`JobCreate` 新增可选 `import_audit`，随岗位原子入库；"是 AI 解析的还是我手改的"从此可回答。前端保存时自动提交。

### P1/P2 修复

6. **Prompt ↔ Schema 一致性**：Prompt 补齐 country / employment_type / degree_requirement / experience_requirement；新增一致性测试（Schema 每个字段名必须出现在 Prompt 文本，position_nature / annual_salary 不得回流）。
7. **annual_salary 删除**（孤立字段：AI 可生成但无持久化去向），Schema/Prompt/前端类型同步移除；salary_text / fixed_income / performance_income 已足够表达。
8. **text/url 互斥**：`ExtractionRequest` model_validator 强制二选一，都不传或同时传都是 422。

### 数据库变化 / Migration

- 新表 `job_import_records`（migration `d281b97059b5_phase_3_1_job_import_audit`，前驱 4a48e7786118，upgrade/downgrade roundtrip 已验证）。其余无变化。

### 测试 / lint / build

- pytest：**106 passed**（新增 SSRF、互斥、超长、导入审计持久化、完整样例逐字段核对、Prompt 一致性）
- vitest：**9 passed**（前端映射纯函数逐字段测试）
- ruff：All checks passed；前端 npm run build：通过
- 浏览器验证：导入页渲染正常；API 冒烟确认 both/neither 均返回 422

### 明确未实现

- **Phase 4 AI Evaluation 流程未实现**；导入审计暂无读取 API/UI（数据已完整入库）；URL 抓取仍未适配具体招聘平台（Collector 属 Phase 7）；DNS rebinding 的 TOCTOU 残余风险已用"每跳重校验"缓解，文档在此如实说明。

---

## Phase 4 — AI Evaluation（2026-08-30 完成）

按审查要求的顺序实现：Step 0 硬化 → Step 1 Context → Step 2 AI 调用 → Step 3 确定性 finalize → Step 4 审计 UI。**评估从第一天起即可复现、可审计。**

### Step 0 硬化（含上轮遗留尾巴）

- 全部 AI 输出 Schema（JobExtractionOut / EvaluationScores / RiskItem / JobEvaluationOut / ReputationTopicOut / ReputationSummaryOut）`extra="forbid"`：模型多输出任何字段（如已删除的 annual_salary）都会触发校验失败并自动重试一次，不再被静默吞掉。
- input_snapshot 强校验：必须是非空 dict 且含 `profile / job / region / evidence / hard_filters` 五键，缺任何键拒绝保存。
- Evidence 作用域校验：用于评估的证据必须属于当前岗位或其单位，跨单位证据 → 409 拒绝。
- Extraction Prompt 枚举对齐 Schema（EUR/GBP、day/hour）；`job_import_records.extraction_json` 文档措辞修正为"经 Pydantic 校验后的 normalized 输出（用户修改前）"。

### Step 1 Context（同一份内容，两条去向）

`build_evaluation_context(db, job)` 自动构造真实 AI 输入五键 dict：
- `profile`：config/profile.yaml 快照
- `job`：岗位结构化信息 + 高校四轴事实
- `region`：地区层级 + 基准分（unrated → null，不猜测）
- `evidence`：作用域内证据（含等级/立场/第一手/独立来源键，供风评维度参考）
- `hard_filters`：用户硬性过滤配置

**同一份 dict 既作为 user message 发给模型，又原样存入 `input_snapshot_json`** —— 数据库里保存的和模型实际看到的保证一致（测试断言 `provider.seen_contexts == [evaluation.input_snapshot_json]`）。

### Step 2+3 AI 调用与确定性落库

- `POST /api/jobs/{id}/evaluate`：Provider 注入（未配置 503）→ `evaluate_job()` 编排 → AI 输出（Pydantic 校验 + 重试一次）→ region 维度合成（AI 分优先，缺失时用地区基准分）→ `finalize_evaluation()` 确定性计算（effective risk / provisional total / score_coverage / hard filters → recommendation）→ JobEvaluation + EvaluationEvidence 同事务落库。
- 错误语义：请求/作用域/快照问题 409，AI 未配置 503，AI 调用或输出失败 502 —— 不伪造结果。
- 权责不变：AI 只产出维度分/风险/信息缺口/置信度；推荐等级只由后端规则引擎计算。

### Step 4 审计 UI

详情页 AI Evaluation 页签：
- 未评估时显示"开始 AI 评估"按钮与流程说明；AI 未配置时透明显示 503 错误。
- 评估后新增 **"本次评价依据（Evaluation Audit）"卡片**：Provider/模型/Prompt 版本/评估时间/覆盖度、profile/scoring/region 三个配置哈希、使用的 Evidence 清单（等级 + 编号 + 主张；无证据时明确说明"风评维度将以 null 呈现，不猜测"）；并提供"重新评估"。
- API 输出增加 `profile_hash / scoring_config_hash / region_config_hash / evidence_items`。

### 数据库变化

- 无新表/新列（审计结构在 Phase 2.1 已就绪，本轮直接启用）；无新 migration。

### 测试 / lint / build

- pytest：**110 passed**（新增：五键快照校验、跨单位证据拒绝、region 基准分合成、evaluate_job 全链路审计断言、AI Schema forbid、作用域构造）
- vitest：9 passed；ruff：All checks passed；前端 build：通过
- 浏览器验证：Evaluation 页签评估入口与 AI 未配置透明报错（503）。

### 明确未实现

- **Phase 5 Career CRM UI 未实现**（Application 模型与 Dashboard 统计已就绪）。
- 批量重评（修改权重后一键重评全部岗位）未实现——单岗位"重新评估"已可用，批量属 Phase 7 设置页。
- input_snapshot 的读取 API/UI（当前数据完整入库，展示配置哈希即可满足 V0.1 审计）。
- 风评聚合（ReputationSummary 调用）未接入流程，属 Phase 6。

---

## Phase 4.1 — Evaluation Integrity Fixes（2026-08-31 完成）

依据第五轮审查执行：修复四个直接影响评分可信度的 P0 与四个 P1。**无新 migration。**

### P0 修复

1. **Job Context 补齐 organization 与 JD 正文（P0-1）**：`_job_context_dict()` 新增 `organization{id,name,organization_type}`、`description_raw`、`description_clean`、`source_url` —— `fit / research_resources / long_term` 维度从此有真实依据（此前模型甚至不知道岗位属于哪所大学、看不到公告正文）。测试断言 context 与数据库逐字段一致。
2. **Evidence 作用域真正分层（P0-2）**：新增 `evidence_in_scope()` 共享规则，context 构造与 finalize 校验共用 ——
   - 绑定当前岗位 → 纳入（无论 scope 标注）；
   - 绑定**其他**岗位 → 排除（job_id 优先于 organization_id，同校不串岗位）；
   - 只挂单位时按 scope_level 分层：`organization`/`unknown` 纳入（unknown 不猜具体院系）、`department` 仅当 scope_name 归一化等于当前院系（同校医学院证据不再串入化学学院）、`lab` 不纳入（Job 无实验室身份，不猜）。
   测试覆盖 7 种组合；context 按 Evidence.id 排序，snapshot 输入稳定。
3. **无 Evidence 强制 reputation=null（P0-3）**：编排层 `evaluate_job()` 在 `context["evidence"]` 为空时强制 `reputation=null`（选择强制 null 而非报错，不因模型犯错导致整个评估失败）——UI 的"风评维度将以 null 呈现"从此是后端保证而非 Prompt 恳求。测试：AI 给 80 → 落库 null。
4. **region 只由用户配置决定（P0-4）**：AI 的 region 分一律忽略（含 unrated 场景），`region_score = context["region"]["score"]`——AI 擅自给未评价城市打 75 分的回流问题封死。测试：AI 75 被忽略（unrated→None），配置基准 90 时 AI 75 仍被忽略。

### P1 修复

5. **审计 Evidence 冻结自 input_snapshot**：`evidence_items` 优先读 `input_snapshot_json["evidence"]`（模型当时实际看到的文本），Evidence 后续编辑不再使历史审计漂移；旧数据无 snapshot 时回退实时内容。测试：评估后修改 claim，API 仍返回旧文本。
6. **重新评估失败提示**：详情页已有评估时"重新评估"失败也会在审计卡上方显示错误（与首次评估一致）。
7. **Evidence context 排序**：`ORDER BY Evidence.id`（真正的 selection/ranking 属 Phase 6）。
8. **AI 关键字段必填**：`risk_level / confidence / scores` 去掉默认值——模型漏字段触发重试，而不是被 Pydantic 补成 medium（"没输出风险" ≠ "明确判断中风险"）。测试覆盖三个字段逐一缺失。

### 数据库变化

- 无新表/新列，无新 migration。

### 测试 / lint / build

- pytest：**114 passed**（新增 P0×4 与 P1×4 对应测试）；vitest：9 passed；ruff：All checks passed；前端 build：通过。

### 明确未实现

- **Phase 5 Career CRM UI 未实现**；批量重评、input_snapshot 读取 API/UI、风评聚合（Phase 6）、Evidence selection/ranking（Phase 6）未实现。

---

## Phase 4.1.1 — Final Audit Invariants（2026-08-31 完成）

第六轮审查后的极小 hotfix，四项不变量封死后 **Phase 4 冻结**。无新 migration。

1. **Snapshot Evidence ↔ EvaluationEvidence 强一致（核心）**：`finalize_evaluation()` 强制
   `input_snapshot["evidence"] 的 ID 集合 == provided evidence_ids 集合`，不一致直接拒绝保存。
   从此"模型实际看到的 Evidence = input_snapshot 冻结的 Evidence = EvaluationEvidence 审计关联"
   三者恒等——即使未来批量重评等服务直接调用 finalize，也不可能产生"快照无证据但审计关联了
   #123"这种逻辑上不可能成立的历史。测试覆盖正反两个方向。
2. **first_contract_period 进入 Evaluation Context**：此前合同年限/中期/聘期考核都在，
   唯独首聘周期遗漏；现在随 academic_details 进入 context，全链路测试断言 `"3+3 年"` 出现在
   模型输入中。
3. **department scope 双非空才可匹配**：`scope_name` 或 `job.department` 任一为空即不匹配，
   不再出现"双方都归一成空串反而判为匹配"的边界。四个边界组合有测试。
4. **region 从 AI Schema/Prompt 彻底删除**：`EvaluationScores` 只剩七个 AI 维度
   （fit/career_stability/research_resources/compensation/reputation/workload/long_term），
   region 由后端 Region Engine（用户配置）唯一计算 —— 与 recommendation_level 同样的
   "单一权威"处理。Schema forbid 下模型连输出 region 的入口都不存在；Prompt 已同步。
   顺带：前端导入页薪资周期下拉补齐 day/hour，与 Schema 枚举完全对齐。

### 数据库变化

- 无。

### 测试 / lint / build

- pytest：**117 passed**（新增 snapshot/provided 双向不一致、department 四边界、region 字段禁用等）
- vitest：9 passed；ruff：All checks passed；前端 build：通过

### 明确未实现

- **Phase 5 Career CRM UI 未实现**；批量重评、input_snapshot 读取 API/UI、风评聚合（Phase 6，
  含 unknown scope 的"情报线索 vs 计量输入"策略）未实现。

---

## Phase 4.1.1 收尾 — finalize 单一事实源（2026-08-31 完成）

第七轮审查指出的最后一个底层不变量：`finalize_evaluation()` 此前仍信任调用方传入的
`dimension_scores["region"]`、`dimension_scores["reputation"]` 与 `profile` 参数——
正常编排路径正确，但未来批量重评等服务绕过 `evaluate_job()` 直接调用 finalize 时，
仍可制造"快照说 A、落库是 B"的矛盾评估。本轮让 finalize 自身成为唯一可信边界：

1. **region_score ← input_snapshot["region"]["score"]**：调用方传入的 region 分一律被
   snapshot 值覆盖（测试：snapshot None + 调用方 80 → 落库 None；snapshot 80 + 调用方 999 → 落库 80）。
2. **reputation 强制下沉到 finalize**：`input_snapshot["evidence"]` 为空时 finalize 自身
   强制 reputation=null（测试：调用方传 80 → 落库 None），编排层不再承担该职责。
3. **Profile / Hard Filters ← input_snapshot["profile"]**：删除 finalize 的 `profile` 参数
   （彻底消除"快照是 A、参数是 B"的可能），`check_hard_filters` 与配置哈希审计全部使用
   snapshot 中的 Profile（测试：snapshot 携带 reject_pi_funded 开关 → X 生效且
   profile_hash 按快照 Profile A 计算）。

至此完整不变量成立：

> AI 实际输入 = input_snapshot = Evidence links = Region score 来源 = Profile/Hard Filters 来源 = 审计配置快照

`test_finalize_computes_total_coverage_recommendation` 已按用户意见修正——不再人为通过
dimension_scores 传 region=80（那是在锁定错误行为），改为 snapshot 的 region.score=80 并
额外断言调用方误传 999 会被覆盖。

### 数据库变化

- 无。

### 测试 / lint / build

- pytest：**120 passed**（新增三个收尾不变量测试）；vitest：9 passed；ruff：All checks passed；前端 build：通过。

### 明确未实现

- **Phase 5 Career CRM UI 未实现**；批量重评、input_snapshot 读取 API/UI、风评聚合与
  unknown scope 策略（Phase 6）未实现。

---

## Phase 5 — Career CRM（2026-08-31 完成）

原则：**不修改 Phase 2-4 的核心事实/评分模型，CRM 只消费评估结果**。Application 模型与
Dashboard 流程计数在 Phase 2.1 已就位，本轮无新表/无 migration。

### 已实现

- **API**（`/api/applications`、`/api/jobs/{id}/application`）：
  - 创建（每岗位一条，重复 409；可直接指定起始状态）、按岗位查询、部分更新、删除（岗位与评估保留）；
  - **状态流转校验**：PATCH status 受 `APPLICATION_STATUS_TRANSITIONS` 约束——正向推进合法、
    非法跳转/终止态出边 → 409 并附"允许的目标状态"提示；进入 contacting/applied 自动记录投递时间；
  - 列表：status 过滤、q 搜索（next_action/备注/联系人 + 岗位标题/院系）、排序（更新时间/行动日期/优先级）；
  - 响应携带 `allowed_next_statuses`（驱动 UI 只显示合法流转）与 job brief（标题/单位/评分/推荐等级）；
  - 写入 Schema `extra="forbid"`。
- **前端申请 CRM 页**（侧边栏「申请 CRM」）：
  - **看板视图**：14 个状态列横向滚动，卡片（岗位/单位/评分/next action，逾期标红）HTML5 拖拽改状态；
    流转被后端拒绝时显示错误并回滚显示；
  - **列表视图**：表格 + 编辑入口；
  - **编辑面板**：状态（只列当前 + 合法目标）、优先级、next action/日期、联系人、简历/Cover Letter 版本、备注、删除。
- **岗位详情 Application 页签**：创建申请（加入 CRM）、申请状态与 next action 摘要、
  一键流转按钮（仅合法目标）、非法流转错误提示、"在申请 CRM 中打开"。
- **Dashboard 联动**：preparing/applied/interviewing/offer 计数卡点击跳转申请 CRM（数据源在 Phase 2.1 已切到 Application）。

### 数据库变化

- 无（applications 表 Phase 1 已建；无新 migration）。

### 测试 / lint / build

- pytest：**131 passed**（新增 CRM 12 项：唯一性 409、404、非法跳转 409 含提示、终止态封死、
  全字段更新、列表过滤/搜索/排序、按岗位查询、删除后岗位保留可重建、Dashboard 联动、extra=forbid）
- vitest：9 passed；ruff：All checks passed；前端 build：通过
- 浏览器端到端：详情页创建申请 → 流转到入围 → CRM 看板卡片就位 → 编辑 next action 保存生效。

### 明确未实现

- **Phase 6 风评聚合未实现**（Evidence UI/聚合/unknown scope 策略）。
- Kanban 拖拽暂无乐观更新（失败由 invalidate 回滚）；申请状态无历史时间线（规格未要求，可作 Phase 7 增强）。
- 批量重评、设置页可视化（Phase 7）。

---

## Phase 5.1 — CRM Integrity Fixes（2026-08-31 完成）

依据第七轮审查执行，五个问题修复。**无 migration，不触碰 Phase 2-4。**

### P0

- **applied_at 语义修正**：只在真正进入 `applied` 时记录投递时间（contacting 洽联不再误写——
  此前"9 月 1 日联系 PI"会被永久写成"9 月 1 日投递"）；创建时仅当直接以 applied 建档才记录；
  直接以 interview/offer 等历史终态建档 → applied_at 保持 null（未知比猜"现在"更正确，后续可
  显式编辑）。
- **假测试修正**：原断言走不存在的 `GET /applications/{id}`（404 JSON is not None 假通过），
  改为断言 PATCH 返回值：contacting → null、preparing → null、applied → 非 null、
  interview/offer 后时间戳不变；另加"历史终态建档 → null"用例。

### P1

- **PATCH `status: null` → 422**：`ApplicationUpdate` model_validator 基于显式字段集校验
  （省略 = 不修改；null = 422），不再走到 NOT NULL 列的 IntegrityError/500。与 AcademicDetails
  四轴、extra="forbid" 的"显式失败"哲学一致。
- **查询失败透明显示**：申请 CRM 列表（isError → 红色错误卡，不再伪装成"还没有申请记录"）与
  岗位详情 Application 页签（loading/error/null/有申请四态分离）都区分了失败与空数据。
- **查询参数严格枚举**：`status` 用 ApplicationStatusLiteral、`sort` 用 Literal 三值，
  非法值 422，不再静默落默认排序。

### P2

- **本地日期边界**：新增 `localToday()`（浏览器本地时区的今天）用于看板逾期判断；
  `formatDate()` 区分 date-only（原样）与 timestamp（明确转本地日历日）——非 UTC 时区午夜
  附近的"逾期漏标"与投递日期展示歧义消除。

### 数据库变化

- 无。

### 测试 / lint / build

- pytest：**133 passed**（applied_at 语义链路、status null 422、非法查询参数 422；假测试已重写）
- vitest：9 passed；ruff：All checks passed；前端 build：通过

### 明确未实现

- **Phase 6 风评聚合未实现**；Kanban 拖拽乐观更新、申请状态历史时间线（可选 Phase 7）、
  applied_at 显式编辑、批量重评与设置页（Phase 7）未实现。

---

## Phase 5.1 收尾 — Timestamp 序列化契约（2026-08-31 完成）

第八轮审查发现的最后一处：SQLite 不保留 tzinfo，API 返回的 datetime 是 naive 字符串
（如 `2026-08-30T17:00:00`），浏览器 `new Date()` 会误当本地时间——UTC+8 用户会把
UTC 17:00（本地已是次日 01:00）错显示成当天。

修复（纯前端契约，不碰数据库、不碰冻结的 Phase 2-4）：

- `parseBackendTimestamp()`：**所有无时区标记的 timestamp 一律视为 UTC**（补 `Z` 解析）；
  已带 `Z` / `±HH:MM` 偏移的时间戳（如未来切 PostgreSQL）原样解析，不重复追加。
- `formatDate()` 接入：date-only（YYYY-MM-DD）原样展示；timestamp 按 UTC 契约解析后转
  本地日历日；非法字符串保守原样返回。
- vitest 纯函数测试 8 项（断言基于 toISOString/字符串比较，与运行机器时区无关）：
  naive 按 UTC、Z 不重复追加、+08:00/+0800 正确换算、naive 与 Z 同一时刻、date-only 不偏移、
  naive 与带 Z 展示一致、非法串原样、空值占位。

### 数据库变化

- 无。未来切 PostgreSQL 时 API 自带偏移量，正则自动识别，契约无需改动。

### 测试 / lint / build

- pytest：133 passed；vitest：**17 passed**（9 → 17）；ruff：All checks passed；前端 build：通过。

---

## Phase 6 — Evidence & Reputation（2026-08-31 完成）

模式沿用 Phase 4 已验证的边界：**Evidence 事实资产 → 确定性统计 → AI 主题叙述综合 → 确定性 eligibility → Reputation UI**。三件必须锁死的事全部落实。

### 已实现

1. **Evidence CRUD API**（`/api/evidence`）：岗位挂载（自动继承单位）/ 组织级挂载、部分更新（EvidenceUpdate 全可选）、删除（**同步清理 EvaluationEvidence 关联**，不留悬挂引用）；列表按单位/岗位/类别过滤。完整 provenance 字段全面开放：独立来源键、第一手/转述、转载关系、立场、作用域层级+名称、等级、原文摘录。
2. **确定性风评统计**（`services/reputation.py`，纯计算不调 AI）：
   - **independence_key 去重**：同 key 同源（含转载跟随源头）；无 key 自成一源；
   - 逐主题（11 类）统计：正/负来源数（组级 stance，混杂归负面——保守）、独立来源数、等级分布、时间跨度；
   - **eligibility 门槛**：独立源 ≥ 2 且等级含 A/B → 可进入定量评分；否则仅情报参考（原因文案明确）；
   - **unknown scope 降级**：不自动升级为"全校通用证据"，降为情报线索单独列出；lab 级同理；岗位级证据不进校级统计；
   - department 过滤：限定院系时校级证据仍纳入、不匹配的院系证据降为线索。
3. **AI 主题综合（prompt v2）**：`POST /organizations/{id}/reputation/synthesize` —— 后端统计（statistics）+ 证据给 AI，AI 输出 `ReputationSynthesisOut`（**只有 topic + conclusion**，无任何计数字段，extra=forbid）；后端把结论合并进确定性报告。AI 未配置 503、失败 502。GET 报告永远纯确定性、不需要 AI。
4. **Evaluation 集成**：context 中每条证据带 `eligible_for_reputation_scoring` 标志（unknown → false）；finalize 的 reputation guard 扩展——无 eligible 证据时强制 reputation=null（旧快照无标志按 True 兼容）。测试：unknown 证据 + AI 硬给 85 → 落库 null；eligible 证据 + AI 70 → 正常保留。
5. **前端**：详情页 Evidence 页签（岗位级 + 单位级两组证据、创建表单含全部 provenance 字段、删除）；Reputation 页签（逐主题卡片：正/负/独立源数、等级、时间跨度、eligibility 徽标 + 原因、AI 结论、情报线索列表、"生成 AI 综合分析"按钮含 503 透明报错）。

### 数据库变化

- 无新表/新列（reputation 报告按需计算不持久化）；无新 migration。

### 测试 / lint / build

- pytest：**147 passed**（新增 14 项：CRUD、关联清理、去重/转载/stance 分组、eligibility 三档、unknown/lab/岗位级降级、department 过滤、AI 合并、503、纯确定性 GET、评估 guard 正反例、AI schema forbid）
- vitest：17 passed；ruff：All checks passed；前端 build：通过
- 浏览器端到端：证据创建 → 聚合报告渲染（逐主题 eligibility 与线索）→ AI 综合入口。

### 明确未实现

- **Phase 7 设置页可视化、批量重评、Collector 架构、历史时间线等收尾项未实现**。
- Evidence selection/ranking（大量证据时的挑选策略）留 Phase 7/优化阶段——当前按 id 排序全量纳入。
- unknown scope 的语义（本阶段：线索）如需进一步细分（例如允许用户手动提升）留待真实使用反馈。

---

## Phase 6.1 — Reputation Integrity Fixes（2026-08-31 完成）

依据第九轮审查执行。核心目标一句话：**一个主题在 Reputation 页被判定"不可定量"，则无论通过什么路径，都不能进入 reputation_score。** 无 migration，不触碰 Phase 2-5 模型。

### P0 修复

1. **eligibility 唯一权威（P0-1）**：新增 `eligible_reputation_evidence_ids(db, org, dept)` ——
   从真正的主题聚合结果取 eligible 主题的 evidence_ids 并集。Evaluation context 的
   `eligible_for_reputation_scoring` 改为 `ev.id in eligible_ids`（此前是复制版规则
   `scope_level != "unknown"`，导致"知乎单帖 org 级 C"在 Reputation 页不可定量、
   却能在 Evaluation 解锁 reputation 分的矛盾）。finalize 对新 snapshot 缺标志默认 False。
   回归测试四件套：单 C → null；双独立 C → null；B+C 双独立源 → eligible 保留；
   job 级 A 事实 → null（官方"聘期六年"不能解锁"风评 70 分"）。
2. **院系不串证据（P0-2）**：`collect_evidence` 语义修正——department=None 只统计
   organization scope（院系级证据全部降为线索"未指定院系"）；department=X 只合并匹配院系。
   前端 ReputationTab 传 `department={job.department}`，GET/synthesize/query key 均含
   department。测试：化学学院岗位的医学院证据永不进入统计/评估。
3. **已参与评估的 Evidence 禁止删除（P0-3）**：DELETE 前检查 EvaluationEvidence——
   被引用 → 409"评估审计链必须保留"；未引用 → 204。**撤销了 Phase 6 初版的
   "删除时清理关联"逻辑**（那会破坏 Phase 4 冻结不变量"input_snapshot = links"）。
   Evidence 编辑仍允许（历史文字已冻结在 input_snapshot）。
4. **repost canonical 跨主题追根（P0-4）**：`canonical_source_keys()` 基于单位**全量**
   证据做追根，不再限于当前主题子集——"原帖 category=other 不在统计子集"时，其两个
   转载不会再被误拆成 2 个独立来源（测试：independent=1）。新增创建/更新校验：
   转载目标不存在/自身/循环/跨单位 → 422（RepostChainError）。
5. **Evidence 表单按 scope 真正挂载（P0-5）**：学校/院系/课题组/未知 →
   `createOrgEvidence`（job_id=null，进入 Reputation 统计）；岗位 → `createJobEvidence`。
   修复"表单选学校但实际挂岗位、永远进不了统计"的错位。另修复空字符串发给
   date 字段导致的 422（提交前空串转 null）+ 创建失败 alert 透明提示。

### P1 修复

6. **AI 综合删除 confidence/overall_note**：ReputationSynthesisOut 只剩 topics
   （topic+conclusion）——overall_confidence 由确定性规则（任一 eligible 主题 → medium，
   否则 low）唯一决定，AI 无法把 low 拔高成 high。Schema/Prompt 同步。
7. **synthesize 结果保留在页面**：onSuccess 用 `setQueryData` 写入 POST 返回的报告，
   不再用确定性 GET 覆盖——AI 结论立即显示且不丢失。
8. **Evidence Schema `extra="forbid"` + NOT NULL 字段显式 null → 422**（与 Phase 5.1
   status:null 同一契约）；岗位证据 organization 强制继承，不能伪造归属（测试：
   organization_id=999 被忽略）。
9. **invalidate 完整性**：证据创建/删除后失效 evidence + reputation 全部相关查询。

### 数据库变化

- 无。

### 测试 / lint / build

- pytest：**154 passed**（重写 reputation 测试套件：CRUD/repost 校验/统计语义/eligibility
  唯一权威四件套/删除保护/department 语义/AI 合并/503）
- vitest：17 passed；ruff：All checks passed；前端 build：通过
- 浏览器验证：学校级表单创建（job_id=null）→ 进入 reputation 统计；AI 综合按钮 503 透明报错。

### 明确未实现

- **Phase 7**：设置页可视化、批量重评、Collector 架构、Evidence selection/ranking、
  申请历史时间线、applied_at 显式编辑。

---

## Phase 6.1.1 — Final Evidence Invariants（2026-08-31 完成）

第十轮审查指出的最后四个 invariant，全部封死后 **Evidence & Reputation 可冻结**。无 migration。

1. **finalize 重验 eligibility（不变量 1）**：`finalize_evaluation()` 不再信任 snapshot 里的
   `eligible_for_reputation_scoring` 布尔值——改为从 snapshot 携带的 job.organization.id +
   department 调用唯一权威 `eligible_reputation_evidence_ids()` 重新计算，要求
   "快照证据 ⊆ 权威 eligible 集合且非空"才允许 reputation 分。**直接调用 finalize 的调用方
   伪造 eligible=true 也无效**（测试：单 C 证据 + 伪造标志 → 落库 null）。快照无单位信息时
   保守拒绝解锁。
2. **repost 优先追 parent（不变量 2）**：canonical resolver 改为"先沿 repost 链追根，
   只有非转载才使用自己的 independence_key"——转载自己填新 key 不再被算成新独立源
   （测试：repost 带 repost_own_key → canonical 仍 = root_key）。
3. **被转载引用的 root 禁止删除（不变量 3）**：DELETE 增加
   `repost_of_evidence_id == 当前 id` 的引用检查 → 409"删除会使转载退化为独立来源，
   改变风评统计"（测试：root 有 child 时 409 且 root 仍在）。
4. **RepostChainError → HTTP 422（不变量 4）**：POST/PATCH 路由 catch
   `RepostChainError` 转为 HTTPException(422)（测试：目标不存在 → 422"转载目标不存在"；
   循环 → 422 且 root 未被修改）。此前契约只存在于文档。

另：Evidence 删除确认文案更新——不再说"历史评估关联会一并清理"，改为说明
"已用于历史评估或仍被转载引用的证据会被拒绝删除（409），审计链与统计不会因此改变"。

### 数据库变化

- 无。

### 测试 / lint / build

- pytest：**158 passed**（新增 4 个不变量测试 + 2 个既有测试按 422 契约更新）
- vitest：17 passed；ruff：All checks passed；前端 build：通过

### 明确未实现

- **Phase 7**：设置页可视化、批量重评、Collector 架构、Evidence selection/ranking、
  申请历史时间线、applied_at 显式编辑。

---

## Phase 6.1.1 Final Closure（2026-08-31 完成）

第十一轮审查：修复 `issubset` gate 误杀合法混合证据的回归，同时保留伪造 flag 防绕过；
补 prompt v2 与 fact 排除。无 migration。

1. **finalize reputation gate 最终语义**：
   - **逐条一致性校验**：snapshot 中每条证据的 `eligible_for_reputation_scoring` 必须与
     唯一权威完全一致，不一致 → 直接 `ValueError` 拒绝保存（伪造 flag 不再静默 null，
     直接调用 finalize 也无法绕过）；快照缺单位信息 → 拒绝；
   - **解锁条件 = 非空交集**：`snapshot_ids & authoritative` 非空才允许 reputation 分——
     不再要求"快照全部证据都必须是 reputation 证据"。岗位事实/参考线索混入 context
     不会误杀合法风评。
   - 测试三件套：B+C eligible + A 岗位事实 → reputation 保留；B+C eligible +
     unknown 线索 → 保留；伪造 eligible=true 单 C → 拒绝（ValueError）。
2. **job_evaluation_v2**：新增契约"reputation 只能使用 `eligible_for_reputation_scoring=true`
   的 Evidence；false 证据可作为其他维度/风险/信息缺口参考，不得影响 reputation 分；
   不存在 true 证据时 reputation 必须为 null"。**v1 保持原样**（历史评估的
   prompt_version 审计指向不被破坏），registry 切到 v2。
3. **category=fact 排除出风评聚合**：fact 证据一律降为线索（"事实证据不直接进入风评
   计量；如能支撑具体风评主题，请归入对应主题"）——2 条 A 级组织级事实不再能形成
   "other" eligible 主题解锁风评分（与"岗位事实不解锁 reputation"边界统一）。
   测试：2 条 A fact → topics 为空、线索提示、reputation=null。

### 数据库变化

- 无。

### 测试 / lint / build

- pytest：**161 passed**（新增 3 个 final closure 测试；forged 测试改为拒绝语义；
  快照契约测试更新）；vitest：17 passed；ruff：All checks passed；前端 build：通过。

### 明确未实现

- **Phase 7**：设置页可视化、批量重评、Collector 架构、Evidence selection/ranking、
  申请历史时间线、applied_at 显式编辑。

---

## Phase 7 — Polish（2026-08-31 完成）—— V0.1 收尾

### 已实现

1. **prompt 文案修正**：`job_evaluation_v2.md` 标题 v1 → v2（registry 早前已切 v2）。
2. **设置 API**（`GET/PUT /api/settings`）：读取/写回 config/{scoring,regions,profile}.yaml——
   写回前自动备份 `.bak`；校验：评分权重合计必须 100、未知维度拒绝、地区层级必须是列表、
   minimum_salary 必须是数字或 null、extra=forbid。配置仍是事实源，改文件即生效。
3. **批量重评**（`POST /api/jobs/re-evaluate-all`）：遍历全部岗位逐个走完整 evaluate_job
   编排（同一 input_snapshot 审计语义），单点失败不中断（Collector 同款容错），返回
   total/succeeded/failed 汇总；AI 未配置 503。
4. **Collector 架构定义**（`app/collectors/`）：`JobCollector` ABC + `RawJob` dataclass +
   `CollectorRegistry`（按 sources.yaml enabled 清单执行、单点失败隔离）。**不实现任何真实
   爬虫** —— 只定义契约，符合"不要为了 V0.1 编写复杂反爬机制"。
5. **前端设置页**：评分权重（8 维，实时合计徽标）、地区偏好四层（顿号/逗号分隔）、
   Hard Filters（最低薪资 + 三个排除开关）、保存配置、批量重评按钮（结果汇总展示）。

### 数据库变化

- 无。

### 测试 / lint / build

- pytest：**168 passed**（settings GET/PUT、权重合计校验、roundtrip 写回并恢复、
  未知文件/非法值拒绝、批量重评 503/容错汇总）；vitest：17 passed；
  ruff：All checks passed；前端 build：通过；浏览器验证设置页渲染。

### 明确未实现（V0.1 范围外，按规格不阻塞）

- 真实 Collector 爬虫（反爬对抗明确不做）；Evidence selection/ranking（大量证据挑选策略）；
- 申请状态历史时间线；applied_at 显式编辑；多用户/权限系统；Redis/Kafka/微服务；
- GitHub Actions CI（仓库无独立 status checks，测试数字为本地执行记录）。

## V0.1 完成状态

Phase 2 Domain Model / Phase 3 AI Extraction / Phase 4 AI Evaluation / Phase 5 Career CRM /
Phase 6 Evidence & Reputation / Phase 7 Polish —— 全部完成。pytest 168 passed、vitest 17 passed、
ruff 全绿、前端 build 通过、alembic 迁移链（e2bcd6b51463 → 4a48e7786118 → d281b97059b5）可用。

---

## Phase 7.1 — Final V0.1 Integrity（2026-08-31 完成）

第十二轮审查：两个 P0（config cache、批量重评事务）+ 六个 P1 收口。无 migration。

### P0

1. **Settings 保存后清配置缓存**：`update_settings()` 全部 YAML 成功写入后调用
   `load_yaml_config.cache_clear()` —— "保存即生效"真正成立（此前页面显示新值、
   评估/地区/Hard Filters 仍用旧 cache）。测试：预热旧 cache → PUT 新 regions →
   `get_region_tier/get_region_score` 立即返回新值（preferred/90）。
2. **批量重评每岗位独立事务**：`re_evaluate_all()` 每个岗位单独 `commit()`——
   中途某岗位失败 `rollback()` 不再撤销之前成功岗位已落库的 Evaluation。
   测试：success → fail → success 三岗位，**查 JobEvaluation 表**确认第 1、3 个
   真实落库、第 2 个无记录（原测试只断言 response，未覆盖"成功之后再失败"）。

### P1

3. **前端地区保存保留 city_details**：`regions_yaml` 改为 spread 原文件后合并。
4. **设置表单竞态**：保存成功后不再 `setLoaded(false)`（本地表单即刚保存值，
   只 invalidate backing query），避免旧 query data 重新初始化表单的回跳竞态。
5. **顿号支持**：地区分隔正则 `/[，,]/` → `/[，,、]/`。
6. **Settings 校验强化**：评分权重 8 维必须齐全、全部 numeric 且非负、合计 100
   （此前 `{fit: 100}` 可通过，八维模型会被缩水）；Hard Filters 三个排除开关
   必须是真正 boolean（字符串 `"false"` 是 Python 真值陷阱，已拒绝）、
   unacceptable_regions 必须是字符串列表、minimum_salary 数字或 null 且非负。
7. **.bak 清理**：删除已跟踪的 `config/regions.yaml.bak`；`.gitignore` 加
   `config/*.bak`；设置写盘测试改用 `tmp_path` + 双 patch（config.py 与
   settings.py 的 CONFIG_DIR）+ 前后清 cache —— **pytest 不再触碰/污染真实
   config/ 目录与 Git working tree**（有专门断言验证真实目录无 .bak）。
8. **文档修正**：README Roadmap Phase 6 状态 ⬜→✅（与顶部"全部完成"矛盾）；
   "配置 Profile/权重/地区"章节的批量重评说明更新（设置页一键重评已交付）；
   `CollectorRegistry.run_configured()` 读取 sources.yaml 的 enabled 清单
   （DEVLOG 声称与实现一致）；sources.yaml 注释更新（"暂不生效"→ 已接线，
   真实爬虫仍未实现）。

### 数据库变化

- 无。

### 测试 / lint / build

- pytest：**170 passed**（settings 套件重写为 tmp_path 化：cache 失效预热测试、
  8 维/负数/非数字/boolean 陷阱/列表校验、事务落库断言、无 .bak 断言）
- vitest：17 passed；ruff：All checks passed；前端 build：通过；
  `git status` 在测试后 config/ 干净（无 .bak 残留）。

### 明确未实现（V0.1 范围外）

真实 Collector 爬虫、Evidence selection/ranking、申请历史时间线、applied_at
显式编辑、多用户/权限、Redis/Kafka/微服务、GitHub Actions CI。

---

## V0.1.1 — Local Launcher（2026-08-31 完成）

把 V0.1 从"开发项目"变成"每天愿意打开的软件"：日常使用不再依赖终端 + Vite。

### 已实现

1. **FastAPI 托管 React 静态产物**：`main.mount_static()` 在 `frontend/dist` 存在时
   提供 index.html + assets，非 /api 路径全部回退 index.html（React Router 前端路由）；
   dist 不存在（开发模式）行为不变。**日常运行零 Vite/Node 进程**。
2. **`launcher/launcher.py`（Tkinter）**：
   - 后端以**无 --reload** 方式启动（subprocess 单进程），stdout/stderr 实时进日志框；
   - PID 持久化到 `data/backend.pid`；停止/关闭 → 优雅 terminate → 超时强制
     `taskkill /PID <pid> /T /F` 清理整个进程树 → 删除 PID 文件；
   - 启动时检测上次异常残留 PID → 提示并清理；
   - 启动成功（轮询 /api/health 按实际端口）后自动打开浏览器；
   - `--serve` 分支供自身 subprocess 复用与冒烟验证。
3. **打包感知**：`config.py` frozen 时资源目录 = `_MEIPASS`（config/、前端静态、
   Prompts），数据目录 = exe 旁 `data/`（自动创建）；launcher 的 PID 文件同样放 exe 旁。
4. **PyInstaller 打包**（`launcher.spec`，onedir）：`dist/PhD Career Radar/PhD Career Radar.exe`
   已生成并验证 —— `--serve` 模式下 /api/health 200、SPA 页面 200、前端路由回退 200、
   数据库文件创建于 exe 旁。
5. **测试**：静态托管（临时 dist 挂载 / 无 dist noop）、ProcessManager（PID 生命周期、
   残留检测与清理、Windows taskkill /T /F）；真实进程级验证（start → health → stop →
   pid 文件清理、残留伪造检测）。

### 数据库变化

- 无（v0.1.1 为交付层改动）。

### 测试 / lint / build

- pytest：**175 passed**（+5：mount_static 两例、ProcessManager 三例）；vitest：17 passed；
  ruff：All checks passed；前端 build：通过；exe 冒烟：通过。

### 说明与边界

- 打包使用 onedir（首次启动快）；`dist/`、`build/` 已加入 .gitignore，不入库；
- GUI 的交互（按钮/日志/自动打开浏览器）为 Tkinter 实现，自动化冒烟验证的是
  `--serve` 后端与 ProcessManager 生命周期；GUI 视觉由用户首次双击确认；
- 开发模式（uvicorn --reload + npm run dev）完整保留。

---

## V0.1.1 Final Closure（2026-08-31 完成）

四项边界 + GUI 线程收尾，Launcher 达到"每天使用的入口"标准。

1. **SPA fallback 不吞 /api**：catch-all 对 `api` / `api/*` 直接 404 ——
   未知 API 不再返回 index.html 200。回归：`/jobs/1 → 200`、`/api/not-exist → 404`。
2. **可复现构建**：`backend/launcher.spec` 提交入库（改用 `Path.cwd()` 推导项目根，
   从 backend 目录运行即可在任何 clone 上复现）；`.gitignore` 改为
   `*.spec` + `!backend/launcher.spec`。
3. **frozen 资源/用户配置分离**：RESOURCE_ROOT（_MEIPASS：前端、默认 config、Prompts）
   ≠ USER_ROOT（exe 旁：`.env`、config/、data/）。首次运行 `seed_user_config()` 从
   bundled 默认配置复制缺失的 YAML（不覆盖已存在文件）；Settings 永远编辑 exe 旁用户配置；
   `.env` 从 exe 旁读取。exe 冒烟验证：全新目录下 4 个 YAML 种子化、数据库创建于 exe 旁。
4. **stale PID 身份校验**：PID 文件升级为 JSON {pid, created_at_marker, port}；
   清理前用 `GetProcessTimes`（Windows）/ `/proc`（Linux）校验进程创建时间与记录一致——
   不一致（PID 被系统复用）只删文件，**绝不 kill 无辜进程**；旧纯数字格式同样保守处理。
   测试：身份匹配 → 清理；创建时间不一致 → 不 kill 只删文件；旧格式 → 不 kill。
5. **GUI 线程修复**：health 检查在后台线程完成，结果经 `root.after` 回主线程更新
   日志/状态/自动开浏览器；失败显示"启动失败：/api/health 超时未响应"。

### 数据库变化

- 无。

### 测试 / lint / build

- pytest：**178 passed**（+3：SPA 404、frozen 种子化、PID 复用防护 ×2/旧格式）；
  vitest：17 passed；ruff：All checks passed；前端 build：通过；
  exe 重新打包并冒烟（health/SPA/SPA 路由/未知 API 404/配置种子化/数据落 exe 旁）。

---

## V0.1.1 Last UX Closure（2026-08-31 完成）

把"双击即用、关闭即净"落实到 GUI 入口。三项 + 一个真实 bug 修复。

1. **双击即启动**：GUI 初始化完成后 `root.after(200, start)` —— 双击 exe →
   自动启动后端 → health OK → 自动打开浏览器（不再需要手动点"启动"）。
2. **关闭即净**：`on_close()` 改为**无条件** `manager.stop()` —— 不再依赖
   `is_running()`（PID 存活 + 身份校验）前置判断。对 Launcher 自己持有的活进程
   stop() 直接 terminate，即使 PID 文件损坏/身份校验失败也绝不残留后端。
   新增回归测试：self.proc alive + 身份校验失败 → stop() 仍 terminate owned proc。
3. **README 构建流程完整化**：全新 clone 复现需 `cd frontend && npm ci && npm run build`
   再打包（frontend/dist 不入库）；并明确**打包版 AI 配置把 .env 放在 exe 同目录**。
4. **真实 bug 修复（GUI 实测发现）**：Tk 变量（StringVar/BooleanVar）原先在
   `tk.Tk()` 之前创建，GUI 一打开即崩溃（"Too early to create variable"）——
   调整初始化顺序到 root 创建之后。真实验证：GUI 模式启动 14 秒后端自动就绪
   （health 200 + JSON PID 文件），进程清理干净。

### 数据库变化

- 无。

### 测试 / lint / build

- pytest：**179 passed**（+1：owned-proc 强制终止回归）；vitest：17 passed；
  ruff：All checks passed；前端 build：通过；
  GUI 自动启动真实验证 + exe 重打包冒烟（health/SPA/未知 API 404/配置种子化）。

---

## V0.2 — Collector MVP（2026-08-31 完成）

把工作台升级为"发现 → 去重 → 人工审核 → AI 结构化 → 评价 → CRM"全链路。
Collector 只负责发现公开招聘材料（DiscoveredJob），从不直接创建正式 Job；
正式 Job 只能由用户确认后的现有 AI Extraction Preview 流程创建。

### 已实现

1. **模型 + migration**（937a152aeca9 → 37f788d24311）：
   - CollectorRun（运行审计：状态/各计数/触发方式）、CollectorRunItem（source 级结果 + 错误信息限 500 字符）、
     DiscoveredJob（Inbox：source 信息/canonical URL/fingerprint/状态/first_run/last_run/possible_duplicate 标记）；
   - 状态机独立于 Job.status（new/reviewing/ignored/imported/possible_duplicate）；
   - 冻结阶段模型零改动。
2. **sources.yaml 正式运行语义**：id 唯一、enabled 严格 boolean、未知 type 报错、配置错误只影响当前 source、
   关键词过滤器（include/exclude，确定性可解释，filtered_count 保留）。
3. **JsonApiCollector + HtmlListCollector**：selector/mapping 全由配置驱动（不写死任何站点）；
   dotted path（data.jobs/result.items）；detail.fetch_detail=false 支持；单条 detail 失败不影响整个 source；
   URL 相对解析。
4. **安全 HTTP 组件**（collectors/http.py）：复用 Phase 3 SSRF 思路（公网 IP、每跳重定向校验、大小限制、
   Content-Type 验证、timeout）——不重写第二套逻辑。
5. **去重引擎**（services/collector_dedupe.py）：Level1 source_job_id → Level2 canonical URL（fragment/trailing
   slash/scheme-host 标准化 + 仅删 utm_*，保留可能代表职位 ID 的 query）→ Level3 fingerprint（org+title+path）→
   Level4 possible duplicate（同单位+标题相似≥80%+URL 不同 → 只标记不合并）。
6. **Runner**（services/collector_runner.py）：逐 source **savepoint 独立事务**（A 成功 → B 失败 → C 成功，
   查库确认 A/C 数据保留、B 标记 failed）；确定性重复更新 last_seen/last_run_id，first_run/discovered_at 保持。
7. **API**：POST /collectors/run（同步返回含 source 级状态）、GET /collectors/runs(/id)、GET /collectors/sources、
   GET/PATCH /discovered-jobs（status 流转校验）、POST /discovered-jobs/{id}/extract（接入现有 Phase 3
   extraction，返回 preview，状态推进 reviewing，不创建正式 Job）。
8. **前端**：侧边栏"招聘发现"；立即检查按钮 + 上次运行摘要（新增/重复/疑似/过滤/失败 + source 级行）+
   Inbox 表格（状态 Badge、疑似重复 Badge + 原因、查看原文/详情/AI 解析/忽略/恢复）+ 详情页（原始正文/元信息/重复判断）；
   AI 解析 → sessionStorage 桥接 → 现有导入页 Preview → 确认 → 正式 Job。

### 真实 Sources 冒烟（2026-08-31，8 个公开来源）

| source | 结果 | 说明 |
| --- | --- | --- |
| 上海交通大学人才招聘 | ✅ 13 抓取/1 新增（关键词过滤 11） | html_list |
| 中科院人才招聘网 | ✅ 173 抓取/16 新增/1 重复（过滤 153） | html_list |
| 复旦大学人事处 | ✅ 0 匹配（选择器未命中列表项） | html_list |
| 中科院上海有机所 | ✅ 0 匹配 | html_list |
| 南京大学人才招聘 | ❌ HTTP 410 | 站点技术限制，按设计隔离 |
| 中科院化学所 | ❌ HTTP 404 | 同上 |
| 西湖大学 | ❌ HTTP 500 | 同上 |
| 高校人才网 | ❌ HTTP 404 | 同上 |

- 第一次运行：21 条进入 Inbox（17 新增 + 4 possible_duplicate）；
- **第二次运行：new=0、dup=22、Inbox 总数不变（21）**——去重是数据库级生效；
  first_run=1/last_run=2（first_seen 保持、last_seen 更新）；
- 第三次（经 UI/API）：new=0、dup=22、4 source 稳定失败——失败隔离与可审计性成立。

### 已知限制

- 4 个 source 因站点返回 4xx/5xx 或技术限制失败（按"unsupported_in_v0.2"处理，不强行突破）；
  选择器按当前站点结构配置，站点改版需调整 sources.yaml；
- 同步执行（几十秒），未做后台任务/调度（按规格留 V0.2.x）；
- possible duplicate 目前只按同单位+标题相似判定，发布时间接近度尚未纳入（原因字段已可扩展）。

### 明确未实现（按规格）

定时调度、Windows Scheduler、Playwright、BOSS/智联/猎聘/前程无忧、登录态站点、验证码/反爬、
RSS/Sitemap Collector、自动投递/联系 HR、AI 参与去重判断。

### 测试 / lint / build

- pytest：**205 passed**（+26：config 解析 4、去重 5、JsonApi 4、HtmlList 4、runner 事务/去重/last_seen/
  possible/filter 5、API 端到端 3、extract bridge 2 等）；vitest：17 passed；ruff：All checks passed；
  前端 build：通过；真实抓取三次冒烟：通过。
- migration 链：e2bcd6b51463 → 4a48e7786118 → d281b97059b5 → 937a152aeca9 → 37f788d24311。
