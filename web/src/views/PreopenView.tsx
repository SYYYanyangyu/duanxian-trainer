import { useEffect, useState } from "react";
import { AiPick } from "@/components/AiPick";
import { HistoryTable } from "@/components/HistoryTable";
import { PaperDesk } from "@/components/PaperDesk";
import { Fold, StockDetail } from "@/components/StockDetail";
import { Pct } from "@/components/StockBits";
import { SectionTitle } from "@/components/Type";
import { Card, CardContent } from "@/components/ui/card";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { chgText, pctRate } from "@/lib/format";
import { stepState, type Session } from "@/lib/session";
import { cn } from "@/lib/utils";
import type { LiveData } from "@/lib/types";

const STEPS = [
  ["915", "9:15", "只看昨 2 板以上"],
  ["920", "9:20", "看高开还是低开"],
  ["925", "9:25", "定档今日龙候选"],
  ["930", "9:30", "切开盘后看封板"],
] as const;

function AuctionSteps() {
  const [, setTick] = useState(0);
  useEffect(() => {
    const id = window.setInterval(() => setTick((n) => n + 1), 1000);
    return () => window.clearInterval(id);
  }, []);
  return (
    <div className="grid gap-2 sm:grid-cols-4">
      {STEPS.map(([id, time, text]) => {
        const st = stepState(id);
        return (
          <div
            key={id}
            className={cn(
              "desk-panel px-3 py-2.5",
              st === "now" && "border-primary bg-accent shadow-panel",
              st === "done" && "opacity-55",
            )}
          >
            <div className="text-sm font-semibold">{time}</div>
            <div className="text-xs text-muted-foreground">{text}</div>
          </div>
        );
      })}
    </div>
  );
}

function AuctionView({
  data,
  selected,
  aiLoading,
  onSelect,
  onRunAi,
}: {
  data: LiveData;
  selected?: string | null;
  aiLoading: boolean;
  onSelect: (code: string) => void;
  onRunAi: () => void;
}) {
  const y = data.yesterday || {};
  const rows = y.preopen || [];
  const auc = data.auction || {};
  const paper = data.paper || {};
  const selectedStock = rows.find((x) => x.code === selected) || rows[0] || null;
  return (
    <div className="space-y-4">
      <AiPick
        data={data}
        selected={selected}
        loading={aiLoading}
        extra={data.tomorrow?.plan || "看昨天涨停今天怎么开。点按钮会先拉东财竞价，再让模型拍板。"}
        onSelect={onSelect}
        onRun={onRunAi}
      />
      <PaperDesk note={paper.note} scoreboard={paper.scoreboard} actors={paper.today?.actors} />
      <AuctionSteps />
      <div className="grid gap-4 xl:grid-cols-[minmax(0,1.5fr)_minmax(20rem,1fr)]">
        <section className="space-y-2">
          <SectionTitle extra={auc.as_of ? `报价 ${auc.as_of}` : "还没拉到今开"}>昨日涨停 · 竞价/今开</SectionTitle>
          <div className="desk-panel">
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>名称</TableHead>
                <TableHead>昨板</TableHead>
                <TableHead>今开</TableHead>
                <TableHead>匹配/现涨</TableHead>
                <TableHead>判定</TableHead>
                <TableHead>级别</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {rows.map((st) => {
                const match = st.match_pct != null ? st.match_pct : st.today_pct;
                const flag = (auc.rows || []).find((x) => x.code === st.code);
                return (
                  <TableRow
                    key={st.code}
                    className={cn("cursor-pointer", selected === st.code && "bg-accent")}
                    onClick={() => st.code && onSelect(st.code)}
                  >
                    <TableCell className="font-medium">{st.name}</TableCell>
                    <TableCell>{st.y_boards}</TableCell>
                    <TableCell>
                      <Pct value={st.open_pct} />
                    </TableCell>
                    <TableCell>
                      <Pct value={match} />
                    </TableCell>
                    <TableCell>{flag?.flag || st.result || "—"}</TableCell>
                    <TableCell>{st.watch_level || ""}</TableCell>
                  </TableRow>
                );
              })}
            </TableBody>
          </Table>
          </div>
        </section>
        <section className="space-y-3">
          <SectionTitle>点中的依据</SectionTitle>
          <StockDetail stock={selectedStock} empty="点左边表格。" />
          <Card>
            <CardContent className="space-y-3 p-4 text-sm">
              <div>
                <p className="text-xs text-muted-foreground">高开 ≥5%</p>
                <p>
                  {(y.auction_strong || []).length
                    ? (y.auction_strong || []).map((x) => `${x.name} ${chgText(x.open_pct)}`).join("、")
                    : "暂无"}
                </p>
              </div>
              <div>
                <p className="text-xs text-muted-foreground">低开</p>
                <p>
                  {(y.auction_weak || []).length
                    ? (y.auction_weak || []).map((x) => `${x.name} ${chgText(x.open_pct)}`).join("、")
                    : "暂无"}
                </p>
              </div>
            </CardContent>
          </Card>
        </section>
      </div>
      <HistoryTable history={paper.history} />
    </div>
  );
}

