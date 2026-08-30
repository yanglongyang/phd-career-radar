import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";
import { Link } from "react-router-dom";
import {
  deleteApplication,
  listApplications,
  updateApplication,
} from "../services/api";
import type { Application, ApplicationUpdateInput } from "../types";
import {
  APPLICATION_STATUS_LABELS,
  APPLICATION_STATUS_ORDER,
  applicationStatusTone,
  formatDate,
} from "../lib/utils";
import {
  Badge,
  Button,
  Card,
  CardContent,
  EmptyState,
  Field,
  Input,
  PageHeader,
  Select,
  Textarea,
} from "../components/ui";

/* Career CRM（Phase 5）：Kanban 看板（拖拽改状态）+ 列表视图 + 申请编辑。
   只消费 Phase 2-4 的评估结果；非法状态流转由后端 409 拒绝并在此透明展示。 */

const EDITABLE_FIELDS: { key: keyof ApplicationUpdateInput; label: string; type?: string }[] = [
  { key: "priority", label: "优先级（1-10）", type: "number" },
  { key: "next_action", label: "下一步行动" },
  { key: "next_action_date", label: "行动日期", type: "date" },
  { key: "contact", label: "联系人" },
  { key: "resume_version", label: "简历版本" },
  { key: "cover_letter_version", label: "Cover Letter 版本" },
];

