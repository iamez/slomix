import { jsxs as l, jsx as t, Fragment as P } from "react/jsx-runtime";
import { useState as R } from "react";
import { s as $, t as A } from "./hooks-UFUMZFGB.js";
import { D as g } from "./DataTable-C9DYv6yb.js";
import { G as E } from "./GlassCard-DKnnuJMt.js";
import { P as h } from "./PageHeader-D4CVo02x.js";
import { S as H, c as p } from "./route-host-CUL1oI6Z.js";
import { f as k } from "./format-BM7Gaq4w.js";
import { n as N, a as v } from "./navigation-BDd1HkpE.js";
import { m as w } from "./game-assets-CWuRxGFH.js";
import { c as K } from "./createLucideIcon-CP-mMPfa.js";
import { T as j } from "./trophy-DLp0OdqF.js";
import { S } from "./skull-BdPXKOvx.js";
import { H as F } from "./heart-Be63oR7h.js";
import { G as I } from "./gamepad-2-CX3iu8NC.js";
import { M as B } from "./map-CPL-Ld_L.js";
import { U as G } from "./users-CNuz17ri.js";
import { C as U } from "./clock-v5cg8EyG.js";
const z = [
  ["path", { d: "m12 19-7-7 7-7", key: "1l729n" }],
  ["path", { d: "M19 12H5", key: "x3x0zl" }]
], O = K("arrow-left", z);
function y(e) {
  const s = Number(e || 0);
  if (!s || s < 0) return "0:00";
  const n = Math.floor(s / 60), a = Math.floor(s % 60);
  return `${n}:${String(a).padStart(2, "0")}`;
}
function D(e) {
  return (e || "Unknown").replace(/^maps[\\/]/, "").replace(/\.(bsp|pk3|arena)$/i, "").replace(/_/g, " ");
}
function C(e) {
  return e === 1 ? "Axis" : e === 2 ? "Allies" : "Tied";
}
function M(e) {
  return e === 1 ? "text-rose-400" : e === 2 ? "text-blue-400" : "text-slate-400";
}
function W({ active: e, onChange: s }) {
  return /* @__PURE__ */ t("div", { className: "flex gap-1 bg-slate-800/80 rounded-lg p-0.5 mb-6", children: [
    { key: "overview", label: "Overview" },
    { key: "players", label: "Players" },
    { key: "rounds", label: "Rounds" }
  ].map((a) => /* @__PURE__ */ t(
    "button",
    {
      onClick: () => s(a.key),
      className: p(
        "px-4 py-2 rounded-md text-sm font-bold transition",
        e === a.key ? "bg-blue-500/20 text-blue-400" : "text-slate-400 hover:text-white"
      ),
      children: a.label
    },
    a.key
  )) });
}
function q({ data: e }) {
  const s = e.matches.reduce((o, i) => o + i.rounds.reduce((d, m) => d + (m.duration_seconds ?? 0), 0), 0), n = e.players.reduce((o, i) => o + i.kills, 0), a = e.matches.length;
  return /* @__PURE__ */ l("div", { className: "grid grid-cols-2 md:grid-cols-5 gap-3 mb-6", children: [
    /* @__PURE__ */ t(x, { icon: I, label: "Rounds", value: e.round_count, color: "text-brand-cyan" }),
    /* @__PURE__ */ t(x, { icon: B, label: "Maps", value: a, color: "text-brand-purple" }),
    /* @__PURE__ */ t(x, { icon: G, label: "Players", value: e.player_count, color: "text-brand-amber" }),
    /* @__PURE__ */ t(x, { icon: S, label: "Total Kills", value: k(n), color: "text-brand-rose" }),
    /* @__PURE__ */ t(x, { icon: U, label: "Duration", value: y(s), color: "text-slate-300" })
  ] });
}
function x({ icon: e, label: s, value: n, color: a }) {
  return /* @__PURE__ */ l("div", { className: "glass-card rounded-xl p-4 text-center", children: [
    /* @__PURE__ */ t(e, { className: p("w-5 h-5 mx-auto mb-2", a) }),
    /* @__PURE__ */ t("div", { className: p("text-xl font-black", a), children: n }),
    /* @__PURE__ */ t("div", { className: "text-[10px] text-slate-500 uppercase", children: s })
  ] });
}
function J({ matches: e, scoring: s }) {
  const n = s?.maps ?? [];
  return /* @__PURE__ */ t("div", { className: "flex flex-wrap gap-3 mb-6", children: e.map((a, o) => {
    const i = n[o], d = i?.team_a_points ?? i?.allies_score, m = i?.team_b_points ?? i?.axis_score, b = d != null && m != null;
    return /* @__PURE__ */ l(
      "div",
      {
        className: "glass-card rounded-xl overflow-hidden min-w-[180px] border border-white/10",
        children: [
          /* @__PURE__ */ l("div", { className: "relative h-16 bg-slate-800", children: [
            /* @__PURE__ */ t("img", { src: w(a.map_name), alt: "", className: "w-full h-full object-cover opacity-60", onError: (u) => {
              u.currentTarget.style.display = "none";
            } }),
            /* @__PURE__ */ t("div", { className: "absolute inset-0 bg-gradient-to-t from-slate-900 to-transparent" }),
            /* @__PURE__ */ t("div", { className: "absolute bottom-1.5 left-3 text-sm font-bold text-white drop-shadow-lg", children: D(a.map_name) })
          ] }),
          /* @__PURE__ */ l("div", { className: "p-4", children: [
            /* @__PURE__ */ l("div", { className: "text-[10px] text-slate-500 uppercase mb-1", children: [
              a.rounds.length,
              " rounds"
            ] }),
            b && /* @__PURE__ */ l("div", { className: "flex items-center gap-2 text-xs", children: [
              /* @__PURE__ */ t("span", { className: "text-blue-400 font-bold", children: d }),
              /* @__PURE__ */ t("span", { className: "text-slate-600", children: "—" }),
              /* @__PURE__ */ t("span", { className: "text-rose-400 font-bold", children: m })
            ] }),
            /* @__PURE__ */ t("div", { className: "mt-2 space-y-1", children: a.rounds.map((u) => /* @__PURE__ */ l("div", { className: "flex items-center justify-between text-[11px]", children: [
              /* @__PURE__ */ l("span", { className: "text-slate-400", children: [
                "R",
                u.round_number
              ] }),
              /* @__PURE__ */ t("span", { className: M(u.winner_team), children: C(u.winner_team) }),
              /* @__PURE__ */ t("span", { className: "text-slate-500 font-mono", children: y(u.duration_seconds) })
            ] }, u.round_id)) })
          ] })
        ]
      },
      `${a.map_name}-${o}`
    );
  }) });
}
function Q({ scoring: e }) {
  if (!e?.available || e.team_a_total == null) return null;
  const s = (e.team_a_total ?? 0) > (e.team_b_total ?? 0), n = e.team_a_total === e.team_b_total;
  return /* @__PURE__ */ l("div", { className: "glass-card rounded-xl p-5 mb-6 flex items-center justify-center gap-6", children: [
    /* @__PURE__ */ l("div", { className: "text-center", children: [
      /* @__PURE__ */ t("div", { className: "text-[10px] text-slate-500 uppercase mb-1", children: "Allies" }),
      /* @__PURE__ */ t("div", { className: p("text-3xl font-black", s && !n ? "text-blue-400" : "text-slate-300"), children: e.team_a_total })
    ] }),
    /* @__PURE__ */ t("div", { className: "text-slate-600 text-2xl font-bold", children: "vs" }),
    /* @__PURE__ */ l("div", { className: "text-center", children: [
      /* @__PURE__ */ t("div", { className: "text-[10px] text-slate-500 uppercase mb-1", children: "Axis" }),
      /* @__PURE__ */ t("div", { className: p("text-3xl font-black", !s && !n ? "text-rose-400" : "text-slate-300"), children: e.team_b_total })
    ] })
  ] });
}
const X = [
  {
    key: "player_name",
    label: "Player",
    render: (e) => /* @__PURE__ */ t(
      "button",
      {
        onClick: () => v(e.player_name),
        className: "text-blue-400 hover:text-blue-300 font-semibold text-left",
        children: e.player_name
      }
    )
  },
  { key: "kills", label: "Kills", sortable: !0, sortValue: (e) => e.kills, className: "font-mono text-white" },
  { key: "deaths", label: "Deaths", sortable: !0, sortValue: (e) => e.deaths, className: "font-mono text-slate-400" },
  { key: "kd", label: "K/D", sortable: !0, sortValue: (e) => e.kd, className: "font-mono text-emerald-400", render: (e) => e.kd.toFixed(2) },
  { key: "dpm", label: "DPM", sortable: !0, sortValue: (e) => e.dpm, className: "font-mono text-cyan-400", render: (e) => e.dpm.toFixed(1) },
  { key: "damage_given", label: "Damage", sortable: !0, sortValue: (e) => e.damage_given, className: "font-mono text-white", render: (e) => k(e.damage_given) },
  { key: "headshot_kills", label: "HS", sortable: !0, sortValue: (e) => e.headshot_kills, className: "font-mono text-amber-400" },
  { key: "revives_given", label: "Revives", sortable: !0, sortValue: (e) => e.revives_given, className: "font-mono text-green-400" },
  { key: "gibs", label: "Gibs", sortable: !0, sortValue: (e) => e.gibs, className: "font-mono text-purple-400" },
  { key: "kill_assists", label: "Assists", sortable: !0, sortValue: (e) => e.kill_assists, className: "font-mono text-slate-400" }
];
function _({ players: e }) {
  return /* @__PURE__ */ t("div", { className: "glass-panel rounded-xl p-0 overflow-hidden", children: /* @__PURE__ */ t(
    g,
    {
      columns: X,
      data: e,
      keyFn: (s) => s.player_guid,
      defaultSort: { key: "dpm", dir: "desc" },
      stickyHeader: !0,
      onRowClick: (s) => v(s.player_name)
    }
  ) });
}
function Y({ matches: e }) {
  const s = e.flatMap(
    (a) => a.rounds.map((o) => ({ ...o, match_map: a.map_name }))
  );
  return /* @__PURE__ */ t("div", { className: "glass-panel rounded-xl p-0 overflow-hidden", children: /* @__PURE__ */ t(
    g,
    {
      columns: [
        { key: "round_id", label: "ID", className: "text-slate-500 font-mono text-xs" },
        { key: "match_map", label: "Map", render: (a) => /* @__PURE__ */ l("span", { className: "text-white font-semibold inline-flex items-center gap-2", children: [
          /* @__PURE__ */ t("img", { src: w(a.match_map), alt: "", className: "w-5 h-5 rounded-sm object-cover bg-slate-700", onError: (o) => {
            o.currentTarget.style.display = "none";
          } }),
          D(a.match_map)
        ] }) },
        { key: "round_number", label: "Round", render: (a) => /* @__PURE__ */ l("span", { className: "text-slate-300", children: [
          "R",
          a.round_number
        ] }) },
        {
          key: "winner_team",
          label: "Winner",
          render: (a) => /* @__PURE__ */ t("span", { className: M(a.winner_team), children: C(a.winner_team) })
        },
        {
          key: "score",
          label: "Score",
          render: (a) => a.allies_score != null ? /* @__PURE__ */ l("span", { children: [
            /* @__PURE__ */ t("span", { className: "text-blue-400", children: a.allies_score }),
            /* @__PURE__ */ t("span", { className: "text-slate-600", children: " — " }),
            /* @__PURE__ */ t("span", { className: "text-rose-400", children: a.axis_score })
          ] }) : /* @__PURE__ */ t("span", { className: "text-slate-600", children: "—" })
        },
        {
          key: "duration_seconds",
          label: "Duration",
          sortable: !0,
          sortValue: (a) => a.duration_seconds ?? 0,
          className: "font-mono text-slate-300",
          render: (a) => y(a.duration_seconds)
        },
        { key: "round_date", label: "Date", className: "text-slate-500 text-xs" },
        { key: "round_time", label: "Time", className: "text-slate-500 text-xs" }
      ],
      data: s,
      keyFn: (a) => String(a.round_id),
      stickyHeader: !0
    }
  ) });
}
function fe({ params: e }) {
  const [s, n] = R("overview"), a = e?.sessionId ? Number(e.sessionId) : null, o = e?.sessionDate ?? null, { data: i, isLoading: d, isError: m } = $(a), { data: b, isLoading: u, isError: T } = A(
    a ? null : o
  ), r = i ?? b, V = a ? d : u, L = a ? m : T;
  return V ? /* @__PURE__ */ l("div", { className: "mt-6", children: [
    /* @__PURE__ */ t(h, { title: "Session Detail", subtitle: "Loading..." }),
    /* @__PURE__ */ t(H, { variant: "card", count: 4 })
  ] }) : L || !r ? /* @__PURE__ */ l("div", { className: "mt-6", children: [
    /* @__PURE__ */ t(h, { title: "Session Detail", subtitle: "Session not found" }),
    /* @__PURE__ */ l("div", { className: "text-center py-12", children: [
      /* @__PURE__ */ t("div", { className: "text-red-400 text-lg mb-4", children: "Session not found" }),
      /* @__PURE__ */ t(
        "button",
        {
          onClick: () => N("#/sessions2"),
          className: "px-4 py-2 rounded-lg bg-blue-500/20 text-blue-400 font-bold text-sm hover:bg-blue-500/30 transition",
          children: "Back to Sessions"
        }
      )
    ] })
  ] }) : /* @__PURE__ */ l("div", { className: "mt-6", children: [
    /* @__PURE__ */ t(
      h,
      {
        title: `Session ${r.session_id ?? ""}`,
        subtitle: r.date ? `${r.date} · ${r.round_count} rounds · ${r.player_count} players` : `${r.round_count} rounds`,
        children: /* @__PURE__ */ l(
          "button",
          {
            onClick: () => N("#/sessions2"),
            className: "flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-slate-800 text-slate-300 text-sm font-bold hover:text-white transition",
            children: [
              /* @__PURE__ */ t(O, { className: "w-4 h-4" }),
              "Back"
            ]
          }
        )
      }
    ),
    /* @__PURE__ */ t(q, { data: r }),
    /* @__PURE__ */ t(W, { active: s, onChange: n }),
    s === "overview" && /* @__PURE__ */ l(P, { children: [
      /* @__PURE__ */ t(Q, { scoring: r.scoring }),
      /* @__PURE__ */ t(J, { matches: r.matches, scoring: r.scoring }),
      /* @__PURE__ */ l("div", { className: "grid grid-cols-1 md:grid-cols-3 gap-4 mb-6", children: [
        /* @__PURE__ */ t(
          f,
          {
            label: "MVP (DPM)",
            color: "text-yellow-500",
            icon: j,
            players: r.players,
            getValue: (c) => c.dpm,
            formatValue: (c) => c.toFixed(1)
          }
        ),
        /* @__PURE__ */ t(
          f,
          {
            label: "Most Kills",
            color: "text-rose-400",
            icon: S,
            players: r.players,
            getValue: (c) => c.kills,
            formatValue: (c) => String(c)
          }
        ),
        /* @__PURE__ */ t(
          f,
          {
            label: "Most Revives",
            color: "text-emerald-400",
            icon: F,
            players: r.players,
            getValue: (c) => c.revives_given,
            formatValue: (c) => String(c)
          }
        )
      ] }),
      /* @__PURE__ */ t("h3", { className: "text-sm font-bold text-slate-500 uppercase tracking-wider mb-3", children: "All Players" }),
      /* @__PURE__ */ t(_, { players: r.players })
    ] }),
    s === "players" && /* @__PURE__ */ t(_, { players: r.players }),
    s === "rounds" && /* @__PURE__ */ t(Y, { matches: r.matches })
  ] });
}
function f({ label: e, color: s, icon: n, players: a, getValue: o, formatValue: i }) {
  if (a.length === 0) return null;
  const d = a.reduce((m, b) => o(b) > o(m) ? b : m, a[0]);
  return /* @__PURE__ */ t(E, { onClick: () => v(d.player_name), children: /* @__PURE__ */ l("div", { className: "flex items-center gap-3", children: [
    /* @__PURE__ */ t(n, { className: p("w-6 h-6", s) }),
    /* @__PURE__ */ l("div", { children: [
      /* @__PURE__ */ t("div", { className: "text-[10px] text-slate-500 uppercase", children: e }),
      /* @__PURE__ */ t("div", { className: "text-lg font-black text-white", children: d.player_name }),
      /* @__PURE__ */ t("div", { className: p("text-sm font-bold", s), children: i(o(d)) })
    ] })
  ] }) });
}
export {
  fe as default
};
