import { r as g, j as e, S as N, c as p } from "./route-host-Ba3v8uFM.js";
import { w as Ve, x as $e, v as Fe, y as Ke, z as Ee, s as Ge, A as ze, B as Ae, C as Be, D as Ie, E as We, F as Oe } from "./hooks-CyQgvbI9.js";
import { C as w } from "./Chart-DkWq45SK.js";
import { D as Q } from "./DataTable-gbZQ6Kgl.js";
import { E as h } from "./EmptyState-CWT5OHyQ.js";
import { G as b } from "./GlassCard-C53TzD-y.js";
import { G as D } from "./GlassPanel-C-uUmQaB.js";
import { P as A } from "./PageHeader-CQ7BTOQj.js";
import { f as S } from "./format-BM7Gaq4w.js";
import { m as He } from "./game-assets-BMYaQb9B.js";
import { n as q, a as _ } from "./navigation-BDd1HkpE.js";
import { c as X } from "./createLucideIcon-BebMLfof.js";
import { G as Ue } from "./gamepad-2-DXqvfHtG.js";
import { U as Ze } from "./users-Blp4mgkM.js";
import { S as W } from "./skull-BhM2GlAn.js";
import { C as Y } from "./clock-KDxcQEST.js";
import { T as qe } from "./target-CZv2kTPB.js";
import { T as Je } from "./trophy-f4_RKZnn.js";
import { S as Qe } from "./shield-Bg1J0PTe.js";
import { Z as Xe } from "./zap-Chh6-OiF.js";
import { S as Ye } from "./swords-BNai6XKn.js";
import { C as ee } from "./crosshair-CPb1OWqx.js";
import { R as es } from "./radar-CtjAN0qD.js";
const ss = [
  ["path", { d: "m12 19-7-7 7-7", key: "1l729n" }],
  ["path", { d: "M19 12H5", key: "x3x0zl" }]
], as = X("arrow-left", ss);
const ts = [
  [
    "path",
    {
      d: "M14.106 5.553a2 2 0 0 0 1.788 0l3.659-1.83A1 1 0 0 1 21 4.619v12.764a1 1 0 0 1-.553.894l-4.553 2.277a2 2 0 0 1-1.788 0l-4.212-2.106a2 2 0 0 0-1.788 0l-3.659 1.83A1 1 0 0 1 3 19.381V6.618a1 1 0 0 1 .553-.894l4.553-2.277a2 2 0 0 1 1.788 0z",
      key: "169xi5"
    }
  ],
  ["path", { d: "M15 5.764v15", key: "1pn4in" }],
  ["path", { d: "M9 3.236v15", key: "1uimfh" }]
], se = X("map", ts), f = [
  "rgba(59, 130, 246, 0.7)",
  "rgba(244, 63, 94, 0.7)",
  "rgba(16, 185, 129, 0.7)",
  "rgba(245, 158, 11, 0.7)",
  "rgba(168, 85, 247, 0.7)",
  "rgba(20, 184, 166, 0.7)",
  "rgba(251, 113, 133, 0.7)",
  "rgba(132, 204, 22, 0.7)"
];
function R(s) {
  const a = Number(s || 0);
  if (!Number.isFinite(a) || a <= 0) return "0:00";
  const t = Math.floor(a / 60), l = Math.floor(a % 60);
  return `${t}:${String(l).padStart(2, "0")}`;
}
function T(s) {
  const a = Math.max(0, Math.round(Number(s || 0))), t = Math.floor(a / 60), l = a % 60;
  return `${t}:${String(l).padStart(2, "0")}`;
}
function L(s) {
  return s == null || !Number.isFinite(s) ? "--" : `${s.toFixed(1)}%`;
}
function M(s) {
  return (s || "Unknown").replace(/^maps[\\/]/, "").replace(/\.(bsp|pk3|arena)$/i, "").replace(/_/g, " ");
}
function O(s) {
  return s === 1 ? "Axis" : s === 2 ? "Allies" : "Tied";
}
function ae(s) {
  return s === 1 ? "text-rose-400" : s === 2 ? "text-blue-400" : "text-slate-400";
}
function ls(s, a) {
  if (s)
    return {
      session_date: s,
      round_start_unix: a?.round_start_unix ?? void 0
    };
}
function ns({
  activeRound: s,
  expandedMap: a,
  onClear: t
}) {
  return s ? /* @__PURE__ */ e.jsxs("div", { className: "glass-panel rounded-xl px-4 py-3 mb-6 flex items-center gap-3", children: [
    /* @__PURE__ */ e.jsx(qe, { className: "w-4 h-4 text-cyan-400" }),
    /* @__PURE__ */ e.jsxs("div", { className: "text-sm text-slate-300", children: [
      "Scoped to ",
      /* @__PURE__ */ e.jsxs("strong", { className: "text-white", children: [
        M(s.map_name),
        " R",
        s.round_number
      ] })
    ] }),
    /* @__PURE__ */ e.jsx(
      "button",
      {
        onClick: t,
        className: "ml-auto text-xs font-bold text-slate-400 hover:text-white transition",
        children: "Clear Scope"
      }
    )
  ] }) : a ? /* @__PURE__ */ e.jsxs("div", { className: "glass-panel rounded-xl px-4 py-3 mb-6 flex items-center gap-3", children: [
    /* @__PURE__ */ e.jsx(se, { className: "w-4 h-4 text-violet-400" }),
    /* @__PURE__ */ e.jsxs("div", { className: "text-sm text-slate-300", children: [
      "Viewing ",
      /* @__PURE__ */ e.jsx("strong", { className: "text-white", children: M(a) }),
      " — full session stats"
    ] }),
    /* @__PURE__ */ e.jsx(
      "button",
      {
        onClick: t,
        className: "ml-auto text-xs font-bold text-slate-400 hover:text-white transition",
        children: "Clear"
      }
    )
  ] }) : /* @__PURE__ */ e.jsxs("div", { className: "glass-panel rounded-xl px-4 py-3 text-sm text-slate-300 mb-6", children: [
    "Scope: ",
    /* @__PURE__ */ e.jsx("strong", { className: "text-white", children: "Full session" })
  ] });
}
function is({ active: s, onChange: a }) {
  const t = [
    { key: "summary", label: "Summary" },
    { key: "players", label: "Player Stats" },
    { key: "teamplay", label: "Teamplay" },
    { key: "charts", label: "Charts" }
  ];
  return /* @__PURE__ */ e.jsx("div", { className: "flex flex-wrap gap-1 bg-slate-800/80 rounded-lg p-1 mb-6", children: t.map((l) => /* @__PURE__ */ e.jsx(
    "button",
    {
      onClick: () => a(l.key),
      className: p(
        "px-4 py-2 rounded-md text-sm font-bold transition",
        s === l.key ? "bg-blue-500/20 text-blue-400" : "text-slate-400 hover:text-white"
      ),
      children: l.label
    },
    l.key
  )) });
}
function rs({ data: s, activeRound: a }) {
  const t = a ? a.duration_seconds ?? 0 : s.matches.reduce((d, n) => d + n.rounds.reduce((c, u) => c + (u.duration_seconds ?? 0), 0), 0), l = a ? 0 : s.players.reduce((d, n) => d + n.kills, 0), i = a ? 1 : s.matches.length, o = s.player_count;
  return /* @__PURE__ */ e.jsxs("div", { className: "grid grid-cols-2 md:grid-cols-5 gap-3 mb-6", children: [
    /* @__PURE__ */ e.jsx(C, { icon: Ue, label: a ? "Round" : "Rounds", value: a ? `R${a.round_number}` : s.round_count, color: "text-cyan-400" }),
    /* @__PURE__ */ e.jsx(C, { icon: se, label: "Maps", value: i, color: "text-violet-400" }),
    /* @__PURE__ */ e.jsx(C, { icon: Ze, label: "Players", value: o, color: "text-amber-400" }),
    /* @__PURE__ */ e.jsx(C, { icon: W, label: a ? "Round Kills" : "Session Kills", value: a ? "--" : S(l), color: "text-rose-400" }),
    /* @__PURE__ */ e.jsx(C, { icon: Y, label: "Duration", value: R(t), color: "text-slate-200" })
  ] });
}
function C({ icon: s, label: a, value: t, color: l }) {
  return /* @__PURE__ */ e.jsxs(b, { className: "!cursor-default", children: [
    /* @__PURE__ */ e.jsx(s, { className: p("w-5 h-5 mx-auto mb-2", l) }),
    /* @__PURE__ */ e.jsx("div", { className: p("text-xl font-black", l), children: t }),
    /* @__PURE__ */ e.jsx("div", { className: "text-[10px] text-slate-500 uppercase", children: a })
  ] });
}
function os({ scoring: s }) {
  if (!s?.available || s.team_a_total == null || s.team_b_total == null) return null;
  const a = s.team_a_total > s.team_b_total, t = s.team_a_total === s.team_b_total;
  return /* @__PURE__ */ e.jsxs("div", { className: "glass-card rounded-xl p-5 mb-6 flex items-center justify-center gap-6", children: [
    /* @__PURE__ */ e.jsxs("div", { className: "text-center", children: [
      /* @__PURE__ */ e.jsx("div", { className: "text-[10px] text-slate-500 uppercase mb-1", children: "Allies" }),
      /* @__PURE__ */ e.jsx("div", { className: p("text-3xl font-black", a && !t ? "text-blue-400" : "text-slate-300"), children: s.team_a_total })
    ] }),
    /* @__PURE__ */ e.jsx("div", { className: "text-slate-600 text-2xl font-bold", children: "vs" }),
    /* @__PURE__ */ e.jsxs("div", { className: "text-center", children: [
      /* @__PURE__ */ e.jsx("div", { className: "text-[10px] text-slate-500 uppercase mb-1", children: "Axis" }),
      /* @__PURE__ */ e.jsx("div", { className: p("text-3xl font-black", !a && !t ? "text-rose-400" : "text-slate-300"), children: s.team_b_total })
    ] })
  ] });
}
function ds({
  matches: s,
  activeRoundId: a,
  expandedMapIndex: t,
  onSelectMap: l,
  onSelectRound: i,
  onClearRound: o
}) {
  const d = t !== null ? s[t] : null;
  return /* @__PURE__ */ e.jsxs("div", { className: "mb-6", children: [
    /* @__PURE__ */ e.jsx("div", { className: "flex flex-wrap gap-3 mb-3", children: s.map((n, c) => {
      const u = t === c, K = u && a !== null;
      return /* @__PURE__ */ e.jsxs(
        "button",
        {
          onClick: () => l(c),
          className: p(
            "relative rounded-xl overflow-hidden border transition group",
            u ? "border-cyan-400/60 ring-1 ring-cyan-400/30" : "border-white/10 hover:border-white/25"
          ),
          style: { width: 160, height: 80 },
          children: [
            /* @__PURE__ */ e.jsx(
              "img",
              {
                src: He(n.map_name),
                alt: "",
                className: "w-full h-full object-cover opacity-60 group-hover:opacity-75 transition",
                onError: (E) => {
                  E.currentTarget.style.display = "none";
                }
              }
            ),
            /* @__PURE__ */ e.jsx("div", { className: "absolute inset-0 bg-gradient-to-t from-slate-900/90 via-slate-900/30 to-transparent" }),
            /* @__PURE__ */ e.jsxs("div", { className: "absolute top-2 right-2 bg-slate-900/80 text-[10px] text-slate-400 rounded px-1.5 py-0.5", children: [
              n.rounds.length,
              "R"
            ] }),
            /* @__PURE__ */ e.jsx("div", { className: "absolute bottom-2 left-2.5 text-xs font-bold text-white drop-shadow-lg leading-tight", children: M(n.map_name) }),
            K && /* @__PURE__ */ e.jsx("div", { className: "absolute top-2 left-2 w-1.5 h-1.5 rounded-full bg-cyan-400" })
          ]
        },
        `${n.map_name}-${c}`
      );
    }) }),
    d && /* @__PURE__ */ e.jsxs("div", { className: "glass-panel rounded-xl px-4 py-3 flex flex-wrap items-center gap-2", children: [
      /* @__PURE__ */ e.jsx("span", { className: "text-xs text-slate-500 uppercase tracking-wider mr-1", children: M(d.map_name) }),
      d.rounds.map((n) => /* @__PURE__ */ e.jsxs(
        "button",
        {
          onClick: () => i(n.round_id),
          className: p(
            "flex items-center gap-1.5 rounded-lg border px-3 py-1.5 text-xs font-bold transition",
            a === n.round_id ? "border-cyan-400/60 bg-cyan-500/10 text-cyan-300" : "border-white/10 bg-slate-900/40 text-slate-300 hover:border-white/20 hover:text-white"
          ),
          children: [
            /* @__PURE__ */ e.jsxs("span", { children: [
              "R",
              n.round_number
            ] }),
            /* @__PURE__ */ e.jsx("span", { className: p("text-[10px]", ae(n.winner_team)), children: O(n.winner_team) }),
            n.duration_seconds ? /* @__PURE__ */ e.jsx("span", { className: "text-slate-500 font-mono", children: R(n.duration_seconds) }) : null
          ]
        },
        n.round_id
      )),
      /* @__PURE__ */ e.jsx(
        "button",
        {
          onClick: o,
          className: p(
            "rounded-lg border px-3 py-1.5 text-xs font-bold transition",
            a === null ? "border-violet-400/60 bg-violet-500/10 text-violet-300" : "border-white/10 bg-slate-900/40 text-slate-400 hover:text-white hover:border-white/20"
          ),
          children: "Full Map"
        }
      )
    ] })
  ] });
}
function B({
  label: s,
  color: a,
  icon: t,
  players: l,
  getValue: i,
  formatValue: o
}) {
  if (l.length === 0) return null;
  const d = l.reduce((n, c) => i(c) > i(n) ? c : n, l[0]);
  return /* @__PURE__ */ e.jsx(b, { onClick: () => _(d.player_name), children: /* @__PURE__ */ e.jsxs("div", { className: "flex items-center gap-3", children: [
    /* @__PURE__ */ e.jsx(t, { className: p("w-6 h-6", a) }),
    /* @__PURE__ */ e.jsxs("div", { children: [
      /* @__PURE__ */ e.jsx("div", { className: "text-[10px] text-slate-500 uppercase", children: s }),
      /* @__PURE__ */ e.jsx("div", { className: "text-lg font-black text-white", children: d.player_name }),
      /* @__PURE__ */ e.jsx("div", { className: p("text-sm font-bold", a), children: o(i(d)) })
    ] })
  ] }) });
}
function cs({
  data: s,
  activeRoundId: a,
  expandedMapIndex: t,
  onSelectMap: l,
  onSelectRound: i,
  onClearRound: o
}) {
  return /* @__PURE__ */ e.jsxs(e.Fragment, { children: [
    /* @__PURE__ */ e.jsx(os, { scoring: s.scoring }),
    /* @__PURE__ */ e.jsx(
      ds,
      {
        matches: s.matches,
        activeRoundId: a,
        expandedMapIndex: t,
        onSelectMap: l,
        onSelectRound: i,
        onClearRound: o
      }
    ),
    /* @__PURE__ */ e.jsxs("div", { className: "grid grid-cols-1 md:grid-cols-3 gap-4 mb-6", children: [
      /* @__PURE__ */ e.jsx(B, { label: "MVP (DPM)", color: "text-yellow-500", icon: Je, players: s.players, getValue: (d) => d.dpm, formatValue: (d) => d.toFixed(1) }),
      /* @__PURE__ */ e.jsx(B, { label: "Most Kills", color: "text-rose-400", icon: W, players: s.players, getValue: (d) => d.kills, formatValue: (d) => String(d) }),
      /* @__PURE__ */ e.jsx(B, { label: "Most Revives", color: "text-emerald-400", icon: Qe, players: s.players, getValue: (d) => d.revives_given, formatValue: (d) => String(d) })
    ] }),
    /* @__PURE__ */ e.jsxs("div", { className: "glass-card rounded-xl p-5 mb-6", children: [
      /* @__PURE__ */ e.jsx("div", { className: "text-sm font-bold text-white mb-3", children: "Session Pulse" }),
      /* @__PURE__ */ e.jsxs("div", { className: "grid grid-cols-2 lg:grid-cols-4 gap-3 text-sm", children: [
        /* @__PURE__ */ e.jsx($, { icon: Xe, label: "Top DPM", value: s.players[0] ? `${s.players[0].player_name} · ${s.players[0].dpm.toFixed(1)}` : "--" }),
        /* @__PURE__ */ e.jsx($, { icon: Ye, label: "Best K/D", value: s.players[0] ? `${[...s.players].sort((d, n) => n.kd - d.kd)[0].kd.toFixed(2)}` : "--" }),
        /* @__PURE__ */ e.jsx($, { icon: ee, label: "Most Gibs", value: String(Math.max(...s.players.map((d) => d.gibs), 0)) }),
        /* @__PURE__ */ e.jsx($, { icon: Y, label: "Most Denied", value: T(Math.max(...s.players.map((d) => d.denied_playtime ?? 0), 0)) })
      ] })
    ] }),
    /* @__PURE__ */ e.jsx(ms, { matches: s.matches, activeRoundId: a, onSelectRound: i })
  ] });
}
function $({ icon: s, label: a, value: t }) {
  return /* @__PURE__ */ e.jsxs("div", { className: "glass-panel rounded-lg p-3", children: [
    /* @__PURE__ */ e.jsxs("div", { className: "flex items-center gap-2 text-slate-500 text-[11px] uppercase", children: [
      /* @__PURE__ */ e.jsx(s, { className: "w-4 h-4 text-cyan-400" }),
      a
    ] }),
    /* @__PURE__ */ e.jsx("div", { className: "mt-2 text-white font-bold", children: t })
  ] });
}
function ms({
  matches: s,
  activeRoundId: a,
  onSelectRound: t
}) {
  const l = s.flatMap((i) => i.rounds.map((o) => ({ ...o, match_map: i.map_name })));
  return l.length === 0 ? /* @__PURE__ */ e.jsx(h, { message: "No rounds found for this session." }) : /* @__PURE__ */ e.jsx("div", { className: "glass-panel rounded-xl overflow-hidden", children: /* @__PURE__ */ e.jsxs("table", { className: "w-full text-left", children: [
    /* @__PURE__ */ e.jsx("thead", { children: /* @__PURE__ */ e.jsxs("tr", { className: "border-b border-white/10 bg-white/5 text-xs uppercase text-slate-500", children: [
      /* @__PURE__ */ e.jsx("th", { className: "px-4 py-3", children: "Map" }),
      /* @__PURE__ */ e.jsx("th", { className: "px-4 py-3", children: "Round" }),
      /* @__PURE__ */ e.jsx("th", { className: "px-4 py-3", children: "Winner" }),
      /* @__PURE__ */ e.jsx("th", { className: "px-4 py-3", children: "Score" }),
      /* @__PURE__ */ e.jsx("th", { className: "px-4 py-3", children: "Duration" }),
      /* @__PURE__ */ e.jsx("th", { className: "px-4 py-3", children: "Date" }),
      /* @__PURE__ */ e.jsx("th", { className: "px-4 py-3 text-right", children: "Scope" })
    ] }) }),
    /* @__PURE__ */ e.jsx("tbody", { children: l.map((i) => /* @__PURE__ */ e.jsxs("tr", { className: "border-b border-white/5 hover:bg-white/5", children: [
      /* @__PURE__ */ e.jsx("td", { className: "px-4 py-3 text-white font-semibold", children: M(i.match_map) }),
      /* @__PURE__ */ e.jsxs("td", { className: "px-4 py-3 text-slate-300", children: [
        "R",
        i.round_number
      ] }),
      /* @__PURE__ */ e.jsx("td", { className: p("px-4 py-3", ae(i.winner_team)), children: O(i.winner_team) }),
      /* @__PURE__ */ e.jsx("td", { className: "px-4 py-3 text-slate-300", children: i.allies_score != null ? /* @__PURE__ */ e.jsxs(e.Fragment, { children: [
        /* @__PURE__ */ e.jsx("span", { className: "text-blue-400", children: i.allies_score }),
        /* @__PURE__ */ e.jsx("span", { className: "text-slate-600", children: " — " }),
        /* @__PURE__ */ e.jsx("span", { className: "text-rose-400", children: i.axis_score })
      ] }) : "—" }),
      /* @__PURE__ */ e.jsx("td", { className: "px-4 py-3 text-slate-400 font-mono", children: R(i.duration_seconds) }),
      /* @__PURE__ */ e.jsx("td", { className: "px-4 py-3 text-slate-500 text-xs", children: [i.round_date, i.round_time].filter(Boolean).join(" · ") || "--" }),
      /* @__PURE__ */ e.jsx("td", { className: "px-4 py-3 text-right", children: /* @__PURE__ */ e.jsx(
        "button",
        {
          onClick: () => t(i.round_id),
          className: p(
            "px-3 py-1.5 rounded-lg text-xs font-bold transition",
            a === i.round_id ? "bg-cyan-500/20 text-cyan-300" : "bg-slate-800 text-slate-300 hover:text-white"
          ),
          children: a === i.round_id ? "Scoped" : "Scope"
        }
      ) })
    ] }, i.round_id)) })
  ] }) });
}
const xs = [
  {
    key: "name",
    label: "Player",
    render: (s) => /* @__PURE__ */ e.jsx("button", { onClick: () => _(s.name), className: "text-blue-400 hover:text-blue-300 font-semibold text-left", children: s.name })
  },
  { key: "kills", label: "Kills", sortable: !0, sortValue: (s) => s.kills, className: "font-mono text-white" },
  { key: "deaths", label: "Deaths", sortable: !0, sortValue: (s) => s.deaths, className: "font-mono text-slate-400" },
  { key: "dpm", label: "DPM", sortable: !0, sortValue: (s) => s.dpm, className: "font-mono text-cyan-400", render: (s) => s.dpm.toFixed(1) },
  { key: "damage", label: "Dmg", sortable: !0, sortValue: (s) => s.damageGiven, className: "font-mono text-white", render: (s) => S(s.damageGiven) },
  { key: "selfKills", label: "Self", sortable: !0, sortValue: (s) => s.selfKills, className: "font-mono text-amber-400" },
  { key: "deniedSeconds", label: "Denied", sortable: !0, sortValue: (s) => s.deniedSeconds, className: "font-mono text-rose-300", render: (s) => T(s.deniedSeconds) },
  { key: "alivePct", label: "Alive%", sortable: !0, sortValue: (s) => s.alivePct ?? -1, className: "font-mono text-emerald-300", render: (s) => L(s.alivePct) },
  { key: "playedPct", label: "Played%", sortable: !0, sortValue: (s) => s.playedPct ?? -1, className: "font-mono text-violet-300", render: (s) => L(s.playedPct) }
];
function te({
  preys: s,
  enemies: a,
  loading: t
}) {
  return t ? /* @__PURE__ */ e.jsx(N, { variant: "card", count: 1 }) : !s.length && !a.length ? null : /* @__PURE__ */ e.jsxs("div", { className: "grid grid-cols-1 lg:grid-cols-2 gap-4 mt-4", children: [
    /* @__PURE__ */ e.jsxs("div", { className: "glass-panel rounded-xl p-4", children: [
      /* @__PURE__ */ e.jsxs("div", { className: "flex items-center gap-2 mb-3", children: [
        /* @__PURE__ */ e.jsx(ee, { className: "w-4 h-4 text-emerald-400" }),
        /* @__PURE__ */ e.jsx("div", { className: "text-sm font-bold text-white", children: "Easiest Preys" })
      ] }),
      s.length ? /* @__PURE__ */ e.jsx("div", { className: "space-y-2", children: s.map((l, i) => /* @__PURE__ */ e.jsxs("div", { className: "flex items-center justify-between rounded-lg bg-slate-900/50 px-3 py-2 text-sm", children: [
        /* @__PURE__ */ e.jsxs("div", { className: "flex items-center gap-2 min-w-0", children: [
          /* @__PURE__ */ e.jsx("span", { className: "text-slate-600 text-xs font-mono w-4", children: i + 1 }),
          /* @__PURE__ */ e.jsx(
            "button",
            {
              onClick: () => _(l.opponent_name),
              className: "text-white font-semibold truncate hover:text-cyan-400 transition",
              children: l.opponent_name
            }
          )
        ] }),
        /* @__PURE__ */ e.jsxs("div", { className: "flex items-center gap-3 text-xs shrink-0", children: [
          /* @__PURE__ */ e.jsxs("span", { className: "text-emerald-400 font-mono", children: [
            l.kills,
            "K"
          ] }),
          /* @__PURE__ */ e.jsxs("span", { className: "text-rose-400 font-mono", children: [
            l.deaths,
            "D"
          ] }),
          /* @__PURE__ */ e.jsx("span", { className: "text-slate-400 font-mono", children: l.kd.toFixed(1) })
        ] })
      ] }, l.opponent_guid ?? l.opponent_name)) }) : /* @__PURE__ */ e.jsx("div", { className: "text-xs text-slate-500 py-2", children: "No prey data" })
    ] }),
    /* @__PURE__ */ e.jsxs("div", { className: "glass-panel rounded-xl p-4", children: [
      /* @__PURE__ */ e.jsxs("div", { className: "flex items-center gap-2 mb-3", children: [
        /* @__PURE__ */ e.jsx(W, { className: "w-4 h-4 text-rose-400" }),
        /* @__PURE__ */ e.jsx("div", { className: "text-sm font-bold text-white", children: "Worst Enemies" })
      ] }),
      a.length ? /* @__PURE__ */ e.jsx("div", { className: "space-y-2", children: a.map((l, i) => /* @__PURE__ */ e.jsxs("div", { className: "flex items-center justify-between rounded-lg bg-slate-900/50 px-3 py-2 text-sm", children: [
        /* @__PURE__ */ e.jsxs("div", { className: "flex items-center gap-2 min-w-0", children: [
          /* @__PURE__ */ e.jsx("span", { className: "text-slate-600 text-xs font-mono w-4", children: i + 1 }),
          /* @__PURE__ */ e.jsx(
            "button",
            {
              onClick: () => _(l.opponent_name),
              className: "text-white font-semibold truncate hover:text-cyan-400 transition",
              children: l.opponent_name
            }
          )
        ] }),
        /* @__PURE__ */ e.jsxs("div", { className: "flex items-center gap-3 text-xs shrink-0", children: [
          /* @__PURE__ */ e.jsxs("span", { className: "text-emerald-400 font-mono", children: [
            l.kills,
            "K"
          ] }),
          /* @__PURE__ */ e.jsxs("span", { className: "text-rose-400 font-mono", children: [
            l.deaths,
            "D"
          ] }),
          /* @__PURE__ */ e.jsx("span", { className: "text-slate-400 font-mono", children: l.kd.toFixed(1) })
        ] })
      ] }, l.opponent_guid ?? l.opponent_name)) }) : /* @__PURE__ */ e.jsx("div", { className: "text-xs text-slate-500 py-2", children: "No enemy data" })
    ] })
  ] });
}
function us({
  row: s,
  weaponMastery: a,
  loading: t,
  vsPreys: l,
  vsEnemies: i,
  vsLoading: o
}) {
  return s ? /* @__PURE__ */ e.jsxs("div", { className: "glass-card rounded-xl p-5 mt-6", children: [
    /* @__PURE__ */ e.jsxs("div", { className: "flex items-center justify-between gap-3 mb-4", children: [
      /* @__PURE__ */ e.jsxs("div", { children: [
        /* @__PURE__ */ e.jsx("div", { className: "text-xs uppercase tracking-wider text-slate-500", children: "Player Focus" }),
        /* @__PURE__ */ e.jsx("div", { className: "text-xl font-black text-white", children: s.name })
      ] }),
      /* @__PURE__ */ e.jsx("button", { onClick: () => _(s.name), className: "text-sm text-cyan-400 hover:text-white transition", children: "Open Profile" })
    ] }),
    /* @__PURE__ */ e.jsxs("div", { className: "grid grid-cols-2 md:grid-cols-4 gap-3 mb-4", children: [
      /* @__PURE__ */ e.jsx(x, { label: "Kills", value: String(s.kills) }),
      /* @__PURE__ */ e.jsx(x, { label: "DPM", value: s.dpm.toFixed(1) }),
      /* @__PURE__ */ e.jsx(x, { label: "Self Kills", value: String(s.selfKills) }),
      /* @__PURE__ */ e.jsx(x, { label: "Time Denied", value: T(s.deniedSeconds) })
    ] }),
    t ? /* @__PURE__ */ e.jsx(N, { variant: "card", count: 1 }) : /* @__PURE__ */ e.jsxs("div", { className: "glass-panel rounded-xl p-4", children: [
      /* @__PURE__ */ e.jsx("div", { className: "text-sm font-bold text-white mb-3", children: "Weapon Mastery" }),
      a?.weapons?.length ? /* @__PURE__ */ e.jsx("div", { className: "space-y-2", children: a.weapons.map((d) => /* @__PURE__ */ e.jsxs("div", { className: "flex items-center justify-between rounded-lg bg-slate-900/50 px-3 py-2 text-sm", children: [
        /* @__PURE__ */ e.jsxs("div", { children: [
          /* @__PURE__ */ e.jsx("div", { className: "font-semibold text-white", children: d.name }),
          /* @__PURE__ */ e.jsxs("div", { className: "text-xs text-slate-500", children: [
            d.kills > 0 ? `${d.kills} kills · ` : "",
            d.accuracy.toFixed(1),
            "% acc"
          ] })
        ] }),
        /* @__PURE__ */ e.jsxs("div", { className: "text-right text-xs", children: [
          d.headshots > 0 && /* @__PURE__ */ e.jsxs("div", { className: "text-cyan-300", children: [
            d.headshots,
            " HS"
          ] }),
          /* @__PURE__ */ e.jsxs("div", { className: "text-slate-500", children: [
            d.hits,
            "/",
            d.shots
          ] })
        ] })
      ] }, d.weapon_key)) }) : /* @__PURE__ */ e.jsx(h, { message: "No weapon mastery data for this player.", className: "!py-6" })
    ] }),
    /* @__PURE__ */ e.jsx(te, { preys: l, enemies: i, loading: o })
  ] }) : null;
}
function ps({ detail: s, loading: a, vsPreys: t, vsEnemies: l, vsLoading: i }) {
  return a ? /* @__PURE__ */ e.jsx(N, { variant: "card", count: 2 }) : s ? /* @__PURE__ */ e.jsxs("div", { className: "glass-card rounded-xl p-5 mt-6", children: [
    /* @__PURE__ */ e.jsxs("div", { className: "flex items-center gap-3 mb-4", children: [
      /* @__PURE__ */ e.jsx(es, { className: "w-5 h-5 text-cyan-400" }),
      /* @__PURE__ */ e.jsxs("div", { children: [
        /* @__PURE__ */ e.jsx("div", { className: "text-xs uppercase tracking-wider text-slate-500", children: "Round Drilldown" }),
        /* @__PURE__ */ e.jsx("div", { className: "text-xl font-black text-white", children: s.player_name })
      ] })
    ] }),
    /* @__PURE__ */ e.jsxs("div", { className: "grid grid-cols-2 md:grid-cols-4 gap-3 mb-4", children: [
      /* @__PURE__ */ e.jsx(x, { label: "Kills", value: String(s.combat.kills) }),
      /* @__PURE__ */ e.jsx(x, { label: "Damage", value: S(s.combat.damage_given) }),
      /* @__PURE__ */ e.jsx(x, { label: "Self Kills", value: String(s.misc.self_kills) }),
      /* @__PURE__ */ e.jsx(x, { label: "Time Denied", value: T(s.time.denied_playtime) })
    ] }),
    /* @__PURE__ */ e.jsxs("div", { className: "grid grid-cols-1 lg:grid-cols-2 gap-4", children: [
      /* @__PURE__ */ e.jsxs(D, { className: "!p-4", children: [
        /* @__PURE__ */ e.jsx("div", { className: "text-sm font-bold text-white mb-3", children: "Combat" }),
        /* @__PURE__ */ e.jsx(
          J,
          {
            items: [
              ["Deaths", String(s.combat.deaths)],
              ["Headshots", String(s.combat.headshots)],
              ["Gibs", String(s.combat.gibs)],
              ["Accuracy", `${s.combat.accuracy.toFixed(1)}%`],
              ["Revives Given", String(s.support.revives_given)],
              ["Times Revived", String(s.support.times_revived)]
            ]
          }
        )
      ] }),
      /* @__PURE__ */ e.jsxs(D, { className: "!p-4", children: [
        /* @__PURE__ */ e.jsx("div", { className: "text-sm font-bold text-white mb-3", children: "Objectives & Time" }),
        /* @__PURE__ */ e.jsx(
          J,
          {
            items: [
              ["Objective Steals", String(s.objectives.stolen)],
              ["Objective Returns", String(s.objectives.returned)],
              ["Dynos Planted", String(s.objectives.dynamites_planted)],
              ["Dynos Defused", String(s.objectives.dynamites_defused)],
              ["Dead Minutes", s.time.dead_minutes.toFixed(1)],
              ["Played Seconds", String(s.time.played_seconds)]
            ]
          }
        )
      ] })
    ] }),
    /* @__PURE__ */ e.jsxs("div", { className: "glass-panel rounded-xl p-4 mt-4", children: [
      /* @__PURE__ */ e.jsx("div", { className: "text-sm font-bold text-white mb-3", children: "Weapons" }),
      s.weapons.length ? /* @__PURE__ */ e.jsx("div", { className: "space-y-2", children: s.weapons.map((o) => /* @__PURE__ */ e.jsxs("div", { className: "flex items-center justify-between rounded-lg bg-slate-900/50 px-3 py-2 text-sm", children: [
        /* @__PURE__ */ e.jsx("div", { className: "font-semibold text-white", children: o.name }),
        /* @__PURE__ */ e.jsxs("div", { className: "text-right text-xs text-slate-400", children: [
          o.kills,
          "K / ",
          o.deaths,
          "D · ",
          o.accuracy.toFixed(1),
          "%"
        ] })
      ] }, o.name)) }) : /* @__PURE__ */ e.jsx(h, { message: "No weapon detail found for this round.", className: "!py-6" })
    ] }),
    /* @__PURE__ */ e.jsx(te, { preys: t, enemies: l, loading: i })
  ] }) : /* @__PURE__ */ e.jsx(h, { message: "Round drilldown is not available for this player.", className: "!py-6" });
}
function x({ label: s, value: a }) {
  return /* @__PURE__ */ e.jsxs("div", { className: "glass-panel rounded-lg p-3", children: [
    /* @__PURE__ */ e.jsx("div", { className: "text-[11px] text-slate-500 uppercase", children: s }),
    /* @__PURE__ */ e.jsx("div", { className: "text-white font-bold mt-1", children: a })
  ] });
}
function J({ items: s }) {
  return /* @__PURE__ */ e.jsx("div", { className: "space-y-2 text-sm", children: s.map(([a, t]) => /* @__PURE__ */ e.jsxs("div", { className: "flex items-center justify-between border-b border-white/5 pb-2 last:border-0 last:pb-0", children: [
    /* @__PURE__ */ e.jsx("span", { className: "text-slate-400", children: a }),
    /* @__PURE__ */ e.jsx("span", { className: "text-white font-semibold", children: t })
  ] }, a)) });
}
function hs({
  rows: s,
  selectedGuid: a,
  onSelectPlayer: t
}) {
  return s.length ? /* @__PURE__ */ e.jsx("div", { className: "glass-panel rounded-xl p-0 overflow-hidden", children: /* @__PURE__ */ e.jsx(
    Q,
    {
      columns: xs,
      data: s,
      keyFn: (l) => l.guid,
      defaultSort: { key: "dpm", dir: "desc" },
      stickyHeader: !0,
      onRowClick: (l) => t(l.guid),
      rowClassName: (l) => p(a === l.guid && "bg-cyan-500/10")
    }
  ) }) : /* @__PURE__ */ e.jsx(h, { message: "No player data for this scope." });
}
function gs({
  loading: s,
  summary: a,
  events: t,
  duos: l,
  teamplay: i,
  movers: o
}) {
  return s ? /* @__PURE__ */ e.jsx(N, { variant: "card", count: 4 }) : !(a?.ready || t?.events?.length || l?.duos?.length || i?.crossfire_kills?.length || i?.sync?.length || i?.focus_survival?.length || o?.distance?.length || o?.sprint?.length || o?.reaction?.length || o?.survival?.length) ? /* @__PURE__ */ e.jsx(h, { message: "No proximity signal data is available for this scope yet." }) : /* @__PURE__ */ e.jsxs("div", { className: "space-y-6", children: [
    /* @__PURE__ */ e.jsxs("div", { className: "grid grid-cols-2 md:grid-cols-4 gap-3", children: [
      /* @__PURE__ */ e.jsx(x, { label: "Trade Opps", value: String(a?.trade_opportunities ?? 0) }),
      /* @__PURE__ */ e.jsx(x, { label: "Trade Success", value: String(a?.trade_success ?? 0) }),
      /* @__PURE__ */ e.jsx(x, { label: "Missed Trades", value: String(a?.missed_trade_candidates ?? 0) }),
      /* @__PURE__ */ e.jsx(x, { label: "Isolation Deaths", value: String(a?.isolation_deaths ?? 0) })
    ] }),
    /* @__PURE__ */ e.jsxs("div", { className: "grid grid-cols-1 xl:grid-cols-2 gap-6", children: [
      /* @__PURE__ */ e.jsxs(D, { className: "!p-5", children: [
        /* @__PURE__ */ e.jsx("div", { className: "text-sm font-bold text-white mb-4", children: "Recent Trade Events" }),
        t?.events?.length ? /* @__PURE__ */ e.jsx("div", { className: "space-y-2", children: t.events.slice(0, 10).map((n, c) => /* @__PURE__ */ e.jsxs("div", { className: "rounded-lg bg-slate-900/50 px-3 py-2 text-sm", children: [
          /* @__PURE__ */ e.jsxs("div", { className: "font-semibold text-white", children: [
            n.victim,
            " vs ",
            n.killer
          ] }),
          /* @__PURE__ */ e.jsxs("div", { className: "text-xs text-slate-400", children: [
            n.map,
            " R",
            n.round,
            " · success ",
            n.success,
            " · attempts ",
            n.attempts,
            " · missed ",
            n.missed
          ] })
        ] }, `${n.round_id ?? n.date}-${c}`)) }) : /* @__PURE__ */ e.jsx(h, { message: "No trade events for this scope.", className: "!py-6" })
      ] }),
      /* @__PURE__ */ e.jsxs(D, { className: "!p-5", children: [
        /* @__PURE__ */ e.jsx("div", { className: "text-sm font-bold text-white mb-4", children: "Top Synergy Duos" }),
        l?.duos?.length ? /* @__PURE__ */ e.jsx("div", { className: "space-y-2", children: l.duos.map((n, c) => /* @__PURE__ */ e.jsxs("div", { className: "rounded-lg bg-slate-900/50 px-3 py-2 text-sm", children: [
          /* @__PURE__ */ e.jsxs("div", { className: "font-semibold text-white", children: [
            n.player1_name || n.player1,
            " + ",
            n.player2_name || n.player2
          ] }),
          /* @__PURE__ */ e.jsxs("div", { className: "text-xs text-slate-400", children: [
            n.crossfire_kills ?? n.crossfires ?? 0,
            " crossfires · ",
            Math.round(n.avg_delay_ms ?? 0),
            "ms avg delay"
          ] })
        ] }, `${n.player1_name ?? n.player1}-${n.player2_name ?? n.player2}-${c}`)) }) : /* @__PURE__ */ e.jsx(h, { message: "No duo signal data for this scope.", className: "!py-6" })
      ] })
    ] }),
    /* @__PURE__ */ e.jsxs("div", { className: "grid grid-cols-1 xl:grid-cols-3 gap-6", children: [
      /* @__PURE__ */ e.jsx(I, { title: "Crossfire Kills", rows: i?.crossfire_kills ?? [], valueLabel: "crossfire_kills", formatValue: (n) => String(n.crossfire_kills ?? n.count ?? 0) }),
      /* @__PURE__ */ e.jsx(I, { title: "Team Sync", rows: i?.sync ?? [], valueLabel: "sync", formatValue: (n) => String(n.crossfire_participations ?? n.count ?? 0) }),
      /* @__PURE__ */ e.jsx(I, { title: "Focus Survival", rows: i?.focus_survival ?? [], valueLabel: "survival", formatValue: (n) => L(n.survival_rate_pct) })
    ] }),
    /* @__PURE__ */ e.jsxs("div", { className: "grid grid-cols-1 xl:grid-cols-2 gap-6", children: [
      /* @__PURE__ */ e.jsx(F, { title: "Distance Leaders", rows: o?.distance ?? [], formatValue: (n) => `${(n.total_distance ?? 0).toFixed(1)}u` }),
      /* @__PURE__ */ e.jsx(F, { title: "Sprint Leaders", rows: o?.sprint ?? [], formatValue: (n) => L(n.sprint_pct) }),
      /* @__PURE__ */ e.jsx(F, { title: "Reaction Leaders", rows: o?.reaction ?? [], formatValue: (n) => n.reaction_ms != null ? `${Math.round(n.reaction_ms)}ms` : "--" }),
      /* @__PURE__ */ e.jsx(F, { title: "Survival Leaders", rows: o?.survival ?? [], formatValue: (n) => n.duration_ms != null ? R(n.duration_ms / 1e3) : "--" })
    ] })
  ] });
}
function I({
  title: s,
  rows: a,
  valueLabel: t,
  formatValue: l
}) {
  return /* @__PURE__ */ e.jsxs(D, { className: "!p-5", children: [
    /* @__PURE__ */ e.jsx("div", { className: "text-sm font-bold text-white mb-4", children: s }),
    a.length ? /* @__PURE__ */ e.jsx("div", { className: "space-y-2", children: a.map((i, o) => /* @__PURE__ */ e.jsxs("div", { className: "flex items-center justify-between rounded-lg bg-slate-900/50 px-3 py-2 text-sm", children: [
      /* @__PURE__ */ e.jsx("span", { className: "font-semibold text-white", children: i.name }),
      /* @__PURE__ */ e.jsx("span", { className: "text-cyan-300 font-mono", children: l(i) })
    ] }, `${i.name}-${o}`)) }) : /* @__PURE__ */ e.jsx(h, { message: "No data in this signal set.", className: "!py-6" })
  ] });
}
function F({
  title: s,
  rows: a,
  formatValue: t
}) {
  return /* @__PURE__ */ e.jsxs(D, { className: "!p-5", children: [
    /* @__PURE__ */ e.jsx("div", { className: "text-sm font-bold text-white mb-4", children: s }),
    a.length ? /* @__PURE__ */ e.jsx("div", { className: "space-y-2", children: a.map((l, i) => /* @__PURE__ */ e.jsxs("div", { className: "flex items-center justify-between rounded-lg bg-slate-900/50 px-3 py-2 text-sm", children: [
      /* @__PURE__ */ e.jsx("span", { className: "font-semibold text-white", children: l.name }),
      /* @__PURE__ */ e.jsx("span", { className: "text-violet-300 font-mono", children: t(l) })
    ] }, `${l.name}-${i}`)) }) : /* @__PURE__ */ e.jsx(h, { message: "No mover data in this scope.", className: "!py-6" })
  ] });
}
function bs({ data: s }) {
  const a = s.players.slice(0, 8), t = a[0]?.dpm_timeline?.map((o) => o.label) ?? [], l = {
    labels: t,
    datasets: a.map((o, d) => ({
      label: o.name,
      data: o.dpm_timeline.map((n) => n.dpm),
      borderColor: f[d % f.length],
      backgroundColor: f[d % f.length],
      borderWidth: 2,
      tension: 0.3
    }))
  }, i = {
    labels: a.map((o) => o.name),
    datasets: [
      {
        label: "Aggression",
        data: a.map((o) => o.playstyle.aggression),
        backgroundColor: "rgba(59, 130, 246, 0.7)"
      },
      {
        label: "Discipline",
        data: a.map((o) => 100 - o.advanced_metrics.damage_efficiency),
        backgroundColor: "rgba(16, 185, 129, 0.6)"
      }
    ]
  };
  return /* @__PURE__ */ e.jsxs("div", { className: "space-y-6", children: [
    /* @__PURE__ */ e.jsxs("div", { className: "grid grid-cols-1 lg:grid-cols-2 gap-6", children: [
      /* @__PURE__ */ e.jsxs(b, { className: "!cursor-default", children: [
        /* @__PURE__ */ e.jsx("div", { className: "text-sm font-bold text-white mb-4", children: "DPM Timeline" }),
        t.length ? /* @__PURE__ */ e.jsx(
          w,
          {
            type: "line",
            data: l,
            height: 320,
            options: {
              plugins: { legend: { labels: { color: "#94a3b8", font: { size: 10 } } } },
              scales: {
                x: { ticks: { color: "#94a3b8", font: { size: 10 } }, grid: { color: "rgba(148,163,184,0.1)" } },
                y: { ticks: { color: "#94a3b8" }, grid: { color: "rgba(148,163,184,0.1)" } }
              }
            }
          }
        ) : /* @__PURE__ */ e.jsx(h, { message: "No timeline points are available for this session.", className: "!py-6" })
      ] }),
      /* @__PURE__ */ e.jsxs(b, { className: "!cursor-default", children: [
        /* @__PURE__ */ e.jsx("div", { className: "text-sm font-bold text-white mb-4", children: "Aggression vs Discipline" }),
        /* @__PURE__ */ e.jsx(
          w,
          {
            type: "bar",
            data: i,
            height: 320,
            options: {
              indexAxis: "y",
              plugins: { legend: { labels: { color: "#94a3b8", font: { size: 10 } } } },
              scales: {
                x: { ticks: { color: "#94a3b8" }, grid: { color: "rgba(148,163,184,0.1)" } },
                y: { ticks: { color: "#e2e8f0", font: { size: 11 } }, grid: { display: !1 } }
              }
            }
          }
        )
      ] })
    ] }),
    /* @__PURE__ */ e.jsx("div", { className: "grid grid-cols-1 md:grid-cols-2 xl:grid-cols-3 gap-4", children: s.players.slice(0, 6).map((o) => /* @__PURE__ */ e.jsxs(b, { onClick: () => _(o.name), children: [
      /* @__PURE__ */ e.jsx("div", { className: "text-lg font-black text-white", children: o.name }),
      /* @__PURE__ */ e.jsxs("div", { className: "grid grid-cols-2 gap-2 mt-4 text-sm", children: [
        /* @__PURE__ */ e.jsx(x, { label: "Survival", value: L(o.advanced_metrics.survival_rate) }),
        /* @__PURE__ */ e.jsx(x, { label: "Dmg Efficiency", value: o.advanced_metrics.damage_efficiency.toFixed(1) }),
        /* @__PURE__ */ e.jsx(x, { label: "Time Denied", value: T(o.advanced_metrics.time_denied_raw_seconds) }),
        /* @__PURE__ */ e.jsx(x, { label: "Self Kills", value: String(o.combat_defense.self_kills) })
      ] })
    ] }, o.name)) })
  ] });
}
function js({ data: s }) {
  const a = O(s.winner_team);
  return /* @__PURE__ */ e.jsxs(b, { className: "!cursor-default", children: [
    /* @__PURE__ */ e.jsx("div", { className: "text-sm font-bold text-white mb-4", children: "Round Summary" }),
    /* @__PURE__ */ e.jsxs("div", { className: "grid grid-cols-2 gap-3 text-sm", children: [
      /* @__PURE__ */ e.jsx(x, { label: "Map", value: M(s.map_name || "Unknown") }),
      /* @__PURE__ */ e.jsx(x, { label: "Round", value: s.round_label || `R${s.round_number}` }),
      /* @__PURE__ */ e.jsx(x, { label: "Date", value: s.round_date || "--" }),
      /* @__PURE__ */ e.jsx(x, { label: "Duration", value: R(s.duration_seconds) }),
      /* @__PURE__ */ e.jsx(x, { label: "Players", value: String(s.player_count) }),
      /* @__PURE__ */ e.jsx(x, { label: "Winner", value: a })
    ] })
  ] });
}
function vs({ players: s }) {
  const a = [...s].sort((c, u) => u.dpm - c.dpm).slice(0, 5), t = Math.max(...a.map((c) => c.kills), 1), l = Math.max(...a.map((c) => c.deaths), 1), i = Math.max(...a.map((c) => c.dpm), 1), o = Math.max(...a.map((c) => c.damage_given), 1), d = Math.max(...a.map((c) => c.gibs), 1), n = {
    labels: ["Kills", "Deaths(inv)", "DPM", "Damage", "Efficiency", "Gibs"],
    datasets: a.map((c, u) => ({
      label: c.name,
      data: [
        Math.round(c.kills / t * 100),
        Math.round((1 - c.deaths / l) * 100),
        Math.round(c.dpm / i * 100),
        Math.round(c.damage_given / o * 100),
        Math.round(c.efficiency),
        Math.round(c.gibs / d * 100)
      ],
      backgroundColor: f[u % f.length],
      borderColor: f[u % f.length],
      borderWidth: 2
    }))
  };
  return /* @__PURE__ */ e.jsxs(b, { className: "!cursor-default", children: [
    /* @__PURE__ */ e.jsx("div", { className: "text-sm font-bold text-white mb-4", children: "Combat Radar" }),
    /* @__PURE__ */ e.jsx(
      w,
      {
        type: "radar",
        data: n,
        height: 320,
        options: {
          plugins: { legend: { position: "bottom", labels: { color: "#94a3b8", font: { size: 10 } } } },
          scales: {
            r: {
              min: 0,
              max: 100,
              ticks: { display: !1 },
              angleLines: { color: "rgba(148,163,184,0.2)" },
              grid: { color: "rgba(148,163,184,0.2)" },
              pointLabels: { color: "#94a3b8", font: { size: 10 } }
            }
          }
        }
      }
    )
  ] });
}
function fs({ players: s }) {
  const a = [...s].sort((t, l) => l.kills - t.kills);
  return /* @__PURE__ */ e.jsxs(b, { className: "!cursor-default", children: [
    /* @__PURE__ */ e.jsx("div", { className: "text-sm font-bold text-white mb-4", children: "Top Fraggers" }),
    /* @__PURE__ */ e.jsx(
      w,
      {
        type: "bar",
        data: {
          labels: a.map((t) => t.name),
          datasets: [
            { label: "Kills", data: a.map((t) => t.kills), backgroundColor: "rgba(59, 130, 246, 0.7)" },
            { label: "Deaths", data: a.map((t) => t.deaths), backgroundColor: "rgba(244, 63, 94, 0.5)" }
          ]
        },
        height: Math.max(220, a.length * 34),
        options: {
          indexAxis: "y",
          plugins: { legend: { labels: { color: "#94a3b8", font: { size: 10 } } } },
          scales: {
            x: { ticks: { color: "#94a3b8" }, grid: { color: "rgba(148,163,184,0.1)" } },
            y: { ticks: { color: "#e2e8f0", font: { size: 11 } }, grid: { display: !1 } }
          }
        }
      }
    )
  ] });
}
function ys({ players: s }) {
  const a = [
    {
      key: "name",
      label: "Player",
      render: (t) => /* @__PURE__ */ e.jsx("button", { onClick: () => _(t.name), className: "text-blue-400 hover:text-blue-300 font-semibold text-left", children: t.name })
    },
    { key: "damage_given", label: "Dmg Given", sortable: !0, sortValue: (t) => t.damage_given, className: "font-mono text-white", render: (t) => S(t.damage_given) },
    { key: "damage_received", label: "Dmg Recv", sortable: !0, sortValue: (t) => t.damage_received, className: "font-mono text-slate-400", render: (t) => S(t.damage_received) },
    { key: "team_damage_given", label: "Team Dmg", sortable: !0, sortValue: (t) => t.team_damage_given, className: "font-mono text-amber-400", render: (t) => S(t.team_damage_given) },
    { key: "dpm", label: "DPM", sortable: !0, sortValue: (t) => t.dpm, className: "font-mono text-cyan-400", render: (t) => t.dpm.toFixed(1) }
  ];
  return /* @__PURE__ */ e.jsxs(b, { className: "!cursor-default", children: [
    /* @__PURE__ */ e.jsx("div", { className: "text-sm font-bold text-white mb-4", children: "Damage Breakdown" }),
    /* @__PURE__ */ e.jsx(Q, { columns: a, data: s, keyFn: (t) => t.guid, defaultSort: { key: "damage_given", dir: "desc" } })
  ] });
}
function Ns({ players: s }) {
  const a = [...s].sort((t, l) => l.revives_given - t.revives_given);
  return /* @__PURE__ */ e.jsxs(b, { className: "!cursor-default", children: [
    /* @__PURE__ */ e.jsx("div", { className: "text-sm font-bold text-white mb-4", children: "Support Performance" }),
    /* @__PURE__ */ e.jsx(
      w,
      {
        type: "bar",
        data: {
          labels: a.map((t) => t.name),
          datasets: [
            { label: "Revives", data: a.map((t) => t.revives_given), backgroundColor: "rgba(16, 185, 129, 0.7)" },
            { label: "Gibs", data: a.map((t) => t.gibs), backgroundColor: "rgba(168, 85, 247, 0.5)" },
            { label: "Self Kills", data: a.map((t) => t.self_kills), backgroundColor: "rgba(245, 158, 11, 0.5)" }
          ]
        },
        height: Math.max(220, a.length * 36),
        options: {
          indexAxis: "y",
          plugins: { legend: { labels: { color: "#94a3b8", font: { size: 10 } } } },
          scales: {
            x: { stacked: !0, ticks: { color: "#94a3b8" }, grid: { color: "rgba(148,163,184,0.1)" } },
            y: { stacked: !0, ticks: { color: "#e2e8f0", font: { size: 11 } }, grid: { display: !1 } }
          }
        }
      }
    )
  ] });
}
function _s({ players: s }) {
  const a = [...s].sort((t, l) => l.time_played_seconds - t.time_played_seconds);
  return /* @__PURE__ */ e.jsxs(b, { className: "!cursor-default", children: [
    /* @__PURE__ */ e.jsx("div", { className: "text-sm font-bold text-white mb-4", children: "Time Distribution" }),
    /* @__PURE__ */ e.jsx(
      w,
      {
        type: "bar",
        data: {
          labels: a.map((t) => t.name),
          datasets: [
            {
              label: "Alive (s)",
              data: a.map((t) => Math.max(0, t.time_played_seconds - t.time_dead_seconds)),
              backgroundColor: "rgba(34, 197, 94, 0.7)"
            },
            {
              label: "Dead (s)",
              data: a.map((t) => t.time_dead_seconds),
              backgroundColor: "rgba(100, 116, 139, 0.5)"
            }
          ]
        },
        height: Math.max(220, a.length * 34),
        options: {
          indexAxis: "y",
          plugins: { legend: { labels: { color: "#94a3b8", font: { size: 10 } } } },
          scales: {
            x: { stacked: !0, ticks: { color: "#94a3b8" }, grid: { color: "rgba(148,163,184,0.1)" } },
            y: { stacked: !0, ticks: { color: "#e2e8f0", font: { size: 11 } }, grid: { display: !1 } }
          }
        }
      }
    )
  ] });
}
function ks({ data: s }) {
  return /* @__PURE__ */ e.jsxs("div", { className: "space-y-6", children: [
    /* @__PURE__ */ e.jsxs("div", { className: "grid grid-cols-1 lg:grid-cols-2 gap-6", children: [
      /* @__PURE__ */ e.jsx(js, { data: s }),
      /* @__PURE__ */ e.jsx(vs, { players: s.players })
    ] }),
    /* @__PURE__ */ e.jsx(fs, { players: s.players }),
    /* @__PURE__ */ e.jsx(ys, { players: s.players }),
    /* @__PURE__ */ e.jsxs("div", { className: "grid grid-cols-1 lg:grid-cols-2 gap-6", children: [
      /* @__PURE__ */ e.jsx(Ns, { players: s.players }),
      /* @__PURE__ */ e.jsx(_s, { players: s.players })
    ] })
  ] });
}
function Zs({ params: s }) {
  const [a, t] = g.useState("summary"), [l, i] = g.useState(null), [o, d] = g.useState(null), [n, c] = g.useState(null), u = s?.sessionId ? Number(s.sessionId) : null, K = s?.sessionDate ?? null, { data: E, isLoading: le, isError: ne } = Ve(u), { data: ie, isLoading: re, isError: oe } = $e(u ? null : K), m = E ?? ie, de = u ? le : re, ce = u ? ne : oe, H = g.useMemo(() => m?.matches.flatMap((r) => r.rounds) ?? [], [m]), k = g.useMemo(() => H.find((r) => r.round_id === l) ?? null, [H, l]), j = g.useMemo(() => ls(m?.date ?? null, k), [m?.date, k]), { data: P, isLoading: me } = Fe(l), { data: U, isLoading: xe } = Ke(
    m?.date ?? null,
    m?.session_id ?? null,
    a === "charts" && !l && !!m?.date
  ), y = g.useMemo(() => k && P?.players?.length ? P.players.map((r) => ({
    guid: r.guid,
    name: r.name,
    kills: r.kills,
    deaths: r.deaths,
    dpm: r.dpm,
    damageGiven: r.damage_given,
    damageReceived: r.damage_received,
    selfKills: r.self_kills,
    deniedSeconds: r.denied_playtime,
    timeDeadSeconds: r.time_dead_seconds,
    alivePct: r.time_played_seconds > 0 ? (r.time_played_seconds - r.time_dead_seconds) / r.time_played_seconds * 100 : null,
    playedPct: null,
    revives: r.revives_given,
    assists: r.kill_assists,
    gibs: r.gibs,
    accuracy: null,
    source: "round",
    roundPlayer: r
  })) : (m?.players ?? []).map((r) => ({
    guid: r.player_guid,
    name: r.player_name,
    kills: r.kills,
    deaths: r.deaths,
    dpm: r.dpm,
    damageGiven: r.damage_given,
    damageReceived: r.damage_received,
    selfKills: r.self_kills,
    deniedSeconds: r.denied_playtime ?? r.time_denied_seconds ?? 0,
    timeDeadSeconds: Math.round((r.time_dead_minutes ?? 0) * 60),
    alivePct: r.alive_pct ?? r.alive_percent ?? null,
    playedPct: r.played_pct ?? r.played_percent ?? null,
    revives: r.revives_given,
    assists: r.kill_assists,
    gibs: r.gibs,
    accuracy: r.accuracy ?? null,
    source: "session",
    sessionPlayer: r
  })), [k, P, m]), v = g.useMemo(() => y.length ? y.some((r) => r.guid === n) ? n : y[0].guid : null, [y, n]), ue = g.useMemo(() => y.find((r) => r.guid === v) ?? null, [y, v]), { data: pe, isLoading: he } = Ee(
    l,
    l ? v : null,
    a === "players" && !!l && !!v
  ), { data: ge, isLoading: be } = Ge(
    "session",
    l ? null : v,
    1,
    50,
    a === "players" && !l && !!v,
    m?.session_id ?? void 0
  ), { data: V, isLoading: Z } = ze(
    v,
    l ? "round" : "session",
    l ? void 0 : m?.session_id ?? void 0,
    l ?? void 0,
    a === "players" && !!v
  ), { data: je, isLoading: ve } = Ae(j, a === "teamplay" && !!j), { data: fe, isLoading: ye } = Be(j, 250, a === "teamplay" && !!j), { data: Ne, isLoading: _e } = Ie(j, 8, a === "teamplay" && !!j), { data: ke, isLoading: Se } = We(j, a === "teamplay" && !!j), { data: we, isLoading: De } = Oe(j, 5, a === "teamplay" && !!j);
  if (de)
    return /* @__PURE__ */ e.jsxs("div", { className: "page-shell", children: [
      /* @__PURE__ */ e.jsx(A, { title: "Session Detail", subtitle: "Loading...", eyebrow: "Deep Session Detail" }),
      /* @__PURE__ */ e.jsx(N, { variant: "card", count: 4 })
    ] });
  if (ce || !m)
    return /* @__PURE__ */ e.jsxs("div", { className: "page-shell", children: [
      /* @__PURE__ */ e.jsx(A, { title: "Session Detail", subtitle: "Session not found", eyebrow: "Deep Session Detail" }),
      /* @__PURE__ */ e.jsxs("div", { className: "text-center py-12", children: [
        /* @__PURE__ */ e.jsx("div", { className: "text-red-400 text-lg mb-4", children: "Session not found" }),
        /* @__PURE__ */ e.jsx(
          "button",
          {
            onClick: () => q("#/sessions2"),
            className: "px-4 py-2 rounded-lg bg-blue-500/20 text-blue-400 font-bold text-sm hover:bg-blue-500/30 transition",
            children: "Back to Sessions"
          }
        )
      ] })
    ] });
  const Me = ve || ye || _e || Se || De, G = g.useMemo(() => !l || !m ? null : m.matches.findIndex(
    (r) => r.rounds.some((Te) => Te.round_id === l)
  ), [l, m]), z = G !== null && G >= 0 ? G : o, Pe = z !== null && m ? m.matches[z]?.map_name ?? null : null;
  function Ce(r) {
    d(r), i(null);
  }
  function Le(r) {
    i(r);
  }
  function Re() {
    i(null), d(null);
  }
  return /* @__PURE__ */ e.jsxs("div", { className: "page-shell", children: [
    /* @__PURE__ */ e.jsxs(
      A,
      {
        title: `Session ${m.session_id ?? ""}`,
        subtitle: m.date ? `${m.date} · ${m.round_count} rounds · ${m.player_count} players` : `${m.round_count} rounds`,
        eyebrow: "Deep Session Detail",
        children: [
          /* @__PURE__ */ e.jsx(
            "button",
            {
              onClick: () => t("players"),
              className: "flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-white/6 border border-white/10 text-slate-300 text-sm font-bold hover:text-white transition",
              children: "Player Stats"
            }
          ),
          /* @__PURE__ */ e.jsxs(
            "button",
            {
              onClick: () => q("#/sessions2"),
              className: "flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-slate-800 text-slate-300 text-sm font-bold hover:text-white transition",
              children: [
                /* @__PURE__ */ e.jsx(as, { className: "w-4 h-4" }),
                "Back"
              ]
            }
          )
        ]
      }
    ),
    /* @__PURE__ */ e.jsx(rs, { data: m, activeRound: k }),
    /* @__PURE__ */ e.jsx(is, { active: a, onChange: t }),
    /* @__PURE__ */ e.jsx(
      ns,
      {
        activeRound: k,
        expandedMap: Pe,
        onClear: Re
      }
    ),
    a === "summary" && /* @__PURE__ */ e.jsx(
      cs,
      {
        data: m,
        activeRoundId: l,
        expandedMapIndex: z,
        onSelectMap: Ce,
        onSelectRound: Le,
        onClearRound: () => i(null)
      }
    ),
    a === "players" && /* @__PURE__ */ e.jsxs(e.Fragment, { children: [
      /* @__PURE__ */ e.jsx(hs, { rows: y, selectedGuid: v, onSelectPlayer: c }),
      l ? /* @__PURE__ */ e.jsx(
        ps,
        {
          detail: pe,
          loading: he,
          vsPreys: V?.easiest_preys ?? [],
          vsEnemies: V?.worst_enemies ?? [],
          vsLoading: Z
        }
      ) : /* @__PURE__ */ e.jsx(
        us,
        {
          row: ue,
          weaponMastery: ge?.players?.[0] ?? null,
          loading: be,
          vsPreys: V?.easiest_preys ?? [],
          vsEnemies: V?.worst_enemies ?? [],
          vsLoading: Z
        }
      )
    ] }),
    a === "teamplay" && /* @__PURE__ */ e.jsx(
      gs,
      {
        loading: Me,
        summary: je,
        events: fe,
        duos: Ne,
        teamplay: ke,
        movers: we
      }
    ),
    a === "charts" && (me && l ? /* @__PURE__ */ e.jsx(N, { variant: "card", count: 4 }) : l ? P ? /* @__PURE__ */ e.jsx(ks, { data: P }) : /* @__PURE__ */ e.jsx(h, { message: "No round viz data is available for this scope." }) : xe ? /* @__PURE__ */ e.jsx(N, { variant: "card", count: 4 }) : U ? /* @__PURE__ */ e.jsx(bs, { data: U }) : /* @__PURE__ */ e.jsx(h, { message: "No session graph data is available for this session." }))
  ] });
}
export {
  Zs as default
};
