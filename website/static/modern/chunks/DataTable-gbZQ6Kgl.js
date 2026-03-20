import { r as p, j as t, c as i } from "./route-host-Ba3v8uFM.js";
import { c as x } from "./createLucideIcon-BebMLfof.js";
const w = [["path", { d: "m6 9 6 6 6-6", key: "qrunsl" }]], S = x("chevron-down", w);
const C = [["path", { d: "m18 15-6-6-6 6", key: "153udz" }]], _ = x("chevron-up", C);
function E({
  columns: c,
  data: a,
  keyFn: h,
  onRowClick: d,
  rowClassName: m,
  emptyMessage: b = "No data available.",
  className: f,
  defaultSort: y,
  stickyHeader: N
}) {
  const [n, g] = p.useState(y ?? null), j = p.useMemo(() => {
    if (!n) return a;
    const e = c.find((r) => r.key === n.key);
    if (!e?.sortable) return a;
    const s = e.sortValue ?? ((r) => r[n.key]);
    return [...a].sort((r, v) => {
      const l = s(r), o = s(v);
      if (l == null && o == null) return 0;
      if (l == null) return 1;
      if (o == null) return -1;
      const u = typeof l == "number" && typeof o == "number" ? l - o : String(l).localeCompare(String(o));
      return n.dir === "asc" ? u : -u;
    });
  }, [a, n, c]);
  function k(e) {
    g((s) => s?.key === e ? s.dir === "desc" ? { key: e, dir: "asc" } : null : { key: e, dir: "desc" });
  }
  return a.length === 0 ? /* @__PURE__ */ t.jsx("div", { className: "glass-panel rounded-[24px] py-12 text-center text-slate-400", children: b }) : /* @__PURE__ */ t.jsx("div", { className: i("table-shell overflow-x-auto rounded-[24px]", f), children: /* @__PURE__ */ t.jsxs("table", { className: "min-w-[720px] w-full text-left", children: [
    /* @__PURE__ */ t.jsx("thead", { children: /* @__PURE__ */ t.jsx("tr", { className: i("border-b border-white/10", N && "sticky top-0 bg-slate-900/95 backdrop-blur-sm z-10"), children: c.map((e) => /* @__PURE__ */ t.jsx(
      "th",
      {
        className: i(
          "px-4 py-3 text-xs font-bold text-slate-400 uppercase tracking-wider",
          e.sortable && "cursor-pointer select-none hover:text-slate-200 transition",
          e.headerClassName
        ),
        onClick: e.sortable ? () => k(e.key) : void 0,
        children: /* @__PURE__ */ t.jsxs("span", { className: "inline-flex items-center gap-1", children: [
          e.label,
          e.sortable && n?.key === e.key && (n.dir === "desc" ? /* @__PURE__ */ t.jsx(S, { className: "w-3 h-3" }) : /* @__PURE__ */ t.jsx(_, { className: "w-3 h-3" }))
        ] })
      },
      e.key
    )) }) }),
    /* @__PURE__ */ t.jsx("tbody", { children: j.map((e, s) => /* @__PURE__ */ t.jsx(
      "tr",
      {
        className: i(
          "border-b border-white/5 transition",
          d && "cursor-pointer hover:bg-white/[0.03]",
          s % 2 === 0 ? "bg-transparent" : "bg-white/[0.015]",
          m?.(e, s)
        ),
        onClick: d ? () => d(e) : void 0,
        children: c.map((r) => /* @__PURE__ */ t.jsx("td", { className: i("px-4 py-3 text-sm text-slate-200", r.className), children: r.render ? r.render(e, s) : String(e[r.key] ?? "") }, r.key))
      },
      h(e, s)
    )) })
  ] }) });
}
export {
  _ as C,
  E as D
};
