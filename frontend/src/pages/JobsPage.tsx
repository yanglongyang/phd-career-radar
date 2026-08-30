import { useQuery } from "@tanstack/react-query";
import { useState } from "react";
import { Link } from "react-router-dom";
import { api, buildQuery, type JobQueryParams } from "../services/api";
import type { JobListItem } from "../types";
import { Badge, Button, Card, EmptyState, Input, PageHeader, Select } from "../components/ui";
import {
  JOB_CATEGORY_LABELS,
  JOB_STATUS_LABELS,
  POSITION_NATURE_LABELS,
  formatDate,
} from "../lib/utils";

interface JobListPage {
  items: JobListItem[];
  total: number;
  page: number;
  page_size: number;
}

export default function JobsPage() {
  const [filters, setFilters] = useState<JobQueryParams>({});
  const [page, setPage] = useState(1);

  const queryString = buildQuery({ ...filters, page, page_size: 20 });
  const { data, isLoading } = useQuery({
    queryKey: ["jobs", queryString],
    queryFn: () => api<JobListPage>(`/jobs${queryString}`),
  });

  const set = (patch: Partial<JobQueryParams>) => {
    setPage(1);
    setFilters((f) => ({ ...f, ...patch }));
  };

  const totalPages = data ? Math.max(1, Math.ceil(data.total / data.page_size)) : 1;

  return (
    <div>
      <PageHeader
        title="岗位库"
        subtitle={data ? `共 ${data.total} 个岗位` : undefined}
        actions={
          <Link to="/jobs/new">
            <Button>+ 新增岗位</Button>
          </Link>
        }
      />

      <Card className="mb-4 p-3">
        <div className="grid grid-cols-6 gap-2">
          <Input placeholder="搜索岗位/院系…" value={filters.q ?? ""} onChange={(e) => set({ q: e.target.value })} />
          <Select value={filters.job_category ?? ""} onChange={(e) => set({ job_category: e.target.value })}>
            <option value="">全部类型</option>
            {Object.entries(JOB_CATEGORY_LABELS).map(([value, label]) => (
              <option key={value} value={value}>{label}</option>
            ))}
          </Select>
          <Select value={filters.status ?? ""} onChange={(e) => set({ status: e.target.value })}>
            <option value="">全部状态</option>
            {Object.entries(JOB_STATUS_LABELS).map(([value, label]) => (
              <option key={value} value={value}>{label}</option>
            ))}
          </Select>
          <Input placeholder="省份" value={filters.province ?? ""} onChange={(e) => set({ province: e.target.value })} />
          <Input placeholder="城市" value={filters.city ?? ""} onChange={(e) => set({ city: e.target.value })} />
          <Select value={filters.sort ?? "first_seen_at"} onChange={(e) => set({ sort: e.target.value })}>
            <option value="first_seen_at">按最新发现</option>
            <option value="total_score">按综合评分</option>
            <option value="deadline">按截止时间</option>
            <option value="region">按地区评分</option>
            <option value="reputation">按风评评分</option>
          </Select>
        </div>
      </Card>

      <Card>
        {isLoading ? (
          <EmptyState title="加载中…" />
        ) : data && data.items.length > 0 ? (
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b border-zinc-200 text-left text-xs text-zinc-500 dark:border-zinc-800 dark:text-zinc-400">
                <th className="px-4 py-2.5 font-medium">岗位</th>
                <th className="px-4 py-2.5 font-medium">单位 / 院系</th>
                <th className="px-4 py-2.5 font-medium">类型</th>
                <th className="px-4 py-2.5 font-medium">性质</th>
                <th className="px-4 py-2.5 font-medium">地点</th>
                <th className="px-4 py-2.5 font-medium">待遇</th>
                <th className="px-4 py-2.5 font-medium">状态</th>
                <th className="px-4 py-2.5 font-medium">评分</th>
                <th className="px-4 py-2.5 font-medium">截止</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-zinc-100 dark:divide-zinc-800">
              {data.items.map((job) => (
                <tr key={job.id} className="hover:bg-zinc-50 dark:hover:bg-zinc-800/50">
                  <td className="px-4 py-2.5">
                    <Link to={`/jobs/${job.id}`} className="font-medium hover:underline">
                      {job.title}
                    </Link>
                  </td>
                  <td className="px-4 py-2.5">
                    {job.organization?.name ?? "—"}
                    {job.department && <span className="text-zinc-400"> · {job.department}</span>}
                  </td>
                  <td className="px-4 py-2.5 text-zinc-500 dark:text-zinc-400">
                    {JOB_CATEGORY_LABELS[job.job_category] ?? job.job_category}
                  </td>
                  <td className="px-4 py-2.5">
                    <Badge tone={job.position_nature === "unknown" ? "zinc" : "neutral"}>
                      {POSITION_NATURE_LABELS[job.position_nature] ?? job.position_nature}
                    </Badge>
                  </td>
                  <td className="px-4 py-2.5 text-zinc-500 dark:text-zinc-400">
                    {[job.province, job.city].filter(Boolean).join(" · ") || "—"}
                  </td>
                  <td className="px-4 py-2.5 text-zinc-500 dark:text-zinc-400">{job.salary_text ?? "—"}</td>
                  <td className="px-4 py-2.5">{JOB_STATUS_LABELS[job.status] ?? job.status}</td>
                  <td className="px-4 py-2.5 font-semibold tabular-nums">
                    {job.evaluation?.total_score ?? "—"}
                  </td>
                  <td className="px-4 py-2.5 text-zinc-500 dark:text-zinc-400">{formatDate(job.deadline)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        ) : (
          <EmptyState title="没有匹配的岗位" hint="调整筛选条件，或点击右上角「新增岗位」手工录入。" />
        )}
      </Card>

      {data && data.total > data.page_size && (
        <div className="mt-4 flex items-center justify-between text-sm text-zinc-500">
          <span>
            第 {data.page} / {totalPages} 页
          </span>
          <div className="flex gap-2">
            <Button variant="outline" size="sm" disabled={page <= 1} onClick={() => setPage((p) => p - 1)}>
              上一页
            </Button>
            <Button variant="outline" size="sm" disabled={page >= totalPages} onClick={() => setPage((p) => p + 1)}>
              下一页
            </Button>
          </div>
        </div>
      )}
    </div>
  );
}
