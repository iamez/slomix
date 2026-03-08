import { jsxs as r, jsx as e } from "react/jsx-runtime";
import { useState as g } from "react";
import { d as k, e as w } from "./hooks-UFUMZFGB.js";
import { G as C } from "./GlassCard-DKnnuJMt.js";
import { P as p } from "./PageHeader-D4CVo02x.js";
import { S as _, c as n } from "./route-host-CUL1oI6Z.js";
import { E as S } from "./EmptyState-DvtQr4qR.js";
import { f as h, a as u } from "./format-BM7Gaq4w.js";
import { a as x } from "./navigation-BDd1HkpE.js";
import { S as j } from "./skull-BdPXKOvx.js";
import { Z as A, T as F } from "./zap-DJKgNY7d.js";
import { S as M, a as R } from "./swords-CDpW6o_n.js";
import { C as T } from "./crosshair-BCiyTdpP.js";
import { H } from "./heart-Be63oR7h.js";
import { B as q } from "./bomb-BF5aFt_5.js";
import { c as d } from "./createLucideIcon-CP-mMPfa.js";
import { S as E } from "./shield-DGUf4YlK.js";
import { X as P } from "./x-B9bYxG31.js";
const $ = [
  ["path", { d: "M5 12h14", key: "1ays0h" }],
  ["path", { d: "m12 5 7 7-7 7", key: "xquz4c" }]
], L = d("arrow-right", $);
const z = [
  ["path", { d: "M21.801 10A10 10 0 1 1 17 3.335", key: "yps3ct" }],
  ["path", { d: "m9 11 3 3L22 4", key: "1pflzl" }]
], B = d("circle-check-big", z);
const G = [
  [
    "path",
    {
      d: "M4 22V4a1 1 0 0 1 .4-.8A6 6 0 0 1 8 2c3 0 5 2 7.333 2q2 0 3.067-.8A1 1 0 0 1 20 4v10a1 1 0 0 1-.4.8A6 6 0 0 1 16 16c-3 0-5-2-8-2a6 6 0 0 0-4 1.528",
      key: "1jaruq"
    }
  ]
], I = d("flag", G);
const D = [
  [
    "path",
    {
      d: "M12 3q1 4 4 6.5t3 5.5a1 1 0 0 1-14 0 5 5 0 0 1 1-3 1 1 0 0 0 5 0c0-2-1.5-3-1.5-5q0-2 2.5-4",
      key: "1slcih"
    }
  ]
], O = d("flame", D), U = [
  { key: "kills", icon: j, color: "text-rose-500", bg: "bg-rose-500/10", border: "border-rose-500/20" },
  { key: "damage", icon: A, color: "text-blue-500", bg: "bg-blue-500/10", border: "border-blue-500/20" },
  { key: "xp", icon: M, color: "text-amber-400", bg: "bg-amber-400/10", border: "border-amber-400/20" },
  { key: "headshots", icon: T, color: "text-purple-500", bg: "bg-purple-500/10", border: "border-purple-500/20" },
  { key: "accuracy", icon: F, color: "text-emerald-500", bg: "bg-emerald-500/10", border: "border-emerald-500/20" },
  { key: "revives", icon: H, color: "text-cyan-500", bg: "bg-cyan-500/10", border: "border-cyan-500/20" },
  { key: "gibs", icon: q, color: "text-orange-500", bg: "bg-orange-500/10", border: "border-orange-500/20" },
  { key: "dyna_planted", icon: O, color: "text-red-500", bg: "bg-red-500/10", border: "border-red-500/20" },
  { key: "dyna_defused", icon: E, color: "text-blue-400", bg: "bg-blue-400/10", border: "border-blue-400/20" },
  { key: "obj_stolen", icon: I, color: "text-yellow-400", bg: "bg-yellow-400/10", border: "border-yellow-400/20" },
  { key: "obj_returned", icon: B, color: "text-green-400", bg: "bg-green-400/10", border: "border-green-400/20" },
  { key: "useful_kills", icon: R, color: "text-indigo-400", bg: "bg-indigo-400/10", border: "border-indigo-400/20" }
];
function f(a) {
  return a.replace(/_/g, " ");
}
function V({
  cat: a,
  records: s,
  onSelect: c
}) {
  if (!s || s.length === 0) return null;
  const t = s[0], i = a.icon, o = t.player.substring(0, 2).toUpperCase();
  return /* @__PURE__ */ r(C, { onClick: c, className: "relative overflow-hidden group", children: [
    /* @__PURE__ */ e("div", { className: "absolute top-0 right-0 p-4 opacity-10 group-hover:opacity-20 transition-opacity duration-500", children: /* @__PURE__ */ e(i, { className: n("w-16 h-16", a.color) }) }),
    /* @__PURE__ */ r("div", { className: "flex items-center gap-3 mb-4", children: [
      /* @__PURE__ */ e("div", { className: n("w-10 h-10 rounded-lg flex items-center justify-center border", a.bg, a.border), children: /* @__PURE__ */ e(i, { className: n("w-5 h-5", a.color) }) }),
      /* @__PURE__ */ e("div", { className: "text-sm font-bold text-slate-400 uppercase tracking-wider", children: f(a.key) })
    ] }),
    /* @__PURE__ */ r("div", { className: "mb-4", children: [
      /* @__PURE__ */ e("div", { className: "text-4xl font-black text-white mb-1 tracking-tight", children: h(t.value) }),
      /* @__PURE__ */ r("div", { className: "text-xs text-slate-500 font-mono flex items-center gap-2", children: [
        /* @__PURE__ */ e("span", { className: "bg-slate-800 px-1.5 py-0.5 rounded text-slate-400", children: t.map }),
        /* @__PURE__ */ e("span", { children: u(t.date) })
      ] })
    ] }),
    /* @__PURE__ */ r("div", { className: "flex items-center justify-between pt-4 border-t border-white/5", children: [
      /* @__PURE__ */ r("div", { className: "flex items-center gap-3", children: [
        /* @__PURE__ */ e("div", { className: "w-8 h-8 rounded bg-slate-800 flex items-center justify-center text-xs font-bold text-slate-400", children: o }),
        /* @__PURE__ */ e(
          "button",
          {
            className: "font-bold text-white group-hover:text-blue-400 transition",
            onClick: (m) => {
              m.stopPropagation(), x(t.player);
            },
            children: t.player
          }
        )
      ] }),
      /* @__PURE__ */ r("div", { className: "text-xs text-blue-400 font-medium opacity-0 group-hover:opacity-100 transition-opacity flex items-center gap-1", children: [
        "View Top 5 ",
        /* @__PURE__ */ e(L, { className: "w-3 h-3" })
      ] })
    ] })
  ] });
}
function Z({
  categoryKey: a,
  records: s,
  onClose: c
}) {
  return /* @__PURE__ */ e(
    "div",
    {
      className: "fixed inset-0 z-50 flex items-center justify-center bg-black/60 backdrop-blur-sm",
      onClick: c,
      children: /* @__PURE__ */ r(
        "div",
        {
          className: "glass-panel rounded-2xl p-6 w-full max-w-lg mx-4",
          onClick: (t) => t.stopPropagation(),
          children: [
            /* @__PURE__ */ r("div", { className: "flex items-center justify-between mb-6", children: [
              /* @__PURE__ */ r("h2", { className: "text-xl font-black text-white", children: [
                f(a).toUpperCase(),
                /* @__PURE__ */ e("span", { className: "text-slate-500 text-sm font-normal ml-2", children: "Top 5 All-Time" })
              ] }),
              /* @__PURE__ */ e(
                "button",
                {
                  className: "text-slate-400 hover:text-white transition",
                  onClick: c,
                  children: /* @__PURE__ */ e(P, { className: "w-5 h-5" })
                }
              )
            ] }),
            /* @__PURE__ */ e("div", { className: "space-y-2", children: s.map((t, i) => {
              const o = i === 0;
              return /* @__PURE__ */ r(
                "div",
                {
                  className: n(
                    "flex items-center justify-between p-3 rounded-lg border transition hover:bg-white/5",
                    o ? "bg-amber-400/10 border-amber-400/20" : "bg-slate-800/50 border-white/5"
                  ),
                  children: [
                    /* @__PURE__ */ r("div", { className: "flex items-center gap-4", children: [
                      /* @__PURE__ */ r(
                        "div",
                        {
                          className: n(
                            "font-mono font-bold text-lg w-6 text-center",
                            o ? "text-amber-400" : "text-slate-400"
                          ),
                          children: [
                            "#",
                            i + 1
                          ]
                        }
                      ),
                      /* @__PURE__ */ r("div", { className: "flex flex-col", children: [
                        /* @__PURE__ */ e(
                          "button",
                          {
                            className: n(
                              "font-bold text-white text-left hover:text-blue-400 transition",
                              o && "text-lg"
                            ),
                            onClick: () => x(t.player),
                            children: t.player
                          }
                        ),
                        /* @__PURE__ */ r("span", { className: "text-xs text-slate-500 font-mono", children: [
                          t.map,
                          " • ",
                          u(t.date)
                        ] })
                      ] })
                    ] }),
                    /* @__PURE__ */ e("div", { className: n("font-black text-white", o ? "text-2xl" : "text-xl"), children: h(t.value) })
                  ]
                },
                `${t.player}-${t.date}`
              );
            }) })
          ]
        }
      )
    }
  );
}
function be({ params: a }) {
  const [s, c] = g(""), [t, i] = g(null), { data: o, isLoading: m, isError: y } = k(s || void 0), { data: v } = w();
  if (m)
    return /* @__PURE__ */ r("div", { className: "mt-6", children: [
      /* @__PURE__ */ e(p, { title: "Hall of Fame", subtitle: "All-time records" }),
      /* @__PURE__ */ e(_, { variant: "card", count: 8 })
    ] });
  if (y)
    return /* @__PURE__ */ r("div", { className: "mt-6", children: [
      /* @__PURE__ */ e(p, { title: "Hall of Fame", subtitle: "All-time records" }),
      /* @__PURE__ */ e("div", { className: "text-center text-red-400 py-12", children: "Failed to load records." })
    ] });
  const N = o && Object.keys(o).length > 0;
  return /* @__PURE__ */ r("div", { className: "mt-6", children: [
    /* @__PURE__ */ e(p, { title: "Hall of Fame", subtitle: "All-time records", children: /* @__PURE__ */ r(
      "select",
      {
        value: s,
        onChange: (l) => c(l.target.value),
        className: "bg-slate-800 border border-white/10 text-slate-200 rounded-lg px-3 py-2 text-sm focus:outline-none focus:border-blue-500/50",
        children: [
          /* @__PURE__ */ e("option", { value: "", children: "All Maps" }),
          v?.map((l) => /* @__PURE__ */ e("option", { value: l, children: l }, l))
        ]
      }
    ) }),
    N ? /* @__PURE__ */ e("div", { className: "grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4 gap-4", children: U.map((l) => {
      const b = o[l.key];
      return !b || b.length === 0 ? null : /* @__PURE__ */ e(
        V,
        {
          cat: l,
          records: b,
          onSelect: () => i(l.key)
        },
        l.key
      );
    }) }) : /* @__PURE__ */ e(S, { message: "No records found for this selection." }),
    t && o?.[t] && /* @__PURE__ */ e(
      Z,
      {
        categoryKey: t,
        records: o[t],
        onClose: () => i(null)
      }
    )
  ] });
}
export {
  be as default
};
