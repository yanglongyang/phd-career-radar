import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";
import { getReputationReport, synthesizeReputation } from "../services/api";
import type { ReputationTopicStat } from "../types";
import { Badge, Button, Card, CardContent, CardHeader, CardTitle, EmptyState } from "./ui";
import { formatDate } from "../lib/utils";

/* Reputation 页签（Phase 6）：风评聚合报告。
   数字（来源数/独立来源数/等级/时间跨度）由后端确定性统计；AI 只补充叙述结论。
   unknown-scope / 单源 / 纯 C-D 主题标记为"仅情报参考"，不进入定量评分。 */

const TOPIC_LABELS: Record<string, string> = {
  assessment_pressure: "考核压力",
  salary_fulfillment: "待遇兑现",
  startup_funding_fulfillment: "启动经费兑现",
  administrative_burden: "行政负担",
  teaching_load: "教学负担",
  young_faculty_turnover: "青年教师流动",
  promotion_environment: "晋升环境",
  department_management: "院系管理",
  research_collaboration: "科研协作",
  student_resources: "学生资源",
  other: "其他",
};

function eligibilityTone(eligible: boolean) {
  return eligible ? "green" : "amber";
}

function TopicCard({ stat }: { stat: ReputationTopicStat }) {
  return (
    <Card>
      <CardHeader className="flex flex-wrap items-center justify-between gap-2">
        <CardTitle>{TOPIC_LABELS[stat.topic] ?? stat.topic}</CardTitle>
        <Badge tone={eligibilityTone(stat.eligible_for_scoring)}>
          {stat.eligible_for_scoring ? "可作为定量风评依据" : "仅情报参考"}
        </Badge>
      </CardHeader>
      <CardContent className="space-y-2 text-sm">
        <div className="flex flex-wrap gap-x-6 gap-y-1">
          <span>
            独立来源 <b className="tabular-nums">{stat.independent_sources}</b>
          </span>
          <span className="text-emerald-600 dark:text-emerald-400">正面 {stat.positive_sources}</span>
          <span className="text-red-600 dark:text-red-400">负面 {stat.negative_sources}</span>
          <span className="text-zinc-500 dark:text-zinc-400">
            等级 {stat.evidence_levels.join(" / ") || "—"}
          </span>
          {(stat.time_start || stat.time_end) && (
            <span className="text-zinc-500 dark:text-zinc-400">
              时间跨度 {stat.time_start ?? "?"} ~ {stat.time_end ?? "?"}
            </span>
          )}
        </div>
        <p className="text-xs text-zinc-500 dark:text-zinc-400">{stat.eligible_reason}</p>
        {stat.ai_conclusion && (
          <p className="rounded bg-zinc-50 px-3 py-2 text-sm leading-relaxed dark:bg-zinc-800/60">
            {stat.ai_conclusion}
          </p>
        )}
      </CardContent>
    </Card>
  );
}

export default function ReputationTab({ organizationId }: { organizationId: number | null }) {
  const queryClient = useQueryClient();
  const [errorMsg, setErrorMsg] = useState<string | null>(null);

  const reportQuery = useQuery({
    queryKey: ["reputation", organizationId],
    queryFn: () => getReputationReport(organizationId!),
    enabled: organizationId != null,
  });

  const synthesizeMutation = useMutation({
    mutationFn: () => synthesizeReputation(organizationId!),
    onSuccess: () => {
      setErrorMsg(null);
      queryClient.invalidateQueries({ queryKey: ["reputation", organizationId] });
    },
    onError: (err) => setErrorMsg(err.message),
  });

  if (organizationId == null) {
    return (
      <EmptyState
        title="岗位未关联单位"
        hint="风评按单位/院系聚合；请先在岗位或单位库中登记所属单位。"
      />
    );
  }

  const report = reportQuery.data;

  return (
    <div className="space-y-4">
      <Card>
        <CardHeader className="flex flex-wrap items-center justify-between gap-2">
          <CardTitle>风评聚合（确定性统计）</CardTitle>
          <div className="flex items-center gap-2">
            {report && (
              <span className="text-xs text-zinc-400">
                整体可信度：{report.overall_confidence}
                {report.synthesized_by_ai ? ` · AI 综合（${report.prompt_version}）` : ""}
              </span>
            )}
            <Button
              size="sm"
              variant="outline"
              onClick={() => synthesizeMutation.mutate()}
              disabled={synthesizeMutation.isPending}
            >
              {synthesizeMutation.isPending ? "AI 综合中…" : "生成 AI 综合分析"}
            </Button>
          </div>
        </CardHeader>
        <CardContent className="text-xs leading-relaxed text-zinc-500 dark:text-zinc-400">
          来源数、独立来源数（按独立来源键去重，转载跟随源头）、等级分布与时间跨度全部由后端
          确定性统计产生；AI 只提供主题叙述结论。单源或纯 C/D 主题、以及 scope 未标明的证据
          仅作情报参考，不会自动进入定量风评。
          {(reportQuery.isError || errorMsg) && (
            <p className="mt-2 rounded-md border border-red-300 bg-red-50 px-3 py-2 text-red-700 dark:border-red-700 dark:bg-red-900/30 dark:text-red-300">
              {reportQuery.isError ? `风评报告加载失败：${reportQuery.error.message}` : errorMsg}
            </p>
          )}
        </CardContent>
      </Card>

      {reportQuery.isLoading ? (
        <EmptyState title="加载中…" />
      ) : report ? (
        <>
          {report.topics.length > 0 ? (
            <div className="grid grid-cols-1 gap-4 xl:grid-cols-2">
              {report.topics.map((t) => (
                <TopicCard key={t.topic} stat={t} />
              ))}
            </div>
          ) : (
            <EmptyState
              title="尚无可统计的风评主题"
              hint="在证据页签添加单位/院系级证据后，这里会按主题聚合。"
            />
          )}

          {report.clues.length > 0 && (
            <Card>
              <CardHeader>
                <CardTitle>情报线索（不进入定量评分）</CardTitle>
              </CardHeader>
              <CardContent className="space-y-2">
                {report.clues.map((c) => (
                  <div key={c.evidence_id} className="text-sm">
                    <Badge tone="zinc">#{c.evidence_id}</Badge>{" "}
                    <span className="text-zinc-600 dark:text-zinc-300">{c.claim}</span>
                    <span className="ml-2 text-xs text-zinc-400">{c.reason}</span>
                  </div>
                ))}
                <p className="pt-1 text-xs text-zinc-400">
                  报告生成于 {formatDate(report.generated_at)}
                </p>
              </CardContent>
            </Card>
          )}
        </>
      ) : null}
    </div>
  );
}
