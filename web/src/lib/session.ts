export type Session = {
  id: string;
  label: string;
  hint: string;
  default_view: "preopen" | "open";
  preopenWhen: string;
  openWhen: string;
};

function hmOf(d: Date) {
  return d.getHours() * 100 + d.getMinutes();
}

export function liveSession(now = new Date()): Session {
  const hm = hmOf(now);
  const day = now.getDay();
  const weekday = day >= 1 && day <= 5;
  if (!weekday) {
    return {
      id: "weekend",
      label: "休市",
      hint: "周末休市。开盘后是最近交易日复盘；开盘前是下周一名单。",
      default_view: "open",
      preopenWhen: "下周一 9:15",
      openWhen: "最近交易日复盘",
    };
  }
  if (hm < 915) {
    return {
      id: "preopen",
      label: "开盘前",
      hint: "还没到 9:15。开盘前看今早竞价该盯谁。",
      default_view: "preopen",
      preopenWhen: "今早 9:15",
      openWhen: "昨天复盘",
    };
  }
  if (hm < 930) {
    return {
      id: "auction",
      label: "集合竞价",
      hint: "9:15–9:30 看昨日连板竞价，高开核按钮、低开晋级变弱。",
      default_view: "preopen",
      preopenWhen: "今早竞价（进行中）",
      openWhen: "等 9:30 看今天",
    };
  }
  if (hm >= 1130 && hm < 1300) {
    return {
      id: "lunch",
      label: "午休",
      hint: "午休。开盘后看上午盘，开盘前回看今早竞价。",
      default_view: "open",
      preopenWhen: "今早竞价（回看）",
      openWhen: "今天上午盘",
    };
  }
  if (hm < 1500) {
    return {
      id: "open",
      label: "开盘后",
      hint: "盘中看天梯高度和封板质量。",
      default_view: "open",
      preopenWhen: "今早竞价（回看）",
      openWhen: hm < 1130 ? "今天上午盘" : "今天下午盘",
    };
  }
  return {
    id: "closed",
    label: "已收盘",
    hint: day === 5 ? "已收盘。开盘前是下周一 9:15 该盯谁。" : "已收盘。开盘前是明早 9:15 该盯谁。",
    default_view: "open",
    preopenWhen: day === 5 ? "下周一 9:15" : "明早 9:15",
    openWhen: "今天复盘",
  };
}

export function stepState(id: string, now = new Date()) {
  const day = now.getDay();
  if (day === 0 || day === 6) return "";
  const hm = hmOf(now);
  if (hm < 915 || hm >= 1500) return "";
  const next: Record<string, number> = { "915": 920, "920": 925, "925": 930, "930": 931 };
  const start: Record<string, number> = { "915": 915, "920": 920, "925": 925, "930": 930 };
  if (hm >= next[id]) return "done";
  if (hm >= start[id]) return "now";
  return "";
}
