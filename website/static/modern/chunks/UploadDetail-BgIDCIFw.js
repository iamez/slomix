import { r as u, j as e, S as f } from "./route-host-Ba3v8uFM.js";
import { P as g } from "./PageHeader-CQ7BTOQj.js";
import { G as a } from "./GlassPanel-C-uUmQaB.js";
import { J as j } from "./hooks-CyQgvbI9.js";
import { n as x } from "./navigation-BDd1HkpE.js";
const v = {
  config: "text-cyan-400 border-cyan-400/30 bg-cyan-400/10",
  hud: "text-purple-400 border-purple-400/30 bg-purple-400/10",
  archive: "text-amber-400 border-amber-400/30 bg-amber-400/10",
  clip: "text-emerald-400 border-emerald-400/30 bg-emerald-400/10"
};
function p(s) {
  return s < 1024 ? `${s} B` : s < 1024 * 1024 ? `${(s / 1024).toFixed(1)} KB` : `${(s / (1024 * 1024)).toFixed(1)} MB`;
}
function C({ params: s }) {
  const m = s?.uploadId ?? null, { data: t, isLoading: h, error: b } = j(m), [r, o] = u.useState(!1);
  if (h) return /* @__PURE__ */ e.jsx(f, { variant: "card", count: 3 });
  if (b || !t)
    return /* @__PURE__ */ e.jsxs("div", { className: "text-center py-16", children: [
      /* @__PURE__ */ e.jsx("div", { className: "text-4xl mb-4", children: "🔍" }),
      /* @__PURE__ */ e.jsx("div", { className: "text-lg font-bold text-rose-400 mb-1", children: "Upload not found" }),
      /* @__PURE__ */ e.jsx("p", { className: "text-sm text-slate-500 mb-4", children: "This upload may have been deleted or the link is invalid." }),
      /* @__PURE__ */ e.jsx(
        "button",
        {
          onClick: () => x("#/uploads"),
          className: "text-sm text-cyan-400 hover:text-white transition-colors",
          children: "Browse all uploads"
        }
      )
    ] });
  const n = v[t.category] || "text-slate-400 border-white/10 bg-white/5", i = `${window.location.origin}${window.location.pathname}#/uploads/${encodeURIComponent(t.id)}`, d = `/api/uploads/${encodeURIComponent(t.id)}/download`, c = () => {
    navigator.clipboard.writeText(i).then(() => {
      o(!0), setTimeout(() => o(!1), 2e3);
    });
  };
  return /* @__PURE__ */ e.jsxs("div", { children: [
    /* @__PURE__ */ e.jsxs(
      "button",
      {
        onClick: () => x("#/uploads"),
        className: "text-xs text-slate-500 hover:text-slate-300 transition-colors mb-4 inline-flex items-center gap-1",
        children: [
          /* @__PURE__ */ e.jsx("span", { children: "←" }),
          " Back to uploads"
        ]
      }
    ),
    /* @__PURE__ */ e.jsx(g, { title: t.title || t.filename, children: /* @__PURE__ */ e.jsx("span", { className: `px-3 py-1 rounded-full text-xs font-bold uppercase border ${n}`, children: t.category }) }),
    t.filename !== t.title && t.title && /* @__PURE__ */ e.jsx("div", { className: "text-xs text-slate-600 font-mono -mt-6 mb-6", children: t.filename }),
    t.description && /* @__PURE__ */ e.jsx(a, { className: "mb-6", children: /* @__PURE__ */ e.jsx("p", { className: "text-sm text-slate-300 leading-relaxed", children: t.description }) }),
    t.is_playable ? /* @__PURE__ */ e.jsx("div", { className: "rounded-xl overflow-hidden shadow-2xl ring-1 ring-white/10 mb-6", children: /* @__PURE__ */ e.jsxs("video", { controls: !0, className: "w-full bg-black", style: { maxHeight: "70vh" }, children: [
      /* @__PURE__ */ e.jsx("source", { src: d, type: "video/mp4" }),
      "Your browser does not support video playback."
    ] }) }) : /* @__PURE__ */ e.jsxs(a, { className: "mb-6 text-center py-12", children: [
      /* @__PURE__ */ e.jsx("div", { className: `w-20 h-20 mx-auto mb-4 rounded-2xl flex items-center justify-center border ${n}`, children: /* @__PURE__ */ e.jsx("span", { className: "text-3xl", children: t.category === "config" ? "⚙" : t.category === "hud" ? "🖥" : t.category === "clip" ? "🎬" : "📦" }) }),
      /* @__PURE__ */ e.jsx("div", { className: "text-sm text-slate-400", children: t.filename }),
      /* @__PURE__ */ e.jsx("div", { className: "text-xs text-slate-600 mt-1", children: p(t.file_size_bytes) })
    ] }),
    /* @__PURE__ */ e.jsxs("div", { className: "grid grid-cols-2 sm:grid-cols-4 gap-3 mb-6", children: [
      /* @__PURE__ */ e.jsxs(a, { className: "!p-4 text-center", children: [
        /* @__PURE__ */ e.jsx("div", { className: "text-[10px] uppercase tracking-widest text-slate-600 mb-1.5 font-bold", children: "Uploaded by" }),
        /* @__PURE__ */ e.jsx("div", { className: "text-sm font-bold text-white", children: t.uploader_name || "Anonymous" })
      ] }),
      /* @__PURE__ */ e.jsxs(a, { className: "!p-4 text-center", children: [
        /* @__PURE__ */ e.jsx("div", { className: "text-[10px] uppercase tracking-widest text-slate-600 mb-1.5 font-bold", children: "Size" }),
        /* @__PURE__ */ e.jsx("div", { className: "text-sm font-bold text-white", children: p(t.file_size_bytes) })
      ] }),
      /* @__PURE__ */ e.jsxs(a, { className: "!p-4 text-center", children: [
        /* @__PURE__ */ e.jsx("div", { className: "text-[10px] uppercase tracking-widest text-slate-600 mb-1.5 font-bold", children: "Downloads" }),
        /* @__PURE__ */ e.jsx("div", { className: "text-sm font-bold text-white", children: t.download_count })
      ] }),
      /* @__PURE__ */ e.jsxs(a, { className: "!p-4 text-center", children: [
        /* @__PURE__ */ e.jsx("div", { className: "text-[10px] uppercase tracking-widest text-slate-600 mb-1.5 font-bold", children: "Uploaded" }),
        /* @__PURE__ */ e.jsx("div", { className: "text-sm font-bold text-white", children: t.created_at ? new Date(t.created_at).toLocaleDateString() : "Unknown" })
      ] })
    ] }),
    t.tags.length > 0 && /* @__PURE__ */ e.jsx("div", { className: "flex flex-wrap gap-2 mb-6", children: t.tags.map((l) => /* @__PURE__ */ e.jsxs(
      "span",
      {
        className: "px-2.5 py-1 rounded-full text-[10px] font-bold text-slate-400 border border-white/10",
        children: [
          /* @__PURE__ */ e.jsx("span", { className: "opacity-50", children: "#" }),
          l
        ]
      },
      l
    )) }),
    /* @__PURE__ */ e.jsxs("div", { className: "flex flex-wrap gap-3 mb-6", children: [
      /* @__PURE__ */ e.jsx(
        "a",
        {
          href: d,
          className: "inline-flex items-center gap-2 bg-blue-600 hover:bg-blue-500 text-white text-sm font-bold px-6 py-2.5 rounded-xl transition-all shadow-[0_0_20px_rgba(59,130,246,0.3)] hover:shadow-[0_0_30px_rgba(59,130,246,0.5)]",
          children: "Download"
        }
      ),
      /* @__PURE__ */ e.jsx(
        "button",
        {
          onClick: c,
          className: `inline-flex items-center gap-2 text-sm font-bold px-6 py-2.5 rounded-xl border transition-all ${r ? "bg-emerald-500/20 border-emerald-400/30 text-emerald-400" : "bg-purple-500/20 border-purple-400/30 text-purple-400 hover:bg-purple-500/30"}`,
          children: r ? "Copied!" : "Copy Link"
        }
      )
    ] }),
    /* @__PURE__ */ e.jsxs(a, { children: [
      /* @__PURE__ */ e.jsx("div", { className: "text-[10px] uppercase tracking-widest text-slate-600 font-bold mb-2", children: "Shareable Link" }),
      /* @__PURE__ */ e.jsxs("div", { className: "flex items-center gap-2", children: [
        /* @__PURE__ */ e.jsx(
          "input",
          {
            type: "text",
            readOnly: !0,
            value: i,
            onClick: (l) => l.target.select(),
            className: "flex-1 bg-slate-900/50 border border-white/5 rounded-lg px-3 py-2 text-xs text-slate-300 font-mono outline-none focus:border-purple-400/30 transition"
          }
        ),
        /* @__PURE__ */ e.jsx(
          "button",
          {
            onClick: c,
            className: "shrink-0 px-3 py-2 rounded-lg text-xs font-bold text-purple-400 hover:bg-purple-500/10 border border-purple-400/20 transition",
            children: r ? "Copied" : "Copy"
          }
        )
      ] })
    ] })
  ] });
}
export {
  C as default
};
