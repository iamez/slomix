import { r as j, j as e, S as k, c as u } from "./route-host-Ba3v8uFM.js";
import { k as _, l as A } from "./hooks-CyQgvbI9.js";
import { D as L } from "./DataTable-gbZQ6Kgl.js";
import { P as w } from "./PageHeader-CQ7BTOQj.js";
import { F as S, S as T } from "./FilterBar-BVrgiC-n.js";
import { f as g } from "./format-BM7Gaq4w.js";
import { a as h } from "./navigation-BDd1HkpE.js";
import { m as $, a as C, w as D } from "./game-assets-BMYaQb9B.js";
const v = {
  combat: { emoji: "⚔️", medal: "accuracy", color: "text-rose-400", bg: "bg-rose-500/10" },
  deaths: { emoji: "💀", color: "text-slate-400", bg: "bg-slate-700/50" },
  skills: { emoji: "🎯", medal: "light_weapons", color: "text-purple-400", bg: "bg-purple-500/10" },
  weapons: { emoji: "🔫", color: "text-blue-400", bg: "bg-blue-500/10" },
  teamwork: { emoji: "🤝", medal: "first_aid", color: "text-emerald-400", bg: "bg-emerald-500/10" },
  objectives: { emoji: "🚩", medal: "engineer", color: "text-amber-400", bg: "bg-amber-400/10" },
  timing: { emoji: "⏱️", color: "text-cyan-400", bg: "bg-cyan-500/10" }
};
function P(a) {
  const t = a.toLowerCase(), s = {
    smg: "mp40",
    thompson: "thompson",
    mp40: "mp40",
    sten: "sten",
    rifle: "kar98",
    garand: "garand",
    fg42: "fg42",
    k43: "k43",
    pistol: "luger",
    grenade: "grenade",
    knife: "knife",
    panzer: "panzerfaust",
    mortar: "mortar",
    mg42: "mg42",
    flamethrower: "flamethrower",
    sniper: "mauser",
    landmine: "landmine",
    dynamite: "dynamite",
    syringe: "syringe"
  };
  for (const [r, l] of Object.entries(s))
    if (t.includes(r)) return D(l);
  return null;
}
function E(a) {
  const t = a.toLowerCase();
  return t.includes("damage") || t.includes("k/d") || t.includes("kill") ? "combat" : t.includes("death") || t.includes("selfkill") || t.includes("gib") ? "deaths" : t.includes("headshot") || t.includes("accuracy") || t.includes("first blood") ? "skills" : t.includes("smg") || t.includes("rifle") || t.includes("pistol") || t.includes("grenade") || t.includes("knife") ? "weapons" : t.includes("revive") || t.includes("heal") || t.includes("ammo") || t.includes("assist") ? "teamwork" : t.includes("dynamite") || t.includes("objective") || t.includes("planted") || t.includes("defused") || t.includes("stolen") ? "objectives" : t.includes("time") || t.includes("playtime") || t.includes("respawn") ? "timing" : "combat";
}
const I = [
  { value: "", label: "All Time" },
  { value: "7", label: "Last 7 Days" },
  { value: "30", label: "Last 30 Days" },
  { value: "90", label: "Last 90 Days" }
], b = 24;
function M(a) {
  return a === 1 ? "🥇" : a === 2 ? "🥈" : a === 3 ? "🥉" : `#${a}`;
}
const R = [
  {
    key: "rank",
    label: "Rank",
    className: "w-16",
    render: (a, t) => /* @__PURE__ */ e.jsx("span", { className: u(
      "font-mono font-bold",
      t === 0 ? "text-amber-400" : t === 1 ? "text-slate-300" : t === 2 ? "text-amber-600" : "text-slate-500"
    ), children: M(t + 1) })
  },
  {
    key: "player",
    label: "Player",
    render: (a) => /* @__PURE__ */ e.jsx(
      "button",
      {
        className: "font-semibold text-white hover:text-blue-400 transition",
        onClick: (t) => {
          t.stopPropagation(), h(a.player);
        },
        children: a.player
      }
    )
  },
  {
    key: "award_count",
    label: "Awards",
    sortable: !0,
    sortValue: (a) => a.award_count,
    className: "font-mono text-brand-cyan font-bold text-right",
    render: (a) => g(a.award_count)
  },
  {
    key: "top_award",
    label: "Most Won",
    className: "text-slate-300",
    render: (a) => /* @__PURE__ */ e.jsxs("span", { children: [
      a.top_award || "-",
      a.top_award_count ? /* @__PURE__ */ e.jsxs("span", { className: "text-xs text-slate-500 ml-1", children: [
        "(",
        a.top_award_count,
        "x)"
      ] }) : null
    ] })
  }
];
function W({ awards: a }) {
  if (!a.length)
    return /* @__PURE__ */ e.jsx("div", { className: "text-center text-slate-500 py-10", children: "No awards found for this filter." });
  const t = /* @__PURE__ */ new Map();
  for (const s of a) {
    const r = `${s.round_id}:${s.date}:${s.map}:${s.round_number}`;
    t.has(r) || t.set(r, { round_id: s.round_id, date: s.date, map: s.map, round_number: s.round_number, awards: [] }), t.get(r).awards.push(s);
  }
  return /* @__PURE__ */ e.jsx("div", { className: "space-y-4", children: Array.from(t.values()).map((s) => {
    const r = s.date ? new Date(s.date).toLocaleDateString("en-US", { weekday: "short", month: "short", day: "numeric" }) : "";
    return /* @__PURE__ */ e.jsxs("div", { className: "glass-card rounded-xl overflow-hidden", children: [
      /* @__PURE__ */ e.jsxs("div", { className: "px-5 py-3 bg-slate-800/50 border-b border-white/5 flex items-center justify-between", children: [
        /* @__PURE__ */ e.jsxs("div", { className: "flex items-center gap-3", children: [
          /* @__PURE__ */ e.jsx("img", { src: $(s.map || ""), alt: "", className: "w-8 h-8 rounded object-cover bg-slate-700", onError: (l) => {
            l.currentTarget.style.display = "none";
          } }),
          /* @__PURE__ */ e.jsxs("div", { children: [
            /* @__PURE__ */ e.jsx("div", { className: "font-bold text-white", children: s.map || "Unknown Map" }),
            /* @__PURE__ */ e.jsxs("div", { className: "text-xs text-slate-500", children: [
              "Round ",
              s.round_number,
              " · ",
              r
            ] })
          ] })
        ] }),
        /* @__PURE__ */ e.jsxs("span", { className: "text-xs px-2 py-1 rounded-full bg-blue-500/20 text-blue-400", children: [
          s.awards.length,
          " awards"
        ] })
      ] }),
      /* @__PURE__ */ e.jsx("div", { className: "p-4 grid grid-cols-1 md:grid-cols-2 gap-3", children: s.awards.map((l, p) => {
        const o = E(l.award), d = v[o] ?? v.combat, c = o === "weapons" ? P(l.award) : null, n = !c && d.medal ? C(d.medal) : null;
        return /* @__PURE__ */ e.jsxs("div", { className: u("flex items-center gap-3 p-3 rounded-lg border border-white/5", d.bg), children: [
          c ? /* @__PURE__ */ e.jsx("img", { src: c, alt: "", className: "w-7 h-5 object-contain opacity-80 shrink-0", style: { filter: "brightness(1.6)" } }) : n ? /* @__PURE__ */ e.jsx("img", { src: n, alt: "", className: "w-6 h-6 object-contain shrink-0" }) : /* @__PURE__ */ e.jsx("span", { className: "text-lg", children: d.emoji }),
          /* @__PURE__ */ e.jsxs("div", { className: "min-w-0 flex-1", children: [
            /* @__PURE__ */ e.jsx("div", { className: "text-xs text-slate-400 truncate", children: l.award }),
            /* @__PURE__ */ e.jsx(
              "button",
              {
                className: "font-semibold text-white hover:text-blue-400 transition truncate block text-left w-full",
                onClick: () => h(l.player),
                children: l.player
              }
            )
          ] }),
          /* @__PURE__ */ e.jsx("div", { className: u("text-sm font-mono", d.color), children: String(l.value ?? "-") })
        ] }, `${l.award}-${l.player}-${p}`);
      }) })
    ] }, `${s.round_id}-${s.date}`);
  }) });
}
function H() {
  const [a, t] = j.useState(""), [s, r] = j.useState(0), { data: l, isLoading: p } = _({ days: a || void 0, limit: 20 }), { data: o, isLoading: d } = A({ days: a || void 0, limit: b, offset: s * b }), c = p || d, n = l?.leaderboard ?? [], y = o?.awards ?? [], f = o?.total ?? 0, m = Math.ceil(f / b);
  return c ? /* @__PURE__ */ e.jsxs("div", { className: "mt-6", children: [
    /* @__PURE__ */ e.jsx(w, { title: "Awards", subtitle: "Achievement tracking and explorer" }),
    /* @__PURE__ */ e.jsx(k, { variant: "card", count: 6 })
  ] }) : /* @__PURE__ */ e.jsxs("div", { className: "mt-6", children: [
    /* @__PURE__ */ e.jsx(w, { title: "Awards", subtitle: "Achievement tracking and explorer" }),
    /* @__PURE__ */ e.jsx(S, { children: /* @__PURE__ */ e.jsx(T, { label: "Time", value: a, onChange: (i) => {
      t(i), r(0);
    }, options: I, allLabel: "All Time" }) }),
    /* @__PURE__ */ e.jsxs("div", { className: "grid grid-cols-2 lg:grid-cols-4 gap-4 mb-6", children: [
      /* @__PURE__ */ e.jsxs("div", { className: "glass-card rounded-xl p-4", children: [
        /* @__PURE__ */ e.jsx("div", { className: "text-xs text-slate-500 uppercase font-bold", children: "Total Awards" }),
        /* @__PURE__ */ e.jsx("div", { className: "text-2xl font-black text-brand-cyan mt-1", children: g(f) })
      ] }),
      /* @__PURE__ */ e.jsxs("div", { className: "glass-card rounded-xl p-4", children: [
        /* @__PURE__ */ e.jsx("div", { className: "text-xs text-slate-500 uppercase font-bold", children: "Unique Winners" }),
        /* @__PURE__ */ e.jsx("div", { className: "text-2xl font-black text-brand-purple mt-1", children: n.length })
      ] }),
      /* @__PURE__ */ e.jsxs("div", { className: "glass-card rounded-xl p-4", children: [
        /* @__PURE__ */ e.jsx("div", { className: "text-xs text-slate-500 uppercase font-bold", children: "Top Winner" }),
        /* @__PURE__ */ e.jsx("div", { className: "text-sm font-black text-brand-gold mt-1 truncate", children: n[0]?.player ?? "-" }),
        /* @__PURE__ */ e.jsx("div", { className: "text-[11px] text-slate-500", children: n[0] ? `${g(n[0].award_count)} awards` : "" })
      ] }),
      /* @__PURE__ */ e.jsxs("div", { className: "glass-card rounded-xl p-4", children: [
        /* @__PURE__ */ e.jsx("div", { className: "text-xs text-slate-500 uppercase font-bold", children: "Period" }),
        /* @__PURE__ */ e.jsx("div", { className: "text-sm font-black text-white mt-1", children: a ? `Last ${a} days` : "All Time" })
      ] })
    ] }),
    /* @__PURE__ */ e.jsxs("div", { className: "glass-panel rounded-xl p-5 mb-6", children: [
      /* @__PURE__ */ e.jsx("h3", { className: "text-lg font-black text-white mb-4", children: "Awards Leaderboard" }),
      /* @__PURE__ */ e.jsx(
        L,
        {
          columns: R,
          data: n,
          keyFn: (i) => i.guid,
          onRowClick: (i) => h(i.player)
        }
      )
    ] }),
    /* @__PURE__ */ e.jsxs("div", { className: "glass-panel rounded-xl p-5", children: [
      /* @__PURE__ */ e.jsxs("div", { className: "flex items-center justify-between mb-4", children: [
        /* @__PURE__ */ e.jsx("h3", { className: "text-lg font-black text-white", children: "Award Explorer" }),
        /* @__PURE__ */ e.jsx("span", { className: "text-xs text-slate-500", children: "Grouped by round" })
      ] }),
      /* @__PURE__ */ e.jsx(W, { awards: y }),
      m > 1 && /* @__PURE__ */ e.jsxs("div", { className: "flex items-center justify-center gap-2 mt-6", children: [
        s > 0 && /* @__PURE__ */ e.jsx("button", { onClick: () => r(s - 1), className: "px-3 py-2 rounded-lg bg-slate-700 text-white hover:bg-slate-600 transition text-sm", children: "Prev" }),
        Array.from({ length: Math.min(5, m) }, (i, N) => {
          const x = Math.max(0, Math.min(s - 2, m - 5)) + N;
          return x >= m ? null : /* @__PURE__ */ e.jsx(
            "button",
            {
              onClick: () => r(x),
              className: u(
                "px-3 py-2 rounded-lg text-sm font-bold transition",
                x === s ? "bg-blue-500 text-white" : "bg-slate-700 text-slate-300 hover:bg-slate-600"
              ),
              children: x + 1
            },
            x
          );
        }),
        s < m - 1 && /* @__PURE__ */ e.jsx("button", { onClick: () => r(s + 1), className: "px-3 py-2 rounded-lg bg-slate-700 text-white hover:bg-slate-600 transition text-sm", children: "Next" })
      ] })
    ] })
  ] });
}
export {
  H as default
};
