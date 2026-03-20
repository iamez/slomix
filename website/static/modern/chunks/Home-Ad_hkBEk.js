import { j as e, S as v, r as y } from "./route-host-Ba3v8uFM.js";
import { C as w } from "./Chart-DkWq45SK.js";
import { G as u } from "./GlassCard-C53TzD-y.js";
import { G as x } from "./GlassPanel-C-uUmQaB.js";
import { P as C } from "./PlayerLookup-CRlHDLm4.js";
import { u as N, a as S, b as A, c as $, d as L, e as M } from "./hooks-CyQgvbI9.js";
import { f as o } from "./format-BM7Gaq4w.js";
import { n as r, a as P } from "./navigation-BDd1HkpE.js";
import { A as k } from "./arrow-right-DXUYYllJ.js";
import { U as _ } from "./users-Blp4mgkM.js";
import { C as T, a as D } from "./chevron-right-DaoXilIT.js";
import { R } from "./radar-CtjAN0qD.js";
function b(s) {
  return (s || "Unknown").replace(/^maps[\\/]/, "").replace(/\.(bsp|pk3|arena)$/i, "").replace(/_/g, " ");
}
function O(s) {
  if (!s || s <= 0) return "--";
  const t = Math.floor(s / 60), a = Math.floor(t / 60), l = t % 60;
  return a > 0 ? `${a}h ${l}m` : `${t}m`;
}
function F(s, t) {
  return s > t ? "Allies edge" : t > s ? "Axis edge" : "Dead even";
}
function g(s) {
  return s ? s.session_id ? `#/session-detail/${s.session_id}` : `#/session-detail/date/${encodeURIComponent(s.date)}` : "#/sessions2";
}
function G() {
  const { data: s, isLoading: t } = N(), { data: a } = S();
  if (t)
    return /* @__PURE__ */ e.jsx(v, { variant: "card", count: 1, className: "grid-cols-1" });
  if (!s)
    return /* @__PURE__ */ e.jsxs(x, { className: "p-8 md:p-10", children: [
      /* @__PURE__ */ e.jsx("div", { className: "section-kicker mb-2", children: "Tonight / Start Here" }),
      /* @__PURE__ */ e.jsx("div", { className: "text-4xl font-black text-white", children: "No session available yet" }),
      /* @__PURE__ */ e.jsx("p", { className: "mt-3 max-w-2xl text-slate-400", children: "The session-first shell is ready. Once the next gaming session lands, this page becomes the fastest route into stats." })
    ] });
  const l = s.maps_played[0] || "", d = `${s.allies_wins ?? 0} : ${s.axis_wins ?? 0}`;
  return /* @__PURE__ */ e.jsx(x, { className: "overflow-hidden p-0", children: /* @__PURE__ */ e.jsxs("div", { className: "grid gap-0 lg:grid-cols-[1.45fr_0.95fr]", children: [
    /* @__PURE__ */ e.jsxs("div", { className: "relative overflow-hidden p-7 md:p-8", children: [
      /* @__PURE__ */ e.jsx("div", { className: "absolute inset-0 bg-[radial-gradient(circle_at_top_left,rgba(56,189,248,0.16),transparent_36%),radial-gradient(circle_at_bottom_left,rgba(168,85,247,0.14),transparent_28%)]" }),
      /* @__PURE__ */ e.jsxs("div", { className: "relative", children: [
        /* @__PURE__ */ e.jsxs("div", { className: "mb-3 flex flex-wrap items-center gap-2", children: [
          /* @__PURE__ */ e.jsx("span", { className: "rounded-full border border-cyan-400/20 bg-cyan-400/10 px-3 py-1 text-[11px] font-bold uppercase tracking-[0.2em] text-cyan-200", children: "Tonight / Start Here" }),
          a && /* @__PURE__ */ e.jsx("span", { className: "rounded-full border border-white/10 bg-white/5 px-3 py-1 text-[11px] font-bold text-slate-300", children: a.name })
        ] }),
        /* @__PURE__ */ e.jsxs("div", { className: "max-w-3xl", children: [
          /* @__PURE__ */ e.jsx("h1", { className: "text-4xl font-black tracking-tight text-white md:text-6xl", children: "Latest session, first." }),
          /* @__PURE__ */ e.jsx("p", { className: "mt-4 text-base leading-7 text-slate-300 md:text-lg", children: "Most visitors arrive to check what just happened. Put the last session, tonight's roster, and personal lookup in front of everything else." })
        ] }),
        /* @__PURE__ */ e.jsxs("div", { className: "mt-6 flex flex-wrap items-center gap-2", children: [
          /* @__PURE__ */ e.jsx("span", { className: "metric-chip", children: s.formatted_date || s.date }),
          /* @__PURE__ */ e.jsxs("span", { className: "metric-chip", children: [
            d,
            " score"
          ] }),
          /* @__PURE__ */ e.jsxs("span", { className: "metric-chip", children: [
            s.round_count,
            " rounds"
          ] }),
          /* @__PURE__ */ e.jsxs("span", { className: "metric-chip", children: [
            s.player_count,
            " players"
          ] }),
          l && /* @__PURE__ */ e.jsx("span", { className: "metric-chip", children: b(l) })
        ] }),
        /* @__PURE__ */ e.jsxs("div", { className: "mt-7 flex flex-wrap gap-3", children: [
          /* @__PURE__ */ e.jsxs(
            "button",
            {
              type: "button",
              onClick: () => r(g(s)),
              className: "inline-flex items-center gap-2 rounded-2xl bg-cyan-400 px-5 py-3 text-sm font-black text-slate-950 transition hover:bg-cyan-300",
              children: [
                "Open Last Session",
                /* @__PURE__ */ e.jsx(k, { className: "h-4 w-4" })
              ]
            }
          ),
          /* @__PURE__ */ e.jsxs(
            "button",
            {
              type: "button",
              onClick: () => r("#/profile"),
              className: "inline-flex items-center gap-2 rounded-2xl border border-white/10 bg-white/6 px-5 py-3 text-sm font-bold text-white transition hover:border-cyan-400/25 hover:bg-white/10",
              children: [
                "Find My Stats",
                /* @__PURE__ */ e.jsx(_, { className: "h-4 w-4" })
              ]
            }
          )
        ] })
      ] })
    ] }),
    /* @__PURE__ */ e.jsxs("div", { className: "border-t border-white/8 p-7 md:p-8 lg:border-l lg:border-t-0", children: [
      /* @__PURE__ */ e.jsx("div", { className: "section-kicker mb-2", children: "Session Snapshot" }),
      /* @__PURE__ */ e.jsx("div", { className: "text-3xl font-black text-white", children: F(s.allies_wins ?? 0, s.axis_wins ?? 0) }),
      /* @__PURE__ */ e.jsxs("p", { className: "mt-2 text-sm text-slate-400", children: [
        s.time_ago || "Most recent tracked session",
        " ",
        s.start_time && s.end_time ? `· ${s.start_time} to ${s.end_time}` : ""
      ] }),
      /* @__PURE__ */ e.jsxs("div", { className: "mt-5 grid grid-cols-2 gap-3", children: [
        /* @__PURE__ */ e.jsx(p, { label: "Duration", value: O(s.duration_seconds) }),
        /* @__PURE__ */ e.jsx(p, { label: "Kills", value: o(s.total_kills || 0) }),
        /* @__PURE__ */ e.jsx(p, { label: "Maps", value: o(s.maps_played.length || s.maps || 0) }),
        /* @__PURE__ */ e.jsx(p, { label: "Roster", value: o(s.player_names.length || s.player_count) })
      ] }),
      /* @__PURE__ */ e.jsxs("div", { className: "surface-divider mt-6", children: [
        /* @__PURE__ */ e.jsx("div", { className: "text-sm font-bold text-white", children: "Fast next steps" }),
        /* @__PURE__ */ e.jsxs("div", { className: "mt-3 space-y-2", children: [
          /* @__PURE__ */ e.jsx(j, { title: "Last session", subtitle: "Open the newest session detail immediately", onClick: () => r(g(s)) }),
          /* @__PURE__ */ e.jsx(j, { title: "Find my stats", subtitle: "Jump straight into a player profile", onClick: () => r("#/profile") }),
          /* @__PURE__ */ e.jsx(j, { title: "Browse archive", subtitle: "Open sessions history and drill deeper", onClick: () => r("#/sessions2") })
        ] })
      ] })
    ] })
  ] }) });
}
function p({ label: s, value: t }) {
  return /* @__PURE__ */ e.jsxs("div", { className: "rounded-[22px] border border-white/8 bg-white/[0.04] p-4", children: [
    /* @__PURE__ */ e.jsx("div", { className: "text-[11px] font-bold uppercase tracking-[0.22em] text-slate-500", children: s }),
    /* @__PURE__ */ e.jsx("div", { className: "mt-2 text-2xl font-black text-white", children: t })
  ] });
}
function j({
  title: s,
  subtitle: t,
  onClick: a
}) {
  return /* @__PURE__ */ e.jsxs(
    "button",
    {
      type: "button",
      onClick: a,
      className: "flex w-full items-center justify-between rounded-[20px] border border-white/8 bg-white/[0.03] px-4 py-3 text-left transition hover:border-cyan-400/20 hover:bg-white/[0.06]",
      children: [
        /* @__PURE__ */ e.jsxs("div", { children: [
          /* @__PURE__ */ e.jsx("div", { className: "text-sm font-bold text-white", children: s }),
          /* @__PURE__ */ e.jsx("div", { className: "text-xs text-slate-500", children: t })
        ] }),
        /* @__PURE__ */ e.jsx(D, { className: "h-4 w-4 text-slate-500" })
      ]
    }
  );
}
function H() {
  const { data: s } = N();
  return /* @__PURE__ */ e.jsxs("div", { className: "grid gap-4 md:grid-cols-3", children: [
    /* @__PURE__ */ e.jsx(
      f,
      {
        kicker: "Fast Action",
        title: "Last Session",
        body: "Open tonight's session without sifting through archive density.",
        onClick: () => r(g(s))
      }
    ),
    /* @__PURE__ */ e.jsx(
      f,
      {
        kicker: "Fast Action",
        title: "Find My Stats",
        body: "Use player lookup when you already know who you want.",
        onClick: () => r("#/profile")
      }
    ),
    /* @__PURE__ */ e.jsx(
      f,
      {
        kicker: "Fast Action",
        title: "Session Archive",
        body: "Browse older sessions only after the newest-session path is obvious.",
        onClick: () => r("#/sessions2")
      }
    )
  ] });
}
function f({
  kicker: s,
  title: t,
  body: a,
  onClick: l
}) {
  return /* @__PURE__ */ e.jsxs(u, { onClick: l, className: "p-5", children: [
    /* @__PURE__ */ e.jsx("div", { className: "section-kicker mb-2", children: s }),
    /* @__PURE__ */ e.jsx("div", { className: "text-2xl font-black text-white", children: t }),
    /* @__PURE__ */ e.jsx("p", { className: "mt-3 text-sm leading-6 text-slate-400", children: a }),
    /* @__PURE__ */ e.jsxs("div", { className: "mt-6 inline-flex items-center gap-2 text-sm font-bold text-cyan-300", children: [
      "Open",
      /* @__PURE__ */ e.jsx(k, { className: "h-4 w-4" })
    ] })
  ] });
}
function U() {
  const { data: s } = N(), { data: t } = A(), { data: a } = $(), l = a?.game_server.map ? b(a.game_server.map) : "Offline", d = a?.game_server.online ? `${a.game_server.player_count}/${a.game_server.max_players}` : "0";
  return /* @__PURE__ */ e.jsxs("section", { className: "space-y-4", children: [
    /* @__PURE__ */ e.jsx("div", { className: "flex items-end justify-between gap-4", children: /* @__PURE__ */ e.jsxs("div", { children: [
      /* @__PURE__ */ e.jsx("div", { className: "section-kicker", children: "Tonight At A Glance" }),
      /* @__PURE__ */ e.jsx("h2", { className: "mt-2 text-3xl font-black text-white", children: "One quick scan, then move." })
    ] }) }),
    /* @__PURE__ */ e.jsxs("div", { className: "grid gap-4 md:grid-cols-2 xl:grid-cols-5", children: [
      /* @__PURE__ */ e.jsx(m, { label: "Rounds tonight", value: o(s?.round_count || 0), accent: "text-cyan-300" }),
      /* @__PURE__ */ e.jsx(m, { label: "Players tonight", value: o(s?.player_count || 0), accent: "text-white" }),
      /* @__PURE__ */ e.jsx(m, { label: "Top map", value: s?.maps_played[0] ? b(s.maps_played[0]) : "--", accent: "text-amber-300" }),
      /* @__PURE__ */ e.jsx(m, { label: "Total kills", value: o(s?.total_kills || t?.total_kills_14d || 0), accent: "text-rose-300" }),
      /* @__PURE__ */ e.jsx(m, { label: "Live server", value: l, secondary: `${d} live`, accent: a?.game_server.online ? "text-emerald-300" : "text-slate-300" })
    ] })
  ] });
}
function m({
  label: s,
  value: t,
  secondary: a,
  accent: l
}) {
  return /* @__PURE__ */ e.jsxs(x, { className: "p-5", children: [
    /* @__PURE__ */ e.jsx("div", { className: "text-[11px] font-bold uppercase tracking-[0.24em] text-slate-500", children: s }),
    /* @__PURE__ */ e.jsx("div", { className: `mt-3 text-2xl font-black ${l}`, children: t }),
    a && /* @__PURE__ */ e.jsx("div", { className: "mt-2 text-xs text-slate-500", children: a })
  ] });
}
function B() {
  const { data: s, isLoading: t } = L(14), { data: a } = M(), l = y.useMemo(() => s?.dates?.length ? {
    labels: s.dates.map((i) => (/* @__PURE__ */ new Date(`${i}T00:00:00`)).toLocaleDateString(void 0, { month: "short", day: "numeric" })),
    datasets: [
      {
        data: s.rounds,
        borderColor: "#22d3ee",
        backgroundColor: "rgba(34,211,238,0.08)",
        fill: !0,
        borderWidth: 2,
        tension: 0.35,
        pointRadius: 0
      }
    ]
  } : null, [s]), d = y.useMemo(() => {
    if (!s?.map_distribution || typeof s.map_distribution != "object") return null;
    const i = Object.entries(s.map_distribution).map(([n, c]) => [b(n), Number(c)]).filter(([, n]) => n > 0).sort((n, c) => c[1] - n[1]).slice(0, 8);
    if (!i.length) return null;
    const h = ["#22d3ee", "#a78bfa", "#f472b6", "#fbbf24", "#34d399", "#fb923c", "#60a5fa", "#e879f9"];
    return {
      labels: i.map(([n]) => n),
      datasets: [{
        data: i.map(([, n]) => n),
        backgroundColor: i.map((n, c) => `${h[c % h.length]}cc`),
        borderColor: i.map((n, c) => h[c % h.length]),
        borderWidth: 1,
        borderRadius: 4
      }]
    };
  }, [s]);
  return /* @__PURE__ */ e.jsxs("section", { className: "grid gap-4 xl:grid-cols-3", children: [
    /* @__PURE__ */ e.jsxs(x, { className: "p-6", children: [
      /* @__PURE__ */ e.jsxs("div", { className: "mb-4 flex items-center justify-between", children: [
        /* @__PURE__ */ e.jsxs("div", { children: [
          /* @__PURE__ */ e.jsx("div", { className: "section-kicker", children: "Preview" }),
          /* @__PURE__ */ e.jsx("h2", { className: "mt-2 text-2xl font-black text-white", children: "Community rhythm" })
        ] }),
        /* @__PURE__ */ e.jsx(
          "button",
          {
            type: "button",
            onClick: () => r("#/leaderboards"),
            className: "rounded-full border border-white/10 bg-white/5 px-3 py-1.5 text-xs font-bold text-slate-300 transition hover:text-white",
            children: "More depth"
          }
        )
      ] }),
      t ? /* @__PURE__ */ e.jsx(v, { variant: "card", count: 1, className: "grid-cols-1" }) : l ? /* @__PURE__ */ e.jsx(
        w,
        {
          type: "line",
          data: l,
          height: "240px",
          options: {
            plugins: { legend: { display: !1 } },
            scales: {
              x: { ticks: { color: "#64748b" }, grid: { color: "rgba(255,255,255,0.04)" } },
              y: { ticks: { color: "#64748b" }, grid: { color: "rgba(255,255,255,0.04)" }, beginAtZero: !0 }
            }
          }
        }
      ) : /* @__PURE__ */ e.jsx("div", { className: "py-16 text-center text-sm text-slate-500", children: "Trend preview unavailable." })
    ] }),
    /* @__PURE__ */ e.jsxs(x, { className: "p-6", children: [
      /* @__PURE__ */ e.jsx("div", { className: "section-kicker", children: "Preview" }),
      /* @__PURE__ */ e.jsx("h2", { className: "mt-2 text-2xl font-black text-white", children: "Map distribution" }),
      /* @__PURE__ */ e.jsx("p", { className: "mt-1 text-xs text-slate-500", children: "Most played maps (14 days)" }),
      /* @__PURE__ */ e.jsx("div", { className: "mt-4", children: t ? /* @__PURE__ */ e.jsx(v, { variant: "card", count: 1, className: "grid-cols-1" }) : d ? /* @__PURE__ */ e.jsx(
        w,
        {
          type: "bar",
          data: d,
          height: "220px",
          options: {
            indexAxis: "y",
            plugins: { legend: { display: !1 } },
            scales: {
              x: { ticks: { color: "#64748b" }, grid: { color: "rgba(255,255,255,0.04)" }, beginAtZero: !0 },
              y: { ticks: { color: "#cbd5e1", font: { size: 11 } }, grid: { display: !1 } }
            }
          }
        }
      ) : /* @__PURE__ */ e.jsx("div", { className: "py-16 text-center text-sm text-slate-500", children: "No map data available." }) })
    ] }),
    /* @__PURE__ */ e.jsxs(x, { className: "p-6", children: [
      /* @__PURE__ */ e.jsx("div", { className: "section-kicker", children: "Preview" }),
      /* @__PURE__ */ e.jsx("h2", { className: "mt-2 text-2xl font-black text-white", children: "Leaderboard snapshot" }),
      /* @__PURE__ */ e.jsx("div", { className: "mt-5 space-y-3", children: (a?.dpm_sessions || []).slice(0, 5).map((i) => /* @__PURE__ */ e.jsxs(
        "button",
        {
          type: "button",
          onClick: () => P(i.name),
          className: "flex w-full items-center justify-between rounded-[20px] border border-white/8 bg-white/[0.03] px-4 py-3 text-left transition hover:bg-white/[0.06]",
          children: [
            /* @__PURE__ */ e.jsxs("div", { className: "flex items-center gap-3", children: [
              /* @__PURE__ */ e.jsx("div", { className: "flex h-10 w-10 items-center justify-center rounded-2xl bg-cyan-400/10 text-cyan-300", children: i.rank }),
              /* @__PURE__ */ e.jsxs("div", { children: [
                /* @__PURE__ */ e.jsx("div", { className: "text-sm font-bold text-white", children: i.name }),
                /* @__PURE__ */ e.jsx("div", { className: "text-xs text-slate-500", children: "DPM sessions" })
              ] })
            ] }),
            /* @__PURE__ */ e.jsxs("div", { className: "text-right", children: [
              /* @__PURE__ */ e.jsx("div", { className: "text-sm font-black text-white", children: o(i.value) }),
              /* @__PURE__ */ e.jsxs("div", { className: "text-xs text-slate-500", children: [
                i.sessions || 0,
                " sessions"
              ] })
            ] })
          ]
        },
        `${i.guid}-${i.rank}`
      )) })
    ] })
  ] });
}
function q() {
  return /* @__PURE__ */ e.jsxs("section", { className: "grid gap-4 xl:grid-cols-[1fr_1fr_1fr]", children: [
    /* @__PURE__ */ e.jsxs(u, { onClick: () => r("#/sessions2"), className: "p-5", children: [
      /* @__PURE__ */ e.jsx("div", { className: "section-kicker mb-2", children: "Browse" }),
      /* @__PURE__ */ e.jsxs("div", { className: "flex items-center gap-3", children: [
        /* @__PURE__ */ e.jsx(T, { className: "h-5 w-5 text-cyan-300" }),
        /* @__PURE__ */ e.jsx("div", { className: "text-xl font-black text-white", children: "Sessions archive" })
      ] }),
      /* @__PURE__ */ e.jsx("p", { className: "mt-3 text-sm text-slate-400", children: "Clean session history for when the latest session is not enough." })
    ] }),
    /* @__PURE__ */ e.jsxs(u, { onClick: () => r("#/profile"), className: "p-5", children: [
      /* @__PURE__ */ e.jsx("div", { className: "section-kicker mb-2", children: "People" }),
      /* @__PURE__ */ e.jsxs("div", { className: "flex items-center gap-3", children: [
        /* @__PURE__ */ e.jsx(_, { className: "h-5 w-5 text-amber-300" }),
        /* @__PURE__ */ e.jsx("div", { className: "text-xl font-black text-white", children: "Player profiles" })
      ] }),
      /* @__PURE__ */ e.jsx("p", { className: "mt-3 text-sm text-slate-400", children: "Search a player quickly when you already know whose stats you want." })
    ] }),
    /* @__PURE__ */ e.jsxs(u, { onClick: () => r("#/proximity"), className: "p-5", children: [
      /* @__PURE__ */ e.jsx("div", { className: "section-kicker mb-2", children: "Deep Analysis" }),
      /* @__PURE__ */ e.jsxs("div", { className: "flex items-center gap-3", children: [
        /* @__PURE__ */ e.jsx(R, { className: "h-5 w-5 text-purple-300" }),
        /* @__PURE__ */ e.jsx("div", { className: "text-xl font-black text-white", children: "Advanced tools" })
      ] }),
      /* @__PURE__ */ e.jsx("p", { className: "mt-3 text-sm text-slate-400", children: "Proximity, viz, uploads, admin, and other specialist surfaces now live behind the main journey." })
    ] })
  ] });
}
function se() {
  return /* @__PURE__ */ e.jsxs("div", { className: "page-shell", children: [
    /* @__PURE__ */ e.jsx(G, {}),
    /* @__PURE__ */ e.jsx(H, {}),
    /* @__PURE__ */ e.jsxs("section", { className: "grid gap-4 xl:grid-cols-[1.1fr_0.9fr]", children: [
      /* @__PURE__ */ e.jsx(U, {}),
      /* @__PURE__ */ e.jsx(
        C,
        {
          title: "Find My Stats",
          subtitle: "Search a player immediately when you want your personal flow instead of the archive."
        }
      )
    ] }),
    /* @__PURE__ */ e.jsx(B, {}),
    /* @__PURE__ */ e.jsx(q, {})
  ] });
}
export {
  se as default
};
