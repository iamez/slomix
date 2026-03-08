import { jsxs as r, jsx as t } from "react/jsx-runtime";
import { useState as k, useMemo as d } from "react";
import { q as D, r as M } from "./hooks-UFUMZFGB.js";
import { C as h } from "./Chart-6fGZGgP8.js";
import { P as x } from "./PageHeader-D4CVo02x.js";
import { S as f, c as _ } from "./route-host-CUL1oI6Z.js";
import { E as y } from "./EmptyState-DvtQr4qR.js";
import { D as w } from "./DataTable-C9DYv6yb.js";
import { f as b } from "./format-BM7Gaq4w.js";
import { a as C } from "./navigation-BDd1HkpE.js";
import { m as R } from "./game-assets-CWuRxGFH.js";
const u = [
  "rgba(59, 130, 246, 0.7)",
  "rgba(244, 63, 94, 0.7)",
  "rgba(16, 185, 129, 0.7)",
  "rgba(245, 158, 11, 0.7)",
  "rgba(168, 85, 247, 0.7)"
];
function N(e) {
  return e === 0 ? "R0 (summary)" : `R${e}`;
}
function S({ data: e }) {
  const a = e.highlights, n = e.winner_team === 1 ? "Axis" : e.winner_team === 2 ? "Allies" : "Tied", l = e.winner_team === 1 ? "text-rose-400" : e.winner_team === 2 ? "text-blue-400" : "text-slate-400", o = e.duration_seconds ? `${Math.round(e.duration_seconds / 60)}m` : "--";
  return /* @__PURE__ */ r("div", { className: "glass-card rounded-xl p-5", children: [
    /* @__PURE__ */ t("h3", { className: "text-sm font-bold text-white mb-4", children: "Match Summary" }),
    /* @__PURE__ */ r("div", { className: "grid grid-cols-2 gap-3 text-sm", children: [
      /* @__PURE__ */ r("div", { className: "glass-panel rounded-lg p-3 flex items-center gap-2", children: [
        /* @__PURE__ */ t("img", { src: R(e.map_name || ""), alt: "", className: "w-8 h-8 rounded object-cover bg-slate-700", onError: (i) => {
          i.currentTarget.style.display = "none";
        } }),
        /* @__PURE__ */ r("div", { children: [
          /* @__PURE__ */ t("div", { className: "text-[11px] text-slate-500", children: "Map" }),
          /* @__PURE__ */ t("div", { className: "font-bold text-white", children: e.map_name || "Unknown" })
        ] })
      ] }),
      /* @__PURE__ */ t(g, { label: "Round", value: e.round_label || N(e.round_number) }),
      /* @__PURE__ */ t(g, { label: "Date", value: e.round_date || "--" }),
      /* @__PURE__ */ t(g, { label: "Duration", value: o }),
      /* @__PURE__ */ t(g, { label: "Players", value: String(e.player_count) }),
      /* @__PURE__ */ r("div", { className: "glass-panel rounded-lg p-3", children: [
        /* @__PURE__ */ t("div", { className: "text-[11px] text-slate-500", children: "Winner" }),
        /* @__PURE__ */ t("div", { className: _("font-bold", l), children: n })
      ] })
    ] }),
    (a.mvp || a.most_kills || a.most_damage) && /* @__PURE__ */ r("div", { className: "mt-4 grid grid-cols-3 gap-2", children: [
      a.mvp && /* @__PURE__ */ t(v, { label: "MVP (DPM)", name: a.mvp.name, value: Math.round(a.mvp.dpm), color: "text-yellow-500" }),
      a.most_kills && /* @__PURE__ */ t(v, { label: "Most Kills", name: a.most_kills.name, value: a.most_kills.kills, color: "text-rose-400" }),
      a.most_damage && /* @__PURE__ */ t(v, { label: "Most Damage", name: a.most_damage.name, value: b(a.most_damage.damage_given), color: "text-orange-400" })
    ] })
  ] });
}
function g({ label: e, value: a }) {
  return /* @__PURE__ */ r("div", { className: "glass-panel rounded-lg p-3", children: [
    /* @__PURE__ */ t("div", { className: "text-[11px] text-slate-500", children: e }),
    /* @__PURE__ */ t("div", { className: "text-white font-bold", children: a })
  ] });
}
function v({ label: e, name: a, value: n, color: l }) {
  return /* @__PURE__ */ r("div", { className: "glass-panel rounded-lg p-2 text-center", children: [
    /* @__PURE__ */ t("div", { className: _("text-[10px]", l), children: e }),
    /* @__PURE__ */ t("div", { className: "text-xs text-white font-bold truncate", children: a }),
    /* @__PURE__ */ t("div", { className: "text-[10px] text-slate-400", children: n })
  ] });
}
function z({ players: e }) {
  const a = d(
    () => [...e].sort((l, o) => o.dpm - l.dpm).slice(0, 5),
    [e]
  ), n = d(() => {
    if (a.length === 0) return null;
    const l = Math.max(...a.map((s) => s.kills), 1), o = Math.max(...a.map((s) => s.deaths), 1), i = Math.max(...a.map((s) => s.dpm), 1), p = Math.max(...a.map((s) => s.damage_given), 1), c = Math.max(...a.map((s) => s.gibs), 1);
    return {
      labels: ["Kills", "Deaths(inv)", "DPM", "Damage", "Efficiency", "Gibs"],
      datasets: a.map((s, m) => ({
        label: s.name,
        data: [
          Math.round(s.kills / l * 100),
          Math.round((1 - s.deaths / o) * 100),
          Math.round(s.dpm / i * 100),
          Math.round(s.damage_given / p * 100),
          Math.round(s.efficiency),
          Math.round(s.gibs / c * 100)
        ],
        backgroundColor: u[m % u.length],
        borderColor: u[m % u.length],
        borderWidth: 2
      }))
    };
  }, [a]);
  return n ? /* @__PURE__ */ r("div", { className: "glass-card rounded-xl p-5", children: [
    /* @__PURE__ */ t("h3", { className: "text-sm font-bold text-white mb-4", children: "Combat Overview" }),
    /* @__PURE__ */ t(
      h,
      {
        type: "radar",
        data: n,
        height: 320,
        options: {
          plugins: { legend: { position: "bottom", labels: { color: "#94a3b8", font: { size: 10 } } } },
          scales: {
            r: {
              angleLines: { color: "rgba(148,163,184,0.2)" },
              grid: { color: "rgba(148,163,184,0.2)" },
              pointLabels: { color: "#94a3b8", font: { size: 10 } },
              ticks: { display: !1 },
              min: 0,
              max: 100
            }
          }
        }
      }
    )
  ] }) : null;
}
function P({ players: e }) {
  const a = d(() => [...e].sort((l, o) => o.kills - l.kills), [e]), n = d(() => ({
    labels: a.map((l) => l.name),
    datasets: [
      {
        label: "Kills",
        data: a.map((l) => l.kills),
        backgroundColor: "rgba(59, 130, 246, 0.7)"
      },
      {
        label: "Deaths",
        data: a.map((l) => l.deaths),
        backgroundColor: "rgba(244, 63, 94, 0.5)"
      }
    ]
  }), [a]);
  return /* @__PURE__ */ r("div", { className: "glass-card rounded-xl p-5", children: [
    /* @__PURE__ */ t("h3", { className: "text-sm font-bold text-white mb-4", children: "Top Fraggers" }),
    /* @__PURE__ */ t(
      h,
      {
        type: "bar",
        data: n,
        height: Math.max(200, e.length * 32),
        options: {
          indexAxis: "y",
          plugins: { legend: { labels: { color: "#94a3b8", font: { size: 10 } } } },
          scales: {
            x: { grid: { color: "rgba(148,163,184,0.1)" }, ticks: { color: "#94a3b8" } },
            y: { grid: { display: !1 }, ticks: { color: "#e2e8f0", font: { size: 11 } } }
          }
        }
      }
    )
  ] });
}
function L({ players: e }) {
  const a = d(
    () => [...e].sort((l, o) => o.revives_given - l.revives_given),
    [e]
  ), n = d(() => ({
    labels: a.map((l) => l.name),
    datasets: [
      {
        label: "Revives",
        data: a.map((l) => l.revives_given),
        backgroundColor: "rgba(16, 185, 129, 0.7)"
      },
      {
        label: "Gibs",
        data: a.map((l) => l.gibs),
        backgroundColor: "rgba(168, 85, 247, 0.5)"
      },
      {
        label: "Self Kills",
        data: a.map((l) => l.self_kills),
        backgroundColor: "rgba(245, 158, 11, 0.5)"
      }
    ]
  }), [a]);
  return /* @__PURE__ */ r("div", { className: "glass-card rounded-xl p-5", children: [
    /* @__PURE__ */ t("h3", { className: "text-sm font-bold text-white mb-4", children: "Support Performance" }),
    /* @__PURE__ */ t(
      h,
      {
        type: "bar",
        data: n,
        height: Math.max(200, e.length * 36),
        options: {
          indexAxis: "y",
          plugins: { legend: { labels: { color: "#94a3b8", font: { size: 10 } } } },
          scales: {
            x: { stacked: !0, grid: { color: "rgba(148,163,184,0.1)" }, ticks: { color: "#94a3b8" } },
            y: { stacked: !0, grid: { display: !1 }, ticks: { color: "#e2e8f0", font: { size: 11 } } }
          }
        }
      }
    )
  ] });
}
function T({ players: e }) {
  const a = d(
    () => [...e].sort((l, o) => o.time_played_seconds - l.time_played_seconds),
    [e]
  ), n = d(() => ({
    labels: a.map((l) => l.name),
    datasets: [
      {
        label: "Alive (s)",
        data: a.map((l) => Math.max(0, l.time_played_seconds - l.time_dead_seconds)),
        backgroundColor: "rgba(34, 197, 94, 0.7)"
      },
      {
        label: "Dead (s)",
        data: a.map((l) => l.time_dead_seconds),
        backgroundColor: "rgba(100, 116, 139, 0.5)"
      }
    ]
  }), [a]);
  return /* @__PURE__ */ r("div", { className: "glass-card rounded-xl p-5", children: [
    /* @__PURE__ */ t("h3", { className: "text-sm font-bold text-white mb-4", children: "Time Distribution" }),
    /* @__PURE__ */ t(
      h,
      {
        type: "bar",
        data: n,
        height: Math.max(200, e.length * 32),
        options: {
          indexAxis: "y",
          plugins: { legend: { labels: { color: "#94a3b8", font: { size: 10 } } } },
          scales: {
            x: { stacked: !0, grid: { color: "rgba(148,163,184,0.1)" }, ticks: { color: "#94a3b8" } },
            y: { stacked: !0, grid: { display: !1 }, ticks: { color: "#e2e8f0", font: { size: 11 } } }
          }
        }
      }
    )
  ] });
}
const V = [
  {
    key: "name",
    label: "Player",
    render: (e) => /* @__PURE__ */ t("button", { onClick: () => C(e.name), className: "text-blue-400 hover:text-blue-300 font-semibold text-left", children: e.name })
  },
  { key: "damage_given", label: "Dmg Given", sortable: !0, sortValue: (e) => e.damage_given, className: "font-mono text-white", render: (e) => b(e.damage_given) },
  { key: "damage_received", label: "Dmg Recv", sortable: !0, sortValue: (e) => e.damage_received, className: "font-mono text-slate-400", render: (e) => b(e.damage_received) },
  { key: "team_damage_given", label: "Team Dmg", sortable: !0, sortValue: (e) => e.team_damage_given, className: "font-mono text-amber-400", render: (e) => b(e.team_damage_given) },
  { key: "dpm", label: "DPM", sortable: !0, sortValue: (e) => e.dpm, className: "font-mono text-cyan-400", render: (e) => e.dpm.toFixed(1) },
  { key: "efficiency", label: "Eff%", sortable: !0, sortValue: (e) => e.efficiency, className: "font-mono text-emerald-400", render: (e) => `${e.efficiency.toFixed(0)}%` }
];
function A({ players: e }) {
  return /* @__PURE__ */ r("div", { className: "glass-card rounded-xl p-5", children: [
    /* @__PURE__ */ t("h3", { className: "text-sm font-bold text-white mb-4", children: "Damage Breakdown" }),
    /* @__PURE__ */ t("div", { className: "overflow-x-auto", children: /* @__PURE__ */ t(
      w,
      {
        columns: V,
        data: e,
        keyFn: (a) => a.guid,
        defaultSort: { key: "damage_given", dir: "desc" }
      }
    ) })
  ] });
}
function W() {
  const { data: e, isLoading: a } = D(50), [n, l] = k(null), o = n ?? e?.[0]?.id ?? null, { data: i, isLoading: p } = M(o);
  if (a)
    return /* @__PURE__ */ r("div", { className: "mt-6", children: [
      /* @__PURE__ */ t(x, { title: "Round Visualizer", subtitle: "Interactive round-by-round combat analytics" }),
      /* @__PURE__ */ t(f, { variant: "card", count: 4 })
    ] });
  const c = (e ?? []).filter((s) => s.round_number > 0);
  return c.length === 0 ? /* @__PURE__ */ r("div", { className: "mt-6", children: [
    /* @__PURE__ */ t(x, { title: "Round Visualizer", subtitle: "Interactive round-by-round combat analytics" }),
    /* @__PURE__ */ t(y, { message: "No round data found. Play some rounds first!" })
  ] }) : /* @__PURE__ */ r("div", { className: "mt-6", children: [
    /* @__PURE__ */ t(x, { title: "Round Visualizer", subtitle: "Interactive round-by-round combat analytics", children: /* @__PURE__ */ t(
      "select",
      {
        value: o ?? "",
        onChange: (s) => l(Number(s.target.value)),
        className: `bg-slate-800 border border-white/10 text-slate-200 rounded-lg px-3 py-2 text-sm
                     focus:outline-none focus:border-cyan-500/50 min-w-[320px]`,
        children: c.map((s) => {
          const m = s.round_date ? (/* @__PURE__ */ new Date(s.round_date + "T00:00:00")).toLocaleDateString("en-US", { month: "short", day: "numeric", year: "numeric" }) : "";
          return /* @__PURE__ */ r("option", { value: s.id, children: [
            s.map_name || "Unknown",
            " ",
            s.round_label || N(s.round_number),
            " — ",
            m,
            " (",
            s.player_count,
            " players)"
          ] }, s.id);
        })
      }
    ) }),
    p ? /* @__PURE__ */ t(f, { variant: "card", count: 6, className: "grid-cols-2" }) : !i || i.players.length === 0 ? /* @__PURE__ */ t(y, { message: "No player data for this round." }) : /* @__PURE__ */ r("div", { className: "space-y-6", children: [
      /* @__PURE__ */ r("div", { className: "grid grid-cols-1 lg:grid-cols-2 gap-6", children: [
        /* @__PURE__ */ t(S, { data: i }),
        /* @__PURE__ */ t(z, { players: i.players })
      ] }),
      /* @__PURE__ */ t(P, { players: i.players }),
      /* @__PURE__ */ t(A, { players: i.players }),
      /* @__PURE__ */ r("div", { className: "grid grid-cols-1 lg:grid-cols-2 gap-6", children: [
        /* @__PURE__ */ t(L, { players: i.players }),
        /* @__PURE__ */ t(T, { players: i.players })
      ] })
    ] })
  ] });
}
export {
  W as default
};
