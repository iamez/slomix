import { r, c as k, j as e } from "./route-host-Ba3v8uFM.js";
import { a as h } from "./navigation-BDd1HkpE.js";
import { S } from "./search-BJtuBiat.js";
import { X as _ } from "./x-CUdvDzU_.js";
import { c as R } from "./createLucideIcon-BebMLfof.js";
const C = [
  ["circle", { cx: "12", cy: "8", r: "5", key: "1hypcn" }],
  ["path", { d: "M20 21a8 8 0 0 0-16 0", key: "rfgkzh" }]
], L = R("user-round", C);
function q({
  className: d,
  compact: n = !1,
  placeholder: m = "Search players...",
  title: f = "Find My Stats",
  subtitle: y = "Jump straight into a player profile."
}) {
  const [x, u] = r.useState(""), [a, l] = r.useState([]), [b, s] = r.useState(!1), [v, o] = r.useState(!1), w = r.useMemo(
    () => k(
      "relative overflow-visible rounded-[26px] border border-white/10 bg-slate-950/75 p-3 shadow-[0_22px_48px_rgba(2,6,23,0.34)] backdrop-blur-md",
      n ? "max-w-xl" : "max-w-2xl",
      d
    ),
    [d, n]
  );
  async function j(t) {
    if (u(t), t.trim().length < 2) {
      l([]), s(!1), o(!1);
      return;
    }
    o(!0);
    try {
      const p = await fetch(`/api/search?q=${encodeURIComponent(t)}&limit=8`);
      if (!p.ok) return;
      const c = await p.json(), N = Array.isArray(c) ? c : c.players || [];
      l(N), s(!0);
    } catch {
      l([]), s(!1);
    } finally {
      o(!1);
    }
  }
  function i() {
    u(""), l([]), s(!1);
  }
  function g() {
    a[0]?.name && (h(a[0].name), i());
  }
  return /* @__PURE__ */ e.jsxs("div", { className: w, children: [
    !n && /* @__PURE__ */ e.jsxs("div", { className: "mb-3 px-2", children: [
      /* @__PURE__ */ e.jsx("div", { className: "section-kicker mb-1", children: "Player Lookup" }),
      /* @__PURE__ */ e.jsx("div", { className: "text-xl font-black text-white", children: f }),
      /* @__PURE__ */ e.jsx("p", { className: "mt-1 text-sm text-slate-400", children: y })
    ] }),
    /* @__PURE__ */ e.jsxs("div", { className: "relative", children: [
      /* @__PURE__ */ e.jsx(S, { className: "pointer-events-none absolute left-4 top-1/2 h-4 w-4 -translate-y-1/2 text-cyan-400" }),
      /* @__PURE__ */ e.jsx(
        "input",
        {
          type: "text",
          value: x,
          onChange: (t) => {
            j(t.target.value);
          },
          onBlur: () => setTimeout(() => s(!1), 140),
          onFocus: () => {
            a.length > 0 && s(!0);
          },
          onKeyDown: (t) => {
            t.key === "Enter" && (t.preventDefault(), g());
          },
          className: "w-full rounded-[20px] border border-white/10 bg-slate-900/80 py-3.5 pl-11 pr-12 text-sm text-white outline-none transition placeholder:text-slate-500 focus:border-cyan-400/50",
          placeholder: m
        }
      ),
      x && /* @__PURE__ */ e.jsx(
        "button",
        {
          type: "button",
          onClick: i,
          className: "absolute right-3 top-1/2 -translate-y-1/2 rounded-full p-1 text-slate-500 transition hover:bg-white/6 hover:text-white",
          "aria-label": "Clear player search",
          children: /* @__PURE__ */ e.jsx(_, { className: "h-4 w-4" })
        }
      )
    ] }),
    b && /* @__PURE__ */ e.jsx("div", { className: "absolute inset-x-0 top-[calc(100%+0.6rem)] z-50 overflow-hidden rounded-[22px] border border-white/10 bg-slate-950/96 p-2 shadow-[0_28px_60px_rgba(2,6,23,0.5)] backdrop-blur-xl", children: v ? /* @__PURE__ */ e.jsx("div", { className: "px-3 py-3 text-sm text-slate-400", children: "Searching players..." }) : a.length > 0 ? a.map((t) => /* @__PURE__ */ e.jsxs(
      "button",
      {
        type: "button",
        className: "flex w-full items-center gap-3 rounded-2xl px-3 py-3 text-left transition hover:bg-white/5",
        onMouseDown: () => {
          h(t.name), i();
        },
        children: [
          /* @__PURE__ */ e.jsx("div", { className: "flex h-9 w-9 items-center justify-center rounded-2xl bg-cyan-500/12 text-cyan-300", children: /* @__PURE__ */ e.jsx(L, { className: "h-4 w-4" }) }),
          /* @__PURE__ */ e.jsxs("div", { children: [
            /* @__PURE__ */ e.jsx("div", { className: "text-sm font-bold text-white", children: t.name }),
            /* @__PURE__ */ e.jsx("div", { className: "text-xs text-slate-500", children: "Open full profile" })
          ] })
        ]
      },
      t.guid || t.name
    )) : /* @__PURE__ */ e.jsx("div", { className: "px-3 py-3 text-sm text-slate-500", children: "No players found." }) })
  ] });
}
export {
  q as P
};
