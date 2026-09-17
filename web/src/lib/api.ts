import type { LiveData } from "./types";

export async function fetchToday(refresh = false, signal?: AbortSignal): Promise<LiveData> {
  const urls = refresh ? ["/api/today?refresh=1"] : ["/api/today", "/today.json"];
  let lastErr: Error | null = null;
  for (const url of urls) {
    try {
      const res = await fetch(url, { cache: "no-store", signal });
      const data = (await res.json()) as LiveData & { error?: string };
      if (!res.ok || data.error) throw new Error(data.error || `HTTP ${res.status}`);
      return data;
    } catch (err) {
      lastErr = err instanceof Error ? err : new Error(String(err));
    }
  }
  throw lastErr || new Error("拉不到实盘");
}

export async function fetchAiPick(signal?: AbortSignal): Promise<LiveData> {
  const res = await fetch("/api/ai", { cache: "no-store", signal });
  const data = (await res.json()) as LiveData & { error?: string };
  if (!res.ok || data.error) throw new Error(data.error || `HTTP ${res.status}`);
  return data;
}

export function hasTape(data?: LiveData | null) {
  if (!data) return false;
  return Boolean(
    (data.limit_up || []).length ||
      ((data.yesterday || {}).preopen || []).length ||
      (data.morning_watch || []).length,
  );
}
