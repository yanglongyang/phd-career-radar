import { clsx, type ClassValue } from "clsx";

export function cn(...inputs: ClassValue[]) {
  return clsx(inputs);
}

export function formatDate(value: string | null | undefined): string {
  if (!value) return "—";
  return value.slice(0, 10);
}

export const JOB_CATEGORY_LABELS: Record<string, string> = {
  university_faculty: "高校教学科研",
  university_research: "高校专职科研",
  postdoc: "博士后",
  research_institute: "科研院所",
  industry_rnd: "企业研发",
  other: "其他",
};

export const POSITION_NATURE_LABELS: Record<string, string> = {
  permanent: "事业编/长聘",
  tenure: "长聘",
  tenure_track: "预聘（非升即走）",
  pre_tenure: "预聘期内",
  fixed_term: "合同制",
  postdoc: "博士后",
  pi_funded: "PI经费聘用",
  unknown: "未知/待确认",
};

export const JOB_STATUS_LABELS: Record<string, string> = {
  new: "新发现",
  reviewing: "查看中",
  shortlisted: "重点关注",
  preparing: "准备投递",
  applied: "已投递",
  interviewing: "面试中",
  offer: "Offer",
  closed: "已关闭",
  ignored: "已忽略",
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
