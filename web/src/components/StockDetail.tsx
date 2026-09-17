import type { ReactNode } from "react";
import { ChevronDown } from "lucide-react";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Collapsible, CollapsibleContent, CollapsibleTrigger } from "@/components/ui/collapsible";
import { clipNames } from "@/lib/format";
import type { EmBoard, Stock } from "@/lib/types";
import { Pct, StockReasons, VerdictBadge } from "./StockBits";

function BoardGrid({ title, items, showZt = false }: { title: string; items: EmBoard[]; showZt?: boolean }) {
  if (!items.length) return null;
  return (
    <div>
      <div className="mb-1.5 text-[11px] text-muted-foreground">{title}</div>
      <div className="grid grid-cols-2 gap-1.5">
        {items.map((b) => (
          <div key={b.bk || b.name} className="rounded-md bg-muted/50 px-2 py-1.5">
            <div className="flex items-start justify-between gap-2">
              <span className="text-xs font-medium leading-4">{b.name}</span>
              <Pct value={b.pct} />
            </div>
            <div className="mt-0.5 text-[11px] text-muted-foreground">
              {[
                b.level === "industry_l1" ? "一级行业" : b.level === "industry_l2" ? "二级行业" : b.level === "industry_l3" ? "三级行业" : "",
                showZt && b.zt ? `涨停${b.zt}` : "",
              ]
                .filter(Boolean)
                .join(" · ")}
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}

export function StockDetail({ stock, empty }: { stock?: Stock | null; empty?: string }) {
  if (!stock) {
    return <p className="text-sm text-muted-foreground">{empty || "点左边看依据。"}</p>;
  }
  const boards = stock.boards_em || [];
  const hy = boards.filter((b) => b.kind === "industry");
  const region = boards.filter((b) => b.kind === "region");
  const gn = boards.filter((b) => b.kind === "concept" || b.kind === "noise");
  return (
    <Card>
      <CardHeader>
        <div className="flex items-start justify-between gap-3">
          <div>
            <CardTitle className="text-base">
              {stock.name} {stock.code || ""}
            </CardTitle>
            <p className="mt-1 text-xs text-muted-foreground">
              {stock.role || ""}
              {stock.boards != null ? ` · ${stock.boards}板` : ""}
              {stock.y_boards != null ? ` · 昨 ${stock.y_boards} 板` : ""}
              {stock.turnover != null ? ` · 换手 ${stock.turnover}%` : ""}
              {stock.open_times != null ? ` · 开板 ${stock.open_times}` : ""}
              {stock.first_seal ? ` · 封板 ${stock.first_seal}` : ""}
              {stock.float_mv_yi != null ? ` · 流通 ${stock.float_mv_yi} 亿` : ""}
            </p>
          </div>
          <VerdictBadge value={stock.verdict} />
        </div>
      </CardHeader>
      <CardContent className="space-y-3 text-sm">
        <p className="text-muted-foreground">
          题材 <span className="font-medium text-foreground">{stock.theme || stock.industry || "—"}</span>
          {stock.theme_count != null ? ` · ${stock.theme_count} 只${stock.clustered ? "成群" : "未成群"}` : ""}
          {stock.vane ? ` · 风向标 ${stock.vane}` : ""}
          {stock.army ? ` · 中军 ${stock.army}` : ""}
        </p>
        <BoardGrid title="所属行业" items={hy} />
        <BoardGrid title="地区" items={region} />
        <BoardGrid title="所属概念" items={gn} showZt />
        {stock.peers?.length ? <p className="text-muted-foreground">同涨 {clipNames(stock.peers, 6)}</p> : null}
        {stock.watch_note ? <p>{stock.name}：{stock.watch_note}</p> : null}
        {stock.action ? <p>{stock.action}</p> : null}
        <StockReasons stock={stock} />
      </CardContent>
    </Card>
  );
}

export function Fold({ title, children, defaultOpen = false }: { title: string; children: ReactNode; defaultOpen?: boolean }) {
  return (
    <Collapsible defaultOpen={defaultOpen} className="rounded-xl border bg-card">
      <CollapsibleTrigger className="flex h-10 w-full items-center justify-between px-4 text-[13px] font-medium leading-none">
        {title}
        <ChevronDown className="h-4 w-4 text-muted-foreground" />
      </CollapsibleTrigger>
      <CollapsibleContent className="border-t px-4 py-3">{children}</CollapsibleContent>
    </Collapsible>
  );
}
