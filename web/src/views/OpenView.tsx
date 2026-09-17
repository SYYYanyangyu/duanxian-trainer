import { AiPick } from "@/components/AiPick";
import { HistoryTable } from "@/components/HistoryTable";
import { Ladder } from "@/components/Ladder";
import { PaperDesk } from "@/components/PaperDesk";
import { Fold, StockDetail } from "@/components/StockDetail";
import { SectionTitle } from "@/components/Type";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { clipNames, pctRate } from "@/lib/format";
import { cn } from "@/lib/utils";
import type { LiveData, Stock } from "@/lib/types";

function poolByTheme(d: LiveData) {
  const stocks = d.limit_up || [];
  const order = (d.themes || []).map((t) => t.name);
  const groups = new Map<string, Stock[]>();
  for (const name of order) groups.set(name, []);
  for (const st of stocks) {
    const name = st.theme || st.industry || "未分类";
    if (!groups.has(name)) groups.set(name, []);
    groups.get(name)!.push(st);
  }
  for (const list of groups.values()) {
    list.sort((a, b) => (Number(b.boards) - Number(a.boards)) || String(a.first_seal || "").localeCompare(String(b.first_seal || "")));
  }
  return [...groups.entries()].filter(([, list]) => list.length);
}

export function OpenView({
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
  const extra = `${data.phase_why || ""} 最高 ${data.max_board} 板 · 涨停 ${data.zt_count} / 炸板 ${data.zb_count} · 昨日晋级 ${y.promoted_n || 0}/${y.count || 0}（${pctRate(y.rate)}）`;
  const stock =
    (data.limit_up || []).find((x) => x.code === selected) ||
    data.picks?.primary?.[0] ||
    null;
  const pool = poolByTheme(data);

  const paper = data.paper || {};
  return (
    <div className="space-y-4">
      <AiPick data={data} selected={selected} loading={aiLoading} extra={extra} onSelect={onSelect} onRun={onRunAi} />
      <PaperDesk note={paper.note} scoreboard={paper.scoreboard} actors={paper.today?.actors} />
      <div className="grid gap-4 xl:grid-cols-[minmax(0,1.4fr)_minmax(20rem,1fr)]">
        <section className="space-y-2">
          <SectionTitle extra="点名字看依据，首板默认收起">连板天梯</SectionTitle>
          <Ladder ladder={data.ladder || []} selected={selected} onSelect={onSelect} />
        </section>
        <section className="space-y-3">
          <SectionTitle>为什么盯 / 躲</SectionTitle>
          <StockDetail stock={stock} empty="点天梯里的股票。" />
          <Fold title="框架在看什么">
            <ol className="list-decimal space-y-1 pl-4 text-sm text-muted-foreground">
              {(data.rules || []).map((x) => (
                <li key={x}>{x}</li>
              ))}
            </ol>
          </Fold>
        </section>
      </div>
      <section className="space-y-2">
        <SectionTitle>今日题材</SectionTitle>
        <div className="desk-panel">
        <Table>
          <TableHeader>
            <TableRow>
              <TableHead>题材</TableHead>
              <TableHead>只数</TableHead>
              <TableHead>最高</TableHead>
              <TableHead>风向标</TableHead>
              <TableHead>中军</TableHead>
              <TableHead>成群</TableHead>
              <TableHead>成员</TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {(data.themes || []).map((t) => (
              <TableRow key={t.name}>
                <TableCell className="font-medium">{t.name}</TableCell>
                <TableCell>{t.count}</TableCell>
                <TableCell>{t.max_board}</TableCell>
                <TableCell>{t.vane}</TableCell>
                <TableCell>{t.army}</TableCell>
                <TableCell>{t.clustered ? "是" : "否"}</TableCell>
                <TableCell>{clipNames(t.members, 4)}</TableCell>
              </TableRow>
            ))}
          </TableBody>
        </Table>
        </div>
      </section>
      <Fold title={`完整涨停池 · 按题材分组 · ${data.limit_up?.length || 0} 只`}>
        <div className="space-y-4">
          {pool.map(([theme, list]) => {
            const meta = (data.themes || []).find((t) => t.name === theme);
            return (
              <div key={theme}>
                <div className="mb-2 text-xs text-muted-foreground">
                  {theme} · {list.length} 只 · 风向标 {meta?.vane || "—"}
                </div>
                <Table>
                  <TableHeader>
                    <TableRow>
                      <TableHead>名称</TableHead>
                      <TableHead>连板</TableHead>
                      <TableHead>换手</TableHead>
                      <TableHead>开板</TableHead>
                      <TableHead>首次封</TableHead>
                      <TableHead>角色</TableHead>
                      <TableHead>结论</TableHead>
                    </TableRow>
                  </TableHeader>
                  <TableBody>
                    {list.map((st) => (
                      <TableRow
                        key={st.code}
                        className={cn("cursor-pointer", selected === st.code && "bg-accent")}
                        onClick={() => st.code && onSelect(st.code)}
                      >
                        <TableCell className="font-medium">{st.name}</TableCell>
                        <TableCell>{st.boards}</TableCell>
                        <TableCell>{st.turnover}%</TableCell>
                        <TableCell>{st.open_times}</TableCell>
                        <TableCell>{st.first_seal || "—"}</TableCell>
                        <TableCell>{st.role}</TableCell>
                        <TableCell>{st.verdict || st.action}</TableCell>
                      </TableRow>
                    ))}
                  </TableBody>
                </Table>
              </div>
            );
          })}
        </div>
      </Fold>
      <HistoryTable history={data.paper?.history} />
    </div>
  );
}
