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
import { readCollectionDetails, referenceLabel, referenceNotice, safeWebUrl } from "../lib/reference";

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
      sessionStorage.setItem("pcr-inbox-source-id", String(id));
      window.location.href = "/jobs/import?from=inbox";
    },
  });

  if (isLoading) return <EmptyState title="加载中…" />;
  if (isError || !job) {
    return <EmptyState title="加载失败" hint={error?.message ?? "招聘材料不存在"} />;
  }

  const details = readCollectionDetails(job.raw_payload);
  const originalUrl = safeWebUrl(job.source_url);

  return (
    <div className="max-w-3xl space-y-4">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <h1 className="text-xl font-semibold tracking-tight">{job.title_raw ?? "(无标题)"}</h1>
          <p className="mt-0.5 text-sm text-zinc-500 dark:text-zinc-400">
            {job.organization_hint ?? "—"} · {job.source_name} · {job.source_id}
          </p>
        </div>
        <div className="flex flex-wrap gap-2">
          <Badge tone={job.reference_status === "historical" ? "amber" : "blue"}>{referenceLabel(job.reference_status, job.announcement_year)}</Badge>
          <Badge>{STATUS_LABELS[job.status] ?? job.status}</Badge>
        </div>
      </div>

      <div className="rounded-md border border-amber-300 bg-amber-50 px-4 py-3 text-sm leading-relaxed text-amber-800 dark:border-amber-700 dark:bg-amber-900/30 dark:text-amber-200">
        {referenceNotice(job.reference_status)}
      </div>

      {job.status === "possible_duplicate" && job.duplicate_reason && (
        <div className="rounded-md border border-amber-300 bg-amber-50 px-4 py-3 text-sm text-amber-800 dark:border-amber-700 dark:bg-amber-900/30 dark:text-amber-200">
          {job.duplicate_reason}
        </div>
      )}

      <Card>
        <CardHeader><CardTitle>招聘条件与待遇参考</CardTitle></CardHeader>
        <CardContent className="space-y-4">
          <p className="text-xs text-zinc-500">以下为公告原文段落摘录，可能涉及不同岗位或人才层次；请结合完整正文及附件核对适用条件。</p>
          <div>
            <h2 className="mb-1 text-sm font-medium">岗位要求</h2>
            <p className="whitespace-pre-wrap text-sm leading-relaxed">{job.requirements_summary || "正文中未提取到明确要求，待核对原文及附件。"}</p>
          </div>
          <div>
            <h2 className="mb-1 text-sm font-medium">待遇与支持</h2>
            <p className="whitespace-pre-wrap text-sm leading-relaxed">{job.benefits_summary || "正文中未提取到明确待遇，待核对原文及附件。"}</p>
          </div>
        </CardContent>
      </Card>

      {(details.detailStatus === "failed" || details.detailStatus === "missing" || details.warnings.length > 0) && (
        <div className="rounded-md border border-amber-300 px-4 py-3 text-sm text-amber-800 dark:border-amber-700 dark:text-amber-200">
          {details.detailStatus === "failed" && <p>详情正文抓取失败：{details.detailError || "请打开原网页核对，或稍后重新采集。"}</p>}
          {details.detailStatus === "missing" && <p>未找到可识别的正文，页面可能由图片或附件承载，请核对原网页。</p>}
          {details.warnings.map((warning, index) => <p key={index}>{warning}</p>)}
        </div>
      )}

      {(details.attachments.length > 0 || details.images.length > 0) && <Card>
        <CardHeader><CardTitle>原文附件与图片</CardTitle></CardHeader>
        <CardContent className="space-y-3">
          <p className="text-xs leading-relaxed text-zinc-500">这里保留原始链接，尚未自动读取附件或识别图片文字。专业要求、岗位表或待遇表可能仅出现在这些材料中。</p>
          {details.attachments.length > 0 && <div className="space-y-2">
            <h2 className="text-sm font-medium">附件（{details.attachments.length}）</h2>
            {details.attachments.map((link) => <a key={link.url} href={link.url} target="_blank" rel="noopener noreferrer" className="block break-all text-sm underline">{link.title}</a>)}
          </div>}
          {details.images.length > 0 && <details>
            <summary className="cursor-pointer text-sm font-medium">图片（{details.images.length}）· 待人工核对</summary>
            <div className="mt-2 space-y-2">{details.images.map((link, index) => <a key={link.url} href={link.url} target="_blank" rel="noopener noreferrer" className="block break-all text-sm underline">{index + 1}. {link.title}</a>)}</div>
          </details>}
        </CardContent>
      </Card>}

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
          <InfoRow label="公告年份" value={job.announcement_year == null ? "待确认" : String(job.announcement_year)} />
          <InfoRow label="地区" value={job.location_hint || job.province || "待确认"} />
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
        {originalUrl && <a href={originalUrl} target="_blank" rel="noopener noreferrer">
          <Button variant="outline">打开原网页</Button>
        </a>}
        <Button onClick={() => extractMutation.mutate()} disabled={extractMutation.isPending}>
          {extractMutation.isPending ? "解析中…" : "AI 解析"}
        </Button>
        {job.status !== "ignored" && (
          <Button variant="ghost" disabled={statusMutation.isPending} onClick={() => statusMutation.mutate("ignored")}>忽略</Button>
        )}
        <Link to="/discovered" className="ml-auto">
          <Button variant="ghost">← 返回 Inbox</Button>
        </Link>
      </div>
      {extractMutation.isError && (
        <p className="text-sm text-red-600 dark:text-red-400">{extractMutation.error.message}</p>
      )}
      {statusMutation.isError && <p className="text-sm text-red-600">{statusMutation.error.message}</p>}
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
