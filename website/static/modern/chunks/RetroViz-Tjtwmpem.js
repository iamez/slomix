import { r as i, j as e, S as v, c as j } from "./route-host-Ba3v8uFM.js";
import { t as _, v as N } from "./hooks-CyQgvbI9.js";
import { C as x } from "./Chart-DkWq45SK.js";
import { P as h } from "./PageHeader-CQ7BTOQj.js";
import { E as f } from "./EmptyState-CWT5OHyQ.js";
import { D as k } from "./DataTable-gbZQ6Kgl.js";
import { f as g } from "./format-BM7Gaq4w.js";
import { a as M } from "./navigation-BDd1HkpE.js";
import { m as D } from "./game-assets-BMYaQb9B.js";
const c = [
  "rgba(59, 130, 246, 0.7)",
  "rgba(244, 63, 94, 0.7)",
  "rgba(16, 185, 129, 0.7)",
  "rgba(245, 158, 11, 0.7)",
  "rgba(168, 85, 247, 0.7)"
];
function y(a) {
  return a === 0 ? "R0 (summary)" : `R${a}`;
}
function w({ data: a }) {
  const s = a.highlights, r = a.winner_team === 1 ? "Axis" : a.winner_team === 2 ? "Allies" : "Tied", t = a.winner_team === 1 ? "text-rose-400" : a.winner_team === 2 ? "text-blue-400" : "text-slate-400", n = a.duration_seconds ? `${Math.round(a.duration_seconds / 60)}m` : "--";
  return /* @__PURE__ */ e.jsxs("div", { className: "glass-card rounded-xl p-5", children: [
    /* @__PURE__ */ e.jsx("h3", { className: "text-sm font-bold text-white mb-4", children: "Match Summary" }),
    /* @__PURE__ */ e.jsxs("div", { className: "grid grid-cols-2 gap-3 text-sm", children: [
      /* @__PURE__ */ e.jsxs("div", { className: "glass-panel rounded-lg p-3 flex items-center gap-2", children: [
        /* @__PURE__ */ e.jsx("img", { src: D(a.map_name || ""), alt: "", className: "w-8 h-8 rounded object-cover bg-slate-700", onError: (o) => {
          o.currentTarget.style.display = "none";
        } }),
        /* @__PURE__ */ e.jsxs("div", { children: [
          /* @__PURE__ */ e.jsx("div", { className: "text-[11px] text-slate-500", children: "Map" }),
          /* @__PURE__ */ e.jsx("div", { className: "font-bold text-white", children: a.map_name || "Unknown" })
        ] })
      ] }),
      /* @__PURE__ */ e.jsx(u, { label: "Round", value: a.round_label || y(a.round_number) }),
      /* @__PURE__ */ e.jsx(u, { label: "Date", value: a.round_date || "--" }),
      /* @__PURE__ */ e.jsx(u, { label: "Duration", value: n }),
      /* @__PURE__ */ e.jsx(u, { label: "Players", value: String(a.player_count) }),
      /* @__PURE__ */ e.jsxs("div", { className: "glass-panel rounded-lg p-3", children: [
        /* @__PURE__ */ e.jsx("div", { className: "text-[11px] text-slate-500", children: "Winner" }),
        /* @__PURE__ */ e.jsx("div", { className: j("font-bold", t), children: r })
      ] })
    ] }),
    (s.mvp || s.most_kills || s.most_damage) && /* @__PURE__ */ e.jsxs("div", { className: "mt-4 grid grid-cols-3 gap-2", children: [
      s.mvp && /* @__PURE__ */ e.jsx(p, { label: "MVP (DPM)", name: s.mvp.name, value: Math.round(s.mvp.dpm), color: "text-yellow-500" }),
      s.most_kills && /* @__PURE__ */ e.jsx(p, { label: "Most Kills", name: s.most_kills.name, value: s.most_kills.kills, color: "text-rose-400" }),
      s.most_damage && /* @__PURE__ */ e.jsx(p, { label: "Most Damage", name: s.most_damage.name, value: g(s.most_damage.damage_given), color: "text-orange-400" })
    ] })
  ] });
}
function u({ label: a, value: s }) {
  return /* @__PURE__ */ e.jsxs("div", { className: "glass-panel rounded-lg p-3", children: [
    /* @__PURE__ */ e.jsx("div", { className: "text-[11px] text-slate-500", children: a }),
    /* @__PURE__ */ e.jsx("div", { className: "text-white font-bold", children: s })
  ] });
}
function p({ label: a, name: s, value: r, color: t }) {
  return /* @__PURE__ */ e.jsxs("div", { className: "glass-panel rounded-lg p-2 text-center", children: [
    /* @__PURE__ */ e.jsx("div", { className: j("text-[10px]", t), children: a }),
    /* @__PURE__ */ e.jsx("div", { className: "text-xs text-white font-bold truncate", children: s }),
    /* @__PURE__ */ e.jsx("div", { className: "text-[10px] text-slate-400", children: r })
  ] });
}
function C({ players: a }) {
  const s = i.useMemo(
    () => [...a].sort((t, n) => n.dpm - t.dpm).slice(0, 5),
    [a]
  ), r = i.useMemo(() => {
    if (s.length === 0) return null;
    const t = Math.max(...s.map((l) => l.kills), 1), n = Math.max(...s.map((l) => l.deaths), 1), o = Math.max(...s.map((l) => l.dpm), 1), b = Math.max(...s.map((l) => l.damage_given), 1), d = Math.max(...s.map((l) => l.gibs), 1);
    return {
      labels: ["Kills", "Deaths(inv)", "DPM", "Damage", "Efficiency", "Gibs"],
      datasets: s.map((l, m) => ({
        label: l.name,
        data: [
          Math.round(l.kills / t * 100),
          Math.round((1 - l.deaths / n) * 100),
          Math.round(l.dpm / o * 100),
          Math.round(l.damage_given / b * 100),
          Math.round(l.efficiency),
          Math.round(l.gibs / d * 100)
        ],
        backgroundColor: c[m % c.length],
        borderColor: c[m % c.length],
        borderWidth: 2
      }))
    };
  }, [s]);
  return r ? /* @__PURE__ */ e.jsxs("div", { className: "glass-card rounded-xl p-5", children: [
    /* @__PURE__ */ e.jsx("h3", { className: "text-sm font-bold text-white mb-4", children: "Combat Overview" }),
    /* @__PURE__ */ e.jsx(
      x,
      {
        type: "radar",
        data: r,
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
function R({ players: a }) {
  const s = i.useMemo(() => [...a].sort((t, n) => n.kills - t.kills), [a]), r = i.useMemo(() => ({
    labels: s.map((t) => t.name),
    datasets: [
      {
        label: "Kills",
        data: s.map((t) => t.kills),
        backgroundColor: "rgba(59, 130, 246, 0.7)"
      },
      {
        label: "Deaths",
        data: s.map((t) => t.deaths),
        backgroundColor: "rgba(244, 63, 94, 0.5)"
      }
    ]
  }), [s]);
  return /* @__PURE__ */ e.jsxs("div", { className: "glass-card rounded-xl p-5", children: [
    /* @__PURE__ */ e.jsx("h3", { className: "text-sm font-bold text-white mb-4", children: "Top Fraggers" }),
    /* @__PURE__ */ e.jsx(
      x,
      {
        type: "bar",
        data: r,
        height: Math.max(200, a.length * 32),
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
function S({ players: a }) {
  const s = i.useMemo(
    () => [...a].sort((t, n) => n.revives_given - t.revives_given),
    [a]
  ), r = i.useMemo(() => ({
    labels: s.map((t) => t.name),
    datasets: [
      {
        label: "Revives",
        data: s.map((t) => t.revives_given),
        backgroundColor: "rgba(16, 185, 129, 0.7)"
      },
      {
        label: "Gibs",
        data: s.map((t) => t.gibs),
        backgroundColor: "rgba(168, 85, 247, 0.5)"
      },
      {
        label: "Self Kills",
        data: s.map((t) => t.self_kills),
        backgroundColor: "rgba(245, 158, 11, 0.5)"
      }
    ]
  }), [s]);
  return /* @__PURE__ */ e.jsxs("div", { className: "glass-card rounded-xl p-5", children: [
    /* @__PURE__ */ e.jsx("h3", { className: "text-sm font-bold text-white mb-4", children: "Support Performance" }),
    /* @__PURE__ */ e.jsx(
      x,
      {
        type: "bar",
        data: r,
        height: Math.max(200, a.length * 36),
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
function z({ players: a }) {
  const s = i.useMemo(
    () => [...a].sort((t, n) => n.time_played_seconds - t.time_played_seconds),
    [a]
  ), r = i.useMemo(() => ({
    labels: s.map((t) => t.name),
    datasets: [
      {
        label: "Alive (s)",
        data: s.map((t) => Math.max(0, t.time_played_seconds - t.time_dead_seconds)),
        backgroundColor: "rgba(34, 197, 94, 0.7)"
      },
      {
        label: "Dead (s)",
        data: s.map((t) => t.time_dead_seconds),
        backgroundColor: "rgba(100, 116, 139, 0.5)"
      }
    ]
  }), [s]);
  return /* @__PURE__ */ e.jsxs("div", { className: "glass-card rounded-xl p-5", children: [
    /* @__PURE__ */ e.jsx("h3", { className: "text-sm font-bold text-white mb-4", children: "Time Distribution" }),
    /* @__PURE__ */ e.jsx(
      x,
      {
        type: "bar",
        data: r,
        height: Math.max(200, a.length * 32),
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
const P = [
  {
    key: "name",
    label: "Player",
    render: (a) => /* @__PURE__ */ e.jsx("button", { onClick: () => M(a.name), className: "text-blue-400 hover:text-blue-300 font-semibold text-left", children: a.name })
  },
  { key: "damage_given", label: "Dmg Given", sortable: !0, sortValue: (a) => a.damage_given, className: "font-mono text-white", render: (a) => g(a.damage_given) },
  { key: "damage_received", label: "Dmg Recv", sortable: !0, sortValue: (a) => a.damage_received, className: "font-mono text-slate-400", render: (a) => g(a.damage_received) },
  { key: "team_damage_given", label: "Team Dmg", sortable: !0, sortValue: (a) => a.team_damage_given, className: "font-mono text-amber-400", render: (a) => g(a.team_damage_given) },
  { key: "dpm", label: "DPM", sortable: !0, sortValue: (a) => a.dpm, className: "font-mono text-cyan-400", render: (a) => a.dpm.toFixed(1) },
  { key: "efficiency", label: "Eff%", sortable: !0, sortValue: (a) => a.efficiency, className: "font-mono text-emerald-400", render: (a) => `${a.efficiency.toFixed(0)}%` }
];
function L({ players: a }) {
  return /* @__PURE__ */ e.jsxs("div", { className: "glass-card rounded-xl p-5", children: [
    /* @__PURE__ */ e.jsx("h3", { className: "text-sm font-bold text-white mb-4", children: "Damage Breakdown" }),
    /* @__PURE__ */ e.jsx("div", { className: "overflow-x-auto", children: /* @__PURE__ */ e.jsx(
      k,
      {
        columns: P,
        data: a,
        keyFn: (s) => s.guid,
        defaultSort: { key: "damage_given", dir: "desc" }
      }
    ) })
  ] });
}
function O() {
  const { data: a, isLoading: s } = _(50), [r, t] = i.useState(null), n = r ?? a?.[0]?.id ?? null, { data: o, isLoading: b } = N(n);
  if (s)
    return /* @__PURE__ */ e.jsxs("div", { className: "mt-6", children: [
      /* @__PURE__ */ e.jsx(h, { title: "Round Visualizer", subtitle: "Interactive round-by-round combat analytics" }),
      /* @__PURE__ */ e.jsx(v, { variant: "card", count: 4 })
    ] });
  const d = (a ?? []).filter((l) => l.round_number > 0);
  return d.length === 0 ? /* @__PURE__ */ e.jsxs("div", { className: "mt-6", children: [
    /* @__PURE__ */ e.jsx(h, { title: "Round Visualizer", subtitle: "Interactive round-by-round combat analytics" }),
    /* @__PURE__ */ e.jsx(f, { message: "No round data found. Play some rounds first!" })
  ] }) : /* @__PURE__ */ e.jsxs("div", { className: "mt-6", children: [
    /* @__PURE__ */ e.jsx(h, { title: "Round Visualizer", subtitle: "Interactive round-by-round combat analytics", children: /* @__PURE__ */ e.jsx(
      "select",
      {
        value: n ?? "",
        onChange: (l) => t(Number(l.target.value)),
        className: `bg-slate-800 border border-white/10 text-slate-200 rounded-lg px-3 py-2 text-sm
                     focus:outline-none focus:border-cyan-500/50 min-w-[320px]`,
        children: d.map((l) => {
          const m = l.round_date ? (/* @__PURE__ */ new Date(l.round_date + "T00:00:00")).toLocaleDateString("en-US", { month: "short", day: "numeric", year: "numeric" }) : "";
          return /* @__PURE__ */ e.jsxs("option", { value: l.id, children: [
            l.map_name || "Unknown",
            " ",
            l.round_label || y(l.round_number),
            " — ",
            m,
            " (",
            l.player_count,
            " players)"
          ] }, l.id);
        })
      }
    ) }),
    b ? /* @__PURE__ */ e.jsx(v, { variant: "card", count: 6, className: "grid-cols-2" }) : !o || o.players.length === 0 ? /* @__PURE__ */ e.jsx(f, { message: "No player data for this round." }) : /* @__PURE__ */ e.jsxs("div", { className: "space-y-6", children: [
      /* @__PURE__ */ e.jsxs("div", { className: "grid grid-cols-1 lg:grid-cols-2 gap-6", children: [
        /* @__PURE__ */ e.jsx(w, { data: o }),
        /* @__PURE__ */ e.jsx(C, { players: o.players })
      ] }),
      /* @__PURE__ */ e.jsx(R, { players: o.players }),
      /* @__PURE__ */ e.jsx(L, { players: o.players }),
      /* @__PURE__ */ e.jsxs("div", { className: "grid grid-cols-1 lg:grid-cols-2 gap-6", children: [
        /* @__PURE__ */ e.jsx(S, { players: o.players }),
        /* @__PURE__ */ e.jsx(z, { players: o.players })
      ] })
    ] })
  ] });
}
export {
  O as default
};
