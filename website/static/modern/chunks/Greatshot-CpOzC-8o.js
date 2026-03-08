import { jsxs as a, jsx as t } from "react/jsx-runtime";
import { useState as b, useRef as L, useCallback as O, useEffect as q } from "react";
import { P as I } from "./PageHeader-D4CVo02x.js";
import { G as v } from "./GlassPanel-S_ADyiYR.js";
import { S as H } from "./route-host-CUL1oI6Z.js";
import { E as x } from "./EmptyState-DvtQr4qR.js";
import { v as F, z as B, A as Q } from "./hooks-UFUMZFGB.js";
import { n as y } from "./navigation-BDd1HkpE.js";
import { m as J } from "./game-assets-CWuRxGFH.js";
const M = {
  uploaded: "text-slate-300 border-slate-500/40 bg-slate-800/40",
  scanning: "text-cyan-400 border-cyan-400/40 bg-cyan-400/10",
  analyzed: "text-emerald-400 border-emerald-400/40 bg-emerald-400/10",
  failed: "text-rose-400 border-rose-400/40 bg-rose-400/10",
  queued: "text-amber-400 border-amber-400/40 bg-amber-400/10",
  rendering: "text-cyan-400 border-cyan-400/40 bg-cyan-400/10",
  rendered: "text-emerald-400 border-emerald-400/40 bg-emerald-400/10"
}, K = [
  { key: "demos", label: "Demos" },
  { key: "highlights", label: "Highlights" },
  { key: "clips", label: "Clips" },
  { key: "renders", label: "Renders" }
];
function V(s) {
  if (s == null || !Number.isFinite(s)) return "--";
  const d = Math.max(0, Math.floor(s / 1e3)), l = Math.floor(d / 3600), f = Math.floor(d % 3600 / 60), g = d % 60;
  return l > 0 ? `${l}:${String(f).padStart(2, "0")}:${String(g).padStart(2, "0")}` : `${String(f).padStart(2, "0")}:${String(g).padStart(2, "0")}`;
}
function W({ item: s }) {
  const d = M[s.status] || "text-slate-300 border-white/10 bg-slate-800/40";
  return /* @__PURE__ */ a(
    "button",
    {
      onClick: () => y(`#/greatshot/demo/${encodeURIComponent(s.id)}`),
      className: "glass-card p-4 rounded-xl border border-white/10 text-left hover:border-cyan-400/40 transition w-full",
      children: [
        /* @__PURE__ */ a("div", { className: "flex items-center justify-between gap-3", children: [
          /* @__PURE__ */ t("div", { className: "text-sm font-bold text-white truncate", children: s.filename || s.id }),
          /* @__PURE__ */ t("span", { className: `text-[10px] font-bold px-2 py-1 rounded border shrink-0 ${d}`, children: s.status.toUpperCase() })
        ] }),
        /* @__PURE__ */ a("div", { className: "mt-2 text-xs text-slate-400 flex flex-wrap items-center gap-3", children: [
          /* @__PURE__ */ a("span", { className: "inline-flex items-center gap-1.5", children: [
            s.map && /* @__PURE__ */ t("img", { src: J(s.map), alt: "", className: "w-4 h-4 rounded-sm object-cover", onError: (l) => {
              l.currentTarget.style.display = "none";
            } }),
            "Map: ",
            s.map || "--"
          ] }),
          /* @__PURE__ */ a("span", { children: [
            "Duration: ",
            V(s.duration_ms)
          ] }),
          /* @__PURE__ */ a("span", { children: [
            "Highlights: ",
            s.highlight_count
          ] }),
          /* @__PURE__ */ a("span", { children: [
            "Renders: ",
            s.rendered_count,
            "/",
            s.render_job_count
          ] }),
          s.created_at && /* @__PURE__ */ t("span", { children: new Date(s.created_at).toLocaleString() })
        ] }),
        s.error && /* @__PURE__ */ t("div", { className: "mt-2 text-xs text-rose-400", children: s.error })
      ]
    }
  );
}
function le({ params: s }) {
  const d = s?.section || "demos", [l, f] = b(d), { data: g } = F(), w = !!g, { data: R, isLoading: A, refetch: N } = B(w), [k, S] = b(!1), [_, P] = b(""), [c, C] = b(/* @__PURE__ */ new Map()), m = L(void 0), h = R?.items ?? [], U = O(async () => {
    const e = new Map(c);
    let r = !1;
    for (const [o, n] of e)
      if (!(n.status === "analyzed" || n.status === "failed"))
        try {
          const i = await Q.getGreatshotStatus(o);
          i.status !== n.status && (e.set(o, { ...n, status: i.status, error: i.error || void 0 }), r = !0);
        } catch {
        }
    if (r) {
      C(e);
      let o = !0;
      for (const [, n] of e)
        if (n.status !== "analyzed" && n.status !== "failed") {
          o = !1;
          break;
        }
      o && (clearInterval(m.current), m.current = void 0, N());
    }
  }, [c, N]);
  q(() => {
    if (c.size > 0) {
      let e = !1;
      for (const [, r] of c)
        if (r.status !== "analyzed" && r.status !== "failed") {
          e = !0;
          break;
        }
      e && !m.current && (m.current = setInterval(U, 2500));
    }
    return () => {
      m.current && (clearInterval(m.current), m.current = void 0);
    };
  }, [c, U]);
  const T = async (e) => {
    e.preventDefault();
    const r = e.currentTarget, n = r.querySelector('input[type="file"]')?.files;
    if (!n || n.length === 0) return;
    S(!0), P("");
    const i = /* @__PURE__ */ new Map();
    for (const p of Array.from(n)) {
      const z = new FormData();
      z.append("file", p);
      try {
        const u = await fetch("/api/greatshot/upload", { method: "POST", body: z });
        if (!u.ok) {
          const G = await u.json().catch(() => ({ detail: "Upload failed" }));
          i.set(`error-${p.name}`, { filename: p.name, status: "failed", error: G.detail });
          continue;
        }
        const E = await u.json();
        i.set(E.demo_id, { filename: p.name, status: "uploaded" });
      } catch (u) {
        i.set(`error-${p.name}`, {
          filename: p.name,
          status: "failed",
          error: u instanceof Error ? u.message : "Upload failed"
        });
      }
    }
    C(i), S(!1), r.reset(), N();
  }, $ = h.filter((e) => e.highlight_count > 0), j = h.filter((e) => e.highlight_count > 0), D = h.filter((e) => e.render_job_count > 0);
  return w ? /* @__PURE__ */ a("div", { children: [
    /* @__PURE__ */ t(I, { title: "Greatshot", subtitle: `${h.length} demos` }),
    /* @__PURE__ */ a(v, { className: "mb-6", children: [
      /* @__PURE__ */ t("div", { className: "text-xs font-bold uppercase tracking-widest text-slate-500 mb-3", children: "Upload Demo" }),
      /* @__PURE__ */ a("form", { onSubmit: T, className: "flex flex-col sm:flex-row items-start sm:items-end gap-3", children: [
        /* @__PURE__ */ a("label", { className: "flex-1 min-w-0", children: [
          /* @__PURE__ */ t("span", { className: "text-xs text-slate-400 mb-1 block", children: "Demo file(s) (.dm_84)" }),
          /* @__PURE__ */ t(
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
        /* @__PURE__ */ t(
          "button",
          {
            type: "submit",
            disabled: k,
            className: "px-5 py-2 bg-cyan-600 hover:bg-cyan-500 disabled:bg-slate-700 disabled:text-slate-500 text-white text-sm font-bold rounded-lg transition-colors",
            children: k ? "Uploading..." : "Upload & Analyze"
          }
        )
      ] }),
      _ && /* @__PURE__ */ t("div", { className: "mt-3 text-sm text-rose-400", children: _ })
    ] }),
    c.size > 0 && /* @__PURE__ */ a(v, { className: "mb-6 border-cyan-400/20", children: [
      /* @__PURE__ */ t("div", { className: "text-xs font-bold uppercase tracking-widest text-cyan-400 mb-3", children: "Analysis Progress" }),
      /* @__PURE__ */ t("div", { className: "space-y-2", children: Array.from(c).map(([e, r]) => {
        const o = M[r.status] || "text-slate-300";
        return /* @__PURE__ */ a("div", { className: "flex items-center gap-2 text-xs", children: [
          r.status === "analyzed" ? /* @__PURE__ */ t("span", { className: "text-emerald-400", children: "✓" }) : r.status === "failed" ? /* @__PURE__ */ t("span", { className: "text-rose-400", children: "✗" }) : /* @__PURE__ */ t("span", { className: "w-3 h-3 inline-block border-2 border-cyan-400/30 border-t-cyan-400 rounded-full animate-spin" }),
          /* @__PURE__ */ t("span", { className: "text-slate-200 truncate flex-1", children: r.filename }),
          /* @__PURE__ */ t("span", { className: o, children: r.status }),
          r.error && /* @__PURE__ */ t("span", { className: "text-rose-400", children: r.error })
        ] }, e);
      }) })
    ] }),
    /* @__PURE__ */ t("div", { className: "flex gap-2 mb-6", children: K.map((e) => /* @__PURE__ */ t(
      "button",
      {
        onClick: () => f(e.key),
        className: `px-3 py-1.5 rounded-lg text-xs font-bold uppercase tracking-wider border transition-all ${l === e.key ? "border-cyan-400/40 text-cyan-400 bg-cyan-400/10" : "border-white/10 text-slate-300 hover:text-white hover:border-cyan-400/40"}`,
        children: e.label
      },
      e.key
    )) }),
    A ? /* @__PURE__ */ t(H, { variant: "card", count: 4 }) : l === "demos" ? h.length === 0 ? /* @__PURE__ */ t(x, { message: "No demos uploaded yet." }) : /* @__PURE__ */ t("div", { className: "space-y-3", children: h.map((e) => /* @__PURE__ */ t(W, { item: e }, e.id)) }) : l === "highlights" ? $.length === 0 ? /* @__PURE__ */ t(x, { message: "No detected highlights yet. Analyze a demo first." }) : /* @__PURE__ */ t("div", { className: "space-y-2", children: $.slice(0, 12).map((e) => /* @__PURE__ */ a("div", { className: "flex items-center justify-between glass-card rounded-xl p-3 border border-white/5", children: [
      /* @__PURE__ */ t("span", { className: "text-sm text-slate-200 truncate", children: e.filename || e.id }),
      /* @__PURE__ */ a("div", { className: "flex items-center gap-3 text-xs shrink-0", children: [
        /* @__PURE__ */ a("span", { className: "text-amber-400", children: [
          e.highlight_count,
          " highlights"
        ] }),
        /* @__PURE__ */ t(
          "button",
          {
            onClick: () => y(`#/greatshot/demo/${encodeURIComponent(e.id)}`),
            className: "px-2 py-1 rounded border border-cyan-400/40 text-cyan-400 hover:bg-cyan-400/10 transition",
            children: "Open"
          }
        )
      ] })
    ] }, e.id)) }) : l === "clips" ? j.length === 0 ? /* @__PURE__ */ t(x, { message: "No clip candidates yet. Highlights appear after analysis." }) : /* @__PURE__ */ t("div", { className: "space-y-2", children: j.slice(0, 12).map((e) => /* @__PURE__ */ a("div", { className: "flex items-center justify-between glass-card rounded-xl p-3 border border-white/5", children: [
      /* @__PURE__ */ t("span", { className: "text-sm text-slate-200 truncate", children: e.filename || e.id }),
      /* @__PURE__ */ a("div", { className: "flex items-center gap-3 text-xs shrink-0", children: [
        /* @__PURE__ */ a("span", { className: "text-slate-400", children: [
          e.highlight_count,
          " clip windows"
        ] }),
        /* @__PURE__ */ t(
          "button",
          {
            onClick: () => y(`#/greatshot/demo/${encodeURIComponent(e.id)}`),
            className: "px-2 py-1 rounded border border-cyan-400/40 text-cyan-400 hover:bg-cyan-400/10 transition",
            children: "Manage"
          }
        )
      ] })
    ] }, e.id)) }) : D.length === 0 ? /* @__PURE__ */ t(x, { message: "No render jobs yet. Queue rendering from a demo highlight." }) : /* @__PURE__ */ t("div", { className: "space-y-2", children: D.slice(0, 12).map((e) => /* @__PURE__ */ a("div", { className: "flex items-center justify-between glass-card rounded-xl p-3 border border-white/5", children: [
      /* @__PURE__ */ t("span", { className: "text-sm text-slate-200 truncate", children: e.filename || e.id }),
      /* @__PURE__ */ a("div", { className: "flex items-center gap-3 text-xs shrink-0", children: [
        /* @__PURE__ */ a("span", { className: "text-emerald-400", children: [
          e.rendered_count,
          " rendered"
        ] }),
        /* @__PURE__ */ a("span", { className: "text-slate-400", children: [
          e.render_job_count,
          " total"
        ] }),
        /* @__PURE__ */ t(
          "button",
          {
            onClick: () => y(`#/greatshot/demo/${encodeURIComponent(e.id)}`),
            className: "px-2 py-1 rounded border border-cyan-400/40 text-cyan-400 hover:bg-cyan-400/10 transition",
            children: "Open"
          }
        )
      ] })
    ] }, e.id)) })
  ] }) : /* @__PURE__ */ a("div", { children: [
    /* @__PURE__ */ t(I, { title: "Greatshot", subtitle: "Demo analysis and highlight rendering" }),
    /* @__PURE__ */ a(v, { className: "text-center py-12", children: [
      /* @__PURE__ */ t("div", { className: "text-4xl mb-4", children: "🔒" }),
      /* @__PURE__ */ t("div", { className: "text-lg font-bold text-white mb-2", children: "Login Required" }),
      /* @__PURE__ */ t("p", { className: "text-sm text-slate-400 mb-6", children: "Sign in with Discord to upload and analyze demos." }),
      /* @__PURE__ */ t(
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
  le as default
};
