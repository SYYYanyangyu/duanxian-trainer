const state = {
  live: null,
  loading: false,
  error: null,
  view: "auto",
  selected: null,
  lastSessId: null,
  notice: "",
  keepScroll: false,
  aiLoading: false,
  fold: { oneBoard: false, pool: false, settle: false, history: false, rules: false }
};

function $(sel) { return document.querySelector(sel); }

function pad2(n) {
  return String(n).padStart(2, "0");
}

function formatLiveTime(d) {
  const week = "日一二三四五六";
  return `${d.getFullYear()}-${pad2(d.getMonth() + 1)}-${pad2(d.getDate())} 周${week[d.getDay()]} ${pad2(d.getHours())}:${pad2(d.getMinutes())}:${pad2(d.getSeconds())}`;
}

function hmOf(d) {
  return d.getHours() * 100 + d.getMinutes();
}

function isWeekday(d) {
  const day = d.getDay();
  return day >= 1 && day <= 5;
}

function liveSession(now) {
  now = now || new Date();
  const hm = hmOf(now);
  const day = now.getDay();
  const weekday = isWeekday(now);
  if (!weekday) {
    return {
      id: "weekend",
      label: "休市",
      hint: "周末休市。开盘后是最近一个交易日复盘；开盘前是下周一 9:15 该盯谁。法定节假日这里识别不了。",
      default_view: "open",
      preopenWhen: "下周一 9:15",
      openWhen: "最近交易日复盘",
      whichDay: "隔天（下周一）"
    };
  }
  if (hm < 915) {
    return {
      id: "preopen",
      label: "开盘前",
      hint: "现在还没到 9:15。开盘前 = 今早竞价该盯谁（当天）；开盘后 = 昨天已经走完的复盘。",
      default_view: "preopen",
      preopenWhen: "今早 9:15",
      openWhen: "昨天复盘",
      whichDay: "当天早上"
    };
  }
  if (hm < 930) {
    return {
      id: "auction",
      label: "集合竞价",
      hint: "9:15–9:30 是今天的竞价。开盘前页看今早竞价；开盘后页要等 9:30 才是当天盘中。",
      default_view: "preopen",
      preopenWhen: "今早竞价（进行中）",
      openWhen: "等 9:30 看今天",
      whichDay: "当天早上"
    };
  }
  if (hm >= 1130 && hm < 1300) {
    return {
      id: "lunch",
      label: "午休",
      hint: "现在是今天午休。开盘后 = 今天上午已经走出来的盘；开盘前 = 回看今早竞价，不是明天。",
      default_view: "open",
      preopenWhen: "今早竞价（回看）",
      openWhen: "今天上午盘",
      whichDay: "当天"
    };
  }
  if (hm < 1500) {
    return {
      id: "open",
      label: "开盘后",
      hint: "现在是今天盘中。开盘后 = 当天天梯/涨停池；开盘前 = 回看今早竞价，不是隔天。",
      default_view: "open",
      preopenWhen: "今早竞价（回看）",
      openWhen: hm < 1130 ? "今天上午盘" : "今天下午盘",
      whichDay: "当天"
    };
  }
  return {
    id: "closed",
    label: "已收盘",
    hint: day === 5
      ? "今天已经收盘。开盘后 = 今天复盘；开盘前 = 下周一 9:15 该盯谁。"
      : "今天已经收盘。开盘后 = 今天复盘，不是明天；开盘前 = 明天早上 9:15 该盯谁。",
    default_view: "open",
    preopenWhen: day === 5 ? "下周一 9:15" : "明早 9:15",
    openWhen: "今天复盘",
    whichDay: day === 5 ? "隔天（下周一）" : "隔天（明早）"
  };
}

function stepClass(id, now) {
  now = now || new Date();
  if (!isWeekday(now)) return "";
  const hm = hmOf(now);
  if (hm < 915 || hm >= 1500) return "";
  const start = { "915": 915, "920": 920, "925": 925, "930": 930 };
  const next = { "915": 920, "920": 925, "925": 930, "930": 931 };
  const t = start[id];
  if (hm >= next[id]) return "done";
  if (hm >= t) return "now";
  return "";
}

