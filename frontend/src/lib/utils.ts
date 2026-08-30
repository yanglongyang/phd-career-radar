import { clsx, type ClassValue } from "clsx";

export function cn(...inputs: ClassValue[]) {
  return clsx(inputs);
}

/**
 * 后端时间戳契约（Phase 5.1 收尾）：SQLite 不保留 tzinfo，API 返回的
 * datetime 字符串可能没有时区标记 —— **所有无时区的时间戳一律视为 UTC**。
 * 已带 Z / ±HH:MM 偏移的时间戳（如未来切 PostgreSQL）原样解析，不重复追加。
 */
export function parseBackendTimestamp(value: string): Date {
  const hasTimezone = /(?:Z|[+-]\d{2}:?\d{2})$/i.test(value);
  return new Date(hasTimezone ? value : `${value}Z`);
}

function localCalendarDate(d: Date): string {
  const m = String(d.getMonth() + 1).padStart(2, "0");
  const day = String(d.getDate()).padStart(2, "0");
  return `${d.getFullYear()}-${m}-${day}`;
}

/** 浏览器本地时区的今天（YYYY-MM-DD）。逾期判断不能用 UTC 日历日。 */
export function localToday(): string {
  return localCalendarDate(new Date());
}

/** date-only 字段（YYYY-MM-DD）原样展示；timestamp 按 UTC 契约解析后转本地日历日；
 *  非法字符串保守原样返回。 */
export function formatDate(value: string | null | undefined): string {
  if (!value) return "—";
  if (/^\d{4}-\d{2}-\d{2}$/.test(value)) return value;
  const d = parseBackendTimestamp(value);
  if (Number.isNaN(d.getTime())) return value;
  return localCalendarDate(d);
}

export const JOB_CATEGORY_LABELS: Record<string, string> = {
  university_faculty: "高校教学科研",
  university_research: "高校专职科研",
  postdoc: "博士后",
  research_institute: "科研院所",
  industry_rnd: "企业研发",
  other: "其他",
};

// 岗位信息筛选状态（JobDisposition）；求职流程状态由申请记录负责
export const JOB_STATUS_LABELS: Record<string, string> = {
  new: "新发现",
  reviewing: "查看中",
  shortlisted: "重点关注",
  ignored: "已忽略",
  closed: "已关闭",
};

// 详情页顶部"聘用"摘要：由 AcademicJobDetails 四轴派生（legacy position_nature 已退出展示）
export function employmentSummary(d: {
  establishment_status: string;
  tenure_status: string;
  contract_type: string;
  funding_source: string;
  is_up_or_out: boolean | null;
} | null): string {
  if (!d) return "未知 / 待确认";
  const parts = [
    ESTABLISHMENT_LABELS[d.establishment_status] ?? d.establishment_status,
    TENURE_LABELS[d.tenure_status] ?? d.tenure_status,
    CONTRACT_TYPE_LABELS[d.contract_type] ?? d.contract_type,
    FUNDING_SOURCE_LABELS[d.funding_source] ?? d.funding_source,
  ];
  if (d.is_up_or_out === true) parts.push("非升即走");
  return parts.join(" · ");
}

export const ESTABLISHMENT_LABELS: Record<string, string> = {
  established: "事业编",
  non_established: "非事业编",
  unknown: "未知 / 待确认",
};

export const TENURE_LABELS: Record<string, string> = {
  tenured: "长聘",
  tenure_track: "预聘 / Tenure-track",
  non_tenure: "非长聘",
  unknown: "未知 / 待确认",
};

export const CONTRACT_TYPE_LABELS: Record<string, string> = {
  open_ended: "无固定期限",
  fixed_term: "固定期限",
  unknown: "未知 / 待确认",
};

export const FUNDING_SOURCE_LABELS: Record<string, string> = {
  university: "学校经费",
  department: "院系经费",
  pi: "PI 经费",
  external: "外部经费",
  mixed: "混合经费",
  unknown: "未知 / 待确认",
};

export const RECOMMENDATION_LABELS: Record<string, string> = {
  S: "强烈关注",
  A: "值得申请",
  B: "可以申请",
  C: "备选",
  D: "优先级低",
  X: "触发排除",
};

export const RISK_LABELS: Record<string, string> = {
  low: "低风险",
  medium: "中风险",
  high: "高风险",
  critical: "极高风险",
};

export const CONFIDENCE_LABELS: Record<string, string> = {
  high: "可信度高",
  medium: "可信度中",
  low: "可信度低",
};

// 申请 CRM 状态（ApplicationStatus）——14 态，看板列按此排列
export const APPLICATION_STATUS_ORDER = [
  "new", "reviewed", "shortlist", "contacting", "preparing", "applied",
  "written_test", "interview_1", "interview_2", "hr", "offer",
  "rejected", "withdrawn", "ignored",
] as const;

export const APPLICATION_STATUS_LABELS: Record<string, string> = {
  new: "新申请",
  reviewed: "已查看",
  shortlist: "入围",
  contacting: "洽联中",
  preparing: "准备材料",
  applied: "已投递",
  written_test: "笔试",
  interview_1: "一面",
  interview_2: "二面",
  hr: "HR 沟通",
  offer: "Offer",
  rejected: "已被拒",
  withdrawn: "已撤回",
  ignored: "已忽略",
};

export function applicationStatusTone(status: string) {
  switch (status) {
    case "offer":
      return "green" as const;
    case "rejected":
    case "withdrawn":
      return "red" as const;
    case "ignored":
      return "zinc" as const;
    case "applied":
    case "written_test":
    case "interview_1":
    case "interview_2":
    case "hr":
      return "blue" as const;
    case "preparing":
    case "contacting":
      return "amber" as const;
    default:
      return "neutral" as const;
  }
}
