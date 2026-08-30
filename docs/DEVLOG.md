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
