import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";
import { Link } from "react-router-dom";
import {
  extractDiscoveredJob,
  listCollectorRuns,
  listDiscoveredJobs,
  patchDiscoveredJob,
  runCollectors,
} from "../services/api";
import type { CollectorRun, CollectorRunItem, DiscoveredJob } from "../types";
import {
  Badge,
  Button,
  Card,
  CardContent,
  CardHeader,
  CardTitle,
  EmptyState,
  PageHeader,
  Select,
} from "../components/ui";
import { formatDate } from "../lib/utils";

/* 招聘发现（V0.2 Inbox）：立即检查招聘更新 + source 级运行结果 + 待审核材料。
   Collector 只负责发现；AI 解析后走现有 Preview → 确认 → 正式 Job 流程。 */

const STATUS_LABELS: Record<string, string> = {
  new: "新发现",
  reviewing: "查看中",
  ignored: "已忽略",
  imported: "已导入",
  possible_duplicate: "疑似重复",
};

function statusTone(status: string) {
  switch (status) {
    case "new":
      return "blue" as const;
    case "reviewing":
      return "amber" as const;
    case "possible_duplicate":
      return "red" as const;
    case "imported":
      return "green" as const;
    case "ignored":
      return "zinc" as const;
    default:
      return "neutral" as const;
  }
}

function runStatusTone(status: string) {
  switch (status) {
    case "success":
    case "completed":
      return "green" as const;
    case "failed":
    case "partial_failure":
      return "red" as const;
    default:
      return "amber" as const;
  }
}