function paintClock() {
  const now = new Date();
  const sess = liveSession(now);
  const label = $("#sess-label");
  const clock = $("#live-clock");
  if (label) label.textContent = sess.label;
  if (clock) clock.textContent = formatLiveTime(now);
  const hint = $("#sess-hint");
  if (hint) hint.textContent = sess.hint + " 现在是「" + sess.label + "」。";
  const pre = document.querySelector("[data-view=preopen] .tab-when");
  const op = document.querySelector("[data-view=open] .tab-when");
  if (pre) pre.textContent = sess.preopenWhen;
  if (op) op.textContent = sess.openWhen;
  document.querySelectorAll(".step[data-step]").forEach((el) => {
    el.classList.remove("now", "done");
    const cls = stepClass(el.dataset.step, now);
    if (cls) el.classList.add(cls);
  });
  if (state.lastSessId && state.lastSessId !== sess.id) {
    state.lastSessId = sess.id;
    if (!state.rendering) render();
    return;
  }
  state.lastSessId = sess.id;
}

function chgClass(v) {
  if (v > 0) return "chg-up";
  if (v < 0) return "chg-dn";
  return "chg-0";
}

function chgText(v) {
  if (v == null || Number.isNaN(Number(v))) return "—";
  const n = Number(v);
  return (n > 0 ? "+" : "") + n.toFixed(1) + "%";
}

function pctRate(v) {
  if (v == null) return "—";
  return Math.round(Number(v) * 100) + "%";
}

function activeView() {
  if (state.view === "preopen" || state.view === "open") return state.view;
  return liveSession().default_view || "open";
}

function applyLive(data, fromAi) {
  state.live = data;
  const watch = (data.ai && data.ai.watch) || [];
  const shot = watch.find((w) => w.side === "盯") || watch[0];
  if (fromAi && shot && shot.code) {
    state.selected = shot.code;
    return;
  }
  if (!state.selected && shot && shot.code) {
    state.selected = shot.code;
    return;
  }
  if (!state.selected && data.picks && data.picks.primary && data.picks.primary[0]) {
    state.selected = data.picks.primary[0].code;
  }
}

function findStock(code) {
  const d = state.live;
  if (!d || !code) return null;
  return (d.limit_up || []).find((x) => x.code === code)
    || ((d.yesterday && d.yesterday.preopen) || []).find((x) => x.code === code)
    || (d.morning_watch || []).find((x) => x.code === code)
    || ((d.ai && d.ai.watch) || []).find((x) => x.code === code)
    || null;
}

async function runAi() {
  if (state.aiLoading) return;
  state.aiLoading = true;
  state.notice = "";
  render();
  const ctrl = new AbortController();
  const timer = setTimeout(() => ctrl.abort(), 130000);
  try {
    const res = await fetch("/api/ai", { cache: "no-store", signal: ctrl.signal });
    const data = await res.json();
    if (!res.ok || data.error) throw new Error(data.error || ("HTTP " + res.status));
    applyLive(data, true);
    const auc = data.auction || {};
    state.notice = auc.as_of
      ? ("已拉东财报价 " + auc.as_of + "（" + (auc.stage || "") + "），AI按竞价/今开决策。")
      : "AI已按打法思路选出名单。";
  } catch (err) {
    state.notice = "AI选股失败：" + (err.name === "AbortError" ? "超时，再点一次" : (err.message || err));
  } finally {
    clearTimeout(timer);
    state.aiLoading = false;
    render();
  }
}

function aiButtonLabel(d) {
  const sid = (d && d.session && d.session.id) || liveSession().id;
  if (state.aiLoading) return sid === "auction" ? "正在拉竞价并让AI决策…" : "AI选股中…";
  if (sid === "auction") return "拉竞价并让AI决策";
  return "让AI选股";
}

