import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";
import { api, createJobEvidence, deleteEvidence, listEvidence } from "../services/api";
import type { Evidence, EvidenceCreateInput } from "../types";
import {
  Badge,
  Button,
  Card,
  CardContent,
  CardHeader,
  CardTitle,
  Field,
  Input,
  Select,
  Textarea,
} from "./ui";
import { formatDate } from "../lib/utils";

/* Evidence 页签（Phase 6）：事实资产的可追溯列表 + 创建表单。
   等级语义：A 正式公告/官方文件；B 多个独立第一手陈述；C 单个帖子；D 无法确认来源的转述。 */

const LEVEL_TONES: Record<string, "green" | "blue" | "amber" | "red"> = {
  A: "green",
  B: "blue",
  C: "amber",
  D: "red",
};

const STANCE_TONES: Record<string, "green" | "red" | "amber" | "zinc"> = {
  positive: "green",
  negative: "red",
  mixed: "amber",
  neutral: "zinc",
  unknown: "zinc",
};

export default function EvidenceTab({ jobId }: { jobId: number }) {
  const queryClient = useQueryClient();
  const [showForm, setShowForm] = useState(false);
  const [form, setForm] = useState({
    claim: "",
    category: "other",
    evidence_level: "C",
    stance: "unknown",
    scope_level: "job",
    scope_name: "",
    source_type: "",
    source_author: "",
    source_url: "",
    independence_key: "",
    published_at: "",
    raw_excerpt: "",
  });

  const { data: jobRows, isLoading, isError, error } = useQuery({
    queryKey: ["evidence", "job", jobId],
    queryFn: () => listEvidence({ job_id: jobId }),
  });
  const { data: orgRows, isLoading: orgLoading, isError: orgError } = useQuery({
    queryKey: ["evidence", "org", jobId],
    queryFn: async () => {
      const job = await api<import("../types").JobDetail>(`/jobs/${jobId}`);
      if (!job.organization) return [];
      return listEvidence({ organization_id: job.organization.id });
    },
  });
  const orgLevelRows = (orgRows ?? []).filter((e) => e.job_id === null);
  const jobRowsList = jobRows ?? [];

  const createMutation = useMutation({
    mutationFn: (payload: EvidenceCreateInput) => createJobEvidence(jobId, payload),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["evidence", "job", jobId] });
      setShowForm(false);
      setForm((f) => ({ ...f, claim: "", raw_excerpt: "" }));
    },
  });

  const removeMutation = useMutation({
    mutationFn: (id: number) => deleteEvidence(id),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["evidence", "job", jobId] }),
  });

  const bind = (key: keyof typeof form) => ({
    value: form[key],
    onChange: (
      e: React.ChangeEvent<HTMLInputElement | HTMLTextAreaElement | HTMLSelectElement>,
    ) => setForm((f) => ({ ...f, [key]: e.target.value })),
  });

  return (
    <div className="space-y-4">
      <Card>
        <CardHeader className="flex items-center justify-between">
          <CardTitle>证据（事实资产，逐条可追溯）</CardTitle>
          <Button size="sm" onClick={() => setShowForm((s) => !s)}>
            {showForm ? "收起表单" : "+ 添加证据"}
          </Button>
        </CardHeader>
        <CardContent className="py-4">
          {showForm && (
            <div className="mb-4 grid grid-cols-2 gap-3 rounded-md border border-zinc-200 p-3 dark:border-zinc-700">
              <div className="col-span-2">
                <Field label="这条证据声称什么 *">
                  <Textarea rows={2} {...bind("claim")} placeholder="例：聘期考核要求主持国家自然科学基金" />
                </Field>
              </div>
              <Field label="证据等级" hint="A 官方文件 / B 多个独立第一手 / C 单帖 / D 转述">
                <Select {...bind("evidence_level")}>
                  <option value="A">A · 正式公告/文件</option>
                  <option value="B">B · 多个独立陈述</option>
                  <option value="C">C · 单个帖子</option>
                  <option value="D">D · 无法确认来源</option>
                </Select>
              </Field>
              <Field label="类别">
                <Select {...bind("category")}>
                  {[
                    "fact", "assessment_pressure", "salary_fulfillment",
                    "startup_funding_fulfillment", "administrative_burden", "teaching_load",
                    "young_faculty_turnover", "promotion_environment", "department_management",
                    "research_collaboration", "student_resources", "other",
                  ].map((c) => (
                    <option key={c} value={c}>{c}</option>
                  ))}
                </Select>
              </Field>
              <Field label="立场">
                <Select {...bind("stance")}>
                  {["positive", "negative", "mixed", "neutral", "unknown"].map((v) => (
                    <option key={v} value={v}>{v}</option>
                  ))}
                </Select>
              </Field>
              <Field label="作用域层级" hint="学校风评 ≠ 学院风评 ≠ 课题组风评">
                <Select {...bind("scope_level")}>
                  <option value="organization">学校</option>
                  <option value="department">院系</option>
                  <option value="lab">课题组</option>
                  <option value="job">岗位</option>
                  <option value="unknown">未知</option>
                </Select>
              </Field>
              <Field label="作用域名称（院系/课题组时填写）">
                <Input {...bind("scope_name")} placeholder="例：化学学院" />
              </Field>
              <Field label="来源类型">
                <Input {...bind("source_type")} placeholder="official / zhihu / xiaohongshu / maimai…" />
              </Field>
              <Field label="来源作者（公开标识）">
                <Input {...bind("source_author")} />
              </Field>
              <Field label="独立来源键" hint="同一信息源及其转载共享同一 key">
                <Input {...bind("independence_key")} placeholder="例：zhihu_user_abc_2025" />
              </Field>
              <Field label="发布日期">
                <Input type="date" {...bind("published_at")} />
              </Field>
              <div className="col-span-2">
                <Field label="原文摘录">
                  <Textarea rows={2} {...bind("raw_excerpt")} />
                </Field>
              </div>
              <div className="col-span-2 flex justify-end">
                <Button
                  size="sm"
                  onClick={() => createMutation.mutate(form)}
                  disabled={createMutation.isPending || form.claim.trim() === ""}
                >
                  保存证据
                </Button>
              </div>
            </div>
          )}

          {isError ? (
            <p className="text-sm text-red-600 dark:text-red-400">证据加载失败：{error.message}</p>
          ) : isLoading ? (
            <p className="text-sm text-zinc-500">加载中…</p>
          ) : (
            <div className="space-y-4">
              <EvidenceGroup
                title="岗位级证据"
                rows={jobRowsList}
                onDelete={(id) => {
                  if (window.confirm("删除这条证据？其与历史评估的关联会一并清理。")) {
                    removeMutation.mutate(id);
                  }
                }}
              />
              {orgError ? (
                <p className="text-xs text-red-600 dark:text-red-400">单位级证据加载失败</p>
              ) : (
                <EvidenceGroup
                  title="单位级证据（校级 / 院系风评，长期资产）"
                  rows={orgLevelRows}
                  orgLoading={orgLoading}
                  onDelete={(id) => {
                    if (window.confirm("删除这条证据？其与历史评估的关联会一并清理。")) {
                      removeMutation.mutate(id);
                    }
                  }}
                />
              )}
            </div>
          )}
        </CardContent>
      </Card>
    </div>
  );
}


