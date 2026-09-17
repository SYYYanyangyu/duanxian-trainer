import { Badge } from "@/components/ui/badge";
import { chgClass, chgText, verdictVariant } from "@/lib/format";
import type { Stock } from "@/lib/types";

export function StockReasons({ stock }: { stock?: Stock | null }) {
  if (!stock?.reasons?.length) return null;
  return (
    <ul className="mt-3 space-y-1.5 text-sm">
      {stock.reasons.map((r, i) => (
        <li
          key={i}
          className={
            r.tone === "good"
              ? "text-down"
              : r.tone === "bad"
                ? "text-up"
                : "text-muted-foreground"
          }
        >
          {r.text}
        </li>
      ))}
    </ul>
  );
}

export function Pct({ value }: { value: number | null | undefined }) {
  return <span className={chgClass(value)}>{chgText(value)}</span>;
}

export function VerdictBadge({ value }: { value?: string }) {
  return <Badge variant={verdictVariant(value)}>{value || "观察"}</Badge>;
}
