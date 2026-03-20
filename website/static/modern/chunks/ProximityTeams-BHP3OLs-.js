import { j as e, S as b } from "./route-host-Ba3v8uFM.js";
import { u as N } from "./useQuery-CHhIv7cp.js";
import { P as h } from "./PageHeader-CQ7BTOQj.js";
import { G as o } from "./GlassPanel-C-uUmQaB.js";
import { G as y } from "./GlassCard-C53TzD-y.js";
const _ = "/api";
function j(a) {
  return a != null ? a.toLocaleString() : "--";
}
function u(a, i = 1) {
  return a != null ? a.toFixed(i) : "--";
}
function g(a) {
  return a != null ? `${a.toFixed(1)}%` : "--";
}
function r({ axisVal: a, alliesVal: i, label: n }) {
  const m = a ?? 0, x = i ?? 0, t = Math.max(m, x, 1), l = Math.round(m / t * 100), d = Math.round(x / t * 100);
  return /* @__PURE__ */ e.jsxs("div", { className: "space-y-1.5", children: [
    /* @__PURE__ */ e.jsx("div", { className: "flex items-center justify-between text-[10px] text-slate-500 uppercase tracking-wider", children: /* @__PURE__ */ e.jsx("span", { children: n }) }),
    /* @__PURE__ */ e.jsxs("div", { className: "flex items-center gap-2", children: [
      /* @__PURE__ */ e.jsx("span", { className: "text-xs text-red-400 font-mono w-14 text-right", children: u(a) }),
      /* @__PURE__ */ e.jsxs("div", { className: "flex-1 flex items-center gap-1 h-4", children: [
        /* @__PURE__ */ e.jsx("div", { className: "flex-1 flex justify-end", children: /* @__PURE__ */ e.jsx(
          "div",
          {
            className: "h-full rounded-l bg-red-500/70 transition-all duration-500",
            style: { width: `${l}%` }
          }
        ) }),
        /* @__PURE__ */ e.jsx("div", { className: "w-px h-full bg-slate-600" }),
        /* @__PURE__ */ e.jsx("div", { className: "flex-1", children: /* @__PURE__ */ e.jsx(
          "div",
          {
            className: "h-full rounded-r bg-blue-500/70 transition-all duration-500",
            style: { width: `${d}%` }
          }
        ) })
      ] }),
      /* @__PURE__ */ e.jsx("span", { className: "text-xs text-blue-400 font-mono w-14", children: u(i) })
    ] })
  ] });
}
function $({ params: a }) {
  const i = a?.roundId ?? "", { data: n, isLoading: m, error: x } = N({
    queryKey: ["proximity-team-comparison", i],
    queryFn: () => fetch(`${_}/proximity/round/${i}/team-comparison`).then((s) => {
      if (!s.ok) throw new Error(`HTTP ${s.status}`);
      return s.json();
    }),
    enabled: !!i,
    staleTime: 6e4
  });
  if (!i)
    return /* @__PURE__ */ e.jsxs(e.Fragment, { children: [
      /* @__PURE__ */ e.jsx(h, { title: "Team Comparison", subtitle: "No round specified" }),
      /* @__PURE__ */ e.jsx(o, { children: /* @__PURE__ */ e.jsx("div", { className: "text-sm text-slate-400", children: "Please select a round from the proximity analytics page." }) })
    ] });
  if (m) return /* @__PURE__ */ e.jsx(b, { variant: "card", count: 4 });
  if (x)
    return /* @__PURE__ */ e.jsxs(e.Fragment, { children: [
      /* @__PURE__ */ e.jsx(h, { title: `Team Comparison - Round #${i}` }),
      /* @__PURE__ */ e.jsxs("div", { className: "rounded-xl border border-red-500/30 bg-red-500/10 px-4 py-3 text-sm text-red-400", children: [
        "Failed to load team comparison data. ",
        x.message
      ] })
    ] });
  const t = n?.cohesion, l = n?.pushes, d = n?.crossfire ?? [];
  return /* @__PURE__ */ e.jsxs(e.Fragment, { children: [
    /* @__PURE__ */ e.jsx(h, { title: `Team Comparison - Round #${i}`, subtitle: "Side-by-side team performance analysis", children: /* @__PURE__ */ e.jsx(
      "a",
      {
        href: "#/proximity",
        className: "px-3 py-1.5 rounded-lg text-xs font-bold border border-white/10 text-slate-300 hover:border-cyan-500/40 transition",
        children: "Back to Proximity"
      }
    ) }),
    /* @__PURE__ */ e.jsxs("div", { className: "flex items-center gap-6 mb-6 text-xs", children: [
      /* @__PURE__ */ e.jsxs("div", { className: "flex items-center gap-2", children: [
        /* @__PURE__ */ e.jsx("span", { className: "w-3 h-3 rounded-full bg-red-500" }),
        /* @__PURE__ */ e.jsx("span", { className: "text-slate-300 font-medium", children: "Axis" })
      ] }),
      /* @__PURE__ */ e.jsxs("div", { className: "flex items-center gap-2", children: [
        /* @__PURE__ */ e.jsx("span", { className: "w-3 h-3 rounded-full bg-blue-500" }),
        /* @__PURE__ */ e.jsx("span", { className: "text-slate-300 font-medium", children: "Allies" })
      ] })
    ] }),
    t && /* @__PURE__ */ e.jsxs(o, { className: "mb-6", children: [
      /* @__PURE__ */ e.jsx("div", { className: "text-xs font-bold uppercase tracking-widest text-slate-400 mb-4", children: "Cohesion Comparison" }),
      /* @__PURE__ */ e.jsxs("div", { className: "space-y-4", children: [
        /* @__PURE__ */ e.jsx(r, { label: "Avg Dispersion", axisVal: t.axis.avg_dispersion, alliesVal: t.allies.avg_dispersion }),
        /* @__PURE__ */ e.jsx(r, { label: "Avg Max Spread", axisVal: t.axis.avg_max_spread, alliesVal: t.allies.avg_max_spread }),
        /* @__PURE__ */ e.jsx(r, { label: "Avg Stragglers", axisVal: t.axis.avg_stragglers, alliesVal: t.allies.avg_stragglers }),
        /* @__PURE__ */ e.jsx(r, { label: "Samples", axisVal: t.axis.samples, alliesVal: t.allies.samples })
      ] })
    ] }),
    l && /* @__PURE__ */ e.jsxs(o, { className: "mb-6", children: [
      /* @__PURE__ */ e.jsx("div", { className: "text-xs font-bold uppercase tracking-widest text-slate-400 mb-4", children: "Push Quality" }),
      /* @__PURE__ */ e.jsx("div", { className: "grid grid-cols-1 md:grid-cols-3 gap-4 mb-5", children: ["push_count", "avg_quality", "avg_alignment"].map((s) => {
        const c = { push_count: "Push Count", avg_quality: "Avg Quality", avg_alignment: "Avg Alignment" };
        return /* @__PURE__ */ e.jsxs(y, { className: "!cursor-default", children: [
          /* @__PURE__ */ e.jsx("div", { className: "text-[10px] text-slate-500 uppercase mb-2", children: c[s] }),
          /* @__PURE__ */ e.jsxs("div", { className: "flex items-end justify-between", children: [
            /* @__PURE__ */ e.jsxs("div", { className: "text-center flex-1", children: [
              /* @__PURE__ */ e.jsx("div", { className: "text-lg font-bold text-red-400", children: u(l.axis[s]) }),
              /* @__PURE__ */ e.jsx("div", { className: "text-[10px] text-slate-500", children: "Axis" })
            ] }),
            /* @__PURE__ */ e.jsx("div", { className: "text-slate-600 text-xs px-2", children: "vs" }),
            /* @__PURE__ */ e.jsxs("div", { className: "text-center flex-1", children: [
              /* @__PURE__ */ e.jsx("div", { className: "text-lg font-bold text-blue-400", children: u(l.allies[s]) }),
              /* @__PURE__ */ e.jsx("div", { className: "text-[10px] text-slate-500", children: "Allies" })
            ] })
          ] })
        ] }, s);
      }) }),
      /* @__PURE__ */ e.jsxs("div", { className: "space-y-4", children: [
        /* @__PURE__ */ e.jsx(r, { label: "Push Count", axisVal: l.axis.push_count, alliesVal: l.allies.push_count }),
        /* @__PURE__ */ e.jsx(r, { label: "Quality", axisVal: l.axis.avg_quality, alliesVal: l.allies.avg_quality }),
        /* @__PURE__ */ e.jsx(r, { label: "Alignment", axisVal: l.axis.avg_alignment, alliesVal: l.allies.avg_alignment })
      ] })
    ] }),
    d.length > 0 && /* @__PURE__ */ e.jsxs(o, { className: "mb-6", children: [
      /* @__PURE__ */ e.jsx("div", { className: "text-xs font-bold uppercase tracking-widest text-slate-400 mb-4", children: "Crossfire Execution" }),
      /* @__PURE__ */ e.jsx("div", { className: "space-y-5", children: d.map((s) => {
        const c = s.execution_rate ?? 0, p = s.target_team.toUpperCase() === "AXIS", f = p ? "bg-red-500/70" : "bg-blue-500/70", v = p ? "text-red-400" : "text-blue-400";
        return /* @__PURE__ */ e.jsxs("div", { children: [
          /* @__PURE__ */ e.jsxs("div", { className: "flex items-center justify-between mb-2", children: [
            /* @__PURE__ */ e.jsxs("span", { className: `text-sm font-medium ${v}`, children: [
              "vs ",
              s.target_team
            ] }),
            /* @__PURE__ */ e.jsxs("span", { className: "text-xs text-slate-400", children: [
              j(s.executed),
              " / ",
              j(s.total_opportunities),
              " opportunities"
            ] })
          ] }),
          /* @__PURE__ */ e.jsx("div", { className: "w-full h-5 rounded-full bg-slate-800/80 overflow-hidden", children: /* @__PURE__ */ e.jsx(
            "div",
            {
              className: `h-full rounded-full ${f} transition-all duration-700 flex items-center justify-end pr-2`,
              style: { width: `${Math.max(c, 2)}%` },
              children: c >= 15 && /* @__PURE__ */ e.jsx("span", { className: "text-[10px] font-bold text-white", children: g(s.execution_rate) })
            }
          ) }),
          c < 15 && /* @__PURE__ */ e.jsx("div", { className: "text-right mt-0.5", children: /* @__PURE__ */ e.jsx("span", { className: "text-[10px] font-bold text-slate-400", children: g(s.execution_rate) }) })
        ] }, s.target_team);
      }) })
    ] }),
    !t && !l && d.length === 0 && /* @__PURE__ */ e.jsx(o, { children: /* @__PURE__ */ e.jsxs("div", { className: "text-center py-8", children: [
      /* @__PURE__ */ e.jsx("div", { className: "text-slate-500 text-sm", children: "No team comparison data available for this round." }),
      /* @__PURE__ */ e.jsx("div", { className: "text-slate-600 text-xs mt-1", children: "This round may not have proximity teamplay data recorded." })
    ] }) })
  ] });
}
export {
  $ as default
};
