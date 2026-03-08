import { jsxs as a, jsx as e } from "react/jsx-runtime";
import { c as r } from "./route-host-CUL1oI6Z.js";
function n({ title: c, subtitle: t, children: s, className: m }) {
  return /* @__PURE__ */ a("div", { className: r("flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4 mb-8", m), children: [
    /* @__PURE__ */ a("div", { children: [
      /* @__PURE__ */ e("h1", { className: "text-3xl font-black text-white tracking-tight", children: c }),
      t && /* @__PURE__ */ e("p", { className: "text-slate-400 mt-1", children: t })
    ] }),
    s && /* @__PURE__ */ e("div", { className: "flex items-center gap-3", children: s })
  ] });
}
export {
  n as P
};
