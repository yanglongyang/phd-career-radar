/* V0.3 → V0.3.2 sector：来源/单位性质分类的展示派生（纯函数，便于单测）。
   医院（hospital）是独立 sector：大学附属医院招聘主体是医院 → hospital，
   不归入 university。 */

export const SECTOR_LABELS: Record<string, string> = {
  university: "高校",
  hospital: "医院",
  state_owned: "央国企",
  enterprise: "企业",
  mixed: "混合",
  other: "其他",
};

export function sectorLabel(sector: string | null | undefined): string {
  return (sector && SECTOR_LABELS[sector]) || "其他";
}

export function sectorTone(sector: string | null | undefined) {
  switch (sector) {
    case "university":
      return "blue" as const;
    case "hospital":
      return "green" as const;
    case "state_owned":
      return "red" as const;
    case "enterprise":
      return "amber" as const;
    case "mixed":
      return "orange" as const;
    default:
      return "zinc" as const;
  }
}

/* Inbox 顶部主分类 tabs。key 直接作为 ?sector= 参数：
   全部 -> 不传；"其他" -> other,mixed（后端支持逗号列表 in_ 查询）。 */
export const SECTOR_TABS: { key: string; label: string }[] = [
  { key: "", label: "全部" },
  { key: "university", label: "高校" },
  { key: "hospital", label: "医院" },
  { key: "state_owned", label: "央国企" },
  { key: "enterprise", label: "企业" },
  { key: "other,mixed", label: "其他" },
];

export function sectorQueryForTab(tab: string): string | undefined {
  return tab || undefined;
}

/* 运行结果按 sector 分组（前端 presentation grouping，不改事务/统计语义）。
   顺序固定：高校 → 医院 → 央国企 → 企业 → 混合 → 其他；未知 sector 归入其他。 */
export function groupRunItemsBySector<T extends { sector?: string | null }>(
  items: T[],
): { sector: string; items: T[] }[] {
  const order = ["university", "hospital", "state_owned", "enterprise", "mixed", "other"];
  const groups = new Map<string, T[]>();
  for (const item of items) {
    const key = item.sector && SECTOR_LABELS[item.sector] ? item.sector : "other";
    if (!groups.has(key)) groups.set(key, []);
    groups.get(key)!.push(item);
  }
  return order
    .filter((sector) => groups.has(sector))
    .map((sector) => ({ sector, items: groups.get(sector)! }));
}
