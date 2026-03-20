import { r as c, j as e, S as C } from "./route-host-Ba3v8uFM.js";
import { E } from "./EmptyState-CWT5OHyQ.js";
import { G as R } from "./GlassCard-C53TzD-y.js";
import { P as b } from "./PageHeader-CQ7BTOQj.js";
import { m as M } from "./hooks-CyQgvbI9.js";
import { m as T } from "./game-assets-BMYaQb9B.js";
import { f as m } from "./format-BM7Gaq4w.js";
import { n as x } from "./navigation-BDd1HkpE.js";
import { S as L } from "./search-BJtuBiat.js";
import { X as P } from "./x-CUdvDzU_.js";
import { C as j, a as D } from "./chevron-right-DaoXilIT.js";
import { U as G } from "./users-Blp4mgkM.js";
import { G as U } from "./gamepad-2-DXqvfHtG.js";
import { C as B } from "./clock-3-JXf94b9Z.js";
const g = 15;
function y(t) {
  return (t || "Unknown").replace(/^maps[\\/]/, "").replace(/\.(bsp|pk3|arena)$/i, "").replace(/_/g, " ");
}
function A(t) {
  return t.replace(/\^[0-9A-Za-z]/g, "");
}
function F(t) {
  if (!t || t <= 0) return "--";
  const a = Math.floor(t / 60), s = Math.floor(a / 60), n = a % 60;
  return s > 0 ? `${s}h ${n}m` : `${a}m`;
}
function H(t) {
  return t.session_id ? `#/session-detail/${t.session_id}` : `#/session-detail/date/${encodeURIComponent(t.date)}`;
}
function I({ session: t }) {
  const a = t.maps_played[0], s = t.player_names.slice(0, 4).map(A).filter(Boolean), n = `${t.allies_wins ?? 0} : ${t.axis_wins ?? 0}`;
  function o() {
    if (t.session_id) {
      x(`#/session-detail/${t.session_id}`);
      return;
    }
    x(`#/session-detail/date/${encodeURIComponent(t.date)}`);
  }
  return /* @__PURE__ */ e.jsx(R, { onClick: o, className: "p-5 md:p-6", children: /* @__PURE__ */ e.jsxs("div", { className: "grid gap-5 lg:grid-cols-[0.85fr_1.15fr_auto] lg:items-center", children: [
    /* @__PURE__ */ e.jsxs("div", { className: "flex items-center gap-4", children: [
      /* @__PURE__ */ e.jsx("div", { className: "h-18 w-18 overflow-hidden rounded-[22px] bg-slate-900/80 md:h-20 md:w-20", children: a ? /* @__PURE__ */ e.jsx(
        "img",
        {
          src: T(a),
          alt: y(a),
          className: "h-full w-full object-cover",
          onError: (i) => {
            i.currentTarget.style.display = "none";
          }
        }
      ) : /* @__PURE__ */ e.jsx("div", { className: "flex h-full w-full items-center justify-center text-cyan-300", children: /* @__PURE__ */ e.jsx(j, { className: "h-6 w-6" }) }) }),
      /* @__PURE__ */ e.jsxs("div", { className: "min-w-0", children: [
        /* @__PURE__ */ e.jsx("div", { className: "section-kicker mb-1", children: "Session" }),
        /* @__PURE__ */ e.jsx("div", { className: "truncate text-2xl font-black text-white", children: t.formatted_date || t.date }),
        /* @__PURE__ */ e.jsxs("div", { className: "mt-2 flex flex-wrap gap-2 text-xs text-slate-400", children: [
          t.time_ago && /* @__PURE__ */ e.jsx("span", { children: t.time_ago }),
          t.start_time && t.end_time && /* @__PURE__ */ e.jsxs("span", { children: [
            t.start_time,
            " to ",
            t.end_time
          ] })
        ] }),
        /* @__PURE__ */ e.jsxs("div", { className: "mt-3 flex flex-wrap gap-2", children: [
          (t.maps_played || []).slice(0, 3).map((i) => /* @__PURE__ */ e.jsx("span", { className: "rounded-full border border-white/10 bg-white/6 px-3 py-1 text-xs font-bold text-slate-300", children: y(i) }, i)),
          (t.maps_played || []).length > 3 && /* @__PURE__ */ e.jsxs("span", { className: "rounded-full border border-white/10 bg-white/6 px-3 py-1 text-xs font-bold text-slate-300", children: [
            "+",
            t.maps_played.length - 3,
            " more"
          ] })
        ] })
      ] })
    ] }),
    /* @__PURE__ */ e.jsxs("div", { className: "grid gap-3 sm:grid-cols-2 xl:grid-cols-4", children: [
      /* @__PURE__ */ e.jsx(d, { icon: G, label: "Players", value: m(t.player_count || t.players || 0), accent: "text-white" }),
      /* @__PURE__ */ e.jsx(d, { icon: U, label: "Rounds", value: m(t.round_count || t.rounds || 0), accent: "text-cyan-300" }),
      /* @__PURE__ */ e.jsx(d, { icon: B, label: "Duration", value: F(t.duration_seconds), accent: "text-amber-300" }),
      /* @__PURE__ */ e.jsx(d, { icon: j, label: "Score", value: n, accent: "text-rose-300" })
    ] }),
    /* @__PURE__ */ e.jsxs("div", { className: "flex items-center justify-between gap-4 lg:flex-col lg:items-end", children: [
      /* @__PURE__ */ e.jsxs("div", { className: "text-right", children: [
        /* @__PURE__ */ e.jsx("div", { className: "section-kicker mb-1", children: "Quick read" }),
        /* @__PURE__ */ e.jsx("div", { className: "text-sm font-bold text-white", children: s.length > 0 ? s.join(", ") : "Roster available in detail" })
      ] }),
      /* @__PURE__ */ e.jsxs("div", { className: "inline-flex items-center gap-2 text-sm font-bold text-cyan-300", children: [
        "Open detail",
        /* @__PURE__ */ e.jsx(D, { className: "h-4 w-4" })
      ] })
    ] })
  ] }) });
}
function d({
  icon: t,
  label: a,
  value: s,
  accent: n
}) {
  return /* @__PURE__ */ e.jsxs("div", { className: "rounded-[20px] border border-white/8 bg-white/[0.03] p-4", children: [
    /* @__PURE__ */ e.jsx(t, { className: `h-4 w-4 ${n}` }),
    /* @__PURE__ */ e.jsx("div", { className: `mt-3 text-xl font-black ${n}`, children: s }),
    /* @__PURE__ */ e.jsx("div", { className: "mt-1 text-[11px] font-bold uppercase tracking-[0.22em] text-slate-500", children: a })
  ] });
}
function ae() {
  const [t, a] = c.useState(""), [s, n] = c.useState(""), o = c.useRef(null), [i, h] = c.useState(0), { data: v, isLoading: w, isError: N } = M({
    limit: g,
    offset: i,
    search: s || void 0
  }), r = v ?? [], _ = r.length >= g, S = c.useMemo(() => {
    if (!r.length) return "No sessions loaded yet.";
    const l = r.reduce((u, f) => u + (f.player_count || 0), 0), p = r.reduce((u, f) => u + (f.round_count || 0), 0);
    return `${r.length} sessions · ${m(l)} player slots · ${m(p)} rounds`;
  }, [r]);
  function k(l) {
    a(l), o.current && clearTimeout(o.current), o.current = setTimeout(() => {
      n(l), h(0);
    }, 250);
  }
  function $() {
    a(""), n(""), h(0), o.current && clearTimeout(o.current);
  }
  return w ? /* @__PURE__ */ e.jsxs("div", { className: "page-shell", children: [
    /* @__PURE__ */ e.jsx(
      b,
      {
        title: "Sessions",
        subtitle: "The archive is now browse-first instead of overloaded at first glance.",
        eyebrow: "Everyday Browsing"
      }
    ),
    /* @__PURE__ */ e.jsx(C, { variant: "card", count: 4, className: "grid-cols-1" })
  ] }) : N ? /* @__PURE__ */ e.jsxs("div", { className: "page-shell", children: [
    /* @__PURE__ */ e.jsx(b, { title: "Sessions", subtitle: "Failed to load session archive.", eyebrow: "Everyday Browsing" }),
    /* @__PURE__ */ e.jsx("div", { className: "text-center text-red-400 py-12", children: "Failed to load sessions." })
  ] }) : /* @__PURE__ */ e.jsxs("div", { className: "page-shell", children: [
    /* @__PURE__ */ e.jsx(
      b,
      {
        title: "Sessions",
        subtitle: "Archive is now a cleaner browse layer, while Home stays the quickest path into the newest session.",
        eyebrow: "Everyday Browsing",
        badge: S
      }
    ),
    /* @__PURE__ */ e.jsx("div", { className: "glass-panel rounded-[26px] p-4 md:p-5", children: /* @__PURE__ */ e.jsxs("div", { className: "grid gap-4 lg:grid-cols-[1fr_auto] lg:items-center", children: [
      /* @__PURE__ */ e.jsxs("div", { className: "relative", children: [
        /* @__PURE__ */ e.jsx(L, { className: "pointer-events-none absolute left-4 top-1/2 h-4 w-4 -translate-y-1/2 text-cyan-300" }),
        /* @__PURE__ */ e.jsx(
          "input",
          {
            type: "text",
            value: t,
            onChange: (l) => k(l.target.value),
            placeholder: "Search sessions by player or map...",
            className: "w-full rounded-[20px] border border-white/10 bg-slate-900/80 py-3.5 pl-11 pr-11 text-sm text-white outline-none transition placeholder:text-slate-500 focus:border-cyan-400/45"
          }
        ),
        t && /* @__PURE__ */ e.jsx(
          "button",
          {
            type: "button",
            onClick: $,
            className: "absolute right-3 top-1/2 -translate-y-1/2 rounded-full p-1 text-slate-500 transition hover:bg-white/6 hover:text-white",
            "aria-label": "Clear search",
            children: /* @__PURE__ */ e.jsx(P, { className: "h-4 w-4" })
          }
        )
      ] }),
      /* @__PURE__ */ e.jsxs("div", { className: "flex flex-wrap gap-2", children: [
        /* @__PURE__ */ e.jsx(
          "button",
          {
            type: "button",
            onClick: () => x(r[0] ? H(r[0]) : "#/sessions2"),
            className: "rounded-full border border-white/10 bg-white/5 px-4 py-2 text-xs font-bold text-slate-300 transition hover:text-white",
            children: "Open Newest Session"
          }
        ),
        /* @__PURE__ */ e.jsx(
          "button",
          {
            type: "button",
            onClick: () => x("#/profile"),
            className: "rounded-full border border-white/10 bg-white/5 px-4 py-2 text-xs font-bold text-slate-300 transition hover:text-white",
            children: "Player Lookup"
          }
        )
      ] })
    ] }) }),
    s && /* @__PURE__ */ e.jsxs("div", { className: "text-sm text-slate-400", children: [
      "Showing ",
      r.length,
      " result",
      r.length !== 1 ? "s" : "",
      ' for "',
      s,
      '".'
    ] }),
    r.length ? /* @__PURE__ */ e.jsx("div", { className: "space-y-4", children: r.map((l, p) => /* @__PURE__ */ e.jsx(I, { session: l }, l.session_id ?? `${l.date}-${p}`)) }) : /* @__PURE__ */ e.jsx(E, { message: s ? `No sessions found for "${s}".` : "No sessions available yet." }),
    _ && /* @__PURE__ */ e.jsx("div", { className: "pt-2", children: /* @__PURE__ */ e.jsx(
      "button",
      {
        type: "button",
        onClick: () => h((l) => l + g),
        className: "rounded-2xl border border-cyan-400/20 bg-cyan-400/10 px-5 py-3 text-sm font-black text-cyan-200 transition hover:bg-cyan-400/16",
        children: "Load More Sessions"
      }
    ) })
  ] });
}
export {
  ae as default
};
