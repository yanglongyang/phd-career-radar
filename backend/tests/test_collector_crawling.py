"""Offline regression coverage for pagination, history seeds and partial failures."""

from dataclasses import replace

import pytest
import yaml

from app.collectors.config import SourceConfig, SourceConfigError, load_sources, parse_source
from app.collectors.html_detail import HtmlDetailCollector, read_article
from app.collectors.html_list import HtmlListCollector
from app.collectors.http import SafeFetcher, SafeFetchError, decode_page

BASE = "https://hr.example.edu.cn/"


@pytest.fixture(autouse=True)
def fixed_announcement_year(monkeypatch):
    monkeypatch.setattr("app.services.announcement_reference.current_year", lambda: 2026)


class Fetcher:
    def __init__(self, pages):
        self.pages = pages
        self.calls = []

    def fetch(self, url, **kwargs):
        self.calls.append(url)
        page = self.pages[url]
        if isinstance(page, Exception):
            raise page
        return url, "text/html", page


def source(**kwargs):
    config = SourceConfig(
        id="shanxi", name="山西高校", type="html_list", enabled=True,
        url=BASE + "index.htm", province="山西", location="山西 太原",
        selectors={"item": "ul.jobs li", "title": "a", "link": "a", "date": "span"},
        pagination={"max_pages": 3, "max_items": 10},
    )
    return replace(config, **kwargs)


def listing(identifier, next_href=None):
    next_link = f'<a href="{next_href}">下一页</a>' if next_href else ""
    return (f'<ul class="jobs"><li><a href="/{identifier}.htm">{identifier}年博士招聘</a>'
            f'<span>{identifier}-04-03</span></li></ul>{next_link}')


def test_history_pagination_deduplicates_and_preserves_old_announcements():
    collector = HtmlListCollector(source(scope="history", history={"max_pages": 3}))
    collector._fetcher = Fetcher({
        BASE + "index.htm": listing(2025, "page2.htm"),
        BASE + "page2.htm": listing(2024, "page3.htm") + listing(2025),
        BASE + "page3.htm": listing(2023),
    })
    jobs = collector.collect()
    assert [job.published_at_raw for job in jobs] == ["2025-04-03", "2024-04-03", "2023-04-03"]
    assert jobs[-1].location_hint == "山西 太原"
    assert not collector.warnings


def test_pagination_cycle_is_stopped_and_reported():
    collector = HtmlListCollector(source())
    collector._fetcher = Fetcher({BASE + "index.htm": listing(2025, "index.htm")})
    assert len(collector.collect()) == 1
    assert collector._fetcher.calls == [BASE + "index.htm"]
    assert any("重复" in text for text in collector.warnings)


def test_second_page_failure_preserves_first_page_and_reports_partial_result():
    collector = HtmlListCollector(source())
    collector._fetcher = Fetcher({
        BASE + "index.htm": listing(2025, "page2.htm"),
        BASE + "page2.htm": SafeFetchError("HTTP 503"),
    })
    assert len(collector.collect()) == 1
    assert any("第 2 页抓取失败" in text for text in collector.warnings)


def test_initial_page_failure_is_not_silently_empty():
    collector = HtmlListCollector(source())
    collector._fetcher = Fetcher({BASE + "index.htm": SafeFetchError("HTTP 403")})
    with pytest.raises(SafeFetchError, match="403"):
        collector.collect()


def test_next_page_cannot_leave_source_origin():
    collector = HtmlListCollector(source())
    collector._fetcher = Fetcher({BASE + "index.htm": listing(2025, "https://other.test/next")})
    assert len(collector.collect()) == 1
    assert collector._fetcher.calls == [BASE + "index.htm"]
    assert any("其他站点" in text for text in collector.warnings)


