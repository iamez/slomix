import { jsx as t, jsxs as a, Fragment as O } from "react/jsx-runtime";
import { useState as w, useMemo as I, useEffect as L, useCallback as $, useRef as K } from "react";
import { u as g } from "./useQuery-C94yztTO.js";
import { P as V } from "./PageHeader-D4CVo02x.js";
import { G as D } from "./GlassPanel-S_ADyiYR.js";
import { G as y } from "./GlassCard-DKnnuJMt.js";
import { S as Y } from "./route-host-CUL1oI6Z.js";
const f = "/api", C = 512;
function M(s) {
  return s != null ? s.toLocaleString() : "--";
}
function j(s) {
  return s != null ? `${s.toFixed(0)}ms` : "--";
}
function S(s) {
  return s != null ? `${Math.round(s)}u` : "--";
}
function P(s) {
  return s != null ? `${s.toFixed(1)}%` : "--";
}
function Z(s) {
  const n = new URLSearchParams();
  return s.sessionDate && n.set("session_date", s.sessionDate), s.mapName && n.set("map_name", s.mapName), s.roundNumber != null && n.set("round_number", String(s.roundNumber)), s.roundStartUnix && n.set("round_start_unix", String(s.roundStartUnix)), n.toString();
}
function ee({ hotzones: s, mapImage: n, intensity: r = 1 }) {
  const o = K(null), d = K(null);
  L(() => {
    if (!n) {
      d.current = null;
      return;
    }
    const c = new Image();
    c.onload = () => {
      d.current = c, u();
    }, c.onerror = () => {
      d.current = null, u();
    }, c.src = n;
  }, [n]);
  const u = $(() => {
    const c = o.current;
    if (!c) return;
    const i = c.getContext("2d");
    if (!i) return;
    const h = c.width, v = c.height;
    if (i.clearRect(0, 0, h, v), d.current ? i.drawImage(d.current, 0, 0, h, v) : (i.fillStyle = "rgba(15, 23, 42, 0.9)", i.fillRect(0, 0, h, v)), !s.length) return;
    const N = Math.max(...s.map((l) => l.count), 1);
    for (const l of s) {
      const p = l.x / C * h, F = (1 - l.y / C) * v, R = Math.min(1, l.count / N * r * 0.8 + 0.1), k = Math.max(4, l.count / N * 12), _ = String(l.team ?? "").toUpperCase();
      _ === "AXIS" || _ === "1" ? i.fillStyle = `rgba(239, 68, 68, ${R})` : _ === "ALLIES" || _ === "2" ? i.fillStyle = `rgba(59, 130, 246, ${R})` : i.fillStyle = `rgba(56, 189, 248, ${R})`, i.beginPath(), i.arc(p, F, k, 0, Math.PI * 2), i.fill();
    }
  }, [s, r]);
  return L(() => {
    u();
  }, [u]), /* @__PURE__ */ t(
    "canvas",
    {
      ref: o,
      width: C,
      height: C,
      className: "w-full max-w-[512px] aspect-square rounded-xl border border-white/10"
    }
  );
}
function b({ title: s, rows: n, format: r }) {
  return /* @__PURE__ */ a(y, { children: [
    /* @__PURE__ */ t("div", { className: "text-[10px] font-bold uppercase tracking-widest text-slate-500 mb-2", children: s }),
    n.length ? /* @__PURE__ */ t("div", { className: "space-y-1", children: n.slice(0, 6).map((o, d) => /* @__PURE__ */ a("div", { className: "flex items-center justify-between text-xs", children: [
      /* @__PURE__ */ t("span", { className: "text-slate-200 truncate", children: o.name }),
      /* @__PURE__ */ t("span", { className: "text-cyan-400 font-mono text-[11px]", children: r(o) })
    ] }, d)) }) : /* @__PURE__ */ t("div", { className: "text-xs text-slate-500", children: "No data yet" })
  ] });
}
function te({ events: s }) {
  return s.length ? /* @__PURE__ */ a(y, { children: [
    /* @__PURE__ */ t("div", { className: "text-[10px] font-bold uppercase tracking-widest text-slate-500 mb-2", children: "Recent Engagements" }),
    /* @__PURE__ */ t("div", { className: "space-y-1 max-h-[300px] overflow-y-auto", children: s.map((n, r) => /* @__PURE__ */ a("div", { className: "flex items-center justify-between text-xs rounded-lg border border-white/5 bg-slate-950/30 px-2.5 py-1.5", children: [
      /* @__PURE__ */ a("div", { className: "flex items-center gap-1.5 min-w-0", children: [
        /* @__PURE__ */ t("span", { className: "text-blue-400 truncate", children: n.attacker_name }),
        /* @__PURE__ */ t("span", { className: "text-slate-600", children: "→" }),
        /* @__PURE__ */ t("span", { className: "text-rose-400 truncate", children: n.target_name })
      ] }),
      /* @__PURE__ */ a("div", { className: "flex items-center gap-3 text-[11px] text-slate-400 shrink-0", children: [
        /* @__PURE__ */ t("span", { children: S(n.distance) }),
        /* @__PURE__ */ t("span", { children: j(n.reaction_ms) }),
        n.weapon && /* @__PURE__ */ t("span", { className: "text-slate-500", children: n.weapon })
      ] })
    ] }, n.id ?? r)) })
  ] }) : null;
}
function se({ summary: s, events: n }) {
  return /* @__PURE__ */ a(y, { children: [
    /* @__PURE__ */ t("div", { className: "text-[10px] font-bold uppercase tracking-widest text-slate-500 mb-2", children: "Trade Kills" }),
    s && /* @__PURE__ */ a("div", { className: "grid grid-cols-3 gap-3 mb-3", children: [
      /* @__PURE__ */ a("div", { className: "text-center", children: [
        /* @__PURE__ */ t("div", { className: "text-[10px] text-slate-500", children: "Total" }),
        /* @__PURE__ */ t("div", { className: "text-lg font-bold text-white", children: M(s.total_trades) })
      ] }),
      /* @__PURE__ */ a("div", { className: "text-center", children: [
        /* @__PURE__ */ t("div", { className: "text-[10px] text-slate-500", children: "Avg Dist" }),
        /* @__PURE__ */ t("div", { className: "text-lg font-bold text-cyan-400", children: S(s.avg_trade_distance) })
      ] }),
      /* @__PURE__ */ a("div", { className: "text-center", children: [
        /* @__PURE__ */ t("div", { className: "text-[10px] text-slate-500", children: "Win Rate" }),
        /* @__PURE__ */ t("div", { className: "text-lg font-bold text-emerald-400", children: P(s.win_rate_pct) })
      ] })
    ] }),
    n.length > 0 && /* @__PURE__ */ t("div", { className: "space-y-1", children: n.slice(0, 8).map((r, o) => /* @__PURE__ */ a("div", { className: "flex items-center justify-between text-xs", children: [
      /* @__PURE__ */ a("span", { className: "text-slate-200", children: [
        r.killer,
        " ",
        "→",
        " ",
        r.victim
      ] }),
      /* @__PURE__ */ a("span", { className: "text-slate-400", children: [
        S(r.distance),
        " ",
        r.trade_ms != null ? `${r.trade_ms}ms` : ""
      ] })
    ] }, r.id ?? o)) }),
    !s && !n.length && /* @__PURE__ */ t("div", { className: "text-xs text-slate-500", children: "No trade data in this scope." })
  ] });
}
function oe() {
  const [s, n] = w(null), [r, o] = w(null), [d, u] = w(null), [c, i] = w(null), [h, v] = w(1), N = I(() => ({ sessionDate: s, mapName: r, roundNumber: d, roundStartUnix: c }), [s, r, d, c]), l = I(() => Z(N), [N]), { data: p, isLoading: F } = g({
    queryKey: ["proximity-scopes"],
    queryFn: () => fetch(`${f}/proximity/scopes?range_days=365`).then((e) => e.json()),
    staleTime: 6e4
  });
  L(() => {
    !s && p?.sessions?.length && n(p.scope?.session_date ?? p.sessions[0].session_date);
  }, [p, s]);
  const k = p?.sessions?.find((e) => e.session_date === s)?.maps ?? [], E = k.find((e) => e.map_name === r)?.rounds ?? [], { data: x } = g({
    queryKey: ["proximity-summary", l],
    queryFn: () => fetch(`${f}/proximity/summary?${l}`).then((e) => e.json()),
    enabled: !!s,
    staleTime: 3e4
  }), m = x?.ready === !0 || x?.status === "ok" || x?.status === "ready", { data: T } = g({
    queryKey: ["proximity-hotzones", l],
    queryFn: () => fetch(`${f}/proximity/hotzones?${l}`).then((e) => e.json()),
    enabled: !!s && m,
    staleTime: 3e4
  }), { data: U } = g({
    queryKey: ["proximity-events", l],
    queryFn: () => fetch(`${f}/proximity/events?${l}&limit=20`).then((e) => e.json()),
    enabled: !!s && m,
    staleTime: 3e4
  }), { data: q } = g({
    queryKey: ["proximity-movers", l],
    queryFn: () => fetch(`${f}/proximity/movers?${l}`).then((e) => e.json()),
    enabled: !!s && m,
    staleTime: 3e4
  }), { data: A } = g({
    queryKey: ["proximity-teamplay", l],
    queryFn: () => fetch(`${f}/proximity/teamplay?${l}&limit=6`).then((e) => e.json()),
    enabled: !!s && m,
    staleTime: 3e4
  }), { data: G } = g({
    queryKey: ["proximity-trades-summary", l],
    queryFn: () => fetch(`${f}/proximity/trades/summary?${l}`).then((e) => e.json()),
    enabled: !!s && m,
    staleTime: 3e4
  }), { data: H } = g({
    queryKey: ["proximity-trades-events", l],
    queryFn: () => fetch(`${f}/proximity/trades/events?${l}&limit=10`).then((e) => e.json()),
    enabled: !!s && m,
    staleTime: 3e4
  }), z = $((e) => {
    n(e || null), o(null), u(null), i(null);
  }, []), Q = $((e) => {
    o(e || null), u(null), i(null);
  }, []), W = $((e) => {
    if (!e) {
      u(null), i(null);
      return;
    }
    const [B, J] = e.split("|");
    u(parseInt(B, 10) || null), i(parseInt(J || "0", 10) || null);
  }, []), X = $(() => {
    n(p?.sessions?.[0]?.session_date ?? null), o(null), u(null), i(null);
  }, [p]);
  return F ? /* @__PURE__ */ t(Y, { variant: "card", count: 3 }) : /* @__PURE__ */ a(O, { children: [
    /* @__PURE__ */ t(V, { title: "Proximity Analytics", subtitle: "Combat engagement heatmaps and player movement analysis" }),
    /* @__PURE__ */ t(D, { children: /* @__PURE__ */ a("div", { className: "flex flex-wrap items-end gap-3", children: [
      /* @__PURE__ */ a("div", { children: [
        /* @__PURE__ */ t("label", { className: "text-[10px] text-slate-500 uppercase block mb-1", children: "Session" }),
        /* @__PURE__ */ t(
          "select",
          {
            value: s ?? "",
            onChange: (e) => z(e.target.value),
            className: "rounded-lg border border-white/10 bg-slate-950/70 px-3 py-1.5 text-xs text-white outline-none focus:border-cyan-500/50",
            children: (p?.sessions ?? []).map((e) => /* @__PURE__ */ t("option", { value: e.session_date, children: e.session_date }, e.session_date))
          }
        )
      ] }),
      /* @__PURE__ */ a("div", { children: [
        /* @__PURE__ */ t("label", { className: "text-[10px] text-slate-500 uppercase block mb-1", children: "Map" }),
        /* @__PURE__ */ a(
          "select",
          {
            value: r ?? "",
            onChange: (e) => Q(e.target.value),
            className: "rounded-lg border border-white/10 bg-slate-950/70 px-3 py-1.5 text-xs text-white outline-none focus:border-cyan-500/50",
            children: [
              /* @__PURE__ */ t("option", { value: "", children: "All Maps" }),
              k.map((e) => /* @__PURE__ */ t("option", { value: e.map_name, children: e.map_name }, e.map_name))
            ]
          }
        )
      ] }),
      /* @__PURE__ */ a("div", { children: [
        /* @__PURE__ */ t("label", { className: "text-[10px] text-slate-500 uppercase block mb-1", children: "Round" }),
        /* @__PURE__ */ a(
          "select",
          {
            value: d != null ? `${d}|${c ?? 0}` : "",
            onChange: (e) => W(e.target.value),
            className: "rounded-lg border border-white/10 bg-slate-950/70 px-3 py-1.5 text-xs text-white outline-none focus:border-cyan-500/50",
            children: [
              /* @__PURE__ */ t("option", { value: "", children: "All Rounds" }),
              E.map((e) => /* @__PURE__ */ a("option", { value: `${e.round_number}|${e.round_start_unix}`, children: [
                "Round ",
                e.round_number
              ] }, `${e.round_number}-${e.round_start_unix}`))
            ]
          }
        )
      ] }),
      /* @__PURE__ */ t(
        "button",
        {
          onClick: X,
          className: "px-3 py-1.5 rounded-lg text-xs font-bold border border-white/10 text-slate-300 hover:border-cyan-500/40 transition",
          children: "Reset"
        }
      )
    ] }) }),
    x && /* @__PURE__ */ a("div", { className: "grid grid-cols-2 md:grid-cols-4 gap-3 mt-4", children: [
      /* @__PURE__ */ a(y, { children: [
        /* @__PURE__ */ t("div", { className: "text-[10px] text-slate-500 uppercase", children: "Status" }),
        /* @__PURE__ */ t("div", { className: `text-sm font-bold ${m ? "text-emerald-400" : "text-amber-400"}`, children: m ? "Live" : "Prototype" })
      ] }),
      /* @__PURE__ */ a(y, { children: [
        /* @__PURE__ */ t("div", { className: "text-[10px] text-slate-500 uppercase", children: "Engagements" }),
        /* @__PURE__ */ t("div", { className: "text-lg font-bold text-white", children: M(x.total_engagements) })
      ] }),
      /* @__PURE__ */ a(y, { children: [
        /* @__PURE__ */ t("div", { className: "text-[10px] text-slate-500 uppercase", children: "Avg Distance" }),
        /* @__PURE__ */ t("div", { className: "text-lg font-bold text-cyan-400", children: S(x.avg_distance) })
      ] }),
      /* @__PURE__ */ a(y, { children: [
        /* @__PURE__ */ t("div", { className: "text-[10px] text-slate-500 uppercase", children: "Avg Reaction" }),
        /* @__PURE__ */ t("div", { className: "text-lg font-bold text-amber-400", children: j(x.avg_reaction_ms) })
      ] })
    ] }),
    !m && x?.message && /* @__PURE__ */ t("div", { className: "mt-4 rounded-xl border border-amber-500/30 bg-amber-500/10 px-4 py-3 text-sm text-amber-400", children: x.message }),
    m && /* @__PURE__ */ a("div", { className: "mt-6 grid grid-cols-1 lg:grid-cols-2 gap-6", children: [
      /* @__PURE__ */ t("div", { children: /* @__PURE__ */ a(D, { children: [
        /* @__PURE__ */ a("div", { className: "flex items-center justify-between mb-3", children: [
          /* @__PURE__ */ t("div", { className: "text-xs font-bold uppercase tracking-widest text-slate-400", children: "Engagement Heatmap" }),
          /* @__PURE__ */ a("div", { className: "flex items-center gap-2", children: [
            /* @__PURE__ */ t("span", { className: "text-[10px] text-slate-500", children: "Intensity" }),
            /* @__PURE__ */ t(
              "input",
              {
                type: "range",
                min: "0.6",
                max: "1.8",
                step: "0.1",
                value: h,
                onChange: (e) => v(parseFloat(e.target.value)),
                className: "w-20 accent-cyan-500"
              }
            ),
            /* @__PURE__ */ a("span", { className: "text-[10px] text-cyan-400 w-8", children: [
              h.toFixed(1),
              "x"
            ] })
          ] })
        ] }),
        /* @__PURE__ */ t(
          ee,
          {
            hotzones: T?.hotzones ?? [],
            mapImage: T?.image_path ?? null,
            intensity: h
          }
        ),
        /* @__PURE__ */ a("div", { className: "flex items-center gap-4 mt-2 text-[10px]", children: [
          /* @__PURE__ */ a("div", { className: "flex items-center gap-1", children: [
            /* @__PURE__ */ t("span", { className: "w-2.5 h-2.5 rounded-full bg-blue-500" }),
            "Allies"
          ] }),
          /* @__PURE__ */ a("div", { className: "flex items-center gap-1", children: [
            /* @__PURE__ */ t("span", { className: "w-2.5 h-2.5 rounded-full bg-rose-500" }),
            "Axis"
          ] })
        ] })
      ] }) }),
      /* @__PURE__ */ a("div", { className: "space-y-4", children: [
        /* @__PURE__ */ a("div", { className: "grid grid-cols-2 gap-3", children: [
          /* @__PURE__ */ t(
            b,
            {
              title: "Distance Leaders",
              rows: q?.distance ?? [],
              format: (e) => S(e.total_distance)
            }
          ),
          /* @__PURE__ */ t(
            b,
            {
              title: "Sprint Leaders",
              rows: q?.sprint ?? [],
              format: (e) => P(e.sprint_pct)
            }
          ),
          /* @__PURE__ */ t(
            b,
            {
              title: "Reaction Leaders",
              rows: q?.reaction ?? [],
              format: (e) => j(e.reaction_ms)
            }
          ),
          /* @__PURE__ */ t(
            b,
            {
              title: "Survival Leaders",
              rows: q?.survival ?? [],
              format: (e) => e.duration_ms != null ? `${(e.duration_ms / 1e3).toFixed(1)}s` : "--"
            }
          )
        ] }),
        /* @__PURE__ */ a("div", { className: "grid grid-cols-2 gap-3", children: [
          /* @__PURE__ */ t(
            b,
            {
              title: "Crossfire Kills",
              rows: A?.crossfire_kills ?? [],
              format: (e) => `${M(e.crossfire_kills)} (${P(e.kill_rate_pct)})`
            }
          ),
          /* @__PURE__ */ t(
            b,
            {
              title: "Team Sync",
              rows: A?.sync ?? [],
              format: (e) => j(e.avg_delay_ms)
            }
          )
        ] })
      ] })
    ] }),
    m && /* @__PURE__ */ a("div", { className: "grid grid-cols-1 lg:grid-cols-2 gap-6 mt-6", children: [
      /* @__PURE__ */ t(te, { events: U?.events ?? [] }),
      /* @__PURE__ */ t(se, { summary: G ?? null, events: H?.events ?? [] })
    ] })
  ] });
}
export {
  oe as default
};
