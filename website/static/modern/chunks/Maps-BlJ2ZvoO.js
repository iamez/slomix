import { jsxs as a, jsx as t } from "react/jsx-runtime";
import { useState as f } from "react";
import { g } from "./hooks-UFUMZFGB.js";
import { D as N } from "./DataTable-C9DYv6yb.js";
import { P as c } from "./PageHeader-D4CVo02x.js";
import { S as y, c as x } from "./route-host-CUL1oI6Z.js";
import { G as _ } from "./GlassCard-DKnnuJMt.js";
import { f as o } from "./format-BM7Gaq4w.js";
import { m as p } from "./game-assets-CWuRxGFH.js";
import { U as w } from "./users-CNuz17ri.js";
import { C as k } from "./clock-v5cg8EyG.js";
import { S as M } from "./skull-BdPXKOvx.js";
import { C as P } from "./crosshair-BCiyTdpP.js";
function h(e) {
  if (!e) return "-";
  const s = Math.floor(e / 60), i = e % 60;
  return `${s}:${String(i).padStart(2, "0")}`;
}
function r(e) {
  return e.replace(/^maps[\\/]/, "").replace(/\.(bsp|pk3|arena)$/i, "").replace(/_/g, " ");
}
function u({ allies: e, axis: s }) {
  return /* @__PURE__ */ a("div", { className: "flex items-center gap-2 min-w-[120px]", children: [
    /* @__PURE__ */ a("span", { className: "text-xs text-blue-400 font-mono w-10 text-right", children: [
      e,
      "%"
    ] }),
    /* @__PURE__ */ a("div", { className: "flex-1 h-2 rounded-full bg-slate-700 overflow-hidden flex", children: [
      /* @__PURE__ */ t("div", { className: "bg-blue-500 h-full", style: { width: `${e}%` } }),
      /* @__PURE__ */ t("div", { className: "bg-rose-500 h-full", style: { width: `${s}%` } })
    ] }),
    /* @__PURE__ */ a("span", { className: "text-xs text-rose-400 font-mono w-10", children: [
      s,
      "%"
    ] })
  ] });
}
const S = [
  {
    key: "name",
    label: "Map",
    render: (e) => /* @__PURE__ */ a("div", { className: "flex items-center gap-3", children: [
      /* @__PURE__ */ t(
        "img",
        {
          src: p(e.name),
          alt: r(e.name),
          className: "w-8 h-8 rounded-lg object-cover bg-slate-800",
          onError: (s) => {
            s.currentTarget.style.display = "none";
          }
        }
      ),
      /* @__PURE__ */ t("span", { className: "font-semibold text-white", children: r(e.name) })
    ] })
  },
  {
    key: "matches_played",
    label: "Matches",
    sortable: !0,
    sortValue: (e) => e.matches_played,
    className: "font-mono text-brand-cyan"
  },
  {
    key: "win_rate",
    label: "Win Rate (A/X)",
    render: (e) => /* @__PURE__ */ t(u, { allies: e.allies_win_rate, axis: e.axis_win_rate })
  },
  {
    key: "avg_duration",
    label: "Avg Duration",
    sortable: !0,
    sortValue: (e) => e.avg_duration,
    className: "font-mono text-slate-300",
    render: (e) => h(e.avg_duration)
  },
  {
    key: "unique_players",
    label: "Players",
    sortable: !0,
    sortValue: (e) => e.unique_players,
    className: "text-slate-400"
  },
  {
    key: "avg_dpm",
    label: "Avg DPM",
    sortable: !0,
    sortValue: (e) => e.avg_dpm,
    className: "font-mono text-slate-300",
    render: (e) => e.avg_dpm.toFixed(1)
  },
  {
    key: "total_kills",
    label: "Total Kills",
    sortable: !0,
    sortValue: (e) => e.total_kills,
    className: "text-slate-400",
    render: (e) => o(e.total_kills)
  },
  {
    key: "last_played",
    label: "Last Played",
    sortable: !0,
    className: "text-slate-500 text-xs"
  }
];
function H() {
  const { data: e, isLoading: s, isError: i } = g(), [d, m] = f("table");
  if (s)
    return /* @__PURE__ */ a("div", { className: "mt-6", children: [
      /* @__PURE__ */ t(c, { title: "Maps", subtitle: "Map statistics and analytics" }),
      /* @__PURE__ */ t(y, { variant: "table", count: 8 })
    ] });
  if (i || !e)
    return /* @__PURE__ */ a("div", { className: "mt-6", children: [
      /* @__PURE__ */ t(c, { title: "Maps", subtitle: "Map statistics and analytics" }),
      /* @__PURE__ */ t("div", { className: "text-center text-red-400 py-12", children: "Failed to load map data." })
    ] });
  const b = e.reduce((l, n) => l + n.matches_played, 0), v = new Set(e.map((l) => l.unique_players)).size;
  return /* @__PURE__ */ a("div", { className: "mt-6", children: [
    /* @__PURE__ */ t(c, { title: "Maps", subtitle: `${e.length} maps tracked`, children: /* @__PURE__ */ a("div", { className: "flex gap-1 bg-slate-800 rounded-lg p-0.5", children: [
      /* @__PURE__ */ t(
        "button",
        {
          onClick: () => m("table"),
          className: x(
            "px-3 py-1.5 rounded-md text-xs font-bold transition",
            d === "table" ? "bg-blue-500/20 text-blue-400" : "text-slate-400 hover:text-white"
          ),
          children: "Table"
        }
      ),
      /* @__PURE__ */ t(
        "button",
        {
          onClick: () => m("cards"),
          className: x(
            "px-3 py-1.5 rounded-md text-xs font-bold transition",
            d === "cards" ? "bg-blue-500/20 text-blue-400" : "text-slate-400 hover:text-white"
          ),
          children: "Cards"
        }
      )
    ] }) }),
    /* @__PURE__ */ a("div", { className: "grid grid-cols-2 lg:grid-cols-4 gap-4 mb-6", children: [
      /* @__PURE__ */ a("div", { className: "glass-card rounded-xl p-4", children: [
        /* @__PURE__ */ t("div", { className: "text-xs text-slate-500 uppercase font-bold", children: "Maps" }),
        /* @__PURE__ */ t("div", { className: "text-2xl font-black text-white mt-1", children: e.length })
      ] }),
      /* @__PURE__ */ a("div", { className: "glass-card rounded-xl p-4", children: [
        /* @__PURE__ */ t("div", { className: "text-xs text-slate-500 uppercase font-bold", children: "Total Matches" }),
        /* @__PURE__ */ t("div", { className: "text-2xl font-black text-brand-cyan mt-1", children: o(b) })
      ] }),
      /* @__PURE__ */ a("div", { className: "glass-card rounded-xl p-4", children: [
        /* @__PURE__ */ t("div", { className: "text-xs text-slate-500 uppercase font-bold", children: "Most Played" }),
        /* @__PURE__ */ t("div", { className: "text-sm font-black text-brand-purple mt-1 truncate", children: r(e[0]?.name ?? "-") }),
        /* @__PURE__ */ a("div", { className: "text-[11px] text-slate-500", children: [
          e[0]?.matches_played ?? 0,
          " matches"
        ] })
      ] }),
      /* @__PURE__ */ a("div", { className: "glass-card rounded-xl p-4", children: [
        /* @__PURE__ */ t("div", { className: "text-xs text-slate-500 uppercase font-bold", children: "Unique Players" }),
        /* @__PURE__ */ t("div", { className: "text-2xl font-black text-brand-emerald mt-1", children: v })
      ] })
    ] }),
    d === "table" ? /* @__PURE__ */ t("div", { className: "glass-panel rounded-xl p-0 overflow-hidden", children: /* @__PURE__ */ t(
      N,
      {
        columns: S,
        data: e,
        keyFn: (l) => l.name,
        defaultSort: { key: "matches_played", dir: "desc" },
        stickyHeader: !0
      }
    ) }) : /* @__PURE__ */ t("div", { className: "grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4", children: e.map((l) => /* @__PURE__ */ a(_, { className: "relative overflow-hidden", children: [
      /* @__PURE__ */ a("div", { className: "relative -mx-5 -mt-5 mb-4 h-28 overflow-hidden rounded-t-xl bg-slate-800", children: [
        /* @__PURE__ */ t(
          "img",
          {
            src: p(l.name),
            alt: r(l.name),
            className: "w-full h-full object-cover opacity-70",
            onError: (n) => {
              n.currentTarget.style.display = "none";
            }
          }
        ),
        /* @__PURE__ */ t("div", { className: "absolute inset-0 bg-gradient-to-t from-slate-900 via-slate-900/40 to-transparent" }),
        /* @__PURE__ */ a("div", { className: "absolute bottom-3 left-4", children: [
          /* @__PURE__ */ t("div", { className: "font-bold text-white text-lg drop-shadow-lg", children: r(l.name) }),
          /* @__PURE__ */ a("div", { className: "text-xs text-slate-300", children: [
            l.matches_played,
            " matches"
          ] })
        ] })
      ] }),
      /* @__PURE__ */ a("div", { className: "grid grid-cols-3 gap-3 mb-3 text-center", children: [
        /* @__PURE__ */ a("div", { children: [
          /* @__PURE__ */ t(w, { className: "w-3.5 h-3.5 mx-auto text-slate-500 mb-1" }),
          /* @__PURE__ */ t("div", { className: "text-sm font-bold text-white", children: l.unique_players }),
          /* @__PURE__ */ t("div", { className: "text-[10px] text-slate-500", children: "Players" })
        ] }),
        /* @__PURE__ */ a("div", { children: [
          /* @__PURE__ */ t(k, { className: "w-3.5 h-3.5 mx-auto text-slate-500 mb-1" }),
          /* @__PURE__ */ t("div", { className: "text-sm font-bold text-white", children: h(l.avg_duration) }),
          /* @__PURE__ */ t("div", { className: "text-[10px] text-slate-500", children: "Avg Time" })
        ] }),
        /* @__PURE__ */ a("div", { children: [
          /* @__PURE__ */ t(M, { className: "w-3.5 h-3.5 mx-auto text-slate-500 mb-1" }),
          /* @__PURE__ */ t("div", { className: "text-sm font-bold text-white", children: o(l.total_kills) }),
          /* @__PURE__ */ t("div", { className: "text-[10px] text-slate-500", children: "Kills" })
        ] })
      ] }),
      /* @__PURE__ */ t(u, { allies: l.allies_win_rate, axis: l.axis_win_rate }),
      /* @__PURE__ */ a("div", { className: "flex items-center justify-between mt-3 pt-3 border-t border-white/5", children: [
        /* @__PURE__ */ a("div", { className: "flex items-center gap-1 text-xs text-slate-500", children: [
          /* @__PURE__ */ t(P, { className: "w-3 h-3" }),
          /* @__PURE__ */ a("span", { children: [
            l.avg_dpm.toFixed(1),
            " DPM"
          ] })
        ] }),
        /* @__PURE__ */ t("span", { className: "text-[10px] text-slate-500", children: l.last_played })
      ] })
    ] }, l.name)) })
  ] });
}
export {
  H as default
};
