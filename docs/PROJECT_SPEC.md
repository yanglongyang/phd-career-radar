# PhD Career Radar — 项目规格（PROJECT_SPEC V0.1）

> 本文件为仓库创建时的原始需求规格（V0.1），原文保留，作为后续所有开发决策的基准。
> 评分权重、地区偏好与个人 Profile 一律以 config/*.yaml 为准，不写入业务代码。

# PhD Career Radar V0.1 — 开发提示词

你是一名资深全栈工程师、数据工程师和 AI Agent 架构师。

请帮助我从零开发一个名为 **PhD Career Radar** 的个人求职监控与决策工作台。

这是一个面向博士研究生、特别是以高校、科研院所和科研型企业岗位为主要目标的个人求职系统。

项目核心目标不是“自动海投”，而是：

> 自动收集、整理和评估招聘信息，尽可能减少人工刷招聘网站的时间，把真正值得关注的岗位筛选出来，最终由用户本人决定是否申请。

整个系统必须坚持：

**AI 负责搜集、结构化、比较、发现风险和辅助判断；用户负责最终职业选择和投递决策。**

禁止在 V0.1 中实现未经用户确认的自动投递。

---

# 一、用户背景与使用场景

当前用户为博士四年级研究生。

主要求职方向包括：

1. 高校教学科研岗
2. 高校专职科研岗
3. 科研院所
4. 博士后岗位
5. 企业研发岗位

其中高校和科研院所是非常重要的目标方向。

因此，该系统不能按照普通互联网职位推荐平台进行设计，而需要重点关注：

* 岗位实际聘用性质
* 编制 / 长聘 / 预聘 / 合同制
* 非升即走
* 聘期考核
* 科研启动经费
* 实验室资源
* 研究生招生指标
* 教学负担
* 行政事务
* 晋升路径
* 地区
* 待遇
* 风评
* 长期职业发展

系统尤其需要帮助用户识别招聘公告中没有直接说明的风险和信息缺口。

---

# 二、产品核心原则

请始终遵守以下设计原则。

## 1. 不做自动海投系统

不得默认：

* 自动填写招聘网站
* 自动提交申请
* 自动发送简历
* 自动联系招聘人员

未来即使加入这些功能，也必须存在明确的人工确认步骤。

---

## 2. 不允许 AI 编造未知信息

例如招聘公告没有说明：

* 是否有编制
* 是否独立招生
* 是否非升即走
* 启动经费到账时间

必须显示：

`未知 / 待确认`

不得根据学校层级、岗位名称或所谓常识推测。

---

## 3. 区分事实与网络风评

官方政策和网络讨论不能混合。

每条信息需要记录：

* source
* source_type
* source_url
* collected_at
* evidence_level
* confidence

证据等级暂定：

### A

正式招聘公告、学校官网、人事处文件、正式政策、合同条款。

### B

多个相互独立的在职 / 离职人员公开陈述。

### C

知乎、小红书、脉脉、论坛等单个或少量帖子。

### D

无法确认来源的转述。

AI 不得因为存在一条负面评论直接判断：

> “该学校风评差。”

而应该输出类似：

> 有 3 个独立来源提到青年教师考核压力较高，其中 1 个来源时间较早。目前缺乏官方材料验证，可信度中等。

---

# 三、技术栈

V0.1 优先保持简单、稳定、易维护。

推荐：

## Backend

Python 3.12+

FastAPI

SQLAlchemy 2 / SQLModel

Pydantic

Alembic

SQLite

后续需要时可切换 PostgreSQL。

---

## Frontend

React

TypeScript

Vite

Tailwind CSS

shadcn/ui

---

## AI

设计一个独立的 Provider abstraction。

例如：

```python
class LLMProvider:
    def evaluate_job(...)
    def extract_job(...)
    def summarize_reputation(...)
```

不要把整个项目绑定到某一个模型 API。

通过环境变量配置：

```env
LLM_PROVIDER=
LLM_API_KEY=
LLM_BASE_URL=
LLM_MODEL=
```

允许未来支持 OpenAI-compatible API。

---

# 四、项目结构

请首先设计清晰、模块化的目录。

推荐形式：

```text
phd-career-radar/

backend/
    app/
        main.py

        api/
        core/
        db/
        models/
        schemas/
        repositories/
        services/

        collectors/
        normalizers/

        scoring/
            rules.py
            weights.py
            evaluator.py

        ai/
            provider.py
            prompts.py
            schemas.py

        reputation/

frontend/
    src/
        pages/
        components/
        features/
        services/
        types/

data/

docs/

tests/

docker/

.env.example
README.md
docker-compose.yml
```

模块必须尽量解耦。

---

# 五、核心数据模型

至少设计以下数据库实体。

---

## Job

字段至少包括：

```text
id

source
source_job_id
source_url

title

organization
department

job_category

country
province
city

description_raw
description_clean

posted_at
deadline

first_seen_at
last_seen_at

employment_type
position_nature

salary_text
salary_min
salary_max

degree_requirement
experience_requirement

status

created_at
updated_at
```

---

## Organization

例如高校、研究院、企业。

```text
id

name
organization_type

province
city

official_url
career_url

notes

created_at
updated_at
```

---

## JobEvaluation

```text
id
job_id

total_score

fit_score
career_stability_score
research_resources_score
region_score
compensation_score
reputation_score
workload_score
long_term_score

recommendation_level

risk_level
confidence_level

summary

strengths_json
weaknesses_json
risks_json
unknowns_json
questions_json

evaluation_version
evaluated_at
```

---

## JobEvidence

用于保存事实和风评证据。

```text
id

job_id
organization_id

category

claim

source_type
source_url
source_title

evidence_level

published_at
collected_at

confidence

raw_excerpt

created_at
```

---

## Application

```text
id

job_id

status

priority

applied_at

resume_version
cover_letter_version

contact

notes

next_action
next_action_date

created_at
updated_at
```

---

## JobVersion

招聘公告发生变化时保留版本。

例如：

```text
id
job_id

content_hash

description

salary_text
deadline

captured_at
```

以后可以分析：

> 招聘公告是否修改过待遇或考核条件。

---

# 六、岗位分类

job_category 至少支持：

```text
university_faculty
university_research
postdoc
research_institute
industry_rnd
other
```

position_nature 独立于 job_category。

例如：

```text
permanent
tenure
tenure_track
pre_tenure
fixed_term
postdoc
pi_funded
unknown
```

如果无法判断：

必须设置为：

```text
unknown
```

---

# 七、岗位评价模型

总分暂定 100。

权重先使用：

```text
岗位与个人匹配度        20

岗位性质与职业稳定性    15

科研平台与资源          15

地区                    15

待遇                    10

风评与组织环境          10

教学与行政负担           5

长期发展潜力            10
```

这些权重必须保存在配置文件，而不是 hardcode。

例如：

```yaml
scoring:
  fit: 20
  career_stability: 15
  research_resources: 15
  region: 15
  compensation: 10
  reputation: 10
  workload: 5
  long_term: 10
```

未来用户可以自行修改。

---

# 八、岗位匹配评分

匹配度包括：

## 研究方向

评价岗位和个人科研背景之间的关系：

* 直接重合
* 高度相关
* 可自然迁移
* 需要一定转型
* 明显不相关

---

## 实验和技术能力

需要支持用户 Profile。

Profile 示例：

```yaml
research_interests:
  - organic chemistry
  - fluorescent probes
  - chemical biology

skills:
  - organic synthesis
  - molecular design
  - column chromatography
  - HPLC
  - NMR
  - fluorescence spectroscopy
  - computational chemistry
```

以后用户只修改 Profile，不修改评分代码。

---

# 九、高校岗位专用解析

对于高校和科研院所岗位，AI 必须尽可能提取：

```text
岗位性质

是否事业编

是否长聘

是否预聘

是否非升即走

合同年限

首聘周期

中期考核

聘期考核

论文要求

基金要求

教学要求

行政要求

当前职称

晋升路径

独立PI资格

实验室空间

启动经费

启动经费到账方式

研究生招生资格

硕士指标

博士指标

年薪

固定收入

绩效收入

安家费

住房补贴

人才房

地方人才补贴
```

如果公告中不存在：

输出 `null`。

不得猜测。

---

# 十、地区评价体系

Region 不只是一个城市名称。

地区评分拆分：

```text
城市主观偏好        4

生活成本            3

科研和产业生态      3

未来职业流动性      3

城市综合生活因素    2
```

系统应允许用户建立：

```yaml
regions:

  preferred:
    - 南京
    - 上海
    - 苏州

  acceptable:
    - 杭州
    - 合肥

  neutral:
    - ...

  avoid:
    - ...
```

这里只是示例。

不要把任何具体城市默认写死。

---

# 十一、科研与产业生态

地区评价时，可以记录：

```text
附近高校数量

主要高校

科研院所

生物医药产业

药企

CRO

CDMO

大型科研平台
```

核心问题之一：

> 如果用户 3–5 年后离开当前单位，这座城市是否提供足够的下一份工作机会？

这项作为：

`career_mobility`

---

# 十二、风评系统

这是本项目的核心特色之一。

不要只保存：

```text
reputation_score = 65
```

还必须保存证据。

风评分类至少包括：

```text
assessment_pressure

salary_fulfillment

startup_funding_fulfillment

administrative_burden

teaching_load

young_faculty_turnover

promotion_environment

department_management

research_collaboration

student_resources
```

---

# 十三、风评聚合规则

例如有以下信息：

```text
Source A：
青年教师考核压力很大

Source B：
考核需要国自然 + 多篇论文

Source C：
压力还可以
```

系统应该形成：

```text
Topic:
assessment_pressure

Positive sources:
1

Negative sources:
2

Independent sources:
3

Evidence:
B/C

Confidence:
medium

Conclusion:
存在较多关于考核压力的负面反馈，但不同来源体验存在差异，需要进一步核实正式考核制度。
```

不要输出绝对化判断。

---

# 十四、信息可信度

评价结果必须同时存在两个独立指标：

```text
Job Score

Information Confidence
```

例如：

```text
综合匹配度：
86 / 100

信息可信度：
中
```

不能因为信息不足而人为降低岗位评分。

信息不足应该反映在：

```text
confidence
unknowns
```

---

# 十五、风险系统

risk_level：

```text
low
medium
high
critical
```

典型风险：

```text
非升即走

聘期考核极高

PI经费聘用

无独立招生资格

启动经费不明确

待遇高度依赖绩效

合同周期过短

风评中反复出现待遇无法兑现

人员流动异常

教学行政负担异常
```

---

# 十六、推荐等级

不要只显示数字。

增加：

```text
S
A
B
C
D
X
```

定义：

```text
S
强烈建议重点关注

A
值得认真申请

B
可以申请

C
作为备选

D
优先级较低

X
触发硬性排除条件
```

推荐等级不能只由 total_score 简单换算。

需要同时考虑：

```text
hard_filters
risk_level
confidence
```

---

# 十七、Hard Filters

支持用户配置：

```yaml
hard_filters:

  unacceptable_regions: []

  minimum_salary: null

  reject_pi_funded: false

  reject_postdoc: false

  reject_high_risk_tenure_track: false
```

不要在代码里提前替用户决定这些偏好。

---

# 十八、AI 输出 Schema

所有 AI 评价必须输出结构化 JSON。

例如：

```json
{
  "summary": "",
  "recommendation_level": "A",

  "scores": {
    "fit": 0,
    "career_stability": 0,
    "research_resources": 0,
    "region": 0,
    "compensation": 0,
    "reputation": 0,
    "workload": 0,
    "long_term": 0
  },

  "strengths": [],

  "weaknesses": [],

  "risks": [],

  "unknowns": [],

  "questions_to_ask": [],

  "confidence": "medium"
}
```

必须使用 Pydantic 验证 AI 输出。

AI 输出不合法时：

允许自动重试一次。

仍失败则保存错误状态，不允许写入伪造结果。

---

# 十九、Dashboard

V0.1 首页至少包括：

```text
今日新增岗位

待查看

高匹配岗位

值得重点关注

准备投递

已投递

面试中

Offer
```

并显示：

```text
Top Jobs
```

例如：

```text
92  A大学  化学学院  青年研究员
89  B研究院  化学生物学研究员
86  C大学  特聘副研究员
```

---

# 二十、岗位列表

支持筛选：

```text
岗位类型

城市

省份

单位

评分范围

推荐等级

风险等级

信息可信度

状态

首次发现日期
```

支持排序：

```text
综合评分

最新发现

截止时间

地区评分

风评评分
```

---

# 二十一、岗位详情页

页面布局建议：

顶部：

```text
单位
岗位
地区

综合分
推荐等级
风险等级
可信度
```

然后分 Tabs：

```text
Overview

Job Description

AI Evaluation

Institution

Region

Reputation

Evidence

Application

History
```

---

# 二十二、Overview

显示：

```text
推荐理由

主要优势

主要风险

最大信息缺口

需要确认的问题
```

目标是让用户在 30 秒内判断：

> 这个岗位值不值得认真看。

---

# 二十三、Evidence 页面

每个重要结论必须可以追溯到 Evidence。

例如：

```text
考核要求：
聘期内主持国家自然科学基金

Evidence:
A

Source:
XX大学人事处

Date:
2026-05-20
```

如果是网络讨论：

```text
启动经费到账较慢

Evidence:
C

Independent reports:
3

Time range:
2024–2026
```

---

# 二十四、Application CRM

状态：

```text
new

reviewed

shortlist

contacting

preparing

applied

written_test

interview_1

interview_2

hr

offer

rejected

withdrawn

ignored
```

UI 使用 Kanban 和列表均可。

---

# 二十五、用户最终决策

AI Evaluation 与 User Decision 必须完全分开。

数据库中增加：

```text
user_rating

user_priority

user_notes
```

AI 不得覆盖用户判断。

---

# 二十六、信息导入

V0.1 实现三种方式。

## 方法 1

手工新建岗位。

---

## 方法 2

粘贴招聘公告文本。

AI 自动解析成结构化 Job。

用户确认后才保存。

---

## 方法 3

输入 URL。

后端下载公开网页并提取正文。

然后 AI 解析。

如果网站禁止访问或解析失败：

提示用户粘贴正文。

不要为了 V0.1 编写复杂反爬机制。

---

# 二十七、未来 Collector 架构

虽然 V0.1 不需要完成所有爬虫，但提前定义：

```python
class JobCollector:

    def collect(self) -> list[RawJob]:
        ...
```

未来支持：

```text
高校官网

学院官网

人才办

科研院所

BOSS

猎聘

智联

51job

高校就业网

其他公开招聘源
```

Collector 出错不能导致整个任务失败。

---

# 二十八、去重

招聘岗位很可能同时出现在：

```text
学校官网

学院官网

招聘平台

公众号转载
```

建立 job fingerprint。

可组合：

```text
organization

department

title

city

description similarity
```

不能仅依赖 URL。

---

# 二十九、版本监控

如果同一个岗位 JD 改变：

不要覆盖旧数据。

保存 JobVersion。

能够提示：

```text
该岗位招聘信息发生变化

薪资：
30–40 万
→
35–45 万

截止日期：
2026-10-01
→
2026-10-15
```

---

# 三十、搜索任务模型

未来支持：

```text
SearchProfile
```

示例：

```yaml
name: 华东高校化学岗位

job_types:
  - university_faculty
  - university_research

keywords:
  - 化学
  - 有机化学
  - 化学生物学
  - 药物化学
  - 荧光探针

regions:
  - 江苏
  - 上海
  - 浙江
  - 安徽
```

---

# 三十一、Prompt 管理

不要把大型 Prompt 散落在业务代码里。

放在：

```text
ai/prompts/
```

并支持版本：

```text
job_extraction_v1

job_evaluation_v1

reputation_summary_v1
```

JobEvaluation 中保存：

```text
prompt_version
model
```

这样未来可以重新评估。

---

# 三十二、审计性

所有 AI 生成的重要字段必须能够知道：

```text
什么时候生成

使用什么模型

使用哪个 Prompt

基于哪些 Evidence
```

目标是避免整个系统成为 AI 黑箱。

---

# 三十三、设置页面

提供 UI 修改：

```text
评分权重

地区偏好

目标岗位

Hard Filters

AI Provider

模型名称
```

修改以后可以选择：

```text
重新评估当前岗位

重新评估全部岗位
```

---

# 三十四、配置文件

建议：

```text
config/

profile.yaml
scoring.yaml
regions.yaml
sources.yaml
```

---

# 三十五、测试

至少为以下模块建立测试：

```text
Job deduplication

Score calculation

Hard filters

AI JSON parsing

Job status transitions

Evidence confidence

Job version detection
```

---

# 三十六、README

README 至少说明：

```text
项目目的

功能截图占位

架构

安装

开发运行

配置 AI

配置 Profile

数据库迁移

未来 Roadmap
```

---

# 三十七、V0.1 明确不要实现

为了避免过度开发，本阶段不要优先实现：

1. 自动海投
2. Selenium 大规模自动操作招聘平台
3. 绕过验证码
4. 绕过招聘平台反爬
5. 自动发送邮件
6. 自动联系 HR
7. 复杂权限系统
8. 多用户 SaaS
9. Redis / Kafka
10. Kubernetes
11. 微服务

这是个人工作台。

保持简单。

---

# 三十八、V0.1 Definition of Done

V0.1 完成时，我应该能够：

1. 启动 Web 工作台。
2. 新建一个岗位。
3. 粘贴一份高校招聘公告。
4. 自动提取单位、岗位、地区、待遇、考核等字段。
5. AI 根据评价模板产生结构化评估。
6. 明确显示“未知信息”。
7. 查看 8 个评分维度。
8. 查看地区评分。
9. 查看风评字段。
10. 保存 Evidence。
11. 查看岗位风险。
12. 将岗位加入 Shortlist。
13. 修改申请状态。
14. 添加自己的评价和备注。
15. 修改评分权重。
16. 修改地区偏好。
17. 保存招聘公告历史版本。
18. 在 Dashboard 中看到值得关注的岗位。

---

# 三十九、推荐开发顺序

不要一次生成整个系统然后声称完成。

按以下阶段实现。

## Phase 1 — Foundation

完成：

* repository
* backend
* frontend
* database
* migrations
* basic UI

并确保项目可以运行。

---

## Phase 2 — Job CRUD

完成：

* Job
* Organization
* Job list
* Job detail
* manual import

---

## Phase 3 — AI extraction

完成：

招聘公告文本：

```text
Raw JD
↓
Structured Job
↓
User confirmation
↓
Save
```

---

## Phase 4 — Evaluation

完成：

```text
Profile
+
Job
+
Evidence
↓
AI Evaluation
```

---

## Phase 5 — Career CRM

完成：

```text
shortlist

application status

notes

next action
```

---

## Phase 6 — Evidence & Reputation

完成：

```text
Evidence CRUD

Reputation aggregation

Confidence
```

---

## Phase 7 — Polish

完成：

```text
Dashboard

filters

settings

tests

documentation
```

---

# 四十、开发过程要求

这是非常重要的要求。

每完成一个 Phase：

1. 总结已经实现的内容。
2. 列出修改的文件。
3. 说明数据库变化。
4. 运行测试。
5. 运行 lint / type check。
6. 明确列出尚未实现的功能。
7. 不得把未实现功能描述为已经完成。

遇到架构决策时：

优先：

```text
简单
可维护
透明
可修改
```

而不是追求复杂技术。

---

# 四十一、重要的人机确认机制

任何可能影响用户真实求职行为的操作必须经过人工确认。

特别是未来涉及：

```text
投递

发送邮件

发送消息

修改申请状态为已投递

对外提交表单
```

不得默认执行。

V0.1 暂时不实现自动外部操作。

---

# 四十二、AI 系统行为要求

AI 应该像一个：

> 求职研究助理

而不是：

> 替用户做职业决定的顾问。

例如应该说：

```text
这个岗位与你的研究背景存在较高匹配。

主要风险是预聘制考核要求尚未找到官方文件。

建议进一步确认：
1. 首聘周期
2. 国自然是否为硬性要求
3. 未通过考核后的处理方式
```

不要说：

```text
你应该接受这个工作。
```

---

# 四十三、UI 风格

希望界面偏：

```text
研究工作台
+
信息密集型 Dashboard
+
简洁专业
```

而不是招聘网站风格。

参考：

```text
Linear
Notion
GitHub
现代科研 Dashboard
```

支持：

```text
Light

Dark
```

重点保证桌面端体验。

---

# 四十四、第一步任务

现在不要直接实现所有功能。

首先执行：

### Step 1

阅读整个需求。

### Step 2

输出：

```text
1. 产品架构
2. 技术架构
3. 数据模型
4. 页面结构
5. API 设计
6. 项目目录
7. Phase 1–7 开发计划
8. 你认为需求中存在的架构风险
```

### Step 3

检查是否存在明显过度设计。

主动简化。

### Step 4

然后开始实现 Phase 1。

完成 Phase 1 后：

运行项目、测试和检查。

### Step 5

继续 Phase 2。

不要因为上下文较长而跳过验证。

---

# 最终目标

这个系统最终应该做到：

```text
大量分散招聘信息
          ↓
统一收集
          ↓
结构化
          ↓
去重
          ↓
AI + Rules 初筛
          ↓
地区 / 平台 / 待遇 / 风评 / 风险评价
          ↓
每天只留下少量真正值得看的岗位
          ↓
用户人工判断
          ↓
申请与面试管理
```

核心产品哲学：

> 不追求“找到最多岗位”。

而追求：

> **尽可能不漏掉真正适合我的岗位，同时显著降低筛选招聘信息所消耗的时间。**

这版可以直接作为仓库最初的 `PROJECT_SPEC.md`，同时把最后的“四十四、第一步任务”作为第一次交给 Codex 的任务提示。

有两个地方我建议你在真正开写前**暂时不要定死**：一是具体地区偏好和城市权重，二是你的个人 Profile。它们应该最终变成 YAML 配置，而不是写进业务代码。这样你找工作过程中目标发生变化，不需要重构整个系统。

另外，我建议从第一版就要求 Agent **每次 AI 评价都保留模型、Prompt 版本、Evidence 和原始 JD**。这一点现在看起来有点多余，但等你真正积累到几百个岗位、不断调整评分规则后，会非常有用。
