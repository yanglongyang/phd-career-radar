import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";
import { Link, useNavigate, useParams } from "react-router-dom";
import { api } from "../services/api";
import type { JobDetail } from "../types";
import {
  Badge,
  Button,
  Card,
  CardContent,
  CardHeader,
  CardTitle,
  EmptyState,
  Field,
  PageHeader,
  ScoreBar,
  Select,
  Tabs,
  Textarea,
} from "../components/ui";
import {
  CONFIDENCE_LABELS,
  JOB_CATEGORY_LABELS,
  JOB_STATUS_LABELS,
  POSITION_NATURE_LABELS,
  RISK_LABELS,
  RECOMMENDATION_LABELS,
  formatDate,
} from "../lib/utils";

const TABS = [
  { key: "overview", label: "Overview" },
  { key: "description", label: "Job Description" },
  { key: "evaluation", label: "AI Evaluation" },
  { key: "institution", label: "Institution" },
  { key: "region", label: "Region" },
  { key: "reputation", label: "Reputation" },
  { key: "evidence", label: "Evidence" },
  { key: "application", label: "Application" },
  { key: "history", label: "History" },
];

function recommendationTone(level: string | null) {
  switch (level) {
    case "S": return "green" as const;
    case "A": return "blue" as const;
    case "B": return "neutral" as const;
    case "C": return "amber" as const;
    case "D": return "zinc" as const;
    case "X": return "red" as const;
    default: return "zinc" as const;
  }
}

function riskTone(risk: string | null) {
  switch (risk) {
    case "low": return "green" as const;
    case "medium": return "amber" as const;
    case "high": return "orange" as const;
    case "critical": return "red" as const;
    default: return "zinc" as const;
  }
}

