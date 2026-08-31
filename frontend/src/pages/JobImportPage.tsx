import { useMutation, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { ApiError, api, extractPreview } from "../services/api";
import { linkDiscoveredJob } from "../services/api";
import type { ExtractionPreview, JobDetail } from "../types";
import { buildSavePayload, seedValuesFromPreview, type FieldValue } from "../lib/extraction";
import { Badge, Button, Card, CardContent, CardHeader, CardTitle, Field, Input, PageHeader, Select, Textarea } from "../components/ui";
import {
  CONTRACT_TYPE_LABELS,
  ESTABLISHMENT_LABELS,
  FUNDING_SOURCE_LABELS,
  JOB_CATEGORY_LABELS,
  TENURE_LABELS,
} from "../lib/utils";

/* AI 解析导入（Phase 3）：粘贴/URL → AI 结构化预览 → 用户逐项确认/修正 → 原子保存 */

const AXIS_OPTIONS: Record<string, Record<string, string>> = {
  establishment_status: ESTABLISHMENT_LABELS,
  tenure_status: TENURE_LABELS,
  contract_type: CONTRACT_TYPE_LABELS,
  funding_source: FUNDING_SOURCE_LABELS,
};

const LONG_FIELDS = new Set([
  "midterm_review", "final_review", "publication_requirements", "grant_requirements",
  "teaching_requirements", "admin_requirements", "promotion_path", "lab_space",
]);

interface GroupDef {
  title: string;
  fields: { key: string; label: string; number?: boolean }[];
}

const ACADEMIC_GROUPS: GroupDef[] = [
  {
    title: "考核与发展",
    fields: [
      { key: "contract_years", label: "合同年限（年）", number: true },
      { key: "first_contract_period", label: "首聘周期" },
      { key: "midterm_review", label: "中期考核" },
      { key: "final_review", label: "聘期考核" },
      { key: "publication_requirements", label: "论文要求" },
      { key: "grant_requirements", label: "基金要求" },
      { key: "teaching_requirements", label: "教学要求" },
      { key: "admin_requirements", label: "行政要求" },
      { key: "current_title", label: "当前职称" },
      { key: "promotion_path", label: "晋升路径" },
    ],
  },
  {
    title: "科研资源",
    fields: [
      { key: "lab_space", label: "实验室空间" },
      { key: "startup_funding", label: "启动经费" },
      { key: "startup_funding_terms", label: "启动经费到账方式" },
    ],
  },
  {
    title: "学生资源",
    fields: [
      { key: "master_quota", label: "硕士指标" },
      { key: "phd_quota", label: "博士指标" },
    ],
  },
  {
    title: "收入与住房（原文）",
    fields: [
      { key: "fixed_income", label: "固定收入" },
      { key: "performance_income", label: "绩效收入" },
      { key: "housing_settlement", label: "安家费" },
      { key: "housing_subsidy", label: "住房补贴" },
      { key: "talent_housing", label: "人才房" },
      { key: "regional_talent_subsidy", label: "地方人才补贴" },
    ],
  },
];

export default function JobImportPage() {
  const inboxPreview = (() => {
    const raw = sessionStorage.getItem("pcr-inbox-preview");
    if (!raw) return null;
    sessionStorage.removeItem("pcr-inbox-preview");
    try {
      return JSON.parse(raw) as { preview: ExtractionPreview; sourceId: number };
    } catch {
      return null;
    }
  })();
  const navigate = useNavigate();
  const queryClient = useQueryClient();
  const [source, setSource] = useState<"text" | "url">("text");
  const [text, setText] = useState("");
  const [pageUrl, setPageUrl] = useState("");
  const [preview, setPreview] = useState<ExtractionPreview | null>(inboxPreview?.preview ?? null);
  const [values, setValues] = useState<Record<string, FieldValue>>(
    inboxPreview ? seedValuesFromPreview(inboxPreview.preview) : {},
  );
  const [errorMsg, setErrorMsg] = useState<string | null>(null);
  const [duplicateOf, setDuplicateOf] = useState<{ id: number; title: string } | null>(null);

  const extractMutation = useMutation({
    mutationFn: extractPreview,
    onSuccess: (data) => {
      setPreview(data);
      setValues(seedValuesFromPreview(data));
      setErrorMsg(null);
    },
    onError: (err) => setErrorMsg(err.message),
  });

  const saveMutation = useMutation({
    mutationFn: (payload: ReturnType<typeof buildSavePayload>) =>
      api<JobDetail>("/jobs", { method: "POST", body: JSON.stringify(payload) }),
    onSuccess: async (job) => {
      queryClient.invalidateQueries({ queryKey: ["jobs"] });
      queryClient.invalidateQueries({ queryKey: ["dashboard"] });
      // P0-2B：来自 Inbox 的解析 → Save 后回写 imported + imported_job_id
      const inbox = sessionStorage.getItem("pcr-inbox-source-id");
      if (inbox) {
        sessionStorage.removeItem("pcr-inbox-source-id");
        const sourceId = Number(inbox);
        try {
          await linkDiscoveredJob(sourceId, job.id);
          queryClient.invalidateQueries({ queryKey: ["discovered"] });
        } catch {
          // 回写失败不阻塞跳转；Inbox 条目保持 reviewing，用户可重试
        }
      }
      navigate(`/jobs/${job.id}`);
    },
    onError: (err) => {
      if (err instanceof ApiError && err.status === 409 && err.body && typeof err.body === "object") {
        const dup = (err.body as { duplicate_of?: { id: number; title: string } }).duplicate_of;
        if (dup) {
          setDuplicateOf(dup);
          return;
        }
      }
      setErrorMsg(err.message);
    },
  });

  const extract = () => {
    setErrorMsg(null);
    setDuplicateOf(null);
    // provenance 由后端 Preview 返回（source_type/source_url），前端不再单独维护 usedUrl
    extractMutation.mutate(source === "text" ? { text } : { url: pageUrl });
  };

  const save = (allowDuplicate: boolean) => {
    if (!preview) return;
    setErrorMsg(null);
    setDuplicateOf(null);
    saveMutation.mutate(buildSavePayload(preview, values, { allowDuplicate }));
  };

  const bind = (key: string) => ({
    value: (values[key] as string) ?? "",
    onChange: (e: React.ChangeEvent<HTMLInputElement | HTMLSelectElement>) =>
      setValues((v) => ({ ...v, [key]: e.target.value })),
  });

  return (
    <div>
      <PageHeader
        title="AI 解析导入"
        subtitle="粘贴招聘公告（或输入链接）→ AI 结构化解析 → 你逐项确认/修正 → 保存入库。AI 只提建议，保存前一切以你确认为准。"
        actions={
          <Button variant="outline" onClick={() => navigate("/jobs/new")}>
            切换到手工新增
          </Button>
        }
      />

      {errorMsg && (
        <div className="mb-4 rounded-md border border-red-300 bg-red-50 px-4 py-3 text-sm text-red-700 dark:border-red-700 dark:bg-red-900/30 dark:text-red-300">
          {errorMsg}
        </div>
      )}
      {duplicateOf && (
        <div className="mb-4 rounded-md border border-amber-300 bg-amber-50 px-4 py-3 text-sm text-amber-800 dark:border-amber-700 dark:bg-amber-900/30 dark:text-amber-200">
          发现疑似重复岗位：
          <a href={`/jobs/${duplicateOf.id}`} className="font-medium underline">
            #{duplicateOf.id} {duplicateOf.title}
          </a>
          。如果确认不是同一岗位，可点击"仍然创建"。
          <div className="mt-2">
            <Button size="sm" variant="outline" onClick={() => save(true)} disabled={saveMutation.isPending}>
              仍然创建
            </Button>
          </div>
        </div>
      )}

      {!preview ? (
        <Card>
          <CardContent className="space-y-4 py-4">
            <div className="flex gap-2">
              <Button variant={source === "text" ? "default" : "outline"} size="sm" onClick={() => setSource("text")}>
                粘贴公告全文
              </Button>
              <Button variant={source === "url" ? "default" : "outline"} size="sm" onClick={() => setSource("url")}>
                从链接抓取
              </Button>
            </div>
            {source === "text" ? (
              <Field label="招聘公告全文 *">
                <Textarea
                  rows={14}
                  value={text}
                  onChange={(e) => setText(e.target.value)}
                  placeholder="粘贴招聘公告全文（正式公告、学院转发、公众号文章均可）"
                />
              </Field>
            ) : (
              <Field label="公告链接 *" hint="只做最简单的公开网页抓取；访问失败或正文提取失败时，请改用粘贴模式">
                <Input
                  value={pageUrl}
                  onChange={(e) => setPageUrl(e.target.value)}
                  placeholder="https://hr.example.edu.cn/..."
                />
              </Field>
            )}
            <div className="flex justify-end">
              <Button
                onClick={extract}
                disabled={extractMutation.isPending || (source === "text" ? text.trim() === "" : pageUrl.trim() === "")}
              >
                {extractMutation.isPending ? "AI 解析中…（可能需要十几秒）" : "AI 解析"}
              </Button>
            </div>
          </CardContent>
        </Card>
      ) : (
        <div className="space-y-4">
          {/* 审计信息与信息缺口 */}
          <Card>
            <CardContent className="flex flex-wrap items-center gap-2 py-3 text-xs text-zinc-500 dark:text-zinc-400">
              <Badge tone="blue">解析预览 · 请逐项确认</Badge>
              <span>Provider：{preview.provider}</span>
              <span>模型：{preview.model ?? "—"}</span>
              <span>Prompt：{preview.prompt_version}</span>
              <span>来源：{preview.source_type === "url" ? "链接抓取" : "粘贴文本"}</span>
              <Button size="sm" variant="ghost" onClick={() => setPreview(null)}>
                ← 重新输入
              </Button>
            </CardContent>
          </Card>
          {preview.extraction.unknowns.length > 0 && (
            <Card>
              <CardHeader><CardTitle>⚠ AI 标记的信息缺口（公告未提及，不得猜测）</CardTitle></CardHeader>
              <CardContent>
                <ul className="list-disc space-y-1 pl-5 text-sm text-amber-700 dark:text-amber-300">
                  {preview.extraction.unknowns.map((u, i) => (
                    <li key={i}>{u}</li>
                  ))}
                </ul>
              </CardContent>
            </Card>
          )}

          {/* 基本信息 */}
          <Card>
            <CardHeader><CardTitle>基本信息</CardTitle></CardHeader>
            <CardContent className="grid grid-cols-2 gap-4 py-4">
              <Field label="岗位名称 *">
                <Input {...bind("title")} />
              </Field>
              <Field label="单位名称">
                <Input {...bind("organization")} />
              </Field>
              <Field label="院系 / 部门">
                <Input {...bind("department")} />
              </Field>
              <Field label="岗位类别">
                <Select {...bind("job_category")}>
                  {Object.entries(JOB_CATEGORY_LABELS).map(([value, label]) => (
                    <option key={value} value={value}>{label}</option>
                  ))}
                </Select>
              </Field>
              <Field label="省份">
                <Input {...bind("province")} />
              </Field>
              <Field label="城市">
                <Input {...bind("city")} />
              </Field>
              <Field label="待遇（原文）">
                <Input {...bind("salary_text")} />
              </Field>
              <Field label="国家 / 地区">
                <Input {...bind("country")} />
              </Field>
              <Field label="用工类型（未知则留空）">
                <Input {...bind("employment_type")} />
              </Field>
              <Field label="发布日期">
                <Input type="date" {...bind("posted_at")} />
              </Field>
              <Field label="截止日期（重要，未知则留空）">
                <Input type="date" {...bind("deadline")} />
              </Field>
              <Field label="学历要求（未知则留空）">
                <Input {...bind("degree_requirement")} />
              </Field>
              <div className="col-span-2">
                <Field label="经验要求（未知则留空）">
                  <Input {...bind("experience_requirement")} />
                </Field>
              </div>
              <div className="grid grid-cols-2 gap-3">
                <Field label="币种">
                  <Select {...bind("salary_currency")}>
                    <option value="">未知</option>
                    <option value="CNY">CNY</option>
                    <option value="USD">USD</option>
                    <option value="EUR">EUR</option>
                    <option value="GBP">GBP</option>
                    <option value="unknown">unknown</option>
                  </Select>
                </Field>
                <Field label="周期">
                  <Select {...bind("salary_period")}>
                    <option value="">未知</option>
                    <option value="year">年</option>
                    <option value="month">月</option>
                    <option value="day">日</option>
                    <option value="hour">时</option>
                    <option value="unknown">unknown</option>
                  </Select>
                </Field>
              </div>
            </CardContent>
          </Card>

          {/* 聘用体系（四轴 + 非升即走） */}
          <Card>
            <CardHeader><CardTitle>聘用体系（四个独立维度）</CardTitle></CardHeader>
            <CardContent className="grid grid-cols-2 gap-4 py-4">
              {Object.entries(AXIS_OPTIONS).map(([key, options]) => (
                <Field key={key} label={AXIS_LABEL_TITLES[key] ?? key}>
                  <Select {...bind(key)}>
                    {Object.entries(options).map(([value, label]) => (
                      <option key={value} value={value}>{label}</option>
                    ))}
                  </Select>
                </Field>
              ))}
              <Field label="非升即走">
                <Select
                  value={values.is_up_or_out === null || values.is_up_or_out === undefined ? "" : String(values.is_up_or_out)}
                  onChange={(e) =>
                    setValues((v) => ({ ...v, is_up_or_out: e.target.value === "" ? null : e.target.value === "true" }))
                  }
                >
                  <option value="">未知 / 待确认</option>
                  <option value="true">是</option>
                  <option value="false">否</option>
                </Select>
              </Field>
            </CardContent>
          </Card>

          {/* 学术详情分组 */}
          {ACADEMIC_GROUPS.map((group) => (
            <Card key={group.title}>
              <CardHeader><CardTitle>{group.title}</CardTitle></CardHeader>
              <CardContent className="grid grid-cols-2 gap-4 py-4">
                {group.fields.map((f) =>
                  f.number ? (
                    <Field key={f.key} label={`${f.label}（未知则留空）`}>
                      <Input type="number" {...bind(f.key)} />
                    </Field>
                  ) : LONG_FIELDS.has(f.key) ? (
                    <div key={f.key} className="col-span-2">
                      <Field label={`${f.label}（未知则留空）`}>
                        <Textarea
                          rows={2}
                          value={(values[f.key] as string) ?? ""}
                          onChange={(e) => setValues((v) => ({ ...v, [f.key]: e.target.value }))}
                        />
                      </Field>
                    </div>
                  ) : (
                    <Field key={f.key} label={`${f.label}（未知则留空）`}>
                      <Input {...bind(f.key)} />
                    </Field>
                  ),
                )}
                {group.title === "学生资源" && (
                  <>
                    <BoolField
                      label="硕士招生资格"
                      value={values.can_supervise_master}
                      onChange={(v) => setValues((prev) => ({ ...prev, can_supervise_master: v }))}
                    />
                    <BoolField
                      label="博士招生资格"
                      value={values.can_supervise_phd}
                      onChange={(v) => setValues((prev) => ({ ...prev, can_supervise_phd: v }))}
                    />
                  </>
                )}
                {group.title === "考核与发展" && (
                  <BoolField
                    label="独立 PI 资格"
                    value={values.independent_pi}
                    onChange={(v) => setValues((prev) => ({ ...prev, independent_pi: v }))}
                  />
                )}
              </CardContent>
            </Card>
          ))}

          <div className="flex justify-end gap-2">
            <Button variant="outline" onClick={() => navigate("/jobs")}>取消</Button>
            <Button onClick={() => save(false)} disabled={saveMutation.isPending || !values.title}>
              {saveMutation.isPending ? "保存中…" : "确认无误，保存岗位"}
            </Button>
          </div>
        </div>
      )}
    </div>
  );
}

const AXIS_LABEL_TITLES: Record<string, string> = {
  establishment_status: "事业编状态",
  tenure_status: "长聘体系",
  contract_type: "合同类型",
  funding_source: "经费来源",
};

function BoolField({
  label,
  value,
  onChange,
}: {
  label: string;
  value: FieldValue;
  onChange: (v: boolean | null) => void;
}) {
  return (
    <Field label={label}>
      <Select
        value={value === null || value === undefined || value === "" ? "" : String(value)}
        onChange={(e) => onChange(e.target.value === "" ? null : e.target.value === "true")}
      >
        <option value="">未知 / 待确认</option>
        <option value="true">是</option>
        <option value="false">否</option>
      </Select>
    </Field>
  );
}
