/** Display only evidence returned by the collector; never infer an open application window. */
export function referenceLabel(status: string | null | undefined, year?: number | null): string {
  const prefix = year == null ? "" : `${year} 年 · `;
  if (status === "historical") return `${prefix}历史参考`;
  if (status === "current_year") return `${prefix}当年公告`;
  if (status === "upcoming") return `${prefix}未来年度`;
  return `${prefix}年份待确认`;
}

export function referenceNotice(status: string | null | undefined): string {
  if (status === "historical") {
    return "这是一份历史公告。岗位要求、薪资、安家费和科研启动费仅供了解往年政策，不能视为今年承诺或当前可申请岗位。请以该单位本年度公告为准。";
  }
  if (status === "current_year") {
    return "公告年份属于当年，不代表报名仍开放。申请条件、截止时间和待遇以原公告及后续通知为准。";
  }
  if (status === "upcoming") {
    return "这份公告面向未来招聘年度，具体报名时间与资格要求仍需核对原文。";
  }
  return "暂无法确认公告所属年份，请核对原文日期与招聘年度后再使用其中的条件和待遇。";
}

export function safeWebUrl(value: unknown): string | null {
  if (typeof value !== "string" || !value.trim()) return null;
  try {
    const url = new URL(value.trim());
    if (!["https:", "http:"].includes(url.protocol) || url.username || url.password) return null;
    return url.href;
  } catch {
    return null;
  }
}

export interface SourceLink {
  url: string;
  title: string;
}

function sourceLinks(value: unknown, fallback: string): SourceLink[] {
  if (!Array.isArray(value)) return [];
  const seen = new Set<string>();
  return value.flatMap((entry: unknown) => {
    if (entry === null || typeof entry !== "object") return [];
    const row = entry as Record<string, unknown>;
    const url = safeWebUrl(row.url);
    if (!url || seen.has(url)) return [];
    seen.add(url);
    const title = typeof row.title === "string" && row.title.trim()
      ? row.title.trim()
      : typeof row.alt === "string" && row.alt.trim() ? row.alt.trim() : fallback;
    return [{ url, title }];
  });
}

export function readCollectionDetails(payload: unknown) {
  const data = payload && typeof payload === "object" && !Array.isArray(payload)
    ? payload as Record<string, unknown> : {};
  return {
    attachments: sourceLinks(data.attachments, "原文附件"),
    images: sourceLinks(data.images, "原文图片"),
    detailStatus: typeof data.detail_status === "string" ? data.detail_status : null,
    detailError: typeof data.detail_error === "string" ? data.detail_error : null,
    warnings: Array.isArray(data.warnings)
      ? data.warnings.filter((item): item is string => typeof item === "string") : [],
  };
}

export function sourceStatusLabel(status: string | null | undefined, enabled = true): string {
  if (!enabled) return "未启用";
  switch (status) {
    case "success": return "最近采集成功";
    case "partial_failure":
    case "partial": return "部分采集失败";
    case "failed": return "最近采集失败";
    case "running": return "采集中";
    case "skipped": return "本次跳过";
    default: return "尚无采集记录";
  }
}