export default function JobDetailPage() {
  const { id } = useParams();
  const navigate = useNavigate();
  const queryClient = useQueryClient();
  const [tab, setTab] = useState("overview");
  const [userNotes, setUserNotes] = useState<string | null>(null);

  const { data: job, isLoading } = useQuery({
    queryKey: ["job", id],
    queryFn: () => api<JobDetail>(`/jobs/${id}`),
    enabled: !!id,
  });

  const patchMutation = useMutation({
    mutationFn: (payload: Record<string, unknown>) =>
      api<JobDetail>(`/jobs/${id}`, { method: "PATCH", body: JSON.stringify(payload) }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["job", id] });
      queryClient.invalidateQueries({ queryKey: ["jobs"] });
      queryClient.invalidateQueries({ queryKey: ["dashboard"] });
    },
  });

  const deleteMutation = useMutation({
    mutationFn: () => api<void>(`/jobs/${id}`, { method: "DELETE" }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["jobs"] });
      navigate("/jobs");
    },
  });

  if (isLoading) return <p className="text-sm text-zinc-500">加载中…</p>;
  if (!job) return <EmptyState title="岗位不存在" />;

  const evaluation = job.evaluation;

  return (
    <div>
      <PageHeader
        title={job.title}
        subtitle={
          <>
            {job.organization ? (
              <Link to="/organizations" className="hover:underline">{job.organization.name}</Link>
            ) : "未登记单位"}
            {job.department ? ` · ${job.department}` : ""}
            {job.city ? ` · ${[job.province, job.city].filter(Boolean).join(" / ")}` : ""}
            {` · ${JOB_CATEGORY_LABELS[job.job_category] ?? job.job_category}`}
          </>
        }
        actions={
          <>
            <Select
              className="w-36"
              value={job.status}
              onChange={(e) => patchMutation.mutate({ status: e.target.value })}
            >
              {Object.entries(JOB_STATUS_LABELS).map(([value, label]) => (
                <option key={value} value={value}>{label}</option>
              ))}
            </Select>
            <Button
              variant="danger"
              onClick={() => {
                if (window.confirm(`确定删除岗位「${job.title}」？相关评估、证据与历史版本会一并删除。`)) {
                  deleteMutation.mutate();
                }
              }}
            >
              删除
            </Button>
          </>
        }
      />

      {/* 顶部指标条 */}
      <Card className="mb-4">
        <CardContent className="flex flex-wrap items-center gap-6 py-4">
          <div>
            <p className="text-xs text-zinc-500">综合评分</p>
            <p className="text-3xl font-semibold tabular-nums">{evaluation?.total_score ?? "—"}</p>
          </div>
          <div>
            <p className="mb-1 text-xs text-zinc-500">推荐等级</p>
            <Badge tone={recommendationTone(evaluation?.recommendation_level ?? null)}>
              {evaluation?.recommendation_level
                ? `${evaluation.recommendation_level} · ${RECOMMENDATION_LABELS[evaluation.recommendation_level]}`
                : "未评估"}
            </Badge>
          </div>
          <div>
            <p className="mb-1 text-xs text-zinc-500">风险等级</p>
            <Badge tone={riskTone(evaluation?.risk_level ?? null)}>
              {evaluation?.risk_level ? RISK_LABELS[evaluation.risk_level] : "未知"}
            </Badge>
          </div>
          <div>
            <p className="mb-1 text-xs text-zinc-500">信息可信度</p>
            <Badge tone={evaluation?.confidence_level === "high" ? "green" : evaluation?.confidence_level === "low" ? "zinc" : "amber"}>
              {evaluation?.confidence_level ? CONFIDENCE_LABELS[evaluation.confidence_level] : "未评估"}
            </Badge>
          </div>
          <div>
            <p className="mb-1 text-xs text-zinc-500">岗位性质</p>
            <Badge tone={job.position_nature === "unknown" ? "zinc" : "neutral"}>
              {POSITION_NATURE_LABELS[job.position_nature] ?? job.position_nature}
            </Badge>
          </div>
          <div>
            <p className="mb-1 text-xs text-zinc-500">截止日期</p>
            <p className="text-sm font-medium">{formatDate(job.deadline)}</p>
          </div>
          <div>
            <p className="mb-1 text-xs text-zinc-500">待遇</p>
            <p className="text-sm font-medium">{job.salary_text ?? "未知/待确认"}</p>
          </div>
          {job.source_url && (
            <div>
              <p className="mb-1 text-xs text-zinc-500">公告链接</p>
              <a href={job.source_url} target="_blank" rel="noreferrer" className="text-sm font-medium underline">
                查看原文
              </a>
            </div>
          )}
        </CardContent>
      </Card>

      <Tabs
        tabs={TABS.map((t) =>
          t.key === "history" && job.versions.length > 0 ? { ...t, badge: String(job.versions.length) } : t,
        )}
        value={tab}
        onChange={setTab}
      />

      <div className="pt-4">
        {tab === "overview" && (
          evaluation ? (
            <div className="grid grid-cols-2 gap-4">
              <Card>
                <CardHeader><CardTitle>AI 概述</CardTitle></CardHeader>
                <CardContent className="text-sm leading-relaxed">{evaluation.summary || "—"}</CardContent>
              </Card>
              <Card>
                <CardHeader><CardTitle>需要确认的问题</CardTitle></CardHeader>
                <CardContent>
                  <ul className="list-disc space-y-1 pl-5 text-sm">
                    {(evaluation.questions.length > 0 ? evaluation.questions : ["—"]).map((q, i) => <li key={i}>{q}</li>)}
                  </ul>
                </CardContent>
              </Card>
              <Card>
                <CardHeader><CardTitle>主要优势</CardTitle></CardHeader>
                <CardContent>
                  <ul className="list-disc space-y-1 pl-5 text-sm">
                    {(evaluation.strengths.length > 0 ? evaluation.strengths : ["—"]).map((s, i) => <li key={i}>{s}</li>)}
                  </ul>
                </CardContent>
              </Card>
              <Card>
                <CardHeader><CardTitle>主要风险</CardTitle></CardHeader>
                <CardContent>
                  <ul className="list-disc space-y-1 pl-5 text-sm">
                    {(evaluation.risks.length > 0 ? evaluation.risks : ["—"]).map((r, i) => <li key={i}>{r}</li>)}
                  </ul>
                </CardContent>
              </Card>
              <Card className="col-span-2">
                <CardHeader><CardTitle>最大信息缺口（未知 / 待确认）</CardTitle></CardHeader>
                <CardContent>
                  <ul className="list-disc space-y-1 pl-5 text-sm text-amber-700 dark:text-amber-300">
                    {(evaluation.unknowns.length > 0 ? evaluation.unknowns : ["—"]).map((u, i) => <li key={i}>{u}</li>)}
                  </ul>
                </CardContent>
              </Card>
            </div>
          ) : (
            <EmptyState
              title="尚未进行 AI 评估"
              hint="评估能力将在 Phase 4 接入：Profile + Job + Evidence → 结构化评估。"
            />
          )
        )}

        {tab === "description" && (
          <Card>
            <CardHeader className="flex items-center justify-between">
              <CardTitle>招聘公告原文</CardTitle>
              {job.has_version_changes && <Badge tone="amber">公告发生过变更（见 History）</Badge>}
            </CardHeader>
            <CardContent>
              {job.description_raw ? (
                <pre className="whitespace-pre-wrap font-sans text-sm leading-relaxed">{job.description_raw}</pre>
              ) : (
                <EmptyState title="未保存公告原文" hint="编辑岗位或使用 Phase 3 的粘贴导入。" />
              )}
            </CardContent>
          </Card>
        )}

        {tab === "evaluation" && (
          evaluation ? (
            <div className="grid grid-cols-2 gap-4">
              <Card className="col-span-2">
                <CardHeader className="flex items-center justify-between">
                  <CardTitle>八维评分</CardTitle>
                  <span className="text-xs text-zinc-400">
                    模型：{evaluation.model ?? "—"} · Prompt：{evaluation.prompt_version ?? "—"} · {formatDate(evaluation.evaluated_at)}
                  </span>
                </CardHeader>
                <CardContent className="grid grid-cols-2 gap-x-8 gap-y-4">
                  <ScoreBar label="岗位与个人匹配度" score={evaluation.fit_score} />
                  <ScoreBar label="岗位性质与稳定性" score={evaluation.career_stability_score} />
                  <ScoreBar label="科研平台与资源" score={evaluation.research_resources_score} />
                  <ScoreBar label="地区" score={evaluation.region_score} />
                  <ScoreBar label="待遇" score={evaluation.compensation_score} />
                  <ScoreBar label="风评与组织环境" score={evaluation.reputation_score} />
                  <ScoreBar label="教学与行政负担" score={evaluation.workload_score} />
                  <ScoreBar label="长期发展潜力" score={evaluation.long_term_score} />
                </CardContent>
              </Card>
              <Card className="col-span-2">
                <CardHeader><CardTitle>劣势 / 弱点</CardTitle></CardHeader>
                <CardContent>
                  <ul className="list-disc space-y-1 pl-5 text-sm">
                    {(evaluation.weaknesses.length > 0 ? evaluation.weaknesses : ["—"]).map((w, i) => <li key={i}>{w}</li>)}
                  </ul>
                </CardContent>
              </Card>
            </div>
          ) : (
            <EmptyState title="尚未进行 AI 评估" hint="评估能力将在 Phase 4 接入。" />
          )
        )}

        {tab === "institution" && (
          <Card>
            <CardContent className="grid grid-cols-2 gap-4 py-4 text-sm">
              <InfoRow label="单位名称" value={job.organization?.name ?? "未登记"} />
              <InfoRow label="单位类型" value={job.organization?.organization_type ?? "未知"} />
              <InfoRow label="省份 / 城市" value={[job.organization?.province ?? job.province, job.organization?.city ?? job.city].filter(Boolean).join(" / ") || "—"} />
              <InfoRow label="院系" value={job.department ?? "—"} />
              <InfoRow label="学历要求" value={job.degree_requirement ?? "未知/待确认"} />
              <InfoRow label="经验要求" value={job.experience_requirement ?? "未知/待确认"} />
              <InfoRow label="用工类型" value={job.employment_type ?? "未知/待确认"} />
              <InfoRow label="发布日期" value={formatDate(job.posted_at)} />
            </CardContent>
          </Card>
        )}

        {tab === "region" && (
          <Card>
            <CardContent className="py-4 text-sm leading-relaxed">
              <p>
                工作地点：<b>{[job.province, job.city].filter(Boolean).join(" / ") || "未知"}</b>
              </p>
              <p className="mt-2 text-zinc-500 dark:text-zinc-400">
                地区偏好分层（preferred / acceptable / neutral / avoid）与子维度评分由
                <code className="mx-1 rounded bg-zinc-100 px-1.5 py-0.5 dark:bg-zinc-800">config/regions.yaml</code>
                与 <code className="mx-1 rounded bg-zinc-100 px-1.5 py-0.5 dark:bg-zinc-800">config/scoring.yaml</code>
                驱动；地区评分将在 Phase 4 评估时写入。
              </p>
            </CardContent>
          </Card>
        )}

        {tab === "reputation" && (
          <EmptyState
            title="风评聚合将在 Phase 6 提供"
            hint="按主题聚合正/负面来源数、独立来源数与证据等级（A/B/C/D），不输出绝对化判断。"
          />
        )}

        {tab === "evidence" && (
          <EmptyState
            title="Evidence 管理将在 Phase 6 提供"
            hint="每条重要结论（考核要求、启动经费、待遇兑现等）都可追溯到来源与证据等级。"
          />
        )}

        {tab === "application" && (
          <EmptyState
            title="申请 CRM 将在 Phase 5 提供"
            hint="Shortlist、申请状态流转（14 个状态）、面试记录与 next action。"
          />
        )}

        {tab === "history" && (
          job.versions.length > 0 ? (
            <div className="space-y-3">
              {job.versions.map((v) => (
                <Card key={v.id}>
                  <CardHeader className="flex items-center justify-between">
                    <CardTitle>变更于 {formatDate(v.captured_at)}</CardTitle>
                    <span className="text-xs text-zinc-400">hash {v.content_hash.slice(0, 10)}</span>
                  </CardHeader>
                  <CardContent className="space-y-2">
                    {v.changes.map((c, i) => (
                      <div key={i} className="flex flex-wrap items-baseline gap-2 text-sm">
                        <Badge tone="amber">{c.field}</Badge>
                        <span className="text-zinc-500 line-through dark:text-zinc-400">{c.old ?? "（空）"}</span>
                        <span className="text-zinc-400">→</span>
                        <span className="font-medium">{c.new ?? "（空）"}</span>
                      </div>
                    ))}
                  </CardContent>
                </Card>
              ))}
            </div>
          ) : (
            <EmptyState title="暂无版本历史" hint="当公告的正文、薪资或截止日期发生变化时，会自动保存变更记录。" />
          )
        )}
      </div>

      {/* 用户决策区 —— 与 AI 评估完全分开 */}
      <Card className="mt-6">
        <CardHeader><CardTitle>我的判断（独立于 AI 评估）</CardTitle></CardHeader>
        <CardContent className="grid grid-cols-4 items-end gap-4">
          <Field label="我的评分（1-5）">
            <Select
              value={job.user_rating ?? ""}
              onChange={(e) => patchMutation.mutate({ user_rating: e.target.value ? Number(e.target.value) : null })}
            >
              <option value="">未评分</option>
              {[1, 2, 3, 4, 5].map((n) => <option key={n} value={n}>{n}</option>)}
            </Select>
          </Field>
          <Field label="我的优先级（1-10）">
            <Select
              value={job.user_priority ?? ""}
              onChange={(e) => patchMutation.mutate({ user_priority: e.target.value ? Number(e.target.value) : null })}
            >
              <option value="">未设置</option>
              {Array.from({ length: 10 }, (_, i) => i + 1).map((n) => <option key={n} value={n}>{n}</option>)}
            </Select>
          </Field>
          <div className="col-span-2">
            <Field label="我的备注">
              <Textarea
                rows={2}
                value={userNotes ?? job.user_notes ?? ""}
                onChange={(e) => setUserNotes(e.target.value)}
                placeholder="记录自己的判断、联系进展等"
              />
            </Field>
          </div>
          <div className="col-span-4 flex justify-end">
            <Button
              size="sm"
              variant="outline"
              disabled={userNotes === null || patchMutation.isPending}
              onClick={() => patchMutation.mutate({ user_notes: userNotes })}
            >
              保存备注
            </Button>
          </div>
        </CardContent>
      </Card>
    </div>
  );
}

function InfoRow({ label, value }: { label: string; value: string }) {
  return (
    <div className="flex gap-2">
      <span className="w-24 shrink-0 text-zinc-500 dark:text-zinc-400">{label}</span>
      <span className="font-medium">{value}</span>
    </div>
  );
}