function EvidenceGroup({
  title,
  rows,
  onDelete,
  orgLoading,
}: {
  title: string;
  rows: Evidence[];
  onDelete: (id: number) => void;
  orgLoading?: boolean;
}) {
  if (orgLoading) return <p className="text-xs text-zinc-500">单位级证据加载中…</p>;
  return (
    <div>
      <p className="mb-2 text-xs font-semibold text-zinc-600 dark:text-zinc-300">
        {title}（{rows.length}）
      </p>
      {rows.length === 0 ? (
        <p className="text-xs text-zinc-400">暂无</p>
      ) : (
        <div className="space-y-2">
          {rows.map((ev) => (
            <div
              key={ev.id}
              className="rounded-md border border-zinc-200 px-3 py-2.5 text-sm dark:border-zinc-700"
            >
              <div className="flex flex-wrap items-center gap-2">
                <Badge tone={LEVEL_TONES[ev.evidence_level] ?? "zinc"}>{ev.evidence_level}</Badge>
                <Badge tone={STANCE_TONES[ev.stance] ?? "zinc"}>{ev.stance}</Badge>
                <span className="text-xs text-zinc-400">
                  {ev.scope_level}
                  {ev.scope_name ? ` · ${ev.scope_name}` : ""} · {ev.category}
                  {ev.is_firsthand === true ? " · 第一手" : ev.is_firsthand === false ? " · 转述" : ""}
                </span>
                <button
                  className="ml-auto text-xs text-zinc-400 underline hover:text-red-600"
                  onClick={() => onDelete(ev.id)}
                >
                  删除
                </button>
              </div>
              <p className="mt-1.5">{ev.claim}</p>
              <p className="mt-1 text-xs text-zinc-400">
                {ev.source_type ?? "来源未知"}
                {ev.source_author ? ` · ${ev.source_author}` : ""} · 采集于 {formatDate(ev.collected_at)}
              </p>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
