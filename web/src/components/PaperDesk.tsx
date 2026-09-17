import { ChevronDown } from "lucide-react";
import { Collapsible, CollapsibleContent, CollapsibleTrigger } from "@/components/ui/collapsible";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { ActorBets, SectionTitle, SettleChip } from "@/components/Type";
import { chgClass, signedYuan, yuan } from "@/lib/format";
import { ROLE_ORDER, findActor } from "@/lib/paper";
import type { Actor } from "@/lib/types";

function rateText(v: number | null | undefined) {
  if (v == null) return "—";
  return `${Math.round(Number(v) * 100)}%`;
}

function RoleColumn({ role, actor }: { role: { id: string; name: string }; actor?: Actor }) {
  const subtitle = role.id === "ai" ? actor?.name || "deepseek-v4-pro" : "初始 10 万";
  const cash = actor?.cash ?? actor?.starting ?? 100000;
  return (
    <div className="min-w-0">
      <div className="flex h-8 items-center justify-between gap-2 px-3">
        <span className="truncate text-[13px] font-semibold leading-none">{role.name}</span>
        <SettleChip actor={actor} settled={actor?.settled} />
      </div>
      <div className="flex h-6 items-center px-3 font-mono text-[15px] leading-none tabular-nums">{yuan(cash)}</div>
      <div className="flex h-4 items-center px-3 text-[11px] leading-none text-muted-foreground">{subtitle}</div>
    </div>
  );
}

export function PaperDesk({
  note,
  scoreboard,
  actors,
}: {
  note?: string;
  scoreboard?: {
    id: string;
    name: string;
    days: number;
    wins: number;
    losses: number;
    pnl: number;
    pnl_yuan?: number;
    cash?: number;
    rate: number | null;
  }[];
  actors?: Actor[];
}) {
  const think = findActor(actors, "ai")?.think;
  return (
    <div className="space-y-3">
      <SectionTitle extra={note || "每人10万纸上资金，成交每笔2万。"}>纸上对打</SectionTitle>
      <div className="overflow-hidden rounded-lg border bg-card">
        <div className="grid grid-cols-2 divide-x border-b md:grid-cols-4">
          {ROLE_ORDER.map((role) => (
            <RoleColumn key={role.id} role={role} actor={findActor(actors, role.id)} />
          ))}
        </div>
        <div className="grid grid-cols-2 divide-x border-b md:grid-cols-4">
          {ROLE_ORDER.map((role) => {
            const actor = findActor(actors, role.id);
            return (
              <p key={role.id} className="min-h-[44px] px-3 py-2.5 text-[13px] leading-5 text-muted-foreground">
                {actor?.stance || "未出手"}
              </p>
            );
          })}
        </div>
        <div className="grid grid-cols-2 divide-x md:grid-cols-4">
          {ROLE_ORDER.map((role) => (
            <div key={role.id} className="px-3 py-2">
              <ActorBets actor={findActor(actors, role.id)} />
            </div>
          ))}
        </div>
      </div>
      <Table>
        <TableHeader>
          <TableRow>
            <TableHead>角色</TableHead>
            <TableHead>净值</TableHead>
            <TableHead>累计盈亏</TableHead>
            <TableHead>天数</TableHead>
            <TableHead>胜</TableHead>
            <TableHead>负</TableHead>
            <TableHead>胜率</TableHead>
          </TableRow>
        </TableHeader>
        <TableBody>
          {(scoreboard || []).map((a) => (
            <TableRow key={a.id}>
              <TableCell className="font-medium">{a.name}</TableCell>
              <TableCell className="font-mono tabular-nums">{yuan(a.cash ?? 100000)}</TableCell>
              <TableCell className={chgClass(a.pnl_yuan ?? a.pnl)}>
                {a.pnl_yuan == null ? "—" : signedYuan(a.pnl_yuan)}
              </TableCell>
              <TableCell>{a.days}</TableCell>
              <TableCell>{a.wins}</TableCell>
              <TableCell>{a.losses}</TableCell>
              <TableCell>{rateText(a.rate)}</TableCell>
            </TableRow>
          ))}
        </TableBody>
      </Table>
      {think ? (
        <Collapsible>
          <CollapsibleTrigger className="flex h-6 items-center gap-1 text-xs leading-none text-muted-foreground hover:text-foreground">
            大模型推理 <ChevronDown className="h-3 w-3" />
          </CollapsibleTrigger>
          <CollapsibleContent>
            <p className="mt-2 whitespace-pre-wrap text-xs leading-5 text-muted-foreground">{think}</p>
          </CollapsibleContent>
        </Collapsible>
      ) : null}
    </div>
  );
}
