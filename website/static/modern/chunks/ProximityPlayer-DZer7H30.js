import { j as e, S as k } from "./route-host-Ba3v8uFM.js";
import { u as y } from "./useQuery-CHhIv7cp.js";
import { P as b } from "./PageHeader-CQ7BTOQj.js";
import { G as c } from "./GlassPanel-C-uUmQaB.js";
import { G as v } from "./GlassCard-C53TzD-y.js";
import { n as w } from "./navigation-BDd1HkpE.js";
const N = "/api";
function d(s) {
  return s != null ? s.toLocaleString() : "--";
}
function m(s) {
  return s != null ? `${Math.round(s)}ms` : "--";
}
function _(s) {
  return s != null ? `${s.toFixed(1)}%` : "--";
}
const f = 300, h = f / 2, g = f / 2, u = 120;
function j(s, l) {
  const t = (s - 90) * Math.PI / 180;
  return [h + l * Math.cos(t), g + l * Math.sin(t)];
}
function P(s) {
  return Array.from({ length: 5 }, (l, t) => {
    const [o, x] = j(72 * t, s);
    return `${o},${x}`;
  }).join(" ");
}
function $({ axes: s, composite: l }) {
  if (s.length !== 5) return null;
  const t = s.map((a, r) => {
    const n = Math.min(a.value, 100) / 100;
    return j(360 / 5 * r, u * n);
  }), o = t.map(([a, r]) => `${a},${r}`).join(" "), x = s.map((a, r) => j(360 / 5 * r, u + 28));
  return /* @__PURE__ */ e.jsxs("svg", { viewBox: `0 0 ${f} ${f}`, className: "w-full max-w-[320px] mx-auto", children: [
    [0.33, 0.66, 1].map((a) => /* @__PURE__ */ e.jsx(
      "polygon",
      {
        points: P(u * a),
        fill: "none",
        stroke: "rgba(148,163,184,0.15)",
        strokeWidth: "1"
      },
      a
    )),
    s.map((a, r) => {
      const [n, p] = j(72 * r, u);
      return /* @__PURE__ */ e.jsx("line", { x1: h, y1: g, x2: n, y2: p, stroke: "rgba(148,163,184,0.1)", strokeWidth: "1" }, r);
    }),
    /* @__PURE__ */ e.jsx(
      "polygon",
      {
        points: o,
        fill: "rgba(56,189,248,0.2)",
        stroke: "rgba(56,189,248,0.8)",
        strokeWidth: "2"
      }
    ),
    t.map(([a, r], n) => /* @__PURE__ */ e.jsx("circle", { cx: a, cy: r, r: "4", fill: "rgb(56,189,248)", stroke: "rgb(15,23,42)", strokeWidth: "2" }, n)),
    s.map((a, r) => {
      const [n, p] = x[r];
      return /* @__PURE__ */ e.jsxs("g", { children: [
        /* @__PURE__ */ e.jsx(
          "text",
          {
            x: n,
            y: p - 6,
            textAnchor: "middle",
            dominantBaseline: "middle",
            className: "fill-slate-400 text-[10px] font-bold",
            children: a.label
          }
        ),
        /* @__PURE__ */ e.jsx(
          "text",
          {
            x: n,
            y: p + 7,
            textAnchor: "middle",
            dominantBaseline: "middle",
            className: "fill-cyan-400 text-[10px] font-mono",
            children: Math.round(a.value)
          }
        )
      ] }, r);
    }),
    /* @__PURE__ */ e.jsx("text", { x: h, y: g - 6, textAnchor: "middle", dominantBaseline: "middle", className: "fill-white text-2xl font-black", children: Math.round(l) }),
    /* @__PURE__ */ e.jsx("text", { x: h, y: g + 12, textAnchor: "middle", dominantBaseline: "middle", className: "fill-slate-500 text-[9px] font-bold uppercase", children: "Composite" })
  ] });
}
function i({ label: s, value: l, color: t = "text-white" }) {
  return /* @__PURE__ */ e.jsxs("div", { children: [
    /* @__PURE__ */ e.jsx("div", { className: "text-[10px] text-slate-500 uppercase font-bold", children: s }),
    /* @__PURE__ */ e.jsx("div", { className: `text-lg font-bold ${t}`, children: l })
  ] });
}
function M({ score: s, label: l }) {
  const t = Math.min(Math.max(s, 0), 100), o = t >= 70 ? "bg-emerald-500" : t >= 40 ? "bg-amber-500" : "bg-rose-500";
  return /* @__PURE__ */ e.jsxs("div", { children: [
    /* @__PURE__ */ e.jsxs("div", { className: "flex items-center justify-between mb-1", children: [
      /* @__PURE__ */ e.jsx("span", { className: "text-[10px] text-slate-500 uppercase font-bold", children: l }),
      /* @__PURE__ */ e.jsx("span", { className: "text-sm font-bold text-white", children: s.toFixed(1) })
    ] }),
    /* @__PURE__ */ e.jsx("div", { className: "h-2 rounded-full bg-slate-700 overflow-hidden", children: /* @__PURE__ */ e.jsx("div", { className: `h-full rounded-full ${o} transition-all`, style: { width: `${t}%` } }) })
  ] });
}
function E({ params: s }) {
  const l = s?.guid ?? "", { data: t, isLoading: o, isError: x } = y({
    queryKey: ["proximity-player-profile", l],
    queryFn: async () => (await fetch(`${N}/proximity/player/${encodeURIComponent(l)}/profile`)).json(),
    enabled: !!l,
    staleTime: 6e4
  }), { data: a } = y({
    queryKey: ["proximity-player-radar", l],
    queryFn: async () => (await fetch(`${N}/proximity/player/${encodeURIComponent(l)}/radar`)).json(),
    enabled: !!l,
    staleTime: 6e4
  });
  return l ? o ? /* @__PURE__ */ e.jsxs("div", { className: "mt-6", children: [
    /* @__PURE__ */ e.jsx(b, { title: "Loading...", subtitle: l }),
    /* @__PURE__ */ e.jsx(k, { variant: "card", count: 6 })
  ] }) : x || !t ? /* @__PURE__ */ e.jsxs("div", { className: "mt-6", children: [
    /* @__PURE__ */ e.jsx(b, { title: "Proximity Profile", subtitle: l }),
    /* @__PURE__ */ e.jsx("div", { className: "text-center text-red-400 py-12", children: "Player not found or failed to load proximity data." })
  ] }) : /* @__PURE__ */ e.jsxs("div", { className: "mt-6", children: [
    /* @__PURE__ */ e.jsx(
      "button",
      {
        onClick: () => w("#/proximity"),
        className: "text-xs text-cyan-400 hover:text-cyan-300 transition mb-4 inline-block",
        children: "← Back to Proximity Analytics"
      }
    ),
    /* @__PURE__ */ e.jsx(b, { title: t.player_name, subtitle: `GUID: ${t.guid}` }),
    /* @__PURE__ */ e.jsxs("div", { className: "grid grid-cols-1 lg:grid-cols-3 gap-6", children: [
      /* @__PURE__ */ e.jsxs(c, { className: "lg:col-span-1 flex flex-col items-center justify-center", children: [
        /* @__PURE__ */ e.jsx("h3", { className: "text-xs font-bold uppercase tracking-widest text-slate-400 mb-4 self-start", children: "Player Radar" }),
        a?.axes?.length === 5 ? /* @__PURE__ */ e.jsx($, { axes: a.axes, composite: a.composite }) : /* @__PURE__ */ e.jsx("div", { className: "text-sm text-slate-500 py-8", children: "Radar data not available" })
      ] }),
      /* @__PURE__ */ e.jsxs("div", { className: "lg:col-span-2 space-y-4", children: [
        /* @__PURE__ */ e.jsxs(c, { children: [
          /* @__PURE__ */ e.jsx("h3", { className: "text-xs font-bold uppercase tracking-widest text-slate-400 mb-4", children: "Engagement Stats" }),
          /* @__PURE__ */ e.jsxs("div", { className: "grid grid-cols-2 sm:grid-cols-3 md:grid-cols-5 gap-4", children: [
            /* @__PURE__ */ e.jsx(i, { label: "Engagements", value: d(t.total_engagements), color: "text-cyan-400" }),
            /* @__PURE__ */ e.jsx(i, { label: "Escapes", value: d(t.escapes), color: "text-emerald-400" }),
            /* @__PURE__ */ e.jsx(i, { label: "Deaths", value: d(t.deaths), color: "text-rose-400" }),
            /* @__PURE__ */ e.jsx(i, { label: "Escape Rate", value: _(t.escape_rate), color: "text-emerald-400" }),
            /* @__PURE__ */ e.jsx(i, { label: "Avg Duration", value: m(t.avg_duration_ms), color: "text-amber-400" })
          ] })
        ] }),
        /* @__PURE__ */ e.jsxs(c, { children: [
          /* @__PURE__ */ e.jsx("h3", { className: "text-xs font-bold uppercase tracking-widest text-slate-400 mb-4", children: "Kill Stats" }),
          /* @__PURE__ */ e.jsxs("div", { className: "grid grid-cols-2 sm:grid-cols-3 gap-4", children: [
            /* @__PURE__ */ e.jsx(i, { label: "Total Kills", value: d(t.total_kills), color: "text-rose-400" }),
            /* @__PURE__ */ e.jsx(i, { label: "Crossfire Kills", value: d(t.crossfire_count), color: "text-purple-400" })
          ] })
        ] }),
        /* @__PURE__ */ e.jsxs(c, { children: [
          /* @__PURE__ */ e.jsx("h3", { className: "text-xs font-bold uppercase tracking-widest text-slate-400 mb-4", children: "Movement" }),
          /* @__PURE__ */ e.jsxs("div", { className: "grid grid-cols-2 sm:grid-cols-3 gap-4", children: [
            /* @__PURE__ */ e.jsx(i, { label: "Avg Speed", value: t.avg_speed != null ? `${Math.round(t.avg_speed)}u/s` : "--", color: "text-cyan-400" }),
            /* @__PURE__ */ e.jsx(i, { label: "Sprint %", value: _(t.sprint_pct), color: "text-blue-400" }),
            /* @__PURE__ */ e.jsx(i, { label: "Dist/Life", value: t.avg_distance_per_life != null ? `${Math.round(t.avg_distance_per_life)}u` : "--", color: "text-indigo-400" })
          ] })
        ] })
      ] })
    ] }),
    /* @__PURE__ */ e.jsxs(c, { className: "mt-6", children: [
      /* @__PURE__ */ e.jsx("h3", { className: "text-xs font-bold uppercase tracking-widest text-slate-400 mb-4", children: "Reaction Times" }),
      /* @__PURE__ */ e.jsxs("div", { className: "grid grid-cols-1 sm:grid-cols-3 gap-6", children: [
        /* @__PURE__ */ e.jsxs(v, { children: [
          /* @__PURE__ */ e.jsx("div", { className: "text-[10px] text-slate-500 uppercase font-bold mb-1", children: "Return Fire" }),
          /* @__PURE__ */ e.jsx("div", { className: "text-2xl font-bold text-amber-400", children: m(t.avg_return_fire_ms) })
        ] }),
        /* @__PURE__ */ e.jsxs(v, { children: [
          /* @__PURE__ */ e.jsx("div", { className: "text-[10px] text-slate-500 uppercase font-bold mb-1", children: "Dodge" }),
          /* @__PURE__ */ e.jsx("div", { className: "text-2xl font-bold text-emerald-400", children: m(t.avg_dodge_ms) })
        ] }),
        /* @__PURE__ */ e.jsxs(v, { children: [
          /* @__PURE__ */ e.jsx("div", { className: "text-[10px] text-slate-500 uppercase font-bold mb-1", children: "Support Reaction" }),
          /* @__PURE__ */ e.jsx("div", { className: "text-2xl font-bold text-blue-400", children: m(t.avg_support_reaction_ms) })
        ] })
      ] })
    ] }),
    /* @__PURE__ */ e.jsxs("div", { className: "grid grid-cols-1 md:grid-cols-2 gap-6 mt-6", children: [
      /* @__PURE__ */ e.jsxs(c, { children: [
        /* @__PURE__ */ e.jsx("h3", { className: "text-xs font-bold uppercase tracking-widest text-slate-400 mb-4", children: "Spawn Timing" }),
        /* @__PURE__ */ e.jsx(M, { score: t.spawn_avg_score ?? 0, label: "Avg Score" }),
        /* @__PURE__ */ e.jsxs("div", { className: "grid grid-cols-2 gap-4 mt-4", children: [
          /* @__PURE__ */ e.jsx(i, { label: "Timed Kills", value: d(t.timed_kills), color: "text-emerald-400" }),
          /* @__PURE__ */ e.jsx(i, { label: "Avg Denial", value: m(t.avg_denial_ms), color: "text-amber-400" })
        ] })
      ] }),
      /* @__PURE__ */ e.jsxs(c, { children: [
        /* @__PURE__ */ e.jsx("h3", { className: "text-xs font-bold uppercase tracking-widest text-slate-400 mb-4", children: "Trade Stats" }),
        /* @__PURE__ */ e.jsx("div", { className: "flex items-center justify-center py-4", children: /* @__PURE__ */ e.jsxs("div", { className: "text-center", children: [
          /* @__PURE__ */ e.jsx("div", { className: "text-4xl font-black text-cyan-400", children: d(t.trades_made) }),
          /* @__PURE__ */ e.jsx("div", { className: "text-[10px] text-slate-500 uppercase font-bold mt-1", children: "Trades Made" })
        ] }) })
      ] })
    ] })
  ] }) : /* @__PURE__ */ e.jsx("div", { className: "mt-6 text-center text-slate-400 py-12", children: "No player GUID provided. Navigate here from the Proximity page." });
}
export {
  E as default
};