def test_trs_template_uses_page_count_without_javascript_execution():
    collector = HtmlListCollector(source(
        scope="history", history={"max_pages": 10},
        pagination={"url_template": "index_{page}.shtml", "start_page": 1},
    ))
    marker = '<script>var countPage = 2; document.write("not executed");</script>'
    collector._fetcher = Fetcher({
        BASE + "index.htm": listing(2025) + marker,
        BASE + "index_1.shtml": listing(2024) + marker,
    })
    assert len(collector.collect()) == 2
    assert len(collector._fetcher.calls) == 2
    assert not collector.warnings


def test_history_limits_do_not_override_recent_refresh_limits():
    config = source(pagination={"max_pages": 1}, history={"max_pages": 2})
    recent = HtmlListCollector(config)
    history = HtmlListCollector(replace(config, scope="history"))
    pages = {BASE + "index.htm": listing(2025, "page2.htm"), BASE + "page2.htm": listing(2024)}
    recent._fetcher = Fetcher(pages)
    history._fetcher = Fetcher(pages)
    assert len(recent.collect()) == 1
    assert len(history.collect()) == 2


def test_max_items_bounds_detail_fetches():
    collector = HtmlListCollector(source(
        pagination={"max_pages": 2, "max_items": 1},
        detail={"fetch_detail": True, "content_selector": "article"},
    ))
    collector._fetcher = Fetcher({
        BASE + "index.htm": listing(2025) + listing(2024),
        BASE + "2025.htm": "<article>博士招聘</article>",
    })
    assert len(collector.collect()) == 1
    assert BASE + "2024.htm" not in collector._fetcher.calls
    assert any("上限" in text for text in collector.warnings)


def test_appointment_notices_do_not_consume_detail_budget():
    collector = HtmlListCollector(source(
        pagination={"max_pages": 2, "max_items": 1}, filters={"exclude_keywords": ["拟聘", "公示"]},
        detail={"fetch_detail": True, "content_selector": "article"},
    ))
    notices = '<ul class="jobs"><li><a href="/result.htm">2025拟聘公示</a><span>2025-04-03</span></li></ul>'
    collector._fetcher = Fetcher({
        BASE + "index.htm": notices + listing(2025),
        BASE + "2025.htm": "<article>博士招聘。拟聘人选公示。</article>",
    })
    # Include 公示 in the title words to exercise exclusion rather than the generic
    # recruitment-title predicate (many real notices include 招聘 as well).
    collector.source.selectors["title_require_words"] = ["招聘", "公示"]
    jobs = collector.collect()
    assert len(jobs) == 1
    assert "公示" in jobs[0].description_raw
    assert collector.prefiltered_count == 1
    assert BASE + "result.htm" not in collector._fetcher.calls


def test_vsb_sibling_attachments_are_kept_without_page_navigation():
    html = """<nav><a href="/policy.pdf">无关政策</a></nav>
        <form name="_newscontent_fromname"><div id="vsb_content">招聘岗位详见附件</div>
        <ul><li><a href="/jobs.xlsx">岗位表.xlsx</a></li></ul></form>"""
    article = read_article(Fetcher({BASE: html}), source(), BASE)
    assert article["payload"]["attachments"] == [
        {"url": BASE + "jobs.xlsx", "title": "岗位表.xlsx", "parsed": False},
    ]


def test_salary_table_preserves_column_labels_amounts_and_nested_paragraphs():
    from app.services.announcement_reference import BENEFIT_WORDS, excerpt

    html = """<article><div><p>优秀博士可获<strong>40</strong><span>万元</span>安家费。</p>
        <table><thead><tr><th>人才类别</th><th>安家费</th><th>科研启动经费</th></tr></thead>
        <tbody><tr><td><p><span>A类博士</span></p></td><td><strong>40万元</strong></td><td>20万元</td></tr>
        <tr><td>B类博士</td><td>30万元</td><td>10万元</td></tr></tbody></table>
        <p>服务期<span>五年</span>，详细条件以合同为准。</p></div></article>"""
    article = read_article(Fetcher({BASE: html}), source(), BASE)
    text = article["description"]
    assert "优秀博士可获40万元安家费。" in text
    assert "人才类别：A类博士 | 安家费：40万元 | 科研启动经费：20万元" in text
    assert "人才类别：B类博士 | 安家费：30万元 | 科研启动经费：10万元" in text
    assert text.count("A类博士") == 1
    assert text.count("服务期五年") == 1
    benefits = excerpt(text, BENEFIT_WORDS)
    assert "安家费：40万元" in benefits
    assert "安家费：30万元" in benefits
    assert "科研启动经费：10万元" in benefits


