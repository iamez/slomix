import { jsxs as a, jsx as t, Fragment as y } from "react/jsx-runtime";
import { useState as b, useRef as C, useCallback as _ } from "react";
import { k as $ } from "./hooks-UFUMZFGB.js";
import { G as M } from "./GlassCard-DKnnuJMt.js";
import { P as j } from "./PageHeader-D4CVo02x.js";
import { S as R, c as S } from "./route-host-CUL1oI6Z.js";
import { E } from "./EmptyState-DvtQr4qR.js";
import { f as G } from "./format-BM7Gaq4w.js";
import { n as w } from "./navigation-BDd1HkpE.js";
import { m as L } from "./game-assets-CWuRxGFH.js";
import { c as v } from "./createLucideIcon-CP-mMPfa.js";
import { X as P } from "./x-B9bYxG31.js";
import { U as k } from "./users-CNuz17ri.js";
import { M as T } from "./map-CPL-Ld_L.js";
import { G as I } from "./gamepad-2-CX3iu8NC.js";
const U = [
  ["path", { d: "M8 2v4", key: "1cmpym" }],
  ["path", { d: "M16 2v4", key: "4m81vk" }],
  ["rect", { width: "18", height: "18", x: "3", y: "4", rx: "2", key: "1hopcy" }],
  ["path", { d: "M3 10h18", key: "8toen8" }]
], A = v("calendar", U);
const D = [["path", { d: "m9 18 6-6-6-6", key: "mthhwq" }]], F = v("chevron-right", D);
const W = [
  ["path", { d: "m21 21-4.34-4.34", key: "14j7rj" }],
  ["circle", { cx: "11", cy: "11", r: "8", key: "4ej97u" }]
], Z = v("search", W), N = 15;
function q(e) {
  if (!e || e <= 0) return "";
  const s = Math.floor(e / 3600), r = Math.floor(e % 3600 / 60);
  return s > 0 ? `${s}h ${r}m` : `${r}m`;
}
function z(e) {
  return e.replace(/\^[0-9A-Za-z]/g, "");
}
function B(e) {
  return e.replace(/^maps[\\/]/, "").replace(/\.(bsp|pk3|arena)$/i, "").replace(/_/g, " ");
}
function H({ session: e }) {
  const s = e.round_count ?? e.rounds ?? 0, r = e.player_count ?? e.players ?? 0, n = e.maps_played ?? [], o = n.length || (e.maps ?? 0), p = q(e.duration_seconds), i = e.start_time && e.end_time ? `${e.start_time} — ${e.end_time}` : "", c = s % 2 !== 0, h = (e.player_names ?? []).map(z).filter(Boolean), d = e.allies_wins ?? 0, m = e.axis_wins ?? 0, x = d > m ? "text-blue-400" : m > d ? "text-rose-400" : "text-slate-400";
  function f() {
    e.session_id ? w(`#/session-detail/${e.session_id}`) : w(`#/session-detail/date/${encodeURIComponent(e.date)}`);
  }
  return /* @__PURE__ */ a(M, { onClick: f, className: "group", children: [
    /* @__PURE__ */ a("div", { className: "flex flex-wrap items-center justify-between gap-4", children: [
      /* @__PURE__ */ a("div", { className: "flex items-center gap-4", children: [
        /* @__PURE__ */ t("div", { className: "w-12 h-12 rounded-lg bg-gradient-to-br from-purple-500 to-blue-500 flex items-center justify-center shrink-0", children: /* @__PURE__ */ t(A, { className: "w-6 h-6 text-white" }) }),
        /* @__PURE__ */ a("div", { children: [
          /* @__PURE__ */ t("div", { className: "text-lg font-black text-white", children: e.formatted_date || e.date }),
          /* @__PURE__ */ a("div", { className: "text-sm text-slate-400 flex flex-wrap items-center gap-2", children: [
            e.time_ago && /* @__PURE__ */ t("span", { children: e.time_ago }),
            i && /* @__PURE__ */ a(y, { children: [
              /* @__PURE__ */ t("span", { className: "text-slate-600", children: "·" }),
              /* @__PURE__ */ t("span", { children: i })
            ] }),
            p && /* @__PURE__ */ a(y, { children: [
              /* @__PURE__ */ t("span", { className: "text-slate-600", children: "·" }),
              /* @__PURE__ */ t("span", { className: "text-slate-500", children: p })
            ] }),
            e.session_id && /* @__PURE__ */ a("span", { className: "px-2 py-0.5 rounded-full bg-slate-800 text-[10px] uppercase tracking-wide text-slate-400", children: [
              "Session ",
              e.session_id
            ] }),
            c && /* @__PURE__ */ t("span", { className: "px-2 py-0.5 rounded-full bg-amber-500/20 text-amber-300 text-[10px] uppercase", children: "Missing Round" })
          ] })
        ] })
      ] }),
      /* @__PURE__ */ a("div", { className: "flex items-center gap-6", children: [
        /* @__PURE__ */ t(u, { icon: k, value: r, label: "Players", color: "text-brand-cyan" }),
        /* @__PURE__ */ t(u, { icon: T, value: o, label: "Maps", color: "text-brand-purple" }),
        /* @__PURE__ */ t(u, { icon: I, value: s, label: "Rounds", color: "text-brand-amber" }),
        e.total_kills > 0 && /* @__PURE__ */ t(u, { icon: null, value: G(e.total_kills), label: "Kills", color: "text-brand-emerald" }),
        /* @__PURE__ */ a("div", { className: "text-center", children: [
          /* @__PURE__ */ a("div", { className: S("text-2xl font-black", x), children: [
            d,
            " - ",
            m
          ] }),
          /* @__PURE__ */ t("div", { className: "text-xs text-slate-500 uppercase", children: "Score" })
        ] })
      ] }),
      /* @__PURE__ */ t(F, { className: "w-5 h-5 text-slate-400 group-hover:text-blue-400 transition" })
    ] }),
    /* @__PURE__ */ a("div", { className: "mt-4 flex flex-col lg:flex-row lg:items-center lg:justify-between gap-3", children: [
      /* @__PURE__ */ a("div", { className: "flex flex-wrap items-center gap-2", children: [
        n.slice(0, 5).map((l) => /* @__PURE__ */ a("span", { className: "inline-flex items-center gap-1.5 px-2 py-0.5 rounded bg-slate-800 text-[10px] text-slate-300 font-medium", children: [
          /* @__PURE__ */ t("img", { src: L(l), alt: "", className: "w-4 h-4 rounded-sm object-cover", onError: (g) => {
            g.currentTarget.style.display = "none";
          } }),
          B(l)
        ] }, l)),
        n.length > 5 && /* @__PURE__ */ a("span", { className: "text-slate-500 text-xs", children: [
          "+",
          n.length - 5,
          " more"
        ] })
      ] }),
      h.length > 0 && /* @__PURE__ */ a("div", { className: "flex flex-wrap items-center gap-2", children: [
        /* @__PURE__ */ t(k, { className: "w-3.5 h-3.5 text-slate-500 shrink-0" }),
        h.map((l) => /* @__PURE__ */ t("span", { className: "px-2 py-0.5 rounded-full bg-slate-800/80 text-xs text-slate-300 font-medium", children: l }, l))
      ] })
    ] })
  ] });
}
function u({ icon: e, value: s, label: r, color: n }) {
  return /* @__PURE__ */ a("div", { className: "text-center", children: [
    /* @__PURE__ */ t("div", { className: S("text-2xl font-black", n), children: s }),
    /* @__PURE__ */ t("div", { className: "text-xs text-slate-500 uppercase", children: r })
  ] });
}
function oe() {
  const [e, s] = b(""), [r, n] = b(""), o = C(null), [p, i] = b(0), { data: c, isLoading: h, isError: d } = $({
    limit: N,
    offset: p,
    search: r || void 0
  }), m = _((l) => {
    s(l), o.current && clearTimeout(o.current), o.current = setTimeout(() => {
      n(l), i(0);
    }, 300);
  }, []), x = _(() => {
    s(""), n(""), i(0), o.current && clearTimeout(o.current);
  }, []), f = (c?.length ?? 0) >= N;
  return /* @__PURE__ */ a("div", { className: "mt-6", children: [
    /* @__PURE__ */ t(j, { title: "Sessions", subtitle: "Gaming session history" }),
    /* @__PURE__ */ a("div", { className: "relative mb-6 max-w-md", children: [
      /* @__PURE__ */ t(Z, { className: "absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-slate-500" }),
      /* @__PURE__ */ t(
        "input",
        {
          type: "text",
          value: e,
          onChange: (l) => m(l.target.value),
          placeholder: "Search sessions by player or map...",
          className: `w-full pl-10 pr-10 py-2.5 bg-slate-800 border border-white/10 text-slate-200 rounded-lg text-sm
                     focus:outline-none focus:border-blue-500/50 placeholder:text-slate-500`
        }
      ),
      e && /* @__PURE__ */ t("button", { onClick: x, className: "absolute right-3 top-1/2 -translate-y-1/2 text-slate-400 hover:text-white", children: /* @__PURE__ */ t(P, { className: "w-4 h-4" }) })
    ] }),
    r && c && /* @__PURE__ */ a("div", { className: "text-sm text-slate-400 mb-4", children: [
      c.length,
      " session",
      c.length !== 1 ? "s" : "",
      ' found for "',
      r,
      '"'
    ] }),
    h ? /* @__PURE__ */ t("div", { className: "space-y-4", children: /* @__PURE__ */ t(R, { variant: "card", count: 3, className: "grid-cols-1" }) }) : d ? /* @__PURE__ */ t("div", { className: "text-center text-red-400 py-12", children: "Failed to load sessions." }) : !c || c.length === 0 ? /* @__PURE__ */ t(E, { message: r ? `No sessions found for "${r}".` : "No sessions available yet." }) : /* @__PURE__ */ a("div", { className: "space-y-4", children: [
      c.map((l, g) => /* @__PURE__ */ t(H, { session: l }, l.session_id ?? `${l.date}-${g}`)),
      f && /* @__PURE__ */ t("div", { className: "text-center pt-4", children: /* @__PURE__ */ t(
        "button",
        {
          onClick: () => i((l) => l + N),
          className: "px-6 py-2.5 rounded-lg bg-blue-500/20 text-blue-400 font-bold text-sm hover:bg-blue-500/30 transition",
          children: "Load More"
        }
      ) })
    ] })
  ] });
}
export {
  oe as default
};