function renderAiPick(d, extra) {
  const ai = d.ai || {};
  const watch = ai.watch || [];
  const avoid = ai.avoid || [];
  const auc = d.auction || {};
  const waiting = !ai.stance || ai.stance === "待选股";
  const failed = ai.stance === "调用失败" || ai.stance === "未接入";
  const aucLine = auc.as_of
    ? `东财竞价 ${auc.stage || ""} · 报价 ${auc.as_of} · 已报价 ${auc.filled || 0} 只`
    : "点按钮会先拉东财实时报价，再让模型决策。";
  return `
    <div class="ai-pick ${failed ? "bad" : ""}">
      <div class="ai-pick-h">
        <div>
          <div class="decision-k">AI选股 · ${ai.model || "deepseek-v4-pro"} · ${ai.note || "纸上选股，不是下单"}</div>
          <div class="decision-v">${ai.stance || "还没让模型选股"}</div>
          <p>${ai.plan || extra || "规则机只打标签。点右边，让模型按龙头思路出名单。"}</p>
          <p class="meta">${aucLine}</p>
        </div>
        <button class="btn" id="run-ai" ${state.aiLoading ? "disabled" : ""}>${aiButtonLabel(d)}</button>
      </div>
      ${watch.length ? `<div class="ai-watch">${watch.map((w) => `
        <button type="button" class="ai-chip ${state.selected === w.code ? "on" : ""} ${w.side === "盯" ? "shot" : ""}" data-code="${w.code}">
          <b>${w.name}</b><span>${w.side || ""}</span>
          <small>${w.why || ""}</small>
        </button>`).join("")}</div>` : `<p class="meta">${state.aiLoading ? "正在拉东财报价并交给模型…" : (waiting ? "还没有进攻名单。" : "这轮模型没有进攻标的。")}</p>`}
      ${avoid.length ? `<p class="meta">躲：${avoid.map((a) => a.name).join("、")}</p>` : ""}
      ${ai.think ? `<details class="fold" data-fold="ai-think" ${state.fold["ai-think"] ? "open" : ""}><summary>AI推理</summary><p class="think">${ai.think}</p></details>` : ""}
    </div>`;
}

async function loadLive(refresh) {
  if (state.loading) return;
  state.loading = true;
  state.error = null;
  render();
  const urls = refresh ? ["/api/today?refresh=1"] : ["/api/today", "today.json"];
  let lastErr = null;
  try {
    for (const url of urls) {
      const ctrl = new AbortController();
      const timer = setTimeout(() => ctrl.abort(), refresh ? 45000 : 15000);
      try {
        const res = await fetch(url, { cache: "no-store", signal: ctrl.signal });
        if (!res.ok) throw new Error("HTTP " + res.status);
        const data = await res.json();
        if (data.error) throw new Error(data.error);
        const hasTape = (data.limit_up || []).length
          || ((data.yesterday || {}).preopen || []).length
          || (data.morning_watch || []).length;
        if (!hasTape) {
          if (state.live && ((state.live.limit_up || []).length || ((state.live.yesterday || {}).preopen || []).length)) {
            state.notice = "刷新没拉到盘面，仍显示上一份。";
            return;
          }
          throw new Error("盘面是空的");
        }
        applyLive(data, false);
        state.notice = data.fetch_error ? ("刷新失败，仍显示上一份：" + data.fetch_error) : "";
        state.error = null;
        return;
      } catch (err) {
        lastErr = err;
      } finally {
        clearTimeout(timer);
      }
    }
    if (state.live && (state.live.limit_up || []).length) {
      state.notice = "刷新失败，仍显示上一份盘面。" + (lastErr ? " " + lastErr : "");
      state.error = null;
    } else {
      state.error = "拉不到实盘。请运行 start.bat。" + (lastErr ? " " + lastErr : "");
    }
  } finally {
    state.loading = false;
    render();
  }
}

function reasonsHtml(list) {
  if (!list || !list.length) return "";
  return `<ul class="reasons">${list.map((x) => `<li class="${x.tone || ""}">${x.text}</li>`).join("")}</ul>`;
}

function verdictTag(v) {
  const map = { "盯": "gold", "躲": "red", "做": "gold" };
  return `<span class="pill ${map[v] || ""}">${v || "观察"}</span>`;
}

function clipNames(list, n) {
  const arr = list || [];
  if (!arr.length) return "—";
  if (arr.length <= n) return arr.join("、");
  return arr.slice(0, n).join("、") + " 等" + arr.length + "只";
}

function foldBox(id, title, html) {
  return `<details class="fold" data-fold="${id}" ${state.fold[id] ? "open" : ""}>
    <summary>${title}</summary>
    <div class="fold-body">${html}</div>
  </details>`;
}