def test_merged_table_headings_keep_order_without_inventing_column_mapping():
    html = """<article><table><tr><th colspan="2">博士人才待遇标准</th></tr>
        <tr><th>人才类别</th><th>安家费</th></tr>
        <tr><td>A类</td><td>40万元</td></tr><tr><td>B类</td><td>30万元</td></tr>
        </table><p>图片详见<a href="/benefits.png">待遇图</a></p><img src="/benefits.png"></article>"""
    article = read_article(Fetcher({BASE: html}), source(), BASE)
    text = article["description"]
    assert "表格列（博士人才待遇标准 / 人才类别 | 安家费）：A类 | 40万元" in text
    assert "表格列（博士人才待遇标准 / 人才类别 | 安家费）：B类 | 30万元" in text
    assert text.count("40万元") == 1
    assert article["payload"]["images"][0]["parsed"] is False


def test_history_skips_current_and_upcoming_before_spending_detail_budget():
    collector = HtmlListCollector(source(
        scope="history", history={"years": 3, "max_pages": 3, "max_items": 1},
        detail={"fetch_detail": True, "content_selector": "article"},
    ))
    collector._fetcher = Fetcher({
        BASE + "index.htm": listing(2027, "page2.htm"),
        BASE + "page2.htm": listing(2026, "page3.htm"),
        BASE + "page3.htm": listing(2025),
        BASE + "2025.htm": "<article>安家费40万元</article>",
    })
    jobs = collector.collect()
    assert [job.title for job in jobs] == ["2025年博士招聘"]
    assert collector._fetcher.calls == [
        BASE + "index.htm", BASE + "page2.htm", BASE + "page3.htm", BASE + "2025.htm",
    ]
    assert collector.recency_prefiltered_count == 2
    assert not collector.warnings


def test_history_honors_requested_year_window_and_does_not_warn_for_filtered_only_page():
    collector = HtmlListCollector(source(scope="history", history={"years": 2}))
    collector._fetcher = Fetcher({BASE + "index.htm": listing(2023) + listing(2022)})
    assert collector.collect() == []
    assert collector.recency_prefiltered_count == 2
    assert not collector.warnings


def test_history_keeps_unknown_and_ambiguous_years_for_review():
    collector = HtmlListCollector(source(scope="history", history={"years": 3}))
    collector._fetcher = Fetcher({BASE + "index.htm": """<ul class="jobs">
        <li><a href="/unknown.htm">长期博士招聘</a></li>
        <li><a href="/ambiguous.htm">2024—2025年博士招聘</a><span>2026-01-01</span></li>
        </ul>"""})
    assert len(collector.collect()) == 2
    assert collector.recency_prefiltered_count == 0


def test_history_seed_year_filter_avoids_expired_and_current_requests():
    collector = HtmlDetailCollector(source(
        type="html_detail", scope="history", history={"years": 3, "max_items": 2}, raw={"seeds": [
            {"url": BASE + "2022.htm", "title": "2022年博士招聘"},
            {"url": BASE + "2026.htm", "title": "博士招聘", "published_at": "2026-03-01"},
            {"url": BASE + "2025.htm", "title": "2025年博士招聘"},
            {"url": BASE + "unknown.htm", "title": "长期人才政策"},
        ]},
    ))
    collector._fetcher = Fetcher({
        BASE + "2025.htm": "<article>博士招聘，提供安家费</article>",
        BASE + "unknown.htm": "<article>人才政策，每年动态调整。</article>",
    })
    assert len(collector.collect()) == 2
    assert collector._fetcher.calls == [BASE + "2025.htm", BASE + "unknown.htm"]
    assert collector.recency_prefiltered_count == 2
    assert not collector.warnings


