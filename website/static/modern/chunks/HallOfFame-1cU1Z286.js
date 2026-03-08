import { jsxs as l, jsx as e } from "react/jsx-runtime";
import { useState as f } from "react";
import { h as u } from "./hooks-UFUMZFGB.js";
import { G as x } from "./GlassCard-DKnnuJMt.js";
import { P as d } from "./PageHeader-D4CVo02x.js";
import { S as h } from "./FilterBar-ClDZvrPF.js";
import { S as v, c } from "./route-host-CUL1oI6Z.js";
import { f as b } from "./format-BM7Gaq4w.js";
import { a as y } from "./navigation-BDd1HkpE.js";
import { c as p } from "./createLucideIcon-CP-mMPfa.js";
import { T as N, Z as _ } from "./zap-DJKgNY7d.js";
import { C as k } from "./crown-BFDJEIu0.js";
import { B as g } from "./bomb-BF5aFt_5.js";
import { a as S, S as M } from "./swords-CDpW6o_n.js";
import { H as w } from "./heart-Be63oR7h.js";
import { S as T } from "./skull-BdPXKOvx.js";
import { G as C } from "./gamepad-2-CX3iu8NC.js";
import { T as P } from "./trophy-DLp0OdqF.js";
const D = [
  [
    "path",
    {
      d: "M20 13c0 5-3.5 7.5-7.66 8.95a1 1 0 0 1-.67-.01C7.5 20.5 4 18 4 13V6a1 1 0 0 1 1-1c2 0 4.5-1.2 6.24-2.72a1.17 1.17 0 0 1 1.52 0C14.51 3.81 17 5 19 5a1 1 0 0 1 1 1z",
      key: "oel41y"
    }
  ],
  ["path", { d: "M12 8v4", key: "1got3b" }],
  ["path", { d: "M12 16h.01", key: "1drbdi" }]
], F = p("shield-alert", D);
const H = [
  ["line", { x1: "10", x2: "14", y1: "2", y2: "2", key: "14vaq8" }],
  ["line", { x1: "12", x2: "15", y1: "14", y2: "11", key: "17fdiu" }],
  ["circle", { cx: "12", cy: "14", r: "8", key: "1e1u0o" }]
], L = p("timer", H), A = {
  most_active: { label: "Most Active", icon: C, color: "text-blue-400", bg: "bg-blue-400/10" },
  most_damage: { label: "Most Damage", icon: _, color: "text-amber-400", bg: "bg-amber-400/10" },
  most_kills: { label: "Most Kills", icon: T, color: "text-rose-500", bg: "bg-rose-500/10" },
  most_revives: { label: "Most Revives", icon: w, color: "text-cyan-500", bg: "bg-cyan-500/10" },
  most_xp: { label: "Most XP", icon: M, color: "text-amber-300", bg: "bg-amber-300/10" },
  most_assists: { label: "Most Assists", icon: S, color: "text-purple-400", bg: "bg-purple-400/10" },
  most_deaths: { label: "Most Deaths", icon: F, color: "text-slate-400", bg: "bg-slate-500/10" },
  most_selfkills: { label: "Most Selfkills", icon: g, color: "text-orange-400", bg: "bg-orange-400/10" },
  most_full_selfkills: { label: "Full Selfkills", icon: g, color: "text-red-400", bg: "bg-red-400/10" },
  most_wins: { label: "Most Wins", icon: k, color: "text-emerald-400", bg: "bg-emerald-400/10" },
  most_dpm: { label: "Best DPM", icon: N, color: "text-indigo-400", bg: "bg-indigo-400/10" },
  most_consecutive_games: { label: "Longest Streak", icon: L, color: "text-brand-cyan", bg: "bg-brand-cyan/10" }
}, j = [
  { value: "all_time", label: "All Time" },
  { value: "7d", label: "Last 7 Days" },
  { value: "14d", label: "Last 14 Days" },
  { value: "30d", label: "Last 30 Days" },
  { value: "90d", label: "Last 90 Days" },
  { value: "season", label: "Current Season" }
];
function G({ category: s, entries: r }) {
  const a = A[s] ?? { label: s, icon: P, color: "text-slate-400", bg: "bg-slate-700/50" }, m = a.icon;
  if (!r?.length) return null;
  const n = r[0];
  return /* @__PURE__ */ l(x, { className: "relative overflow-hidden group", children: [
    /* @__PURE__ */ e("div", { className: "absolute top-0 right-0 p-4 opacity-10 group-hover:opacity-20 transition-opacity", children: /* @__PURE__ */ e(m, { className: c("w-16 h-16", a.color) }) }),
    /* @__PURE__ */ l("div", { className: "flex items-center gap-3 mb-4", children: [
      /* @__PURE__ */ e("div", { className: c("w-10 h-10 rounded-lg flex items-center justify-center", a.bg), children: /* @__PURE__ */ e(m, { className: c("w-5 h-5", a.color) }) }),
      /* @__PURE__ */ e("div", { className: "text-sm font-bold text-slate-400 uppercase tracking-wider", children: a.label })
    ] }),
    /* @__PURE__ */ l("div", { className: "mb-4", children: [
      /* @__PURE__ */ e("div", { className: "text-3xl font-black text-white tracking-tight", children: b(n.value) }),
      /* @__PURE__ */ e("div", { className: "text-xs text-slate-500", children: n.unit })
    ] }),
    /* @__PURE__ */ e("div", { className: "space-y-1.5 mb-3", children: r.slice(0, 5).map((o, t) => /* @__PURE__ */ l("div", { className: "flex items-center justify-between text-sm", children: [
      /* @__PURE__ */ l("div", { className: "flex items-center gap-2 min-w-0", children: [
        /* @__PURE__ */ e("span", { className: c(
          "font-mono text-xs w-5",
          t === 0 ? "text-amber-400" : t === 1 ? "text-slate-300" : t === 2 ? "text-amber-600" : "text-slate-500"
        ), children: t + 1 }),
        /* @__PURE__ */ e(
          "button",
          {
            className: "text-white hover:text-blue-400 transition truncate font-medium",
            onClick: (i) => {
              i.stopPropagation(), y(o.player_name);
            },
            children: o.player_name
          }
        )
      ] }),
      /* @__PURE__ */ e("span", { className: c("font-mono text-xs", t === 0 ? a.color : "text-slate-400"), children: b(o.value) })
    ] }, o.player_guid)) })
  ] });
}
function ae() {
  const [s, r] = f("all_time"), { data: a, isLoading: m, isError: n } = u(s);
  if (m)
    return /* @__PURE__ */ l("div", { className: "mt-6", children: [
      /* @__PURE__ */ e(d, { title: "Hall of Fame", subtitle: "Top players across all categories" }),
      /* @__PURE__ */ e(v, { variant: "card", count: 8 })
    ] });
  if (n)
    return /* @__PURE__ */ l("div", { className: "mt-6", children: [
      /* @__PURE__ */ e(d, { title: "Hall of Fame", subtitle: "Top players across all categories" }),
      /* @__PURE__ */ e("div", { className: "text-center text-red-400 py-12", children: "Failed to load hall of fame." })
    ] });
  const o = a?.categories ?? {}, t = Object.keys(o);
  return /* @__PURE__ */ l("div", { className: "mt-6", children: [
    /* @__PURE__ */ e(d, { title: "Hall of Fame", subtitle: "Top players across all categories", children: /* @__PURE__ */ e(
      h,
      {
        label: "Period",
        value: s,
        onChange: r,
        options: j,
        allLabel: "All Time"
      }
    ) }),
    t.length === 0 ? /* @__PURE__ */ e("div", { className: "text-center text-slate-400 py-12", children: "No hall of fame data available." }) : /* @__PURE__ */ e("div", { className: "grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4 gap-4", children: t.map((i) => /* @__PURE__ */ e(G, { category: i, entries: o[i] }, i)) })
  ] });
}
export {
  ae as default
};
