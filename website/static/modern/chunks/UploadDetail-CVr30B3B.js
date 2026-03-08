import { jsx as e, jsxs as l } from "react/jsx-runtime";
import { useState as f } from "react";
import { P as g } from "./PageHeader-D4CVo02x.js";
import { G as r } from "./GlassPanel-S_ADyiYR.js";
import { S as v } from "./route-host-CUL1oI6Z.js";
import { y as N } from "./hooks-UFUMZFGB.js";
import { n as m } from "./navigation-BDd1HkpE.js";
const w = {
  config: "text-cyan-400 border-cyan-400/30 bg-cyan-400/10",
  hud: "text-purple-400 border-purple-400/30 bg-purple-400/10",
  archive: "text-amber-400 border-amber-400/30 bg-amber-400/10",
  clip: "text-emerald-400 border-emerald-400/30 bg-emerald-400/10"
};
function x(a) {
  return a < 1024 ? `${a} B` : a < 1024 * 1024 ? `${(a / 1024).toFixed(1)} KB` : `${(a / (1024 * 1024)).toFixed(1)} MB`;
}
function L({ params: a }) {
  const h = a?.uploadId ?? null, { data: t, isLoading: b, error: u } = N(h), [n, s] = f(!1);
  if (b) return /* @__PURE__ */ e(v, { variant: "card", count: 3 });
  if (u || !t)
    return /* @__PURE__ */ l("div", { className: "text-center py-16", children: [
      /* @__PURE__ */ e("div", { className: "text-4xl mb-4", children: "🔍" }),
      /* @__PURE__ */ e("div", { className: "text-lg font-bold text-rose-400 mb-1", children: "Upload not found" }),
      /* @__PURE__ */ e("p", { className: "text-sm text-slate-500 mb-4", children: "This upload may have been deleted or the link is invalid." }),
      /* @__PURE__ */ e(
        "button",
        {
          onClick: () => m("#/uploads"),
          className: "text-sm text-cyan-400 hover:text-white transition-colors",
          children: "Browse all uploads"
        }
      )
    ] });
  const i = w[t.category] || "text-slate-400 border-white/10 bg-white/5", d = `${window.location.origin}${window.location.pathname}#/uploads/${encodeURIComponent(t.id)}`, c = `/api/uploads/${encodeURIComponent(t.id)}/download`, p = () => {
    navigator.clipboard.writeText(d).then(() => {
      s(!0), setTimeout(() => s(!1), 2e3);
    });
  };
  return /* @__PURE__ */ l("div", { children: [
    /* @__PURE__ */ l(
      "button",
      {
        onClick: () => m("#/uploads"),
        className: "text-xs text-slate-500 hover:text-slate-300 transition-colors mb-4 inline-flex items-center gap-1",
        children: [
          /* @__PURE__ */ e("span", { children: "←" }),
          " Back to uploads"
        ]
      }
    ),
    /* @__PURE__ */ e(g, { title: t.title || t.filename, children: /* @__PURE__ */ e("span", { className: `px-3 py-1 rounded-full text-xs font-bold uppercase border ${i}`, children: t.category }) }),
    t.filename !== t.title && t.title && /* @__PURE__ */ e("div", { className: "text-xs text-slate-600 font-mono -mt-6 mb-6", children: t.filename }),
    t.description && /* @__PURE__ */ e(r, { className: "mb-6", children: /* @__PURE__ */ e("p", { className: "text-sm text-slate-300 leading-relaxed", children: t.description }) }),
    t.is_playable ? /* @__PURE__ */ e("div", { className: "rounded-xl overflow-hidden shadow-2xl ring-1 ring-white/10 mb-6", children: /* @__PURE__ */ l("video", { controls: !0, className: "w-full bg-black", style: { maxHeight: "70vh" }, children: [
      /* @__PURE__ */ e("source", { src: c, type: "video/mp4" }),
      "Your browser does not support video playback."
    ] }) }) : /* @__PURE__ */ l(r, { className: "mb-6 text-center py-12", children: [
      /* @__PURE__ */ e("div", { className: `w-20 h-20 mx-auto mb-4 rounded-2xl flex items-center justify-center border ${i}`, children: /* @__PURE__ */ e("span", { className: "text-3xl", children: t.category === "config" ? "⚙" : t.category === "hud" ? "🖥" : t.category === "clip" ? "🎬" : "📦" }) }),
      /* @__PURE__ */ e("div", { className: "text-sm text-slate-400", children: t.filename }),
      /* @__PURE__ */ e("div", { className: "text-xs text-slate-600 mt-1", children: x(t.file_size_bytes) })
    ] }),
    /* @__PURE__ */ l("div", { className: "grid grid-cols-2 sm:grid-cols-4 gap-3 mb-6", children: [
      /* @__PURE__ */ l(r, { className: "!p-4 text-center", children: [
        /* @__PURE__ */ e("div", { className: "text-[10px] uppercase tracking-widest text-slate-600 mb-1.5 font-bold", children: "Uploaded by" }),
        /* @__PURE__ */ e("div", { className: "text-sm font-bold text-white", children: t.uploader_name || "Anonymous" })
      ] }),
      /* @__PURE__ */ l(r, { className: "!p-4 text-center", children: [
        /* @__PURE__ */ e("div", { className: "text-[10px] uppercase tracking-widest text-slate-600 mb-1.5 font-bold", children: "Size" }),
        /* @__PURE__ */ e("div", { className: "text-sm font-bold text-white", children: x(t.file_size_bytes) })
      ] }),
      /* @__PURE__ */ l(r, { className: "!p-4 text-center", children: [
        /* @__PURE__ */ e("div", { className: "text-[10px] uppercase tracking-widest text-slate-600 mb-1.5 font-bold", children: "Downloads" }),
        /* @__PURE__ */ e("div", { className: "text-sm font-bold text-white", children: t.download_count })
      ] }),
      /* @__PURE__ */ l(r, { className: "!p-4 text-center", children: [
        /* @__PURE__ */ e("div", { className: "text-[10px] uppercase tracking-widest text-slate-600 mb-1.5 font-bold", children: "Uploaded" }),
        /* @__PURE__ */ e("div", { className: "text-sm font-bold text-white", children: t.created_at ? new Date(t.created_at).toLocaleDateString() : "Unknown" })
      ] })
    ] }),
    t.tags.length > 0 && /* @__PURE__ */ e("div", { className: "flex flex-wrap gap-2 mb-6", children: t.tags.map((o) => /* @__PURE__ */ l(
      "span",
      {
        className: "px-2.5 py-1 rounded-full text-[10px] font-bold text-slate-400 border border-white/10",
        children: [
          /* @__PURE__ */ e("span", { className: "opacity-50", children: "#" }),
          o
        ]
      },
      o
    )) }),
    /* @__PURE__ */ l("div", { className: "flex flex-wrap gap-3 mb-6", children: [
      /* @__PURE__ */ e(
        "a",
        {
          href: c,
          className: "inline-flex items-center gap-2 bg-blue-600 hover:bg-blue-500 text-white text-sm font-bold px-6 py-2.5 rounded-xl transition-all shadow-[0_0_20px_rgba(59,130,246,0.3)] hover:shadow-[0_0_30px_rgba(59,130,246,0.5)]",
          children: "Download"
        }
      ),
      /* @__PURE__ */ e(
        "button",
        {
          onClick: p,
          className: `inline-flex items-center gap-2 text-sm font-bold px-6 py-2.5 rounded-xl border transition-all ${n ? "bg-emerald-500/20 border-emerald-400/30 text-emerald-400" : "bg-purple-500/20 border-purple-400/30 text-purple-400 hover:bg-purple-500/30"}`,
          children: n ? "Copied!" : "Copy Link"
        }
      )
    ] }),
    /* @__PURE__ */ l(r, { children: [
      /* @__PURE__ */ e("div", { className: "text-[10px] uppercase tracking-widest text-slate-600 font-bold mb-2", children: "Shareable Link" }),
      /* @__PURE__ */ l("div", { className: "flex items-center gap-2", children: [
        /* @__PURE__ */ e(
          "input",
          {
            type: "text",
            readOnly: !0,
            value: d,
            onClick: (o) => o.target.select(),
            className: "flex-1 bg-slate-900/50 border border-white/5 rounded-lg px-3 py-2 text-xs text-slate-300 font-mono outline-none focus:border-purple-400/30 transition"
          }
        ),
        /* @__PURE__ */ e(
          "button",
          {
            onClick: p,
            className: "shrink-0 px-3 py-2 rounded-lg text-xs font-bold text-purple-400 hover:bg-purple-500/10 border border-purple-400/20 transition",
            children: n ? "Copied" : "Copy"
          }
        )
      ] })
    ] })
  ] });
}
export {
  L as default
};
