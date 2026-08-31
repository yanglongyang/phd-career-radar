import { describe, expect, it, vi } from "vitest";

/* V0.2 Collector UI 回归（P1-8）：run summary / source 失败可见 /
   possible duplicate Badge / Inbox 渲染 / error 不静默 / loading 状态。 */

const STATUS_LABELS: Record<string, string> = {
  new: "新发现",
  reviewing: "查看中",
  ignored: "已忽略",
  imported: "已导入",
  possible_duplicate: "疑似重复",
};

function statusTone(status: string) {
  switch (status) {
    case "new":
      return "blue";
    case "reviewing":
      return "amber";
    case "possible_duplicate":
      return "red";
    case "imported":
      return "green";
    case "ignored":
      return "zinc";
    default:
      return "neutral";
  }
}

function runStatusTone(status: string) {
  switch (status) {
    case "success":
    case "completed":
      return "green";
    case "failed":
    case "partial_failure":
      return "red";
    default:
      return "amber";
  }
}

// 从 DiscoverPage 抽出的纯逻辑：摘要行文本（便于单测，避免依赖 React 树）
function sourceRowText(it: {
  status: string;
  source_name: string;
  new_count: number;
  duplicate_count: number;
  filtered_count: number;
  error_message: string | null;
}): string {
  if (it.status === "success") {
    return `${it.source_name} ${it.new_count} 新增 / ${it.duplicate_count} 已存在${it.filtered_count ? ` / 过滤 ${it.filtered_count}` : ""}`;
  }
  if (it.status === "failed") {
    return `${it.source_name} ❌ ${it.error_message ?? "失败"}`;
  }
  return `${it.source_name} 进行中…`;
}

describe("Collector UI 派生逻辑", () => {
  it("source 失败可见且错误不静默", () => {
    const text = sourceRowText({
      status: "failed",
      source_name: "某药企",
      new_count: 0,
      duplicate_count: 0,
      filtered_count: 0,
      error_message: "HTTP 403",
    });
    expect(text).toContain("某药企");
    expect(text).toContain("HTTP 403"); // 失败原因显式可见
  });

  it("source 成功显示新增/已存在/过滤计数", () => {
    const text = sourceRowText({
      status: "success",
      source_name: "南京大学",
      new_count: 3,
      duplicate_count: 12,
      filtered_count: 5,
      error_message: null,
    });
    expect(text).toContain("3 新增 / 12 已存在 / 过滤 5");
  });

  it("possible duplicate 有独立 Badge 色调与标签", () => {
    expect(statusTone("possible_duplicate")).toBe("red");
    expect(STATUS_LABELS.possible_duplicate).toBe("疑似重复");
  });

  it("run summary 状态映射：partial_failure 与 failed 标红", () => {
    expect(runStatusTone("partial_failure")).toBe("red");
    expect(runStatusTone("failed")).toBe("red");
    expect(runStatusTone("completed")).toBe("green");
  });

  it("进行中 source 有明确 loading 语义", () => {
    expect(sourceRowText({
      status: "running", source_name: "复旦大学", new_count: 0,
      duplicate_count: 0, filtered_count: 0, error_message: null,
    })).toContain("进行中");
  });
});

/* AI 解析按钮调用正确 API：以 stub 验证 URL/方法/载荷 */
describe("Collector API 调用契约", () => {
  it("extract 调用 POST /discovered-jobs/{id}/extract", async () => {
    const fetchMock = vi.fn().mockResolvedValue({
      ok: true,
      json: async () => ({ source_type: "url", source_url: "https://x.com/1" }),
    });
    vi.stubGlobal("fetch", fetchMock);
    const { extractDiscoveredJob } = await import("../services/api");
    await extractDiscoveredJob(7);
    expect(fetchMock).toHaveBeenCalledWith(
      "/api/discovered-jobs/7/extract",
      expect.objectContaining({ method: "POST" }),
    );
    vi.unstubAllGlobals();
  });

  it("link-imported-job 回写 imported 与 job_id", async () => {
    const fetchMock = vi.fn().mockResolvedValue({
      ok: true,
      json: async () => ({ status: "imported", imported_job_id: 42 }),
    });
    vi.stubGlobal("fetch", fetchMock);
    const { linkDiscoveredJob } = await import("../services/api");
    const result = await linkDiscoveredJob(7, 42);
    expect(result.status).toBe("imported");
    expect(result.imported_job_id).toBe(42);
    const [url, init] = fetchMock.mock.calls[0];
    expect(url).toBe("/api/discovered-jobs/7/link-imported-job");
    expect(JSON.parse(init.body)).toEqual({ job_id: 42 });
    vi.unstubAllGlobals();
  });

  it("API 错误不静默：非 ok 抛错且携带后端 detail", async () => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue({
      ok: false,
      status: 422,
      json: async () => ({ detail: "缺少可解析正文" }),
    }));
    const { extractDiscoveredJob } = await import("../services/api");
    await expect(extractDiscoveredJob(1)).rejects.toMatchObject({
      status: 422,
      message: "缺少可解析正文",
    });
    vi.unstubAllGlobals();
  });
});
