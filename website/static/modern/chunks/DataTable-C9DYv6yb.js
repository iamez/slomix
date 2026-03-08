import { jsx as r, jsxs as m } from "react/jsx-runtime";
import { useState as w, useMemo as S } from "react";
import { c as l } from "./route-host-CUL1oI6Z.js";
import { c as p } from "./createLucideIcon-CP-mMPfa.js";
const C = [["path", { d: "m6 9 6 6 6-6", key: "qrunsl" }]], _ = p("chevron-down", C);
const D = [["path", { d: "m18 15-6-6-6 6", key: "153udz" }]], j = p("chevron-up", D);
function L({
  columns: c,
  data: a,
  keyFn: h,
  onRowClick: d,
  emptyMessage: b = "No data available.",
  className: f,
  defaultSort: y,
  stickyHeader: x
}) {
  const [s, N] = w(y ?? null), g = S(() => {
    if (!s) return a;
    const e = c.find((t) => t.key === s.key);
    if (!e?.sortable) return a;
    const n = e.sortValue ?? ((t) => t[s.key]);
    return [...a].sort((t, v) => {
      const o = n(t), i = n(v);
      if (o == null && i == null) return 0;
      if (o == null) return 1;
      if (i == null) return -1;
      const u = typeof o == "number" && typeof i == "number" ? o - i : String(o).localeCompare(String(i));
      return s.dir === "asc" ? u : -u;
    });
  }, [a, s, c]);
  function k(e) {
    N((n) => n?.key === e ? n.dir === "desc" ? { key: e, dir: "asc" } : null : { key: e, dir: "desc" });
  }
  return a.length === 0 ? /* @__PURE__ */ r("div", { className: "text-center text-slate-400 py-12", children: b }) : /* @__PURE__ */ r("div", { className: l("overflow-x-auto", f), children: /* @__PURE__ */ m("table", { className: "w-full text-left", children: [
    /* @__PURE__ */ r("thead", { children: /* @__PURE__ */ r("tr", { className: l("border-b border-white/10", x && "sticky top-0 bg-slate-900/95 backdrop-blur-sm z-10"), children: c.map((e) => /* @__PURE__ */ r(
      "th",
      {
        className: l(
          "px-4 py-3 text-xs font-bold text-slate-400 uppercase tracking-wider",
          e.sortable && "cursor-pointer select-none hover:text-slate-200 transition",
          e.headerClassName
        ),
        onClick: e.sortable ? () => k(e.key) : void 0,
        children: /* @__PURE__ */ m("span", { className: "inline-flex items-center gap-1", children: [
          e.label,
          e.sortable && s?.key === e.key && (s.dir === "desc" ? /* @__PURE__ */ r(_, { className: "w-3 h-3" }) : /* @__PURE__ */ r(j, { className: "w-3 h-3" }))
        ] })
      },
      e.key
    )) }) }),
    /* @__PURE__ */ r("tbody", { children: g.map((e, n) => /* @__PURE__ */ r(
      "tr",
      {
        className: l(
          "border-b border-white/5 transition",
          d && "cursor-pointer hover:bg-white/[0.03]",
          n % 2 === 0 ? "bg-transparent" : "bg-white/[0.01]"
        ),
        onClick: d ? () => d(e) : void 0,
        children: c.map((t) => /* @__PURE__ */ r("td", { className: l("px-4 py-3 text-sm text-slate-200", t.className), children: t.render ? t.render(e, n) : String(e[t.key] ?? "") }, t.key))
      },
      h(e, n)
    )) })
  ] }) });
}
export {
  L as D
};
