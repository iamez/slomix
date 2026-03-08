import { jsxs as s, jsx as t } from "react/jsx-runtime";
import { useState as v } from "react";
import { i as j, j as A } from "./hooks-UFUMZFGB.js";
import { D as L } from "./DataTable-C9DYv6yb.js";
import { P as y } from "./PageHeader-D4CVo02x.js";
import { F as S, S as T } from "./FilterBar-ClDZvrPF.js";
import { S as $, c as b } from "./route-host-CUL1oI6Z.js";
import { f as h } from "./format-BM7Gaq4w.js";
import { a as f } from "./navigation-BDd1HkpE.js";
import { m as C, a as D, w as P } from "./game-assets-CWuRxGFH.js";
const N = {
  combat: { emoji: "⚔️", medal: "accuracy", color: "text-rose-400", bg: "bg-rose-500/10" },
  deaths: { emoji: "💀", color: "text-slate-400", bg: "bg-slate-700/50" },
  skills: { emoji: "🎯", medal: "light_weapons", color: "text-purple-400", bg: "bg-purple-500/10" },
  weapons: { emoji: "🔫", color: "text-blue-400", bg: "bg-blue-500/10" },
  teamwork: { emoji: "🤝", medal: "first_aid", color: "text-emerald-400", bg: "bg-emerald-500/10" },
  objectives: { emoji: "🚩", medal: "engineer", color: "text-amber-400", bg: "bg-amber-400/10" },
  timing: { emoji: "⏱️", color: "text-cyan-400", bg: "bg-cyan-500/10" }
};
function I(a) {
  const e = a.toLowerCase(), l = {
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
  for (const [n, r] of Object.entries(l))
    if (e.includes(n)) return P(r);
  return null;
}
function M(a) {
  const e = a.toLowerCase();
  return e.includes("damage") || e.includes("k/d") || e.includes("kill") ? "combat" : e.includes("death") || e.includes("selfkill") || e.includes("gib") ? "deaths" : e.includes("headshot") || e.includes("accuracy") || e.includes("first blood") ? "skills" : e.includes("smg") || e.includes("rifle") || e.includes("pistol") || e.includes("grenade") || e.includes("knife") ? "weapons" : e.includes("revive") || e.includes("heal") || e.includes("ammo") || e.includes("assist") ? "teamwork" : e.includes("dynamite") || e.includes("objective") || e.includes("planted") || e.includes("defused") || e.includes("stolen") ? "objectives" : e.includes("time") || e.includes("playtime") || e.includes("respawn") ? "timing" : "combat";
}
const E = [
  { value: "", label: "All Time" },
  { value: "7", label: "Last 7 Days" },
  { value: "30", label: "Last 30 Days" },
  { value: "90", label: "Last 90 Days" }
], x = 24;
function W(a) {
  return a === 1 ? "🥇" : a === 2 ? "🥈" : a === 3 ? "🥉" : `#${a}`;
}
const F = [
  {
    key: "rank",
    label: "Rank",
    className: "w-16",
    render: (a, e) => /* @__PURE__ */ t("span", { className: b(
      "font-mono font-bold",
      e === 0 ? "text-amber-400" : e === 1 ? "text-slate-300" : e === 2 ? "text-amber-600" : "text-slate-500"
    ), children: W(e + 1) })
  },
  {
    key: "player",
    label: "Player",
    render: (a) => /* @__PURE__ */ t(
      "button",
      {
        className: "font-semibold text-white hover:text-blue-400 transition",
        onClick: (e) => {
          e.stopPropagation(), f(a.player);
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
    render: (a) => h(a.award_count)
  },
  {
    key: "top_award",
    label: "Most Won",
    className: "text-slate-300",
    render: (a) => /* @__PURE__ */ s("span", { children: [
      a.top_award || "-",
      a.top_award_count ? /* @__PURE__ */ s("span", { className: "text-xs text-slate-500 ml-1", children: [
        "(",
        a.top_award_count,
        "x)"
      ] }) : null
    ] })
  }
];
function R({ awards: a }) {
  if (!a.length)
    return /* @__PURE__ */ t("div", { className: "text-center text-slate-500 py-10", children: "No awards found for this filter." });
  const e = /* @__PURE__ */ new Map();
  for (const l of a) {
    const n = `${l.round_id}:${l.date}:${l.map}:${l.round_number}`;
    e.has(n) || e.set(n, { round_id: l.round_id, date: l.date, map: l.map, round_number: l.round_number, awards: [] }), e.get(n).awards.push(l);
  }
  return /* @__PURE__ */ t("div", { className: "space-y-4", children: Array.from(e.values()).map((l) => {
    const n = l.date ? new Date(l.date).toLocaleDateString("en-US", { weekday: "short", month: "short", day: "numeric" }) : "";
    return /* @__PURE__ */ s("div", { className: "glass-card rounded-xl overflow-hidden", children: [
      /* @__PURE__ */ s("div", { className: "px-5 py-3 bg-slate-800/50 border-b border-white/5 flex items-center justify-between", children: [
        /* @__PURE__ */ s("div", { className: "flex items-center gap-3", children: [
          /* @__PURE__ */ t("img", { src: C(l.map || ""), alt: "", className: "w-8 h-8 rounded object-cover bg-slate-700", onError: (r) => {
            r.currentTarget.style.display = "none";
          } }),
          /* @__PURE__ */ s("div", { children: [
            /* @__PURE__ */ t("div", { className: "font-bold text-white", children: l.map || "Unknown Map" }),
            /* @__PURE__ */ s("div", { className: "text-xs text-slate-500", children: [
              "Round ",
              l.round_number,
              " · ",
              n
            ] })
          ] })
        ] }),
        /* @__PURE__ */ s("span", { className: "text-xs px-2 py-1 rounded-full bg-blue-500/20 text-blue-400", children: [
          l.awards.length,
          " awards"
        ] })
      ] }),
      /* @__PURE__ */ t("div", { className: "p-4 grid grid-cols-1 md:grid-cols-2 gap-3", children: l.awards.map((r, g) => {
        const c = M(r.award), d = N[c] ?? N.combat, m = c === "weapons" ? I(r.award) : null, i = !m && d.medal ? D(d.medal) : null;
        return /* @__PURE__ */ s("div", { className: b("flex items-center gap-3 p-3 rounded-lg border border-white/5", d.bg), children: [
          m ? /* @__PURE__ */ t("img", { src: m, alt: "", className: "w-7 h-5 object-contain opacity-80 shrink-0", style: { filter: "brightness(1.6)" } }) : i ? /* @__PURE__ */ t("img", { src: i, alt: "", className: "w-6 h-6 object-contain shrink-0" }) : /* @__PURE__ */ t("span", { className: "text-lg", children: d.emoji }),
          /* @__PURE__ */ s("div", { className: "min-w-0 flex-1", children: [
            /* @__PURE__ */ t("div", { className: "text-xs text-slate-400 truncate", children: r.award }),
            /* @__PURE__ */ t(
              "button",
              {
                className: "font-semibold text-white hover:text-blue-400 transition truncate block text-left w-full",
                onClick: () => f(r.player),
                children: r.player
              }
            )
          ] }),
          /* @__PURE__ */ t("div", { className: b("text-sm font-mono", d.color), children: String(r.value ?? "-") })
        ] }, `${r.award}-${r.player}-${g}`);
      }) })
    ] }, `${l.round_id}-${l.date}`);
  }) });
}
function Z() {
  const [a, e] = v(""), [l, n] = v(0), { data: r, isLoading: g } = j({ days: a || void 0, limit: 20 }), { data: c, isLoading: d } = A({ days: a || void 0, limit: x, offset: l * x }), m = g || d, i = r?.leaderboard ?? [], k = c?.awards ?? [], w = c?.total ?? 0, u = Math.ceil(w / x);
  return m ? /* @__PURE__ */ s("div", { className: "mt-6", children: [
    /* @__PURE__ */ t(y, { title: "Awards", subtitle: "Achievement tracking and explorer" }),
    /* @__PURE__ */ t($, { variant: "card", count: 6 })
  ] }) : /* @__PURE__ */ s("div", { className: "mt-6", children: [
    /* @__PURE__ */ t(y, { title: "Awards", subtitle: "Achievement tracking and explorer" }),
    /* @__PURE__ */ t(S, { children: /* @__PURE__ */ t(T, { label: "Time", value: a, onChange: (o) => {
      e(o), n(0);
    }, options: E, allLabel: "All Time" }) }),
    /* @__PURE__ */ s("div", { className: "grid grid-cols-2 lg:grid-cols-4 gap-4 mb-6", children: [
      /* @__PURE__ */ s("div", { className: "glass-card rounded-xl p-4", children: [
        /* @__PURE__ */ t("div", { className: "text-xs text-slate-500 uppercase font-bold", children: "Total Awards" }),
        /* @__PURE__ */ t("div", { className: "text-2xl font-black text-brand-cyan mt-1", children: h(w) })
      ] }),
      /* @__PURE__ */ s("div", { className: "glass-card rounded-xl p-4", children: [
        /* @__PURE__ */ t("div", { className: "text-xs text-slate-500 uppercase font-bold", children: "Unique Winners" }),
        /* @__PURE__ */ t("div", { className: "text-2xl font-black text-brand-purple mt-1", children: i.length })
      ] }),
      /* @__PURE__ */ s("div", { className: "glass-card rounded-xl p-4", children: [
        /* @__PURE__ */ t("div", { className: "text-xs text-slate-500 uppercase font-bold", children: "Top Winner" }),
        /* @__PURE__ */ t("div", { className: "text-sm font-black text-brand-gold mt-1 truncate", children: i[0]?.player ?? "-" }),
        /* @__PURE__ */ t("div", { className: "text-[11px] text-slate-500", children: i[0] ? `${h(i[0].award_count)} awards` : "" })
      ] }),
      /* @__PURE__ */ s("div", { className: "glass-card rounded-xl p-4", children: [
        /* @__PURE__ */ t("div", { className: "text-xs text-slate-500 uppercase font-bold", children: "Period" }),
        /* @__PURE__ */ t("div", { className: "text-sm font-black text-white mt-1", children: a ? `Last ${a} days` : "All Time" })
      ] })
    ] }),
    /* @__PURE__ */ s("div", { className: "glass-panel rounded-xl p-5 mb-6", children: [
      /* @__PURE__ */ t("h3", { className: "text-lg font-black text-white mb-4", children: "Awards Leaderboard" }),
      /* @__PURE__ */ t(
        L,
        {
          columns: F,
          data: i,
          keyFn: (o) => o.guid,
          onRowClick: (o) => f(o.player)
        }
      )
    ] }),
    /* @__PURE__ */ s("div", { className: "glass-panel rounded-xl p-5", children: [
      /* @__PURE__ */ s("div", { className: "flex items-center justify-between mb-4", children: [
        /* @__PURE__ */ t("h3", { className: "text-lg font-black text-white", children: "Award Explorer" }),
        /* @__PURE__ */ t("span", { className: "text-xs text-slate-500", children: "Grouped by round" })
      ] }),
      /* @__PURE__ */ t(R, { awards: k }),
      u > 1 && /* @__PURE__ */ s("div", { className: "flex items-center justify-center gap-2 mt-6", children: [
        l > 0 && /* @__PURE__ */ t("button", { onClick: () => n(l - 1), className: "px-3 py-2 rounded-lg bg-slate-700 text-white hover:bg-slate-600 transition text-sm", children: "Prev" }),
        Array.from({ length: Math.min(5, u) }, (o, _) => {
          const p = Math.max(0, Math.min(l - 2, u - 5)) + _;
          return p >= u ? null : /* @__PURE__ */ t(
            "button",
            {
              onClick: () => n(p),
              className: b(
                "px-3 py-2 rounded-lg text-sm font-bold transition",
                p === l ? "bg-blue-500 text-white" : "bg-slate-700 text-slate-300 hover:bg-slate-600"
              ),
              children: p + 1
            },
            p
          );
        }),
        l < u - 1 && /* @__PURE__ */ t("button", { onClick: () => n(l + 1), className: "px-3 py-2 rounded-lg bg-slate-700 text-white hover:bg-slate-600 transition text-sm", children: "Next" })
      ] })
    ] })
  ] });
}
export {
  Z as default
};