def test_article_year_overrides_stale_seed_and_preserves_original_metadata():
    collector = HtmlDetailCollector(source(type="html_detail", raw={"seeds": [
        {"url": BASE + "updated.htm", "title": "2025年博士招聘", "published_at": "2025-03-01"},
    ]}))
    collector._fetcher = Fetcher({BASE + "updated.htm": """
        <meta name="ArticleTitle" content="2026年博士招聘"><meta name="PubDate" content="2026-05-02">
        <h1>人才招聘</h1><article>2026年安家费50万元</article>
    """})
    job = collector.collect()[0]
    assert job.title == "2026年博士招聘"
    assert job.published_at_raw == "2026-05-02"
    assert job.raw_payload["seed_title"] == "2025年博士招聘"
    assert job.raw_payload["seed_published_at"] == "2025-03-01"
    assert "2025" in job.raw_payload["metadata_conflict"]
    assert collector.warnings


def test_article_year_overrides_stale_list_without_reusing_old_publication_date():
    collector = HtmlListCollector(source(detail={"fetch_detail": True}))
    collector._fetcher = Fetcher({
        BASE + "index.htm": listing(2025),
        BASE + "2025.htm": "<h1>2026年博士招聘</h1><article>2026年安家费50万元</article>",
    })
    job = collector.collect()[0]
    assert job.title == "2026年博士招聘"
    assert job.published_at_raw is None
    assert job.raw_payload["list_title"] == "2025年博士招聘"
    assert job.raw_payload["list_published_at"] == "2025-04-03"


def test_generic_document_title_cannot_replace_a_seed_title():
    collector = HtmlDetailCollector(source(type="html_detail", raw={"seeds": [
        {"url": BASE, "title": "2025年博士招聘", "published_at": "2025-03-01"},
    ]}))
    collector._fetcher = Fetcher({BASE: "<title>2026年大学官网</title><article>博士招聘待遇面议</article>"})
    job = collector.collect()[0]
    assert job.title == "2025年博士招聘"
    assert job.published_at_raw == "2025-03-01"
    assert not collector.warnings


def test_history_rechecks_year_after_repurposed_seed_url_is_fetched():
    collector = HtmlDetailCollector(source(type="html_detail", scope="history", raw={"seeds": [
        {"url": BASE, "title": "2025年博士招聘", "published_at": "2025-03-01"},
    ]}))
    collector._fetcher = Fetcher({BASE: "<h1>2026年博士招聘</h1><article>2026年安家费50万元</article>"})
    assert collector.collect() == []
    assert collector.recency_prefiltered_count == 1
    assert any("正文标题为 2026" in warning for warning in collector.warnings)


def test_official_university_english_publication_date_is_normalized():
    html = """<h1>企业人才招聘</h1><div class="published">发布时间：Sep 29, 2024 5:09:20 PM</div>
        <article>招聘药物研发博士，待遇面议。</article>"""
    article = read_article(Fetcher({BASE: html}), source(detail={"date_selector": ".published"}), BASE)
    assert article["published_at"] == "2024-09-29"


def test_explicit_article_selectors_override_stale_government_template_metadata():
    html = """<meta name="ArticleTitle" content="2020年医药卫生体制改革通知">
        <meta name="PubDate" content="2020-12-28 09:50:21">
        <div class="boxC"><h3>山西白求恩医院2025年公开招聘博士研究生公告</h3>
        <div class="artxx">发布时间：2025-03-03</div>
        <article>博士人才安家费，按岗位条件执行。</article></div>"""
    article = read_article(Fetcher({BASE: html}), source(detail={
        "title_selector": ".boxC > h3", "date_selector": ".artxx", "content_selector": "article",
    }), BASE)
    assert article["title"] == "山西白求恩医院2025年公开招聘博士研究生公告"
    assert article["title_source"] == "configured_selector"
    assert article["published_at"] == "2025-03-03"


