import { j as e, c as t } from "./route-host-Ba3v8uFM.js";
function x({ label: a, value: l, options: r, onChange: n, allLabel: c = "All", className: i }) {
  return /* @__PURE__ */ e.jsxs("label", { className: t("flex items-center gap-2", i), children: [
    a && /* @__PURE__ */ e.jsx("span", { className: "text-xs font-bold text-slate-400 uppercase tracking-wider", children: a }),
    /* @__PURE__ */ e.jsxs(
      "select",
      {
        value: l,
        onChange: (s) => n(s.target.value),
        className: "rounded-xl border border-white/10 bg-slate-900/85 px-3 py-2 text-sm text-slate-200 focus:border-cyan-400/40 focus:outline-none",
        children: [
          /* @__PURE__ */ e.jsx("option", { value: "", children: c }),
          r.map((s) => /* @__PURE__ */ e.jsx("option", { value: s.value, children: s.label }, s.value))
        ]
      }
    )
  ] });
}
function d({ children: a, className: l }) {
  return /* @__PURE__ */ e.jsx("div", { className: t("glass-panel flex flex-wrap items-center gap-3 rounded-[24px] p-3 md:p-4 mb-6", l), children: a });
}
export {
  d as F,
  x as S
};
