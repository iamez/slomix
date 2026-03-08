import { jsx as r } from "react/jsx-runtime";
import { useRef as c, useEffect as f } from "react";
function l() {
  return typeof window < "u" && window.Chart ? window.Chart : null;
}
function h({ type: n, data: a, options: u, height: i, className: o }) {
  const e = c(null), t = c(null);
  return f(() => {
    const s = l();
    if (!(!s || !e.current))
      return t.current = new s(e.current.getContext("2d"), {
        type: n,
        data: a,
        options: { responsive: !0, maintainAspectRatio: !1, ...u }
      }), () => {
        t.current?.destroy(), t.current = null;
      };
  }, [n, a, u]), l() ? /* @__PURE__ */ r("div", { className: o, style: i ? { height: i } : void 0, children: /* @__PURE__ */ r("canvas", { ref: e }) }) : /* @__PURE__ */ r("div", { className: "flex items-center justify-center h-full text-slate-500 text-sm", children: "Chart library unavailable" });
}
export {
  h as C
};
