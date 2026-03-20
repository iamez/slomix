import { j as e, S as N, r as g } from "./route-host-Ba3v8uFM.js";
import { P as f } from "./PageHeader-CQ7BTOQj.js";
import { G as c } from "./GlassPanel-C-uUmQaB.js";
import { M as y, N as v, L as w } from "./hooks-CyQgvbI9.js";
import { n as j } from "./navigation-BDd1HkpE.js";
const b = {
  uploaded: "text-slate-300 border-slate-500/40 bg-slate-800/40",
  scanning: "text-cyan-400 border-cyan-400/40 bg-cyan-400/10",
  analyzed: "text-emerald-400 border-emerald-400/40 bg-emerald-400/10",
  failed: "text-rose-400 border-rose-400/40 bg-rose-400/10",
  queued: "text-amber-400 border-amber-400/40 bg-amber-400/10",
  rendering: "text-cyan-400 border-cyan-400/40 bg-cyan-400/10",
  rendered: "text-emerald-400 border-emerald-400/40 bg-emerald-400/10"
};
function u(a) {
  if (a == null || !Number.isFinite(a)) return "--";
  const r = Math.max(0, Math.floor(a / 1e3)), s = Math.floor(r / 3600), t = Math.floor(r % 3600 / 60), n = r % 60;
  return s > 0 ? `${s}:${String(t).padStart(2, "0")}:${String(n).padStart(2, "0")}` : `${String(t).padStart(2, "0")}:${String(n).padStart(2, "0")}`;
}
function p(a, r) {
  return a == null || !Number.isFinite(a) ? "--" : u(Math.max(0, a - r));
}
function k({ events: a, roundStartMs: r }) {
  const s = a.slice(0, 120);
  return s.length === 0 ? /* @__PURE__ */ e.jsx("p", { className: "text-slate-500 text-sm", children: "No timeline events." }) : /* @__PURE__ */ e.jsx("div", { className: "space-y-0.5 max-h-64 overflow-y-auto text-xs", children: s.map((t, n) => /* @__PURE__ */ e.jsxs("div", { className: "flex gap-2", children: [
    /* @__PURE__ */ e.jsx("span", { className: "text-slate-500 w-14 shrink-0 text-right", children: p(t.t_ms, r) }),
    t.type === "kill" ? /* @__PURE__ */ e.jsxs("span", { className: "text-slate-200", children: [
      t.attacker || "world",
      " → ",
      t.victim || "?",
      " ",
      /* @__PURE__ */ e.jsx("span", { className: "text-amber-400", children: t.weapon || "--" })
    ] }) : t.type === "chat" ? /* @__PURE__ */ e.jsxs("span", { className: "text-slate-300", children: [
      t.attacker,
      ": ",
      t.message
    ] }) : /* @__PURE__ */ e.jsx("span", { className: "text-slate-300", children: t.type })
  ] }, n)) });
}
function S({
  highlight: a,
  demoId: r,
  roundStartMs: s,
  onRenderQueued: t
}) {
  const [n, i] = g.useState(!1), x = a.meta, d = Array.isArray(x?.kill_sequence) ? x.kill_sequence : [], o = x?.weapons_used ?? {}, m = async () => {
    i(!0);
    try {
      await w.queueGreatshotRender(r, a.id), t();
    } catch (l) {
      alert(l instanceof Error ? l.message : "Render queue failed");
    } finally {
      i(!1);
    }
  };
  return /* @__PURE__ */ e.jsx("div", { className: "glass-card p-4 rounded-xl border border-white/10", children: /* @__PURE__ */ e.jsxs("div", { className: "flex items-center justify-between gap-3", children: [
    /* @__PURE__ */ e.jsxs("div", { className: "flex-1 min-w-0", children: [
      /* @__PURE__ */ e.jsx("div", { className: "text-sm font-bold text-white", children: a.type }),
      /* @__PURE__ */ e.jsxs("div", { className: "text-xs text-slate-400 mt-1", children: [
        a.player,
        " | ",
        p(a.start_ms, s),
        " – ",
        p(a.end_ms, s),
        " | score ",
        a.score.toFixed(2)
      ] }),
      a.explanation && /* @__PURE__ */ e.jsx("div", { className: "text-xs text-slate-500 mt-1", children: a.explanation }),
      d.length > 0 && /* @__PURE__ */ e.jsx("div", { className: "mt-2 text-xs leading-relaxed space-y-0.5", children: d.map((l, h) => /* @__PURE__ */ e.jsxs("div", { children: [
        /* @__PURE__ */ e.jsx("span", { className: "text-slate-500", children: p(l.t_ms, s) }),
        " ",
        String(l.victim || "?"),
        " ",
        /* @__PURE__ */ e.jsx("span", { className: "text-amber-400", children: String(l.weapon || "?") }),
        l.headshot ? /* @__PURE__ */ e.jsx("span", { className: "text-rose-400 ml-1", children: "HS" }) : null
      ] }, h)) }),
      Object.keys(o).length > 0 && /* @__PURE__ */ e.jsx("div", { className: "mt-2 flex flex-wrap gap-1", children: Object.entries(o).sort((l, h) => h[1] - l[1]).map(([l, h]) => /* @__PURE__ */ e.jsxs("span", { className: "px-2 py-0.5 rounded border border-white/10 text-[10px] text-slate-300", children: [
        l,
        " x",
        h
      ] }, l)) })
    ] }),
    /* @__PURE__ */ e.jsxs("div", { className: "flex items-center gap-2 shrink-0", children: [
      a.clip_download && /* @__PURE__ */ e.jsx(
        "a",
        {
          href: a.clip_download,
          className: "px-3 py-2 rounded-lg text-xs font-bold border border-amber-400/40 text-amber-400 hover:bg-amber-400/10 transition",
          children: "Clip"
        }
      ),
      /* @__PURE__ */ e.jsx(
        "button",
        {
          onClick: m,
          disabled: n,
          className: "px-3 py-2 rounded-lg text-xs font-bold border border-cyan-400/40 text-cyan-400 hover:bg-cyan-400/10 transition disabled:opacity-50",
          children: n ? "Queuing..." : "Render"
        }
      )
    ] })
  ] }) });
}
function _({ job: a }) {
  const r = b[a.status] || "text-slate-300 border-white/10";
  return /* @__PURE__ */ e.jsxs("div", { className: "flex items-center justify-between text-xs glass-card rounded-xl p-3 border border-white/5", children: [
    /* @__PURE__ */ e.jsx("span", { className: "text-slate-300 truncate", children: a.id }),
    /* @__PURE__ */ e.jsxs("div", { className: "flex items-center gap-2 shrink-0", children: [
      /* @__PURE__ */ e.jsx("span", { className: `px-2 py-1 rounded border ${r}`, children: a.status.toUpperCase() }),
      a.video_download && /* @__PURE__ */ e.jsx(
        "a",
        {
          href: a.video_download,
          className: "px-2 py-1 rounded border border-emerald-400/40 text-emerald-400 hover:bg-emerald-400/10 transition text-[11px] font-bold",
          children: "MP4"
        }
      ),
      a.error && /* @__PURE__ */ e.jsx("span", { className: "text-rose-400", children: a.error })
    ] })
  ] });
}
function C({ stats: a }) {
  const r = Object.entries(a).map(([s, t]) => ({
    name: s,
    kills: t.kills || 0,
    deaths: t.deaths || 0,
    damage: t.damage_given || t.damage || 0,
    accuracy: t.accuracy ?? null,
    headshots: t.headshots || t.headshot_kills || 0,
    tpm: t.tpm ?? t.time_played_minutes ?? null
  })).sort((s, t) => t.kills - s.kills);
  return /* @__PURE__ */ e.jsx("div", { className: "overflow-x-auto", children: /* @__PURE__ */ e.jsxs("table", { className: "w-full text-xs", children: [
    /* @__PURE__ */ e.jsx("thead", { children: /* @__PURE__ */ e.jsxs("tr", { className: "text-slate-500 border-b border-white/10", children: [
      /* @__PURE__ */ e.jsx("th", { className: "text-left py-1 pr-3", children: "Player" }),
      /* @__PURE__ */ e.jsx("th", { className: "text-right pr-3", children: "Kills" }),
      /* @__PURE__ */ e.jsx("th", { className: "text-right pr-3", children: "Deaths" }),
      /* @__PURE__ */ e.jsx("th", { className: "text-right pr-3", children: "KDR" }),
      /* @__PURE__ */ e.jsx("th", { className: "text-right pr-3", children: "Damage" }),
      /* @__PURE__ */ e.jsx("th", { className: "text-right pr-3", children: "Acc%" }),
      /* @__PURE__ */ e.jsx("th", { className: "text-right", children: "HS" })
    ] }) }),
    /* @__PURE__ */ e.jsx("tbody", { children: r.map((s) => {
      const t = s.deaths > 0 ? (s.kills / s.deaths).toFixed(2) : s.kills > 0 ? String(s.kills) : "0.00";
      return /* @__PURE__ */ e.jsxs("tr", { className: "border-b border-white/5", children: [
        /* @__PURE__ */ e.jsx("td", { className: "py-1 pr-3 text-slate-200", children: s.name }),
        /* @__PURE__ */ e.jsx("td", { className: "text-right pr-3 text-white", children: s.kills }),
        /* @__PURE__ */ e.jsx("td", { className: "text-right pr-3 text-white", children: s.deaths }),
        /* @__PURE__ */ e.jsx("td", { className: "text-right pr-3 text-white", children: t }),
        /* @__PURE__ */ e.jsx("td", { className: "text-right pr-3 text-white", children: s.damage }),
        /* @__PURE__ */ e.jsx("td", { className: "text-right pr-3 text-white", children: s.accuracy != null ? s.accuracy.toFixed(1) : "--" }),
        /* @__PURE__ */ e.jsx("td", { className: "text-right text-white", children: s.headshots })
      ] }, s.name);
    }) })
  ] }) });
}
function D({ demoId: a }) {
  const { data: r, isLoading: s } = v(a);
  if (s) return /* @__PURE__ */ e.jsx("p", { className: "text-slate-500 text-sm", children: "Checking database..." });
  if (!r) return /* @__PURE__ */ e.jsx("p", { className: "text-slate-500 text-sm", children: "Cross-reference unavailable." });
  if (!r.matched) return /* @__PURE__ */ e.jsx("p", { className: "text-slate-500 text-sm", children: r.reason || "No match found" });
  const t = r.round ?? {}, n = Number(t.confidence || 0), i = n >= 80 ? "text-emerald-400" : n >= 50 ? "text-amber-400" : "text-rose-400";
  return /* @__PURE__ */ e.jsxs("div", { children: [
    /* @__PURE__ */ e.jsx("div", { className: "flex items-center gap-3 mb-3", children: /* @__PURE__ */ e.jsxs("span", { className: `text-xs font-bold ${i}`, children: [
      n,
      "% confidence"
    ] }) }),
    /* @__PURE__ */ e.jsxs("div", { className: "grid grid-cols-2 sm:grid-cols-4 gap-2 text-xs mb-4", children: [
      /* @__PURE__ */ e.jsxs("div", { children: [
        /* @__PURE__ */ e.jsx("span", { className: "text-slate-500", children: "Round ID:" }),
        " ",
        /* @__PURE__ */ e.jsx("span", { className: "text-white", children: String(t.round_id ?? "--") })
      ] }),
      /* @__PURE__ */ e.jsxs("div", { children: [
        /* @__PURE__ */ e.jsx("span", { className: "text-slate-500", children: "Session:" }),
        " ",
        /* @__PURE__ */ e.jsx("span", { className: "text-white", children: String(t.gaming_session_id ?? "--") })
      ] }),
      /* @__PURE__ */ e.jsxs("div", { children: [
        /* @__PURE__ */ e.jsx("span", { className: "text-slate-500", children: "Date:" }),
        " ",
        /* @__PURE__ */ e.jsx("span", { className: "text-white", children: String(t.round_date ?? "--") })
      ] }),
      /* @__PURE__ */ e.jsxs("div", { children: [
        /* @__PURE__ */ e.jsx("span", { className: "text-slate-500", children: "Winner:" }),
        " ",
        /* @__PURE__ */ e.jsx("span", { className: "text-white", children: String(t.winner_team ?? "--") })
      ] })
    ] })
  ] });
}
function $({ params: a }) {
  const r = a?.demoId ?? null, { data: s, isLoading: t, error: n, refetch: i } = y(r);
  if (t) return /* @__PURE__ */ e.jsx(N, { variant: "card", count: 3 });
  if (n || !s)
    return /* @__PURE__ */ e.jsxs("div", { className: "text-center py-16", children: [
      /* @__PURE__ */ e.jsx("div", { className: "text-4xl mb-4", children: "🔍" }),
      /* @__PURE__ */ e.jsx("div", { className: "text-lg font-bold text-rose-400 mb-1", children: "Demo not found" }),
      /* @__PURE__ */ e.jsx("p", { className: "text-sm text-slate-500 mb-4", children: "This demo may have been deleted or you don't have access." }),
      /* @__PURE__ */ e.jsx("button", { onClick: () => j("#/greatshot/demos"), className: "text-sm text-cyan-400 hover:text-white transition-colors", children: "Back to Greatshot" })
    ] });
  const x = b[s.status] || "text-slate-300 border-white/10", d = s.metadata || {}, o = Number(d.start_ms || 0), m = s.analysis?.events ?? [];
  return /* @__PURE__ */ e.jsxs("div", { children: [
    /* @__PURE__ */ e.jsxs(
      "button",
      {
        onClick: () => j("#/greatshot/demos"),
        className: "text-xs text-slate-500 hover:text-slate-300 transition-colors mb-4 inline-flex items-center gap-1",
        children: [
          /* @__PURE__ */ e.jsx("span", { children: "←" }),
          " Back to Greatshot"
        ]
      }
    ),
    /* @__PURE__ */ e.jsx(f, { title: s.filename || s.id, children: /* @__PURE__ */ e.jsx("span", { className: `px-3 py-1 rounded-md text-xs font-bold border ${x}`, children: s.status.toUpperCase() }) }),
    s.error && /* @__PURE__ */ e.jsxs("div", { className: "mb-6 text-sm text-rose-400 glass-panel rounded-xl p-4 border border-rose-400/20", children: [
      "Error: ",
      s.error
    ] }),
    /* @__PURE__ */ e.jsxs(c, { className: "mb-6", children: [
      /* @__PURE__ */ e.jsx("div", { className: "text-xs font-bold uppercase tracking-widest text-slate-500 mb-3", children: "Demo Info" }),
      /* @__PURE__ */ e.jsxs("div", { className: "grid grid-cols-2 sm:grid-cols-5 gap-3 text-sm", children: [
        /* @__PURE__ */ e.jsxs("div", { children: [
          /* @__PURE__ */ e.jsx("span", { className: "text-slate-500 text-xs", children: "Map" }),
          /* @__PURE__ */ e.jsx("div", { className: "text-white font-bold", children: String(d.map || "--") })
        ] }),
        /* @__PURE__ */ e.jsxs("div", { children: [
          /* @__PURE__ */ e.jsx("span", { className: "text-slate-500 text-xs", children: "Duration" }),
          /* @__PURE__ */ e.jsx("div", { className: "text-white font-bold", children: u(d.duration_ms) })
        ] }),
        /* @__PURE__ */ e.jsxs("div", { children: [
          /* @__PURE__ */ e.jsx("span", { className: "text-slate-500 text-xs", children: "Mod" }),
          /* @__PURE__ */ e.jsx("div", { className: "text-white font-bold", children: String(d.mod || "--") })
        ] }),
        /* @__PURE__ */ e.jsxs("div", { children: [
          /* @__PURE__ */ e.jsx("span", { className: "text-slate-500 text-xs", children: "Players" }),
          /* @__PURE__ */ e.jsx("div", { className: "text-white font-bold", children: String(s.analysis?.stats?.player_count ?? s.analysis?.metadata?.player_count ?? "--") })
        ] }),
        /* @__PURE__ */ e.jsxs("div", { children: [
          /* @__PURE__ */ e.jsx("span", { className: "text-slate-500 text-xs", children: "Created" }),
          /* @__PURE__ */ e.jsx("div", { className: "text-white font-bold", children: s.created_at ? new Date(s.created_at).toLocaleString() : "--" })
        ] })
      ] })
    ] }),
    (s.downloads.json || s.downloads.txt) && /* @__PURE__ */ e.jsxs("div", { className: "flex gap-2 mb-6", children: [
      s.downloads.json && /* @__PURE__ */ e.jsx("a", { href: s.downloads.json, className: "px-3 py-2 rounded-lg border border-cyan-400/40 text-cyan-400 text-xs font-bold hover:bg-cyan-400/10 transition", children: "Download JSON" }),
      s.downloads.txt && /* @__PURE__ */ e.jsx("a", { href: s.downloads.txt, className: "px-3 py-2 rounded-lg border border-amber-400/40 text-amber-400 text-xs font-bold hover:bg-amber-400/10 transition", children: "Download TXT" })
    ] }),
    s.player_stats && Object.keys(s.player_stats).length > 0 && /* @__PURE__ */ e.jsxs(c, { className: "mb-6", children: [
      /* @__PURE__ */ e.jsx("div", { className: "text-xs font-bold uppercase tracking-widest text-slate-500 mb-3", children: "Player Stats" }),
      /* @__PURE__ */ e.jsx(C, { stats: s.player_stats })
    ] }),
    /* @__PURE__ */ e.jsxs(c, { className: "mb-6", children: [
      /* @__PURE__ */ e.jsxs("div", { className: "text-xs font-bold uppercase tracking-widest text-slate-500 mb-3", children: [
        "Highlights (",
        s.highlights.length,
        ")"
      ] }),
      s.highlights.length === 0 ? /* @__PURE__ */ e.jsx("p", { className: "text-slate-500 text-sm", children: "No clip-worthy highlights detected." }) : /* @__PURE__ */ e.jsx("div", { className: "space-y-3", children: s.highlights.map((l) => /* @__PURE__ */ e.jsx(S, { highlight: l, demoId: s.id, roundStartMs: o, onRenderQueued: i }, l.id)) })
    ] }),
    s.renders.length > 0 && /* @__PURE__ */ e.jsxs(c, { className: "mb-6", children: [
      /* @__PURE__ */ e.jsxs("div", { className: "text-xs font-bold uppercase tracking-widest text-slate-500 mb-3", children: [
        "Render Jobs (",
        s.renders.length,
        ")"
      ] }),
      /* @__PURE__ */ e.jsx("div", { className: "space-y-2", children: s.renders.map((l) => /* @__PURE__ */ e.jsx(_, { job: l }, l.id)) })
    ] }),
    m.length > 0 && /* @__PURE__ */ e.jsxs(c, { className: "mb-6", children: [
      /* @__PURE__ */ e.jsxs("div", { className: "text-xs font-bold uppercase tracking-widest text-slate-500 mb-3", children: [
        "Timeline (",
        m.length,
        " events)"
      ] }),
      /* @__PURE__ */ e.jsx(k, { events: m, roundStartMs: o })
    ] }),
    s.status === "analyzed" && /* @__PURE__ */ e.jsxs(c, { children: [
      /* @__PURE__ */ e.jsx("div", { className: "text-xs font-bold uppercase tracking-widest text-slate-500 mb-3", children: "Database Cross-Reference" }),
      /* @__PURE__ */ e.jsx(D, { demoId: s.id })
    ] })
  ] });
}
export {
  $ as default
};
