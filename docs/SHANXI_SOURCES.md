# 山西招聘来源、历年参考与覆盖边界

本来源包解决“只看少量列表首页、只留近一年标题”导致的漏采。它同时配置后续公告发现和历年正文补采。配置文件为 `config/sources_shanxi.yaml`，与原 `config/sources.yaml` 独立；原有用户配置不需要重写。

核验日期：**2026-10-30**。核验只说明当次公开网页及结构可读取，不保证外部网站以后持续可用。

## 已接入的动态来源

目前新增包有 **10 个启用的动态列表**、**3 个只供历史补采的种子来源**，另列 **6 个禁用的覆盖缺口**。这些是采集入口数量，不等于已覆盖机构数量，更不等于全省招聘信息已经完整收齐。

| 类型 | 机构或发布者 | 已核验的动态入口 | 自动读取方式与边界 |
| --- | --- | --- | --- |
| 高校 | 山西大学 | [教师招聘](https://rsc.sxu.edu.cn/gkzp/jszpzp/index.htm) | 列表、发布日期、分页和正文；同一目录兼含太原/大同校区，具体工作地看公告 |
| 高校 | 太原理工大学 | [人事网人才引进](https://renshi.tyut.edu.cn/rczp/rcyj.htm) | 列表、分页和正文；人事网并未同步全部校级年度公告，另补2025校级正文种子 |
| 高校 | 山西农业大学 | [硕博招聘](https://zzrsb.sxau.edu.cn/sbzp.htm) | 列表、分页和正文；具体学科要求可能在岗位表附件 |
| 高校 | 山西师范大学 | [师资引进](https://www.sxnu.edu.cn/jsdw/szyj.htm) | 当前导航指向此页，已发现2026公告；旧 `/rczp/gkzp1.htm` 仅列到2025，不能继续作为唯一入口 |
| 高校 | 中北大学 | [人力资源部通知公告](https://rlzyglc.nuc.edu.cn/tzgg.htm) | 真实招聘在通知公告中；名为“历次人才招聘公告”的栏目实际为空。每页仅5条，需分页及种子补足 |
| 高校 | 太原科技大学 | [通知公告](https://www.tyust.edu.cn/index/tzgg.htm) | 列表将日放在年月之前，发布日期取详情页 `.arc-info`，避免拼错日期 |
| 医院 | 山西省卫生健康委员会 | [公告公示](https://wjw.shanxi.gov.cn/zfxxgk/fdzdgknr/gggs/index.shtml) | 官方汇总覆盖多家所属医院；发布者是卫健委，雇主按公告标题中的医院名单匹配 |
| 企业 | 亚宝药业 | [吉林大学就业网企业专页](https://jdjyw.jlu.edu.cn/portal/company/details?id=3fd9b895b5c9457993c838d84c4fb673) | 动态读取该企业向吉林大学发布的招聘信息；这是学校官方转载渠道，不是企业全部职位接口 |
| 企业 | 振东制药 | [天津商业大学就业网企业专页](https://career.tjcu.edu.cn/company/index/id/7231.html) | 动态读取该企业专页中的职位及详情；保留真实学历要求，不能把硕士岗位改称博士专岗 |
| 企业 | 西北农林科技大学食品学院发布的山西企业信息 | [就业信息](https://food.nwsuaf.edu.cn/zhdt/jyxx/index.htm) | 仅接收标题命中亚宝、山西振东、锦波生物、山西仟源、国药集团威奇达、山西康宝或山西普德的公告；不把其他地区企业混入山西范围 |

企业总部或注册地在山西，不意味着每个岗位都在山西。亚宝、振东等公告可能包含北京及其他地区的职位，来源包不据企业名称推定实际工作地。发布高校也不作为招聘雇主。

## 已配置的历史正文

历史种子用于补足旧公告已经翻到深层分页、原列表漏项或列表迁移的情况。它们与动态列表配合使用；只配置固定旧网址无法持续发现未来公告。

| 机构 | 已配置的年份/正文 | 主要参考内容 |
| --- | --- | --- |
| 山西大学 | [2025年专任教师，太原校区](https://rsc.sxu.edu.cn/gkzp/jszpzp/bb62047d39764de186e21f7c79695d92.htm) | 专业范围、博士年龄、薪资、安家费、科研启动费、补贴条件 |
| 太原理工大学 | [2025年优秀青年博士](https://www.tyut.edu.cn/info/1026/61801.htm)、[2024年优秀青年博士](https://renshi.tyut.edu.cn/info/1007/4339.htm) | 岗位条件、编制、报名周期、待遇咨询口径；未公开具体数字时不填估算数字 |
| 山西农业大学 | [2025年博士招聘](https://zzrsb.sxau.edu.cn/info/1058/5130.htm)、[2024年第二批博士招聘](https://zzrsb.sxau.edu.cn/info/1058/5065.htm) | 岗位表、年龄、人才档次、安家费和启动费、发放及考核条件 |
| 山西师范大学 | [2025年高层次人才](https://www.sxnu.edu.cn/info/1301/9828.htm)、[2025年博士招聘](https://www.sxnu.edu.cn/info/1301/15657.htm) | 人才层次与薪酬表、年龄、专业、校内安家和科研支持 |
| 中北大学 | [2025年博士毕业生招聘](https://rlzyglc.nuc.edu.cn/info/1007/4549.htm) | 岗位类别、聘期、发放条件；主要待遇表为图片，保留原图并标待核验 |
| 太原科技大学 | [2025年博士招聘](https://www.tyust.edu.cn/info/1092/12042.htm)、[2025年补充公告](https://www.tyust.edu.cn/info/1092/12456.htm) | 岗位表、报名要求、后来延长的报名时间；补充公告不与原文混为一个发布日期 |
| 山西省人民医院 | [2025年博士招聘](https://wjw.shanxi.gov.cn/tzgg/gsgg/202501/t20250123_9757470.shtml) | 学历、专业/资格要求、岗位附件、待遇 |
| 山西白求恩医院 | [2025年博士招聘](https://wjw.shanxi.gov.cn/zfxxgk/fdzdgknr/gggs/202503/t20250303_9779740.shtml) | 编制、薪资、安家费、科研费、补贴和适用条件 |
| 山西医科大学第一医院 | [2025年博士招聘](https://wjw.shanxi.gov.cn/zfxxgk/fdzdgknr/gggs/202502/t20250225_9775956.shtml) | 年龄、博士及具体岗位资格、岗位附件 |
| 山西医科大学第二医院 | [2025年博士招聘](https://wjw.shanxi.gov.cn/zfxxgk/fdzdgknr/gggs/202503/t20250303_9779732.shtml) | 年龄、专业、报名时间、岗位附件及待遇 |
| 山西省肿瘤医院 | [2025年博士招聘](https://wjw.shanxi.gov.cn/tzgg/gsgg/202501/t20250123_9757495.shtml) | 招聘专业、科研与临床岗位条件、待遇 |
| 山西省儿童医院 | [2025年博士招聘](https://wjw.shanxi.gov.cn/zfxxgk/fdzdgknr/gggs/202503/t20250314_9788667.shtml) | 年龄、待遇、图片形式的具体岗位表 |
| 山西省中医药研究院（省中医院） | [2025年博士招聘](https://wjw.shanxi.gov.cn/zfxxgk/fdzdgknr/gggs/202503/t20250314_9788680.shtml) | 招聘条件、人才待遇及岗位原始证据 |
| 亚宝药业 | [2025年招聘简章](https://food.nwsuaf.edu.cn/zhdt/jyxx/7611f141bd114367b57cde5b888df6a8.htm)、[2024年秋季校招](https://jdjyw.jlu.edu.cn/portal/jyzp/recruit/details?id=461df77431cb42e8b1d93581826c1282) | 专业、学历、福利、工作地区；岗位图表/附件未识别时保留待核验状态 |
| 振东制药 | [2025年综合招聘](https://zsjy.czmc.edu.cn/info/1011/42511.htm)、[2025年发布的26届硕士管培生](https://career.tjcu.edu.cn/correcruit/content/id/13526.html) | 研究员和管培生要求、待遇及地点；长治医学院原文已由网页检索核验，但本次直连返回503，采集失败应显示失败原因 |

上述共有 **21 条种子**，集中在2024—2025；动态分页继续查找默认3年窗口内的公告。它不是人工宣称已补齐2023—2025全部公告的数据库。发布日期、招聘年度、面向的毕业届别及报名截止日期是不同字段；2025年发布的2026届校招不应被标成2026年发布。

## 尚未接通的来源

下面的入口在配置中明确 `enabled: false`，并写明 `coverage_note`。不能因为登记了官方地址就将它计为自动采集成功，也不能将访问失败或空列表解释成“该机构今年没有招聘”。

| 机构 | 已核查的入口及依据 | 缺口 |
| --- | --- | --- |
| 山西医科大学 | [2025年省人社厅原文链接](https://rst.shanxi.gov.cn/ztzl/zpxx/szsydwzpgg/202504/t20250425_9820348.shtml) | 多个转载页指向该原文；本次学校官网和省人社直连503。尚未验证正文结构，待恢复或增加可核实的官方发布渠道 |
| 振东集团官方系统 | [北森招聘](https://zdbj2019.zhiye.com/)，由[集团官网](https://www.zdjt.com/)“加入我们”直接链接 | 动态职位接口尚未适配；目前以高校官方转载补充 |
| 亚宝药业官方系统 | [北森招聘](https://yabaoyaoye1.zhiye.com/)，吉林大学2024简章列为网申地址 | 动态职位接口尚未适配；目前以高校官方转载补充 |
| 锦波生物 | [官网人才招聘](https://www.sxjbswyy.com/h-col-145.html) | 只有图片和智联外链，没有可直接采集的岗位列表；尚无已验证的近期历史正文种子 |
| 仟源医药 | [官网招贤纳士](https://www.cy-pharm.com/pages/jobs.html) | 链接实际指向51job雇主后台，不作为公开岗位源；企业理念文案不是招聘公告 |
| 国药威奇达 | [原工作机会目录](https://www.weiqida.com/wqd/rczp/xyzp/A006007003Gone1.html)、[2025年招聘渠道变更声明](https://www.weiqida.com/wqd/xinxigk/xggg/2025/9/I1421178428995928064.html) | 声明校园招聘改在国聘发布；原目录为空不能推断没有招聘，仍需国聘职位适配 |

因此，**当前已核验能动态发现公告的企业专页是亚宝和振东两家**。定向转载目录对其他山西企业持续查找，但命中与否取决于发布者，不能据此宣称已抓全锦波、仟源和威奇达。

## 采集与展示约定

- 日常模式只检查有限的新页；历史模式扩大分页范围，并启用 `history.only: true` 的正文种子。
- 每个来源都有页数和条数上限，避免手动回溯或定时采集无界运行。达到上限时保留“还有更早页面未遍历”的提示。
- 排除“拟聘、公示、成绩、资格复审”等按标题判断。正式招聘正文普遍包含面试、体检和公示流程，不能据这些正文词语删除整篇公告。
- 有公告正文不代表已看懂全部附件。Excel/PDF/Word岗位表和图片待遇表在未解析前必须显示“待核验”，保留原始链接，不猜学历、论文门槛、金额或是否适合生物学博士。
- 临床医师资格、规培、专业目录等要求按具体岗位识别。综合医院公告包含科研/药学岗位时不能直接因出现“执业医师”就删除整篇，也不能因此判定全部岗位要求临床执照。
- 历史薪酬、安家费、科研经费、政府补贴分别保留。不要把科研经费加成个人年薪，也不要把可能附条件、互斥或分期发放的补贴合计成无条件待遇。
- 历史参考持续保留原公告年份和原文出处；今年或下一届未发现公告只能表述为“当前已采集来源中未发现”，不能表述为已经证实没有招聘。

## 页面结构核验记录

以下选择器已经对2026-10-30下载的公开原始HTML验证；不是根据站点名称猜测。

| 来源 | 列表项目 | 标题/链接 | 日期 | 正文 |
| --- | --- | --- | --- | --- |
| 山西大学 | `.lm_list > ul > li` | `a` | `span` | `#vsb_content_2` |
| 太原理工 | `div.animate-onscroll[id^="line_"]` | `a h2` / `a` | `h2`内日期 | VSB正文 |
| 山西农业大学 | `ul.ej-news-list > li` | `.ej-news-word p[title]` / `a` | `.ej-news-deta` | `#vsb_content_2` |
| 山西师范大学 | `li[id^="line_u"]` | `h3` / `a` | `.flex span` | `#vsb_content` |
| 中北大学 | `li[id^="line_u"]` | `span.tit` / `a` | `span.time` | `#vsb_content` |
| 太原科技大学 | `li[id^="line_u"]` | `h4` / `a` | 详情 `.arc-info` | `#vsb_content` |
| 省卫健委 | `.demo-right > ul > li` | 列表 `a:nth-of-type(2)`，详情 `.boxC > h3` | 列表 `span`，详情 `.artxx` | `.trs_editor_view` |
| 亚宝/吉林大学 | `ul.m-component-content__list__container > li` | `a` | 详情 `.m-detail-container__info`，兼容英文月份 | `.m-content-container` |
| 振东/天津商业大学 | `ul.company_index_info_zpul > li` | `.zw_title .p1` / `a.lizw` | `.zw_title .p2` | `.s_midin_con > .s_left`；独立薪资字段 `.pay` |
| 企业定向转载 | `.sort_rightcont > ul > li` | `a` | `span.date` | `.sort_rightcont2 .cont` |

卫健委每条列表项目有两个链接，第一个链接文字为空；其分页通过脚本写入 `index_1.shtml` 等地址。采集器只解析已经验证的分页模板和页数，不执行网站JavaScript。该站部分详情页的 `PubDate`、`ArticleTitle` 元数据残留2020年模板，标题和发布日期必须优先取正文可见的 `.boxC > h3` 与 `.artxx`。

为重现这次核验，研发临时下载缓存位于 `/tmp/shanxi-source-html/`，不是运行时依赖。主要文件对应：`rsc.sxu.edu.cn.html`、`tyut-list.html`、`sxau-list.html`、`sxnu-current-list.html`、`rlzyglc.nuc.edu.cn.html`、`tyust-list.html`、`wjw.shanxi.gov.cn.html` 为列表；`sxu-detail.html`、`www.tyut.edu.cn.html`、`sxau-detail.html`、`sxnu-detail.html`、`nuc-detail.html`、`tyust-detail.html`、`hospital-detail.html` 为正文。亚宝桌面企业列表为 `yabao-portal-company.html`，其完整招聘正文为 `enterprise-jlu.html`；其他企业页面以 `enterprise-` 前缀命名。长期回归测试应保留精简结构样例，避免把完整外站网页作为应用数据提交。
