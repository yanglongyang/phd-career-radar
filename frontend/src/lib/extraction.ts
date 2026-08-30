import type { ExtractionPreview } from "../types";
import type { JobCreateInput } from "../types";

export type FieldValue = string | number | boolean | null;

/**
 * Extraction → Preview → Save 的确定性字段映射（Phase 3.1）。
 *
 * 纯函数、不依赖 React：seedValuesFromPreview 决定预览里出现什么，
 * buildSavePayload 决定保存时提交什么 —— 两者共用同一张字段映射表，
 * 保证"AI 解析出来的信息不会在用户确认保存后丢失或串错类型"。
 */

export const AXIS_KEYS = [
  "establishment_status",
  "tenure_status",
  "contract_type",
  "funding_source",
] as const;

export const BOOL_KEYS = [
  "is_up_or_out",
  "independent_pi",
  "can_supervise_master",
  "can_supervise_phd",
] as const;

export const NUMBER_KEYS = ["contract_years"] as const;

// 学术文本字段 = 全部学术键 - 四轴 - 布尔 - 数字
export const ACADEMIC_TEXT_KEYS = [
  "first_contract_period",
  "midterm_review",
  "final_review",
  "publication_requirements",
  "grant_requirements",
  "teaching_requirements",
  "admin_requirements",
  "current_title",
  "promotion_path",
  "lab_space",
  "startup_funding",
  "startup_funding_terms",
  "master_quota",
  "phd_quota",
  "fixed_income",
  "performance_income",
  "housing_settlement",
  "housing_subsidy",
  "talent_housing",
  "regional_talent_subsidy",
] as const;

// Job 基本文本字段：AI 解析 → 预览编辑 → 保存（此前丢失的六个字段都在这里）
export const CORE_TEXT_KEYS = [
  "title",
  "organization",
  "department",
  "job_category",
  "country",
  "province",
  "city",
  "employment_type",
  "degree_requirement",
  "experience_requirement",
  "salary_text",
  "salary_currency",
  "salary_period",
] as const;

// 日期字段：YYYY-MM-DD 或空
export const DATE_KEYS = ["posted_at", "deadline"] as const;

function extractionValue(
  preview: ExtractionPreview,
  key: string,
): FieldValue {
  return (preview.extraction as unknown as Record<string, FieldValue>)[key] ?? null;
}

export function seedValuesFromPreview(
  preview: ExtractionPreview,
): Record<string, FieldValue> {
  const values: Record<string, FieldValue> = {};
  for (const key of [...CORE_TEXT_KEYS, ...DATE_KEYS]) {
    values[key] = extractionValue(preview, key);
  }
  for (const key of AXIS_KEYS) {
    values[key] = extractionValue(preview, key) ?? "unknown";
  }
  for (const key of BOOL_KEYS) {
    const v = extractionValue(preview, key);
    values[key] = typeof v === "boolean" ? v : null;
  }
  for (const key of NUMBER_KEYS) {
    const v = extractionValue(preview, key);
    values[key] = typeof v === "number" ? v : null;
  }
  for (const key of ACADEMIC_TEXT_KEYS) {
    values[key] = extractionValue(preview, key);
  }
  return values;
}

function toText(v: FieldValue): string | null {
  return typeof v === "string" && v.trim() !== "" ? v.trim() : null;
}

function toBool(v: FieldValue): boolean | null {
  return typeof v === "boolean" ? v : null;
}

function toNumber(v: FieldValue): number | null {
  // 确定性映射：只接受 number（预览由 seedValues 保证类型）；
  // 兼容用户在 number 输入框中产生的数字字符串。
  if (typeof v === "number") return Number.isFinite(v) ? v : null;
  if (typeof v === "string" && v.trim() !== "") {
    const n = Number(v);
    return Number.isFinite(n) ? n : null;
  }
  return null;
}

export function buildSavePayload(
  preview: ExtractionPreview,
  values: Record<string, FieldValue>,
  opts: { allowDuplicate?: boolean } = {},
): JobCreateInput {
  const job: JobCreateInput = {
    title: toText(values.title) ?? "",
    organization_name: toText(values.organization),
    department: toText(values.department),
    job_category: (toText(values.job_category) as string) || "other",
    country: toText(values.country),
    province: toText(values.province),
    city: toText(values.city),
    employment_type: toText(values.employment_type),
    posted_at: toText(values.posted_at),
    deadline: toText(values.deadline),
    degree_requirement: toText(values.degree_requirement),
    experience_requirement: toText(values.experience_requirement),
    salary_text: toText(values.salary_text),
    salary_currency: toText(values.salary_currency),
    salary_period: toText(values.salary_period),
    // 原文始终随岗位保存，供版本监控与去重使用
    description_raw: preview.source_text,
    // provenance 来自 Preview 本身，而不是独立的 React state —— 不可能串单
    source_url: preview.source_url,
    status: "new",
    academic_details: {},
    import_audit: {
      ingestion_method: preview.source_type,
      source_url: preview.source_url,
      provider: preview.provider,
      model: preview.model,
      prompt_version: preview.prompt_version,
      extraction_json: preview.extraction as unknown as Record<string, unknown>,
    },
    allow_duplicate: opts.allowDuplicate ?? false,
  };

  const academic: Record<string, FieldValue> = {};
  for (const key of AXIS_KEYS) {
    academic[key] = toText(values[key]) ?? "unknown";
  }
  for (const key of BOOL_KEYS) {
    academic[key] = toBool(values[key]);
  }
  for (const key of NUMBER_KEYS) {
    academic[key] = toNumber(values[key]);
  }
  for (const key of ACADEMIC_TEXT_KEYS) {
    academic[key] = toText(values[key]);
  }
  job.academic_details = academic;

  return job;
}
