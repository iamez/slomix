import { jsx as e, jsxs as a } from "react/jsx-runtime";
import { useState as f } from "react";
import { P as y } from "./PageHeader-D4CVo02x.js";
import { G as o } from "./GlassPanel-S_ADyiYR.js";
import { S as v } from "./route-host-CUL1oI6Z.js";
import { B as w, C as k, A as S } from "./hooks-UFUMZFGB.js";
import { n as u } from "./navigation-BDd1HkpE.js";
const N = {
  uploaded: "text-slate-300 border-slate-500/40 bg-slate-800/40",
  scanning: "text-cyan-400 border-cyan-400/40 bg-cyan-400/10",
  analyzed: "text-emerald-400 border-emerald-400/40 bg-emerald-400/10",
  failed: "text-rose-400 border-rose-400/40 bg-rose-400/10",
  queued: "text-amber-400 border-amber-400/40 bg-amber-400/10",
  rendering: "text-cyan-400 border-cyan-400/40 bg-cyan-400/10",
  rendered: "text-emerald-400 border-emerald-400/40 bg-emerald-400/10"
};
function g(r) {
  if (r == null || !Number.isFinite(r)) return "--";
  const l = Math.max(0, Math.floor(r / 1e3)), t = Math.floor(l / 3600), s = Math.floor(l % 3600 / 60), d = l % 60;
  return t > 0 ? `${t}:${String(s).padStart(2, "0")}:${String(d).padStart(2, "0")}` : `${String(s).padStart(2, "0")}:${String(d).padStart(2, "0")}`;
}
function b(r, l) {
  return r == null || !Number.isFinite(r) ? "--" : g(Math.max(0, r - l));
}
function _({ events: r, roundStartMs: l }) {
  const t = r.slice(0, 120);
  return t.length === 0 ? /* @__PURE__ */ e("p", { className: "text-slate-500 text-sm", children: "No timeline events." }) : /* @__PURE__ */ e("div", { className: "space-y-0.5 max-h-64 overflow-y-auto text-xs", children: t.map((s, d) => /* @__PURE__ */ a("div", { className: "flex gap-2", children: [
    /* @__PURE__ */ e("span", { className: "text-slate-500 w-14 shrink-0 text-right", children: b(s.t_ms, l) }),
    s.type === "kill" ? /* @__PURE__ */ a("span", { className: "text-slate-200", children: [
      s.attacker || "world",
      " → ",
      s.victim || "?",
      " ",
      /* @__PURE__ */ e("span", { className: "text-amber-400", children: s.weapon || "--" })
    ] }) : s.type === "chat" ? /* @__PURE__ */ a("span", { className: "text-slate-300", children: [
      s.attacker,
      ": ",
      s.message
    ] }) : /* @__PURE__ */ e("span", { className: "text-slate-300", children: s.type })
  ] }, d)) });
}
function C({
  highlight: r,
  demoId: l,
  roundStartMs: t,
  onRenderQueued: s
}) {
  const [d, c] = f(!1), m = r.meta, i = Array.isArray(m?.kill_sequence) ? m.kill_sequence : [], h = m?.weapons_used ?? {}, x = async () => {
    c(!0);
    try {
      await S.queueGreatshotRender(l, r.id), s();
    } catch (n) {
      alert(n instanceof Error ? n.message : "Render queue failed");
    } finally {
      c(!1);
    }
  };
  return /* @__PURE__ */ e("div", { className: "glass-card p-4 rounded-xl border border-white/10", children: /* @__PURE__ */ a("div", { className: "flex items-center justify-between gap-3", children: [
    /* @__PURE__ */ a("div", { className: "flex-1 min-w-0", children: [
      /* @__PURE__ */ e("div", { className: "text-sm font-bold text-white", children: r.type }),
      /* @__PURE__ */ a("div", { className: "text-xs text-slate-400 mt-1", children: [
        r.player,
        " | ",
        b(r.start_ms, t),
        " – ",
        b(r.end_ms, t),
        " | score ",
        r.score.toFixed(2)
      ] }),
      r.explanation && /* @__PURE__ */ e("div", { className: "text-xs text-slate-500 mt-1", children: r.explanation }),
      i.length > 0 && /* @__PURE__ */ e("div", { className: "mt-2 text-xs leading-relaxed space-y-0.5", children: i.map((n, p) => /* @__PURE__ */ a("div", { children: [
        /* @__PURE__ */ e("span", { className: "text-slate-500", children: b(n.t_ms, t) }),
        " ",
        String(n.victim || "?"),
        " ",
        /* @__PURE__ */ e("span", { className: "text-amber-400", children: String(n.weapon || "?") }),
        n.headshot ? /* @__PURE__ */ e("span", { className: "text-rose-400 ml-1", children: "HS" }) : null
      ] }, p)) }),
      Object.keys(h).length > 0 && /* @__PURE__ */ e("div", { className: "mt-2 flex flex-wrap gap-1", children: Object.entries(h).sort((n, p) => p[1] - n[1]).map(([n, p]) => /* @__PURE__ */ a("span", { className: "px-2 py-0.5 rounded border border-white/10 text-[10px] text-slate-300", children: [
        n,
        " x",
        p
      ] }, n)) })
    ] }),
    /* @__PURE__ */ a("div", { className: "flex items-center gap-2 shrink-0", children: [
      r.clip_download && /* @__PURE__ */ e(
        "a",
        {
          href: r.clip_download,
          className: "px-3 py-2 rounded-lg text-xs font-bold border border-amber-400/40 text-amber-400 hover:bg-amber-400/10 transition",
          children: "Clip"
        }
      ),
      /* @__PURE__ */ e(
        "button",
        {
          onClick: x,
          disabled: d,
          className: "px-3 py-2 rounded-lg text-xs font-bold border border-cyan-400/40 text-cyan-400 hover:bg-cyan-400/10 transition disabled:opacity-50",
          children: d ? "Queuing..." : "Render"
        }
      )
    ] })
  ] }) });
}
function D({ job: r }) {
  const l = N[r.status] || "text-slate-300 border-white/10";
  return /* @__PURE__ */ a("div", { className: "flex items-center justify-between text-xs glass-card rounded-xl p-3 border border-white/5", children: [
    /* @__PURE__ */ e("span", { className: "text-slate-300 truncate", children: r.id }),
    /* @__PURE__ */ a("div", { className: "flex items-center gap-2 shrink-0", children: [
      /* @__PURE__ */ e("span", { className: `px-2 py-1 rounded border ${l}`, children: r.status.toUpperCase() }),
      r.video_download && /* @__PURE__ */ e(
        "a",
        {
          href: r.video_download,
          className: "px-2 py-1 rounded border border-emerald-400/40 text-emerald-400 hover:bg-emerald-400/10 transition text-[11px] font-bold",
          children: "MP4"
        }
      ),
      r.error && /* @__PURE__ */ e("span", { className: "text-rose-400", children: r.error })
    ] })
  ] });
}
function R({ stats: r }) {
  const l = Object.entries(r).map(([t, s]) => ({
    name: t,
    kills: s.kills || 0,
    deaths: s.deaths || 0,
    damage: s.damage_given || s.damage || 0,
    accuracy: s.accuracy ?? null,
    headshots: s.headshots || s.headshot_kills || 0,
    tpm: s.tpm ?? s.time_played_minutes ?? null
  })).sort((t, s) => s.kills - t.kills);
  return /* @__PURE__ */ e("div", { className: "overflow-x-auto", children: /* @__PURE__ */ a("table", { className: "w-full text-xs", children: [
    /* @__PURE__ */ e("thead", { children: /* @__PURE__ */ a("tr", { className: "text-slate-500 border-b border-white/10", children: [
      /* @__PURE__ */ e("th", { className: "text-left py-1 pr-3", children: "Player" }),
      /* @__PURE__ */ e("th", { className: "text-right pr-3", children: "Kills" }),
      /* @__PURE__ */ e("th", { className: "text-right pr-3", children: "Deaths" }),
      /* @__PURE__ */ e("th", { className: "text-right pr-3", children: "KDR" }),
      /* @__PURE__ */ e("th", { className: "text-right pr-3", children: "Damage" }),
      /* @__PURE__ */ e("th", { className: "text-right pr-3", children: "Acc%" }),
      /* @__PURE__ */ e("th", { className: "text-right", children: "HS" })
    ] }) }),
    /* @__PURE__ */ e("tbody", { children: l.map((t) => {
      const s = t.deaths > 0 ? (t.kills / t.deaths).toFixed(2) : t.kills > 0 ? String(t.kills) : "0.00";
      return /* @__PURE__ */ a("tr", { className: "border-b border-white/5", children: [
        /* @__PURE__ */ e("td", { className: "py-1 pr-3 text-slate-200", children: t.name }),
        /* @__PURE__ */ e("td", { className: "text-right pr-3 text-white", children: t.kills }),
        /* @__PURE__ */ e("td", { className: "text-right pr-3 text-white", children: t.deaths }),
        /* @__PURE__ */ e("td", { className: "text-right pr-3 text-white", children: s }),
        /* @__PURE__ */ e("td", { className: "text-right pr-3 text-white", children: t.damage }),
        /* @__PURE__ */ e("td", { className: "text-right pr-3 text-white", children: t.accuracy != null ? t.accuracy.toFixed(1) : "--" }),
        /* @__PURE__ */ e("td", { className: "text-right text-white", children: t.headshots })
      ] }, t.name);
    }) })
  ] }) });
}
function M({ demoId: r }) {
  const { data: l, isLoading: t } = k(r);
  if (t) return /* @__PURE__ */ e("p", { className: "text-slate-500 text-sm", children: "Checking database..." });
  if (!l) return /* @__PURE__ */ e("p", { className: "text-slate-500 text-sm", children: "Cross-reference unavailable." });
  if (!l.matched) return /* @__PURE__ */ e("p", { className: "text-slate-500 text-sm", children: l.reason || "No match found" });
  const s = l.round ?? {}, d = Number(s.confidence || 0), c = d >= 80 ? "text-emerald-400" : d >= 50 ? "text-amber-400" : "text-rose-400";
  return /* @__PURE__ */ a("div", { children: [
    /* @__PURE__ */ e("div", { className: "flex items-center gap-3 mb-3", children: /* @__PURE__ */ a("span", { className: `text-xs font-bold ${c}`, children: [
      d,
      "% confidence"
    ] }) }),
    /* @__PURE__ */ a("div", { className: "grid grid-cols-2 sm:grid-cols-4 gap-2 text-xs mb-4", children: [
      /* @__PURE__ */ a("div", { children: [
        /* @__PURE__ */ e("span", { className: "text-slate-500", children: "Round ID:" }),
        " ",
        /* @__PURE__ */ e("span", { className: "text-white", children: String(s.round_id ?? "--") })
      ] }),
      /* @__PURE__ */ a("div", { children: [
        /* @__PURE__ */ e("span", { className: "text-slate-500", children: "Session:" }),
        " ",
        /* @__PURE__ */ e("span", { className: "text-white", children: String(s.gaming_session_id ?? "--") })
      ] }),
      /* @__PURE__ */ a("div", { children: [
        /* @__PURE__ */ e("span", { className: "text-slate-500", children: "Date:" }),
        " ",
        /* @__PURE__ */ e("span", { className: "text-white", children: String(s.round_date ?? "--") })
      ] }),
      /* @__PURE__ */ a("div", { children: [
        /* @__PURE__ */ e("span", { className: "text-slate-500", children: "Winner:" }),
        " ",
        /* @__PURE__ */ e("span", { className: "text-white", children: String(s.winner_team ?? "--") })
      ] })
    ] })
  ] });
}
function A({ params: r }) {
  const l = r?.demoId ?? null, { data: t, isLoading: s, error: d, refetch: c } = w(l);
  if (s) return /* @__PURE__ */ e(v, { variant: "card", count: 3 });
  if (d || !t)
    return /* @__PURE__ */ a("div", { className: "text-center py-16", children: [
      /* @__PURE__ */ e("div", { className: "text-4xl mb-4", children: "🔍" }),
      /* @__PURE__ */ e("div", { className: "text-lg font-bold text-rose-400 mb-1", children: "Demo not found" }),
      /* @__PURE__ */ e("p", { className: "text-sm text-slate-500 mb-4", children: "This demo may have been deleted or you don't have access." }),
      /* @__PURE__ */ e("button", { onClick: () => u("#/greatshot/demos"), className: "text-sm text-cyan-400 hover:text-white transition-colors", children: "Back to Greatshot" })
    ] });
  const m = N[t.status] || "text-slate-300 border-white/10", i = t.metadata || {}, h = Number(i.start_ms || 0), x = t.analysis?.events ?? [];
  return /* @__PURE__ */ a("div", { children: [
    /* @__PURE__ */ a(
      "button",
      {
        onClick: () => u("#/greatshot/demos"),
        className: "text-xs text-slate-500 hover:text-slate-300 transition-colors mb-4 inline-flex items-center gap-1",
        children: [
          /* @__PURE__ */ e("span", { children: "←" }),
          " Back to Greatshot"
        ]
      }
    ),
    /* @__PURE__ */ e(y, { title: t.filename || t.id, children: /* @__PURE__ */ e("span", { className: `px-3 py-1 rounded-md text-xs font-bold border ${m}`, children: t.status.toUpperCase() }) }),
    t.error && /* @__PURE__ */ a("div", { className: "mb-6 text-sm text-rose-400 glass-panel rounded-xl p-4 border border-rose-400/20", children: [
      "Error: ",
      t.error
    ] }),
    /* @__PURE__ */ a(o, { className: "mb-6", children: [
      /* @__PURE__ */ e("div", { className: "text-xs font-bold uppercase tracking-widest text-slate-500 mb-3", children: "Demo Info" }),
      /* @__PURE__ */ a("div", { className: "grid grid-cols-2 sm:grid-cols-5 gap-3 text-sm", children: [
        /* @__PURE__ */ a("div", { children: [
          /* @__PURE__ */ e("span", { className: "text-slate-500 text-xs", children: "Map" }),
          /* @__PURE__ */ e("div", { className: "text-white font-bold", children: String(i.map || "--") })
        ] }),
        /* @__PURE__ */ a("div", { children: [
          /* @__PURE__ */ e("span", { className: "text-slate-500 text-xs", children: "Duration" }),
          /* @__PURE__ */ e("div", { className: "text-white font-bold", children: g(i.duration_ms) })
        ] }),
        /* @__PURE__ */ a("div", { children: [
          /* @__PURE__ */ e("span", { className: "text-slate-500 text-xs", children: "Mod" }),
          /* @__PURE__ */ e("div", { className: "text-white font-bold", children: String(i.mod || "--") })
        ] }),
        /* @__PURE__ */ a("div", { children: [
          /* @__PURE__ */ e("span", { className: "text-slate-500 text-xs", children: "Players" }),
          /* @__PURE__ */ e("div", { className: "text-white font-bold", children: String(t.analysis?.stats?.player_count ?? t.analysis?.metadata?.player_count ?? "--") })
        ] }),
        /* @__PURE__ */ a("div", { children: [
          /* @__PURE__ */ e("span", { className: "text-slate-500 text-xs", children: "Created" }),
          /* @__PURE__ */ e("div", { className: "text-white font-bold", children: t.created_at ? new Date(t.created_at).toLocaleString() : "--" })
        ] })
      ] })
    ] }),
    (t.downloads.json || t.downloads.txt) && /* @__PURE__ */ a("div", { className: "flex gap-2 mb-6", children: [
      t.downloads.json && /* @__PURE__ */ e("a", { href: t.downloads.json, className: "px-3 py-2 rounded-lg border border-cyan-400/40 text-cyan-400 text-xs font-bold hover:bg-cyan-400/10 transition", children: "Download JSON" }),
      t.downloads.txt && /* @__PURE__ */ e("a", { href: t.downloads.txt, className: "px-3 py-2 rounded-lg border border-amber-400/40 text-amber-400 text-xs font-bold hover:bg-amber-400/10 transition", children: "Download TXT" })
    ] }),
    t.player_stats && Object.keys(t.player_stats).length > 0 && /* @__PURE__ */ a(o, { className: "mb-6", children: [
      /* @__PURE__ */ e("div", { className: "text-xs font-bold uppercase tracking-widest text-slate-500 mb-3", children: "Player Stats" }),
      /* @__PURE__ */ e(R, { stats: t.player_stats })
    ] }),
    /* @__PURE__ */ a(o, { className: "mb-6", children: [
      /* @__PURE__ */ a("div", { className: "text-xs font-bold uppercase tracking-widest text-slate-500 mb-3", children: [
        "Highlights (",
        t.highlights.length,
        ")"
      ] }),
      t.highlights.length === 0 ? /* @__PURE__ */ e("p", { className: "text-slate-500 text-sm", children: "No clip-worthy highlights detected." }) : /* @__PURE__ */ e("div", { className: "space-y-3", children: t.highlights.map((n) => /* @__PURE__ */ e(C, { highlight: n, demoId: t.id, roundStartMs: h, onRenderQueued: c }, n.id)) })
    ] }),
    t.renders.length > 0 && /* @__PURE__ */ a(o, { className: "mb-6", children: [
      /* @__PURE__ */ a("div", { className: "text-xs font-bold uppercase tracking-widest text-slate-500 mb-3", children: [
        "Render Jobs (",
        t.renders.length,
        ")"
      ] }),
      /* @__PURE__ */ e("div", { className: "space-y-2", children: t.renders.map((n) => /* @__PURE__ */ e(D, { job: n }, n.id)) })
    ] }),
    x.length > 0 && /* @__PURE__ */ a(o, { className: "mb-6", children: [
      /* @__PURE__ */ a("div", { className: "text-xs font-bold uppercase tracking-widest text-slate-500 mb-3", children: [
        "Timeline (",
        x.length,
        " events)"
      ] }),
      /* @__PURE__ */ e(_, { events: x, roundStartMs: h })
    ] }),
    t.status === "analyzed" && /* @__PURE__ */ a(o, { children: [
      /* @__PURE__ */ e("div", { className: "text-xs font-bold uppercase tracking-widest text-slate-500 mb-3", children: "Database Cross-Reference" }),
      /* @__PURE__ */ e(M, { demoId: t.id })
    ] })
  ] });
}
export {
  A as default
};
