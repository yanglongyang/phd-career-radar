import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useEffect, useState } from "react";
import { getSettings, reEvaluateAll, updateSettings } from "../services/api";
import type { SettingsData } from "../types";
import { Badge, Button, Card, CardContent, CardHeader, CardTitle, Field, Input, PageHeader } from "../components/ui";

/* 设置页（Phase 7）：可视化编辑 config/*.yaml —— 评分权重 / 地区偏好 / Hard Filters。
   保存后立即生效（配置仍以 YAML 文件为事实源）；保存前自动备份 .bak。 */

const DIMENSION_LABELS: Record<string, string> = {
  fit: "岗位与个人匹配度",
  career_stability: "岗位性质与稳定性",
  research_resources: "科研平台与资源",
  region: "地区",
  compensation: "待遇",
  reputation: "风评与组织环境",
  workload: "教学与行政负担",
  long_term: "长期发展潜力",
};

const REGION_TIERS = ["preferred", "acceptable", "neutral", "avoid"] as const;
const TIER_LABELS: Record<string, string> = {
  preferred: "优先（基准 90）",
  acceptable: "可接受（基准 70）",
  neutral: "中立（基准 50）",
  avoid: "回避（基准 20）",
};

export default function SettingsPage() {
  const queryClient = useQueryClient();
  const [weights, setWeights] = useState<Record<string, string>>({});
  const [regions, setRegions] = useState<Record<string, string>>({ preferred: "", acceptable: "", neutral: "", avoid: "" });
  const [minSalary, setMinSalary] = useState("");
  const [rejectPi, setRejectPi] = useState(false);
  const [rejectPostdoc, setRejectPostdoc] = useState(false);
  const [rejectRiskTrack, setRejectRiskTrack] = useState(false);
  const [message, setMessage] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loaded, setLoaded] = useState(false);

  const { data: settings, isError } = useQuery<SettingsData>({
    queryKey: ["settings"],
    queryFn: getSettings,
  });

  // 数据到达后初始化表单（只执行一次；保存后 invalidate 会刷新 data）
  useEffect(() => {
    if (!settings || loaded) return;
    const w: Record<string, string> = {};
    for (const [k, v] of Object.entries(settings["scoring.yaml"].scoring ?? {})) {
      w[k] = String(v);
    }
    setWeights(w);
    const r: Record<string, string> = {};
    for (const tier of REGION_TIERS) r[tier] = (settings["regions.yaml"][tier] ?? []).join("，");
    setRegions(r);
    const hf = settings["profile.yaml"].hard_filters ?? {};
    setMinSalary(hf.minimum_salary == null ? "" : String(hf.minimum_salary));
    setRejectPi(Boolean(hf.reject_pi_funded));
    setRejectPostdoc(Boolean(hf.reject_postdoc));
    setRejectRiskTrack(Boolean(hf.reject_high_risk_tenure_track));
    setLoaded(true);
  }, [settings, loaded]);

  const saveMutation = useMutation({
    mutationFn: () => {
      const scoring: Record<string, number> = {};
      for (const [k, v] of Object.entries(weights)) {
        const n = Number(v);
        if (Number.isFinite(n)) scoring[k] = n;
      }
      const regionsYaml: Record<string, string[]> = {};
      for (const tier of REGION_TIERS) {
        regionsYaml[tier] = (regions[tier] ?? "")
          .split(/[，,、]/)
          .map((s) => s.trim())
          .filter(Boolean);
      }
      return updateSettings({
        scoring_yaml: { ...settings!["scoring.yaml"], scoring },
        regions_yaml: { ...settings!["regions.yaml"], ...regionsYaml },  // 保留 city_details,
        profile_yaml: {
          ...settings!["profile.yaml"],
          hard_filters: {
            ...settings!["profile.yaml"].hard_filters,
            minimum_salary: minSalary === "" ? null : Number(minSalary),
            reject_pi_funded: rejectPi,
            reject_postdoc: rejectPostdoc,
            reject_high_risk_tenure_track: rejectRiskTrack,
          },
        },
      });
    },
    onSuccess: () => {
      // 不重置 loaded：本地表单即刚保存的值，只失效 backing query 刷新后台数据
      setMessage("已保存并立即生效（原文件备份为 .bak；注释会被重写丢弃）");
      setError(null);
      queryClient.invalidateQueries({ queryKey: ["settings"] });
    },
    onError: (err) => {
      setError(err.message);
      setMessage(null);
    },
  });

  const reEvalMutation = useMutation({
    mutationFn: reEvaluateAll,
    onSuccess: (r) => {
      setMessage(
        `批量重评完成：共 ${r.total} 个岗位，成功 ${r.succeeded.length}，失败 ${r.failed.length}` +
          (r.failed.length ? `（首个失败：${r.failed[0].error.slice(0, 80)}）` : ""),
      );
      setError(null);
      queryClient.invalidateQueries({ queryKey: ["jobs"] });
      queryClient.invalidateQueries({ queryKey: ["dashboard"] });
    },
    onError: (err) => setError(err.message),
  });

  const weightSum = Object.values(weights).reduce((sum, v) => sum + (Number(v) || 0), 0);

  return (
    <div className="max-w-3xl space-y-4">
      <PageHeader
        title="设置"
        subtitle="配置以 config/*.yaml 为事实源：这里编辑并保存后立即生效，无需重启。"
      />

      {isError && (
        <div className="rounded-md border border-red-300 bg-red-50 px-4 py-3 text-sm text-red-700 dark:border-red-700 dark:bg-red-900/30 dark:text-red-300">
          设置加载失败
        </div>
      )}
      {message && (
        <div className="rounded-md border border-emerald-300 bg-emerald-50 px-4 py-3 text-sm text-emerald-700 dark:border-emerald-700 dark:bg-emerald-900/30 dark:text-emerald-300">
          {message}
        </div>
      )}
      {error && (
        <div className="rounded-md border border-red-300 bg-red-50 px-4 py-3 text-sm text-red-700 dark:border-red-700 dark:bg-red-900/30 dark:text-red-300">
          {error}
        </div>
      )}

      <Card>
        <CardHeader className="flex items-center justify-between">
          <CardTitle>评分权重（合计必须为 100）</CardTitle>
          <Badge tone={weightSum === 100 ? "green" : "red"}>当前合计 {weightSum}</Badge>
        </CardHeader>
        <CardContent className="grid grid-cols-2 gap-4 py-4">
          {Object.entries(DIMENSION_LABELS).map(([key, label]) => (
            <Field key={key} label={label}>
              <Input
                type="number"
                value={weights[key] ?? ""}
                onChange={(e) => setWeights((w) => ({ ...w, [key]: e.target.value }))}
              />
            </Field>
          ))}
        </CardContent>
      </Card>

      <Card>
        <CardHeader><CardTitle>地区偏好（逗号或顿号分隔城市/省份）</CardTitle></CardHeader>
        <CardContent className="grid grid-cols-2 gap-4 py-4">
          {REGION_TIERS.map((tier) => (
            <Field key={tier} label={TIER_LABELS[tier]}>
              <Input
                value={regions[tier] ?? ""}
                onChange={(e) => setRegions((r) => ({ ...r, [tier]: e.target.value }))}
              />
            </Field>
          ))}
          <div className="col-span-2 text-xs text-zinc-400">
            未出现在任何层级的地区 = unrated → 评分为空，不替用户猜测。
          </div>
        </CardContent>
      </Card>

      <Card>
        <CardHeader><CardTitle>Hard Filters（触发即推荐等级 X）</CardTitle></CardHeader>
        <CardContent className="space-y-3 py-4 text-sm">
          <Field label="最低薪资（CNY 万元/年，单位不明时不触发）">
            <Input
              type="number"
              value={minSalary}
              onChange={(e) => setMinSalary(e.target.value)}
            />
          </Field>
          <label className="flex items-center gap-2">
            <input type="checkbox" checked={rejectPi} onChange={(e) => setRejectPi(e.target.checked)} />
            排除 PI 经费聘用岗位
          </label>
          <label className="flex items-center gap-2">
            <input type="checkbox" checked={rejectPostdoc} onChange={(e) => setRejectPostdoc(e.target.checked)} />
            排除博士后岗位
          </label>
          <label className="flex items-center gap-2">
            <input type="checkbox" checked={rejectRiskTrack} onChange={(e) => setRejectRiskTrack(e.target.checked)} />
            排除高风险预聘（非升即走）岗位
          </label>
        </CardContent>
      </Card>

      <div className="flex flex-wrap items-center gap-3">
        <Button onClick={() => saveMutation.mutate()} disabled={saveMutation.isPending || weightSum !== 100}>
          {saveMutation.isPending ? "保存中…" : "保存配置"}
        </Button>
        <Button
          variant="outline"
          onClick={() => reEvalMutation.mutate()}
          disabled={reEvalMutation.isPending}
        >
          {reEvalMutation.isPending ? "批量重评中…（需 AI 配置）" : "用当前配置重新评估全部岗位"}
        </Button>
      </div>
    </div>
  );
}