export default function ApplicationsPage() {
  const queryClient = useQueryClient();
  const [view, setView] = useState<"kanban" | "list">("kanban");
  const [editing, setEditing] = useState<Application | null>(null);
  const [errorMsg, setErrorMsg] = useState<string | null>(null);

  const { data, isLoading } = useQuery({
    queryKey: ["applications"],
    queryFn: () => listApplications({ sort: "updated_at" }),
  });
  const items = data?.items ?? [];

  const invalidate = () => {
    queryClient.invalidateQueries({ queryKey: ["applications"] });
    queryClient.invalidateQueries({ queryKey: ["dashboard"] });
  };

  const moveMutation = useMutation({
    mutationFn: ({ id, status }: { id: number; status: string }) =>
      updateApplication(id, { status }),
    onSuccess: invalidate,
    onError: (err) => {
      setErrorMsg(err.message);
      invalidate(); // 失败回滚显示
    },
  });

  const removeMutation = useMutation({
    mutationFn: (id: number) => deleteApplication(id),
    onSuccess: () => {
      setEditing(null);
      invalidate();
    },
    onError: (err) => setErrorMsg(err.message),
  });

  const byStatus = new Map<string, Application[]>();
  for (const status of APPLICATION_STATUS_ORDER) byStatus.set(status, []);
  for (const app of items) {
    byStatus.get(app.status)?.push(app);
  }

  return (
    <div>
      <PageHeader
        title="申请 CRM"
        subtitle="管理真正准备申请和正在推进的岗位；非法状态流转会被后端拒绝并在此提示。"
        actions={
          <div className="flex gap-2">
            <Button variant={view === "kanban" ? "default" : "outline"} size="sm" onClick={() => setView("kanban")}>
              看板
            </Button>
            <Button variant={view === "list" ? "default" : "outline"} size="sm" onClick={() => setView("list")}>
              列表
            </Button>
          </div>
        }
      />

      {errorMsg && (
        <div className="mb-4 rounded-md border border-red-300 bg-red-50 px-4 py-3 text-sm text-red-700 dark:border-red-700 dark:bg-red-900/30 dark:text-red-300">
          {errorMsg}
          <button className="ml-3 underline" onClick={() => setErrorMsg(null)}>知道了</button>
        </div>
      )}

      {isLoading ? (
        <EmptyState title="加载中…" />
      ) : items.length === 0 ? (
        <Card>
          <EmptyState
            title="还没有申请记录"
            hint="在岗位详情的 Application 页签点击「创建申请」，岗位即进入 CRM 流程。"
          />
        </Card>
      ) : view === "kanban" ? (
        <div className="flex gap-3 overflow-x-auto pb-4">
          {APPLICATION_STATUS_ORDER.map((status) => {
            const cards = byStatus.get(status) ?? [];
            return (
              <div
                key={status}
                className="w-56 shrink-0 rounded-lg bg-zinc-100/70 p-2 dark:bg-zinc-900"
                onDragOver={(e) => e.preventDefault()}
                onDrop={(e) => {
                  const id = Number(e.dataTransfer.getData("text/plain"));
                  const app = items.find((a) => a.id === id);
                  if (app && app.status !== status) {
                    moveMutation.mutate({ id, status });
                  }
                }}
              >
                <div className="mb-2 flex items-center justify-between px-1">
                  <span className="text-xs font-semibold text-zinc-600 dark:text-zinc-300">
                    {APPLICATION_STATUS_LABELS[status]}
                  </span>
                  <span className="text-xs tabular-nums text-zinc-400">{cards.length}</span>
                </div>
                <div className="space-y-2">
                  {cards.map((app) => (
                    <Card
                      key={app.id}
                      draggable
                      onDragStart={(e) => e.dataTransfer.setData("text/plain", String(app.id))}
                      className="cursor-grab active:cursor-grabbing"
                    >
                      <CardContent className="space-y-1.5 p-2.5">
                        <Link
                          to={`/jobs/${app.job_id}`}
                          className="line-clamp-2 text-xs font-medium hover:underline"
                        >
                          {app.job?.title ?? `岗位 #${app.job_id}`}
                        </Link>
                        <p className="truncate text-xs text-zinc-400">
                          {app.job?.organization_name ?? "—"}
                          {app.job?.total_score != null && ` · ${app.job.total_score} 分`}
                        </p>
                        {app.next_action && (
                          <p
                            className={`line-clamp-2 text-xs ${
                              app.next_action_date && app.next_action_date < new Date().toISOString().slice(0, 10)
                                ? "font-medium text-red-600 dark:text-red-400"
                                : "text-amber-700 dark:text-amber-400"
                            }`}
                          >
                            ▶ {app.next_action}
                            {app.next_action_date && `（${formatDate(app.next_action_date)}）`}
                          </p>
                        )}
                        <button
                          className="text-xs text-zinc-500 underline dark:text-zinc-400"
                          onClick={() => setEditing(app)}
                        >
                          编辑
                        </button>
                      </CardContent>
                    </Card>
                  ))}
                </div>
              </div>
            );
          })}
        </div>
      ) : (
        <Card>
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b border-zinc-200 text-left text-xs text-zinc-500 dark:border-zinc-800 dark:text-zinc-400">
                <th className="px-4 py-2.5 font-medium">岗位</th>
                <th className="px-4 py-2.5 font-medium">状态</th>
                <th className="px-4 py-2.5 font-medium">评分</th>
                <th className="px-4 py-2.5 font-medium">下一步</th>
                <th className="px-4 py-2.5 font-medium">投递时间</th>
                <th className="px-4 py-2.5 font-medium">编辑</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-zinc-100 dark:divide-zinc-800">
              {items.map((app) => (
                <tr key={app.id} className="hover:bg-zinc-50 dark:hover:bg-zinc-800/50">
                  <td className="px-4 py-2.5">
                    <Link to={`/jobs/${app.job_id}`} className="font-medium hover:underline">
                      {app.job?.title ?? `#${app.job_id}`}
                    </Link>
                    <span className="text-zinc-400"> · {app.job?.organization_name ?? "—"}</span>
                  </td>
                  <td className="px-4 py-2.5">
                    <Badge tone={applicationStatusTone(app.status)}>
                      {APPLICATION_STATUS_LABELS[app.status] ?? app.status}
                    </Badge>
                  </td>
                  <td className="px-4 py-2.5 tabular-nums">{app.job?.total_score ?? "—"}</td>
                  <td className="px-4 py-2.5 text-zinc-500 dark:text-zinc-400">
                    {app.next_action ? `${app.next_action}（${formatDate(app.next_action_date)}）` : "—"}
                  </td>
                  <td className="px-4 py-2.5 text-zinc-500 dark:text-zinc-400">{formatDate(app.applied_at)}</td>
                  <td className="px-4 py-2.5">
                    <Button size="sm" variant="outline" onClick={() => setEditing(app)}>
                      编辑
                    </Button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </Card>
      )}

      {editing && (
        <EditPanel
          app={editing}
          onClose={() => setEditing(null)}
          onDelete={() => {
            if (window.confirm("确定删除这条申请记录？岗位与评估结果会保留。")) {
              removeMutation.mutate(editing.id);
            }
          }}
        />
      )}
    </div>
  );
}

function EditPanel({
  app,
  onClose,
  onDelete,
}: {
  app: Application;
  onClose: () => void;
  onDelete: () => void;
}) {
  const queryClient = useQueryClient();
  const [form, setForm] = useState<Record<string, string>>({
    status: app.status,
    priority: app.priority?.toString() ?? "",
    next_action: app.next_action ?? "",
    next_action_date: app.next_action_date ?? "",
    contact: app.contact ?? "",
    resume_version: app.resume_version ?? "",
    cover_letter_version: app.cover_letter_version ?? "",
    notes: app.notes ?? "",
  });
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const bind = (key: string) => ({
    value: form[key] ?? "",
    onChange: (e: React.ChangeEvent<HTMLInputElement | HTMLTextAreaElement | HTMLSelectElement>) =>
      setForm((f) => ({ ...f, [key]: e.target.value })),
  });

  const save = async () => {
    setSaving(true);
    setError(null);
    const payload: ApplicationUpdateInput = {
      status: form.status,
      priority: form.priority === "" ? null : Number(form.priority),
      next_action: form.next_action === "" ? null : form.next_action,
      next_action_date: form.next_action_date === "" ? null : form.next_action_date,
      contact: form.contact === "" ? null : form.contact,
      resume_version: form.resume_version === "" ? null : form.resume_version,
      cover_letter_version: form.cover_letter_version === "" ? null : form.cover_letter_version,
      notes: form.notes === "" ? null : form.notes,
    };
    try {
      await updateApplication(app.id, payload);
      queryClient.invalidateQueries({ queryKey: ["applications"] });
      queryClient.invalidateQueries({ queryKey: ["dashboard"] });
      queryClient.invalidateQueries({ queryKey: ["job", String(app.job_id)] });
      onClose();
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err));
      queryClient.invalidateQueries({ queryKey: ["applications"] });  // 失败回滚显示
    } finally {
      setSaving(false);
    }
  };

  return (
    <div className="fixed inset-0 z-50 flex justify-end bg-black/30" onClick={onClose}>
      <Card
        className="h-full w-[26rem] overflow-y-auto rounded-none"
        onClick={(e) => e.stopPropagation()}
      >
        <CardContent className="space-y-4 py-4">
          <div className="flex items-start justify-between">
            <div>
              <h3 className="text-sm font-semibold">{app.job?.title ?? `岗位 #${app.job_id}`}</h3>
              <p className="text-xs text-zinc-400">{app.job?.organization_name ?? "—"}</p>
            </div>
            <Button size="sm" variant="ghost" onClick={onClose}>✕</Button>
          </div>

          {error && (
            <div className="rounded-md border border-red-300 bg-red-50 px-3 py-2 text-xs text-red-700 dark:border-red-700 dark:bg-red-900/30 dark:text-red-300">
              {error}
            </div>
          )}

          <Field label="状态">
            <Select {...bind("status")}>
              {/* 当前状态 + 后端声明的合法目标状态 */}
              {[app.status, ...app.allowed_next_statuses].map((s) => (
                <option key={s} value={s}>{APPLICATION_STATUS_LABELS[s] ?? s}</option>
              ))}
            </Select>
          </Field>
          {EDITABLE_FIELDS.map((f) => (
            <Field key={String(f.key)} label={f.label}>
              <Input type={f.type ?? "text"} {...bind(String(f.key))} />
            </Field>
          ))}
          <Field label="备注">
            <Textarea rows={4} {...bind("notes")} />
          </Field>

          <div className="flex justify-between pt-2">
            <Button variant="danger" size="sm" onClick={onDelete}>删除申请</Button>
            <Button onClick={save} disabled={saving}>
              {saving ? "保存中…" : "保存"}
            </Button>
          </div>
        </CardContent>
      </Card>
    </div>
  );
}
