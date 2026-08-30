import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";
import { api } from "../services/api";
import type { Organization } from "../types";
import { Button, Card, EmptyState, Field, Input, PageHeader, Select } from "../components/ui";

const ORG_TYPES = [
  { value: "university", label: "高校" },
  { value: "research_institute", label: "科研院所" },
  { value: "enterprise", label: "企业" },
  { value: "hospital", label: "医院" },
  { value: "other", label: "其他" },
];

export default function OrganizationsPage() {
  const queryClient = useQueryClient();
  const [keyword, setKeyword] = useState("");
  const [showForm, setShowForm] = useState(false);
  const [form, setForm] = useState({ name: "", organization_type: "university", province: "", city: "", official_url: "", career_url: "" });

  const { data: orgs, isLoading } = useQuery({
    queryKey: ["organizations", keyword],
    queryFn: () => api<Organization[]>(`/organizations?q=${encodeURIComponent(keyword)}`),
  });

  const createMutation = useMutation({
    mutationFn: () => api<Organization>("/organizations", { method: "POST", body: JSON.stringify(form) }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["organizations"] });
      setShowForm(false);
      setForm({ name: "", organization_type: "university", province: "", city: "", official_url: "", career_url: "" });
    },
  });

  return (
    <div>
      <PageHeader
        title="单位库"
        subtitle="岗位会按单位名自动关联到这里；同一单位多岗位便于横向比较。"
        actions={
          <Button onClick={() => setShowForm((s) => !s)}>{showForm ? "收起" : "+ 新增单位"}</Button>
        }
      />

      {showForm && (
        <Card className="mb-4 p-4">
          <div className="grid grid-cols-3 gap-3">
            <Field label="单位名称 *">
              <Input value={form.name} onChange={(e) => setForm((f) => ({ ...f, name: e.target.value }))} />
            </Field>
            <Field label="类型">
              <Select value={form.organization_type} onChange={(e) => setForm((f) => ({ ...f, organization_type: e.target.value }))}>
                {ORG_TYPES.map((t) => <option key={t.value} value={t.value}>{t.label}</option>)}
              </Select>
            </Field>
            <div className="grid grid-cols-2 gap-3">
              <Field label="省份">
                <Input value={form.province} onChange={(e) => setForm((f) => ({ ...f, province: e.target.value }))} />
              </Field>
              <Field label="城市">
                <Input value={form.city} onChange={(e) => setForm((f) => ({ ...f, city: e.target.value }))} />
              </Field>
            </div>
            <Field label="官网">
              <Input value={form.official_url} onChange={(e) => setForm((f) => ({ ...f, official_url: e.target.value }))} />
            </Field>
            <Field label="招聘页">
              <Input value={form.career_url} onChange={(e) => setForm((f) => ({ ...f, career_url: e.target.value }))} />
            </Field>
            <div className="flex items-end">
              <Button onClick={() => createMutation.mutate()} disabled={createMutation.isPending || form.name === ""}>
                保存
              </Button>
            </div>
          </div>
        </Card>
      )}

      <div className="mb-4">
        <Input
          className="max-w-xs"
          placeholder="搜索单位名称…"
          value={keyword}
          onChange={(e) => setKeyword(e.target.value)}
        />
      </div>

      <Card>
        {isLoading ? (
          <EmptyState title="加载中…" />
        ) : orgs && orgs.length > 0 ? (
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b border-zinc-200 text-left text-xs text-zinc-500 dark:border-zinc-800 dark:text-zinc-400">
                <th className="px-4 py-2.5 font-medium">单位</th>
                <th className="px-4 py-2.5 font-medium">类型</th>
                <th className="px-4 py-2.5 font-medium">地点</th>
                <th className="px-4 py-2.5 font-medium">岗位数</th>
                <th className="px-4 py-2.5 font-medium">招聘页</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-zinc-100 dark:divide-zinc-800">
              {orgs.map((org) => (
                <tr key={org.id} className="hover:bg-zinc-50 dark:hover:bg-zinc-800/50">
                  <td className="px-4 py-2.5 font-medium">{org.name}</td>
                  <td className="px-4 py-2.5 text-zinc-500 dark:text-zinc-400">
                    {ORG_TYPES.find((t) => t.value === org.organization_type)?.label ?? org.organization_type ?? "—"}
                  </td>
                  <td className="px-4 py-2.5 text-zinc-500 dark:text-zinc-400">
                    {[org.province, org.city].filter(Boolean).join(" · ") || "—"}
                  </td>
                  <td className="px-4 py-2.5 tabular-nums">{org.job_count}</td>
                  <td className="px-4 py-2.5">
                    {org.career_url ? (
                      <a href={org.career_url} target="_blank" rel="noreferrer" className="underline">链接</a>
                    ) : "—"}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        ) : (
          <EmptyState title="还没有单位" hint="新增岗位时填写单位名称会自动创建；也可以在这里手工添加。" />
        )}
      </Card>
    </div>
  );
}
