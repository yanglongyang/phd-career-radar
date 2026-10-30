import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import {
  extractDiscoveredJob, getCollectorScheduler, listCollectorRuns, listCollectorSources,
  listDiscoveredJobs, patchDiscoveredJob, startCollectors,
} from "../services/api";
import type { CollectorStartRequest } from "../types";
import {
  Badge, Button, Card, CardContent, CardHeader, CardTitle, EmptyState,
  Input, PageHeader, Select, Tabs,
} from "../components/ui";
import { formatDate } from "../lib/utils";
import { SECTOR_TABS, groupRunItemsBySector, sectorLabel, sectorQueryForTab, sectorTone } from "../lib/sector";
import { readCollectionDetails, referenceLabel, safeWebUrl, sourceStatusLabel } from "../lib/reference";

const PAGE_SIZE = 30;
const STATUS_LABELS: Record<string, string> = {
  new: "新发现", reviewing: "查看中", ignored: "已忽略",
  imported: "已导入", possible_duplicate: "疑似重复",
};
const RUN_LABELS: Record<string, string> = {
  running: "采集中", completed: "已完成", success: "成功", failed: "失败",
  partial_failure: "部分失败", partial: "部分失败", skipped: "已跳过", interrupted: "已中断",
};
const REFERENCE_TABS = [
  { key: "", label: "全部公告" }, { key: "current_year", label: "当年公告" },
  { key: "historical", label: "历年参考" }, { key: "upcoming", label: "未来年度" },
  { key: "unknown", label: "年份待确认" },
];

function statusTone(status: string) {
  switch (status) {
    case "new": return "blue" as const;
    case "reviewing": return "amber" as const;
    case "possible_duplicate": return "red" as const;
    case "imported": return "green" as const;
    default: return "zinc" as const;
  }
}
function runStatusTone(status: string) {
  if (status === "success" || status === "completed") return "green" as const;
  if (["failed", "partial_failure", "partial"].includes(status)) return "red" as const;
  return "amber" as const;
}

