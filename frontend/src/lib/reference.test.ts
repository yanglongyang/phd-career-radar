import { afterEach, describe, expect, it, vi } from "vitest";
import { readCollectionDetails, referenceLabel, referenceNotice, safeWebUrl, sourceStatusLabel } from "./reference";
import { getCollectorScheduler, listDiscoveredJobs, startCollectors } from "../services/api";

afterEach(() => vi.unstubAllGlobals());

describe("招聘历史参考的证据展示", () => {
  it("明确区分历史、当年、未来年度和未知，不把公告年份视为在招", () => {
    expect(referenceLabel("historical", 2025)).toBe("2025 年 · 历史参考");
    expect(referenceLabel("current_year", 2026)).toBe("2026 年 · 当年公告");
    expect(referenceLabel("upcoming", 2027)).toBe("2027 年 · 未来年度");
    expect(referenceLabel("unknown", null)).toBe("年份待确认");
    expect(referenceNotice("historical")).toContain("不能视为今年承诺");
    expect(referenceNotice("current_year")).toContain("不代表报名仍开放");
  });

  it("只提供完整http(s)原始链接，拒绝脚本、文件、相对链接及内嵌凭据", () => {
    for (const value of ["javascript:alert(1)", "file:///tmp/doc.pdf", "data:text/html,x", "/download.pdf", "https://user:pass@example.org/a", null]) {
      expect(safeWebUrl(value)).toBeNull();
    }
    expect(safeWebUrl("https://example.edu.cn/jobs/file.pdf?download=1")).toBe("https://example.edu.cn/jobs/file.pdf?download=1");
  });

  it("附件和图片来自真实元信息，过滤畸形条目及重复链接，保留失败原因", () => {
    const details = readCollectionDetails({
      attachments: [null, { url: "javascript:alert(1)", title: "bad" },
        { url: "https://example.edu.cn/jobs.pdf", title: "岗位表" },
        { url: "https://example.edu.cn/jobs.pdf", title: "重复" }],
      images: [{ url: "https://example.edu.cn/pay.png", alt: "人才待遇" }],
      detail_status: "failed", detail_error: "HTTP 403", warnings: [null, "附件尚未解析"],
    });
    expect(details.attachments).toEqual([{ url: "https://example.edu.cn/jobs.pdf", title: "岗位表" }]);
    expect(details.images[0].title).toBe("人才待遇");
    expect(details.detailError).toBe("HTTP 403");
    expect(details.warnings).toEqual(["附件尚未解析"]);
    expect(readCollectionDetails(null).attachments).toEqual([]);
  });

  it("已配置或未启用来源不显示为采集成功", () => {
    expect(sourceStatusLabel(null)).toBe("尚无采集记录");
    expect(sourceStatusLabel("success", false)).toBe("未启用");
    expect(sourceStatusLabel("failed")).toBe("最近采集失败");
    expect(sourceStatusLabel("partial_failure")).toBe("部分采集失败");
  });
});

describe("历史采集 API 契约", () => {
  it("后台补抓保留地区、年数和选择的来源", async () => {
    const fetchMock = vi.fn().mockResolvedValue({ ok: true, json: async () => ({ status: "started" }) });
    vi.stubGlobal("fetch", fetchMock);
    const payload = { mode: "history" as const, province: "山西", history_years: 3, source_ids: ["sxu_faculty"] };
    await startCollectors(payload);
    expect(fetchMock.mock.calls[0][0]).toBe("/api/collectors/start");
    expect(fetchMock.mock.calls[0][1].method).toBe("POST");
    expect(JSON.parse(fetchMock.mock.calls[0][1].body)).toEqual(payload);
  });

  it("列表请求携带历史状态、公告年份和页码", async () => {
    const fetchMock = vi.fn().mockResolvedValue({ ok: true, json: async () => ({ items: [], total: 0 }) });
    vi.stubGlobal("fetch", fetchMock);
    await listDiscoveredJobs({ province: "山西", reference_status: "historical", announcement_year: 2025, page: 3, page_size: 30 });
    const params = new URLSearchParams(fetchMock.mock.calls[0][0].split("?")[1]);
    expect(params.get("province")).toBe("山西");
    expect(params.get("reference_status")).toBe("historical");
    expect(params.get("announcement_year")).toBe("2025");
    expect(params.get("page")).toBe("3");
  });

  it("任务冲突展示后端原因，不报告为启动成功", async () => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue({ ok: false, status: 409, json: async () => ({ detail: "已有采集任务运行中" }) }));
    await expect(startCollectors({ mode: "recent" })).rejects.toMatchObject({ status: 409, message: "已有采集任务运行中" });
  });

  it("自动采集状态使用独立接口", async () => {
    const fetchMock = vi.fn().mockResolvedValue({ ok: true, json: async () => ({ enabled: true, running: false }) });
    vi.stubGlobal("fetch", fetchMock);
    await getCollectorScheduler();
    expect(fetchMock.mock.calls[0][0]).toBe("/api/collectors/scheduler");
  });
});