function renderLadder(d) {
  const ladder = d.ladder || [];
  return `<div class="ladder">
    ${ladder.map((col) => {
      const isOne = col.boards === 1;
      const hide = isOne && !state.fold.oneBoard;
      const stocks = hide ? [] : col.stocks;
      return `
        <div class="ladder-col">
          <div class="ladder-h">${col.boards}板 · ${col.stocks.length}</div>
          <div class="ladder-list">
            ${stocks.map((s) => `
              <button class="ladder-item ${s.verdict === "躲" ? "hide" : ""} ${state.selected === s.code ? "on" : ""}" data-code="${s.code}" title="${s.theme || s.industry || ""}">
                <b>${s.name}</b><span>${s.verdict || ""}</span>
              </button>`).join("")}
            ${isOne ? `<button class="ladder-more" data-fold-one>${state.fold.oneBoard ? "收起首板" : "展开首板 " + col.stocks.length + " 只"}</button>` : ""}
          </div>
        </div>`;
    }).join("")}
  </div>`;
}

function renderOpen(d) {
  const y = d.yesterday || {};
  const picks = d.picks || {};
  const selected = findStock(state.selected) || (picks.primary && picks.primary[0]) || null;
  const poolHtml = poolByTheme(d).map(([theme, list]) => {
    const meta = (d.themes || []).find((t) => t.name === theme) || {};
    return `
      <div class="pool-theme">${theme} · ${list.length} 只 · 风向标 ${meta.vane || "—"}</div>
      <table>
        <thead><tr><th>名称</th><th>连板</th><th>换手</th><th>开板</th><th>首次封</th><th>角色</th><th>结论</th></tr></thead>
        <tbody>${list.map(stockRow).join("")}</tbody>
      </table>`;
  }).join("");
  return `
    ${renderAiPick(d, (d.phase_why || "") + " 最高 " + d.max_board + " 板 · 涨停 " + d.zt_count + " / 炸板 " + d.zb_count + " · 昨日晋级 " + (y.promoted_n || 0) + "/" + (y.count || 0) + "（" + pctRate(y.rate) + "）")}
    <div class="desk">
      <section>
        <h2 class="section-title">连板天梯 · 点名字看依据，首板默认收起</h2>
        ${renderLadder(d)}
      </section>
      <section>
        <h2 class="section-title">为什么盯 / 躲</h2>
        ${selected ? `
          <article class="card">
            <div class="pick-head">
              <strong>${selected.name} ${selected.code || ""}</strong>
              ${verdictTag(selected.verdict)}
            </div>
            <p class="meta">${selected.role || ""} · ${selected.boards != null ? selected.boards + "板" : ""} · 换手 ${selected.turnover}% · 开板 ${selected.open_times} · 封板 ${selected.first_seal || "—"} · 流通 ${selected.float_mv_yi || "—"} 亿</p>
            <p class="meta">题材 <b style="color:var(--text)">${selected.theme || selected.industry || "—"}</b> · ${selected.theme_count || 0} 只${selected.clustered ? "成群" : "未成群"} · 风向标 ${selected.vane || "—"} · 中军 ${selected.army || "—"}</p>
            ${selected.peers && selected.peers.length ? `<p class="meta">同涨 ${clipNames(selected.peers, 6)}</p>` : ""}
            <p style="margin:6px 0">${selected.action || ""}</p>
            ${reasonsHtml(selected.reasons)}
          </article>` : `<p class="lede">点天梯里的股票。</p>`}
        ${foldBox("rules", "框架在看什么", `<ol class="rules">${(d.rules || []).map((x) => `<li>${x}</li>`).join("")}</ol>`)}
      </section>
    </div>
    <h2 class="section-title">今日题材</h2>
    <div class="table-wrap">
      <table>
        <thead><tr><th>题材</th><th>只数</th><th>最高</th><th>风向标</th><th>中军</th><th>成群</th><th>成员</th></tr></thead>
        <tbody>${(d.themes || []).map((t) => `
          <tr>
            <td>${t.name}</td>
            <td>${t.count}</td>
            <td>${t.max_board}</td>
            <td>${t.vane}</td>
            <td>${t.army}</td>
            <td>${t.clustered ? "是" : "否"}</td>
            <td>${clipNames(t.members, 4)}</td>
          </tr>`).join("")}</tbody>
      </table>
    </div>
    ${foldBox("pool", "完整涨停池 · 按题材分组", poolHtml)}`;
}

