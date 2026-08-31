import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Link, useParams } from "react-router-dom";
import { extractDiscoveredJob, getDiscoveredJob, patchDiscoveredJob } from "../services/api";
import {
  Badge,
  Button,
  Card,
  CardContent,
  CardHeader,
  CardTitle,
  EmptyState,
} from "../components/ui";
import { formatDate } from "../lib/utils";

const STATUS_LABELS: Record<string, string> = {
  new: "新发现",
  reviewing: "查看中",
  ignored: "已忽略",
  imported: "已导入",
  possible_duplicate: "疑似重复",
};

export default function DiscoveredDetailPage() {
  const { id } = useParams();
  const queryClient = useQueryClient();

  const { data: job, isLoading, isError, error } = useQuery({
    queryKey: ["discovered", id],
    queryFn: () => getDiscoveredJob(Number(id)),
    enabled: !!id,
  });

  const statusMutation = useMutation({
    mutationFn: (status: string) => patchDiscoveredJob(Number(id), { status }),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["discovered"] }),
  });

  const extractMutation = useMutation({
    mutationFn: () => extractDiscoveredJob(Number(id)),
    onSuccess: (preview) => {
      sessionStorage.setItem("pcr-inbox-preview", JSON.stringify({ preview, sourceId: Number(id) }));
      window.location.href = "/jobs/import?from=inbox";
    },
  });

  if (isLoading) return <EmptyState title="加载中…" />;
  if (isError || !job) {
    return <EmptyState title="加载失败" hint={error?.message ?? "招聘材料不存在"} />;
  }

  return (
    <div className="max-w-3xl space-y-4">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <h1 className="text-xl font-semibold tracking-tight">{job.title_raw ?? "(无标题)"}</h1>
          <p className="mt-0.5 text-sm text-zinc-500 dark:text-zinc-400">
            {job.organization_hint ?? "—"} · {job.source_name} · {job.source_id}
          </p>
        </div>
        <Badge>{STATUS_LABELS[job.status] ?? job.status}</Badge>
      </div>

      {job.status === "possible_duplicate" && job.duplicate_reason && (
        <div className="rounded-md border border-amber-300 bg-amber-50 px-4 py-3 text-sm text-amber-800 dark:border-amber-700 dark:bg-amber-900/30 dark:text-amber-200">
          {job.duplicate_reason}
        </div>
      )}

      <Card>
        <CardHeader><CardTitle>原始招聘材料</CardTitle></CardHeader>
        <CardContent>
          {job.description_raw ? (
            <pre className="whitespace-pre-wrap font-sans text-sm leading-relaxed">{job.description_raw}</pre>
          ) : (
            <p className="text-sm text-zinc-400">该来源未抓取详情正文（列表级信息）。</p>
          )}
        </CardContent>
      </Card>

      <Card>
        <CardHeader><CardTitle>抓取元信息</CardTitle></CardHeader>
        <CardContent className="grid grid-cols-2 gap-3 text-sm">
          <InfoRow label="Source ID" value={job.source_id} />
          <InfoRow label="来源" value={job.source_name} />
          <InfoRow label="Source 岗位 ID" value={job.source_job_id ?? "—"} />
          <InfoRow label="发布时间" value={job.published_at_raw ?? "—"} />
          <InfoRow label="首次发现" value={formatDate(job.discovered_at)} />
          <InfoRow label="最后出现" value={formatDate(job.last_seen_at)} />
          <InfoRow label="首次运行" value={job.first_run_id != null ? `#${job.first_run_id}` : "—"} />
          <InfoRow label="最近运行" value={job.last_run_id != null ? `#${job.last_run_id}` : "—"} />
          <div className="col-span-2">
            <InfoRow label="原始 URL" value={job.source_url} />
          </div>
          {job.imported_job_id && (
            <div className="col-span-2">
              <InfoRow label="已导入岗位" value={`#${job.imported_job_id}`} />
            </div>
          )}
        </CardContent>
      </Card>

      <div className="flex flex-wrap gap-2">
        <a href={job.source_url} target="_blank" rel="noreferrer">
          <Button variant="outline">打开原网页</Button>
        </a>
        <Button onClick={() => extractMutation.mutate()} disabled={extractMutation.isPending}>
          {extractMutation.isPending ? "解析中…" : "AI 解析"}
        </Button>
        {job.status !== "ignored" && (
          <Button variant="ghost" onClick={() => statusMutation.mutate("ignored")}>忽略</Button>
        )}
        <Link to="/discovered" className="ml-auto">
          <Button variant="ghost">← 返回 Inbox</Button>
        </Link>
      </div>
      {extractMutation.isError && (
        <p className="text-sm text-red-600 dark:text-red-400">{extractMutation.error.message}</p>
      )}
    </div>
  );
}

function InfoRow({ label, value }: { label: string; value: string }) {
  return (
    <div className="flex gap-2">
      <span className="w-24 shrink-0 text-zinc-500 dark:text-zinc-400">{label}</span>
      <span className="break-all font-medium">{value}</span>
    </div>
  );
}
