import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";
import { Link, useNavigate, useParams } from "react-router-dom";
import { api, createApplication, evaluateJob, getApplicationByJob, updateApplication } from "../services/api";
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
  APPLICATION_STATUS_LABELS,
  applicationStatusTone,
  CONFIDENCE_LABELS,
  CONTRACT_TYPE_LABELS,
  ESTABLISHMENT_LABELS,
  FUNDING_SOURCE_LABELS,
  JOB_CATEGORY_LABELS,
  JOB_STATUS_LABELS,
  RISK_LABELS,
  RECOMMENDATION_LABELS,
  TENURE_LABELS,
  employmentSummary,
  formatDate,
} from "../lib/utils";
import type { AcademicJobDetails } from "../types";
import EvidenceTab from "../components/EvidenceTab";
import ReputationTab from "../components/ReputationTab";

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

  const evaluateMutation = useMutation({
    mutationFn: () => evaluateJob(Number(id)),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["job", id] });
      queryClient.invalidateQueries({ queryKey: ["jobs"] });
      queryClient.invalidateQueries({ queryKey: ["dashboard"] });
      setTab("evaluation");
    },
  });

  const applicationQuery = useQuery({
    queryKey: ["application", id],
    queryFn: () => getApplicationByJob(Number(id)),
    enabled: !!id,
  });
  const application = applicationQuery.data ?? null;

  const createAppMutation = useMutation({
    mutationFn: () => createApplication(Number(id)),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["application", id] });
      queryClient.invalidateQueries({ queryKey: ["applications"] });
      queryClient.invalidateQueries({ queryKey: ["dashboard"] });
    },
  });
  const appStatusMutation = useMutation({
    mutationFn: ({ appId, status }: { appId: number; status: string }) =>
      updateApplication(appId, { status }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["application", id] });
      queryClient.invalidateQueries({ queryKey: ["applications"] });
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
                if (window.confirm(`确定删除岗位「${job.title}」？评估、申请记录与历史版本会一并删除；风评证据会保留（与岗位解绑）。`)) {
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
            {evaluation?.score_coverage !== null && evaluation?.score_coverage !== undefined && (
              <p
                className={
                  evaluation.score_coverage < 40
                    ? "mt-0.5 text-xs font-medium text-amber-600 dark:text-amber-400"
                    : "mt-0.5 text-xs text-zinc-400"
                }
                title="评分覆盖度：已评分维度的权重占比；覆盖度低表示高分可能基于少量信息"
              >
                覆盖度 {evaluation.score_coverage}%
                {evaluation.score_coverage < 40 ? " · 信息覆盖不足" : ""}
              </p>
            )}
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
            <p className="mb-1 text-xs text-zinc-500">聘用</p>
            <Badge tone={job.academic_details ? "neutral" : "zinc"}>
              {employmentSummary(job.academic_details)}
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
              hint="切换到 AI Evaluation 页签开始评估。"
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
          !evaluation ? (
            <Card>
              <CardContent className="flex flex-col items-center gap-3 py-10">
                <p className="text-sm text-zinc-500">尚未进行 AI 评估</p>
                <p className="text-xs text-zinc-400">
                  评估流程：后端构造输入快照（Profile + 岗位 + 地区 + Evidence + Hard Filters）→
                  同一份内容发给模型并存档 → 规则引擎计算总分/覆盖度/推荐等级。
                </p>
                {evaluateMutation.isPending && <p className="text-sm">评估中…（约需十几秒）</p>}
                {evaluateMutation.isError && (
                  <div className="max-w-lg rounded-md border border-red-300 bg-red-50 px-4 py-3 text-sm text-red-700 dark:border-red-700 dark:bg-red-900/30 dark:text-red-300">
                    {evaluateMutation.error.message}
                  </div>
                )}
                <Button onClick={() => evaluateMutation.mutate()} disabled={evaluateMutation.isPending}>
                  开始 AI 评估
                </Button>
              </CardContent>
            </Card>
          ) : (
            <div className="grid grid-cols-2 gap-4">
              {evaluateMutation.isError && (
                <div className="col-span-2 rounded-md border border-red-300 bg-red-50 px-4 py-3 text-sm text-red-700 dark:border-red-700 dark:bg-red-900/30 dark:text-red-300">
                  重新评估失败：{evaluateMutation.error.message}
                </div>
              )}
              <Card className="col-span-2">
                <CardHeader className="flex items-center justify-between">
                  <CardTitle>本次评价依据（Evaluation Audit）</CardTitle>
                  <Button size="sm" variant="outline" onClick={() => evaluateMutation.mutate()} disabled={evaluateMutation.isPending}>
                    重新评估
                  </Button>
                </CardHeader>
                <CardContent className="space-y-2 text-xs text-zinc-600 dark:text-zinc-400">
                  <div className="flex flex-wrap gap-x-6 gap-y-1">
                    <span>Provider：{evaluation.provider ?? "—"}</span>
                    <span>模型：{evaluation.model ?? "—"}</span>
                    <span>Prompt：{evaluation.prompt_version ?? "—"}</span>
                    <span>评估时间：{formatDate(evaluation.evaluated_at)}</span>
                    <span>覆盖度：{evaluation.score_coverage ?? "—"}%</span>
                  </div>
                  <div className="flex flex-wrap gap-x-6 gap-y-1 font-mono">
                    <span>profile {evaluation.profile_hash?.slice(0, 12) ?? "—"}</span>
                    <span>scoring {evaluation.scoring_config_hash?.slice(0, 12) ?? "—"}</span>
                    <span>region {evaluation.region_config_hash?.slice(0, 12) ?? "—"}</span>
                  </div>
                  <div>
                    <p className="mt-1 font-medium text-zinc-700 dark:text-zinc-300">使用的 Evidence（{evaluation.evidence_items.length}）：</p>
                    {evaluation.evidence_items.length > 0 ? (
                      <ul className="mt-1 list-disc space-y-1 pl-5">
                        {evaluation.evidence_items.map((ev) => (
                          <li key={ev.id}>
                            <Badge tone={ev.evidence_level === "A" ? "green" : ev.evidence_level === "B" ? "blue" : "zinc"}>
                              {ev.evidence_level}
                            </Badge>{" "}
                            #{ev.id} {ev.claim}
                          </li>
                        ))}
                      </ul>
                    ) : (
                      <p className="mt-1">本次评估没有可用证据（风评维度将以 null 呈现，不猜测）。</p>
                    )}
                  </div>
                </CardContent>
              </Card>
              <Card className="col-span-2">
                <CardHeader className="flex items-center justify-between">
                  <CardTitle>八维评分</CardTitle>
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
                <CardHeader><CardTitle>风险条目（结构化）</CardTitle></CardHeader>
                <CardContent className="space-y-2">
                  {evaluation.risk_items.length > 0
                    ? evaluation.risk_items.map((item, i) => (
                        <div key={i} className="flex flex-wrap items-baseline gap-2 text-sm">
                          <Badge tone={item.severity === "high" || item.severity === "critical" ? "red" : item.severity === "medium" ? "amber" : "zinc"}>
                            {item.severity}
                          </Badge>
                          <span className="font-medium">{item.type}</span>
                          <span className="text-zinc-600 dark:text-zinc-400">{item.reason}</span>
                        </div>
                      ))
                    : <span className="text-sm text-zinc-400">—</span>}
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
          )
        )}

        {tab === "institution" && (
          <div className="space-y-4">
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
            <Card>
              <CardHeader className="flex items-center justify-between">
                <CardTitle>高校岗位专用字段</CardTitle>
                <span className="text-xs text-zinc-400">
                  {job.academic_details ? "" : "尚未填写（PATCH /api/jobs/{id}/academic-details）"}
                </span>
              </CardHeader>
              <CardContent className="grid grid-cols-2 gap-4 py-4 text-sm">
                {job.academic_details
                  ? academicRows(job.academic_details).map(([label, value]) => (
                      <InfoRow key={label} label={label} value={value} />
                    ))
                  : (
                    <p className="col-span-2 text-sm text-zinc-500 dark:text-zinc-400">
                      暂无高校聘用事实。编制、长聘体系、合同期限、经费来源是四个独立维度，
                      可通过 academic-details 接口维护；未填写的字段一律视为「未知 / 待确认」。
                    </p>
                  )}
              </CardContent>
            </Card>
          </div>
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
          <ReputationTab organizationId={job.organization?.id ?? null} />
        )}

        {tab === "evidence" && <EvidenceTab jobId={job.id} />}

        {tab === "application" && (
          applicationQuery.isLoading ? (
            <EmptyState title="加载申请记录中…" />
          ) : applicationQuery.isError ? (
            <Card>
              <div className="px-4 py-6 text-center">
                <p className="text-sm font-medium text-red-600 dark:text-red-400">申请记录加载失败</p>
                <p className="mt-1 text-xs text-zinc-500 dark:text-zinc-400">
                  {applicationQuery.error.message}
                </p>
              </div>
            </Card>
          ) : application ? (
            <Card>
              <CardHeader className="flex items-center justify-between">
                <CardTitle>申请记录</CardTitle>
                <Badge tone={applicationStatusTone(application.status)}>
                  {APPLICATION_STATUS_LABELS[application.status] ?? application.status}
                </Badge>
              </CardHeader>
              <CardContent className="space-y-3 text-sm">
                <div className="grid grid-cols-2 gap-3">
                  <InfoRow label="下一步" value={application.next_action ?? "—"} />
                  <InfoRow label="行动日期" value={formatDate(application.next_action_date)} />
                  <InfoRow label="联系人" value={application.contact ?? "—"} />
                  <InfoRow label="投递时间" value={application.applied_at ? formatDate(application.applied_at) : "未投递"} />
                  <InfoRow label="简历版本" value={application.resume_version ?? "—"} />
                  <InfoRow label="Cover Letter" value={application.cover_letter_version ?? "—"} />
                </div>
                {application.notes && (
                  <p className="whitespace-pre-wrap rounded bg-zinc-50 px-3 py-2 text-xs text-zinc-600 dark:bg-zinc-800/60 dark:text-zinc-300">
                    {application.notes}
                  </p>
                )}
                <div className="flex flex-wrap items-center gap-2 pt-1">
                  <span className="text-xs text-zinc-500">流转到：</span>
                  {application.allowed_next_statuses.map((s) => (
                    <Button
                      key={s}
                      size="sm"
                      variant="outline"
                      disabled={appStatusMutation.isPending}
                      onClick={() => appStatusMutation.mutate({ appId: application.id, status: s })}
                    >
                      {APPLICATION_STATUS_LABELS[s] ?? s}
                    </Button>
                  ))}
                  <Link to="/applications" className="ml-auto text-xs underline">
                    在申请 CRM 中打开 →
                  </Link>
                </div>
                {appStatusMutation.isError && (
                  <p className="text-xs text-red-600 dark:text-red-400">{appStatusMutation.error.message}</p>
                )}
              </CardContent>
            </Card>
          ) : (
            <Card>
              <CardContent className="flex flex-col items-center gap-3 py-10">
                <p className="text-sm text-zinc-500">该岗位还没有进入申请流程</p>
                <p className="text-xs text-zinc-400">
                  创建申请后即可在「申请 CRM」中管理状态流转、下一步行动与面试进度。
                </p>
                {createAppMutation.isError && (
                  <p className="text-xs text-red-600 dark:text-red-400">{createAppMutation.error.message}</p>
                )}
                <Button onClick={() => createAppMutation.mutate()} disabled={createAppMutation.isPending}>
                  创建申请（加入 CRM）
                </Button>
              </CardContent>
            </Card>
          )
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


function unknownIfEmpty(value: string | null | undefined): string {
  return value && value.trim() !== "" ? value : "未知 / 待确认";
}

function boolLabel(value: boolean | null | undefined, yes: string, no: string): string {
  if (value === null || value === undefined) return "未知 / 待确认";
  return value ? yes : no;
}

function academicRows(d: AcademicJobDetails): [string, string][] {
  return [
    ["事业编状态", ESTABLISHMENT_LABELS[d.establishment_status] ?? d.establishment_status],
    ["长聘体系", TENURE_LABELS[d.tenure_status] ?? d.tenure_status],
    ["合同类型", CONTRACT_TYPE_LABELS[d.contract_type] ?? d.contract_type],
    ["经费来源", FUNDING_SOURCE_LABELS[d.funding_source] ?? d.funding_source],
    ["非升即走", boolLabel(d.is_up_or_out, "是", "否")],
    ["合同年限", d.contract_years !== null ? `${d.contract_years} 年` : "未知 / 待确认"],
    ["首聘周期", unknownIfEmpty(d.first_contract_period)],
    ["中期考核", unknownIfEmpty(d.midterm_review)],
    ["聘期考核", unknownIfEmpty(d.final_review)],
    ["论文要求", unknownIfEmpty(d.publication_requirements)],
    ["基金要求", unknownIfEmpty(d.grant_requirements)],
    ["教学要求", unknownIfEmpty(d.teaching_requirements)],
    ["行政要求", unknownIfEmpty(d.admin_requirements)],
    ["启动经费", unknownIfEmpty(d.startup_funding)],
    ["到账方式", unknownIfEmpty(d.startup_funding_terms)],
    ["独立 PI", boolLabel(d.independent_pi, "是", "否")],
    ["硕士招生", boolLabel(d.can_supervise_master, "可", "不可")],
    ["博士招生", boolLabel(d.can_supervise_phd, "可", "不可")],
    ["硕士指标", unknownIfEmpty(d.master_quota)],
    ["博士指标", unknownIfEmpty(d.phd_quota)],
    ["固定收入", unknownIfEmpty(d.fixed_income)],
    ["绩效收入", unknownIfEmpty(d.performance_income)],
    ["安家费", unknownIfEmpty(d.housing_settlement)],
    ["住房补贴", unknownIfEmpty(d.housing_subsidy)],
    ["人才房", unknownIfEmpty(d.talent_housing)],
    ["地方人才补贴", unknownIfEmpty(d.regional_talent_subsidy)],
  ];
}
