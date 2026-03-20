import { r as j, j as e, S as v, c as x } from "./route-host-Ba3v8uFM.js";
import { i as f } from "./hooks-CyQgvbI9.js";
import { D as g } from "./DataTable-gbZQ6Kgl.js";
import { P as n } from "./PageHeader-CQ7BTOQj.js";
import { G as N } from "./GlassCard-C53TzD-y.js";
import { f as c } from "./format-BM7Gaq4w.js";
import { m } from "./game-assets-BMYaQb9B.js";
import { U as y } from "./users-Blp4mgkM.js";
import { C as w } from "./clock-KDxcQEST.js";
import { S as _ } from "./skull-BhM2GlAn.js";
import { C as k } from "./crosshair-CPb1OWqx.js";
function p(s) {
  if (!s) return "-";
  const a = Math.floor(s / 60), r = s % 60;
  return `${a}:${String(r).padStart(2, "0")}`;
}
function l(s) {
  return s.replace(/^maps[\\/]/, "").replace(/\.(bsp|pk3|arena)$/i, "").replace(/_/g, " ");
}
function h({ allies: s, axis: a }) {
  return /* @__PURE__ */ e.jsxs("div", { className: "flex items-center gap-2 min-w-[120px]", children: [
    /* @__PURE__ */ e.jsxs("span", { className: "text-xs text-blue-400 font-mono w-10 text-right", children: [
      s,
      "%"
    ] }),
    /* @__PURE__ */ e.jsxs("div", { className: "flex-1 h-2 rounded-full bg-slate-700 overflow-hidden flex", children: [
      /* @__PURE__ */ e.jsx("div", { className: "bg-blue-500 h-full", style: { width: `${s}%` } }),
      /* @__PURE__ */ e.jsx("div", { className: "bg-rose-500 h-full", style: { width: `${a}%` } })
    ] }),
    /* @__PURE__ */ e.jsxs("span", { className: "text-xs text-rose-400 font-mono w-10", children: [
      a,
      "%"
    ] })
  ] });
}
const M = [
  {
    key: "name",
    label: "Map",
    render: (s) => /* @__PURE__ */ e.jsxs("div", { className: "flex items-center gap-3", children: [
      /* @__PURE__ */ e.jsx(
        "img",
        {
          src: m(s.name),
          alt: l(s.name),
          className: "w-8 h-8 rounded-lg object-cover bg-slate-800",
          onError: (a) => {
            a.currentTarget.style.display = "none";
          }
        }
      ),
      /* @__PURE__ */ e.jsx("span", { className: "font-semibold text-white", children: l(s.name) })
    ] })
  },
  {
    key: "matches_played",
    label: "Matches",
    sortable: !0,
    sortValue: (s) => s.matches_played,
    className: "font-mono text-brand-cyan"
  },
  {
    key: "win_rate",
    label: "Win Rate (A/X)",
    render: (s) => /* @__PURE__ */ e.jsx(h, { allies: s.allies_win_rate, axis: s.axis_win_rate })
  },
  {
    key: "avg_duration",
    label: "Avg Duration",
    sortable: !0,
    sortValue: (s) => s.avg_duration,
    className: "font-mono text-slate-300",
    render: (s) => p(s.avg_duration)
  },
  {
    key: "unique_players",
    label: "Players",
    sortable: !0,
    sortValue: (s) => s.unique_players,
    className: "text-slate-400"
  },
  {
    key: "avg_dpm",
    label: "Avg DPM",
    sortable: !0,
    sortValue: (s) => s.avg_dpm,
    className: "font-mono text-slate-300",
    render: (s) => s.avg_dpm.toFixed(1)
  },
  {
    key: "total_kills",
    label: "Total Kills",
    sortable: !0,
    sortValue: (s) => s.total_kills,
    className: "text-slate-400",
    render: (s) => c(s.total_kills)
  },
  {
    key: "last_played",
    label: "Last Played",
    sortable: !0,
    className: "text-slate-500 text-xs"
  }
];
function L() {
  const { data: s, isLoading: a, isError: r } = f(), [i, o] = j.useState("table");
  if (a)
    return /* @__PURE__ */ e.jsxs("div", { className: "page-shell", children: [
      /* @__PURE__ */ e.jsx(n, { title: "Maps", subtitle: "Historical map context once the main session and player questions are already answered.", eyebrow: "More" }),
      /* @__PURE__ */ e.jsx(v, { variant: "table", count: 8 })
    ] });
  if (r || !s)
    return /* @__PURE__ */ e.jsxs("div", { className: "page-shell", children: [
      /* @__PURE__ */ e.jsx(n, { title: "Maps", subtitle: "Map statistics and analytics", eyebrow: "More" }),
      /* @__PURE__ */ e.jsx("div", { className: "text-center text-red-400 py-12", children: "Failed to load map data." })
    ] });
  const u = s.reduce((t, d) => t + d.matches_played, 0), b = new Set(s.map((t) => t.unique_players)).size;
  return /* @__PURE__ */ e.jsxs("div", { className: "page-shell", children: [
    /* @__PURE__ */ e.jsx(n, { title: "Maps", subtitle: `${s.length} maps tracked across the archive.`, eyebrow: "More", children: /* @__PURE__ */ e.jsxs("div", { className: "flex gap-1 bg-slate-800 rounded-lg p-0.5", children: [
      /* @__PURE__ */ e.jsx(
        "button",
        {
          onClick: () => o("table"),
          className: x(
            "px-3 py-1.5 rounded-md text-xs font-bold transition",
            i === "table" ? "bg-blue-500/20 text-blue-400" : "text-slate-400 hover:text-white"
          ),
          children: "Table"
        }
      ),
      /* @__PURE__ */ e.jsx(
        "button",
        {
          onClick: () => o("cards"),
          className: x(
            "px-3 py-1.5 rounded-md text-xs font-bold transition",
            i === "cards" ? "bg-blue-500/20 text-blue-400" : "text-slate-400 hover:text-white"
          ),
          children: "Cards"
        }
      )
    ] }) }),
    /* @__PURE__ */ e.jsxs("div", { className: "grid grid-cols-2 lg:grid-cols-4 gap-4 mb-6", children: [
      /* @__PURE__ */ e.jsxs("div", { className: "glass-card rounded-xl p-4", children: [
        /* @__PURE__ */ e.jsx("div", { className: "text-xs text-slate-500 uppercase font-bold", children: "Maps" }),
        /* @__PURE__ */ e.jsx("div", { className: "text-2xl font-black text-white mt-1", children: s.length })
      ] }),
      /* @__PURE__ */ e.jsxs("div", { className: "glass-card rounded-xl p-4", children: [
        /* @__PURE__ */ e.jsx("div", { className: "text-xs text-slate-500 uppercase font-bold", children: "Total Matches" }),
        /* @__PURE__ */ e.jsx("div", { className: "text-2xl font-black text-brand-cyan mt-1", children: c(u) })
      ] }),
      /* @__PURE__ */ e.jsxs("div", { className: "glass-card rounded-xl p-4", children: [
        /* @__PURE__ */ e.jsx("div", { className: "text-xs text-slate-500 uppercase font-bold", children: "Most Played" }),
        /* @__PURE__ */ e.jsx("div", { className: "text-sm font-black text-brand-purple mt-1 truncate", children: l(s[0]?.name ?? "-") }),
        /* @__PURE__ */ e.jsxs("div", { className: "text-[11px] text-slate-500", children: [
          s[0]?.matches_played ?? 0,
          " matches"
        ] })
      ] }),
      /* @__PURE__ */ e.jsxs("div", { className: "glass-card rounded-xl p-4", children: [
        /* @__PURE__ */ e.jsx("div", { className: "text-xs text-slate-500 uppercase font-bold", children: "Unique Players" }),
        /* @__PURE__ */ e.jsx("div", { className: "text-2xl font-black text-brand-emerald mt-1", children: b })
      ] })
    ] }),
    i === "table" ? /* @__PURE__ */ e.jsx(
      g,
      {
        columns: M,
        data: s,
        keyFn: (t) => t.name,
        defaultSort: { key: "matches_played", dir: "desc" },
        stickyHeader: !0
      }
    ) : /* @__PURE__ */ e.jsx("div", { className: "grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4", children: s.map((t) => /* @__PURE__ */ e.jsxs(N, { className: "relative overflow-hidden", children: [
      /* @__PURE__ */ e.jsxs("div", { className: "relative -mx-5 -mt-5 mb-4 h-28 overflow-hidden rounded-t-xl bg-slate-800", children: [
        /* @__PURE__ */ e.jsx(
          "img",
          {
            src: m(t.name),
            alt: l(t.name),
            className: "w-full h-full object-cover opacity-70",
            onError: (d) => {
              d.currentTarget.style.display = "none";
            }
          }
        ),
        /* @__PURE__ */ e.jsx("div", { className: "absolute inset-0 bg-gradient-to-t from-slate-900 via-slate-900/40 to-transparent" }),
        /* @__PURE__ */ e.jsxs("div", { className: "absolute bottom-3 left-4", children: [
          /* @__PURE__ */ e.jsx("div", { className: "font-bold text-white text-lg drop-shadow-lg", children: l(t.name) }),
          /* @__PURE__ */ e.jsxs("div", { className: "text-xs text-slate-300", children: [
            t.matches_played,
            " matches"
          ] })
        ] })
      ] }),
      /* @__PURE__ */ e.jsxs("div", { className: "grid grid-cols-3 gap-3 mb-3 text-center", children: [
        /* @__PURE__ */ e.jsxs("div", { children: [
          /* @__PURE__ */ e.jsx(y, { className: "w-3.5 h-3.5 mx-auto text-slate-500 mb-1" }),
          /* @__PURE__ */ e.jsx("div", { className: "text-sm font-bold text-white", children: t.unique_players }),
          /* @__PURE__ */ e.jsx("div", { className: "text-[10px] text-slate-500", children: "Players" })
        ] }),
        /* @__PURE__ */ e.jsxs("div", { children: [
          /* @__PURE__ */ e.jsx(w, { className: "w-3.5 h-3.5 mx-auto text-slate-500 mb-1" }),
          /* @__PURE__ */ e.jsx("div", { className: "text-sm font-bold text-white", children: p(t.avg_duration) }),
          /* @__PURE__ */ e.jsx("div", { className: "text-[10px] text-slate-500", children: "Avg Time" })
        ] }),
        /* @__PURE__ */ e.jsxs("div", { children: [
          /* @__PURE__ */ e.jsx(_, { className: "w-3.5 h-3.5 mx-auto text-slate-500 mb-1" }),
          /* @__PURE__ */ e.jsx("div", { className: "text-sm font-bold text-white", children: c(t.total_kills) }),
          /* @__PURE__ */ e.jsx("div", { className: "text-[10px] text-slate-500", children: "Kills" })
        ] })
      ] }),
      /* @__PURE__ */ e.jsx(h, { allies: t.allies_win_rate, axis: t.axis_win_rate }),
      /* @__PURE__ */ e.jsxs("div", { className: "flex items-center justify-between mt-3 pt-3 border-t border-white/5", children: [
        /* @__PURE__ */ e.jsxs("div", { className: "flex items-center gap-1 text-xs text-slate-500", children: [
          /* @__PURE__ */ e.jsx(k, { className: "w-3 h-3" }),
          /* @__PURE__ */ e.jsxs("span", { children: [
            t.avg_dpm.toFixed(1),
            " DPM"
          ] })
        ] }),
        /* @__PURE__ */ e.jsx("span", { className: "text-[10px] text-slate-500", children: t.last_played })
      ] })
    ] }, t.name)) })
  ] });
}
export {
  L as default
};
