import { r as x, j as e, S as L } from "./route-host-Ba3v8uFM.js";
import { P as I } from "./PageHeader-CQ7BTOQj.js";
import { G as y } from "./GlassPanel-C-uUmQaB.js";
import { E as g } from "./EmptyState-CWT5OHyQ.js";
import { G as T, K as O, L as q } from "./hooks-CyQgvbI9.js";
import { n as b } from "./navigation-BDd1HkpE.js";
import { m as H } from "./game-assets-BMYaQb9B.js";
const M = {
  uploaded: "text-slate-300 border-slate-500/40 bg-slate-800/40",
  scanning: "text-cyan-400 border-cyan-400/40 bg-cyan-400/10",
  analyzed: "text-emerald-400 border-emerald-400/40 bg-emerald-400/10",
  failed: "text-rose-400 border-rose-400/40 bg-rose-400/10",
  queued: "text-amber-400 border-amber-400/40 bg-amber-400/10",
  rendering: "text-cyan-400 border-cyan-400/40 bg-cyan-400/10",
  rendered: "text-emerald-400 border-emerald-400/40 bg-emerald-400/10"
}, F = [
  { key: "demos", label: "Demos" },
  { key: "highlights", label: "Highlights" },
  { key: "clips", label: "Clips" },
  { key: "renders", label: "Renders" }
];
function B(t) {
  if (t == null || !Number.isFinite(t)) return "--";
  const i = Math.max(0, Math.floor(t / 1e3)), n = Math.floor(i / 3600), u = Math.floor(i % 3600 / 60), f = i % 60;
  return n > 0 ? `${n}:${String(u).padStart(2, "0")}:${String(f).padStart(2, "0")}` : `${String(u).padStart(2, "0")}:${String(f).padStart(2, "0")}`;
}
function K({ item: t }) {
  const i = M[t.status] || "text-slate-300 border-white/10 bg-slate-800/40";
  return /* @__PURE__ */ e.jsxs(
    "button",
    {
      onClick: () => b(`#/greatshot/demo/${encodeURIComponent(t.id)}`),
      className: "glass-card p-4 rounded-xl border border-white/10 text-left hover:border-cyan-400/40 transition w-full",
      children: [
        /* @__PURE__ */ e.jsxs("div", { className: "flex items-center justify-between gap-3", children: [
          /* @__PURE__ */ e.jsx("div", { className: "text-sm font-bold text-white truncate", children: t.filename || t.id }),
          /* @__PURE__ */ e.jsx("span", { className: `text-[10px] font-bold px-2 py-1 rounded border shrink-0 ${i}`, children: t.status.toUpperCase() })
        ] }),
        /* @__PURE__ */ e.jsxs("div", { className: "mt-2 text-xs text-slate-400 flex flex-wrap items-center gap-3", children: [
          /* @__PURE__ */ e.jsxs("span", { className: "inline-flex items-center gap-1.5", children: [
            t.map && /* @__PURE__ */ e.jsx("img", { src: H(t.map), alt: "", className: "w-4 h-4 rounded-sm object-cover", onError: (n) => {
              n.currentTarget.style.display = "none";
            } }),
            "Map: ",
            t.map || "--"
          ] }),
          /* @__PURE__ */ e.jsxs("span", { children: [
            "Duration: ",
            B(t.duration_ms)
          ] }),
          /* @__PURE__ */ e.jsxs("span", { children: [
            "Highlights: ",
            t.highlight_count
          ] }),
          /* @__PURE__ */ e.jsxs("span", { children: [
            "Renders: ",
            t.rendered_count,
            "/",
            t.render_job_count
          ] }),
          t.created_at && /* @__PURE__ */ e.jsx("span", { children: new Date(t.created_at).toLocaleString() })
        ] }),
        t.error && /* @__PURE__ */ e.jsx("div", { className: "mt-2 text-xs text-rose-400", children: t.error })
      ]
    }
  );
}
function ee({ params: t }) {
  const i = t?.section || "demos", [n, u] = x.useState(i), { data: f } = T(), N = !!f, { data: R, isLoading: z, refetch: j } = O(N), [v, w] = x.useState(!1), [k, E] = x.useState(""), [d, S] = x.useState(/* @__PURE__ */ new Map()), c = x.useRef(void 0), m = R?.items ?? [], _ = x.useCallback(async () => {
    const s = new Map(d);
    let a = !1;
    for (const [l, r] of s)
      if (!(r.status === "analyzed" || r.status === "failed"))
        try {
          const o = await q.getGreatshotStatus(l);
          o.status !== r.status && (s.set(l, { ...r, status: o.status, error: o.error || void 0 }), a = !0);
        } catch {
        }
    if (a) {
      S(s);
      let l = !0;
      for (const [, r] of s)
        if (r.status !== "analyzed" && r.status !== "failed") {
          l = !1;
          break;
        }
      l && (clearInterval(c.current), c.current = void 0, j());
    }
  }, [d, j]);
  x.useEffect(() => {
    if (d.size > 0) {
      let s = !1;
      for (const [, a] of d)
        if (a.status !== "analyzed" && a.status !== "failed") {
          s = !0;
          break;
        }
      s && !c.current && (c.current = setInterval(_, 2500));
    }
    return () => {
      c.current && (clearInterval(c.current), c.current = void 0);
    };
  }, [d, _]);
  const P = async (s) => {
    s.preventDefault();
    const a = s.currentTarget, r = a.querySelector('input[type="file"]')?.files;
    if (!r || r.length === 0) return;
    w(!0), E("");
    const o = /* @__PURE__ */ new Map();
    for (const h of Array.from(r)) {
      const D = new FormData();
      D.append("file", h);
      try {
        const p = await fetch("/api/greatshot/upload", { method: "POST", body: D });
        if (!p.ok) {
          const G = await p.json().catch(() => ({ detail: "Upload failed" }));
          o.set(`error-${h.name}`, { filename: h.name, status: "failed", error: G.detail });
          continue;
        }
        const A = await p.json();
        o.set(A.demo_id, { filename: h.name, status: "uploaded" });
      } catch (p) {
        o.set(`error-${h.name}`, {
          filename: h.name,
          status: "failed",
          error: p instanceof Error ? p.message : "Upload failed"
        });
      }
    }
    S(o), w(!1), a.reset(), j();
  }, C = m.filter((s) => s.highlight_count > 0), U = m.filter((s) => s.highlight_count > 0), $ = m.filter((s) => s.render_job_count > 0);
  return N ? /* @__PURE__ */ e.jsxs("div", { children: [
    /* @__PURE__ */ e.jsx(I, { title: "Greatshot", subtitle: `${m.length} demos` }),
    /* @__PURE__ */ e.jsxs(y, { className: "mb-6", children: [
      /* @__PURE__ */ e.jsx("div", { className: "text-xs font-bold uppercase tracking-widest text-slate-500 mb-3", children: "Upload Demo" }),
      /* @__PURE__ */ e.jsxs("form", { onSubmit: P, className: "flex flex-col sm:flex-row items-start sm:items-end gap-3", children: [
        /* @__PURE__ */ e.jsxs("label", { className: "flex-1 min-w-0", children: [
          /* @__PURE__ */ e.jsx("span", { className: "text-xs text-slate-400 mb-1 block", children: "Demo file(s) (.dm_84)" }),
          /* @__PURE__ */ e.jsx(
            "input",
            {
              type: "file",
              accept: ".dm_84",
              multiple: !0,
              required: !0,
              className: "w-full text-sm text-slate-300 file:mr-3 file:py-2 file:px-4 file:rounded-lg file:border-0 file:text-sm file:font-bold file:bg-slate-700 file:text-slate-200 hover:file:bg-slate-600 cursor-pointer"
            }
          )
        ] }),
        /* @__PURE__ */ e.jsx(
          "button",
          {
            type: "submit",
            disabled: v,
            className: "px-5 py-2 bg-cyan-600 hover:bg-cyan-500 disabled:bg-slate-700 disabled:text-slate-500 text-white text-sm font-bold rounded-lg transition-colors",
            children: v ? "Uploading..." : "Upload & Analyze"
          }
        )
      ] }),
      k && /* @__PURE__ */ e.jsx("div", { className: "mt-3 text-sm text-rose-400", children: k })
    ] }),
    d.size > 0 && /* @__PURE__ */ e.jsxs(y, { className: "mb-6 border-cyan-400/20", children: [
      /* @__PURE__ */ e.jsx("div", { className: "text-xs font-bold uppercase tracking-widest text-cyan-400 mb-3", children: "Analysis Progress" }),
      /* @__PURE__ */ e.jsx("div", { className: "space-y-2", children: Array.from(d).map(([s, a]) => {
        const l = M[a.status] || "text-slate-300";
        return /* @__PURE__ */ e.jsxs("div", { className: "flex items-center gap-2 text-xs", children: [
          a.status === "analyzed" ? /* @__PURE__ */ e.jsx("span", { className: "text-emerald-400", children: "✓" }) : a.status === "failed" ? /* @__PURE__ */ e.jsx("span", { className: "text-rose-400", children: "✗" }) : /* @__PURE__ */ e.jsx("span", { className: "w-3 h-3 inline-block border-2 border-cyan-400/30 border-t-cyan-400 rounded-full animate-spin" }),
          /* @__PURE__ */ e.jsx("span", { className: "text-slate-200 truncate flex-1", children: a.filename }),
          /* @__PURE__ */ e.jsx("span", { className: l, children: a.status }),
          a.error && /* @__PURE__ */ e.jsx("span", { className: "text-rose-400", children: a.error })
        ] }, s);
      }) })
    ] }),
    /* @__PURE__ */ e.jsx("div", { className: "flex gap-2 mb-6", children: F.map((s) => /* @__PURE__ */ e.jsx(
      "button",
      {
        onClick: () => u(s.key),
        className: `px-3 py-1.5 rounded-lg text-xs font-bold uppercase tracking-wider border transition-all ${n === s.key ? "border-cyan-400/40 text-cyan-400 bg-cyan-400/10" : "border-white/10 text-slate-300 hover:text-white hover:border-cyan-400/40"}`,
        children: s.label
      },
      s.key
    )) }),
    z ? /* @__PURE__ */ e.jsx(L, { variant: "card", count: 4 }) : n === "demos" ? m.length === 0 ? /* @__PURE__ */ e.jsx(g, { message: "No demos uploaded yet." }) : /* @__PURE__ */ e.jsx("div", { className: "space-y-3", children: m.map((s) => /* @__PURE__ */ e.jsx(K, { item: s }, s.id)) }) : n === "highlights" ? C.length === 0 ? /* @__PURE__ */ e.jsx(g, { message: "No detected highlights yet. Analyze a demo first." }) : /* @__PURE__ */ e.jsx("div", { className: "space-y-2", children: C.slice(0, 12).map((s) => /* @__PURE__ */ e.jsxs("div", { className: "flex items-center justify-between glass-card rounded-xl p-3 border border-white/5", children: [
      /* @__PURE__ */ e.jsx("span", { className: "text-sm text-slate-200 truncate", children: s.filename || s.id }),
      /* @__PURE__ */ e.jsxs("div", { className: "flex items-center gap-3 text-xs shrink-0", children: [
        /* @__PURE__ */ e.jsxs("span", { className: "text-amber-400", children: [
          s.highlight_count,
          " highlights"
        ] }),
        /* @__PURE__ */ e.jsx(
          "button",
          {
            onClick: () => b(`#/greatshot/demo/${encodeURIComponent(s.id)}`),
            className: "px-2 py-1 rounded border border-cyan-400/40 text-cyan-400 hover:bg-cyan-400/10 transition",
            children: "Open"
          }
        )
      ] })
    ] }, s.id)) }) : n === "clips" ? U.length === 0 ? /* @__PURE__ */ e.jsx(g, { message: "No clip candidates yet. Highlights appear after analysis." }) : /* @__PURE__ */ e.jsx("div", { className: "space-y-2", children: U.slice(0, 12).map((s) => /* @__PURE__ */ e.jsxs("div", { className: "flex items-center justify-between glass-card rounded-xl p-3 border border-white/5", children: [
      /* @__PURE__ */ e.jsx("span", { className: "text-sm text-slate-200 truncate", children: s.filename || s.id }),
      /* @__PURE__ */ e.jsxs("div", { className: "flex items-center gap-3 text-xs shrink-0", children: [
        /* @__PURE__ */ e.jsxs("span", { className: "text-slate-400", children: [
          s.highlight_count,
          " clip windows"
        ] }),
        /* @__PURE__ */ e.jsx(
          "button",
          {
            onClick: () => b(`#/greatshot/demo/${encodeURIComponent(s.id)}`),
            className: "px-2 py-1 rounded border border-cyan-400/40 text-cyan-400 hover:bg-cyan-400/10 transition",
            children: "Manage"
          }
        )
      ] })
    ] }, s.id)) }) : $.length === 0 ? /* @__PURE__ */ e.jsx(g, { message: "No render jobs yet. Queue rendering from a demo highlight." }) : /* @__PURE__ */ e.jsx("div", { className: "space-y-2", children: $.slice(0, 12).map((s) => /* @__PURE__ */ e.jsxs("div", { className: "flex items-center justify-between glass-card rounded-xl p-3 border border-white/5", children: [
      /* @__PURE__ */ e.jsx("span", { className: "text-sm text-slate-200 truncate", children: s.filename || s.id }),
      /* @__PURE__ */ e.jsxs("div", { className: "flex items-center gap-3 text-xs shrink-0", children: [
        /* @__PURE__ */ e.jsxs("span", { className: "text-emerald-400", children: [
          s.rendered_count,
          " rendered"
        ] }),
        /* @__PURE__ */ e.jsxs("span", { className: "text-slate-400", children: [
          s.render_job_count,
          " total"
        ] }),
        /* @__PURE__ */ e.jsx(
          "button",
          {
            onClick: () => b(`#/greatshot/demo/${encodeURIComponent(s.id)}`),
            className: "px-2 py-1 rounded border border-cyan-400/40 text-cyan-400 hover:bg-cyan-400/10 transition",
            children: "Open"
          }
        )
      ] })
    ] }, s.id)) })
  ] }) : /* @__PURE__ */ e.jsxs("div", { children: [
    /* @__PURE__ */ e.jsx(I, { title: "Greatshot", subtitle: "Demo analysis and highlight rendering" }),
    /* @__PURE__ */ e.jsxs(y, { className: "text-center py-12", children: [
      /* @__PURE__ */ e.jsx("div", { className: "text-4xl mb-4", children: "🔒" }),
      /* @__PURE__ */ e.jsx("div", { className: "text-lg font-bold text-white mb-2", children: "Login Required" }),
      /* @__PURE__ */ e.jsx("p", { className: "text-sm text-slate-400 mb-6", children: "Sign in with Discord to upload and analyze demos." }),
      /* @__PURE__ */ e.jsx(
        "a",
        {
          href: "/auth/discord",
          className: "inline-flex items-center gap-2 px-6 py-3 bg-[#5865F2] hover:bg-[#4752C4] text-white font-bold rounded-xl transition-colors",
          children: "Login with Discord"
        }
      )
    ] })
  ] });
}
export {
  ee as default
};
