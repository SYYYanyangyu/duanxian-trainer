export function chgText(v: number | null | undefined) {
  if (v == null || Number.isNaN(Number(v))) return "—";
  const n = Number(v);
  return `${n > 0 ? "+" : ""}${n.toFixed(1)}%`;
}

export function chgClass(v: number | null | undefined) {
  if (v == null) return "text-muted-foreground";
  if (v > 0) return "text-up";
  if (v < 0) return "text-down";
  return "text-muted-foreground";
}

export function pctRate(v: number | null | undefined) {
  if (v == null) return "—";
  return `${Math.round(Number(v) * 100)}%`;
}

export function clipNames(list: string[] | undefined, n: number) {
  const arr = list || [];
  if (!arr.length) return "—";
  if (arr.length <= n) return arr.join("、");
  return `${arr.slice(0, n).join("、")} 等${arr.length}只`;
}

export function yuan(n: number | null | undefined) {
  if (n == null || Number.isNaN(Number(n))) return "—";
  return `${Math.round(Number(n)).toLocaleString("zh-CN")} 元`;
}

export function signedYuan(n: number | null | undefined) {
  if (n == null || Number.isNaN(Number(n))) return "—";
  const v = Math.round(Number(n));
  return `${v > 0 ? "+" : ""}${v.toLocaleString("zh-CN")} 元`;
}

export function pad2(n: number) {
  return String(n).padStart(2, "0");
}

export function formatLiveTime(d: Date) {
  const week = "日一二三四五六";
  return `${d.getFullYear()}-${pad2(d.getMonth() + 1)}-${pad2(d.getDate())} 周${week[d.getDay()]} ${pad2(d.getHours())}:${pad2(d.getMinutes())}:${pad2(d.getSeconds())}`;
}

export function verdictVariant(v?: string) {
  if (v === "盯" || v === "做") return "watch" as const;
  if (v === "躲") return "hide" as const;
  if (v === "核按钮") return "up" as const;
  return "secondary" as const;
}
