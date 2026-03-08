import { jsx as t, jsxs as a } from "react/jsx-runtime";
import { c as s } from "./route-host-CUL1oI6Z.js";
function m({ label: l, value: r, options: n, onChange: c, allLabel: i = "All", className: o }) {
  return /* @__PURE__ */ a("label", { className: s("flex items-center gap-2", o), children: [
    l && /* @__PURE__ */ t("span", { className: "text-xs font-bold text-slate-400 uppercase tracking-wider", children: l }),
    /* @__PURE__ */ a(
      "select",
      {
        value: r,
        onChange: (e) => c(e.target.value),
        className: "bg-slate-800 border border-white/10 text-slate-200 rounded-lg px-3 py-2 text-sm focus:outline-none focus:border-blue-500/50",
        children: [
          /* @__PURE__ */ t("option", { value: "", children: i }),
          n.map((e) => /* @__PURE__ */ t("option", { value: e.value, children: e.label }, e.value))
        ]
      }
    )
  ] });
}
function p({ children: l, className: r }) {
  return /* @__PURE__ */ t("div", { className: s("flex flex-wrap items-center gap-3 mb-6", r), children: l });
}
export {
  p as F,
  m as S
};