export default function DiscoverPage() {
  const queryClient = useQueryClient();
  const [sectorTab, setSectorTab] = useState("");
  const [referenceFilter, setReferenceFilter] = useState("");
  const [provinceFilter, setProvinceFilter] = useState("山西");
  const [sourceFilter, setSourceFilter] = useState("");
  const [statusFilter, setStatusFilter] = useState("");
  const [yearFilter, setYearFilter] = useState("");
  const [page, setPage] = useState(1);
  const [errorMsg, setErrorMsg] = useState<string | null>(null);
  const [runMessage, setRunMessage] = useState<string | null>(null);

  const schedulerQuery = useQuery({
    queryKey: ["collector-scheduler"], queryFn: getCollectorScheduler, refetchInterval: 5000,
  });
  const runsQuery = useQuery({
    queryKey: ["collector-runs"], queryFn: () => listCollectorRuns(3),
    refetchInterval: (query) => query.state.data?.some((run) => run.status === "running") ? 2000 : 10000,
  });
  const sourcesQuery = useQuery({
    queryKey: ["collector-sources"], queryFn: listCollectorSources,
    refetchInterval: schedulerQuery.data?.running ? 5000 : 30000,
  });
  const lastRun = runsQuery.data?.[0];
  const isRunning = schedulerQuery.data?.running || lastRun?.status === "running";
  const validYear = /^\d{4}$/.test(yearFilter) && Number(yearFilter) >= 2000 && Number(yearFilter) <= 2100;
  const inboxQuery = useQuery({
    queryKey: ["discovered", sectorTab, provinceFilter, referenceFilter, sourceFilter, statusFilter, yearFilter, page],
    queryFn: () => listDiscoveredJobs({
      status: statusFilter || undefined, sector: sectorQueryForTab(sectorTab),
      province: provinceFilter || undefined, reference_status: referenceFilter || undefined,
      announcement_year: validYear ? Number(yearFilter) : undefined,
      source_id: sourceFilter || undefined, page, page_size: PAGE_SIZE,
    }),
    refetchInterval: isRunning ? 5000 : 30000,
  });

  // Includes runs started by the scheduler or another page.
  useEffect(() => {
    queryClient.invalidateQueries({ queryKey: ["discovered"] });
    queryClient.invalidateQueries({ queryKey: ["collector-sources"] });
  }, [lastRun?.id, lastRun?.status, lastRun?.finished_at, queryClient]);

  const runMutation = useMutation({
    mutationFn: startCollectors,
    onSuccess: (_result, request) => {
      setErrorMsg(null);
      setRunMessage(`${request.mode === "history" ? "历年公告补抓" : "招聘更新检查"}已在后台启动，结果会自动更新。`);
      queryClient.invalidateQueries({ queryKey: ["collector-runs"] });
      queryClient.invalidateQueries({ queryKey: ["collector-scheduler"] });
    },
    onError: (err) => { setRunMessage(null); setErrorMsg(err.message); },
  });
  const statusMutation = useMutation({
    mutationFn: ({ id, status }: { id: number; status: string }) => patchDiscoveredJob(id, { status }),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["discovered"] }),
    onError: (err) => setErrorMsg(err.message),
  });
  const extractMutation = useMutation({
    mutationFn: extractDiscoveredJob,
    onSuccess: (preview, id) => {
      sessionStorage.setItem("pcr-inbox-preview", JSON.stringify({ preview, sourceId: id }));
      sessionStorage.setItem("pcr-inbox-source-id", String(id));
      window.location.href = "/jobs/import?from=inbox";
    },
    onError: (err) => setErrorMsg(err.message),
  });
  function startRun(mode: CollectorStartRequest["mode"]) {
    runMutation.mutate({ mode, province: provinceFilter || undefined,
      history_years: mode === "history" ? 3 : undefined,
      source_ids: sourceFilter ? [sourceFilter] : undefined });
  }
  function changeFilter(setter: (value: string) => void, value: string) { setter(value); setPage(1); }

  const items = inboxQuery.data?.items ?? [];
  const total = inboxQuery.data?.total ?? 0;
  const pages = Math.max(1, Math.ceil(total / PAGE_SIZE));
  const visibleSources = (sourcesQuery.data?.sources ?? []).filter((source) => !provinceFilter || source.province === provinceFilter);
  const selectedSource = sourcesQuery.data?.sources.find((source) => source.id === sourceFilter);
  const scheduler = schedulerQuery.data;

  return (
    <div className="space-y-4">
      <PageHeader title="招聘发现" subtitle="跟踪招聘更新，保存历年公告中的条件和待遇，按原始来源核对。" />
      <Card><CardContent className="space-y-3">
        <div className="flex flex-wrap items-end justify-between gap-3">
          <div className="flex flex-wrap items-end gap-3">
            <label className="space-y-1 text-xs text-zinc-500"><span className="block">采集及查看范围</span>
              <Select aria-label="地区" className="w-36" value={provinceFilter} onChange={(event) => {
                changeFilter(setProvinceFilter, event.target.value); setSourceFilter("");
              }}><option value="山西">山西</option><option value="">全部地区</option></Select>
            </label>
            <label className="space-y-1 text-xs text-zinc-500"><span className="block">来源</span>
              <Select aria-label="来源" className="max-w-full sm:w-72" value={sourceFilter} onChange={(event) => changeFilter(setSourceFilter, event.target.value)}>
                <option value="">全部来源</option>
                {visibleSources.map((source) => <option key={source.id} value={source.id}>{source.name}{source.enabled ? "" : "（未启用）"}</option>)}
              </Select>
            </label>
          </div>
          <div className="flex flex-wrap gap-2">
            <Button variant="outline" onClick={() => startRun("history")} disabled={!!isRunning || runMutation.isPending || selectedSource?.enabled === false || selectedSource?.history_enabled === false}>补抓近 3 年公告</Button>
            <Button onClick={() => startRun("recent")} disabled={!!isRunning || runMutation.isPending || selectedSource?.enabled === false}>{isRunning || runMutation.isPending ? "正在采集…" : "立即检查招聘更新"}</Button>
          </div>
        </div>
        <p className="text-xs text-zinc-500">采集按钮使用上方地区与来源范围；下方类型、年份和状态仅筛选已发现的公告。</p>
        {schedulerQuery.isError ? <p className="text-xs text-red-600">自动采集状态读取失败：{schedulerQuery.error.message}</p>
          : scheduler ? <div className="rounded-md bg-zinc-50 px-3 py-2 text-xs leading-relaxed dark:bg-zinc-800/60">
            <Badge tone={scheduler.enabled ? "green" : "zinc"}>{scheduler.enabled ? "自动采集已开启" : "自动采集未开启"}</Badge>
            <span className="ml-2">{scheduler.enabled ? `${scheduler.province || "全部地区"}：每 ${scheduler.interval_hours} 小时检查更新，每 ${scheduler.history_interval_hours} 小时补抓近 ${scheduler.history_years} 年。程序运行期间自动执行。` : "可使用上方按钮手动采集。"}</span>
            {scheduler.last_error && <p className="mt-1 text-red-600">最近任务提示：{scheduler.last_error}</p>}
          </div> : <p className="text-xs text-zinc-500">正在读取自动采集状态…</p>}
        {runMessage && <p role="status" className="text-xs text-sky-700 dark:text-sky-300">{runMessage}</p>}
      </CardContent></Card>

      {errorMsg && <div role="alert" className="rounded-md border border-red-300 bg-red-50 px-4 py-3 text-sm text-red-700 dark:border-red-700 dark:bg-red-900/30 dark:text-red-300">
        {errorMsg}<button className="ml-3 underline" onClick={() => setErrorMsg(null)}>知道了</button>
      </div>}

      <details className="rounded-lg border border-zinc-200 bg-white dark:border-zinc-800 dark:bg-zinc-900">
        <summary className="cursor-pointer px-4 py-3 text-sm font-semibold">来源覆盖与采集情况 · {provinceFilter || "全部地区"}（{visibleSources.filter((source) => source.enabled).length} 个已启用 / {visibleSources.length} 个已登记）</summary>
        <div className="space-y-2 border-t border-zinc-200 px-4 py-3 dark:border-zinc-800">
          <p className="text-xs text-zinc-500">登记来源不等于已完整采集。未启用、网络失败、页面结构变化和详情缺失均需单独核对。</p>
          {sourcesQuery.isError && <p className="text-sm text-red-600">来源列表加载失败：{sourcesQuery.error.message}</p>}
          {sourcesQuery.data?.config_errors.map((error, index) => <p key={`${error.source_id}-${index}`} className="text-xs text-red-600">配置错误 · {error.name}：{error.error}</p>)}
          {visibleSources.map((source) => <div key={source.id} className="rounded-md border border-zinc-200 p-2.5 text-xs dark:border-zinc-700">
            <div className="flex flex-wrap items-center gap-2">
              <span className="font-medium">{source.name}</span><Badge tone={sectorTone(source.sector)}>{sectorLabel(source.sector)}</Badge>
              <Badge tone={source.enabled ? runStatusTone(source.last_status || "unknown") : "zinc"}>{sourceStatusLabel(source.last_status, source.enabled)}</Badge>
              {source.history_enabled && <span className="text-zinc-500">支持历史补抓</span>}
              {safeWebUrl(source.url) && <a href={safeWebUrl(source.url)!} target="_blank" rel="noopener noreferrer" className="underline">来源网页</a>}
              {source.last_run_at && <span className="text-zinc-500">{formatDate(source.last_run_at)}</span>}
            </div>
            {source.coverage_note && <p className="mt-1 text-zinc-500">{source.coverage_note}</p>}
            {source.last_error && <p className="mt-1 text-red-600">{source.last_error}</p>}
          </div>)}
        </div>
      </details>

      {runsQuery.isError && <p className="text-sm text-red-600">运行记录加载失败：{runsQuery.error.message}</p>}
      {lastRun && <Card>
        <CardHeader className="flex flex-wrap items-center gap-2">
          <CardTitle>{lastRun.mode === "history" ? "历年补抓" : "招聘更新"}（{formatDate(lastRun.started_at)}）</CardTitle>
          <Badge tone={runStatusTone(lastRun.status)}>{RUN_LABELS[lastRun.status] || lastRun.status}</Badge>
          <span className="text-xs text-zinc-400">#{lastRun.id} · {lastRun.trigger === "manual" ? "手动" : "自动"}</span>
        </CardHeader>
        <CardContent className="space-y-3">
          <div className="flex flex-wrap gap-x-5 gap-y-1 text-sm">
            <span>新增 <b className="text-emerald-600">{lastRun.new_count}</b></span><span>已存在 <b>{lastRun.duplicate_count}</b></span>
            <span>疑似重复 <b className="text-amber-600">{lastRun.possible_duplicate_count}</b></span><span>已过滤 <b>{lastRun.filtered_count}</b></span>
            {lastRun.recency_skipped_count > 0 && <span>范围外跳过 <b>{lastRun.recency_skipped_count}</b></span>}
            <span>来源失败 <b className="text-red-600">{lastRun.failed_source_count}</b></span><span>进度 {lastRun.completed_source_count} / {lastRun.source_count}</span>
          </div>
          {lastRun.items.length > 0 && <details><summary className="cursor-pointer text-xs text-zinc-500">查看各来源结果与提示</summary>
            <div className="mt-2 space-y-3">{groupRunItemsBySector(lastRun.items).map((group) => <div key={group.sector}>
              <p className="mb-1 text-xs font-semibold text-zinc-500">{sectorLabel(group.sector)}</p>
              <div className="space-y-1.5">{group.items.map((item) => <div key={item.id} className="flex flex-wrap items-center gap-2 text-xs">
                <Badge tone={runStatusTone(item.status)}>{RUN_LABELS[item.status] || item.status}</Badge><span className="font-medium">{item.source_name}</span>
                {item.status !== "running" && <span className="text-zinc-500">{item.new_count} 新增 / {item.duplicate_count} 已存在{item.filtered_count ? ` / 过滤 ${item.filtered_count}` : ""}{item.warning_count ? ` / ${item.warning_count} 条提示` : ""}</span>}
                {item.error_message && <span className="break-all text-red-600">{item.error_message}</span>}
              </div>)}</div>
            </div>)}</div>
          </details>}
        </CardContent>
      </Card>}

      <Card>
        <CardHeader className="space-y-3">
          <CardTitle>公告收件箱（{total}）</CardTitle>
          <Tabs tabs={REFERENCE_TABS} value={referenceFilter} onChange={(value) => changeFilter(setReferenceFilter, value)} />
          <Tabs tabs={SECTOR_TABS} value={sectorTab} onChange={(value) => changeFilter(setSectorTab, value)} />
          <div className="flex flex-wrap items-center gap-3">
            <label className="flex items-center gap-2 text-xs text-zinc-500">公告年份<Input aria-label="公告年份" type="number" inputMode="numeric" min={2000} max={2100} placeholder="全部年份" className="w-32" value={yearFilter} onChange={(event) => changeFilter(setYearFilter, event.target.value)} /></label>
            <label className="flex items-center gap-2 text-xs text-zinc-500">审核状态<Select aria-label="审核状态" className="w-36" value={statusFilter} onChange={(event) => changeFilter(setStatusFilter, event.target.value)}>
              <option value="">全部状态</option>{Object.entries(STATUS_LABELS).map(([value, label]) => <option key={value} value={value}>{label}</option>)}
            </Select></label>
            {yearFilter && !validYear && <span className="text-xs text-amber-600">请输入 2000–2100 之间的四位年份。</span>}
          </div>
          <p className="text-xs text-zinc-500">历年要求与待遇仅供参考；“当年公告”也需核对报名截止时间。AI 解析后仍由你确认是否导入正式岗位。</p>
        </CardHeader>
        <CardContent className="space-y-4 py-4">
          {inboxQuery.isError ? <p className="text-sm text-red-600">公告加载失败：{inboxQuery.error.message}</p>
            : inboxQuery.isLoading ? <p className="text-sm text-zinc-500">加载中…</p>
            : items.length === 0 ? <EmptyState title="当前筛选下暂无公告" hint="可补抓历年公告、检查招聘更新，或调整地区和年份筛选。" />
            : <div className="space-y-3">{items.map((job) => {
              const details = readCollectionDetails(job.raw_payload);
              const originalUrl = safeWebUrl(job.source_url);
              return <article key={job.id} className="rounded-md border border-zinc-200 p-3 text-sm dark:border-zinc-700">
                <div className="mb-1.5 flex flex-wrap items-center gap-1.5">
                  <Badge tone={job.reference_status === "historical" ? "amber" : job.reference_status === "current_year" ? "blue" : "zinc"}>{referenceLabel(job.reference_status, job.announcement_year)}</Badge>
                  <Badge tone={sectorTone(job.sector)}>{sectorLabel(job.sector)}</Badge><Badge tone={statusTone(job.status)}>{STATUS_LABELS[job.status] ?? job.status}</Badge>
                  {job.province && <span className="text-xs text-zinc-500">{job.province}</span>}
                </div>
                <Link to={`/discovered/${job.id}`} className="font-medium hover:underline">{job.title_raw ?? "(无标题)"}</Link>
                <p className="mt-1 text-xs text-zinc-500">{job.organization_hint ?? "招聘单位待确认"} · {job.source_name}{job.published_at_raw ? ` · 发布 ${job.published_at_raw}` : ""}</p>
                {job.requirements_summary && <p className="mt-2 line-clamp-2 text-xs leading-relaxed"><span className="text-zinc-500">要求摘录：</span>{job.requirements_summary}</p>}
                {job.benefits_summary && <p className="mt-1 line-clamp-2 text-xs leading-relaxed"><span className="text-zinc-500">待遇摘录：</span>{job.benefits_summary}</p>}
                {details.detailStatus === "failed" && <p className="mt-1 text-xs text-amber-700">正文抓取未完成，需查看原网页或稍后重试。</p>}
                {job.status === "possible_duplicate" && job.duplicate_reason && <p className="mt-1 text-xs text-amber-600">{job.duplicate_reason}</p>}
                <div className="mt-2 flex flex-wrap items-center gap-2">
                  {originalUrl && <a href={originalUrl} target="_blank" rel="noopener noreferrer" className="text-xs underline">查看原文</a>}
                  <Link to={`/discovered/${job.id}`} className="text-xs underline">查看详情{details.attachments.length ? `及 ${details.attachments.length} 个附件` : ""}</Link>
                  <Button size="sm" variant="outline" disabled={extractMutation.isPending} onClick={() => extractMutation.mutate(job.id)}>AI 解析</Button>
                  <Button size="sm" variant="ghost" disabled={statusMutation.isPending} onClick={() => statusMutation.mutate({ id: job.id, status: job.status === "ignored" ? "new" : "ignored" })}>{job.status === "ignored" ? "恢复" : "忽略"}</Button>
                  <span className="ml-auto text-xs text-zinc-400">发现 {formatDate(job.discovered_at)}</span>
                </div>
              </article>;
            })}</div>}
          {total > 0 && <div className="flex items-center justify-between gap-3 border-t border-zinc-200 pt-3 text-xs text-zinc-500 dark:border-zinc-800">
            <span>第 {page} / {pages} 页 · 共 {total} 条</span><div className="flex gap-2">
              <Button size="sm" variant="outline" disabled={page <= 1 || inboxQuery.isFetching} onClick={() => setPage((value) => value - 1)}>上一页</Button>
              <Button size="sm" variant="outline" disabled={page >= pages || inboxQuery.isFetching} onClick={() => setPage((value) => value + 1)}>下一页</Button>
            </div>
          </div>}
        </CardContent>
      </Card>
    </div>
  );
}