def test_salary_selector_keeps_bare_amount_with_explicit_salary_semantics():
    from app.services.announcement_reference import BENEFIT_WORDS, excerpt

    html = """<div class="pay">6000-8000元</div>
        <article>药品研发岗位，提供住宿。</article><footer>联系电话12345678900</footer>"""
    article = read_article(Fetcher({BASE: html}), source(detail={"salary_selector": ".pay"}), BASE)
    assert article["payload"]["salary_text"] == "6000-8000元"
    assert article["description"].startswith("薪资（原文）：6000-8000元\n")
    assert "6000-8000元" in excerpt(article["description"], BENEFIT_WORDS)
    assert "12345678900" not in article["description"]
    without_selector = read_article(Fetcher({BASE: html}), source(), BASE)
    assert "salary_text" not in without_selector["payload"]
    assert "薪资（原文）" not in without_selector["description"]


def test_empty_selector_is_a_visible_warning():
    collector = HtmlListCollector(source())
    collector._fetcher = Fetcher({BASE + "index.htm": "<html>请启用JavaScript</html>"})
    assert collector.collect() == []
    assert any("选择器未匹配" in text for text in collector.warnings)


def test_detail_failure_retains_list_evidence():
    collector = HtmlListCollector(source(detail={"fetch_detail": True, "content_selector": "article"}))
    collector._fetcher = Fetcher({
        BASE + "index.htm": listing(2025), BASE + "2025.htm": SafeFetchError("HTTP 502"),
    })
    job = collector.collect()[0]
    assert job.description_raw is None
    assert job.published_at_raw == "2025-04-03"
    assert job.raw_payload["detail_status"] == "failed"
    assert "502" in job.raw_payload["detail_error"]
    assert collector.warnings


def test_article_records_unparsed_documents_and_images_and_keeps_requirements():
    config = source(detail={"content_selector": "article"})
    fetcher = Fetcher({BASE + "2025.htm": """
        <meta name="PubDate" content="2025-02-19"><h1>2025年博士招聘公告</h1>
        <nav>导航不可作正文</nav><article><p>博士要求：生物学。拟聘人选将进行公示。</p>
        <p>安家费 30 万元。</p><a href="/files/jobs.xlsx">岗位条件表.xlsx</a>
        <a href="/download?id=123">附件：人才待遇</a><img src="/salary.png" alt="待遇表">
        <script>tracking()</script></article>
    """})
    article = read_article(fetcher, config, BASE + "2025.htm")
    assert "公示" in article["description"]  # filtering must not remove a valid full announcement
    assert "安家费" in article["description"]
    assert "tracking" not in article["description"]
    assert "导航" not in article["description"]
    assert article["published_at"] == "2025-02-19"
    assert [link["url"] for link in article["payload"]["attachments"]] == [
        BASE + "files/jobs.xlsx", BASE + "download?id=123",
    ]
    assert article["payload"]["images"][0]["url"] == BASE + "salary.png"
    assert all(not link["parsed"] for link in article["payload"]["attachments"])
    assert fetcher.calls == [BASE + "2025.htm"]  # attachments were not downloaded


def test_missing_content_selector_does_not_import_navigation():
    article = read_article(
        Fetcher({BASE: "<h1>招聘入口</h1><nav>人才招聘 首页 2026-01-01</nav>"}),
        source(detail={"content_selector": "article"}), BASE,
    )
    assert article["description"] is None
    assert article["payload"]["detail_status"] == "missing"
    assert article["published_at"] is None


