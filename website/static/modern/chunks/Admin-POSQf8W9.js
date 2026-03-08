import { jsxs as a, Fragment as g, jsx as e } from "react/jsx-runtime";
import { useState as h, useCallback as k, useMemo as P } from "react";
import { u as w } from "./useQuery-C94yztTO.js";
import { P as N } from "./PageHeader-D4CVo02x.js";
import { G as S } from "./GlassPanel-S_ADyiYR.js";
import { G as m } from "./GlassCard-DKnnuJMt.js";
import { S as C } from "./route-host-CUL1oI6Z.js";
import { v as L, a as D } from "./hooks-UFUMZFGB.js";
const y = "/api", _ = {
  core_game_server: { title: "puran.hehe.si (Game Server)", eli5: "The live game server where matches are played.", group: "infrastructure" },
  core_postgres: { title: "PostgreSQL (Central DB)", eli5: "The vault that stores every stat safely.", group: "infrastructure" },
  core_bot_web: { title: "Bot + Website Host", eli5: "Runs the Discord bot, API backend, and website.", group: "infrastructure" },
  et_server: { title: "ET:Legacy Runtime", eli5: "The game itself running on the server.", group: "game-server" },
  lua_modules: { title: "Lua Modules", eli5: "Scripts that watch the game and write stats files.", group: "game-server" },
  lua_c0rnp0rn7: { title: "c0rnp0rn7.lua", eli5: "Writes the main stats file after each round.", group: "lua", files: "c0rnp0rn7.lua" },
  lua_endstats: { title: "endstats.lua", eli5: "Writes the awards file when a round ends.", group: "lua", files: "endstats.lua" },
  lua_webhook: { title: "stats_discord_webhook.lua", eli5: "Sends a quick ping when rounds start/end.", group: "lua", files: "vps_scripts/stats_discord_webhook.lua" },
  lua_proximity: { title: "proximity_tracker.lua", eli5: "Logs how close players are.", group: "lua", files: "proximity/lua/proximity_tracker.lua" },
  stats_parser: { title: "Stats Parser", eli5: "Turns raw text into clean numbers.", group: "pipeline", files: "bot/community_stats_parser.py" },
  differential_calc: { title: "R1/R2 Differential", eli5: "Computes Round 2 by subtracting Round 1.", group: "pipeline", files: "bot/community_stats_parser.py" },
  validation_caps: { title: "Validation & Caps", eli5: "Stops impossible numbers from sneaking in.", group: "pipeline", files: "postgresql_database_manager.py" },
  ssh_monitor: { title: "SSH Monitor", eli5: "Downloads new stats files from the game server.", group: "pipeline", files: "bot/services/automation/ssh_monitor.py" },
  file_tracker: { title: "File Tracker", eli5: "Keeps track of which files are new.", group: "pipeline", files: "bot/automation/file_tracker.py" },
  webhook_receiver: { title: "Webhook Receiver", eli5: "Catches Lua timing pings.", group: "pipeline", files: "bot/ultimate_bot.py" },
  session_aggregator: { title: "Session Aggregator", eli5: "Groups rounds into gaming sessions.", group: "pipeline", files: "bot/services/" },
  discord_bot: { title: "Discord Bot", eli5: "Posts stats and handles commands.", group: "output", files: "bot/ultimate_bot.py" },
  website_api: { title: "Website API", eli5: "Serves stats to the website.", group: "output", files: "website/backend/main.py" },
  proximity_parser: { title: "Proximity Parser", eli5: "Parses proximity engagement logs.", group: "pipeline", files: "proximity/parser/parser.py" },
  endstats_parser: { title: "Endstats Parser", eli5: "Turns awards files into award rows.", group: "pipeline", files: "bot/endstats_parser.py" }
}, b = {
  infrastructure: { label: "Infrastructure", color: "text-purple-400" },
  "game-server": { label: "Game Server", color: "text-cyan-400" },
  lua: { label: "Lua Modules", color: "text-amber-400" },
  pipeline: { label: "Data Pipeline", color: "text-emerald-400" },
  output: { label: "Output", color: "text-blue-400" }
}, R = [
  { from: "ET:Legacy Runtime", to: "Lua Modules", label: "Game events" },
  { from: "c0rnp0rn7.lua", to: "gamestats/*.txt", label: "Stats files" },
  { from: "endstats.lua", to: "endstats/*.txt", label: "Award files" },
  { from: "Lua Webhook", to: "Webhook Receiver", label: "HTTP POST" },
  { from: "SSH Monitor", to: "File Tracker", label: "Sync files" },
  { from: "File Tracker", to: "Stats Parser", label: "Parse queue" },
  { from: "Stats Parser", to: "R1/R2 Differential", label: "R2 split" },
  { from: "R1/R2 Differential", to: "Validation & Caps", label: "Validate" },
  { from: "Validation & Caps", to: "PostgreSQL", label: "Write rows" },
  { from: "PostgreSQL", to: "Session Aggregator", label: "Session totals" },
  { from: "Session Aggregator", to: "Discord Bot", label: "Post embeds" },
  { from: "PostgreSQL", to: "Website API", label: "Query data" }
];
function f(t) {
  return t === "connected" || t === "ok" || t === "online" || t === "green" ? "green" : t === "error" || t === "not_found" || t === "red" ? "red" : t === "warning" || t === "degraded" || t === "amber" ? "amber" : "blue";
}
function c({ color: t }) {
  const r = {
    green: "bg-emerald-500 shadow-emerald-500/50",
    red: "bg-rose-500 shadow-rose-500/50",
    amber: "bg-amber-500 shadow-amber-500/50",
    blue: "bg-blue-500 shadow-blue-500/50"
  }[t];
  return /* @__PURE__ */ e("span", { className: `inline-block w-2.5 h-2.5 rounded-full shadow-[0_0_6px] ${r}` });
}
function p(t) {
  if (t == null || !Number.isFinite(t)) return "--";
  const r = t < 0 ? "-" : "";
  let s = Math.floor(Math.abs(t));
  const l = Math.floor(s / 3600);
  s -= l * 3600;
  const n = Math.floor(s / 60);
  return s = s % 60, l > 0 ? `${r}${l}:${String(n).padStart(2, "0")}:${String(s).padStart(2, "0")}` : `${r}${n}:${String(s).padStart(2, "0")}`;
}
function v(t) {
  return t == null ? "--" : t.toLocaleString();
}
function T({ diag: t, apiStatus: r }) {
  const { data: s } = D(), l = f(t?.database?.status ?? "unknown"), n = f(r?.status ?? "unknown"), u = s?.game_server?.online ? "green" : "red", d = t?.issues?.length ? "red" : t?.warnings?.length ? "amber" : "green";
  return /* @__PURE__ */ a(S, { children: [
    /* @__PURE__ */ a("div", { className: "flex items-center justify-between mb-4", children: [
      /* @__PURE__ */ e("div", { className: "text-xs font-bold uppercase tracking-widest text-slate-400", children: "System Health" }),
      /* @__PURE__ */ a("div", { className: "flex items-center gap-2", children: [
        /* @__PURE__ */ e(c, { color: d }),
        /* @__PURE__ */ e("span", { className: "text-xs text-slate-300", children: t?.status?.toUpperCase() ?? "CHECKING" })
      ] })
    ] }),
    /* @__PURE__ */ a("div", { className: "grid grid-cols-2 md:grid-cols-4 gap-3", children: [
      /* @__PURE__ */ a("div", { className: "rounded-xl border border-white/10 bg-slate-950/40 p-3", children: [
        /* @__PURE__ */ a("div", { className: "flex items-center gap-2 mb-1", children: [
          /* @__PURE__ */ e(c, { color: l }),
          /* @__PURE__ */ e("span", { className: "text-xs font-bold text-white", children: "Database" })
        ] }),
        /* @__PURE__ */ e("div", { className: "text-[11px] text-slate-400", children: t?.database?.status ?? "unknown" })
      ] }),
      /* @__PURE__ */ a("div", { className: "rounded-xl border border-white/10 bg-slate-950/40 p-3", children: [
        /* @__PURE__ */ a("div", { className: "flex items-center gap-2 mb-1", children: [
          /* @__PURE__ */ e(c, { color: n }),
          /* @__PURE__ */ e("span", { className: "text-xs font-bold text-white", children: "API" })
        ] }),
        /* @__PURE__ */ e("div", { className: "text-[11px] text-slate-400", children: r?.status ?? "unknown" })
      ] }),
      /* @__PURE__ */ a("div", { className: "rounded-xl border border-white/10 bg-slate-950/40 p-3", children: [
        /* @__PURE__ */ a("div", { className: "flex items-center gap-2 mb-1", children: [
          /* @__PURE__ */ e(c, { color: u }),
          /* @__PURE__ */ e("span", { className: "text-xs font-bold text-white", children: "Game Server" })
        ] }),
        /* @__PURE__ */ e("div", { className: "text-[11px] text-slate-400", children: s?.game_server?.online ? `${s.game_server.player_count}/${s.game_server.max_players} players` : "offline" })
      ] }),
      /* @__PURE__ */ a("div", { className: "rounded-xl border border-white/10 bg-slate-950/40 p-3", children: [
        /* @__PURE__ */ a("div", { className: "flex items-center gap-2 mb-1", children: [
          /* @__PURE__ */ e(c, { color: s?.voice_channel?.count ? "green" : "blue" }),
          /* @__PURE__ */ e("span", { className: "text-xs font-bold text-white", children: "Voice" })
        ] }),
        /* @__PURE__ */ a("div", { className: "text-[11px] text-slate-400", children: [
          s?.voice_channel?.count ?? 0,
          " in voice"
        ] })
      ] })
    ] })
  ] });
}
function $({ tables: t }) {
  return t.length ? /* @__PURE__ */ a(m, { children: [
    /* @__PURE__ */ e("div", { className: "text-xs font-bold uppercase tracking-widest text-slate-400 mb-3", children: "Database Tables" }),
    /* @__PURE__ */ e("div", { className: "space-y-1.5", children: t.map((r) => /* @__PURE__ */ a("div", { className: "flex items-center justify-between rounded-lg border border-white/10 bg-slate-950/30 px-3 py-2", children: [
      /* @__PURE__ */ a("div", { className: "flex items-center gap-2", children: [
        /* @__PURE__ */ e(c, { color: f(r.status) }),
        /* @__PURE__ */ e("span", { className: "text-xs text-white font-mono", children: r.name }),
        r.required && /* @__PURE__ */ e("span", { className: "text-[9px] text-amber-400 font-bold", children: "REQ" })
      ] }),
      /* @__PURE__ */ e("div", { className: "text-[11px] text-slate-400", children: r.status === "ok" ? `${v(r.row_count)} rows` : r.status })
    ] }, r.name)) })
  ] }) : null;
}
function A({ issues: t, warnings: r }) {
  return !t.length && !r.length ? /* @__PURE__ */ e(m, { children: /* @__PURE__ */ a("div", { className: "flex items-center gap-2", children: [
    /* @__PURE__ */ e(c, { color: "green" }),
    /* @__PURE__ */ e("span", { className: "text-xs text-slate-300", children: "Diagnostics clean. No critical warnings detected." })
  ] }) }) : /* @__PURE__ */ a(m, { children: [
    /* @__PURE__ */ e("div", { className: "text-xs font-bold uppercase tracking-widest text-slate-400 mb-3", children: "Alerts" }),
    /* @__PURE__ */ a("div", { className: "space-y-2", children: [
      t.map((s, l) => /* @__PURE__ */ a("div", { className: "flex items-start gap-2", children: [
        /* @__PURE__ */ e(c, { color: "red" }),
        /* @__PURE__ */ e("span", { className: "text-xs text-rose-400", children: s })
      ] }, `i${l}`)),
      r.map((s, l) => /* @__PURE__ */ a("div", { className: "flex items-start gap-2", children: [
        /* @__PURE__ */ e(c, { color: "blue" }),
        /* @__PURE__ */ e("span", { className: "text-xs text-blue-400", children: s })
      ] }, `w${l}`))
    ] })
  ] });
}
function M({ time: t }) {
  return /* @__PURE__ */ a(m, { children: [
    /* @__PURE__ */ e("div", { className: "text-xs font-bold uppercase tracking-widest text-slate-400 mb-3", children: "Timing Metrics" }),
    /* @__PURE__ */ e("div", { className: "grid grid-cols-2 md:grid-cols-5 gap-3", children: [
      { label: "Raw Dead", value: p(t.raw_dead_seconds) },
      { label: "Capped Dead", value: p(t.agg_dead_seconds) },
      { label: "Raw Denied", value: p(t.raw_denied_seconds) },
      { label: "Cap Hits", value: v(t.cap_hits) },
      { label: "Cap Seconds", value: p(t.cap_seconds) }
    ].map(({ label: r, value: s }) => /* @__PURE__ */ a("div", { className: "text-center", children: [
      /* @__PURE__ */ e("div", { className: "text-[10px] text-slate-500 uppercase", children: r }),
      /* @__PURE__ */ e("div", { className: "text-sm font-bold text-white font-mono", children: s })
    ] }, r)) })
  ] });
}
function G({ monitoring: t }) {
  const r = Object.entries(t);
  return r.length ? /* @__PURE__ */ a(m, { children: [
    /* @__PURE__ */ e("div", { className: "text-xs font-bold uppercase tracking-widest text-slate-400 mb-3", children: "Monitoring History" }),
    /* @__PURE__ */ e("div", { className: "grid grid-cols-1 md:grid-cols-2 gap-3", children: r.map(([s, l]) => /* @__PURE__ */ a("div", { className: "rounded-lg border border-white/10 bg-slate-950/30 p-3", children: [
      /* @__PURE__ */ a("div", { className: "flex items-center gap-2 mb-1", children: [
        /* @__PURE__ */ e(c, { color: l.error ? "amber" : l.count > 0 ? "green" : "blue" }),
        /* @__PURE__ */ e("span", { className: "text-xs font-bold text-white capitalize", children: s })
      ] }),
      /* @__PURE__ */ a("div", { className: "text-[11px] text-slate-400", children: [
        v(l.count),
        " records",
        l.last_recorded_at && /* @__PURE__ */ a(g, { children: [
          " · Last: ",
          new Date(l.last_recorded_at).toLocaleString()
        ] })
      ] })
    ] }, s)) })
  ] }) : null;
}
function j() {
  return /* @__PURE__ */ a(m, { children: [
    /* @__PURE__ */ e("div", { className: "text-xs font-bold uppercase tracking-widest text-slate-400 mb-3", children: "Data Flow Pipeline" }),
    /* @__PURE__ */ e("div", { className: "space-y-1", children: R.map((t, r) => /* @__PURE__ */ a("div", { className: "flex items-center gap-2 text-xs", children: [
      /* @__PURE__ */ e("span", { className: "text-cyan-400 font-mono min-w-[140px] text-right", children: t.from }),
      /* @__PURE__ */ e("span", { className: "text-slate-600", children: "→" }),
      /* @__PURE__ */ e("span", { className: "text-emerald-400 font-mono min-w-[140px]", children: t.to }),
      /* @__PURE__ */ e("span", { className: "text-slate-500 text-[11px]", children: t.label })
    ] }, r)) })
  ] });
}
function W() {
  const [t, r] = h(""), [s, l] = h(null), [n, u] = h(null), d = P(() => {
    const i = t.toLowerCase();
    return Object.entries(_).filter(([o, x]) => !(s && x.group !== s || i && !x.title.toLowerCase().includes(i) && !x.eli5.toLowerCase().includes(i)));
  }, [t, s]);
  return /* @__PURE__ */ a(S, { children: [
    /* @__PURE__ */ a("div", { className: "text-xs font-bold uppercase tracking-widest text-slate-400 mb-3", children: [
      "System Components (",
      Object.keys(_).length,
      ")"
    ] }),
    /* @__PURE__ */ a("div", { className: "flex flex-wrap gap-2 mb-3", children: [
      /* @__PURE__ */ e(
        "button",
        {
          onClick: () => l(null),
          className: `px-2.5 py-1 rounded-lg text-[11px] font-bold border transition ${s ? "border-white/15 text-slate-400 hover:text-white" : "border-cyan-500/50 text-cyan-400 bg-cyan-500/10"}`,
          children: "All"
        }
      ),
      Object.entries(b).map(([i, o]) => /* @__PURE__ */ e(
        "button",
        {
          onClick: () => l(s === i ? null : i),
          className: `px-2.5 py-1 rounded-lg text-[11px] font-bold border transition ${s === i ? "border-cyan-500/50 text-cyan-400 bg-cyan-500/10" : "border-white/15 text-slate-400 hover:text-white"}`,
          children: o.label
        },
        i
      ))
    ] }),
    /* @__PURE__ */ e(
      "input",
      {
        value: t,
        onChange: (i) => r(i.target.value),
        placeholder: "Search components...",
        className: "w-full rounded-lg border border-white/10 bg-slate-950/50 px-3 py-2 text-xs text-white placeholder-slate-500 outline-none focus:border-cyan-500/50 mb-3"
      }
    ),
    /* @__PURE__ */ a("div", { className: "space-y-1.5 max-h-[500px] overflow-y-auto", children: [
      d.map(([i, o]) => /* @__PURE__ */ a(
        "button",
        {
          onClick: () => u(n === i ? null : i),
          className: "w-full text-left rounded-lg border border-white/10 bg-slate-950/30 px-3 py-2 hover:border-cyan-500/30 transition",
          children: [
            /* @__PURE__ */ a("div", { className: "flex items-center justify-between", children: [
              /* @__PURE__ */ a("div", { className: "flex items-center gap-2", children: [
                /* @__PURE__ */ e("span", { className: `text-[10px] font-bold ${b[o.group]?.color ?? "text-slate-500"}`, children: b[o.group]?.label ?? o.group }),
                /* @__PURE__ */ e("span", { className: "text-xs font-semibold text-white", children: o.title })
              ] }),
              /* @__PURE__ */ e("span", { className: "text-[11px] text-slate-500", children: n === i ? "▲" : "▼" })
            ] }),
            n === i && /* @__PURE__ */ a("div", { className: "mt-2 space-y-1 text-[11px]", children: [
              /* @__PURE__ */ e("div", { className: "text-slate-300", children: o.eli5 }),
              o.files && /* @__PURE__ */ e("div", { className: "text-slate-500 font-mono", children: o.files })
            ] })
          ]
        },
        i
      )),
      d.length === 0 && /* @__PURE__ */ e("div", { className: "text-xs text-slate-500 text-center py-4", children: "No matching components." })
    ] })
  ] });
}
function B() {
  const { data: t } = L(), [r, s] = h(0), { data: l, isLoading: n } = w({
    queryKey: ["diagnostics", r],
    queryFn: () => fetch(`${y}/diagnostics`).then((i) => i.json()),
    staleTime: 1e4,
    refetchInterval: 15e3
  }), { data: u } = w({
    queryKey: ["api-status", r],
    queryFn: () => fetch(`${y}/status`).then((i) => i.json()),
    staleTime: 1e4,
    refetchInterval: 15e3
  }), d = k(() => s((i) => i + 1), []);
  return t ? n ? /* @__PURE__ */ e(C, { variant: "card", count: 4 }) : /* @__PURE__ */ a(g, { children: [
    /* @__PURE__ */ e(N, { title: "Admin Panel", subtitle: "System diagnostics and operational overview" }),
    /* @__PURE__ */ a("div", { className: "flex items-center justify-between mb-4", children: [
      /* @__PURE__ */ a("div", { className: "text-[11px] text-slate-500", children: [
        "Last refresh: ",
        l?.timestamp ? new Date(l.timestamp).toLocaleTimeString() : "--"
      ] }),
      /* @__PURE__ */ e(
        "button",
        {
          onClick: d,
          className: "px-3 py-1.5 rounded-lg text-xs font-bold border border-white/10 text-slate-300 hover:border-cyan-500/40 hover:text-white transition",
          children: "Refresh Now"
        }
      )
    ] }),
    /* @__PURE__ */ e(T, { diag: l, apiStatus: u }),
    /* @__PURE__ */ e("div", { className: "mt-4", children: /* @__PURE__ */ e(A, { issues: l?.issues ?? [], warnings: l?.warnings ?? [] }) }),
    /* @__PURE__ */ a("div", { className: "grid grid-cols-1 lg:grid-cols-2 gap-4 mt-4", children: [
      /* @__PURE__ */ e(M, { time: l?.time ?? {} }),
      /* @__PURE__ */ e(G, { monitoring: l?.monitoring ?? {} })
    ] }),
    /* @__PURE__ */ a("div", { className: "grid grid-cols-1 lg:grid-cols-2 gap-4 mt-4", children: [
      /* @__PURE__ */ e($, { tables: l?.tables ?? [] }),
      /* @__PURE__ */ e(j, {})
    ] }),
    /* @__PURE__ */ e("div", { className: "mt-4", children: /* @__PURE__ */ e(W, {}) })
  ] }) : /* @__PURE__ */ a(g, { children: [
    /* @__PURE__ */ e(N, { title: "Admin Panel", subtitle: "System diagnostics and architecture" }),
    /* @__PURE__ */ a("div", { className: "text-center py-16", children: [
      /* @__PURE__ */ e("div", { className: "text-4xl mb-4", children: "🔒" }),
      /* @__PURE__ */ e("p", { className: "text-slate-400 text-lg mb-4", children: "Admin access requires authentication." }),
      /* @__PURE__ */ e("a", { href: "/auth/discord", className: "inline-block px-6 py-2 rounded-xl bg-indigo-600 text-white font-bold text-sm hover:bg-indigo-500 transition", children: "Login with Discord" })
    ] })
  ] });
}
export {
  B as default
};
