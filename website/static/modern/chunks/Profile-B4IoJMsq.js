import { r as S, j as e, S as C, c as u } from "./route-host-Ba3v8uFM.js";
import { n as R, o as D, p as L } from "./hooks-CyQgvbI9.js";
import { C as F } from "./Chart-DkWq45SK.js";
import { D as M } from "./DataTable-gbZQ6Kgl.js";
import { G as f } from "./GlassPanel-C-uUmQaB.js";
import { P as x } from "./PageHeader-CQ7BTOQj.js";
import { P as j } from "./PlayerLookup-CRlHDLm4.js";
import { a as h, f as n } from "./format-BM7Gaq4w.js";
import { w as v, m as y } from "./game-assets-BMYaQb9B.js";
import { n as g } from "./navigation-BDd1HkpE.js";
import { S as T } from "./skull-BhM2GlAn.js";
import { Z as U } from "./zap-Chh6-OiF.js";
import { C as N } from "./crosshair-CPb1OWqx.js";
import { T as $ } from "./trophy-f4_RKZnn.js";
import { c as k } from "./createLucideIcon-BebMLfof.js";
import { S as A } from "./star-DzJ3yYFk.js";
import { C as E } from "./clock-3-JXf94b9Z.js";
import { S as H } from "./shield-Bg1J0PTe.js";
const W = [
  ["path", { d: "M3 3v16a2 2 0 0 0 2 2h16", key: "c24i48" }],
  [
    "path",
    {
      d: "M7 11.207a.5.5 0 0 1 .146-.353l2-2a.5.5 0 0 1 .708 0l3.292 3.292a.5.5 0 0 0 .708 0l4.292-4.292a.5.5 0 0 1 .854.353V16a1 1 0 0 1-1 1H8a1 1 0 0 1-1-1z",
      key: "q0gr47"
    }
  ]
], I = k("chart-area", W);
const K = [
  ["path", { d: "M9 17H7A5 5 0 0 1 7 7h2", key: "8i5ue5" }],
  ["path", { d: "M15 7h2a5 5 0 1 1 0 10h-2", key: "1b9ql8" }],
  ["line", { x1: "8", x2: "16", y1: "12", y2: "12", key: "1jonct" }]
], V = k("link-2", K), q = [
  {
    key: "round_date",
    label: "Date",
    render: (t) => h(t.round_date),
    className: "text-slate-400"
  },
  {
    key: "map_name",
    label: "Map",
    render: (t) => /* @__PURE__ */ e.jsxs("div", { className: "flex items-center gap-3", children: [
      /* @__PURE__ */ e.jsx(
        "img",
        {
          src: y(t.map_name),
          alt: t.map_name,
          className: "h-9 w-9 rounded-2xl object-cover bg-slate-900/80",
          onError: (r) => {
            r.currentTarget.style.display = "none";
          }
        }
      ),
      /* @__PURE__ */ e.jsxs("div", { children: [
        /* @__PURE__ */ e.jsx("div", { className: "font-semibold text-white", children: t.map_name }),
        /* @__PURE__ */ e.jsxs("div", { className: "text-xs text-slate-500", children: [
          "Round ",
          t.round_number
        ] })
      ] })
    ] })
  },
  {
    key: "kills",
    label: "Kills",
    sortable: !0,
    sortValue: (t) => t.kills,
    className: "text-emerald-300 font-mono"
  },
  {
    key: "deaths",
    label: "Deaths",
    sortable: !0,
    sortValue: (t) => t.deaths,
    className: "text-rose-300 font-mono"
  },
  {
    key: "dpm",
    label: "DPM",
    sortable: !0,
    sortValue: (t) => t.dpm,
    className: "text-cyan-300 font-mono",
    render: (t) => t.dpm?.toFixed(1) ?? "--"
  },
  {
    key: "result",
    label: "Result",
    render: (t) => {
      const r = t.team === t.winner_team && t.winner_team !== 0, a = t.team !== t.winner_team && t.winner_team !== 0;
      return r ? /* @__PURE__ */ e.jsx("span", { className: "text-xs font-bold text-emerald-300", children: "WIN" }) : a ? /* @__PURE__ */ e.jsx("span", { className: "text-xs font-bold text-rose-300", children: "LOSS" }) : /* @__PURE__ */ e.jsx("span", { className: "text-xs text-slate-500", children: "-" });
    }
  }
];
function Z() {
  const t = window.location.hash.split("?")[1] ?? "";
  return new URLSearchParams(t).get("name") ?? "";
}
function i({
  label: t,
  value: r,
  icon: a,
  accent: o
}) {
  return /* @__PURE__ */ e.jsxs("div", { className: "rounded-[22px] border border-white/8 bg-white/[0.03] p-4", children: [
    /* @__PURE__ */ e.jsxs("div", { className: "flex items-center gap-2", children: [
      /* @__PURE__ */ e.jsx(a, { className: `h-4 w-4 ${o}` }),
      /* @__PURE__ */ e.jsx("span", { className: "text-[11px] font-bold uppercase tracking-[0.2em] text-slate-500", children: t })
    ] }),
    /* @__PURE__ */ e.jsx("div", { className: `mt-3 text-2xl font-black ${o}`, children: r })
  ] });
}
function B({ achievement: t }) {
  return /* @__PURE__ */ e.jsxs(
    "div",
    {
      className: u(
        "rounded-[22px] border p-4 transition",
        t.unlocked ? "border-amber-300/20 bg-amber-300/8" : "border-white/8 bg-white/[0.02] opacity-70"
      ),
      children: [
        /* @__PURE__ */ e.jsx("div", { className: "text-2xl", children: t.icon }),
        /* @__PURE__ */ e.jsx("div", { className: u("mt-3 text-sm font-bold", t.unlocked ? "text-white" : "text-slate-500"), children: t.name }),
        /* @__PURE__ */ e.jsx("div", { className: "mt-1 text-xs text-slate-500", children: t.description })
      ]
    }
  );
}
function me({ params: t }) {
  const r = t?.name || Z(), { data: a, isLoading: o, isError: w } = R(r), { data: d } = D(r), { data: c } = L(r), b = S.useMemo(() => c?.length ? {
    labels: c.map((l) => h(l.date)),
    datasets: [
      {
        data: c.map((l) => l.dpm),
        borderColor: "#22d3ee",
        backgroundColor: "rgba(34,211,238,0.08)",
        fill: !0,
        tension: 0.35,
        borderWidth: 2,
        pointRadius: 2
      }
    ]
  } : null, [c]);
  if (!r)
    return /* @__PURE__ */ e.jsxs("div", { className: "page-shell", children: [
      /* @__PURE__ */ e.jsx(
        x,
        {
          title: "Find a Player",
          subtitle: "Profile is now the direct lookup surface when you already know the player you want.",
          eyebrow: "Players"
        }
      ),
      /* @__PURE__ */ e.jsx(j, { title: "Search a player", subtitle: "Type at least two characters to open a full player profile." })
    ] });
  if (o)
    return /* @__PURE__ */ e.jsxs("div", { className: "page-shell", children: [
      /* @__PURE__ */ e.jsx(x, { title: r, subtitle: "Loading player profile...", eyebrow: "Players" }),
      /* @__PURE__ */ e.jsx(C, { variant: "card", count: 5 })
    ] });
  if (w || !a)
    return /* @__PURE__ */ e.jsxs("div", { className: "page-shell", children: [
      /* @__PURE__ */ e.jsx(x, { title: r, subtitle: "Player profile could not be loaded.", eyebrow: "Players" }),
      /* @__PURE__ */ e.jsx("div", { className: "text-center text-red-400 py-12", children: "Player not found or failed to load." })
    ] });
  const s = a.stats, m = d?.[0] ?? null, p = m ? `#/session-detail/date/${encodeURIComponent(m.round_date)}` : null, _ = a.name.slice(0, 2).toUpperCase(), P = a.achievements.filter((l) => l.unlocked).length;
  return /* @__PURE__ */ e.jsxs("div", { className: "page-shell", children: [
    /* @__PURE__ */ e.jsx(
      x,
      {
        title: a.name,
        subtitle: "Personal performance, recent form, and a direct path back into the latest session context.",
        eyebrow: "Players",
        badge: a.discord_linked ? "Discord linked" : "Website profile",
        children: /* @__PURE__ */ e.jsx(
          "button",
          {
            type: "button",
            onClick: () => g("#/sessions2"),
            className: "rounded-full border border-white/10 bg-white/5 px-4 py-2 text-xs font-bold text-slate-300 transition hover:text-white",
            children: "Back to Sessions"
          }
        )
      }
    ),
    /* @__PURE__ */ e.jsx(f, { className: "p-0 overflow-hidden", children: /* @__PURE__ */ e.jsxs("div", { className: "grid gap-0 lg:grid-cols-[0.85fr_1.15fr]", children: [
      /* @__PURE__ */ e.jsxs("div", { className: "border-b border-white/8 p-6 md:p-7 lg:border-b-0 lg:border-r", children: [
        /* @__PURE__ */ e.jsxs("div", { className: "flex items-start gap-4", children: [
          /* @__PURE__ */ e.jsx("div", { className: "flex h-18 w-18 items-center justify-center rounded-[26px] bg-gradient-to-br from-cyan-400 to-purple-500 text-2xl font-black text-slate-950", children: _ }),
          /* @__PURE__ */ e.jsxs("div", { className: "min-w-0", children: [
            /* @__PURE__ */ e.jsx("div", { className: "section-kicker mb-2", children: "Player Summary" }),
            /* @__PURE__ */ e.jsx("div", { className: "text-3xl font-black text-white", children: a.name }),
            /* @__PURE__ */ e.jsx("div", { className: "mt-2 flex flex-wrap gap-2", children: a.aliases.slice(0, 3).map((l) => /* @__PURE__ */ e.jsx("span", { className: "rounded-full border border-white/10 bg-white/6 px-3 py-1 text-xs font-bold text-slate-300", children: l }, l)) }),
            /* @__PURE__ */ e.jsxs("div", { className: "mt-4 text-sm text-slate-400", children: [
              "Last seen ",
              s.last_seen ? h(s.last_seen) : "unknown",
              "."
            ] })
          ] })
        ] }),
        /* @__PURE__ */ e.jsxs("div", { className: "mt-6 grid gap-3 sm:grid-cols-2", children: [
          /* @__PURE__ */ e.jsx(i, { label: "Kills", value: n(s.kills), icon: T, accent: "text-white" }),
          /* @__PURE__ */ e.jsx(i, { label: "DPM", value: n(s.dpm), icon: U, accent: "text-cyan-300" }),
          /* @__PURE__ */ e.jsx(i, { label: "K/D", value: s.kd.toFixed(2), icon: N, accent: "text-amber-300" }),
          /* @__PURE__ */ e.jsx(i, { label: "Win Rate", value: `${s.win_rate}%`, icon: $, accent: "text-emerald-300" })
        ] }),
        /* @__PURE__ */ e.jsxs("div", { className: "surface-divider mt-6 space-y-3", children: [
          p && /* @__PURE__ */ e.jsxs(
            "button",
            {
              type: "button",
              onClick: () => p && g(p),
              className: "flex w-full items-center justify-between rounded-[20px] border border-white/8 bg-white/[0.03] px-4 py-3 text-left transition hover:bg-white/[0.06]",
              children: [
                /* @__PURE__ */ e.jsxs("div", { children: [
                  /* @__PURE__ */ e.jsx("div", { className: "text-sm font-bold text-white", children: "Latest played session" }),
                  /* @__PURE__ */ e.jsx("div", { className: "text-xs text-slate-500", children: m ? h(m.round_date) : "Unknown date" })
                ] }),
                /* @__PURE__ */ e.jsx(V, { className: "h-4 w-4 text-slate-500" })
              ]
            }
          ),
          /* @__PURE__ */ e.jsx(j, { compact: !0, placeholder: "Search another player...", title: "Search another player", subtitle: "" })
        ] })
      ] }),
      /* @__PURE__ */ e.jsxs("div", { className: "p-6 md:p-7", children: [
        /* @__PURE__ */ e.jsxs("div", { className: "grid gap-3 sm:grid-cols-2 xl:grid-cols-4", children: [
          /* @__PURE__ */ e.jsx(i, { label: "Rounds", value: n(s.games), icon: A, accent: "text-purple-300" }),
          /* @__PURE__ */ e.jsx(i, { label: "Playtime", value: `${s.playtime_hours}h`, icon: E, accent: "text-slate-200" }),
          /* @__PURE__ */ e.jsx(i, { label: "Damage", value: n(s.damage), icon: H, accent: "text-rose-300" }),
          /* @__PURE__ */ e.jsx(i, { label: "XP", value: n(s.total_xp), icon: I, accent: "text-cyan-300" })
        ] }),
        /* @__PURE__ */ e.jsxs("div", { className: "mt-6 grid gap-4 xl:grid-cols-[1fr_0.9fr]", children: [
          /* @__PURE__ */ e.jsxs("div", { className: "rounded-[22px] border border-white/8 bg-white/[0.03] p-5", children: [
            /* @__PURE__ */ e.jsx("div", { className: "section-kicker mb-2", children: "Recent Form" }),
            /* @__PURE__ */ e.jsx("div", { className: "text-xl font-black text-white", children: "DPM over recent sessions" }),
            /* @__PURE__ */ e.jsx("div", { className: "mt-4", children: b ? /* @__PURE__ */ e.jsx(
              F,
              {
                type: "line",
                data: b,
                height: "220px",
                options: {
                  plugins: { legend: { display: !1 } },
                  scales: {
                    x: { ticks: { color: "#64748b" }, grid: { color: "rgba(255,255,255,0.04)" } },
                    y: { ticks: { color: "#64748b" }, grid: { color: "rgba(255,255,255,0.04)" }, beginAtZero: !0 }
                  }
                }
              }
            ) : /* @__PURE__ */ e.jsx("div", { className: "py-16 text-center text-sm text-slate-500", children: "Recent form data unavailable." }) })
          ] }),
          /* @__PURE__ */ e.jsxs("div", { className: "rounded-[22px] border border-white/8 bg-white/[0.03] p-5", children: [
            /* @__PURE__ */ e.jsx("div", { className: "section-kicker mb-2", children: "Personal Taste" }),
            /* @__PURE__ */ e.jsx("div", { className: "text-xl font-black text-white", children: "Preferred loadout" }),
            /* @__PURE__ */ e.jsxs("div", { className: "mt-5 space-y-4", children: [
              /* @__PURE__ */ e.jsxs("div", { className: "rounded-[20px] border border-white/8 bg-slate-900/70 p-4", children: [
                /* @__PURE__ */ e.jsx("div", { className: "text-[11px] font-bold uppercase tracking-[0.2em] text-slate-500", children: "Favorite weapon" }),
                /* @__PURE__ */ e.jsxs("div", { className: "mt-3 flex items-center gap-3", children: [
                  s.favorite_weapon && v(s.favorite_weapon) ? /* @__PURE__ */ e.jsx("img", { src: v(s.favorite_weapon), alt: "", className: "h-7 object-contain opacity-80", style: { filter: "brightness(1.7)" } }) : /* @__PURE__ */ e.jsx(N, { className: "h-5 w-5 text-cyan-300" }),
                  /* @__PURE__ */ e.jsx("div", { className: "text-lg font-black text-white", children: s.favorite_weapon || "Unknown" })
                ] })
              ] }),
              /* @__PURE__ */ e.jsxs("div", { className: "rounded-[20px] border border-white/8 bg-slate-900/70 p-4", children: [
                /* @__PURE__ */ e.jsx("div", { className: "text-[11px] font-bold uppercase tracking-[0.2em] text-slate-500", children: "Favorite map" }),
                /* @__PURE__ */ e.jsxs("div", { className: "mt-3 flex items-center gap-3", children: [
                  s.favorite_map ? /* @__PURE__ */ e.jsx(
                    "img",
                    {
                      src: y(s.favorite_map),
                      alt: s.favorite_map,
                      className: "h-12 w-12 rounded-2xl object-cover bg-slate-950",
                      onError: (l) => {
                        l.currentTarget.style.display = "none";
                      }
                    }
                  ) : /* @__PURE__ */ e.jsx("div", { className: "h-12 w-12 rounded-2xl bg-slate-950" }),
                  /* @__PURE__ */ e.jsx("div", { className: "text-lg font-black text-white", children: s.favorite_map || "Unknown" })
                ] })
              ] })
            ] })
          ] })
        ] })
      ] })
    ] }) }),
    a.achievements.length > 0 && /* @__PURE__ */ e.jsxs(f, { className: "p-6", children: [
      /* @__PURE__ */ e.jsx("div", { className: "mb-4 flex items-end justify-between gap-4", children: /* @__PURE__ */ e.jsxs("div", { children: [
        /* @__PURE__ */ e.jsx("div", { className: "section-kicker mb-2", children: "Achievements" }),
        /* @__PURE__ */ e.jsxs("div", { className: "text-2xl font-black text-white", children: [
          "Unlocked ",
          P,
          " of ",
          a.achievements.length
        ] })
      ] }) }),
      /* @__PURE__ */ e.jsx("div", { className: "grid gap-3 md:grid-cols-2 xl:grid-cols-3", children: a.achievements.map((l) => /* @__PURE__ */ e.jsx(B, { achievement: l }, l.name)) })
    ] }),
    d && d.length > 0 && /* @__PURE__ */ e.jsxs("div", { children: [
      /* @__PURE__ */ e.jsxs("div", { className: "mb-4", children: [
        /* @__PURE__ */ e.jsx("div", { className: "section-kicker mb-2", children: "Recent rounds" }),
        /* @__PURE__ */ e.jsx("div", { className: "text-2xl font-black text-white", children: "What the player has been doing lately" })
      ] }),
      /* @__PURE__ */ e.jsx(
        M,
        {
          columns: q,
          data: d,
          keyFn: (l) => String(l.round_id),
          defaultSort: { key: "round_date", dir: "desc" }
        }
      )
    ] })
  ] });
}
export {
  me as default
};