function poolByTheme(d) {
  const stocks = d.limit_up || [];
  const order = (d.themes || []).map((t) => t.name);
  const groups = new Map();
  for (const name of order) groups.set(name, []);
  for (const st of stocks) {
    const name = st.theme || st.industry || "未分类";
    if (!groups.has(name)) groups.set(name, []);
    groups.get(name).push(st);
  }
  for (const list of groups.values()) {
    list.sort((a, b) => (b.boards - a.boards) || String(a.first_seal || "").localeCompare(String(b.first_seal || "")));
  }
  return [...groups.entries()].filter(([, list]) => list.length);
}

function stockRow(st) {
  return `
    <tr class="clickable ${state.selected === st.code ? "pick" : ""}" data-code="${st.code}">
      <td>${st.name}</td>
      <td>${st.boards}</td>
      <td>${st.turnover}%</td>
      <td>${st.open_times}</td>
      <td>${st.first_seal || "—"}</td>
      <td>${st.role}</td>
      <td>${st.verdict || st.action}</td>
    </tr>`;
}

function rateText(v) {
  if (v == null) return "还没结算";
  return Math.round(Number(v) * 100) + "%";
}

function actorLine(a) {
  const bets = (a.bets || []).map((b) => ((b.side || "") + (b.name ? " " + b.name : "")).trim()).filter(Boolean).join("、") || "无标的";
  const pnl = a.settled && a.pnl != null ? ((Number(a.pnl) > 0 ? "+" : "") + a.pnl + "%") : (a.settled ? "0%" : "未结算");
  return `${a.name} · ${pnl} · ${bets}`;
}

function renderHistory(paper) {
  const rows = ((paper && paper.history) || []).slice(0, 8);
  if (!rows.length) return "";
  const table = `
    <div class="table-wrap short">
      <table>
        <thead><tr><th>日期</th><th>情绪</th><th>结算</th><th>角色摘要</th></tr></thead>
        <tbody>${rows.map((day) => `
          <tr>
            <td>${day.date}</td>
            <td>${day.phase || "—"}</td>
            <td>${day.settled ? "已结算" : "未结算"}</td>
            <td>${(day.actors || []).map(actorLine).join(" ｜ ")}</td>
          </tr>`).join("")}</tbody>
      </table>
    </div>`;
  return foldBox("history", "回溯台账 · " + rows.length + " 天", table);
}

function renderAuction(d, sess) {
  const y = d.yesterday || {};
  const rows = y.preopen || [];
  const tm = d.tomorrow || {};
  const auc = d.auction || {};
  const selected = rows.find((x) => x.code === state.selected) || rows[0] || null;
  const steps = [
    ["915", "9:15", "只看昨 2 板以上"],
    ["920", "9:20", "看高开还是低开"],
    ["925", "9:25", "定档今日龙候选"],
    ["930", "9:30", "切开盘后看封板"]
  ];
  const now = new Date();
  return `
    ${renderAiPick(d, tm.plan || "看昨天涨停今天怎么开。点按钮会先拉东财竞价，再让模型拍板。")}
    <div class="steps">
      ${steps.map((s) => `<div class="step ${stepClass(s[0], now)}" data-step="${s[0]}"><b>${s[1]}</b><span>${s[2]}</span></div>`).join("")}
    </div>
    <div class="desk">
      <section>
        <h2 class="section-title">昨日涨停 · 竞价/今开 ${auc.as_of ? "· 报价 " + auc.as_of : ""}</h2>
        <div class="table-wrap">
          <table>
            <thead><tr><th>名称</th><th>昨板</th><th>今开</th><th>匹配/现涨</th><th>判定</th><th>级别</th></tr></thead>
            <tbody>${rows.map((st) => {
              const match = st.match_pct != null ? st.match_pct : st.today_pct;
              const flag = (auc.rows || []).find((x) => x.code === st.code);
              return `
              <tr class="clickable ${state.selected === st.code ? "pick" : ""}" data-code="${st.code}">
                <td>${st.name}</td>
                <td>${st.y_boards}</td>
                <td class="${chgClass(st.open_pct)}">${chgText(st.open_pct)}</td>
                <td class="${chgClass(match)}">${chgText(match)}</td>
                <td>${(flag && flag.flag) || st.result || "—"}</td>
                <td>${st.watch_level || ""}</td>
              </tr>`;
            }).join("")}</tbody>
          </table>
        </div>
      </section>
      <section>
        <h2 class="section-title">点中的依据</h2>
        ${selected ? `
          <article class="card">
            <div class="pick-head"><strong>${selected.name}</strong><span class="pill gold">昨 ${selected.y_boards} 板</span></div>
            <p class="meta">${selected.code} · ${selected.industry || ""} · 今开 ${chgText(selected.open_pct)} · ${selected.result || ""}</p>
            ${reasonsHtml(selected.reasons)}
          </article>` : `<p class="lede">点左边表格。</p>`}
        <article class="card" style="margin-top:8px">
          <p class="meta">高开 ≥5%</p>
          <p>${(y.auction_strong || []).map((x) => x.name + " " + chgText(x.open_pct)).join("、") || "暂无"}</p>
          <p class="meta" style="margin-top:8px">低开</p>
          <p>${(y.auction_weak || []).map((x) => x.name + " " + chgText(x.open_pct)).join("、") || "暂无"}</p>
        </article>
      </section>
    </div>`;
}

