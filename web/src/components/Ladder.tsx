import { ChevronDown } from "lucide-react";
import { Collapsible, CollapsibleContent, CollapsibleTrigger } from "@/components/ui/collapsible";
import { Button } from "@/components/ui/button";
import { cn } from "@/lib/utils";
import type { Stock } from "@/lib/types";

export function Ladder({
  ladder,
  selected,
  onSelect,
}: {
  ladder: { boards: number; stocks: Stock[] }[];
  selected?: string | null;
  onSelect: (code: string) => void;
}) {
  return (
    <div className="grid auto-cols-[minmax(9.5rem,1fr)] grid-flow-col gap-2 overflow-x-auto pb-1">
      {ladder.map((col) => {
        const isOne = col.boards === 1;
        const list = (
          <div className="max-h-72 space-y-1 overflow-y-auto pr-0.5">
            {col.stocks.map((s) => (
              <button
                key={s.code}
                type="button"
                onClick={() => s.code && onSelect(s.code)}
                className={cn(
                  "flex h-8 w-full items-center justify-between rounded-md border px-2 text-left text-[13px] leading-none transition-colors",
                  selected === s.code ? "border-primary bg-accent" : "border-transparent bg-muted/60 hover:bg-muted",
                  s.verdict === "躲" && selected !== s.code && "opacity-70",
                )}
                title={s.theme || s.industry || ""}
              >
                <span className="truncate font-medium leading-none">{s.name}</span>
                <span className="ml-2 shrink-0 text-[11px] leading-none text-muted-foreground">{s.verdict || ""}</span>
              </button>
            ))}
          </div>
        );
        return (
          <div key={col.boards} className="min-w-[9.5rem] rounded-lg border bg-card p-2">
            <div className="mb-2 flex h-5 items-center text-[12px] leading-none text-muted-foreground">
              {col.boards}板 · {col.stocks.length}
            </div>
            {isOne ? (
              <Collapsible defaultOpen={false}>
                <CollapsibleTrigger asChild>
                  <Button variant="ghost" size="sm" className="h-7 w-full text-xs text-muted-foreground">
                    首板 {col.stocks.length} 只
                    <ChevronDown className="h-3 w-3" />
                  </Button>
                </CollapsibleTrigger>
                <CollapsibleContent>{list}</CollapsibleContent>
              </Collapsible>
            ) : (
              list
            )}
          </div>
        );
      })}
    </div>
  );
}
