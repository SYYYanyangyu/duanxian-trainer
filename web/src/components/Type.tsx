import type { ReactNode } from "react";
import { cn } from "@/lib/utils";
import { betItems, pnlText } from "@/lib/paper";
import type { Actor } from "@/lib/types";

export function SectionTitle({ children, extra }: { children: ReactNode; extra?: ReactNode }) {
  return (
    <div className="flex min-h-8 items-start justify-between gap-3">
      <h2 className="shrink-0 pt-1 text-[13px] font-semibold leading-none tracking-tight">{children}</h2>
      {extra ? <div className="max-w-[78%] text-right text-xs leading-5 text-muted-foreground">{extra}</div> : null}
    </div>
  );
}

export function StatusChip({
  children,
  tone = "muted",
}: {
  children: ReactNode;
  tone?: "muted" | "up" | "down";
}) {
  return (
    <span
      className={cn(
        "inline-flex h-5 shrink-0 items-center rounded px-1.5 text-[11px] font-medium leading-none",
        tone === "muted" && "bg-muted text-muted-foreground",
        tone === "up" && "bg-red-50 text-up",
        tone === "down" && "bg-emerald-50 text-down",
      )}
    >
      {children}
    </span>
  );
}

export function BetLine({ side, name }: { side?: string; name?: string }) {
  const empty = !side && (!name || name === "无标的");
  return (
    <div className="flex h-6 items-center gap-2 text-[13px] leading-none">
      <span className="w-[3.25rem] shrink-0 text-muted-foreground">{side || (empty ? "" : "—")}</span>
      <span className={cn("min-w-0 truncate", empty ? "text-muted-foreground" : "font-medium")}>
        {name || "无标的"}
      </span>
    </div>
  );
}

export function SettleChip({ actor, settled }: { actor?: Actor; settled?: boolean }) {
  const text = pnlText(actor, settled);
  const done = Boolean(actor?.settled || settled);
  const n = Number(actor?.pnl_yuan ?? actor?.pnl ?? 0);
  const tone = !done ? "muted" : n > 0 ? "up" : n < 0 ? "down" : "muted";
  return <StatusChip tone={tone}>{text}</StatusChip>;
}

export function ActorBets({ actor }: { actor?: Actor }) {
  return (
    <div className="space-y-0.5">
      {betItems(actor).map((b, i) => (
        <BetLine key={`${b.side}-${b.name}-${i}`} side={b.side} name={b.name} />
      ))}
    </div>
  );
}
