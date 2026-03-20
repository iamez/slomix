import { r as b, j as e, S as v, c as i } from "./route-host-Ba3v8uFM.js";
import { f as N, g as k } from "./hooks-CyQgvbI9.js";
import { G as w } from "./GlassCard-C53TzD-y.js";
import { P as m } from "./PageHeader-CQ7BTOQj.js";
import { E as C } from "./EmptyState-CWT5OHyQ.js";
import { f as p, a as g } from "./format-BM7Gaq4w.js";
import { a as u } from "./navigation-BDd1HkpE.js";
import { S } from "./skull-BhM2GlAn.js";
import { Z as _ } from "./zap-Chh6-OiF.js";
import { S as A } from "./star-DzJ3yYFk.js";
import { C as F } from "./crosshair-CPb1OWqx.js";
import { T as R } from "./target-CZv2kTPB.js";
import { H as E, B as M } from "./heart-BlqPAczq.js";
import { c as x } from "./createLucideIcon-BebMLfof.js";
import { S as T } from "./shield-Bg1J0PTe.js";
import { S as H } from "./swords-BNai6XKn.js";
import { A as P } from "./arrow-right-DXUYYllJ.js";
import { X as q } from "./x-CUdvDzU_.js";
const L = [
  ["path", { d: "M21.801 10A10 10 0 1 1 17 3.335", key: "yps3ct" }],
  ["path", { d: "m9 11 3 3L22 4", key: "1pflzl" }]
], $ = x("circle-check-big", L);
const B = [
  [
    "path",
    {
      d: "M4 22V4a1 1 0 0 1 .4-.8A6 6 0 0 1 8 2c3 0 5 2 7.333 2q2 0 3.067-.8A1 1 0 0 1 20 4v10a1 1 0 0 1-.4.8A6 6 0 0 1 16 16c-3 0-5-2-8-2a6 6 0 0 0-4 1.528",
      key: "1jaruq"
    }
  ]
], G = x("flag", B);
const I = [
  [
    "path",
    {
      d: "M12 3q1 4 4 6.5t3 5.5a1 1 0 0 1-14 0 5 5 0 0 1 1-3 1 1 0 0 0 5 0c0-2-1.5-3-1.5-5q0-2 2.5-4",
      key: "1slcih"
    }
  ]
], z = x("flame", I), D = [
  { key: "kills", icon: S, color: "text-rose-500", bg: "bg-rose-500/10", border: "border-rose-500/20" },
  { key: "damage", icon: _, color: "text-blue-500", bg: "bg-blue-500/10", border: "border-blue-500/20" },
  { key: "xp", icon: A, color: "text-amber-400", bg: "bg-amber-400/10", border: "border-amber-400/20" },
  { key: "headshots", icon: F, color: "text-purple-500", bg: "bg-purple-500/10", border: "border-purple-500/20" },
  { key: "accuracy", icon: R, color: "text-emerald-500", bg: "bg-emerald-500/10", border: "border-emerald-500/20" },
  { key: "revives", icon: E, color: "text-cyan-500", bg: "bg-cyan-500/10", border: "border-cyan-500/20" },
  { key: "gibs", icon: M, color: "text-orange-500", bg: "bg-orange-500/10", border: "border-orange-500/20" },
  { key: "dyna_planted", icon: z, color: "text-red-500", bg: "bg-red-500/10", border: "border-red-500/20" },
  { key: "dyna_defused", icon: T, color: "text-blue-400", bg: "bg-blue-400/10", border: "border-blue-400/20" },
  { key: "obj_stolen", icon: G, color: "text-yellow-400", bg: "bg-yellow-400/10", border: "border-yellow-400/20" },
  { key: "obj_returned", icon: $, color: "text-green-400", bg: "bg-green-400/10", border: "border-green-400/20" },
  { key: "useful_kills", icon: H, color: "text-indigo-400", bg: "bg-indigo-400/10", border: "border-indigo-400/20" }
];
function h(s) {
  return s.replace(/_/g, " ");
}
function O({
  cat: s,
  records: a,
  onSelect: n
}) {
  if (!a || a.length === 0) return null;
  const t = a[0], l = s.icon, r = t.player.substring(0, 2).toUpperCase();
  return /* @__PURE__ */ e.jsxs(w, { onClick: n, className: "relative overflow-hidden group", children: [
    /* @__PURE__ */ e.jsx("div", { className: "absolute top-0 right-0 p-4 opacity-10 group-hover:opacity-20 transition-opacity duration-500", children: /* @__PURE__ */ e.jsx(l, { className: i("w-16 h-16", s.color) }) }),
    /* @__PURE__ */ e.jsxs("div", { className: "flex items-center gap-3 mb-4", children: [
      /* @__PURE__ */ e.jsx("div", { className: i("w-10 h-10 rounded-lg flex items-center justify-center border", s.bg, s.border), children: /* @__PURE__ */ e.jsx(l, { className: i("w-5 h-5", s.color) }) }),
      /* @__PURE__ */ e.jsx("div", { className: "text-sm font-bold text-slate-400 uppercase tracking-wider", children: h(s.key) })
    ] }),
    /* @__PURE__ */ e.jsxs("div", { className: "mb-4", children: [
      /* @__PURE__ */ e.jsx("div", { className: "text-4xl font-black text-white mb-1 tracking-tight", children: p(t.value) }),
      /* @__PURE__ */ e.jsxs("div", { className: "text-xs text-slate-500 font-mono flex items-center gap-2", children: [
        /* @__PURE__ */ e.jsx("span", { className: "bg-slate-800 px-1.5 py-0.5 rounded text-slate-400", children: t.map }),
        /* @__PURE__ */ e.jsx("span", { children: g(t.date) })
      ] })
    ] }),
    /* @__PURE__ */ e.jsxs("div", { className: "flex items-center justify-between pt-4 border-t border-white/5", children: [
      /* @__PURE__ */ e.jsxs("div", { className: "flex items-center gap-3", children: [
        /* @__PURE__ */ e.jsx("div", { className: "w-8 h-8 rounded bg-slate-800 flex items-center justify-center text-xs font-bold text-slate-400", children: r }),
        /* @__PURE__ */ e.jsx(
          "button",
          {
            className: "font-bold text-white group-hover:text-blue-400 transition",
            onClick: (c) => {
              c.stopPropagation(), u(t.player);
            },
            children: t.player
          }
        )
      ] }),
      /* @__PURE__ */ e.jsxs("div", { className: "text-xs text-blue-400 font-medium opacity-0 group-hover:opacity-100 transition-opacity flex items-center gap-1", children: [
        "View Top 5 ",
        /* @__PURE__ */ e.jsx(P, { className: "w-3 h-3" })
      ] })
    ] })
  ] });
}
function U({
  categoryKey: s,
  records: a,
  onClose: n
}) {
  return /* @__PURE__ */ e.jsx(
    "div",
    {
      className: "fixed inset-0 z-50 flex items-center justify-center bg-black/60 backdrop-blur-sm",
      onClick: n,
      children: /* @__PURE__ */ e.jsxs(
        "div",
        {
          className: "glass-panel rounded-2xl p-6 w-full max-w-lg mx-4",
          onClick: (t) => t.stopPropagation(),
          children: [
            /* @__PURE__ */ e.jsxs("div", { className: "flex items-center justify-between mb-6", children: [
              /* @__PURE__ */ e.jsxs("h2", { className: "text-xl font-black text-white", children: [
                h(s).toUpperCase(),
                /* @__PURE__ */ e.jsx("span", { className: "text-slate-500 text-sm font-normal ml-2", children: "Top 5 All-Time" })
              ] }),
              /* @__PURE__ */ e.jsx(
                "button",
                {
                  className: "text-slate-400 hover:text-white transition",
                  onClick: n,
                  children: /* @__PURE__ */ e.jsx(q, { className: "w-5 h-5" })
                }
              )
            ] }),
            /* @__PURE__ */ e.jsx("div", { className: "space-y-2", children: a.map((t, l) => {
              const r = l === 0;
              return /* @__PURE__ */ e.jsxs(
                "div",
                {
                  className: i(
                    "flex items-center justify-between p-3 rounded-lg border transition hover:bg-white/5",
                    r ? "bg-amber-400/10 border-amber-400/20" : "bg-slate-800/50 border-white/5"
                  ),
                  children: [
                    /* @__PURE__ */ e.jsxs("div", { className: "flex items-center gap-4", children: [
                      /* @__PURE__ */ e.jsxs(
                        "div",
                        {
                          className: i(
                            "font-mono font-bold text-lg w-6 text-center",
                            r ? "text-amber-400" : "text-slate-400"
                          ),
                          children: [
                            "#",
                            l + 1
                          ]
                        }
                      ),
                      /* @__PURE__ */ e.jsxs("div", { className: "flex flex-col", children: [
                        /* @__PURE__ */ e.jsx(
                          "button",
                          {
                            className: i(
                              "font-bold text-white text-left hover:text-blue-400 transition",
                              r && "text-lg"
                            ),
                            onClick: () => u(t.player),
                            children: t.player
                          }
                        ),
                        /* @__PURE__ */ e.jsxs("span", { className: "text-xs text-slate-500 font-mono", children: [
                          t.map,
                          " • ",
                          g(t.date)
                        ] })
                      ] })
                    ] }),
                    /* @__PURE__ */ e.jsx("div", { className: i("font-black text-white", r ? "text-2xl" : "text-xl"), children: p(t.value) })
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
function de({ params: s }) {
  const [a, n] = b.useState(""), [t, l] = b.useState(null), { data: r, isLoading: c, isError: f } = N(a || void 0), { data: j } = k();
  if (c)
    return /* @__PURE__ */ e.jsxs("div", { className: "mt-6", children: [
      /* @__PURE__ */ e.jsx(m, { title: "Hall of Fame", subtitle: "All-time records" }),
      /* @__PURE__ */ e.jsx(v, { variant: "card", count: 8 })
    ] });
  if (f)
    return /* @__PURE__ */ e.jsxs("div", { className: "mt-6", children: [
      /* @__PURE__ */ e.jsx(m, { title: "Hall of Fame", subtitle: "All-time records" }),
      /* @__PURE__ */ e.jsx("div", { className: "text-center text-red-400 py-12", children: "Failed to load records." })
    ] });
  const y = r && Object.keys(r).length > 0;
  return /* @__PURE__ */ e.jsxs("div", { className: "mt-6", children: [
    /* @__PURE__ */ e.jsx(m, { title: "Hall of Fame", subtitle: "All-time records", children: /* @__PURE__ */ e.jsxs(
      "select",
      {
        value: a,
        onChange: (o) => n(o.target.value),
        className: "bg-slate-800 border border-white/10 text-slate-200 rounded-lg px-3 py-2 text-sm focus:outline-none focus:border-blue-500/50",
        children: [
          /* @__PURE__ */ e.jsx("option", { value: "", children: "All Maps" }),
          j?.map((o) => /* @__PURE__ */ e.jsx("option", { value: o, children: o }, o))
        ]
      }
    ) }),
    y ? /* @__PURE__ */ e.jsx("div", { className: "grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4 gap-4", children: D.map((o) => {
      const d = r[o.key];
      return !d || d.length === 0 ? null : /* @__PURE__ */ e.jsx(
        O,
        {
          cat: o,
          records: d,
          onSelect: () => l(o.key)
        },
        o.key
      );
    }) }) : /* @__PURE__ */ e.jsx(C, { message: "No records found for this selection." }),
    t && r?.[t] && /* @__PURE__ */ e.jsx(
      U,
      {
        categoryKey: t,
        records: r[t],
        onClose: () => l(null)
      }
    )
  ] });
}
export {
  de as default
};
