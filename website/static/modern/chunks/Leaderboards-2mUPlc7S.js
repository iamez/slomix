import { jsxs as t, jsx as a } from "react/jsx-runtime";
import { useState as c } from "react";
import { f as g } from "./hooks-UFUMZFGB.js";
import { D as N } from "./DataTable-C9DYv6yb.js";
import { P as n } from "./PageHeader-D4CVo02x.js";
import { F as L } from "./FilterBar-ClDZvrPF.js";
import { S as D, c as d } from "./route-host-CUL1oI6Z.js";
import { f as r } from "./format-BM7Gaq4w.js";
import { a as p } from "./navigation-BDd1HkpE.js";
import { r as S } from "./game-assets-CWuRxGFH.js";
import { Z as m, T as b } from "./zap-DJKgNY7d.js";
import { S as w } from "./skull-BdPXKOvx.js";
import { C as P } from "./crosshair-BCiyTdpP.js";
import { H as T } from "./heart-Be63oR7h.js";
import { B as R } from "./bomb-BF5aFt_5.js";
import { G as C } from "./gamepad-2-CX3iu8NC.js";
import { T as K } from "./trophy-DLp0OdqF.js";
const u = [
  { key: "dpm", label: "DPM", icon: m, color: "text-blue-500", valueLabel: "DPM" },
  { key: "kills", label: "Kills", icon: w, color: "text-rose-500", valueLabel: "Kills" },
  { key: "kd", label: "K/D Ratio", icon: P, color: "text-purple-500", valueLabel: "K/D" },
  { key: "damage", label: "Damage", icon: m, color: "text-amber-400", valueLabel: "Damage" },
  { key: "headshots", label: "Headshots", icon: b, color: "text-emerald-500", valueLabel: "Headshots" },
  { key: "revives", label: "Revives", icon: T, color: "text-cyan-500", valueLabel: "Revives" },
  { key: "accuracy", label: "Accuracy", icon: b, color: "text-green-400", valueLabel: "Accuracy" },
  { key: "gibs", label: "Gibs", icon: R, color: "text-orange-500", valueLabel: "Gibs" },
  { key: "games", label: "Games Played", icon: C, color: "text-indigo-400", valueLabel: "Rounds" }
], V = [
  { value: "7d", label: "Last 7 days" },
  { value: "30d", label: "Last 30 days" },
  { value: "season", label: "Season" },
  { value: "all", label: "All time" }
];
function F(e) {
  return e === 1 ? /* @__PURE__ */ a("span", { className: "text-amber-400 font-black", children: "🥇 1" }) : e === 2 ? /* @__PURE__ */ a("span", { className: "text-slate-300 font-black", children: "🥈 2" }) : e === 3 ? /* @__PURE__ */ a("span", { className: "text-amber-600 font-black", children: "🥉 3" }) : e <= 11 ? /* @__PURE__ */ t("span", { className: "inline-flex items-center gap-1.5 text-slate-400 font-mono", children: [
    /* @__PURE__ */ a("img", { src: S(e), alt: "", className: "w-4 h-4 object-contain" }),
    "#",
    e
  ] }) : /* @__PURE__ */ t("span", { className: "text-slate-500 font-mono", children: [
    "#",
    e
  ] });
}
const G = [
  {
    key: "rank",
    label: "Rank",
    className: "w-16",
    render: (e) => F(e.rank)
  },
  {
    key: "name",
    label: "Player",
    render: (e) => /* @__PURE__ */ a(
      "button",
      {
        className: "font-semibold text-white hover:text-blue-400 transition",
        onClick: (s) => {
          s.stopPropagation(), p(e.name);
        },
        children: e.name
      }
    )
  },
  {
    key: "value",
    label: "Value",
    sortable: !0,
    sortValue: (e) => e.value,
    className: "font-mono text-brand-cyan font-bold",
    render: (e) => r(e.value)
  },
  {
    key: "rounds",
    label: "Rounds",
    sortable: !0,
    sortValue: (e) => e.rounds,
    className: "text-slate-400",
    render: (e) => r(e.rounds)
  },
  {
    key: "kd",
    label: "K/D",
    sortable: !0,
    sortValue: (e) => e.kd,
    className: "text-slate-400 font-mono",
    render: (e) => e.kd.toFixed(2)
  },
  {
    key: "kills",
    label: "Kills",
    sortable: !0,
    sortValue: (e) => e.kills,
    className: "text-slate-400",
    render: (e) => r(e.kills)
  },
  {
    key: "deaths",
    label: "Deaths",
    sortable: !0,
    sortValue: (e) => e.deaths,
    className: "text-slate-400",
    render: (e) => r(e.deaths)
  }
];
function _() {
  const [e, s] = c("dpm"), [i, f] = c("30d"), { data: x, isLoading: h, isError: v } = g(e, i), o = u.find((l) => l.key === e), y = o?.icon ?? K;
  return h ? /* @__PURE__ */ t("div", { className: "mt-6", children: [
    /* @__PURE__ */ a(n, { title: "Leaderboards", subtitle: "Top players by stat" }),
    /* @__PURE__ */ a(D, { variant: "table", count: 10 })
  ] }) : v ? /* @__PURE__ */ t("div", { className: "mt-6", children: [
    /* @__PURE__ */ a(n, { title: "Leaderboards", subtitle: "Top players by stat" }),
    /* @__PURE__ */ a("div", { className: "text-center text-red-400 py-12", children: "Failed to load leaderboard." })
  ] }) : /* @__PURE__ */ t("div", { className: "mt-6", children: [
    /* @__PURE__ */ a(n, { title: "Leaderboards", subtitle: "Top players by stat", children: /* @__PURE__ */ t("div", { className: "flex items-center gap-2", children: [
      /* @__PURE__ */ a(y, { className: d("w-5 h-5", o?.color) }),
      /* @__PURE__ */ a("span", { className: "text-sm font-bold text-white", children: o?.valueLabel })
    ] }) }),
    /* @__PURE__ */ t(L, { children: [
      /* @__PURE__ */ a("div", { className: "flex flex-wrap gap-2", children: u.map((l) => {
        const k = l.icon;
        return /* @__PURE__ */ t(
          "button",
          {
            onClick: () => s(l.key),
            className: d(
              "px-3 py-1.5 rounded-lg text-xs font-bold transition flex items-center gap-1.5",
              e === l.key ? "bg-blue-500/20 text-blue-400 border border-blue-500/30" : "bg-slate-800 text-slate-400 border border-white/5 hover:bg-slate-700"
            ),
            children: [
              /* @__PURE__ */ a(k, { className: "w-3.5 h-3.5" }),
              l.label
            ]
          },
          l.key
        );
      }) }),
      /* @__PURE__ */ t("label", { className: "flex items-center gap-2", children: [
        /* @__PURE__ */ a("span", { className: "text-xs font-bold text-slate-400 uppercase tracking-wider", children: "Period" }),
        /* @__PURE__ */ a(
          "select",
          {
            value: i,
            onChange: (l) => f(l.target.value),
            className: "bg-slate-800 border border-white/10 text-slate-200 rounded-lg px-3 py-2 text-sm focus:outline-none focus:border-blue-500/50",
            children: V.map((l) => /* @__PURE__ */ a("option", { value: l.value, children: l.label }, l.value))
          }
        )
      ] })
    ] }),
    /* @__PURE__ */ a("div", { className: "glass-panel rounded-xl p-0 overflow-hidden", children: /* @__PURE__ */ a(
      N,
      {
        columns: G,
        data: x ?? [],
        keyFn: (l) => l.guid,
        onRowClick: (l) => p(l.name),
        defaultSort: { key: "value", dir: "desc" }
      }
    ) })
  ] });
}
export {
  _ as default
};
