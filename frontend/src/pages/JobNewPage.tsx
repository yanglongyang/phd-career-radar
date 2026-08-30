import { useMutation, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { ApiError, api } from "../services/api";
import type { JobCreateInput, JobDetail } from "../types";
import { Button, Card, CardContent, Field, Input, PageHeader, Select, Textarea } from "../components/ui";
import { JOB_CATEGORY_LABELS } from "../lib/utils";

type FormState = {
  title: string;
  organization_name: string;
  department: string;
  job_category: string;
  employment_type: string;
  province: string;
  city: string;
  salary_text: string;
  salary_min: string;
  salary_max: string;
  posted_at: string;
  deadline: string;
  degree_requirement: string;
  source_url: string;
  description_raw: string;
};

const EMPTY_FORM: FormState = {
  title: "",
  organization_name: "",
  department: "",
  job_category: "other",
  employment_type: "",
  province: "",
  city: "",
  salary_text: "",
  salary_min: "",
  salary_max: "",
  posted_at: "",
  deadline: "",
  degree_requirement: "",
  source_url: "",
  description_raw: "",
};

function toPayload(form: FormState, allowDuplicate: boolean): JobCreateInput {
  const num = (s: string) => (s === "" ? null : Number(s));
  const str = (s: string) => (s === "" ? null : s);
  return {
    title: form.title,
    organization_name: str(form.organization_name),
    department: str(form.department),
    job_category: form.job_category,
    employment_type: str(form.employment_type),
    province: str(form.province),
    city: str(form.city),
    salary_text: str(form.salary_text),
    salary_min: num(form.salary_min),
    salary_max: num(form.salary_max),
    posted_at: str(form.posted_at),
    deadline: str(form.deadline),
    degree_requirement: str(form.degree_requirement),
    source_url: str(form.source_url),
    description_raw: str(form.description_raw),
    status: "new",
    allow_duplicate: allowDuplicate,
  };
}

export default function JobNewPage() {
  const navigate = useNavigate();
  const queryClient = useQueryClient();
  const [form, setForm] = useState<FormState>({ ...EMPTY_FORM });
  const [duplicateOf, setDuplicateOf] = useState<{ id: number; title: string } | null>(null);
  const [errorMsg, setErrorMsg] = useState<string | null>(null);

  const mutation = useMutation({
    mutationFn: (payload: JobCreateInput) =>
      api<JobDetail>("/jobs", { method: "POST", body: JSON.stringify(payload) }),
    onSuccess: (job) => {
      queryClient.invalidateQueries({ queryKey: ["jobs"] });
      queryClient.invalidateQueries({ queryKey: ["dashboard"] });
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

  const submit = (allowDuplicate: boolean) => {
    setDuplicateOf(null);
    setErrorMsg(null);
    mutation.mutate(toPayload(form, allowDuplicate));
  };

  const bind = (key: keyof FormState) => ({
    value: form[key],
    onChange: (e: React.ChangeEvent<HTMLInputElement | HTMLTextAreaElement | HTMLSelectElement>) =>
      setForm((f) => ({ ...f, [key]: e.target.value })),
  });

  return (
    <div className="max-w-3xl">
      <PageHeader
        title="新增岗位"
        subtitle="手工录入招聘信息；粘贴公告自动解析将在 Phase 3 提供。岗位性质不确定时请保持「未知/待确认」。"
      />

      {duplicateOf && (
        <div className="mb-4 rounded-md border border-amber-300 bg-amber-50 px-4 py-3 text-sm text-amber-800 dark:border-amber-700 dark:bg-amber-900/30 dark:text-amber-200">
          发现疑似重复岗位：
          <a href={`/jobs/${duplicateOf.id}`} className="font-medium underline">
            #{duplicateOf.id} {duplicateOf.title}
          </a>
          。如果确认不是同一岗位，可点击"仍然创建"。
          <div className="mt-2">
            <Button size="sm" variant="outline" onClick={() => submit(true)} disabled={mutation.isPending}>
              仍然创建
            </Button>
          </div>
        </div>
      )}
      {errorMsg && (
        <div className="mb-4 rounded-md border border-red-300 bg-red-50 px-4 py-3 text-sm text-red-700 dark:border-red-700 dark:bg-red-900/30 dark:text-red-300">
          {errorMsg}
        </div>
      )}

      <Card>
        <CardContent className="grid grid-cols-2 gap-4 py-4">
          <Field label="岗位名称 *">
            <Input placeholder="例：青年研究员（化学生物学）" {...bind("title")} />
          </Field>
          <Field label="单位名称">
            <Input placeholder="例：某某大学" {...bind("organization_name")} />
          </Field>
          <Field label="院系 / 部门">
            <Input placeholder="例：化学学院" {...bind("department")} />
          </Field>
          <Field label="岗位类别">
            <Select {...bind("job_category")}>
              {Object.entries(JOB_CATEGORY_LABELS).map(([value, label]) => (
                <option key={value} value={value}>{label}</option>
              ))}
            </Select>
          </Field>
          <Field label="用工类型">
            <Input placeholder="例：全职 / 全日制博士后" {...bind("employment_type")} />
          </Field>
          <Field label="省份">
            <Input {...bind("province")} />
          </Field>
          <Field label="城市">
            <Input {...bind("city")} />
          </Field>
          <Field label="待遇（原文）">
            <Input placeholder="例：年薪 30-40 万（含绩效）" {...bind("salary_text")} />
          </Field>
          <div className="grid grid-cols-2 gap-3">
            <Field label="薪资下限（万/年）">
              <Input type="number" {...bind("salary_min")} />
            </Field>
            <Field label="薪资上限（万/年）">
              <Input type="number" {...bind("salary_max")} />
            </Field>
          </div>
          <Field label="发布日期">
            <Input type="date" {...bind("posted_at")} />
          </Field>
          <Field label="截止日期">
            <Input type="date" {...bind("deadline")} />
          </Field>
          <Field label="学历要求">
            <Input placeholder="例：博士" {...bind("degree_requirement")} />
          </Field>
          <Field label="公告链接">
            <Input placeholder="https://…" {...bind("source_url")} />
          </Field>
          <div className="col-span-2">
            <Field label="招聘公告原文">
              <Textarea rows={10} placeholder="粘贴招聘公告全文（保存后修改会保留历史版本）" {...bind("description_raw")} />
            </Field>
          </div>
          <div className="col-span-2 flex justify-end gap-2">
            <Button variant="outline" onClick={() => navigate("/jobs")}>取消</Button>
            <Button onClick={() => submit(false)} disabled={mutation.isPending || form.title === ""}>
              {mutation.isPending ? "保存中…" : "保存岗位"}
            </Button>
          </div>
        </CardContent>
      </Card>
    </div>
  );
}