function renderClose(d, sess) {
  const y = d.yesterday || {};
  const rows = y.preopen || [];
  const watch = d.morning_watch || [];
  const tm = d.tomorrow || {};
  const paper = d.paper || {};
  const selected = watch.find((x) => x.code === state.selected)
    || rows.find((x) => x.code === state.selected)
    || watch[0]
    || null;
  const actors = (paper.today && paper.today.actors) || [];
  const settleTable = `
    <p class="meta">晋级 ${y.promoted_n || 0}/${y.count || 0}（${pctRate(y.rate)}）。这是复盘，不是明早名单。</p>
    <div class="table-wrap">
      <table>
        <thead><tr><th>名称</th><th>昨板</th><th>今开</th><th>收盘涨幅</th><th>结果</th></tr></thead>
        <tbody>${rows.map((st) => `
          <tr class="clickable ${state.selected === st.code ? "pick" : ""}" data-code="${st.code}">
            <td>${st.name}</td>
            <td>${st.y_boards}</td>
            <td class="${chgClass(st.open_pct)}">${chgText(st.open_pct)}</td>
            <td class="${chgClass(st.today_pct)}">${chgText(st.today_pct)}</td>
            <td>${st.result || "—"}</td>
          </tr>`).join("")}</tbody>
      </table>
    </div>`;
  return `
    ${renderAiPick(d, tm.plan || "用今天的连板做明天竞价名单。")}
    <div class="desk">
      <section>
        <h2 class="section-title">明早竞价名单</h2>
        <div class="table-wrap">
          <table>
            <thead><tr><th>名称</th><th>今板</th><th>涨幅</th><th>换手</th><th>开板</th><th>题材</th><th>角色</th><th>明早</th></tr></thead>
            <tbody>${watch.map((st) => `
              <tr class="clickable ${state.selected === st.code ? "pick" : ""}" data-code="${st.code}">
                <td>${st.name}</td>
                <td>${st.boards}</td>
                <td class="${chgClass(st.pct)}">${chgText(st.pct)}</td>
                <td>${st.turnover}%</td>
                <td>${st.open_times}</td>
                <td>${st.theme || ""}</td>
                <td>${st.role || ""}</td>
                <td>${st.verdict || ""}</td>
              </tr>`).join("")}</tbody>
          </table>
        </div>
        ${selected && selected.watch_note ? `<article class="card" style="margin-top:8px"><p>${selected.name}：${selected.watch_note}</p></article>` : ""}
      </section>
      <section>
        <h2 class="section-title">纸上对打</h2>
        <p class="meta">${paper.note || "纸上记账，不是实盘。"}</p>
        <div class="table-wrap short">
          <table>
            <thead><tr><th>角色</th><th>天数</th><th>胜</th><th>负</th><th>胜率</th><th>累计</th></tr></thead>
            <tbody>${(paper.scoreboard || []).map((a) => `
              <tr>
                <td>${a.name}</td>
                <td>${a.days}</td>
                <td>${a.wins}</td>
                <td>${a.losses}</td>
                <td>${rateText(a.rate)}</td>
                <td class="${chgClass(a.pnl)}">${a.pnl == null ? "—" : (a.pnl > 0 ? "+" : "") + a.pnl + "%"}</td>
              </tr>`).join("")}</tbody>
          </table>
        </div>
        <div class="actor-grid">
          ${actors.map((a) => `
            <article class="card">
              <div class="pick-head"><strong>${a.name}</strong><span class="pill">${a.stance || ""}</span></div>
              ${(a.bets || []).length ? `<p class="meta">${(a.bets || []).map((b) => (b.side || "") + " " + (b.name || "")).join(" · ")}</p>` : `<p class="meta">今天没有标的。</p>`}
              ${a.think ? `<details ${state.fold["think-" + a.id] ? "open" : ""} data-fold="think-${a.id}"><summary>推理</summary><p class="think">${a.think}</p></details>` : ""}
            </article>`).join("")}
        </div>
      </section>
    </div>
    ${foldBox("settle", "今日结算 · 昨天涨停今天去向", settleTable)}
    ${renderHistory(paper)}`;
}

