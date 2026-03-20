import { r, j as n } from "./route-host-Ba3v8uFM.js";
function l() {
  return typeof window < "u" && window.Chart ? window.Chart : null;
}
function d({ type: s, data: a, options: u, height: i, className: o }) {
  const e = r.useRef(null), t = r.useRef(null);
  return r.useEffect(() => {
    const c = l();
    if (!(!c || !e.current))
      return t.current = new c(e.current.getContext("2d"), {
        type: s,
        data: a,
        options: { responsive: !0, maintainAspectRatio: !1, ...u }
      }), () => {
        t.current?.destroy(), t.current = null;
      };
  }, [s, a, u]), l() ? /* @__PURE__ */ n.jsx("div", { className: o, style: i ? { height: i } : void 0, children: /* @__PURE__ */ n.jsx("canvas", { ref: e }) }) : /* @__PURE__ */ n.jsx("div", { className: "flex items-center justify-center h-full text-slate-500 text-sm", children: "Chart library unavailable" });
}
export {
  d as C
};
