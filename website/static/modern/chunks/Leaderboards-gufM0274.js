import { r as i, j as a, S as g, c } from "./route-host-Ba3v8uFM.js";
import { h as k } from "./hooks-CyQgvbI9.js";
import { D as j } from "./DataTable-gbZQ6Kgl.js";
import { P as o } from "./PageHeader-CQ7BTOQj.js";
import { F as N } from "./FilterBar-BVrgiC-n.js";
import { f as t } from "./format-BM7Gaq4w.js";
import { a as u } from "./navigation-BDd1HkpE.js";
import { r as w } from "./game-assets-BMYaQb9B.js";
import { Z as d } from "./zap-Chh6-OiF.js";
import { S as L } from "./skull-BhM2GlAn.js";
import { C as S } from "./crosshair-CPb1OWqx.js";
import { T as m } from "./target-CZv2kTPB.js";
import { H as D, B as P } from "./heart-BlqPAczq.js";
import { G as T } from "./gamepad-2-DXqvfHtG.js";
import { T as R } from "./trophy-f4_RKZnn.js";
const b = [
  { key: "dpm", label: "DPM", icon: d, color: "text-blue-500", valueLabel: "DPM" },
  { key: "kills", label: "Kills", icon: L, color: "text-rose-500", valueLabel: "Kills" },
  { key: "kd", label: "K/D Ratio", icon: S, color: "text-purple-500", valueLabel: "K/D" },
  { key: "damage", label: "Damage", icon: d, color: "text-amber-400", valueLabel: "Damage" },
  { key: "headshots", label: "Headshots", icon: m, color: "text-emerald-500", valueLabel: "Headshots" },
  { key: "revives", label: "Revives", icon: D, color: "text-cyan-500", valueLabel: "Revives" },
  { key: "accuracy", label: "Accuracy", icon: m, color: "text-green-400", valueLabel: "Accuracy" },
  { key: "gibs", label: "Gibs", icon: P, color: "text-orange-500", valueLabel: "Gibs" },
  { key: "games", label: "Games Played", icon: T, color: "text-indigo-400", valueLabel: "Rounds" }
], B = [
  { value: "7d", label: "Last 7 days" },
  { value: "30d", label: "Last 30 days" },
  { value: "season", label: "Season" },
  { value: "all", label: "All time" }
];
function C(e) {
  return e === 1 ? /* @__PURE__ */ a.jsx("span", { className: "text-amber-400 font-black", children: "🥇 1" }) : e === 2 ? /* @__PURE__ */ a.jsx("span", { className: "text-slate-300 font-black", children: "🥈 2" }) : e === 3 ? /* @__PURE__ */ a.jsx("span", { className: "text-amber-600 font-black", children: "🥉 3" }) : e <= 11 ? /* @__PURE__ */ a.jsxs("span", { className: "inline-flex items-center gap-1.5 text-slate-400 font-mono", children: [
    /* @__PURE__ */ a.jsx("img", { src: w(e), alt: "", className: "w-4 h-4 object-contain" }),
    "#",
    e
  ] }) : /* @__PURE__ */ a.jsxs("span", { className: "text-slate-500 font-mono", children: [
    "#",
    e
  ] });
}
const E = [
  {
    key: "rank",
    label: "Rank",
    className: "w-16",
    render: (e) => C(e.rank)
  },
  {
    key: "name",
    label: "Player",
    render: (e) => /* @__PURE__ */ a.jsx(
      "button",
      {
        className: "font-semibold text-white hover:text-blue-400 transition",
        onClick: (s) => {
          s.stopPropagation(), u(e.name);
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
    render: (e) => t(e.value)
  },
  {
    key: "rounds",
    label: "Rounds",
    sortable: !0,
    sortValue: (e) => e.rounds,
    className: "text-slate-400",
    render: (e) => t(e.rounds)
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
    render: (e) => t(e.kills)
  },
  {
    key: "deaths",
    label: "Deaths",
    sortable: !0,
    sortValue: (e) => e.deaths,
    className: "text-slate-400",
    render: (e) => t(e.deaths)
  }
];
function W() {
  const [e, s] = i.useState("dpm"), [n, x] = i.useState("30d"), { data: p, isLoading: f, isError: y } = k(e, n), r = b.find((l) => l.key === e), h = r?.icon ?? R;
  return f ? /* @__PURE__ */ a.jsxs("div", { className: "page-shell", children: [
    /* @__PURE__ */ a.jsx(o, { title: "Leaderboards", subtitle: "Compare top players once you are past the home and sessions flow.", eyebrow: "Everyday Browsing" }),
    /* @__PURE__ */ a.jsx(g, { variant: "table", count: 10 })
  ] }) : y ? /* @__PURE__ */ a.jsxs("div", { className: "page-shell", children: [
    /* @__PURE__ */ a.jsx(o, { title: "Leaderboards", subtitle: "Top players by stat", eyebrow: "Everyday Browsing" }),
    /* @__PURE__ */ a.jsx("div", { className: "text-center text-red-400 py-12", children: "Failed to load leaderboard." })
  ] }) : /* @__PURE__ */ a.jsxs("div", { className: "page-shell", children: [
    /* @__PURE__ */ a.jsx(o, { title: "Leaderboards", subtitle: "Top players by stat with the archive and player flow now doing the heavy lifting up front.", eyebrow: "Everyday Browsing", children: /* @__PURE__ */ a.jsxs("div", { className: "flex items-center gap-2", children: [
      /* @__PURE__ */ a.jsx(h, { className: c("w-5 h-5", r?.color) }),
      /* @__PURE__ */ a.jsx("span", { className: "text-sm font-bold text-white", children: r?.valueLabel })
    ] }) }),
    /* @__PURE__ */ a.jsxs(N, { children: [
      /* @__PURE__ */ a.jsx("div", { className: "flex flex-wrap gap-2", children: b.map((l) => {
        const v = l.icon;
        return /* @__PURE__ */ a.jsxs(
          "button",
          {
            onClick: () => s(l.key),
            className: c(
              "px-3 py-1.5 rounded-lg text-xs font-bold transition flex items-center gap-1.5",
              e === l.key ? "bg-blue-500/20 text-blue-400 border border-blue-500/30" : "bg-slate-800 text-slate-400 border border-white/5 hover:bg-slate-700"
            ),
            children: [
              /* @__PURE__ */ a.jsx(v, { className: "w-3.5 h-3.5" }),
              l.label
            ]
          },
          l.key
        );
      }) }),
      /* @__PURE__ */ a.jsxs("label", { className: "flex items-center gap-2", children: [
        /* @__PURE__ */ a.jsx("span", { className: "text-xs font-bold text-slate-400 uppercase tracking-wider", children: "Period" }),
        /* @__PURE__ */ a.jsx(
          "select",
          {
            value: n,
            onChange: (l) => x(l.target.value),
            className: "bg-slate-800 border border-white/10 text-slate-200 rounded-lg px-3 py-2 text-sm focus:outline-none focus:border-blue-500/50",
            children: B.map((l) => /* @__PURE__ */ a.jsx("option", { value: l.value, children: l.label }, l.value))
          }
        )
      ] })
    ] }),
    /* @__PURE__ */ a.jsx(
      j,
      {
        columns: E,
        data: p ?? [],
        keyFn: (l) => l.guid,
        onRowClick: (l) => u(l.name),
        defaultSort: { key: "value", dir: "desc" }
      }
    )
  ] });
}
export {
  W as default
};