function renderPreopen(d) {
  const sess = liveSession();
  if (sess.id === "closed" || sess.id === "weekend") return renderClose(d, sess);
  return renderAuction(d, sess);
}

function render() {
  const d = state.live;
  const y = state.keepScroll ? window.scrollY : 0;
  state.rendering = true;
  try {
  paintClock();
  const root = $("#page");
  if (state.loading && !d) {
    root.innerHTML = `<h1>正在拉数据</h1><p class="lede">涨停池、昨日连板、今开/竞价。</p>`;
    return;
  }
  if (state.error && !d) {
    root.innerHTML = `<h1>短线选股</h1><p class="lede">${state.error}</p><button class="btn" id="refresh-live">重试</button>`;
    bind();
    return;
  }
  if (!d) {
    root.innerHTML = `<p class="lede">尚未加载。</p>`;
    return;
  }
  const view = activeView();
  const sess = liveSession();
  root.innerHTML = `
    <div class="play-head">
      <div>
        <div class="mode-tabs">
          <button class="${view === "preopen" ? "on" : ""}" data-view="preopen">开盘前<span class="tab-when">${sess.preopenWhen}</span></button>
          <button class="${view === "open" ? "on" : ""}" data-view="open">开盘后<span class="tab-when">${sess.openWhen}</span></button>
        </div>
        <div class="meta" id="sess-hint">${sess.hint} 现在是「${sess.label}」。</div>
        ${state.notice || d.fetch_error || d.ledger_error ? `<div class="meta" style="color:var(--gold)">${state.notice || ("刷新警告：" + (d.fetch_error || d.ledger_error))}</div>` : ""}
      </div>
      <button class="btn" id="refresh-live">${state.loading ? "刷新中…" : "刷新数据"}</button>
    </div>
    ${view === "preopen" ? renderPreopen(d) : renderOpen(d)}
    <p class="warn-line">${d.disclaimer || ""}</p>`;
  bind();
  } finally {
    state.rendering = false;
    if (state.keepScroll) window.scrollTo(0, y);
    state.keepScroll = false;
  }
}

function bind() {
  const btn = $("#refresh-live");
  if (btn) btn.onclick = () => loadLive(true);
  const aiBtn = $("#run-ai");
  if (aiBtn) aiBtn.onclick = () => runAi();
  document.querySelectorAll("[data-view]").forEach((b) => {
    b.onclick = () => { state.view = b.dataset.view; render(); };
  });
  document.querySelectorAll("[data-code]").forEach((el) => {
    el.onclick = () => { state.selected = el.dataset.code; state.keepScroll = true; render(); };
  });
  document.querySelectorAll("details[data-fold]").forEach((el) => {
    el.addEventListener("toggle", () => { state.fold[el.dataset.fold] = el.open; });
  });
  const one = document.querySelector("[data-fold-one]");
  if (one) {
    one.onclick = (ev) => {
      ev.preventDefault();
      ev.stopPropagation();
      state.fold.oneBoard = !state.fold.oneBoard;
      state.keepScroll = true;
      render();
    };
  }
}

loadLive(false);
paintClock();
if (!window.__clockOn) {
  window.__clockOn = true;
  setInterval(paintClock, 1000);
}
