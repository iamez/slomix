import { r as c, j as e, S as _, c as n } from "./route-host-Ba3v8uFM.js";
import { q as E, r as M, s as P } from "./hooks-CyQgvbI9.js";
import { G as N } from "./GlassCard-C53TzD-y.js";
import { P as y } from "./PageHeader-CQ7BTOQj.js";
import { E as O } from "./EmptyState-CWT5OHyQ.js";
import { f as d } from "./format-BM7Gaq4w.js";
import { a as v } from "./navigation-BDd1HkpE.js";
import { w as g } from "./game-assets-BMYaQb9B.js";
import { U as R } from "./users-Blp4mgkM.js";
import { C as H } from "./crown-DSN73Z2P.js";
import { C as W } from "./crosshair-CPb1OWqx.js";
const A = [
  { value: "all", label: "All-time" },
  { value: "season", label: "Season" },
  { value: "30d", label: "30d" },
  { value: "7d", label: "7d" }
], G = {
  knife: "Melee",
  luger: "Pistol",
  colt: "Pistol",
  mp40: "SMG",
  thompson: "SMG",
  sten: "SMG",
  fg42: "Rifle",
  garand: "Rifle",
  k43: "Rifle",
  kar98: "Rifle",
  panzerfaust: "Heavy",
  flamethrower: "Heavy",
  mortar: "Heavy",
  mg42: "Heavy",
  grenade: "Explosive",
  dynamite: "Explosive",
  landmine: "Explosive",
  airstrike: "Support",
  artillery: "Support",
  syringe: "Support",
  smokegrenade: "Support"
}, p = {
  Melee: "text-amber-400 border-amber-400/30",
  Pistol: "text-slate-300 border-slate-400/30",
  SMG: "text-blue-400 border-blue-400/30",
  Rifle: "text-purple-400 border-purple-400/30",
  Heavy: "text-rose-400 border-rose-400/30",
  Explosive: "text-yellow-400 border-yellow-400/30",
  Support: "text-emerald-400 border-emerald-400/30",
  Other: "text-cyan-400 border-cyan-400/30"
}, L = ["all", "SMG", "Rifle", "Pistol", "Heavy", "Explosive", "Support", "Melee"];
function T(s) {
  return (s || "").toLowerCase().replace(/^ws[_\s]+/, "").replace(/[_\s]+/g, "");
}
function h(s) {
  return G[T(s)] ?? "Other";
}
function F(s) {
  return p[h(s)] ?? p.Other;
}
function I({ entry: s }) {
  const t = h(s.weapon), l = p[t] ?? p.Other, [o] = l.split(" "), r = g(s.weapon_key || s.weapon);
  return /* @__PURE__ */ e.jsxs(
    N,
    {
      onClick: () => v(s.player_name),
      className: "relative overflow-hidden",
      children: [
        /* @__PURE__ */ e.jsxs("div", { className: "flex items-center justify-between mb-3", children: [
          /* @__PURE__ */ e.jsx("span", { className: "text-[10px] uppercase tracking-wider text-slate-500 font-bold", children: t }),
          /* @__PURE__ */ e.jsxs("div", { className: "flex items-center gap-2", children: [
            r && /* @__PURE__ */ e.jsx("img", { src: r, alt: s.weapon, className: "h-5 object-contain opacity-70", style: { filter: "brightness(1.8)" } }),
            /* @__PURE__ */ e.jsx("span", { className: n("text-xs font-bold", o), children: s.weapon })
          ] })
        ] }),
        /* @__PURE__ */ e.jsxs("div", { className: "flex items-center gap-2 mb-1", children: [
          /* @__PURE__ */ e.jsx(H, { className: "w-4 h-4 text-yellow-500 shrink-0" }),
          /* @__PURE__ */ e.jsx("span", { className: "text-lg font-black text-white truncate", children: s.player_name })
        ] }),
        /* @__PURE__ */ e.jsxs("div", { className: "text-xs text-slate-400", children: [
          d(s.kills),
          " kills · ",
          d(s.headshots),
          " HS · ",
          s.accuracy,
          "% acc"
        ] })
      ]
    }
  );
}
function K({ weapon: s, totalKills: t }) {
  const l = t > 0 ? s.kills / t * 100 : 0, o = F(s.name), [r, f] = o.split(" "), i = h(s.name), x = g(s.weapon_key || s.name);
  return /* @__PURE__ */ e.jsxs("div", { className: n("glass-card p-5 rounded-xl border-l-4", f), children: [
    /* @__PURE__ */ e.jsxs("div", { className: "flex items-center justify-between mb-3", children: [
      /* @__PURE__ */ e.jsx("span", { className: "px-2 py-0.5 rounded bg-slate-800 text-[10px] font-bold text-slate-400 uppercase", children: i }),
      x ? /* @__PURE__ */ e.jsx("img", { src: x, alt: s.name, className: "h-6 object-contain opacity-80 drop-shadow-lg", style: { filter: "brightness(1.8)" } }) : /* @__PURE__ */ e.jsx(W, { className: n("w-5 h-5", r) })
    ] }),
    /* @__PURE__ */ e.jsx("h3", { className: "text-lg font-black text-white mb-3", children: s.name }),
    /* @__PURE__ */ e.jsxs("div", { className: "space-y-2 text-sm", children: [
      /* @__PURE__ */ e.jsxs("div", { className: "flex justify-between", children: [
        /* @__PURE__ */ e.jsx("span", { className: "text-slate-400", children: "Kills" }),
        /* @__PURE__ */ e.jsx("span", { className: "font-bold text-white", children: d(s.kills) })
      ] }),
      /* @__PURE__ */ e.jsxs("div", { className: "flex justify-between", children: [
        /* @__PURE__ */ e.jsx("span", { className: "text-slate-400", children: "HS Rate" }),
        /* @__PURE__ */ e.jsxs("span", { className: "font-bold text-slate-300", children: [
          s.hs_rate,
          "%"
        ] })
      ] }),
      /* @__PURE__ */ e.jsxs("div", { className: "flex justify-between", children: [
        /* @__PURE__ */ e.jsx("span", { className: "text-slate-400", children: "Accuracy" }),
        /* @__PURE__ */ e.jsxs("span", { className: "font-bold text-slate-300", children: [
          s.accuracy,
          "%"
        ] })
      ] }),
      /* @__PURE__ */ e.jsxs("div", { className: "flex justify-between", children: [
        /* @__PURE__ */ e.jsx("span", { className: "text-slate-400", children: "Usage" }),
        /* @__PURE__ */ e.jsxs("span", { className: "font-mono text-slate-300", children: [
          l.toFixed(1),
          "%"
        ] })
      ] }),
      /* @__PURE__ */ e.jsx("div", { className: "w-full bg-slate-800 h-1.5 rounded-full overflow-hidden mt-1", children: /* @__PURE__ */ e.jsx(
        "div",
        {
          className: n("h-full rounded-full", r.replace("text-", "bg-")),
          style: { width: `${Math.min(l * 2, 100)}%` }
        }
      ) })
    ] })
  ] });
}
function z({ player: s }) {
  return /* @__PURE__ */ e.jsxs(N, { onClick: () => v(s.player_name), children: [
    /* @__PURE__ */ e.jsxs("div", { className: "flex items-start justify-between mb-3", children: [
      /* @__PURE__ */ e.jsxs("div", { children: [
        /* @__PURE__ */ e.jsx("div", { className: "text-lg font-black text-white", children: s.player_name }),
        /* @__PURE__ */ e.jsxs("div", { className: "text-[10px] text-slate-500 font-mono", children: [
          s.player_guid.slice(0, 12),
          "..."
        ] })
      ] }),
      /* @__PURE__ */ e.jsxs("div", { className: "text-right", children: [
        /* @__PURE__ */ e.jsx("div", { className: "text-[10px] text-slate-500 uppercase", children: "Total Kills" }),
        /* @__PURE__ */ e.jsx("div", { className: "text-base font-black text-rose-400", children: d(s.total_kills) })
      ] })
    ] }),
    /* @__PURE__ */ e.jsx("div", { className: "space-y-1", children: s.weapons.map((t) => {
      const l = g(t.weapon_key || t.name);
      return /* @__PURE__ */ e.jsxs("div", { className: "flex items-center justify-between text-xs py-1 border-b border-white/5 last:border-b-0", children: [
        /* @__PURE__ */ e.jsxs("span", { className: "text-slate-300 font-semibold flex items-center gap-2", children: [
          l && /* @__PURE__ */ e.jsx("img", { src: l, alt: t.name, className: "h-3.5 object-contain opacity-60", style: { filter: "brightness(1.6)" } }),
          t.name
        ] }),
        /* @__PURE__ */ e.jsxs("span", { className: "text-slate-500", children: [
          d(t.kills),
          "K · ",
          t.accuracy,
          "% ACC · ",
          t.hs_rate,
          "% HS"
        ] })
      ] }, t.weapon_key);
    }) })
  ] });
}
function ee() {
  const [s, t] = c.useState("all"), [l, o] = c.useState("all"), { data: r, isLoading: f } = E(s), { data: i, isLoading: x } = M(s), { data: m, isLoading: w } = P(s), k = f || x || w, j = c.useMemo(() => {
    if (!i?.leaders) return [];
    const a = ["luger", "colt", "mp40", "thompson", "sten", "fg42", "garand", "k43", "kar98", "panzerfaust", "mortar", "grenade"];
    return Object.values(i.leaders).sort(
      (u, S) => a.indexOf(u.weapon_key) - a.indexOf(S.weapon_key)
    );
  }, [i]), b = c.useMemo(() => r ? l === "all" ? r : r.filter((a) => h(a.name) === l) : [], [r, l]), C = c.useMemo(
    () => (r ?? []).reduce((a, u) => a + u.kills, 0),
    [r]
  );
  return k ? /* @__PURE__ */ e.jsxs("div", { className: "page-shell", children: [
    /* @__PURE__ */ e.jsx(y, { title: "Weapon Arsenal", subtitle: "Deeper weapon analysis once the main session/player path is done.", eyebrow: "More" }),
    /* @__PURE__ */ e.jsx(_, { variant: "card", count: 6, className: "grid-cols-3" })
  ] }) : /* @__PURE__ */ e.jsxs("div", { className: "page-shell", children: [
    /* @__PURE__ */ e.jsx(y, { title: "Weapon Arsenal", subtitle: "Detailed weapon statistics and per-player mastery.", eyebrow: "More", children: /* @__PURE__ */ e.jsx("div", { className: "flex gap-1 bg-slate-800 rounded-lg p-0.5", children: A.map((a) => /* @__PURE__ */ e.jsx(
      "button",
      {
        onClick: () => t(a.value),
        className: n(
          "px-3 py-1.5 rounded-md text-xs font-bold transition",
          s === a.value ? "bg-rose-500/20 text-rose-400" : "text-slate-400 hover:text-white"
        ),
        children: a.label
      },
      a.value
    )) }) }),
    j.length > 0 && /* @__PURE__ */ e.jsxs("section", { className: "mb-8", children: [
      /* @__PURE__ */ e.jsx("h2", { className: "text-sm font-bold uppercase tracking-wider text-slate-500 mb-4", children: "Hall of Fame — Best per Weapon" }),
      /* @__PURE__ */ e.jsx("div", { className: "grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4 gap-4", children: j.map((a) => /* @__PURE__ */ e.jsx(I, { entry: a }, a.weapon_key)) })
    ] }),
    /* @__PURE__ */ e.jsx("div", { className: "flex flex-wrap justify-center gap-2 mb-6", children: L.map((a) => /* @__PURE__ */ e.jsx(
      "button",
      {
        onClick: () => o(a),
        className: n(
          "px-3 py-1.5 rounded-md text-xs font-bold transition",
          l === a ? "bg-rose-500 text-white shadow-lg" : "text-slate-400 hover:text-white"
        ),
        children: a === "all" ? "All Weapons" : a
      },
      a
    )) }),
    b.length === 0 ? /* @__PURE__ */ e.jsx(O, { message: "No weapons found for this filter." }) : /* @__PURE__ */ e.jsx("div", { className: "grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4 mb-10", children: b.map((a) => /* @__PURE__ */ e.jsx(K, { weapon: a, totalKills: C }, a.weapon_key || a.name)) }),
    m && m.players.length > 0 && /* @__PURE__ */ e.jsxs("section", { children: [
      /* @__PURE__ */ e.jsxs("h2", { className: "text-sm font-bold uppercase tracking-wider text-slate-500 mb-4 flex items-center gap-2", children: [
        /* @__PURE__ */ e.jsx(R, { className: "w-4 h-4" }),
        "Player Weapon Mastery — ",
        m.player_count,
        " players"
      ] }),
      /* @__PURE__ */ e.jsx("div", { className: "grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4", children: m.players.map((a) => /* @__PURE__ */ e.jsx(z, { player: a }, a.player_guid)) })
    ] })
  ] });
}
export {
  ee as default
};
