import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { ActorBets, SettleChip } from "@/components/Type";
import { Fold } from "./StockDetail";
import { yuan } from "@/lib/format";
import { ROLE_ORDER, findActor } from "@/lib/paper";
import type { Actor } from "@/lib/types";

export function HistoryTable({
  history,
}: {
  history?: { date: string; phase?: string; settled?: boolean; actors?: Actor[] }[];
}) {
  const rows = (history || []).slice(0, 12);
  if (!rows.length) return null;
  return (
    <Fold title={`回溯台账 · ${rows.length} 天`}>
      <Table>
        <TableHeader>
          <TableRow>
            <TableHead className="w-24">日期</TableHead>
            <TableHead className="w-16">情绪</TableHead>
            {ROLE_ORDER.map((role) => (
              <TableHead key={role.id}>{role.name}</TableHead>
            ))}
          </TableRow>
        </TableHeader>
        <TableBody>
          {rows.map((day) => (
            <TableRow key={day.date} className="align-top">
              <TableCell className="pt-3 font-medium leading-5">{day.date}</TableCell>
              <TableCell className="pt-3 leading-5 text-muted-foreground">{day.phase || "—"}</TableCell>
              {ROLE_ORDER.map((role) => {
                const actor = findActor(day.actors, role.id);
                return (
                  <TableCell key={role.id} className="py-3 align-top">
                    <div className="space-y-1.5">
                      <div className="flex h-5 items-center gap-2">
                        <SettleChip actor={actor} settled={day.settled} />
                      </div>
                      <p className="font-mono text-[12px] leading-5 tabular-nums text-muted-foreground">
                        {yuan(actor?.cash ?? 100000)}
                      </p>
                      <p className="line-clamp-2 min-h-5 text-[12px] leading-5 text-muted-foreground">
                        {actor?.stance || "—"}
                      </p>
                      <ActorBets actor={actor} />
                    </div>
                  </TableCell>
                );
              })}
            </TableRow>
          ))}
        </TableBody>
      </Table>
    </Fold>
  );
}
