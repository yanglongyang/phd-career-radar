import { describe, expect, it } from "vitest";
import type { ExtractionPreview } from "../types";
import { buildSavePayload, seedValuesFromPreview } from "./extraction";

/* Phase 3.1 核心回归：AI 返回完整样例 → 不做任何修改 → buildSavePayload →
   逐字段核对。任何"解析出来但保存丢失/类型串错"的字段都会在这里失败。 */

const FULL_EXTRACTION = {
  title: "预聘副教授（化学生物学）",
  organization: "某某大学",
  department: "化学学院",
  job_category: "university_faculty",
  country: "中国",
  province: "江苏",
  city: "南京",
  employment_type: "全职",
  posted_at: "2026-08-20",
  deadline: "2026-10-31",
  degree_requirement: "博士",
  experience_requirement: null,
  establishment_status: "non_established",
  tenure_status: "tenure_track",
  contract_type: "fixed_term",
  funding_source: "university",
  is_up_or_out: true,
  contract_years: 6,
  startup_funding: "50 万元",
  startup_funding_terms: "分三年到账",
  can_supervise_master: true,
  can_supervise_phd: false,
  master_quota: "2",
  phd_quota: null,
  fixed_income: "年薪 22 万",
  performance_income: null,
  housing_settlement: "安家费 30 万",
  housing_subsidy: null,
  talent_housing: null,
  regional_talent_subsidy: null,
  unknowns: ["首聘周期", "国自然是否为硬性要求"],
};

const PREVIEW: ExtractionPreview = {
  source_type: "url",
  source_url: "https://example.edu.cn/hr/1",
  source_text: "某某大学化学学院公开招聘预聘副教授，聘期六年，年薪 30-45 万。",
  extraction: FULL_EXTRACTION as unknown as ExtractionPreview["extraction"],
  provider: "fake",
  model: "fake-model",
  prompt_version: "job_extraction_v1",
};

describe("seedValuesFromPreview", () => {
  it("把全部可持久化字段放进编辑状态（含此前丢失的六个基本字段）", () => {
    const values = seedValuesFromPreview(PREVIEW);
    for (const key of [
      "title", "organization", "department", "job_category", "country",
      "province", "city", "employment_type", "degree_requirement",
      "experience_requirement", "salary_text", "salary_currency", "salary_period",
      "posted_at", "deadline",
    ]) {
      expect(values, key).toHaveProperty(key);
    }
    expect(values.country).toBe("中国");
    expect(values.deadline).toBe("2026-10-31");
    expect(values.employment_type).toBe("全职");
    expect(values.degree_requirement).toBe("博士");
    expect(values.posted_at).toBe("2026-08-20");
    expect(values.experience_requirement).toBeNull();
  });

  it("学术字段按确定类型落位：number/bool/axis/text", () => {
    const values = seedValuesFromPreview(PREVIEW);
    expect(values.contract_years).toBe(6); // number 保持 number
    expect(values.is_up_or_out).toBe(true);
    expect(values.can_supervise_phd).toBe(false);
    expect(values.tenure_status).toBe("tenure_track");
    expect(values.master_quota).toBe("2"); // 纯数字文本仍是字符串
    expect(values.phd_quota).toBeNull();
  });
});

describe("buildSavePayload", () => {
  const values = seedValuesFromPreview(PREVIEW);
  const payload = buildSavePayload(PREVIEW, values);

  it("不修改任何字段时，全部解析信息原样进入保存 payload", () => {
    expect(payload.title).toBe("预聘副教授（化学生物学）");
    expect(payload.organization_name).toBe("某某大学");
    expect(payload.country).toBe("中国");
    expect(payload.deadline).toBe("2026-10-31");
    expect(payload.posted_at).toBe("2026-08-20");
    expect(payload.employment_type).toBe("全职");
    expect(payload.degree_requirement).toBe("博士");
    expect(payload.experience_requirement).toBeNull();
    expect(payload.description_raw).toBe(PREVIEW.source_text);
  });

  it("contract_years 保持 number，不再被字符串化转换吞掉", () => {
    expect(payload.academic_details?.contract_years).toBe(6);
  });

  it("纯数字文本字段保持字符串", () => {
    expect(payload.academic_details?.master_quota).toBe("2");
  });

  it("四轴默认 unknown、布尔字段允许 null", () => {
    expect(payload.academic_details?.establishment_status).toBe("non_established");
    expect(payload.academic_details?.tenure_status).toBe("tenure_track");
    expect(payload.academic_details?.funding_source).toBe("university");
    expect(payload.academic_details?.can_supervise_master).toBe(true);
    expect(payload.academic_details?.can_supervise_phd).toBe(false);
  });

  it("provenance 来自 Preview 本身：source_url 与审计随 payload 一起提交", () => {
    expect(payload.source_url).toBe("https://example.edu.cn/hr/1");
    expect(payload.import_audit).toEqual({
      ingestion_method: "url",
      source_url: "https://example.edu.cn/hr/1",
      provider: "fake",
      model: "fake-model",
      prompt_version: "job_extraction_v1",
      extraction_json: FULL_EXTRACTION,
    });
  });

  it("文本来源时 source_url 为 null，不会残留上一次 URL", () => {
    const textPreview: ExtractionPreview = {
      ...PREVIEW,
      source_type: "text",
      source_url: null,
    };
    const p = buildSavePayload(textPreview, seedValuesFromPreview(textPreview));
    expect(p.source_url).toBeNull();
    expect(p.import_audit?.ingestion_method).toBe("text");
    expect(p.import_audit?.source_url).toBeNull();
  });

  it("用户修改过的字段覆盖 AI 结果", () => {
    const edited = { ...values, deadline: "2026-11-15", contract_years: 3 };
    const p = buildSavePayload(PREVIEW, edited);
    expect(p.deadline).toBe("2026-11-15");
    expect(p.academic_details?.contract_years).toBe(3);
  });
});
