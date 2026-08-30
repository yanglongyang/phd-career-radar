import { describe, expect, it } from "vitest";
import { formatDate, parseBackendTimestamp } from "./utils";

/* Phase 5.1 收尾：后端时间戳序列化契约。
   断言全部基于 toISOString / 字符串比较，与运行机器的本地时区无关。 */

describe("parseBackendTimestamp", () => {
  it("把无时区的 backend timestamp 按 UTC 解释（SQLite 丢 tzinfo 的契约）", () => {
    expect(parseBackendTimestamp("2026-08-30T17:00:00").toISOString()).toBe(
      "2026-08-30T17:00:00.000Z",
    );
  });

  it("已带 Z 的时间戳不重复追加", () => {
    expect(parseBackendTimestamp("2026-08-30T17:00:00Z").toISOString()).toBe(
      "2026-08-30T17:00:00.000Z",
    );
  });

  it("已带数字偏移（如 +08:00）正确换算且不追加 Z", () => {
    expect(parseBackendTimestamp("2026-08-30T17:00:00+08:00").toISOString()).toBe(
      "2026-08-30T09:00:00.000Z",
    );
    expect(parseBackendTimestamp("2026-08-30T17:00:00+0800").toISOString()).toBe(
      "2026-08-30T09:00:00.000Z",
    );
  });

  it("naive 与带 Z 的同一时刻解析结果完全一致", () => {
    expect(parseBackendTimestamp("2026-08-30T17:00:00").getTime()).toBe(
      parseBackendTimestamp("2026-08-30T17:00:00Z").getTime(),
    );
  });
});

describe("formatDate", () => {
  it("date-only 字段原样返回，绝不做时区转换", () => {
    expect(formatDate("2026-09-05")).toBe("2026-09-05");
    expect(formatDate("2026-08-31")).toBe("2026-08-31");
  });

  it("naive timestamp 与带 Z 的 timestamp 展示同一本地日历日（UTC 契约生效）", () => {
    expect(formatDate("2026-08-30T17:00:00")).toBe(formatDate("2026-08-30T17:00:00Z"));
  });

  it("非法字符串保守原样返回", () => {
    expect(formatDate("not-a-date")).toBe("not-a-date");
  });

  it("空值返回占位符", () => {
    expect(formatDate(null)).toBe("—");
    expect(formatDate(undefined)).toBe("—");
    expect(formatDate("")).toBe("—");
  });
});
