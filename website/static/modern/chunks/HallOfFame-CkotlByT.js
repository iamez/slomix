import { r as g, j as e, S as p, c as i } from "./route-host-Ba3v8uFM.js";
import { j as f } from "./hooks-CyQgvbI9.js";
import { G as u } from "./GlassCard-C53TzD-y.js";
import { P as m } from "./PageHeader-CQ7BTOQj.js";
import { S as h } from "./FilterBar-BVrgiC-n.js";
import { f as d } from "./format-BM7Gaq4w.js";
import { a as v } from "./navigation-BDd1HkpE.js";
import { c as b } from "./createLucideIcon-BebMLfof.js";
import { T as y } from "./target-CZv2kTPB.js";
import { C as j } from "./crown-DSN73Z2P.js";
import { B as x, H as N } from "./heart-BlqPAczq.js";
import { S as _ } from "./swords-BNai6XKn.js";
import { S as k } from "./star-DzJ3yYFk.js";
import { S } from "./skull-BhM2GlAn.js";
import { Z as M } from "./zap-Chh6-OiF.js";
import { G as w } from "./gamepad-2-DXqvfHtG.js";
import { T } from "./trophy-f4_RKZnn.js";
const C = [
  [
    "path",
    {
      d: "M20 13c0 5-3.5 7.5-7.66 8.95a1 1 0 0 1-.67-.01C7.5 20.5 4 18 4 13V6a1 1 0 0 1 1-1c2 0 4.5-1.2 6.24-2.72a1.17 1.17 0 0 1 1.52 0C14.51 3.81 17 5 19 5a1 1 0 0 1 1 1z",
      key: "oel41y"
    }
  ],
  ["path", { d: "M12 8v4", key: "1got3b" }],
  ["path", { d: "M12 16h.01", key: "1drbdi" }]
], P = b("shield-alert", C);
const D = [
  ["line", { x1: "10", x2: "14", y1: "2", y2: "2", key: "14vaq8" }],
  ["line", { x1: "12", x2: "15", y1: "14", y2: "11", key: "17fdiu" }],
  ["circle", { cx: "12", cy: "14", r: "8", key: "1e1u0o" }]
], F = b("timer", D), H = {
  most_active: { label: "Most Active", icon: w, color: "text-blue-400", bg: "bg-blue-400/10" },
  most_damage: { label: "Most Damage", icon: M, color: "text-amber-400", bg: "bg-amber-400/10" },
  most_kills: { label: "Most Kills", icon: S, color: "text-rose-500", bg: "bg-rose-500/10" },
  most_revives: { label: "Most Revives", icon: N, color: "text-cyan-500", bg: "bg-cyan-500/10" },
  most_xp: { label: "Most XP", icon: k, color: "text-amber-300", bg: "bg-amber-300/10" },
  most_assists: { label: "Most Assists", icon: _, color: "text-purple-400", bg: "bg-purple-400/10" },
  most_deaths: { label: "Most Deaths", icon: P, color: "text-slate-400", bg: "bg-slate-500/10" },
  most_selfkills: { label: "Most Selfkills", icon: x, color: "text-orange-400", bg: "bg-orange-400/10" },
  most_full_selfkills: { label: "Full Selfkills", icon: x, color: "text-red-400", bg: "bg-red-400/10" },
  most_wins: { label: "Most Wins", icon: j, color: "text-emerald-400", bg: "bg-emerald-400/10" },
  most_dpm: { label: "Best DPM", icon: y, color: "text-indigo-400", bg: "bg-indigo-400/10" },
  most_consecutive_games: { label: "Longest Streak", icon: F, color: "text-brand-cyan", bg: "bg-brand-cyan/10" }
}, L = [
  { value: "all_time", label: "All Time" },
  { value: "7d", label: "Last 7 Days" },
  { value: "14d", label: "Last 14 Days" },
  { value: "30d", label: "Last 30 Days" },
  { value: "90d", label: "Last 90 Days" },
  { value: "season", label: "Current Season" }
];
function A({ category: l, entries: o }) {
  const t = H[l] ?? { label: l, icon: T, color: "text-slate-400", bg: "bg-slate-700/50" }, c = t.icon;
  if (!o?.length) return null;
  const n = o[0];
  return /* @__PURE__ */ e.jsxs(u, { className: "relative overflow-hidden group", children: [
    /* @__PURE__ */ e.jsx("div", { className: "absolute top-0 right-0 p-4 opacity-10 group-hover:opacity-20 transition-opacity", children: /* @__PURE__ */ e.jsx(c, { className: i("w-16 h-16", t.color) }) }),
    /* @__PURE__ */ e.jsxs("div", { className: "flex items-center gap-3 mb-4", children: [
      /* @__PURE__ */ e.jsx("div", { className: i("w-10 h-10 rounded-lg flex items-center justify-center", t.bg), children: /* @__PURE__ */ e.jsx(c, { className: i("w-5 h-5", t.color) }) }),
      /* @__PURE__ */ e.jsx("div", { className: "text-sm font-bold text-slate-400 uppercase tracking-wider", children: t.label })
    ] }),
    /* @__PURE__ */ e.jsxs("div", { className: "mb-4", children: [
      /* @__PURE__ */ e.jsx("div", { className: "text-3xl font-black text-white tracking-tight", children: d(n.value) }),
      /* @__PURE__ */ e.jsx("div", { className: "text-xs text-slate-500", children: n.unit })
    ] }),
    /* @__PURE__ */ e.jsx("div", { className: "space-y-1.5 mb-3", children: o.slice(0, 5).map((s, a) => /* @__PURE__ */ e.jsxs("div", { className: "flex items-center justify-between text-sm", children: [
      /* @__PURE__ */ e.jsxs("div", { className: "flex items-center gap-2 min-w-0", children: [
        /* @__PURE__ */ e.jsx("span", { className: i(
          "font-mono text-xs w-5",
          a === 0 ? "text-amber-400" : a === 1 ? "text-slate-300" : a === 2 ? "text-amber-600" : "text-slate-500"
        ), children: a + 1 }),
        /* @__PURE__ */ e.jsx(
          "button",
          {
            className: "text-white hover:text-blue-400 transition truncate font-medium",
            onClick: (r) => {
              r.stopPropagation(), v(s.player_name);
            },
            children: s.player_name
          }
        )
      ] }),
      /* @__PURE__ */ e.jsx("span", { className: i("font-mono text-xs", a === 0 ? t.color : "text-slate-400"), children: d(s.value) })
    ] }, s.player_guid)) })
  ] });
}
function U() {
  const [l, o] = g.useState("all_time"), { data: t, isLoading: c, isError: n } = f(l);
  if (c)
    return /* @__PURE__ */ e.jsxs("div", { className: "mt-6", children: [
      /* @__PURE__ */ e.jsx(m, { title: "Hall of Fame", subtitle: "Top players across all categories" }),
      /* @__PURE__ */ e.jsx(p, { variant: "card", count: 8 })
    ] });
  if (n)
    return /* @__PURE__ */ e.jsxs("div", { className: "mt-6", children: [
      /* @__PURE__ */ e.jsx(m, { title: "Hall of Fame", subtitle: "Top players across all categories" }),
      /* @__PURE__ */ e.jsx("div", { className: "text-center text-red-400 py-12", children: "Failed to load hall of fame." })
    ] });
  const s = t?.categories ?? {}, a = Object.keys(s);
  return /* @__PURE__ */ e.jsxs("div", { className: "mt-6", children: [
    /* @__PURE__ */ e.jsx(m, { title: "Hall of Fame", subtitle: "Top players across all categories", children: /* @__PURE__ */ e.jsx(
      h,
      {
        label: "Period",
        value: l,
        onChange: o,
        options: L,
        allLabel: "All Time"
      }
    ) }),
    a.length === 0 ? /* @__PURE__ */ e.jsx("div", { className: "text-center text-slate-400 py-12", children: "No hall of fame data available." }) : /* @__PURE__ */ e.jsx("div", { className: "grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4 gap-4", children: a.map((r) => /* @__PURE__ */ e.jsx(A, { category: r, entries: s[r] }, r)) })
  ] });
}
export {
  U as default
};
