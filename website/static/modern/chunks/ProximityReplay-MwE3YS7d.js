import { r as u, j as e, S as R } from "./route-host-Ba3v8uFM.js";
import { u as _ } from "./useQuery-CHhIv7cp.js";
import { P as y } from "./PageHeader-CQ7BTOQj.js";
import { G as j } from "./GlassPanel-C-uUmQaB.js";
import { G as b } from "./GlassCard-C53TzD-y.js";
import { n as k } from "./navigation-BDd1HkpE.js";
const w = "/api";
function f(t) {
  const s = Math.floor(t / 1e3), r = Math.floor(s / 60), l = s % 60;
  return `${r}:${l.toString().padStart(2, "0")}`;
}
function S(t) {
  return t != null ? t.toLocaleString() : "--";
}
const $ = {
  engagement: "#ef4444",
  // red
  trade_kill: "#3b82f6",
  // blue
  team_push: "#22c55e",
  // green
  spawn_timing_kill: "#eab308",
  // yellow
  crossfire: "#a855f7"
  // purple
}, T = {
  engagement: "Kill",
  trade_kill: "Trade Kill",
  team_push: "Team Push",
  spawn_timing_kill: "Spawn Kill",
  crossfire: "Crossfire"
};
function v(t) {
  return $[t] ?? "#64748b";
}
function N(t) {
  return T[t] ?? t;
}
function E({
  events: t,
  durationMs: s,
  currentTime: r,
  onSeek: l
}) {
  const d = u.useRef(null), i = u.useCallback(
    (a) => {
      const m = d.current?.getBoundingClientRect();
      if (!m || s <= 0) return;
      const c = Math.max(0, Math.min(1, (a.clientX - m.left) / m.width));
      l(c * s);
    },
    [s, l]
  ), x = s > 0 ? r / s * 100 : 0;
  return /* @__PURE__ */ e.jsxs(j, { children: [
    /* @__PURE__ */ e.jsxs("div", { className: "flex items-center justify-between mb-2", children: [
      /* @__PURE__ */ e.jsx("div", { className: "text-xs font-bold uppercase tracking-widest text-slate-400", children: "Round Timeline" }),
      /* @__PURE__ */ e.jsxs("div", { className: "text-xs text-slate-500 font-mono", children: [
        f(r),
        " / ",
        f(s)
      ] })
    ] }),
    /* @__PURE__ */ e.jsxs(
      "div",
      {
        ref: d,
        className: "relative h-10 rounded-lg bg-slate-900/80 border border-white/10 cursor-crosshair select-none overflow-hidden",
        onClick: i,
        children: [
          t.map((a, m) => {
            const c = s > 0 ? a.time / s * 100 : 0, h = v(a.type);
            if (a.type === "team_push" && a.duration_ms) {
              const o = a.duration_ms / s * 100;
              return /* @__PURE__ */ e.jsx(
                "div",
                {
                  className: "absolute top-1/2 -translate-y-1/2 h-4 rounded-sm opacity-60",
                  style: {
                    left: `${c}%`,
                    width: `${Math.max(o, 0.5)}%`,
                    backgroundColor: h
                  },
                  title: `${N(a.type)} @ ${f(a.time)}`
                },
                m
              );
            }
            return /* @__PURE__ */ e.jsx(
              "div",
              {
                className: "absolute top-1/2 -translate-y-1/2 w-2 h-2 rounded-full",
                style: {
                  left: `${c}%`,
                  backgroundColor: h,
                  transform: "translate(-50%, -50%)",
                  boxShadow: `0 0 4px ${h}`
                },
                title: `${N(a.type)} @ ${f(a.time)}`
              },
              m
            );
          }),
          /* @__PURE__ */ e.jsx(
            "div",
            {
              className: "absolute top-0 bottom-0 w-0.5 bg-white/80 pointer-events-none",
              style: { left: `${x}%` }
            }
          )
        ]
      }
    ),
    /* @__PURE__ */ e.jsx("div", { className: "flex flex-wrap items-center gap-4 mt-2 text-[10px]", children: Object.entries($).map(([a, m]) => /* @__PURE__ */ e.jsxs("div", { className: "flex items-center gap-1", children: [
      /* @__PURE__ */ e.jsx("span", { className: "w-2.5 h-2.5 rounded-full", style: { backgroundColor: m } }),
      /* @__PURE__ */ e.jsx("span", { className: "text-slate-400", children: N(a) })
    ] }, a)) })
  ] });
}
function K({ event: t, isActive: s }) {
  const r = v(t.type);
  let l = "";
  switch (t.type) {
    case "engagement":
      l = `${t.attacker_name ?? "?"} → ${t.victim_name ?? "?"}`, t.damage && (l += ` (${t.damage} dmg`), t.weapon && (l += `, ${t.weapon}`), (t.damage || t.weapon) && (l += ")");
      break;
    case "trade_kill":
      l = `${t.trader_name ?? t.attacker_name ?? "?"} avenged ${t.avenged_name ?? t.victim_name ?? "?"}`, t.delta_ms != null && (l += ` (+${t.delta_ms}ms)`);
      break;
    case "team_push":
      l = `${t.team ?? "TEAM"} push`, t.quality != null && (l += ` (quality: ${t.quality.toFixed(1)}`), t.alignment != null && (l += `, align: ${t.alignment.toFixed(1)}`), t.participants != null && (l += `, ${t.participants} players`), t.quality != null && (l += ")");
      break;
    case "spawn_timing_kill":
      l = `${t.attacker_name ?? "?"} → ${t.victim_name ?? "?"}`, t.score != null && (l += ` (score: ${t.score.toFixed(1)})`);
      break;
    case "crossfire":
      l = `${t.attacker_name ?? "?"} → ${t.victim_name ?? "?"}`, t.distance != null && (l += ` (${Math.round(t.distance)}u)`);
      break;
    default:
      l = `${t.attacker_name ?? ""} ${t.victim_name ? "→ " + t.victim_name : ""}`.trim() || t.type;
  }
  return /* @__PURE__ */ e.jsxs(
    "div",
    {
      className: `flex items-center gap-3 text-xs rounded-lg border px-3 py-2 transition-all ${s ? "border-white/20 bg-white/[0.06]" : "border-white/5 bg-slate-950/30"}`,
      children: [
        /* @__PURE__ */ e.jsx("span", { className: "font-mono text-slate-500 w-12 shrink-0 text-right", children: f(t.time) }),
        /* @__PURE__ */ e.jsx("span", { className: "w-2 h-2 rounded-full shrink-0", style: { backgroundColor: r } }),
        /* @__PURE__ */ e.jsx(
          "span",
          {
            className: "text-[10px] uppercase font-bold tracking-wider w-20 shrink-0",
            style: { color: r },
            children: N(t.type)
          }
        ),
        /* @__PURE__ */ e.jsx("span", { className: "text-slate-200 truncate", children: l })
      ]
    }
  );
}
function P({ events: t }) {
  const s = u.useMemo(() => {
    let l = 0, d = 0, i = 0, x = 0, a = 0, m = 0;
    for (const c of t)
      switch (c.type) {
        case "engagement":
          c.outcome === "killed" || c.outcome === "kill" ? l++ : c.outcome === "escaped" || c.outcome === "escape" ? d++ : l++;
          break;
        case "trade_kill":
          x++;
          break;
        case "crossfire":
          i++;
          break;
        case "team_push":
          a++;
          break;
        case "spawn_timing_kill":
          m++;
          break;
      }
    return { kills: l, escapes: d, crossfires: i, tradeKills: x, pushes: a, spawnKills: m };
  }, [t]), r = [
    { label: "Total Kills", value: s.kills, color: "text-rose-400" },
    { label: "Escapes", value: s.escapes, color: "text-emerald-400" },
    { label: "Crossfires", value: s.crossfires, color: "text-purple-400" },
    { label: "Trade Kills", value: s.tradeKills, color: "text-blue-400" },
    { label: "Team Pushes", value: s.pushes, color: "text-green-400" },
    { label: "Spawn Kills", value: s.spawnKills, color: "text-yellow-400" }
  ];
  return /* @__PURE__ */ e.jsx("div", { className: "grid grid-cols-3 md:grid-cols-6 gap-3", children: r.map((l) => /* @__PURE__ */ e.jsxs(b, { className: "text-center", children: [
    /* @__PURE__ */ e.jsx("div", { className: "text-[10px] text-slate-500 uppercase", children: l.label }),
    /* @__PURE__ */ e.jsx("div", { className: `text-lg font-bold ${l.color}`, children: S(l.value) })
  ] }, l.label)) });
}
function L({ events: t }) {
  const { axisKills: s, alliesKills: r } = u.useMemo(() => {
    let d = 0, i = 0;
    for (const x of t) {
      if (x.type !== "engagement" && x.type !== "spawn_timing_kill" && x.type !== "crossfire") continue;
      const a = (x.attacker_team ?? "").toUpperCase();
      a === "AXIS" || a === "1" ? d++ : (a === "ALLIES" || a === "2") && i++;
    }
    return { axisKills: d, alliesKills: i };
  }, [t]), l = s + r || 1;
  return /* @__PURE__ */ e.jsxs(j, { children: [
    /* @__PURE__ */ e.jsx("div", { className: "text-xs font-bold uppercase tracking-widest text-slate-400 mb-3", children: "Team Summary" }),
    /* @__PURE__ */ e.jsxs("div", { className: "flex items-center gap-4", children: [
      /* @__PURE__ */ e.jsxs("div", { className: "text-center flex-1", children: [
        /* @__PURE__ */ e.jsx("div", { className: "text-[10px] text-slate-500 uppercase mb-1", children: "Axis" }),
        /* @__PURE__ */ e.jsx("div", { className: "text-2xl font-bold text-rose-400", children: s })
      ] }),
      /* @__PURE__ */ e.jsxs("div", { className: "flex-[2] h-4 rounded-full overflow-hidden bg-slate-800 flex", children: [
        /* @__PURE__ */ e.jsx(
          "div",
          {
            className: "h-full bg-rose-500 transition-all",
            style: { width: `${s / l * 100}%` }
          }
        ),
        /* @__PURE__ */ e.jsx(
          "div",
          {
            className: "h-full bg-blue-500 transition-all",
            style: { width: `${r / l * 100}%` }
          }
        )
      ] }),
      /* @__PURE__ */ e.jsxs("div", { className: "text-center flex-1", children: [
        /* @__PURE__ */ e.jsx("div", { className: "text-[10px] text-slate-500 uppercase mb-1", children: "Allies" }),
        /* @__PURE__ */ e.jsx("div", { className: "text-2xl font-bold text-blue-400", children: r })
      ] })
    ] })
  ] });
}
function G({ params: t }) {
  const s = t?.roundId ? parseInt(t.roundId, 10) : null, [r, l] = u.useState(0), d = u.useRef(null), {
    data: i,
    isLoading: x,
    error: a
  } = _({
    queryKey: ["proximity-round-timeline", s],
    queryFn: () => fetch(`${w}/proximity/round/${s}/timeline`).then((n) => n.json()),
    enabled: s !== null && s > 0,
    staleTime: 3e5
  }), { data: m } = _({
    queryKey: ["proximity-round-tracks", s],
    queryFn: () => fetch(`${w}/proximity/round/${s}/tracks`).then((n) => n.json()),
    enabled: s !== null && s > 0,
    staleTime: 3e5
  }), c = i?.events ?? [], h = i?.duration_ms ?? 0, o = u.useMemo(
    () => [...c].sort((n, p) => n.time - p.time),
    [c]
  ), g = u.useMemo(() => {
    if (!o.length) return -1;
    let n = -1;
    for (let p = 0; p < o.length && o[p].time <= r + 500; p++)
      n = p;
    return n;
  }, [o, r]);
  u.useEffect(() => {
    if (g < 0 || !d.current) return;
    const n = d.current.children[g];
    n && n.scrollIntoView({ behavior: "smooth", block: "nearest" });
  }, [g]);
  const C = u.useCallback((n) => {
    l(Math.max(0, n));
  }, []);
  return s === null || s <= 0 ? /* @__PURE__ */ e.jsxs(e.Fragment, { children: [
    /* @__PURE__ */ e.jsx(y, { title: "Round Replay", subtitle: "No round selected" }),
    /* @__PURE__ */ e.jsx(j, { children: /* @__PURE__ */ e.jsxs("div", { className: "text-center py-12 text-slate-400", children: [
      /* @__PURE__ */ e.jsx("p", { className: "text-lg mb-2", children: "No round ID specified." }),
      /* @__PURE__ */ e.jsx(
        "button",
        {
          onClick: () => k("#/proximity"),
          className: "text-cyan-400 hover:text-cyan-300 underline text-sm",
          children: "Back to Proximity Analytics"
        }
      )
    ] }) })
  ] }) : x ? /* @__PURE__ */ e.jsxs(e.Fragment, { children: [
    /* @__PURE__ */ e.jsx(y, { title: "Round Replay", subtitle: "Loading timeline..." }),
    /* @__PURE__ */ e.jsx(R, { variant: "card", count: 4 })
  ] }) : a || !i ? /* @__PURE__ */ e.jsxs(e.Fragment, { children: [
    /* @__PURE__ */ e.jsx(y, { title: "Round Replay", subtitle: "Error loading round data" }),
    /* @__PURE__ */ e.jsx(j, { children: /* @__PURE__ */ e.jsxs("div", { className: "text-center py-12 text-slate-400", children: [
      /* @__PURE__ */ e.jsxs("p", { className: "text-lg mb-2", children: [
        "Failed to load timeline for round ",
        s,
        "."
      ] }),
      /* @__PURE__ */ e.jsx("p", { className: "text-sm text-slate-500 mb-4", children: a instanceof Error ? a.message : "The round may not have proximity data." }),
      /* @__PURE__ */ e.jsx(
        "button",
        {
          onClick: () => k("#/proximity"),
          className: "text-cyan-400 hover:text-cyan-300 underline text-sm",
          children: "Back to Proximity Analytics"
        }
      )
    ] }) })
  ] }) : /* @__PURE__ */ e.jsxs(e.Fragment, { children: [
    /* @__PURE__ */ e.jsx(
      y,
      {
        title: `${i.map_name ?? "Unknown Map"} - Round ${i.round_number ?? "?"}`,
        subtitle: i.round_date ? `${i.round_date} · ${o.length} events · ${f(h)} duration` : `Round ${s}`,
        children: /* @__PURE__ */ e.jsxs(
          "button",
          {
            onClick: () => k("#/proximity"),
            className: "px-3 py-1.5 rounded-lg text-xs font-bold border border-white/10 text-slate-300 hover:border-cyan-500/40 transition flex items-center gap-1.5",
            children: [
              /* @__PURE__ */ e.jsx("span", { children: "←" }),
              " Proximity"
            ]
          }
        )
      }
    ),
    /* @__PURE__ */ e.jsx(
      E,
      {
        events: o,
        durationMs: h,
        currentTime: r,
        onSeek: C
      }
    ),
    /* @__PURE__ */ e.jsx("div", { className: "mt-4", children: /* @__PURE__ */ e.jsx(P, { events: o }) }),
    /* @__PURE__ */ e.jsxs("div", { className: "mt-6 grid grid-cols-1 lg:grid-cols-3 gap-6", children: [
      /* @__PURE__ */ e.jsx("div", { className: "lg:col-span-2", children: /* @__PURE__ */ e.jsxs(j, { children: [
        /* @__PURE__ */ e.jsxs("div", { className: "flex items-center justify-between mb-3", children: [
          /* @__PURE__ */ e.jsxs("div", { className: "text-xs font-bold uppercase tracking-widest text-slate-400", children: [
            "Events (",
            o.length,
            ")"
          ] }),
          /* @__PURE__ */ e.jsx("div", { className: "text-[10px] text-slate-500", children: "Click timeline to jump to a time" })
        ] }),
        /* @__PURE__ */ e.jsx(
          "div",
          {
            ref: d,
            className: "space-y-1 max-h-[500px] overflow-y-auto pr-1 scrollbar-thin scrollbar-thumb-slate-700",
            children: o.length === 0 ? /* @__PURE__ */ e.jsx("div", { className: "text-xs text-slate-500 text-center py-8", children: "No events recorded for this round." }) : o.map((n, p) => /* @__PURE__ */ e.jsx(
              "div",
              {
                onClick: () => l(n.time),
                className: "cursor-pointer",
                children: /* @__PURE__ */ e.jsx(K, { event: n, isActive: p === g })
              },
              n.id ?? p
            ))
          }
        )
      ] }) }),
      /* @__PURE__ */ e.jsxs("div", { className: "space-y-4", children: [
        /* @__PURE__ */ e.jsx(L, { events: o }),
        /* @__PURE__ */ e.jsxs(b, { children: [
          /* @__PURE__ */ e.jsx("div", { className: "text-[10px] text-slate-500 uppercase mb-1", children: "Round Duration" }),
          /* @__PURE__ */ e.jsx("div", { className: "text-lg font-bold text-white", children: f(h) })
        ] }),
        /* @__PURE__ */ e.jsxs(b, { children: [
          /* @__PURE__ */ e.jsx("div", { className: "text-[10px] text-slate-500 uppercase mb-1", children: "Map" }),
          /* @__PURE__ */ e.jsx("div", { className: "text-lg font-bold text-cyan-400", children: i.map_name ?? "--" })
        ] }),
        /* @__PURE__ */ e.jsxs(b, { children: [
          /* @__PURE__ */ e.jsx("div", { className: "text-[10px] text-slate-500 uppercase mb-1", children: "Round" }),
          /* @__PURE__ */ e.jsxs("div", { className: "text-lg font-bold text-white", children: [
            "#",
            i.round_number ?? "--"
          ] })
        ] }),
        i.round_date && /* @__PURE__ */ e.jsxs(b, { children: [
          /* @__PURE__ */ e.jsx("div", { className: "text-[10px] text-slate-500 uppercase mb-1", children: "Date" }),
          /* @__PURE__ */ e.jsx("div", { className: "text-sm font-bold text-slate-200", children: i.round_date })
        ] })
      ] })
    ] })
  ] });
}
export {
  G as default
};