export default function DiscoverPage() {
  const queryClient = useQueryClient();
  const [statusFilter, setStatusFilter] = useState("");
  const [errorMsg, setErrorMsg] = useState<string | null>(null);

  const runsQuery = useQuery({
    queryKey: ["collector-runs"],
    queryFn: () => listCollectorRuns(3),
  });
  const inboxQuery = useQuery({
    queryKey: ["discovered", statusFilter],
    queryFn: () => listDiscoveredJobs({ status: statusFilter || undefined, page_size: 50 }),
  });

  const runMutation = useMutation({
    mutationFn: runCollectors,
    onSuccess: () => {
      setErrorMsg(null);
      queryClient.invalidateQueries({ queryKey: ["collector-runs"] });
      queryClient.invalidateQueries({ queryKey: ["discovered"] });
    },
    onError: (err) => setErrorMsg(err.message),
  });

  const statusMutation = useMutation({
    mutationFn: ({ id, status }: { id: number; status: string }) =>
      patchDiscoveredJob(id, { status }),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["discovered"] }),
    onError: (err) => setErrorMsg(err.message),
  });

  const extractMutation = useMutation({
    mutationFn: extractDiscoveredJob,
    onSuccess: (preview, id) => {
      // 进入现有 Preview：携带解析结果与 source id（保存后回写 imported）
      sessionStorage.setItem("pcr-inbox-preview", JSON.stringify({ preview, sourceId: id }));
      sessionStorage.setItem("pcr-inbox-source-id", String(id));
      window.location.href = "/jobs/import?from=inbox";
    },
    onError: (err) => setErrorMsg(err.message),
  });

  const lastRun: CollectorRun | undefined = runsQuery.data?.[0];
  const items = inboxQuery.data?.items ?? [];

  return (
    <div className="space-y-4">
      <PageHeader
        title="招聘发现"
        subtitle="Collector 只负责发现公开招聘材料；AI 解析、去重确认与正式入库都由你掌控。"
        actions={
          <Button onClick={() => runMutation.mutate()} disabled={runMutation.isPending}>
            {runMutation.isPending ? "正在检查招聘更新…" : "立即检查招聘更新"}
          </Button>
        }
      />

      {errorMsg && (
        <div className="rounded-md border border-red-300 bg-red-50 px-4 py-3 text-sm text-red-700 dark:border-red-700 dark:bg-red-900/30 dark:text-red-300">
          {errorMsg}
          <button className="ml-3 underline" onClick={() => setErrorMsg(null)}>知道了</button>
        </div>
      )}

      {lastRun && (
        <Card>
          <CardHeader className="flex flex-wrap items-center gap-2">
            <CardTitle>上次运行（{formatDate(lastRun.started_at)}）</CardTitle>
            <Badge tone={runStatusTone(lastRun.status)}>{lastRun.status}</Badge>
            <span className="text-xs text-zinc-400">#{lastRun.id}</span>
          </CardHeader>
          <CardContent className="space-y-2">
            <div className="flex flex-wrap gap-x-6 gap-y-1 text-sm">
              <span>新增 <b className="text-emerald-600">{lastRun.new_count}</b></span>
              <span>重复 <b className="tabular-nums">{lastRun.duplicate_count}</b></span>
              <span>疑似重复 <b className="text-amber-600">{lastRun.possible_duplicate_count}</b></span>
              <span>已过滤 <b className="tabular-nums">{lastRun.filtered_count}</b></span>
              {lastRun.recency_skipped_count > 0 && (
                <span>过期跳过 <b className="text-zinc-500">{lastRun.recency_skipped_count}</b></span>
              )}
              <span>失败 <b className="text-red-600">{lastRun.failed_source_count}</b></span>
              <span>进度 {lastRun.completed_source_count} / {lastRun.source_count}</span>
            </div>
            {lastRun.items.length > 0 && (
              <div className="space-y-1">
                {lastRun.items.map((it: CollectorRunItem) => (
                  <div key={it.id} className="flex items-center gap-2 text-xs">
                    <Badge tone={runStatusTone(it.status)}>{it.status}</Badge>
                    <span className="font-medium">{it.source_name}</span>
                    {it.status === "success" ? (
                      <span className="text-zinc-400">
                        {it.new_count} 新增 / {it.duplicate_count} 已存在
                        {it.filtered_count ? ` / 过滤 ${it.filtered_count}` : ""}
                        {it.recency_skipped_count ? ` / 过期跳过 ${it.recency_skipped_count}` : ""}
                      </span>
                    ) : it.status === "failed" ? (
                      <span className="text-red-500">{it.error_message ?? "失败"}</span>
                    ) : (
                      <span className="text-amber-500">进行中…</span>
                    )}
                  </div>
                ))}
              </div>
            )}
          </CardContent>
        </Card>
      )}

      <Card>
        <CardHeader className="flex items-center justify-between">
          <CardTitle>Inbox（{inboxQuery.data?.total ?? 0}）</CardTitle>
          <Select
            className="w-36"
            value={statusFilter}
            onChange={(e) => setStatusFilter(e.target.value)}
          >
            <option value="">全部状态</option>
            {Object.entries(STATUS_LABELS).map(([value, label]) => (
              <option key={value} value={value}>{label}</option>
            ))}
          </Select>
        </CardHeader>
        <CardContent className="py-4">
          {inboxQuery.isError ? (
            <p className="text-sm text-red-600 dark:text-red-400">Inbox 加载失败：{inboxQuery.error.message}</p>
          ) : inboxQuery.isLoading ? (
            <p className="text-sm text-zinc-500">加载中…</p>
          ) : items.length === 0 ? (
            <EmptyState
              title="Inbox 为空"
              hint="点击右上角「立即检查招聘更新」从已配置来源发现招聘材料。"
            />
          ) : (
            <div className="space-y-2">
              {items.map((job: DiscoveredJob) => (
                <div key={job.id} className="rounded-md border border-zinc-200 px-3 py-2.5 text-sm dark:border-zinc-700">
                  <div className="flex flex-wrap items-center gap-2">
                    <Badge tone={statusTone(job.status)}>{STATUS_LABELS[job.status] ?? job.status}</Badge>
                    {job.status === "possible_duplicate" && (
                      <Badge tone="red">疑似重复</Badge>
                    )}
                    <Link to={`/discovered/${job.id}`} className="font-medium hover:underline">
                      {job.title_raw ?? "(无标题)"}
                    </Link>
                    <span className="text-xs text-zinc-400">
                      {job.organization_hint ?? "—"} · {job.source_name}
                      {job.published_at_raw ? ` · ${job.published_at_raw}` : ""}
                    </span>
                  </div>
                  {job.status === "possible_duplicate" && job.duplicate_reason && (
                    <p className="mt-1 text-xs text-amber-600 dark:text-amber-400">{job.duplicate_reason}</p>
                  )}
                  <div className="mt-1.5 flex flex-wrap items-center gap-2">
                    <a href={job.source_url} target="_blank" rel="noreferrer" className="text-xs underline">
                      查看原文
                    </a>
                    <Link to={`/discovered/${job.id}`} className="text-xs underline">查看详情</Link>
                    <Button size="sm" variant="outline" onClick={() => extractMutation.mutate(job.id)}>
                      AI 解析
                    </Button>
                    {job.status !== "ignored" && (
                      <Button size="sm" variant="ghost" onClick={() => statusMutation.mutate({ id: job.id, status: "ignored" })}>
                        忽略
                      </Button>
                    )}
                    {job.status === "ignored" && (
                      <Button size="sm" variant="ghost" onClick={() => statusMutation.mutate({ id: job.id, status: "new" })}>
                        恢复
                      </Button>
                    )}
                    <span className="ml-auto text-xs text-zinc-400">
                      发现 {formatDate(job.discovered_at)} · 最后出现 {formatDate(job.last_seen_at)}
                    </span>
                  </div>
                </div>
              ))}
            </div>
          )}
        </CardContent>
      </Card>
    </div>
  );
}

