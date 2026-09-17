import { ChevronDown, Sparkles } from "lucide-react";
import { Alert } from "@/components/ui/alert";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { Collapsible, CollapsibleContent, CollapsibleTrigger } from "@/components/ui/collapsible";
import { cn } from "@/lib/utils";
import type { LiveData } from "@/lib/types";

export function AiPick({
  data,
  selected,
  loading,
  extra,
  onSelect,
  onRun,
}: {
  data: LiveData;
  selected?: string | null;
  loading: boolean;
  extra?: string;
  onSelect: (code: string) => void;
  onRun: () => void;
}) {
  const ai = data.ai || {};
  const watch = ai.watch || [];
  const avoid = ai.avoid || [];
  const auc = data.auction || {};
  const failed = ai.stance === "调用失败" || ai.stance === "未接入";
  const waiting = !ai.stance || ai.stance === "待选股";
  const sid = data.session?.id;
  const label = loading
    ? sid === "auction"
      ? "正在拉竞价并让AI决策…"
      : "AI选股中…"
    : sid === "auction"
      ? "拉竞价并让AI决策"
      : "让AI选股";
  const aucLine = auc.as_of
    ? `东财竞价 ${auc.stage || ""} · 报价 ${auc.as_of} · 已报价 ${auc.filled || 0} 只`
    : "点按钮会先拉东财实时报价，再让模型决策。";

  return (
    <Card className={cn(failed && "border-destructive/40")}>
      <CardContent className="space-y-3 p-5">
        <div className="flex items-start justify-between gap-4">
          <div className="min-w-0 flex-1 space-y-2">
            <div className="flex h-5 items-center gap-1.5 text-xs leading-none text-muted-foreground">
              <Sparkles className="h-3.5 w-3.5 shrink-0" />
              <span className="truncate">
                AI选股 · {ai.model || "deepseek-v4-pro"} · {ai.note || "纸上选股，不是下单"}
              </span>
            </div>
            <div className="text-[15px] font-semibold leading-6">{ai.stance || "还没让模型选股"}</div>
            <p className="text-[13px] leading-5 text-muted-foreground">
              {ai.plan || extra || "规则机只打标签。点右边，让模型按龙头思路出名单。"}
            </p>
            <p className="text-xs leading-none text-muted-foreground">{aucLine}</p>
          </div>
          <Button onClick={onRun} disabled={loading} className="mt-0.5 shrink-0">
            {label}
          </Button>
        </div>
        {watch.length ? (
          <div className="flex flex-wrap gap-2">
            {watch.map((w) => (
              <button
                key={w.code || w.name}
                type="button"
                onClick={() => w.code && onSelect(w.code)}
                className={cn(
                  "max-w-sm rounded-md border px-3 py-2 text-left transition-colors",
                  selected === w.code ? "border-primary bg-accent" : "border-border/70 bg-card hover:bg-accent",
                  w.side === "盯" && "border-watch/60",
                )}
              >
                <div className="flex h-5 items-center gap-2">
                  <span className="text-[13px] font-medium leading-none">{w.name}</span>
                  <Badge variant={w.side === "盯" ? "watch" : "secondary"}>{w.side || ""}</Badge>
                </div>
                {w.why ? <p className="mt-1.5 text-xs leading-5 text-muted-foreground">{w.why}</p> : null}
              </button>
            ))}
          </div>
        ) : (
          <p className="text-[13px] leading-5 text-muted-foreground">
            {loading ? "正在拉东财报价并交给模型…" : waiting ? "还没有进攻名单。" : "这轮模型没有进攻标的。"}
          </p>
        )}
        {avoid.length ? (
          <p className="text-xs leading-5 text-muted-foreground">躲：{avoid.map((a) => a.name).join("、")}</p>
        ) : null}
        {ai.think ? (
          <Collapsible>
            <CollapsibleTrigger className="flex h-5 items-center gap-1 text-xs leading-none text-muted-foreground hover:text-foreground">
              AI推理 <ChevronDown className="h-3 w-3" />
            </CollapsibleTrigger>
            <CollapsibleContent>
              <Alert className="mt-2 whitespace-pre-wrap text-xs leading-5 text-muted-foreground">{ai.think}</Alert>
            </CollapsibleContent>
          </Collapsible>
        ) : null}
      </CardContent>
    </Card>
  );
}
