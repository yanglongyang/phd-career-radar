import { useQuery } from "@tanstack/react-query";
import { Link } from "react-router-dom";
import { api } from "../services/api";
import type { Dashboard } from "../types";
import { EmptyState, PageHeader, Badge, Card, CardContent } from "../components/ui";
import {
  JOB_CATEGORY_LABELS,
  RECOMMENDATION_LABELS,
  formatDate,
} from "../lib/utils";

const COUNT_CARDS: {
  key: keyof Dashboard["counts"];
  label: string;
  accent: string;
  to?: string;
}[] = [
  { key: "new_today", label: "今日新增", accent: "text-zinc-900 dark:text-zinc-100", to: "/jobs" },
  { key: "to_review", label: "待查看", accent: "text-zinc-900 dark:text-zinc-100", to: "/jobs" },
  { key: "high_match", label: "高匹配（S/A）", accent: "text-emerald-600 dark:text-emerald-400", to: "/jobs" },
  { key: "focus", label: "重点关注", accent: "text-sky-600 dark:text-sky-400", to: "/jobs" },
  { key: "preparing", label: "准备投递", accent: "text-amber-600 dark:text-amber-400", to: "/applications" },
  { key: "applied", label: "已投递", accent: "text-zinc-900 dark:text-zinc-100", to: "/applications" },
  { key: "interviewing", label: "面试中", accent: "text-sky-600 dark:text-sky-400", to: "/applications" },
  { key: "offer", label: "Offer", accent: "text-emerald-600 dark:text-emerald-400", to: "/applications" },
];

function recommendationTone(level: string | null) {
  switch (level) {
    case "S":
      return "green" as const;
    case "A":
      return "blue" as const;
    case "B":
      return "neutral" as const;
    case "C":
      return "amber" as const;
    case "D":
      return "zinc" as const;
    case "X":
      return "red" as const;
    default:
      return "zinc" as const;
  }
}

export default function DashboardPage() {
  const { data, isLoading } = useQuery({
    queryKey: ["dashboard"],
    queryFn: () => api<Dashboard>("/dashboard"),
  });

  return (
    <div>
      <PageHeader
        title="Dashboard"
        subtitle="把注意力留给真正值得看的岗位；投递决策始终由你本人做出。"
      />

      <div className="grid grid-cols-4 gap-3">
        {COUNT_CARDS.map((card) => (
          <Card key={card.key} className={card.to ? "cursor-pointer transition-colors hover:border-zinc-400 dark:hover:border-zinc-600" : ""} onClick={card.to ? () => (window.location.href = card.to!) : undefined}>
            <CardContent className="py-4">
              <p className="text-xs text-zinc-500 dark:text-zinc-400">{card.label}</p>
              <p className={`mt-1 text-2xl font-semibold tabular-nums ${card.accent}`}>
                {isLoading ? "…" : data?.counts[card.key] ?? 0}
              </p>
            </CardContent>
          </Card>
        ))}
      </div>

      <div className="mt-6">
        <h2 className="mb-3 text-sm font-semibold text-zinc-700 dark:text-zinc-300">Top Jobs（按综合评分）</h2>
        <Card>
          {data && data.top_jobs.length > 0 ? (
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b border-zinc-200 text-left text-xs text-zinc-500 dark:border-zinc-800 dark:text-zinc-400">
                  <th className="px-4 py-2.5 font-medium">综合分</th>
                  <th className="px-4 py-2.5 font-medium">推荐</th>
                  <th className="px-4 py-2.5 font-medium">单位 / 院系</th>
                  <th className="px-4 py-2.5 font-medium">岗位</th>
                  <th className="px-4 py-2.5 font-medium">类型</th>
                  <th className="px-4 py-2.5 font-medium">城市</th>
                  <th className="px-4 py-2.5 font-medium">首次发现</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-zinc-100 dark:divide-zinc-800">
                {data.top_jobs.map((job) => (
                  <tr key={job.id} className="hover:bg-zinc-50 dark:hover:bg-zinc-800/50">
                    <td className="px-4 py-2.5">
                      <div className="font-semibold tabular-nums">{job.evaluation?.total_score ?? "—"}</div>
                      {job.evaluation?.score_coverage != null && (
                        <div
                          className={
                            job.evaluation.score_coverage < 40
                              ? "text-xs font-medium text-amber-600 dark:text-amber-400"
                              : "text-xs text-zinc-400"
                          }
                          title="评分覆盖度：已评分维度的权重占比"
                        >
                          覆盖 {job.evaluation.score_coverage}%
                          {job.evaluation.score_coverage < 40 ? " ⚠" : ""}
                        </div>
                      )}
                    </td>
                    <td className="px-4 py-2.5">
                      <Badge tone={recommendationTone(job.evaluation?.recommendation_level ?? null)}>
                        {job.evaluation?.recommendation_level ?? "—"}
                        {job.evaluation?.recommendation_level
                          ? ` ${RECOMMENDATION_LABELS[job.evaluation.recommendation_level] ?? ""}`
                          : ""}
                      </Badge>
                    </td>
                    <td className="px-4 py-2.5">
                      {job.organization?.name ?? "—"}
                      {job.department && <span className="text-zinc-400"> · {job.department}</span>}
                    </td>
                    <td className="px-4 py-2.5">
                      <Link to={`/jobs/${job.id}`} className="font-medium hover:underline">
                        {job.title}
                      </Link>
                    </td>
                    <td className="px-4 py-2.5 text-zinc-500 dark:text-zinc-400">
                      {JOB_CATEGORY_LABELS[job.job_category] ?? job.job_category}
                    </td>
                    <td className="px-4 py-2.5 text-zinc-500 dark:text-zinc-400">{job.city ?? "—"}</td>
                    <td className="px-4 py-2.5 text-zinc-500 dark:text-zinc-400">{formatDate(job.first_seen_at)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          ) : (
            <EmptyState
              title="还没有已评估的岗位"
              hint="先到「岗位库」手工录入几个岗位；AI 评估将在 Phase 4 接入。"
            />
          )}
        </Card>
      </div>
    </div>
  );
}
