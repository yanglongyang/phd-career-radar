import { Card, CardContent, CardHeader, CardTitle, PageHeader } from "../components/ui";

const CONFIG_FILES = [
  { name: "config/profile.yaml", desc: "研究方向、技能、Hard Filters（触发即推荐等级 X）" },
  { name: "config/scoring.yaml", desc: "8 维评分权重、推荐等级阈值与封顶规则、地区子权重" },
  { name: "config/regions.yaml", desc: "地区偏好分层（preferred / acceptable / neutral / avoid）" },
  { name: "config/sources.yaml", desc: "未来 Collector 来源配置（V0.1 未启用）" },
];

export default function SettingsPage() {
  return (
    <div className="max-w-3xl">
      <PageHeader
        title="设置"
        subtitle="V0.1 阶段通过 YAML 配置文件管理偏好；可视化设置页将在 Phase 7 提供。"
      />

      <Card>
        <CardHeader><CardTitle>配置文件（修改后立即生效，无需重启）</CardTitle></CardHeader>
        <CardContent className="space-y-3">
          {CONFIG_FILES.map((f) => (
            <div key={f.name} className="flex items-baseline gap-3 text-sm">
              <code className="rounded bg-zinc-100 px-2 py-0.5 text-xs dark:bg-zinc-800">{f.name}</code>
              <span className="text-zinc-600 dark:text-zinc-400">{f.desc}</span>
            </div>
          ))}
        </CardContent>
      </Card>

      <Card className="mt-4">
        <CardHeader><CardTitle>AI Provider</CardTitle></CardHeader>
        <CardContent className="space-y-2 text-sm text-zinc-600 dark:text-zinc-400">
          <p>
            通过项目根目录 <code className="rounded bg-zinc-100 px-1.5 py-0.5 text-xs dark:bg-zinc-800">.env</code>{" "}
            配置（参考 <code className="rounded bg-zinc-100 px-1.5 py-0.5 text-xs dark:bg-zinc-800">.env.example</code>）：
            <code className="ml-1 rounded bg-zinc-100 px-1.5 py-0.5 text-xs dark:bg-zinc-800">LLM_PROVIDER / LLM_API_KEY / LLM_BASE_URL / LLM_MODEL</code>。
          </p>
          <p>
            未配置 AI 时，手工功能全部可用；AI 解析与评估会明确提示未配置，<b>不会伪造评估结果</b>。
            支持任何 OpenAI-compatible API。
          </p>
        </CardContent>
      </Card>

      <Card className="mt-4">
        <CardHeader><CardTitle>即将提供（Roadmap）</CardTitle></CardHeader>
        <CardContent>
          <ul className="list-disc space-y-1 pl-5 text-sm text-zinc-600 dark:text-zinc-400">
            <li>Phase 4：修改评分权重 / 地区偏好后一键重新评估岗位</li>
            <li>Phase 6：Evidence 证据管理与风评聚合设置</li>
            <li>Phase 7：设置页面可视化编辑全部配置</li>
          </ul>
        </CardContent>
      </Card>
    </div>
  );
}
