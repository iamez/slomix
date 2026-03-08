import { jsxs as t, jsx as a } from "react/jsx-runtime";
import { useState as v, useMemo as g } from "react";
import { n as P, o as O, p as H } from "./hooks-UFUMZFGB.js";
import { G as k } from "./GlassCard-DKnnuJMt.js";
import { P as w } from "./PageHeader-D4CVo02x.js";
import { S as R, c as i } from "./route-host-CUL1oI6Z.js";
import { E as W } from "./EmptyState-DvtQr4qR.js";
import { f as d } from "./format-BM7Gaq4w.js";
import { a as C } from "./navigation-BDd1HkpE.js";
import { w as b } from "./game-assets-CWuRxGFH.js";
import { U as M } from "./users-CNuz17ri.js";
import { C as A } from "./crown-BFDJEIu0.js";
import { C as G } from "./crosshair-BCiyTdpP.js";
const L = [
  { value: "all", label: "All-time" },
  { value: "season", label: "Season" },
  { value: "30d", label: "30d" },
  { value: "7d", label: "7d" }
], T = {
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
}, h = {
  Melee: "text-amber-400 border-amber-400/30",
  Pistol: "text-slate-300 border-slate-400/30",
  SMG: "text-blue-400 border-blue-400/30",
  Rifle: "text-purple-400 border-purple-400/30",
  Heavy: "text-rose-400 border-rose-400/30",
  Explosive: "text-yellow-400 border-yellow-400/30",
  Support: "text-emerald-400 border-emerald-400/30",
  Other: "text-cyan-400 border-cyan-400/30"
}, F = ["all", "SMG", "Rifle", "Pistol", "Heavy", "Explosive", "Support", "Melee"];
function I(e) {
  return (e || "").toLowerCase().replace(/^ws[_\s]+/, "").replace(/[_\s]+/g, "");
}
function f(e) {
  return T[I(e)] ?? "Other";
}
function K(e) {
  return h[f(e)] ?? h.Other;
}
function z({ entry: e }) {
  const l = f(e.weapon), r = h[l] ?? h.Other, [o] = r.split(" "), n = b(e.weapon_key || e.weapon);
  return /* @__PURE__ */ t(
    k,
    {
      onClick: () => C(e.player_name),
      className: "relative overflow-hidden",
      children: [
        /* @__PURE__ */ t("div", { className: "flex items-center justify-between mb-3", children: [
          /* @__PURE__ */ a("span", { className: "text-[10px] uppercase tracking-wider text-slate-500 font-bold", children: l }),
          /* @__PURE__ */ t("div", { className: "flex items-center gap-2", children: [
            n && /* @__PURE__ */ a("img", { src: n, alt: e.weapon, className: "h-5 object-contain opacity-70", style: { filter: "brightness(1.8)" } }),
            /* @__PURE__ */ a("span", { className: i("text-xs font-bold", o), children: e.weapon })
          ] })
        ] }),
        /* @__PURE__ */ t("div", { className: "flex items-center gap-2 mb-1", children: [
          /* @__PURE__ */ a(A, { className: "w-4 h-4 text-yellow-500 shrink-0" }),
          /* @__PURE__ */ a("span", { className: "text-lg font-black text-white truncate", children: e.player_name })
        ] }),
        /* @__PURE__ */ t("div", { className: "text-xs text-slate-400", children: [
          d(e.kills),
          " kills · ",
          d(e.headshots),
          " HS · ",
          e.accuracy,
          "% acc"
        ] })
      ]
    }
  );
}
function D({ weapon: e, totalKills: l }) {
  const r = l > 0 ? e.kills / l * 100 : 0, o = K(e.name), [n, x] = o.split(" "), c = f(e.name), m = b(e.weapon_key || e.name);
  return /* @__PURE__ */ t("div", { className: i("glass-card p-5 rounded-xl border-l-4", x), children: [
    /* @__PURE__ */ t("div", { className: "flex items-center justify-between mb-3", children: [
      /* @__PURE__ */ a("span", { className: "px-2 py-0.5 rounded bg-slate-800 text-[10px] font-bold text-slate-400 uppercase", children: c }),
      m ? /* @__PURE__ */ a("img", { src: m, alt: e.name, className: "h-6 object-contain opacity-80 drop-shadow-lg", style: { filter: "brightness(1.8)" } }) : /* @__PURE__ */ a(G, { className: i("w-5 h-5", n) })
    ] }),
    /* @__PURE__ */ a("h3", { className: "text-lg font-black text-white mb-3", children: e.name }),
    /* @__PURE__ */ t("div", { className: "space-y-2 text-sm", children: [
      /* @__PURE__ */ t("div", { className: "flex justify-between", children: [
        /* @__PURE__ */ a("span", { className: "text-slate-400", children: "Kills" }),
        /* @__PURE__ */ a("span", { className: "font-bold text-white", children: d(e.kills) })
      ] }),
      /* @__PURE__ */ t("div", { className: "flex justify-between", children: [
        /* @__PURE__ */ a("span", { className: "text-slate-400", children: "HS Rate" }),
        /* @__PURE__ */ t("span", { className: "font-bold text-slate-300", children: [
          e.hs_rate,
          "%"
        ] })
      ] }),
      /* @__PURE__ */ t("div", { className: "flex justify-between", children: [
        /* @__PURE__ */ a("span", { className: "text-slate-400", children: "Accuracy" }),
        /* @__PURE__ */ t("span", { className: "font-bold text-slate-300", children: [
          e.accuracy,
          "%"
        ] })
      ] }),
      /* @__PURE__ */ t("div", { className: "flex justify-between", children: [
        /* @__PURE__ */ a("span", { className: "text-slate-400", children: "Usage" }),
        /* @__PURE__ */ t("span", { className: "font-mono text-slate-300", children: [
          r.toFixed(1),
          "%"
        ] })
      ] }),
      /* @__PURE__ */ a("div", { className: "w-full bg-slate-800 h-1.5 rounded-full overflow-hidden mt-1", children: /* @__PURE__ */ a(
        "div",
        {
          className: i("h-full rounded-full", n.replace("text-", "bg-")),
          style: { width: `${Math.min(r * 2, 100)}%` }
        }
      ) })
    ] })
  ] });
}
function U({ player: e }) {
  return /* @__PURE__ */ t(k, { onClick: () => C(e.player_name), children: [
    /* @__PURE__ */ t("div", { className: "flex items-start justify-between mb-3", children: [
      /* @__PURE__ */ t("div", { children: [
        /* @__PURE__ */ a("div", { className: "text-lg font-black text-white", children: e.player_name }),
        /* @__PURE__ */ t("div", { className: "text-[10px] text-slate-500 font-mono", children: [
          e.player_guid.slice(0, 12),
          "..."
        ] })
      ] }),
      /* @__PURE__ */ t("div", { className: "text-right", children: [
        /* @__PURE__ */ a("div", { className: "text-[10px] text-slate-500 uppercase", children: "Total Kills" }),
        /* @__PURE__ */ a("div", { className: "text-base font-black text-rose-400", children: d(e.total_kills) })
      ] })
    ] }),
    /* @__PURE__ */ a("div", { className: "space-y-1", children: e.weapons.map((l) => {
      const r = b(l.weapon_key || l.name);
      return /* @__PURE__ */ t("div", { className: "flex items-center justify-between text-xs py-1 border-b border-white/5 last:border-b-0", children: [
        /* @__PURE__ */ t("span", { className: "text-slate-300 font-semibold flex items-center gap-2", children: [
          r && /* @__PURE__ */ a("img", { src: r, alt: l.name, className: "h-3.5 object-contain opacity-60", style: { filter: "brightness(1.6)" } }),
          l.name
        ] }),
        /* @__PURE__ */ t("span", { className: "text-slate-500", children: [
          d(l.kills),
          "K · ",
          l.accuracy,
          "% ACC · ",
          l.hs_rate,
          "% HS"
        ] })
      ] }, l.weapon_key);
    }) })
  ] });
}
function le() {
  const [e, l] = v("all"), [r, o] = v("all"), { data: n, isLoading: x } = P(e), { data: c, isLoading: m } = O(e), { data: p, isLoading: S } = H(e), _ = x || m || S, y = g(() => {
    if (!c?.leaders) return [];
    const s = ["luger", "colt", "mp40", "thompson", "sten", "fg42", "garand", "k43", "kar98", "panzerfaust", "mortar", "grenade"];
    return Object.values(c.leaders).sort(
      (u, E) => s.indexOf(u.weapon_key) - s.indexOf(E.weapon_key)
    );
  }, [c]), N = g(() => n ? r === "all" ? n : n.filter((s) => f(s.name) === r) : [], [n, r]), j = g(
    () => (n ?? []).reduce((s, u) => s + u.kills, 0),
    [n]
  );
  return _ ? /* @__PURE__ */ t("div", { className: "mt-6", children: [
    /* @__PURE__ */ a(w, { title: "Weapon Arsenal", subtitle: "Detailed weapon statistics" }),
    /* @__PURE__ */ a(R, { variant: "card", count: 6, className: "grid-cols-3" })
  ] }) : /* @__PURE__ */ t("div", { className: "mt-6", children: [
    /* @__PURE__ */ a(w, { title: "Weapon Arsenal", subtitle: "Detailed weapon statistics", children: /* @__PURE__ */ a("div", { className: "flex gap-1 bg-slate-800 rounded-lg p-0.5", children: L.map((s) => /* @__PURE__ */ a(
      "button",
      {
        onClick: () => l(s.value),
        className: i(
          "px-3 py-1.5 rounded-md text-xs font-bold transition",
          e === s.value ? "bg-rose-500/20 text-rose-400" : "text-slate-400 hover:text-white"
        ),
        children: s.label
      },
      s.value
    )) }) }),
    y.length > 0 && /* @__PURE__ */ t("section", { className: "mb-8", children: [
      /* @__PURE__ */ a("h2", { className: "text-sm font-bold uppercase tracking-wider text-slate-500 mb-4", children: "Hall of Fame — Best per Weapon" }),
      /* @__PURE__ */ a("div", { className: "grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4 gap-4", children: y.map((s) => /* @__PURE__ */ a(z, { entry: s }, s.weapon_key)) })
    ] }),
    /* @__PURE__ */ a("div", { className: "flex flex-wrap justify-center gap-2 mb-6", children: F.map((s) => /* @__PURE__ */ a(
      "button",
      {
        onClick: () => o(s),
        className: i(
          "px-3 py-1.5 rounded-md text-xs font-bold transition",
          r === s ? "bg-rose-500 text-white shadow-lg" : "text-slate-400 hover:text-white"
        ),
        children: s === "all" ? "All Weapons" : s
      },
      s
    )) }),
    N.length === 0 ? /* @__PURE__ */ a(W, { message: "No weapons found for this filter." }) : /* @__PURE__ */ a("div", { className: "grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4 mb-10", children: N.map((s) => /* @__PURE__ */ a(D, { weapon: s, totalKills: j }, s.weapon_key || s.name)) }),
    p && p.players.length > 0 && /* @__PURE__ */ t("section", { children: [
      /* @__PURE__ */ t("h2", { className: "text-sm font-bold uppercase tracking-wider text-slate-500 mb-4 flex items-center gap-2", children: [
        /* @__PURE__ */ a(M, { className: "w-4 h-4" }),
        "Player Weapon Mastery — ",
        p.player_count,
        " players"
      ] }),
      /* @__PURE__ */ a("div", { className: "grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4", children: p.players.map((s) => /* @__PURE__ */ a(U, { player: s }, s.player_guid)) })
    ] })
  ] });
}
export {
  le as default
};
