import { useCallback, useEffect, useMemo, useState } from "react";
import { RefreshCw } from "lucide-react";
import { Alert } from "@/components/ui/alert";
import { Button } from "@/components/ui/button";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { fetchAiPick, fetchToday, hasTape } from "@/lib/api";
import { formatLiveTime } from "@/lib/format";
import { liveSession } from "@/lib/session";
import type { LiveData } from "@/lib/types";
import { OpenView } from "@/views/OpenView";
import { PreopenView } from "@/views/PreopenView";

function pickDefaultCode(data: LiveData) {
  const watch = data.ai?.watch || [];
  const shot = watch.find((w) => w.side === "盯") || watch[0];
  return shot?.code || data.picks?.primary?.[0]?.code || data.morning_watch?.[0]?.code || data.yesterday?.preopen?.[0]?.code || "";
}

export default function App() {
  const [now, setNow] = useState(() => new Date());
  const [live, setLive] = useState<LiveData | null>(null);
  const [loading, setLoading] = useState(false);
  const [aiLoading, setAiLoading] = useState(false);
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");
  const [view, setView] = useState<"auto" | "preopen" | "open">("auto");
  const [selected, setSelected] = useState<string>("");
  const session = useMemo(() => liveSession(now), [now]);
  const activeView = view === "auto" ? session.default_view : view;

  useEffect(() => {
    const id = window.setInterval(() => setNow(new Date()), 1000);
    return () => window.clearInterval(id);
  }, []);

  const applyLive = useCallback((data: LiveData, fromAi = false) => {
    setLive(data);
    setSelected((prev) => {
      if (fromAi) return pickDefaultCode(data) || prev;
      return prev || pickDefaultCode(data);
    });
  }, []);

  const load = useCallback(
    async (refresh = false) => {
      if (loading) return;
      setLoading(true);
      setError("");
      const ctrl = new AbortController();
      const timer = window.setTimeout(() => ctrl.abort(), refresh ? 45000 : 15000);
      try {
        const data = await fetchToday(refresh, ctrl.signal);
        if (!hasTape(data)) {
          if (hasTape(live)) {
            setNotice("刷新没拉到盘面，仍显示上一份。");
            return;
          }
          throw new Error("盘面是空的");
        }
        applyLive(data);
        setNotice(data.fetch_error ? `刷新失败，仍显示上一份：${data.fetch_error}` : "");
      } catch (err) {
        const msg = err instanceof Error ? err.message : String(err);
        if (hasTape(live)) {
          setNotice(`刷新失败，仍显示上一份盘面。 ${msg}`);
        } else {
          setError(`拉不到实盘。请运行 start.bat。 ${msg}`);
        }
      } finally {
        window.clearTimeout(timer);
        setLoading(false);
      }
    },
    [applyLive, live, loading],
  );

  useEffect(() => {
    void load(false);
    // initial load only
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  async function runAi() {
    if (aiLoading) return;
    setAiLoading(true);
    setNotice("");
    const ctrl = new AbortController();
    const timer = window.setTimeout(() => ctrl.abort(), 130000);
    try {
      const data = await fetchAiPick(ctrl.signal);
      applyLive(data, true);
      const auc = data.auction || {};
      setNotice(
        auc.as_of
          ? `已拉东财报价 ${auc.as_of}（${auc.stage || ""}），AI按竞价/今开决策。`
          : "AI已按打法思路选出名单。",
      );
    } catch (err) {
      const aborted = err instanceof DOMException && err.name === "AbortError";
      setNotice(`AI选股失败：${aborted ? "超时，再点一次" : err instanceof Error ? err.message : String(err)}`);
    } finally {
      window.clearTimeout(timer);
      setAiLoading(false);
    }
  }

  return (
    <div className="min-h-screen">
      <header className="sticky top-0 z-20 border-b bg-background/95 backdrop-blur">
        <div className="mx-auto flex h-12 max-w-[1480px] items-center justify-between gap-4 px-4">
          <div className="flex items-center gap-3">
            <span className="text-[15px] font-semibold leading-none">短线选股</span>
            <span className="text-xs leading-none text-muted-foreground">开盘前 / 开盘后 · 纸上对打</span>
          </div>
          <div className="flex items-center gap-3">
            <span className="text-[13px] leading-none text-muted-foreground">{session.label}</span>
            <span className="font-mono text-[13px] leading-none tabular-nums">{formatLiveTime(now)}</span>
            <Button onClick={() => void load(true)} disabled={loading} variant="outline" size="sm">
              <RefreshCw className={loading ? "h-3.5 w-3.5 animate-spin" : "h-3.5 w-3.5"} />
              {loading ? "刷新中…" : "刷新数据"}
            </Button>
          </div>
        </div>
      </header>
      <main className="mx-auto max-w-[1480px] space-y-4 px-4 py-4">
        {error && !live ? (
          <Alert>
            <p className="font-medium">短线选股</p>
            <p className="mt-1 text-sm text-muted-foreground">{error}</p>
            <Button className="mt-3" onClick={() => void load(true)}>
              重试
            </Button>
          </Alert>
        ) : null}
        {loading && !live ? <p className="text-sm text-muted-foreground">正在拉数据：涨停池、昨日连板、今开/竞价。</p> : null}
        {live ? (
          <>
            <Tabs value={activeView} onValueChange={(v) => setView(v as "preopen" | "open")}>
              <TabsList>
                <TabsTrigger value="preopen">
                  开盘前
                  <span className="text-xs font-normal text-muted-foreground">{session.preopenWhen}</span>
                </TabsTrigger>
                <TabsTrigger value="open">
                  开盘后
                  <span className="text-xs font-normal text-muted-foreground">{session.openWhen}</span>
                </TabsTrigger>
              </TabsList>
              <p className="mt-3 text-[13px] leading-5 text-muted-foreground">
                {session.hint} 现在是「{session.label}」。
              </p>
              {notice || live.fetch_error || live.ledger_error ? (
                <Alert className="mt-3 border-amber-200 bg-amber-50 text-amber-900">
                  {notice || `刷新警告：${live.fetch_error || live.ledger_error}`}
                </Alert>
              ) : null}
              <TabsContent value="preopen">
                <PreopenView
                  data={live}
                  session={session}
                  selected={selected}
                  aiLoading={aiLoading}
                  onSelect={setSelected}
                  onRunAi={() => void runAi()}
                />
              </TabsContent>
              <TabsContent value="open">
                <OpenView
                  data={live}
                  selected={selected}
                  aiLoading={aiLoading}
                  onSelect={setSelected}
                  onRunAi={() => void runAi()}
                />
              </TabsContent>
            </Tabs>
            <p className="pb-6 text-xs text-muted-foreground">{live.disclaimer || ""}</p>
          </>
        ) : null}
      </main>
    </div>
  );
}
