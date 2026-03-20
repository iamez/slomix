import { r as d, j as e, S as y } from "./route-host-Ba3v8uFM.js";
import { u as f } from "./useQuery-CHhIv7cp.js";
import { P as j } from "./PageHeader-CQ7BTOQj.js";
import { G as N } from "./GlassPanel-C-uUmQaB.js";
import { G as x } from "./GlassCard-C53TzD-y.js";
import { G as _, c as S } from "./hooks-CyQgvbI9.js";
const v = "/api", w = {
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
}, h = {
  infrastructure: { label: "Infrastructure", color: "text-purple-400" },
  "game-server": { label: "Game Server", color: "text-cyan-400" },
  lua: { label: "Lua Modules", color: "text-amber-400" },
  pipeline: { label: "Data Pipeline", color: "text-emerald-400" },
  output: { label: "Output", color: "text-blue-400" }
}, k = [
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
function b(t) {
  return t === "connected" || t === "ok" || t === "online" || t === "green" ? "green" : t === "error" || t === "not_found" || t === "red" ? "red" : t === "warning" || t === "degraded" || t === "amber" ? "amber" : "blue";
}
function o({ color: t }) {
  const a = {
    green: "bg-emerald-500 shadow-emerald-500/50",
    red: "bg-rose-500 shadow-rose-500/50",
    amber: "bg-amber-500 shadow-amber-500/50",
    blue: "bg-blue-500 shadow-blue-500/50"
  }[t];
  return /* @__PURE__ */ e.jsx("span", { className: `inline-block w-2.5 h-2.5 rounded-full shadow-[0_0_6px] ${a}` });
}
function u(t) {
  if (t == null || !Number.isFinite(t)) return "--";
  const a = t < 0 ? "-" : "";
  let s = Math.floor(Math.abs(t));
  const r = Math.floor(s / 3600);
  s -= r * 3600;
  const i = Math.floor(s / 60);
  return s = s % 60, r > 0 ? `${a}${r}:${String(i).padStart(2, "0")}:${String(s).padStart(2, "0")}` : `${a}${i}:${String(s).padStart(2, "0")}`;
}
function g(t) {
  return t == null ? "--" : t.toLocaleString();
}
function P({ diag: t, apiStatus: a }) {
  const { data: s } = S(), r = b(t?.database?.status ?? "unknown"), i = b(a?.status ?? "unknown"), m = s?.game_server?.online ? "green" : "red", c = t?.issues?.length ? "red" : t?.warnings?.length ? "amber" : "green";
  return /* @__PURE__ */ e.jsxs(N, { children: [
    /* @__PURE__ */ e.jsxs("div", { className: "flex items-center justify-between mb-4", children: [
      /* @__PURE__ */ e.jsx("div", { className: "text-xs font-bold uppercase tracking-widest text-slate-400", children: "System Health" }),
      /* @__PURE__ */ e.jsxs("div", { className: "flex items-center gap-2", children: [
        /* @__PURE__ */ e.jsx(o, { color: c }),
        /* @__PURE__ */ e.jsx("span", { className: "text-xs text-slate-300", children: t?.status?.toUpperCase() ?? "CHECKING" })
      ] })
    ] }),
    /* @__PURE__ */ e.jsxs("div", { className: "grid grid-cols-2 md:grid-cols-4 gap-3", children: [
      /* @__PURE__ */ e.jsxs("div", { className: "rounded-xl border border-white/10 bg-slate-950/40 p-3", children: [
        /* @__PURE__ */ e.jsxs("div", { className: "flex items-center gap-2 mb-1", children: [
          /* @__PURE__ */ e.jsx(o, { color: r }),
          /* @__PURE__ */ e.jsx("span", { className: "text-xs font-bold text-white", children: "Database" })
        ] }),
        /* @__PURE__ */ e.jsx("div", { className: "text-[11px] text-slate-400", children: t?.database?.status ?? "unknown" })
      ] }),
      /* @__PURE__ */ e.jsxs("div", { className: "rounded-xl border border-white/10 bg-slate-950/40 p-3", children: [
        /* @__PURE__ */ e.jsxs("div", { className: "flex items-center gap-2 mb-1", children: [
          /* @__PURE__ */ e.jsx(o, { color: i }),
          /* @__PURE__ */ e.jsx("span", { className: "text-xs font-bold text-white", children: "API" })
        ] }),
        /* @__PURE__ */ e.jsx("div", { className: "text-[11px] text-slate-400", children: a?.status ?? "unknown" })
      ] }),
      /* @__PURE__ */ e.jsxs("div", { className: "rounded-xl border border-white/10 bg-slate-950/40 p-3", children: [
        /* @__PURE__ */ e.jsxs("div", { className: "flex items-center gap-2 mb-1", children: [
          /* @__PURE__ */ e.jsx(o, { color: m }),
          /* @__PURE__ */ e.jsx("span", { className: "text-xs font-bold text-white", children: "Game Server" })
        ] }),
        /* @__PURE__ */ e.jsx("div", { className: "text-[11px] text-slate-400", children: s?.game_server?.online ? `${s.game_server.player_count}/${s.game_server.max_players} players` : "offline" })
      ] }),
      /* @__PURE__ */ e.jsxs("div", { className: "rounded-xl border border-white/10 bg-slate-950/40 p-3", children: [
        /* @__PURE__ */ e.jsxs("div", { className: "flex items-center gap-2 mb-1", children: [
          /* @__PURE__ */ e.jsx(o, { color: s?.voice_channel?.count ? "green" : "blue" }),
          /* @__PURE__ */ e.jsx("span", { className: "text-xs font-bold text-white", children: "Voice" })
        ] }),
        /* @__PURE__ */ e.jsxs("div", { className: "text-[11px] text-slate-400", children: [
          s?.voice_channel?.count ?? 0,
          " in voice"
        ] })
      ] })
    ] })
  ] });
}
function C({ tables: t }) {
  return t.length ? /* @__PURE__ */ e.jsxs(x, { children: [
    /* @__PURE__ */ e.jsx("div", { className: "text-xs font-bold uppercase tracking-widest text-slate-400 mb-3", children: "Database Tables" }),
    /* @__PURE__ */ e.jsx("div", { className: "space-y-1.5", children: t.map((a) => /* @__PURE__ */ e.jsxs("div", { className: "flex items-center justify-between rounded-lg border border-white/10 bg-slate-950/30 px-3 py-2", children: [
      /* @__PURE__ */ e.jsxs("div", { className: "flex items-center gap-2", children: [
        /* @__PURE__ */ e.jsx(o, { color: b(a.status) }),
        /* @__PURE__ */ e.jsx("span", { className: "text-xs text-white font-mono", children: a.name }),
        a.required && /* @__PURE__ */ e.jsx("span", { className: "text-[9px] text-amber-400 font-bold", children: "REQ" })
      ] }),
      /* @__PURE__ */ e.jsx("div", { className: "text-[11px] text-slate-400", children: a.status === "ok" ? `${g(a.row_count)} rows` : a.status })
    ] }, a.name)) })
  ] }) : null;
}
function L({ issues: t, warnings: a }) {
  return !t.length && !a.length ? /* @__PURE__ */ e.jsx(x, { children: /* @__PURE__ */ e.jsxs("div", { className: "flex items-center gap-2", children: [
    /* @__PURE__ */ e.jsx(o, { color: "green" }),
    /* @__PURE__ */ e.jsx("span", { className: "text-xs text-slate-300", children: "Diagnostics clean. No critical warnings detected." })
  ] }) }) : /* @__PURE__ */ e.jsxs(x, { children: [
    /* @__PURE__ */ e.jsx("div", { className: "text-xs font-bold uppercase tracking-widest text-slate-400 mb-3", children: "Alerts" }),
    /* @__PURE__ */ e.jsxs("div", { className: "space-y-2", children: [
      t.map((s, r) => /* @__PURE__ */ e.jsxs("div", { className: "flex items-start gap-2", children: [
        /* @__PURE__ */ e.jsx(o, { color: "red" }),
        /* @__PURE__ */ e.jsx("span", { className: "text-xs text-rose-400", children: s })
      ] }, `i${r}`)),
      a.map((s, r) => /* @__PURE__ */ e.jsxs("div", { className: "flex items-start gap-2", children: [
        /* @__PURE__ */ e.jsx(o, { color: "blue" }),
        /* @__PURE__ */ e.jsx("span", { className: "text-xs text-blue-400", children: s })
      ] }, `w${r}`))
    ] })
  ] });
}
function D({ time: t }) {
  return /* @__PURE__ */ e.jsxs(x, { children: [
    /* @__PURE__ */ e.jsx("div", { className: "text-xs font-bold uppercase tracking-widest text-slate-400 mb-3", children: "Timing Metrics" }),
    /* @__PURE__ */ e.jsx("div", { className: "grid grid-cols-2 md:grid-cols-5 gap-3", children: [
      { label: "Raw Dead", value: u(t.raw_dead_seconds) },
      { label: "Capped Dead", value: u(t.agg_dead_seconds) },
      { label: "Raw Denied", value: u(t.raw_denied_seconds) },
      { label: "Cap Hits", value: g(t.cap_hits) },
      { label: "Cap Seconds", value: u(t.cap_seconds) }
    ].map(({ label: a, value: s }) => /* @__PURE__ */ e.jsxs("div", { className: "text-center", children: [
      /* @__PURE__ */ e.jsx("div", { className: "text-[10px] text-slate-500 uppercase", children: a }),
      /* @__PURE__ */ e.jsx("div", { className: "text-sm font-bold text-white font-mono", children: s })
    ] }, a)) })
  ] });
}
function R({ monitoring: t }) {
  const a = Object.entries(t);
  return a.length ? /* @__PURE__ */ e.jsxs(x, { children: [
    /* @__PURE__ */ e.jsx("div", { className: "text-xs font-bold uppercase tracking-widest text-slate-400 mb-3", children: "Monitoring History" }),
    /* @__PURE__ */ e.jsx("div", { className: "grid grid-cols-1 md:grid-cols-2 gap-3", children: a.map(([s, r]) => /* @__PURE__ */ e.jsxs("div", { className: "rounded-lg border border-white/10 bg-slate-950/30 p-3", children: [
      /* @__PURE__ */ e.jsxs("div", { className: "flex items-center gap-2 mb-1", children: [
        /* @__PURE__ */ e.jsx(o, { color: r.error ? "amber" : r.count > 0 ? "green" : "blue" }),
        /* @__PURE__ */ e.jsx("span", { className: "text-xs font-bold text-white capitalize", children: s })
      ] }),
      /* @__PURE__ */ e.jsxs("div", { className: "text-[11px] text-slate-400", children: [
        g(r.count),
        " records",
        r.last_recorded_at && /* @__PURE__ */ e.jsxs(e.Fragment, { children: [
          " · Last: ",
          new Date(r.last_recorded_at).toLocaleString()
        ] })
      ] })
    ] }, s)) })
  ] }) : null;
}
function T() {
  return /* @__PURE__ */ e.jsxs(x, { children: [
    /* @__PURE__ */ e.jsx("div", { className: "text-xs font-bold uppercase tracking-widest text-slate-400 mb-3", children: "Data Flow Pipeline" }),
    /* @__PURE__ */ e.jsx("div", { className: "space-y-1", children: k.map((t, a) => /* @__PURE__ */ e.jsxs("div", { className: "flex items-center gap-2 text-xs", children: [
      /* @__PURE__ */ e.jsx("span", { className: "text-cyan-400 font-mono min-w-[140px] text-right", children: t.from }),
      /* @__PURE__ */ e.jsx("span", { className: "text-slate-600", children: "→" }),
      /* @__PURE__ */ e.jsx("span", { className: "text-emerald-400 font-mono min-w-[140px]", children: t.to }),
      /* @__PURE__ */ e.jsx("span", { className: "text-slate-500 text-[11px]", children: t.label })
    ] }, a)) })
  ] });
}
function A() {
  const [t, a] = d.useState(""), [s, r] = d.useState(null), [i, m] = d.useState(null), c = d.useMemo(() => {
    const l = t.toLowerCase();
    return Object.entries(w).filter(([n, p]) => !(s && p.group !== s || l && !p.title.toLowerCase().includes(l) && !p.eli5.toLowerCase().includes(l)));
  }, [t, s]);
  return /* @__PURE__ */ e.jsxs(N, { children: [
    /* @__PURE__ */ e.jsxs("div", { className: "text-xs font-bold uppercase tracking-widest text-slate-400 mb-3", children: [
      "System Components (",
      Object.keys(w).length,
      ")"
    ] }),
    /* @__PURE__ */ e.jsxs("div", { className: "flex flex-wrap gap-2 mb-3", children: [
      /* @__PURE__ */ e.jsx(
        "button",
        {
          onClick: () => r(null),
          className: `px-2.5 py-1 rounded-lg text-[11px] font-bold border transition ${s ? "border-white/15 text-slate-400 hover:text-white" : "border-cyan-500/50 text-cyan-400 bg-cyan-500/10"}`,
          children: "All"
        }
      ),
      Object.entries(h).map(([l, n]) => /* @__PURE__ */ e.jsx(
        "button",
        {
          onClick: () => r(s === l ? null : l),
          className: `px-2.5 py-1 rounded-lg text-[11px] font-bold border transition ${s === l ? "border-cyan-500/50 text-cyan-400 bg-cyan-500/10" : "border-white/15 text-slate-400 hover:text-white"}`,
          children: n.label
        },
        l
      ))
    ] }),
    /* @__PURE__ */ e.jsx(
      "input",
      {
        value: t,
        onChange: (l) => a(l.target.value),
        placeholder: "Search components...",
        className: "w-full rounded-lg border border-white/10 bg-slate-950/50 px-3 py-2 text-xs text-white placeholder-slate-500 outline-none focus:border-cyan-500/50 mb-3"
      }
    ),
    /* @__PURE__ */ e.jsxs("div", { className: "space-y-1.5 max-h-[500px] overflow-y-auto", children: [
      c.map(([l, n]) => /* @__PURE__ */ e.jsxs(
        "button",
        {
          onClick: () => m(i === l ? null : l),
          className: "w-full text-left rounded-lg border border-white/10 bg-slate-950/30 px-3 py-2 hover:border-cyan-500/30 transition",
          children: [
            /* @__PURE__ */ e.jsxs("div", { className: "flex items-center justify-between", children: [
              /* @__PURE__ */ e.jsxs("div", { className: "flex items-center gap-2", children: [
                /* @__PURE__ */ e.jsx("span", { className: `text-[10px] font-bold ${h[n.group]?.color ?? "text-slate-500"}`, children: h[n.group]?.label ?? n.group }),
                /* @__PURE__ */ e.jsx("span", { className: "text-xs font-semibold text-white", children: n.title })
              ] }),
              /* @__PURE__ */ e.jsx("span", { className: "text-[11px] text-slate-500", children: i === l ? "▲" : "▼" })
            ] }),
            i === l && /* @__PURE__ */ e.jsxs("div", { className: "mt-2 space-y-1 text-[11px]", children: [
              /* @__PURE__ */ e.jsx("div", { className: "text-slate-300", children: n.eli5 }),
              n.files && /* @__PURE__ */ e.jsx("div", { className: "text-slate-500 font-mono", children: n.files })
            ] })
          ]
        },
        l
      )),
      c.length === 0 && /* @__PURE__ */ e.jsx("div", { className: "text-xs text-slate-500 text-center py-4", children: "No matching components." })
    ] })
  ] });
}
function F() {
  const { data: t } = _(), [a, s] = d.useState(0), { data: r, isLoading: i } = f({
    queryKey: ["diagnostics", a],
    queryFn: () => fetch(`${v}/diagnostics`).then((l) => l.json()),
    staleTime: 1e4,
    refetchInterval: 15e3
  }), { data: m } = f({
    queryKey: ["api-status", a],
    queryFn: () => fetch(`${v}/status`).then((l) => l.json()),
    staleTime: 1e4,
    refetchInterval: 15e3
  }), c = d.useCallback(() => s((l) => l + 1), []);
  return t ? i ? /* @__PURE__ */ e.jsx(y, { variant: "card", count: 4 }) : /* @__PURE__ */ e.jsxs("div", { className: "page-shell", children: [
    /* @__PURE__ */ e.jsx(j, { title: "Admin Panel", subtitle: "System diagnostics and operational overview.", eyebrow: "Advanced" }),
    /* @__PURE__ */ e.jsxs("div", { className: "flex items-center justify-between mb-4", children: [
      /* @__PURE__ */ e.jsxs("div", { className: "text-[11px] text-slate-500", children: [
        "Last refresh: ",
        r?.timestamp ? new Date(r.timestamp).toLocaleTimeString() : "--"
      ] }),
      /* @__PURE__ */ e.jsx(
        "button",
        {
          onClick: c,
          className: "px-3 py-1.5 rounded-lg text-xs font-bold border border-white/10 text-slate-300 hover:border-cyan-500/40 hover:text-white transition",
          children: "Refresh Now"
        }
      )
    ] }),
    /* @__PURE__ */ e.jsx(P, { diag: r, apiStatus: m }),
    /* @__PURE__ */ e.jsx("div", { className: "mt-4", children: /* @__PURE__ */ e.jsx(L, { issues: r?.issues ?? [], warnings: r?.warnings ?? [] }) }),
    /* @__PURE__ */ e.jsxs("div", { className: "grid grid-cols-1 lg:grid-cols-2 gap-4 mt-4", children: [
      /* @__PURE__ */ e.jsx(D, { time: r?.time ?? {} }),
      /* @__PURE__ */ e.jsx(R, { monitoring: r?.monitoring ?? {} })
    ] }),
    /* @__PURE__ */ e.jsxs("div", { className: "grid grid-cols-1 lg:grid-cols-2 gap-4 mt-4", children: [
      /* @__PURE__ */ e.jsx(C, { tables: r?.tables ?? [] }),
      /* @__PURE__ */ e.jsx(T, {})
    ] }),
    /* @__PURE__ */ e.jsx("div", { className: "mt-4", children: /* @__PURE__ */ e.jsx(A, {}) })
  ] }) : /* @__PURE__ */ e.jsxs("div", { className: "page-shell", children: [
    /* @__PURE__ */ e.jsx(j, { title: "Admin Panel", subtitle: "Operational diagnostics and architecture.", eyebrow: "Advanced" }),
    /* @__PURE__ */ e.jsxs("div", { className: "text-center py-16", children: [
      /* @__PURE__ */ e.jsx("div", { className: "text-4xl mb-4", children: "🔒" }),
      /* @__PURE__ */ e.jsx("p", { className: "text-slate-400 text-lg mb-4", children: "Admin access requires authentication." }),
      /* @__PURE__ */ e.jsx("a", { href: "/auth/discord", className: "inline-block px-6 py-2 rounded-xl bg-indigo-600 text-white font-bold text-sm hover:bg-indigo-500 transition", children: "Login with Discord" })
    ] })
  ] });
}
export {
  F as default
};