def test_application_deadline_is_not_used_as_publication_date():
    article = read_article(
        Fetcher({BASE: "<article>报名截止 2025-05-03；发布日期待确认。</article>"}),
        source(detail={"content_selector": "article"}), BASE,
    )
    assert article["published_at"] is None


def test_seed_collector_retains_failed_seed_and_other_successful_announcements():
    config = source(type="html_detail", scope="history", detail={"content_selector": "article"}, raw={
        "seeds": [
            {"url": BASE + "2024.htm", "title": "2024博士招聘", "published_at": "2024-03-05"},
            {"url": BASE + "2025.htm", "organization": "医院甲", "sector": "hospital"},
        ],
    })
    collector = HtmlDetailCollector(config)
    collector._fetcher = Fetcher({
        BASE + "2024.htm": SafeFetchError("HTTP 503"),
        BASE + "2025.htm": "<h1>2025博士招聘</h1><article>安家费需面议</article>",
    })
    jobs = collector.collect()
    assert len(jobs) == 2
    assert jobs[0].published_at_raw == "2024-03-05"
    assert jobs[0].raw_payload["detail_status"] == "failed"
    assert jobs[1].organization_hint == "医院甲"
    assert jobs[1].sector_hint == "hospital"
    assert jobs[1].description_raw == "安家费需面议"
    assert len(collector.warnings) == 1


@pytest.mark.parametrize("content_type,markup", [
    ("text/html; charset=gb2312", "<article>生物学博士招聘</article>"),
    ("text/html", '<meta charset="GBK"><article>生物学博士招聘</article>'),
    ("text/html", "<article>生物学博士招聘</article>"),
])
def test_chinese_legacy_encoding(content_type, markup):
    assert "生物学博士招聘" in decode_page(markup.encode("gb18030"), content_type)


def test_redirect_to_unsupported_protocol_is_rejected(monkeypatch):
    monkeypatch.setattr("app.collectors.http.assert_public_host", lambda host: None)
    fetcher = SafeFetcher()
    monkeypatch.setattr(fetcher, "_once", lambda url, timeout: (302, "", "file:///etc/passwd", url, b""))
    with pytest.raises(SafeFetchError, match="http/https"):
        fetcher.fetch(BASE)


@pytest.mark.parametrize("extra", [
    {"pagination": {"max_pages": 0}}, {"history": {"max_items": -1}},
    {"history": {"enabled": "yes"}}, {"detail": {"fetch_detail": "false"}},
    {"pagination": {"url_template": "index_{secret}.htm"}}, {"request": {"max_bytes": True}},
    {"pagination": {"start_page": -1}}, {"seeds": [{"url": "file:///tmp/a"}]},
])
def test_new_config_bounds_are_validated(extra):
    with pytest.raises(SourceConfigError):
        parse_source({"id": "a", "type": "html_list", "enabled": True, "url": BASE, **extra})


@pytest.mark.parametrize("empty,include,expected_ids", [
    (False, True, ["custom", "new"]), (False, False, ["custom"]), (True, True, []),
])
def test_additive_source_pack_respects_user_overrides(tmp_path, monkeypatch, empty, include, expected_ids):
    monkeypatch.setattr("app.collectors.config.CONFIG_DIR", tmp_path)
    user = {"id": "custom", "name": "我的设置", "type": "html_list", "enabled": False, "url": BASE}
    main = {"schema_version": 2, "include_shanxi": include, "collectors": [] if empty else [user]}
    extra = {"collectors": [{**user, "enabled": True}, {**user, "id": "new", "enabled": True}]}
    (tmp_path / "sources.yaml").write_text(yaml.safe_dump(main), encoding="utf-8")
    (tmp_path / "sources_shanxi.yaml").write_text(yaml.safe_dump(extra), encoding="utf-8")
    parsed, errors = load_sources()
    assert not errors
    assert [item.id for item in parsed] == expected_ids
    if parsed:
        assert not parsed[0].enabled
        assert parsed[0].name == "我的设置"
