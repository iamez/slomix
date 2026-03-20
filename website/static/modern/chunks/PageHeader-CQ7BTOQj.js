import { j as e, c as i } from "./route-host-Ba3v8uFM.js";
function n({ title: x, subtitle: t, children: l, className: r, eyebrow: s, badge: a }) {
  return /* @__PURE__ */ e.jsxs("div", { className: i("glass-panel relative overflow-hidden rounded-[30px] p-6 md:p-7 mb-8", r), children: [
    /* @__PURE__ */ e.jsx("div", { className: "absolute inset-y-0 right-0 w-48 bg-[radial-gradient(circle_at_top_right,rgba(56,189,248,0.15),transparent_60%)]" }),
    /* @__PURE__ */ e.jsxs("div", { className: "relative flex flex-col gap-5 lg:flex-row lg:items-end lg:justify-between", children: [
      /* @__PURE__ */ e.jsxs("div", { className: "max-w-3xl", children: [
        (s || a) && /* @__PURE__ */ e.jsxs("div", { className: "mb-3 flex flex-wrap items-center gap-2", children: [
          s && /* @__PURE__ */ e.jsx("div", { className: "section-kicker", children: s }),
          a && /* @__PURE__ */ e.jsx("span", { className: "rounded-full border border-cyan-400/25 bg-cyan-400/12 px-3 py-1 text-[11px] font-bold text-cyan-200", children: a })
        ] }),
        /* @__PURE__ */ e.jsx("h1", { className: "text-3xl font-black tracking-tight text-white md:text-4xl", children: x }),
        t && /* @__PURE__ */ e.jsx("p", { className: "mt-2 max-w-2xl text-sm text-slate-400 md:text-base", children: t })
      ] }),
      l && /* @__PURE__ */ e.jsx("div", { className: "flex flex-wrap items-center gap-2", children: l })
    ] })
  ] });
}
export {
  n as P
};
