import { jsxs as l, jsx as e } from "react/jsx-runtime";
import { useState as f, useMemo as g } from "react";
import { G as u } from "./GlassPanel-S_ADyiYR.js";
import { C as v } from "./Chart-6fGZGgP8.js";
import { S as N } from "./route-host-CUL1oI6Z.js";
import { u as w, a as y, b as _, c as C } from "./hooks-UFUMZFGB.js";
import { n as k } from "./navigation-BDd1HkpE.js";
import { f as p } from "./format-BM7Gaq4w.js";
import { e as S, m as D } from "./game-assets-CWuRxGFH.js";
function b({
  label: a,
  value: t,
  sub: s,
  sub2: r,
  borderColor: n
}) {
  return /* @__PURE__ */ l(u, { className: `!p-4 border-l-4 ${n}`, children: [
    /* @__PURE__ */ e("div", { className: "text-[10px] uppercase tracking-widest text-slate-500 font-bold mb-1", children: a }),
    /* @__PURE__ */ e("div", { className: "text-2xl font-black font-mono text-white", children: t }),
    s && /* @__PURE__ */ e("div", { className: "text-[11px] text-slate-500 mt-1", children: s }),
    r && /* @__PURE__ */ e("div", { className: "text-[11px] text-slate-500", children: r })
  ] });
}
function $() {
  const { data: a } = y();
  if (!a)
    return /* @__PURE__ */ e(u, { className: "!p-4", children: /* @__PURE__ */ l("div", { className: "flex items-center gap-3", children: [
      /* @__PURE__ */ e("div", { className: "w-10 h-10 rounded-lg bg-slate-700/50 animate-pulse" }),
      /* @__PURE__ */ l("div", { className: "flex-1 space-y-2", children: [
        /* @__PURE__ */ e("div", { className: "h-3 w-24 bg-slate-700/50 rounded animate-pulse" }),
        /* @__PURE__ */ e("div", { className: "h-3 w-40 bg-slate-700/50 rounded animate-pulse" })
      ] })
    ] }) });
  const t = a.game_server, s = t.online ? { text: "ONLINE", cls: "bg-emerald-500/20 text-emerald-400" } : { text: "OFFLINE", cls: "bg-red-500/20 text-red-400" };
  return /* @__PURE__ */ e(u, { className: `!p-4 ${t.online && t.player_count > 0 ? "border-emerald-500/30" : ""}`, children: /* @__PURE__ */ l("div", { className: "flex items-center gap-3", children: [
    /* @__PURE__ */ e("div", { className: "w-10 h-10 rounded-lg bg-slate-800 overflow-hidden shrink-0", children: t.online && t.map ? /* @__PURE__ */ e("img", { src: D(t.map), alt: t.map, className: "w-full h-full object-cover", onError: (r) => {
      r.currentTarget.parentElement.textContent = "🖥";
    } }) : /* @__PURE__ */ e("div", { className: "w-full h-full flex items-center justify-center text-slate-400 text-lg", children: "🖥" }) }),
    /* @__PURE__ */ l("div", { className: "flex-1 min-w-0", children: [
      /* @__PURE__ */ l("div", { className: "flex items-center gap-2 mb-0.5", children: [
        /* @__PURE__ */ e("span", { className: "text-xs font-bold text-slate-500 uppercase", children: "Game Server" }),
        /* @__PURE__ */ e("span", { className: `px-2 py-0.5 rounded text-[10px] font-bold ${s.cls}`, children: s.text })
      ] }),
      t.online ? /* @__PURE__ */ l("div", { className: "text-sm text-slate-400 truncate", children: [
        /* @__PURE__ */ e("span", { className: "text-white font-semibold", children: t.hostname || "Server" }),
        /* @__PURE__ */ e("span", { className: "text-slate-500 mx-1", children: "·" }),
        /* @__PURE__ */ e("span", { className: "text-cyan-400", children: t.map }),
        /* @__PURE__ */ e("span", { className: "text-slate-500 mx-1", children: "·" }),
        t.player_count > 0 ? /* @__PURE__ */ e("span", { children: t.players.map((r) => r.name).join(", ") }) : /* @__PURE__ */ l("span", { className: "text-slate-500", children: [
          t.player_count,
          "/",
          t.max_players,
          " players"
        ] })
      ] }) : /* @__PURE__ */ e("div", { className: "text-sm text-red-400/70", children: t.error || "Not responding" })
    ] }),
    t.online && t.player_count > 0 && /* @__PURE__ */ l("div", { className: "text-right", children: [
      /* @__PURE__ */ e("div", { className: "text-2xl font-black text-white", children: t.player_count }),
      /* @__PURE__ */ e("div", { className: "text-[10px] text-slate-500 uppercase", children: "Players" })
    ] })
  ] }) });
}
function T() {
  const { data: a } = y();
  if (!a) return null;
  const t = a.voice_channel, s = t.count > 0;
  return /* @__PURE__ */ e(u, { className: `!p-4 ${s ? "border-purple-500/30" : ""}`, children: /* @__PURE__ */ l("div", { className: "flex items-center gap-3", children: [
    /* @__PURE__ */ e("div", { className: "w-10 h-10 rounded-lg bg-slate-800 flex items-center justify-center text-slate-400 text-lg", children: "🎙" }),
    /* @__PURE__ */ l("div", { className: "flex-1 min-w-0", children: [
      /* @__PURE__ */ l("div", { className: "flex items-center gap-2 mb-0.5", children: [
        /* @__PURE__ */ e("span", { className: "text-xs font-bold text-slate-500 uppercase", children: "Voice Channel" }),
        /* @__PURE__ */ e("span", { className: `px-2 py-0.5 rounded text-[10px] font-bold ${s ? "bg-purple-500/20 text-purple-400" : "bg-slate-700 text-slate-400"}`, children: s ? "ACTIVE" : "EMPTY" })
      ] }),
      /* @__PURE__ */ e("div", { className: "text-sm text-slate-400", children: s ? /* @__PURE__ */ e("span", { className: "text-white", children: t.members.map((r) => r.name).join(", ") }) : "No one in voice" })
    ] }),
    /* @__PURE__ */ l("div", { className: "text-right", children: [
      /* @__PURE__ */ e("div", { className: "text-2xl font-black text-white", children: t.count }),
      /* @__PURE__ */ e("div", { className: "text-[10px] text-slate-500 uppercase", children: "Online" })
    ] })
  ] }) });
}
function L() {
  const { data: a } = _();
  if (!a) return null;
  const t = new Date(a.start_date), s = new Date(a.end_date), r = /* @__PURE__ */ new Date(), n = Math.max(1, (s.getTime() - t.getTime()) / 864e5), c = Math.max(0, (r.getTime() - t.getTime()) / 864e5), x = Math.min(100, c / n * 100);
  return /* @__PURE__ */ l(u, { className: "!p-5 border-l-4 border-amber-400", children: [
    /* @__PURE__ */ e("div", { className: "text-xs font-bold text-slate-500 uppercase tracking-wider", children: "Current Season" }),
    /* @__PURE__ */ e("div", { className: "text-2xl font-black text-white mt-1", children: a.name }),
    /* @__PURE__ */ e("div", { className: "w-full bg-slate-800 h-2 rounded-full overflow-hidden mt-3", children: /* @__PURE__ */ e("div", { className: "bg-amber-400 h-full transition-all", style: { width: `${x}%` } }) }),
    /* @__PURE__ */ l("div", { className: "flex justify-between text-[10px] text-slate-500 mt-2", children: [
      /* @__PURE__ */ l("span", { children: [
        t.toLocaleDateString(),
        " – ",
        s.toLocaleDateString()
      ] }),
      /* @__PURE__ */ l("span", { children: [
        a.days_left,
        " days left"
      ] })
    ] })
  ] });
}
function A({ days: a }) {
  const { data: t, isLoading: s } = C(a), r = g(() => t?.dates ? {
    labels: t.dates.map((o) => (/* @__PURE__ */ new Date(o + "T00:00:00")).toLocaleDateString(void 0, { month: "short", day: "numeric" })),
    datasets: [
      {
        data: t.rounds,
        borderColor: "#3b82f6",
        backgroundColor: "rgba(59,130,246,0.1)",
        borderWidth: 2,
        tension: 0.3,
        fill: !0,
        pointRadius: a <= 14 ? 3 : 0,
        pointBackgroundColor: "#3b82f6"
      }
    ]
  } : null, [t, a]), n = g(() => t?.dates ? {
    labels: t.dates.map((o) => (/* @__PURE__ */ new Date(o + "T00:00:00")).toLocaleDateString(void 0, { month: "short", day: "numeric" })),
    datasets: [
      {
        data: t.active_players,
        borderColor: "#06b6d4",
        backgroundColor: "rgba(6,182,212,0.12)",
        borderWidth: 2,
        tension: 0.3,
        fill: !0,
        pointRadius: a <= 14 ? 3 : 0,
        pointBackgroundColor: "#06b6d4"
      }
    ]
  } : null, [t, a]), c = g(() => {
    if (!t?.map_distribution) return null;
    const m = Object.entries(t.map_distribution).filter(([d, h]) => d.trim() && h > 0).sort((d, h) => h[1] - d[1]).slice(0, 8);
    if (m.length === 0) return null;
    const o = ["#3b82f6", "#06b6d4", "#8b5cf6", "#10b981", "#f43f5e", "#f59e0b", "#ec4899", "#6366f1"];
    return {
      labels: m.map(([d]) => d),
      datasets: [
        {
          data: m.map(([, d]) => d),
          backgroundColor: m.map((d, h) => o[h % o.length] + "bf"),
          borderColor: m.map((d, h) => o[h % o.length]),
          borderWidth: 1
        }
      ]
    };
  }, [t]), x = g(
    () => ({
      plugins: {
        legend: { display: !1 },
        tooltip: {
          backgroundColor: "rgba(15,23,42,0.9)",
          borderColor: "rgba(255,255,255,0.1)",
          borderWidth: 1
        }
      },
      scales: {
        x: {
          grid: { color: "rgba(255,255,255,0.04)" },
          ticks: { color: "#64748b", font: { size: 10 }, maxTicksLimit: 7 }
        },
        y: {
          grid: { color: "rgba(255,255,255,0.04)" },
          ticks: { color: "#64748b", font: { size: 10 } },
          beginAtZero: !0
        }
      }
    }),
    []
  ), i = g(
    () => ({
      indexAxis: "y",
      plugins: {
        legend: { display: !1 },
        tooltip: {
          backgroundColor: "rgba(15,23,42,0.9)",
          borderColor: "rgba(255,255,255,0.1)",
          borderWidth: 1
        }
      },
      scales: {
        x: {
          grid: { color: "rgba(255,255,255,0.04)" },
          ticks: { color: "#64748b", font: { size: 10 } },
          beginAtZero: !0
        },
        y: {
          grid: { display: !1 },
          ticks: { color: "#e2e8f0", font: { size: 10 } }
        }
      }
    }),
    []
  );
  return s ? /* @__PURE__ */ e(N, { variant: "card", count: 3 }) : /* @__PURE__ */ l("div", { className: "grid grid-cols-1 md:grid-cols-3 gap-4", children: [
    /* @__PURE__ */ l(u, { children: [
      /* @__PURE__ */ e("h3", { className: "text-sm font-bold text-white mb-1", children: "Rounds per Day" }),
      /* @__PURE__ */ e("p", { className: "text-[11px] text-slate-500 mb-3", children: "Daily round activity" }),
      r ? /* @__PURE__ */ e(v, { type: "line", data: r, options: x, height: "200px" }) : /* @__PURE__ */ e("div", { className: "h-[200px] flex items-center justify-center text-xs text-slate-500", children: "No data" })
    ] }),
    /* @__PURE__ */ l(u, { children: [
      /* @__PURE__ */ e("h3", { className: "text-sm font-bold text-white mb-1", children: "Active Players per Day" }),
      /* @__PURE__ */ e("p", { className: "text-[11px] text-slate-500 mb-3", children: "Unique players each day" }),
      n ? /* @__PURE__ */ e(v, { type: "line", data: n, options: x, height: "200px" }) : /* @__PURE__ */ e("div", { className: "h-[200px] flex items-center justify-center text-xs text-slate-500", children: "No data" })
    ] }),
    /* @__PURE__ */ l(u, { children: [
      /* @__PURE__ */ e("h3", { className: "text-sm font-bold text-white mb-1", children: "Map Distribution" }),
      /* @__PURE__ */ e("p", { className: "text-[11px] text-slate-500 mb-3", children: "Most played maps" }),
      c ? /* @__PURE__ */ e(v, { type: "bar", data: c, options: i, height: "200px" }) : /* @__PURE__ */ e("div", { className: "h-[200px] flex items-center justify-center text-xs text-slate-500", children: "No data" })
    ] })
  ] });
}
function j() {
  const [a, t] = f(""), [s, r] = f([]), [n, c] = f(!1), x = async (i) => {
    if (t(i), i.length < 2) {
      r([]), c(!1);
      return;
    }
    try {
      const m = await fetch(`/api/search?q=${encodeURIComponent(i)}&limit=8`);
      if (m.ok) {
        const o = await m.json();
        r(Array.isArray(o) ? o : o.players || []), c(!0);
      }
    } catch {
    }
  };
  return /* @__PURE__ */ l("div", { className: "relative max-w-xl mx-auto", children: [
    /* @__PURE__ */ e("div", { className: "absolute -inset-1 bg-gradient-to-r from-blue-500 to-purple-500 rounded-xl blur opacity-25" }),
    /* @__PURE__ */ l("div", { className: "relative flex items-center bg-slate-900 border border-white/10 rounded-xl p-2 shadow-2xl", children: [
      /* @__PURE__ */ e("span", { className: "ml-3 text-slate-400 text-lg", children: "🔍" }),
      /* @__PURE__ */ e(
        "input",
        {
          type: "text",
          value: a,
          onChange: (i) => x(i.target.value),
          onBlur: () => setTimeout(() => c(!1), 200),
          onFocus: () => {
            s.length > 0 && c(!0);
          },
          className: "w-full bg-transparent border-none text-white placeholder-slate-500 focus:ring-0 focus:outline-none px-4 py-2 text-lg font-medium",
          placeholder: "Search player (e.g. BAMBAM)..."
        }
      )
    ] }),
    n && s.length > 0 && /* @__PURE__ */ e("div", { className: "absolute top-full left-0 right-0 mt-2 bg-slate-900/95 backdrop-blur-xl border border-white/10 rounded-xl shadow-2xl overflow-hidden z-50", children: s.map((i) => /* @__PURE__ */ e(
      "button",
      {
        className: "w-full text-left px-4 py-3 hover:bg-white/5 transition-colors border-b border-white/5 last:border-0",
        onMouseDown: () => {
          k(`#/profile?name=${encodeURIComponent(i.name)}`), c(!1), t("");
        },
        children: /* @__PURE__ */ e("span", { className: "text-sm font-bold text-white", children: i.name })
      },
      i.guid || i.name
    )) })
  ] });
}
function G() {
  const { data: a, isLoading: t } = w(), [s, r] = f(14);
  return /* @__PURE__ */ l("div", { children: [
    /* @__PURE__ */ l("div", { className: "relative pt-12 pb-20 text-center", children: [
      /* @__PURE__ */ e("div", { className: "absolute top-0 left-1/2 -translate-x-1/2 w-[800px] h-[500px] bg-blue-500/20 rounded-full blur-[120px] -z-10" }),
      /* @__PURE__ */ l("div", { className: "inline-flex items-center gap-2 px-3 py-1 rounded-full bg-white/5 border border-white/10 text-cyan-400 text-xs font-bold mb-8", children: [
        /* @__PURE__ */ l("span", { className: "relative flex h-2 w-2", children: [
          /* @__PURE__ */ e("span", { className: "animate-ping absolute inline-flex h-full w-full rounded-full bg-cyan-400 opacity-75" }),
          /* @__PURE__ */ e("span", { className: "relative inline-flex rounded-full h-2 w-2 bg-cyan-400" })
        ] }),
        "SEASON 4 IS LIVE"
      ] }),
      /* @__PURE__ */ e("img", { src: S(), alt: "Enemy Territory", className: "h-16 md:h-20 mx-auto mb-6 opacity-80 drop-shadow-2xl", onError: (n) => {
        n.currentTarget.style.display = "none";
      } }),
      /* @__PURE__ */ l("h1", { className: "text-6xl md:text-8xl font-black text-white tracking-tight mb-6 leading-tight", children: [
        "TRACK YOUR ",
        /* @__PURE__ */ e("br", {}),
        /* @__PURE__ */ e("span", { className: "text-transparent bg-clip-text bg-gradient-to-r from-blue-500 via-cyan-400 to-purple-500", children: "LEGACY" })
      ] }),
      /* @__PURE__ */ e("p", { className: "text-lg text-slate-400 mb-10 max-w-2xl mx-auto leading-relaxed", children: "Track every frag, analyze every round, celebrate every victory." }),
      /* @__PURE__ */ e(j, {})
    ] }),
    t ? /* @__PURE__ */ e(N, { variant: "card", count: 6 }) : a ? /* @__PURE__ */ l("div", { className: "grid grid-cols-1 sm:grid-cols-2 md:grid-cols-3 gap-4 mb-8", children: [
      /* @__PURE__ */ e(
        b,
        {
          label: "Rounds Tracked",
          value: p(a.rounds),
          sub: a.rounds_since ? `Since ${new Date(a.rounds_since).toLocaleDateString()}` : void 0,
          sub2: `Last ${a.window_days}d: ${p(a.rounds_14d)}`,
          borderColor: "border-blue-500/60"
        }
      ),
      /* @__PURE__ */ e(
        b,
        {
          label: `Active Players (${a.window_days}d)`,
          value: p(a.players_14d),
          sub: `All-time: ${p(a.players_all_time)}`,
          borderColor: "border-cyan-500/60"
        }
      ),
      /* @__PURE__ */ e(
        b,
        {
          label: "Most Active (All-time)",
          value: a.most_active_overall?.name || "--",
          sub: a.most_active_overall ? `${a.most_active_overall.rounds} rounds` : void 0,
          borderColor: "border-amber-500/60"
        }
      ),
      /* @__PURE__ */ e(
        b,
        {
          label: `Most Active (${a.window_days}d)`,
          value: a.most_active_14d?.name || "--",
          sub: a.most_active_14d ? `${a.most_active_14d.rounds} rounds` : void 0,
          borderColor: "border-emerald-500/60"
        }
      ),
      /* @__PURE__ */ e(
        b,
        {
          label: "Gaming Sessions",
          value: p(a.sessions),
          sub: `Last ${a.window_days}d: ${p(a.sessions_14d)}`,
          borderColor: "border-purple-500/60"
        }
      ),
      /* @__PURE__ */ e(
        b,
        {
          label: "Total Kills",
          value: p(a.total_kills),
          sub: `Last ${a.window_days}d: ${p(a.total_kills_14d)}`,
          borderColor: "border-rose-500/60"
        }
      )
    ] }) : null,
    /* @__PURE__ */ l("div", { className: "grid grid-cols-1 md:grid-cols-2 gap-4 mb-8", children: [
      /* @__PURE__ */ e($, {}),
      /* @__PURE__ */ e(T, {})
    ] }),
    /* @__PURE__ */ e("div", { className: "mb-8", children: /* @__PURE__ */ e(L, {}) }),
    /* @__PURE__ */ l("div", { className: "mb-8", children: [
      /* @__PURE__ */ l("div", { className: "flex items-center justify-between mb-4", children: [
        /* @__PURE__ */ l("div", { children: [
          /* @__PURE__ */ e("h2", { className: "text-sm font-bold text-white uppercase tracking-wider", children: "Community Insights" }),
          /* @__PURE__ */ e("span", { className: "text-[10px] text-slate-600 uppercase tracking-widest", children: "Trends" })
        ] }),
        /* @__PURE__ */ e("div", { className: "flex gap-1", children: [14, 30, 90].map((n) => /* @__PURE__ */ l(
          "button",
          {
            onClick: () => r(n),
            className: `px-2.5 py-1 rounded text-xs font-bold transition ${s === n ? "bg-blue-500/20 text-blue-400" : "bg-slate-700 text-slate-400 hover:bg-slate-600"}`,
            children: [
              n,
              "d"
            ]
          },
          n
        )) })
      ] }),
      /* @__PURE__ */ e(A, { days: s })
    ] })
  ] });
}
export {
  G as default
};
