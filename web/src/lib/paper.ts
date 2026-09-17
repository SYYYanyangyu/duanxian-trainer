import type { Actor } from "./types";

export const ROLE_ORDER = [
  { id: "rules", name: "纪律派" },
  { id: "chase", name: "补涨派" },
  { id: "cash", name: "空仓派" },
  { id: "ai", name: "大模型" },
] as const;

export function findActor(actors: Actor[] | undefined, id: string) {
  return (actors || []).find((a) => a.id === id);
}

export function actorTitle(actor?: Actor, fallback = "—") {
  if (!actor) return fallback;
  if (actor.id === "ai") return actor.name || "大模型";
  return actor.name || fallback;
}

export function betItems(actor?: Actor) {
  const bets = actor?.bets || [];
  if (!bets.length) return [{ side: "", name: "无标的" }];
  return bets.map((b) => ({ side: (b.side || "").trim(), name: (b.name || "").trim() })).filter((b) => b.side || b.name);
}

export function betLines(actor?: Actor) {
  return betItems(actor).map((b) => [b.side, b.name].filter(Boolean).join(" "));
}

export function pnlText(actor?: Actor, settled?: boolean) {
  if (!actor) return "—";
  const done = actor.settled || settled;
  if (!done) return "未结算";
  if (actor.pnl_yuan != null && !Number.isNaN(Number(actor.pnl_yuan))) {
    const n = Number(actor.pnl_yuan);
    return `${n > 0 ? "+" : ""}${Math.round(n).toLocaleString("zh-CN")} 元`;
  }
  if (actor.pnl == null) return "0 元";
  const n = Math.round(Number(actor.pnl) * 1000);
  return `${n > 0 ? "+" : ""}${n.toLocaleString("zh-CN")} 元`;
}
