import { describe, expect, it, vi } from "vitest";
import {
  SECTOR_LABELS,
  SECTOR_TABS,
  groupRunItemsBySector,
  sectorLabel,
  sectorQueryForTab,
  sectorTone,
} from "./sector";

/* V0.3 sector：tab → API 参数、badge 标签/色调、run 分组（纯函数）。 */

describe("sector 派生逻辑", () => {
  it("sector tab 切换映射正确的 API 参数", () => {
    expect(sectorQueryForTab("")).toBeUndefined();        // 全部 -> 不传
    expect(sectorQueryForTab("university")).toBe("university");
    expect(sectorQueryForTab("research_institute")).toBe("research_institute");
    expect(sectorQueryForTab("hospital")).toBe("hospital");
    expect(sectorQueryForTab("state_owned")).toBe("state_owned");
    expect(sectorQueryForTab("other,mixed")).toBe("other,mixed");  // 其他 -> 逗号列表
  });

  it("sector tabs 覆盖 全部/高校/科研院所/医院/央国企/企业/其他（V0.3.3）", () => {
    expect(SECTOR_TABS.map((t) => t.label)).toEqual([
      "全部", "高校", "科研院所", "医院", "央国企", "企业", "其他",
    ]);
  });

  it("sector badge 标签与色调正确（含 research_institute）", () => {
    expect(sectorLabel("university")).toBe("高校");
    expect(sectorLabel("research_institute")).toBe("科研院所");
    expect(sectorLabel("hospital")).toBe("医院");
    expect(sectorLabel("state_owned")).toBe("央国企");
    expect(sectorLabel("enterprise")).toBe("企业");
    expect(sectorLabel("mixed")).toBe("混合");
    expect(sectorLabel(null)).toBe("其他");   // 未知 -> 其他
    expect(sectorLabel("weird")).toBe("其他");
    expect(sectorTone("university")).toBe("blue");
    expect(sectorTone("research_institute")).toBe("violet");
    expect(sectorTone("hospital")).toBe("green");
    expect(sectorTone("state_owned")).toBe("red");
    expect(sectorTone("enterprise")).toBe("amber");
    expect(sectorTone("mixed")).toBe("orange");
    expect(sectorTone("other")).toBe("zinc");
  });

  it("run 结果按 sector 分组且顺序固定（科研院所在高校后），未知归入其他", () => {
    const items = [
      { sector: "enterprise", source_name: "E" },
      { sector: "research_institute", source_name: "化学所" },
      { sector: "hospital", source_name: "华西" },
      { sector: "university", source_name: "U1" },
      { sector: null, source_name: "X" },
      { sector: "mixed", source_name: "M" },
    ];
    const groups = groupRunItemsBySector(items);
    expect(groups.map((g) => g.sector)).toEqual([
      "university", "research_institute", "hospital", "enterprise", "mixed", "other",
    ]);
    expect(groups[0].items.map((i) => i.source_name)).toEqual(["U1"]);
    expect(groups[1].items.map((i) => i.source_name)).toEqual(["化学所"]);
    expect(groups[5].items.map((i) => i.source_name)).toEqual(["X"]);
  });
});

describe("Collector API 契约（V0.3）", () => {
  it("sector 筛选拼进 /discovered-jobs 查询串", async () => {
    const fetchMock = vi.fn().mockResolvedValue({
      ok: true,
      json: async () => ({ items: [], total: 0 }),
    });
    vi.stubGlobal("fetch", fetchMock);
    const { listDiscoveredJobs } = await import("../services/api");
    await listDiscoveredJobs({ sector: "other,mixed", status: "new", page_size: 50 });
    const [url] = fetchMock.mock.calls[0];
    expect(url).toContain("/discovered-jobs?");
    expect(url).toContain("sector=other%2Cmixed");
    expect(url).toContain("status=new");
    vi.unstubAllGlobals();
  });

  it("listCollectorSources 调用 GET /collectors/sources", async () => {
    const fetchMock = vi.fn().mockResolvedValue({
      ok: true,
      json: async () => ({ sources: [{ id: "s", sector: "university" }], config_errors: [] }),
    });
    vi.stubGlobal("fetch", fetchMock);
    const { listCollectorSources } = await import("../services/api");
    const data = await listCollectorSources();
    expect(data.sources[0].sector).toBe("university");
    expect(fetchMock).toHaveBeenCalledWith(
      "/api/collectors/sources",
      expect.objectContaining({}),
    );
    vi.unstubAllGlobals();
  });

  it("sector 标签与后端 DiscoveredJobOut.sector 契约一致", () => {
    expect(SECTOR_LABELS).toMatchObject({
      university: "高校",
      state_owned: "央国企",
      enterprise: "企业",
      mixed: "混合",
      other: "其他",
    });
  });
});
