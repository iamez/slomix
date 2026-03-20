import { r as o, j as e, S as K } from "./route-host-Ba3v8uFM.js";
import { u as v } from "./useQuery-CHhIv7cp.js";
import { P as Z } from "./PageHeader-CQ7BTOQj.js";
import { G as M } from "./GlassPanel-C-uUmQaB.js";
import { G as j } from "./GlassCard-C53TzD-y.js";
import { C as ee, D as se } from "./DataTable-gbZQ6Kgl.js";
import { c as U } from "./createLucideIcon-BebMLfof.js";
import { S as te, T as ae } from "./hooks-CyQgvbI9.js";
const ne = [
  ["circle", { cx: "12", cy: "12", r: "10", key: "1mglay" }],
  ["path", { d: "M9.09 9a3 3 0 0 1 5.83 1c0 2-3 3-3 3", key: "1u773s" }],
  ["path", { d: "M12 17h.01", key: "p32p05" }]
], re = U("circle-question-mark", ne);
const ie = [
  ["circle", { cx: "12", cy: "12", r: "10", key: "1mglay" }],
  ["path", { d: "M12 16v-4", key: "1dtifu" }],
  ["path", { d: "M12 8h.01", key: "e9boi3" }]
], A = U("info", ie);
function N({ label: s, children: t, className: r }) {
  const [m, x] = o.useState(!1), i = o.useRef(null);
  return o.useEffect(() => {
    if (!m) return;
    function l(c) {
      i.current && !i.current.contains(c.target) && x(!1);
    }
    return document.addEventListener("mousedown", l), () => document.removeEventListener("mousedown", l);
  }, [m]), /* @__PURE__ */ e.jsxs("div", { ref: i, className: `relative inline-flex items-center ${r ?? ""}`, children: [
    /* @__PURE__ */ e.jsx(
      "button",
      {
        type: "button",
        onClick: () => x((l) => !l),
        className: "text-slate-500 hover:text-cyan-400 transition-colors focus:outline-none",
        "aria-label": s ? `Info: ${s}` : "More info",
        children: /* @__PURE__ */ e.jsx(re, { className: "w-3.5 h-3.5" })
      }
    ),
    m && /* @__PURE__ */ e.jsxs("div", { className: "absolute z-50 left-0 top-full mt-1.5 w-72 rounded-xl border border-white/10 bg-slate-800/95 backdrop-blur-lg p-3.5 shadow-xl shadow-black/40 text-xs text-slate-300 leading-relaxed", children: [
      s && /* @__PURE__ */ e.jsx("div", { className: "font-bold text-white text-[11px] mb-1.5", children: s }),
      t
    ] })
  ] });
}
const E = "proximity-intro-dismissed";
function le() {
  const [s, t] = o.useState(() => {
    try {
      return localStorage.getItem(E) === "1";
    } catch {
      return !1;
    }
  }), r = () => {
    t(!0);
    try {
      localStorage.setItem(E, "1");
    } catch {
    }
  }, m = () => {
    t(!1);
    try {
      localStorage.removeItem(E);
    } catch {
    }
  };
  return s ? /* @__PURE__ */ e.jsxs(
    "button",
    {
      onClick: m,
      className: "flex items-center gap-1.5 text-[11px] text-slate-500 hover:text-cyan-400 transition-colors mb-3",
      children: [
        /* @__PURE__ */ e.jsx(A, { className: "w-3.5 h-3.5" }),
        "How proximity tracking works"
      ]
    }
  ) : /* @__PURE__ */ e.jsx("div", { className: "rounded-2xl border border-blue-500/20 bg-blue-500/5 p-5 mb-4", children: /* @__PURE__ */ e.jsxs("div", { className: "flex items-start justify-between gap-4", children: [
    /* @__PURE__ */ e.jsxs("div", { className: "space-y-2 text-xs text-slate-300 leading-relaxed", children: [
      /* @__PURE__ */ e.jsxs("p", { className: "text-sm font-bold text-white flex items-center gap-2", children: [
        /* @__PURE__ */ e.jsx(A, { className: "w-4 h-4 text-blue-400 shrink-0" }),
        "How Proximity Tracking Works"
      ] }),
      /* @__PURE__ */ e.jsxs("p", { children: [
        "A ",
        /* @__PURE__ */ e.jsx("span", { className: "text-cyan-400", children: "Lua tracker" }),
        " running on the game server records every damage event, kill, and player position in real time. This raw data is parsed and stored in the database, then aggregated into the metrics you see below."
      ] }),
      /* @__PURE__ */ e.jsxs("p", { children: [
        /* @__PURE__ */ e.jsx("strong", { className: "text-white", children: "What's an engagement?" }),
        " A combat encounter that starts when a player deals ",
        ">",
        "1 HP damage. It ends when one player dies, escapes (moves 300+ units away for 5 seconds), or the 15-second timeout expires."
      ] }),
      /* @__PURE__ */ e.jsxs("p", { children: [
        /* @__PURE__ */ e.jsx("strong", { className: "text-white", children: "Distance units:" }),
        " ET:Legacy uses game units (u). Roughly",
        " ",
        /* @__PURE__ */ e.jsx("span", { className: "text-cyan-400", children: "300 units ≈ 5 meters" }),
        " (one sprint-second). Sprint speed is ~300 u/s."
      ] }),
      /* @__PURE__ */ e.jsxs("p", { children: [
        "Look for the ",
        /* @__PURE__ */ e.jsx("span", { className: "inline-flex items-center text-slate-400", children: /* @__PURE__ */ e.jsx(A, { className: "w-3 h-3 mx-0.5" }) }),
        " icons next to metrics for detailed explanations of what each number means and how it's measured."
      ] })
    ] }),
    /* @__PURE__ */ e.jsx(
      "button",
      {
        onClick: r,
        className: "shrink-0 text-slate-500 hover:text-white transition-colors",
        "aria-label": "Dismiss intro",
        children: /* @__PURE__ */ e.jsx(ee, { className: "w-5 h-5" })
      }
    )
  ] }) });
}
const u = {
  engagement: {
    label: "Engagement",
    oneLiner: "A tracked combat encounter between two players.",
    detail: "An engagement starts when a player deals >1 HP damage to an enemy. It ends when one player dies, escapes (moves 300+ game units away for 5 seconds), or the 15-second timeout expires.",
    howMeasured: "The Lua tracker on the game server monitors damage events in real time and groups them into engagements."
  },
  avg_duration: {
    label: "Avg Fight Duration",
    oneLiner: "Average length of each combat engagement in milliseconds.",
    detail: "Shorter fights mean faster eliminations. Longer fights may indicate evasive play or drawn-out duels. Typical ET fights last 800–3000 ms.",
    howMeasured: "Measured from the first damage event to the kill/escape/timeout that ends the engagement."
  },
  trade_kill: {
    label: "Trade Kill",
    oneLiner: "A revenge kill — your teammate avenges your death within 3 seconds.",
    detail: "When you die, a trade kill happens if a teammate kills your attacker within 3000 ms. High trade rates mean the team reacts quickly to losses and denies the enemy any advantage."
  },
  distance: {
    label: "Distance",
    oneLiner: "Distance between players in game units.",
    detail: "ET:Legacy uses its own distance unit. Roughly 300 game units ≈ 5 meters (one sprint-second). Close combat is <200u, medium range 200–600u, long range 600u+."
  }
}, q = {
  power: "Composite score combining engagement dominance, movement efficiency, crossfire participation, trade success, spawn timing, and reaction speed. Higher = more impactful player.",
  spawn: "Measures how well-timed your kills are relative to enemy respawn waves. 1.0 = killed right after respawn (maximum time denied), 0.0 = killed just before respawn (minimal impact).",
  crossfire: "Top duos creating crossfire angles — two teammates attacking the same enemy from 45°+ separation. Crossfire is extremely hard to defend against and marks strong team coordination.",
  trades: "Fastest and most prolific traders. A trade kill avenges a teammate’s death within 3 seconds. High trade counts mean the team never lets a death go unpunished.",
  reactions: "Quickest return fire after being hit. Measures raw reflexes — the time from taking damage to firing the first shot back. Also shows dodge speed (evasive movement) and support speed (teammate assistance).",
  survivors: "Highest escape rate from engagements. Players who survive by moving 300+ units from the attacker for 5 seconds. High escape rates signal exceptional movement and map awareness.",
  movement: "Speed and distance leaders. Average movement speed (u/s), sprint percentage, and total distance covered. ET sprint speed is ~300 u/s.",
  focus_fire: "Top targets of coordinated team fire. Focus score combines timing tightness (how simultaneously attackers deal damage) and DPS concentration into a 0–1 score. Higher = better-coordinated fire."
}, b = "/api", T = 512, H = [
  { key: "power", label: "Power Rating", unit: "pts", desc: "Composite 5-axis combat score" },
  { key: "spawn", label: "Spawn Timing", unit: "score 0–1", desc: "Kill efficiency vs respawn waves" },
  { key: "crossfire", label: "Crossfire", unit: "kills", desc: "Top crossfire duos (45°+ angle)" },
  { key: "trades", label: "Trade Kills", unit: "trades", desc: "Revenge kills within 3 seconds" },
  { key: "reactions", label: "Reactions", unit: "ms", desc: "Fastest return fire after being hit" },
  { key: "survivors", label: "Survivors", unit: "%", desc: "Escape rate from engagements" },
  { key: "movement", label: "Movement", unit: "u/s", desc: "Speed & distance (≈300u = 5m)" },
  { key: "focus_fire", label: "Focus Fire", unit: "score 0–1", desc: "Coordinated multi-attacker bursts" }
];
function oe(s, t) {
  switch (s) {
    case "power":
      return `${t.value}`;
    case "spawn":
      return `${t.value.toFixed(3)}`;
    case "crossfire":
      return `${t.value} kills`;
    case "trades":
      return `${t.value} trades`;
    case "reactions":
      return `${t.value}ms`;
    case "survivors":
      return `${t.value}%`;
    case "movement":
      return `${t.value} u/s`;
    case "focus_fire":
      return `${t.value.toFixed(3)}`;
    default:
      return String(t.value);
  }
}
function ce(s, t) {
  switch (s) {
    case "power": {
      const r = t.axes;
      return r ? `A:${r.aggression} W:${r.awareness} T:${r.teamplay} Ti:${r.timing} M:${r.mechanical}` : "";
    }
    case "spawn":
      return `${t.timed_kills ?? 0} kills, ${t.avg_denial_ms ?? 0}ms denial`;
    case "crossfire":
      return `${t.total ?? 0} opportunities, ${t.avg_delay_ms ?? 0}ms avg delay`;
    case "trades":
      return `avg ${t.avg_trade_ms ?? 0}ms`;
    case "reactions":
      return `dodge ${t.avg_dodge_ms ?? 0}ms, support ${t.avg_support_ms ?? 0}ms`;
    case "survivors":
      return `${t.escapes ?? 0}/${t.total ?? 0} engagements`;
    case "movement":
      return `sprint ${t.sprint_pct ?? 0}%, ${(t.total_distance ?? 0).toLocaleString()}u total`;
    case "focus_fire":
      return `${t.times_focused ?? 0}x focused, avg ${t.avg_attackers ?? 0} attackers, ${t.avg_damage ?? 0} dmg`;
    default:
      return "";
  }
}
function F(s) {
  return s != null ? s.toLocaleString() : "--";
}
function C(s) {
  return s != null ? `${s.toFixed(0)}ms` : "--";
}
function _(s) {
  return s != null ? `${Math.round(s)}u` : "--";
}
function P(s) {
  return s != null ? `${s.toFixed(1)}%` : "--";
}
function de(s) {
  const t = new URLSearchParams();
  return s.sessionDate && t.set("session_date", s.sessionDate), s.mapName && t.set("map_name", s.mapName), s.roundNumber != null && t.set("round_number", String(s.roundNumber)), s.roundStartUnix && t.set("round_start_unix", String(s.roundStartUnix)), t.toString();
}
function me({ hotzones: s, mapImage: t, intensity: r = 1 }) {
  const m = o.useRef(null), x = o.useRef(null);
  o.useEffect(() => {
    if (!t) {
      x.current = null;
      return;
    }
    const l = new Image();
    l.onload = () => {
      x.current = l, i();
    }, l.onerror = () => {
      x.current = null, i();
    }, l.src = t;
  }, [t]);
  const i = o.useCallback(() => {
    const l = m.current;
    if (!l) return;
    const c = l.getContext("2d");
    if (!c) return;
    const n = l.width, p = l.height;
    if (c.clearRect(0, 0, n, p), x.current ? c.drawImage(x.current, 0, 0, n, p) : (c.fillStyle = "rgba(15, 23, 42, 0.9)", c.fillRect(0, 0, n, p)), !s.length) return;
    const w = Math.max(...s.map((d) => d.count), 1);
    for (const d of s) {
      const g = d.x / T * n, R = (1 - d.y / T) * p, $ = Math.min(1, d.count / w * r * 0.8 + 0.1), S = Math.max(4, d.count / w * 12), k = String(d.team ?? "").toUpperCase();
      k === "AXIS" || k === "1" ? c.fillStyle = `rgba(239, 68, 68, ${$})` : k === "ALLIES" || k === "2" ? c.fillStyle = `rgba(59, 130, 246, ${$})` : c.fillStyle = `rgba(56, 189, 248, ${$})`, c.beginPath(), c.arc(g, R, S, 0, Math.PI * 2), c.fill();
    }
  }, [s, r]);
  return o.useEffect(() => {
    i();
  }, [i]), /* @__PURE__ */ e.jsx(
    "canvas",
    {
      ref: m,
      width: T,
      height: T,
      className: "w-full max-w-[512px] aspect-square rounded-xl border border-white/10"
    }
  );
}
function y({ title: s, rows: t, format: r, tip: m }) {
  return /* @__PURE__ */ e.jsxs(j, { children: [
    /* @__PURE__ */ e.jsxs("div", { className: "flex items-center gap-1 text-[10px] font-bold uppercase tracking-widest text-slate-500 mb-2", children: [
      s,
      m && /* @__PURE__ */ e.jsx(N, { children: m })
    ] }),
    t.length ? /* @__PURE__ */ e.jsx("div", { className: "space-y-1", children: t.map((x, i) => /* @__PURE__ */ e.jsxs("div", { className: "flex items-center justify-between text-xs", children: [
      /* @__PURE__ */ e.jsx("span", { className: "text-slate-200 truncate", children: x.name }),
      /* @__PURE__ */ e.jsx("span", { className: "text-cyan-400 font-mono text-[11px]", children: r(x) })
    ] }, i)) }) : /* @__PURE__ */ e.jsx("div", { className: "text-xs text-slate-500", children: "No data yet" })
  ] });
}
function xe({ events: s }) {
  return s.length ? /* @__PURE__ */ e.jsxs(j, { children: [
    /* @__PURE__ */ e.jsxs("div", { className: "flex items-center gap-1 text-[10px] font-bold uppercase tracking-widest text-slate-500 mb-2", children: [
      "Recent Engagements",
      /* @__PURE__ */ e.jsx(N, { label: "Engagement Events", children: /* @__PURE__ */ e.jsx("p", { children: "Individual combat encounters. Each row shows attacker → target with distance (game units, ~300u = 5m) and fight duration (ms)." }) })
    ] }),
    /* @__PURE__ */ e.jsx("div", { className: "space-y-1 max-h-[300px] overflow-y-auto", children: s.map((t, r) => /* @__PURE__ */ e.jsxs("div", { className: "flex items-center justify-between text-xs rounded-lg border border-white/5 bg-slate-950/30 px-2.5 py-1.5", children: [
      /* @__PURE__ */ e.jsxs("div", { className: "flex items-center gap-1.5 min-w-0", children: [
        /* @__PURE__ */ e.jsx("span", { className: "text-blue-400 truncate", children: t.attacker_name }),
        /* @__PURE__ */ e.jsx("span", { className: "text-slate-600", children: "→" }),
        /* @__PURE__ */ e.jsx("span", { className: "text-rose-400 truncate", children: t.target_name })
      ] }),
      /* @__PURE__ */ e.jsxs("div", { className: "flex items-center gap-3 text-[11px] text-slate-400 shrink-0", children: [
        /* @__PURE__ */ e.jsx("span", { title: "Distance (game units)", children: _(t.distance) }),
        /* @__PURE__ */ e.jsx("span", { title: "Fight duration (ms)", children: C(t.reaction_ms) }),
        t.weapon && /* @__PURE__ */ e.jsx("span", { className: "text-slate-500", children: t.weapon })
      ] })
    ] }, t.id ?? r)) })
  ] }) : null;
}
function ue({ summary: s, events: t }) {
  return /* @__PURE__ */ e.jsxs(j, { children: [
    /* @__PURE__ */ e.jsxs("div", { className: "flex items-center gap-1 text-[10px] font-bold uppercase tracking-widest text-slate-500 mb-2", children: [
      "Trade Kills",
      /* @__PURE__ */ e.jsxs(N, { label: u.trade_kill.label, children: [
        /* @__PURE__ */ e.jsx("p", { children: u.trade_kill.oneLiner }),
        /* @__PURE__ */ e.jsx("p", { className: "mt-1.5 text-slate-400", children: u.trade_kill.detail })
      ] })
    ] }),
    s && /* @__PURE__ */ e.jsxs("div", { className: "grid grid-cols-3 gap-3 mb-3", children: [
      /* @__PURE__ */ e.jsxs("div", { className: "text-center", children: [
        /* @__PURE__ */ e.jsx("div", { className: "text-[10px] text-slate-500", children: "Total" }),
        /* @__PURE__ */ e.jsx("div", { className: "text-lg font-bold text-white", children: F(s.total_trades) })
      ] }),
      /* @__PURE__ */ e.jsxs("div", { className: "text-center", children: [
        /* @__PURE__ */ e.jsxs("div", { className: "text-[10px] text-slate-500", children: [
          "Avg Dist ",
          /* @__PURE__ */ e.jsx("span", { className: "text-slate-600", children: "(u)" })
        ] }),
        /* @__PURE__ */ e.jsx("div", { className: "text-lg font-bold text-cyan-400", children: _(s.avg_trade_distance) })
      ] }),
      /* @__PURE__ */ e.jsxs("div", { className: "text-center", children: [
        /* @__PURE__ */ e.jsx("div", { className: "text-[10px] text-slate-500", children: "Win Rate" }),
        /* @__PURE__ */ e.jsx("div", { className: "text-lg font-bold text-emerald-400", children: P(s.win_rate_pct) })
      ] })
    ] }),
    t.length > 0 && /* @__PURE__ */ e.jsx("div", { className: "space-y-1", children: t.slice(0, 8).map((r, m) => /* @__PURE__ */ e.jsxs("div", { className: "flex items-center justify-between text-xs", children: [
      /* @__PURE__ */ e.jsxs("span", { className: "text-slate-200", children: [
        r.killer,
        " ",
        "→",
        " ",
        r.victim
      ] }),
      /* @__PURE__ */ e.jsxs("span", { className: "text-slate-400", children: [
        _(r.distance),
        " ",
        r.trade_ms != null ? `${r.trade_ms}ms` : ""
      ] })
    ] }, r.id ?? m)) }),
    !s && !t.length && /* @__PURE__ */ e.jsx("div", { className: "text-xs text-slate-500", children: "No trade data in this scope." })
  ] });
}
function pe({ sessionDate: s }) {
  const { data: t, isLoading: r } = te(s ?? void 0);
  if (r) return /* @__PURE__ */ e.jsx(K, { variant: "card", count: 1 });
  if (!t?.players?.length) return null;
  const m = ["kill_timing", "crossfire", "focus_fire", "trades", "survivability", "movement", "reactions"], x = {
    kill_timing: "Timing",
    crossfire: "XFire",
    focus_fire: "Focus",
    trades: "Trade",
    survivability: "Survive",
    movement: "Move",
    reactions: "React"
  };
  return /* @__PURE__ */ e.jsx("div", { className: "mt-8", children: /* @__PURE__ */ e.jsxs(M, { children: [
    /* @__PURE__ */ e.jsx("div", { className: "text-xs font-bold uppercase tracking-widest text-slate-400 mb-1", children: "Session Combat Score" }),
    /* @__PURE__ */ e.jsxs("div", { className: "text-[10px] text-slate-500 mb-4", children: [
      "Composite score (0-100) from 7 proximity categories for ",
      t.session_date
    ] }),
    /* @__PURE__ */ e.jsx("div", { className: "space-y-2", children: t.players.map((i, l) => {
      const c = Math.min(i.total_score, 100);
      return /* @__PURE__ */ e.jsxs("div", { className: "bg-slate-900/50 rounded-lg p-3 border border-white/5", children: [
        /* @__PURE__ */ e.jsxs("div", { className: "flex items-center justify-between mb-1.5", children: [
          /* @__PURE__ */ e.jsxs("div", { className: "flex items-center gap-2", children: [
            /* @__PURE__ */ e.jsxs("span", { className: `font-bold text-sm ${l < 3 ? "text-amber-400" : "text-slate-500"}`, children: [
              "#",
              l + 1
            ] }),
            /* @__PURE__ */ e.jsx("span", { className: "text-white font-medium text-sm truncate", children: i.name }),
            /* @__PURE__ */ e.jsxs("span", { className: "text-slate-600 text-[10px]", children: [
              i.engagement_count,
              " eng"
            ] })
          ] }),
          /* @__PURE__ */ e.jsx("span", { className: "text-cyan-400 font-mono font-bold text-lg", children: i.total_score.toFixed(1) })
        ] }),
        /* @__PURE__ */ e.jsx("div", { className: "w-full h-1.5 bg-slate-800 rounded-full overflow-hidden mb-1.5", children: /* @__PURE__ */ e.jsx(
          "div",
          {
            className: "h-full rounded-full bg-gradient-to-r from-cyan-500 to-teal-400",
            style: { width: `${c}%` }
          }
        ) }),
        /* @__PURE__ */ e.jsx("div", { className: "flex flex-wrap gap-x-3 gap-y-0.5 text-[10px] text-slate-500", children: m.map((n) => /* @__PURE__ */ e.jsxs("span", { title: i.categories[n]?.detail ?? "", children: [
          x[n],
          ": ",
          /* @__PURE__ */ e.jsx("span", { className: "text-slate-400", children: (i.categories[n]?.weighted ?? 0).toFixed(0) })
        ] }, n)) })
      ] }, i.guid);
    }) })
  ] }) });
}
function he() {
  const [s, t] = o.useState("power"), [r, m] = o.useState(30), { data: x, isLoading: i } = ae(s, r, 10), l = H.find((n) => n.key === s), c = o.useMemo(() => [
    {
      key: "rank",
      label: "#",
      className: "w-12 text-center",
      render: (n, p) => /* @__PURE__ */ e.jsxs("span", { className: `font-bold ${p < 3 ? "text-amber-400" : "text-slate-500"}`, children: [
        "#",
        p + 1
      ] })
    },
    {
      key: "name",
      label: "Player",
      render: (n) => /* @__PURE__ */ e.jsx("span", { className: "text-slate-200 font-medium truncate", children: s === "crossfire" ? `${n.name} + ${n.partner_name ?? "?"}` : n.name })
    },
    {
      key: "value",
      label: l?.label ?? "Value",
      sortable: !0,
      sortValue: (n) => n.value,
      className: "text-right",
      headerClassName: "text-right",
      render: (n) => /* @__PURE__ */ e.jsx("span", { className: "text-cyan-400 font-mono font-bold", children: oe(s, n) })
    },
    {
      key: "detail",
      label: "Detail",
      className: "hidden md:table-cell text-slate-500 text-[11px] max-w-[280px]",
      headerClassName: "hidden md:table-cell",
      render: (n) => /* @__PURE__ */ e.jsx("span", { className: "truncate block", children: ce(s, n) })
    }
  ], [s, l]);
  return /* @__PURE__ */ e.jsx("div", { className: "mt-8", children: /* @__PURE__ */ e.jsxs(M, { children: [
    /* @__PURE__ */ e.jsxs("div", { className: "flex items-center justify-between mb-4", children: [
      /* @__PURE__ */ e.jsxs("div", { children: [
        /* @__PURE__ */ e.jsx("div", { className: "text-xs font-bold uppercase tracking-widest text-slate-400", children: "Proximity Leaderboards" }),
        /* @__PURE__ */ e.jsx("div", { className: "text-[10px] text-slate-500 mt-0.5", children: l?.desc ?? "" })
      ] }),
      /* @__PURE__ */ e.jsxs(
        "select",
        {
          value: r,
          onChange: (n) => m(parseInt(n.target.value, 10)),
          className: "rounded-lg border border-white/10 bg-slate-950/70 px-2 py-1 text-xs text-white outline-none focus:border-cyan-500/50",
          children: [
            /* @__PURE__ */ e.jsx("option", { value: 7, children: "7 days" }),
            /* @__PURE__ */ e.jsx("option", { value: 30, children: "30 days" }),
            /* @__PURE__ */ e.jsx("option", { value: 90, children: "90 days" }),
            /* @__PURE__ */ e.jsx("option", { value: 365, children: "All time" })
          ]
        }
      )
    ] }),
    /* @__PURE__ */ e.jsx("div", { className: "flex flex-wrap gap-1.5 mb-2", children: H.map((n) => /* @__PURE__ */ e.jsx(
      "button",
      {
        onClick: () => t(n.key),
        className: `px-3 py-1.5 rounded-lg text-xs font-bold border transition ${s === n.key ? "border-cyan-500/50 bg-cyan-500/10 text-cyan-400" : "border-white/10 text-slate-400 hover:border-white/20 hover:text-slate-300"}`,
        children: n.label
      },
      n.key
    )) }),
    q[s] && /* @__PURE__ */ e.jsx("div", { className: "text-[10px] text-slate-500 leading-relaxed mb-4 max-w-2xl", children: q[s] }),
    i ? /* @__PURE__ */ e.jsx("div", { className: "space-y-2", children: Array.from({ length: 5 }).map((n, p) => /* @__PURE__ */ e.jsx("div", { className: "h-10 rounded-lg bg-slate-800/50 animate-pulse" }, p)) }) : /* @__PURE__ */ e.jsx(
      se,
      {
        columns: c,
        data: x?.entries ?? [],
        keyFn: (n) => n.guid + (n.partner_guid ?? ""),
        defaultSort: { key: "value", dir: "desc" },
        emptyMessage: "No data for this category in the selected time range."
      }
    )
  ] }) });
}
function ke() {
  const [s, t] = o.useState(null), [r, m] = o.useState(null), [x, i] = o.useState(null), [l, c] = o.useState(null), [n, p] = o.useState(1), w = o.useMemo(() => ({ sessionDate: s, mapName: r, roundNumber: x, roundStartUnix: l }), [s, r, x, l]), d = o.useMemo(() => de(w), [w]), { data: g, isLoading: R } = v({
    queryKey: ["proximity-scopes"],
    queryFn: () => fetch(`${b}/proximity/scopes?range_days=365`).then((a) => a.json()),
    staleTime: 6e4
  });
  o.useEffect(() => {
    !s && g?.sessions?.length && t(g.scope?.session_date ?? g.sessions[0].session_date);
  }, [g, s]);
  const S = g?.sessions?.find((a) => a.session_date === s)?.maps ?? [], G = S.find((a) => a.map_name === r)?.rounds ?? [], { data: f } = v({
    queryKey: ["proximity-summary", d],
    queryFn: () => fetch(`${b}/proximity/summary?${d}`).then((a) => a.json()),
    enabled: !!s,
    staleTime: 3e4
  }), h = f?.ready === !0 || f?.status === "ok" || f?.status === "ready", { data: D } = v({
    queryKey: ["proximity-hotzones", d],
    queryFn: () => fetch(`${b}/proximity/hotzones?${d}`).then((a) => a.json()),
    enabled: !!s && h,
    staleTime: 3e4
  }), { data: O } = v({
    queryKey: ["proximity-events", d],
    queryFn: () => fetch(`${b}/proximity/events?${d}&limit=20`).then((a) => a.json()),
    enabled: !!s && h,
    staleTime: 3e4
  }), { data: L } = v({
    queryKey: ["proximity-movers", d],
    queryFn: () => fetch(`${b}/proximity/movers?${d}&limit=50`).then((a) => a.json()),
    enabled: !!s && h,
    staleTime: 3e4
  }), { data: I } = v({
    queryKey: ["proximity-teamplay", d],
    queryFn: () => fetch(`${b}/proximity/teamplay?${d}&limit=50`).then((a) => a.json()),
    enabled: !!s && h,
    staleTime: 3e4
  }), { data: W } = v({
    queryKey: ["proximity-trades-summary", d],
    queryFn: () => fetch(`${b}/proximity/trades/summary?${d}`).then((a) => a.json()),
    enabled: !!s && h,
    staleTime: 3e4
  }), { data: z } = v({
    queryKey: ["proximity-trades-events", d],
    queryFn: () => fetch(`${b}/proximity/trades/events?${d}&limit=10`).then((a) => a.json()),
    enabled: !!s && h,
    staleTime: 3e4
  }), B = o.useCallback((a) => {
    t(a || null), m(null), i(null), c(null);
  }, []), Q = o.useCallback((a) => {
    m(a || null), i(null), c(null);
  }, []), V = o.useCallback((a) => {
    if (!a) {
      i(null), c(null);
      return;
    }
    const [Y, J] = a.split("|");
    i(parseInt(Y, 10) || null), c(parseInt(J || "0", 10) || null);
  }, []), X = o.useCallback(() => {
    t(g?.sessions?.[0]?.session_date ?? null), m(null), i(null), c(null);
  }, [g]);
  return R ? /* @__PURE__ */ e.jsx(K, { variant: "card", count: 3 }) : /* @__PURE__ */ e.jsxs("div", { className: "page-shell", children: [
    /* @__PURE__ */ e.jsx(
      Z,
      {
        title: "Proximity Analytics",
        subtitle: "Real-time combat telemetry from the game server — every fight, trade, and team play measured automatically.",
        eyebrow: "Advanced"
      }
    ),
    /* @__PURE__ */ e.jsx(le, {}),
    /* @__PURE__ */ e.jsxs(M, { children: [
      /* @__PURE__ */ e.jsxs("div", { className: "flex flex-wrap items-end gap-3", children: [
        /* @__PURE__ */ e.jsxs("div", { children: [
          /* @__PURE__ */ e.jsx("label", { className: "text-[10px] text-slate-500 uppercase block mb-1", children: "Session" }),
          /* @__PURE__ */ e.jsx(
            "select",
            {
              value: s ?? "",
              onChange: (a) => B(a.target.value),
              className: "rounded-lg border border-white/10 bg-slate-950/70 px-3 py-1.5 text-xs text-white outline-none focus:border-cyan-500/50",
              children: (g?.sessions ?? []).map((a) => /* @__PURE__ */ e.jsx("option", { value: a.session_date, children: a.session_date }, a.session_date))
            }
          )
        ] }),
        /* @__PURE__ */ e.jsxs("div", { children: [
          /* @__PURE__ */ e.jsx("label", { className: "text-[10px] text-slate-500 uppercase block mb-1", children: "Map" }),
          /* @__PURE__ */ e.jsxs(
            "select",
            {
              value: r ?? "",
              onChange: (a) => Q(a.target.value),
              className: "rounded-lg border border-white/10 bg-slate-950/70 px-3 py-1.5 text-xs text-white outline-none focus:border-cyan-500/50",
              children: [
                /* @__PURE__ */ e.jsx("option", { value: "", children: "All Maps" }),
                S.map((a) => /* @__PURE__ */ e.jsx("option", { value: a.map_name, children: a.map_name }, a.map_name))
              ]
            }
          )
        ] }),
        /* @__PURE__ */ e.jsxs("div", { children: [
          /* @__PURE__ */ e.jsx("label", { className: "text-[10px] text-slate-500 uppercase block mb-1", children: "Round" }),
          /* @__PURE__ */ e.jsxs(
            "select",
            {
              value: x != null ? `${x}|${l ?? 0}` : "",
              onChange: (a) => V(a.target.value),
              className: "rounded-lg border border-white/10 bg-slate-950/70 px-3 py-1.5 text-xs text-white outline-none focus:border-cyan-500/50",
              children: [
                /* @__PURE__ */ e.jsx("option", { value: "", children: "All Rounds" }),
                G.map((a) => /* @__PURE__ */ e.jsxs("option", { value: `${a.round_number}|${a.round_start_unix}`, children: [
                  "Round ",
                  a.round_number
                ] }, `${a.round_number}-${a.round_start_unix}`))
              ]
            }
          )
        ] }),
        /* @__PURE__ */ e.jsx(
          "button",
          {
            onClick: X,
            className: "px-3 py-1.5 rounded-lg text-xs font-bold border border-white/10 text-slate-300 hover:border-cyan-500/40 transition",
            children: "Reset"
          }
        )
      ] }),
      /* @__PURE__ */ e.jsx("div", { className: "text-[10px] text-slate-500 mt-2", children: "Filter by gaming session, map, or individual round. Each session is one continuous play period (60-minute gap = new session)." })
    ] }),
    f && /* @__PURE__ */ e.jsxs("div", { className: "grid grid-cols-2 md:grid-cols-4 gap-3 mt-4", children: [
      /* @__PURE__ */ e.jsxs(j, { children: [
        /* @__PURE__ */ e.jsx("div", { className: "text-[10px] text-slate-500 uppercase", children: "Status" }),
        /* @__PURE__ */ e.jsx("div", { className: `text-sm font-bold ${h ? "text-emerald-400" : "text-amber-400"}`, children: h ? "Live" : "Prototype" })
      ] }),
      /* @__PURE__ */ e.jsxs(j, { children: [
        /* @__PURE__ */ e.jsxs("div", { className: "flex items-center gap-1 text-[10px] text-slate-500 uppercase", children: [
          "Engagements",
          /* @__PURE__ */ e.jsxs(N, { label: u.engagement.label, children: [
            /* @__PURE__ */ e.jsx("p", { children: u.engagement.oneLiner }),
            /* @__PURE__ */ e.jsx("p", { className: "mt-1.5 text-slate-400", children: u.engagement.detail }),
            /* @__PURE__ */ e.jsx("p", { className: "mt-1.5 text-slate-500 text-[10px]", children: u.engagement.howMeasured })
          ] })
        ] }),
        /* @__PURE__ */ e.jsx("div", { className: "text-lg font-bold text-white", children: F(f.total_engagements) })
      ] }),
      /* @__PURE__ */ e.jsxs(j, { children: [
        /* @__PURE__ */ e.jsxs("div", { className: "flex items-center gap-1 text-[10px] text-slate-500 uppercase", children: [
          "Avg Distance ",
          /* @__PURE__ */ e.jsx("span", { className: "normal-case text-slate-600", children: "(u)" }),
          /* @__PURE__ */ e.jsxs(N, { label: u.distance.label, children: [
            /* @__PURE__ */ e.jsx("p", { children: u.distance.oneLiner }),
            /* @__PURE__ */ e.jsx("p", { className: "mt-1.5 text-slate-400", children: u.distance.detail })
          ] })
        ] }),
        /* @__PURE__ */ e.jsx("div", { className: "text-lg font-bold text-cyan-400", children: _(f.avg_distance) })
      ] }),
      /* @__PURE__ */ e.jsxs(j, { children: [
        /* @__PURE__ */ e.jsxs("div", { className: "flex items-center gap-1 text-[10px] text-slate-500 uppercase", children: [
          "Avg Fight Duration ",
          /* @__PURE__ */ e.jsx("span", { className: "normal-case text-slate-600", children: "(ms)" }),
          /* @__PURE__ */ e.jsxs(N, { label: u.avg_duration.label, children: [
            /* @__PURE__ */ e.jsx("p", { children: u.avg_duration.oneLiner }),
            /* @__PURE__ */ e.jsx("p", { className: "mt-1.5 text-slate-400", children: u.avg_duration.detail }),
            /* @__PURE__ */ e.jsx("p", { className: "mt-1.5 text-slate-500 text-[10px]", children: u.avg_duration.howMeasured })
          ] })
        ] }),
        /* @__PURE__ */ e.jsx("div", { className: "text-lg font-bold text-amber-400", children: C(f.avg_reaction_ms) })
      ] })
    ] }),
    !h && f?.message && /* @__PURE__ */ e.jsx("div", { className: "mt-4 rounded-xl border border-amber-500/30 bg-amber-500/10 px-4 py-3 text-sm text-amber-400", children: f.message }),
    h && /* @__PURE__ */ e.jsxs("div", { className: "mt-6 grid grid-cols-1 lg:grid-cols-2 gap-6", children: [
      /* @__PURE__ */ e.jsx("div", { children: /* @__PURE__ */ e.jsxs(M, { children: [
        /* @__PURE__ */ e.jsxs("div", { className: "flex items-center justify-between mb-3", children: [
          /* @__PURE__ */ e.jsx("div", { className: "text-xs font-bold uppercase tracking-widest text-slate-400", children: "Engagement Heatmap" }),
          /* @__PURE__ */ e.jsxs("div", { className: "flex items-center gap-2", children: [
            /* @__PURE__ */ e.jsx("span", { className: "text-[10px] text-slate-500", children: "Intensity" }),
            /* @__PURE__ */ e.jsx(
              "input",
              {
                type: "range",
                min: "0.6",
                max: "1.8",
                step: "0.1",
                value: n,
                onChange: (a) => p(parseFloat(a.target.value)),
                className: "w-20 accent-cyan-500"
              }
            ),
            /* @__PURE__ */ e.jsxs("span", { className: "text-[10px] text-cyan-400 w-8", children: [
              n.toFixed(1),
              "x"
            ] })
          ] })
        ] }),
        /* @__PURE__ */ e.jsx(
          me,
          {
            hotzones: D?.hotzones ?? [],
            mapImage: D?.image_path ?? null,
            intensity: n
          }
        ),
        /* @__PURE__ */ e.jsxs("div", { className: "flex items-center gap-4 mt-2 text-[10px]", children: [
          /* @__PURE__ */ e.jsxs("div", { className: "flex items-center gap-1", children: [
            /* @__PURE__ */ e.jsx("span", { className: "w-2.5 h-2.5 rounded-full bg-blue-500" }),
            "Allies"
          ] }),
          /* @__PURE__ */ e.jsxs("div", { className: "flex items-center gap-1", children: [
            /* @__PURE__ */ e.jsx("span", { className: "w-2.5 h-2.5 rounded-full bg-rose-500" }),
            "Axis"
          ] })
        ] })
      ] }) }),
      /* @__PURE__ */ e.jsxs("div", { className: "space-y-4", children: [
        /* @__PURE__ */ e.jsxs("div", { className: "grid grid-cols-2 gap-3", children: [
          /* @__PURE__ */ e.jsx(
            y,
            {
              title: "Distance Leaders",
              rows: L?.distance ?? [],
              format: (a) => _(a.total_distance),
              tip: "Total distance covered in game units (~300u = 5m). More distance = more active map movement."
            }
          ),
          /* @__PURE__ */ e.jsx(
            y,
            {
              title: "Sprint Leaders",
              rows: L?.sprint ?? [],
              format: (a) => P(a.sprint_pct),
              tip: "Percentage of time spent sprinting (~300 u/s). Higher sprint % = more aggressive positioning."
            }
          ),
          /* @__PURE__ */ e.jsx(
            y,
            {
              title: "Return Fire Leaders",
              rows: L?.reaction ?? [],
              format: (a) => C(a.reaction_ms),
              tip: "Fastest return fire — time (ms) to shoot back after being hit. Lower = faster reflexes."
            }
          ),
          /* @__PURE__ */ e.jsx(
            y,
            {
              title: "Survival Leaders",
              rows: L?.survival ?? [],
              format: (a) => a.duration_ms != null ? `${(a.duration_ms / 1e3).toFixed(1)}s` : "--",
              tip: "Players who survived longest in engagements. Escape = moved 300+ units from attacker for 5 seconds."
            }
          )
        ] }),
        /* @__PURE__ */ e.jsxs("div", { className: "grid grid-cols-2 gap-3", children: [
          /* @__PURE__ */ e.jsx(
            y,
            {
              title: "Crossfire Kills",
              rows: I?.crossfire_kills ?? [],
              format: (a) => `${F(a.crossfire_kills)} (${P(a.kill_rate_pct)})`,
              tip: "Kills involving crossfire — 2+ teammates attacking the same enemy from 45°+ angular separation within 2000 units."
            }
          ),
          /* @__PURE__ */ e.jsx(
            y,
            {
              title: "Team Sync",
              rows: I?.sync ?? [],
              format: (a) => C(a.avg_delay_ms),
              tip: "Average delay (ms) between teammates engaging the same target. Lower = more synchronized attacks."
            }
          )
        ] })
      ] })
    ] }),
    h && /* @__PURE__ */ e.jsxs("div", { className: "grid grid-cols-1 lg:grid-cols-2 gap-6 mt-6", children: [
      /* @__PURE__ */ e.jsx(xe, { events: O?.events ?? [] }),
      /* @__PURE__ */ e.jsx(ue, { summary: W ?? null, events: z?.events ?? [] })
    ] }),
    /* @__PURE__ */ e.jsx(pe, { sessionDate: s }),
    /* @__PURE__ */ e.jsx(he, {})
  ] });
}
export {
  ke as default
};