function CloseView({
  data,
  selected,
  aiLoading,
  onSelect,
  onRunAi,
}: {
  data: LiveData;
  selected?: string | null;
  aiLoading: boolean;
  onSelect: (code: string) => void;
  onRunAi: () => void;
}) {
  const y = data.yesterday || {};
  const rows = y.preopen || [];
  const watch = data.morning_watch || [];
  const paper = data.paper || {};
  const selectedStock =
    watch.find((x) => x.code === selected) || rows.find((x) => x.code === selected) || watch[0] || null;

  return (
    <div className="space-y-4">
      <AiPick
        data={data}
        selected={selected}
        loading={aiLoading}
        extra={data.tomorrow?.plan || "用今天的连板做明天竞价名单。"}
        onSelect={onSelect}
        onRun={onRunAi}
      />
      <PaperDesk note={paper.note} scoreboard={paper.scoreboard} actors={paper.today?.actors} />
      <div className="grid gap-4 xl:grid-cols-[minmax(0,1.6fr)_minmax(18rem,0.9fr)]">
        <section className="space-y-2">
          <SectionTitle extra="用今天连板做明早竞价名单">明早竞价名单</SectionTitle>
          <div className="desk-panel">
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>名称</TableHead>
                <TableHead>今板</TableHead>
                <TableHead>涨幅</TableHead>
                <TableHead>换手</TableHead>
                <TableHead>开板</TableHead>
                <TableHead>题材</TableHead>
                <TableHead>角色</TableHead>
                <TableHead>明早</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {watch.map((st) => (
                <TableRow
                  key={st.code}
                  className={cn("cursor-pointer", selected === st.code && "bg-accent")}
                  onClick={() => st.code && onSelect(st.code)}
                >
                  <TableCell className="font-medium">{st.name}</TableCell>
                  <TableCell>{st.boards}</TableCell>
                  <TableCell>
                    <Pct value={st.pct} />
                  </TableCell>
                  <TableCell>{st.turnover}%</TableCell>
                  <TableCell>{st.open_times}</TableCell>
                  <TableCell>{st.theme || ""}</TableCell>
                  <TableCell>{st.role || ""}</TableCell>
                  <TableCell>{st.verdict || ""}</TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
          </div>
        </section>
        <section className="space-y-2">
          <SectionTitle>点中的依据</SectionTitle>
          <StockDetail stock={selectedStock} empty="点左边名单。" />
        </section>
      </div>
      <Fold title="今日结算 · 昨天涨停今天去向">
        <p className="mb-3 text-xs text-muted-foreground">
          晋级 {y.promoted_n || 0}/{y.count || 0}（{pctRate(y.rate)}）。这是复盘，不是明早名单。
        </p>
        <Table>
          <TableHeader>
            <TableRow>
              <TableHead>名称</TableHead>
              <TableHead>昨板</TableHead>
              <TableHead>今开</TableHead>
              <TableHead>收盘涨幅</TableHead>
              <TableHead>结果</TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {rows.map((st) => (
              <TableRow
                key={st.code}
                className={cn("cursor-pointer", selected === st.code && "bg-accent")}
                onClick={() => st.code && onSelect(st.code)}
              >
                <TableCell className="font-medium">{st.name}</TableCell>
                <TableCell>{st.y_boards}</TableCell>
                <TableCell>
                  <Pct value={st.open_pct} />
                </TableCell>
                <TableCell>
                  <Pct value={st.today_pct} />
                </TableCell>
                <TableCell>{st.result || "—"}</TableCell>
              </TableRow>
            ))}
          </TableBody>
        </Table>
      </Fold>
      <HistoryTable history={paper.history} />
    </div>
  );
}

export function PreopenView({
  data,
  session,
  selected,
  aiLoading,
  onSelect,
  onRunAi,
}: {
  data: LiveData;
  session: Session;
  selected?: string | null;
  aiLoading: boolean;
  onSelect: (code: string) => void;
  onRunAi: () => void;
}) {
  if (session.id === "closed" || session.id === "weekend") {
    return <CloseView data={data} selected={selected} aiLoading={aiLoading} onSelect={onSelect} onRunAi={onRunAi} />;
  }
  return <AuctionView data={data} selected={selected} aiLoading={aiLoading} onSelect={onSelect} onRunAi={onRunAi} />;
}
