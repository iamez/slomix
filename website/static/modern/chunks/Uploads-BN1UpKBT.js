import { r as a, j as e, S as G } from "./route-host-Ba3v8uFM.js";
import { P as O } from "./PageHeader-CQ7BTOQj.js";
import { G as R } from "./GlassPanel-C-uUmQaB.js";
import { E as H } from "./EmptyState-CWT5OHyQ.js";
import { G as z, H as B, I as L } from "./hooks-CyQgvbI9.js";
import { n as q } from "./navigation-BDd1HkpE.js";
const K = [
  { value: "", label: "All" },
  { value: "config", label: "Config", color: "text-cyan-400 border-cyan-400/30 bg-cyan-400/10" },
  { value: "hud", label: "HUD", color: "text-purple-400 border-purple-400/30 bg-purple-400/10" },
  { value: "archive", label: "Archive", color: "text-amber-400 border-amber-400/30 bg-amber-400/10" },
  { value: "clip", label: "Clip", color: "text-emerald-400 border-emerald-400/30 bg-emerald-400/10" }
], Z = {
  config: "text-cyan-400 border-cyan-400/30 bg-cyan-400/10",
  hud: "text-purple-400 border-purple-400/30 bg-purple-400/10",
  archive: "text-amber-400 border-amber-400/30 bg-amber-400/10",
  clip: "text-emerald-400 border-emerald-400/30 bg-emerald-400/10"
};
function J(s) {
  return s < 1024 ? `${s} B` : s < 1024 * 1024 ? `${(s / 1024).toFixed(1)} KB` : `${(s / (1024 * 1024)).toFixed(1)} MB`;
}
const n = 50;
function te() {
  const [s, y] = a.useState(""), [N, C] = a.useState(""), [m, S] = a.useState(""), [l, i] = a.useState(0), [b, h] = a.useState(!1), [d, c] = a.useState(null), f = a.useRef(void 0), [U, k] = a.useState(""), { data: T } = z(), { data: g, isLoading: E, refetch: P } = B({
    category: s || void 0,
    tag: m || void 0,
    search: N || void 0,
    limit: n,
    offset: l
  }), { data: x } = L(), $ = a.useCallback((t) => {
    k(t), clearTimeout(f.current), f.current = setTimeout(() => {
      C(t), i(0);
    }, 400);
  }, []), A = (t) => {
    y(t), i(0);
  }, _ = (t) => {
    S((r) => r === t ? "" : t), i(0);
  }, D = async (t) => {
    t.preventDefault();
    const r = t.currentTarget, w = new FormData(r), p = w.get("file");
    if (!(!p || p.size === 0)) {
      h(!0), c(null);
      try {
        const o = await fetch("/api/uploads", { method: "POST", body: w });
        if (!o.ok) {
          const I = await o.json().catch(() => ({ detail: "Upload failed" }));
          throw new Error(I.detail || "Upload failed");
        }
        const F = await o.json();
        c({ text: `Uploaded: ${F.filename || p.name}`, type: "success" }), r.reset(), P();
      } catch (o) {
        c({ text: o instanceof Error ? o.message : "Upload failed", type: "error" });
      } finally {
        h(!1);
      }
    }
  }, v = g?.items ?? [], u = g?.total ?? 0, j = Math.ceil(u / n), M = Math.floor(l / n) + 1;
  return /* @__PURE__ */ e.jsxs("div", { children: [
    /* @__PURE__ */ e.jsx(O, { title: "Uploads", subtitle: `${u} community files` }),
    T && /* @__PURE__ */ e.jsxs(R, { className: "mb-6", children: [
      /* @__PURE__ */ e.jsx("div", { className: "text-xs font-bold uppercase tracking-widest text-slate-500 mb-3", children: "Upload a file" }),
      /* @__PURE__ */ e.jsxs("form", { onSubmit: D, className: "flex flex-col sm:flex-row items-start sm:items-end gap-3", children: [
        /* @__PURE__ */ e.jsxs("label", { className: "flex-1 min-w-0", children: [
          /* @__PURE__ */ e.jsx("span", { className: "text-xs text-slate-400 mb-1 block", children: "File" }),
          /* @__PURE__ */ e.jsx(
            "input",
            {
              type: "file",
              name: "file",
              required: !0,
              className: "w-full text-sm text-slate-300 file:mr-3 file:py-2 file:px-4 file:rounded-lg file:border-0 file:text-sm file:font-bold file:bg-slate-700 file:text-slate-200 hover:file:bg-slate-600 cursor-pointer"
            }
          )
        ] }),
        /* @__PURE__ */ e.jsxs("label", { children: [
          /* @__PURE__ */ e.jsx("span", { className: "text-xs text-slate-400 mb-1 block", children: "Category" }),
          /* @__PURE__ */ e.jsxs(
            "select",
            {
              name: "category",
              required: !0,
              className: "bg-slate-800 border border-white/10 text-slate-200 rounded-lg px-3 py-2 text-sm focus:outline-none focus:border-blue-500/50",
              children: [
                /* @__PURE__ */ e.jsx("option", { value: "config", children: "Config" }),
                /* @__PURE__ */ e.jsx("option", { value: "hud", children: "HUD" }),
                /* @__PURE__ */ e.jsx("option", { value: "archive", children: "Archive" }),
                /* @__PURE__ */ e.jsx("option", { value: "clip", children: "Clip" })
              ]
            }
          )
        ] }),
        /* @__PURE__ */ e.jsxs("label", { className: "flex-1 min-w-0", children: [
          /* @__PURE__ */ e.jsx("span", { className: "text-xs text-slate-400 mb-1 block", children: "Title (optional)" }),
          /* @__PURE__ */ e.jsx(
            "input",
            {
              type: "text",
              name: "title",
              placeholder: "File title...",
              className: "w-full bg-slate-800 border border-white/10 text-slate-200 rounded-lg px-3 py-2 text-sm focus:outline-none focus:border-blue-500/50"
            }
          )
        ] }),
        /* @__PURE__ */ e.jsx(
          "button",
          {
            type: "submit",
            disabled: b,
            className: "px-5 py-2 bg-blue-600 hover:bg-blue-500 disabled:bg-slate-700 disabled:text-slate-500 text-white text-sm font-bold rounded-lg transition-colors",
            children: b ? "Uploading..." : "Upload"
          }
        )
      ] }),
      d && /* @__PURE__ */ e.jsx("div", { className: `mt-3 text-sm font-medium ${d.type === "success" ? "text-emerald-400" : "text-rose-400"}`, children: d.text })
    ] }),
    /* @__PURE__ */ e.jsxs("div", { className: "flex flex-wrap items-center gap-2 mb-4", children: [
      K.map((t) => /* @__PURE__ */ e.jsx(
        "button",
        {
          onClick: () => A(t.value),
          className: `px-3 py-1.5 rounded-lg text-xs font-bold uppercase tracking-wider border transition-all ${s === t.value ? "bg-white/10 border-white/20 text-white" : "border-white/5 text-slate-400 hover:border-white/10 hover:text-slate-200"}`,
          children: t.label
        },
        t.value
      )),
      /* @__PURE__ */ e.jsx("div", { className: "flex-1" }),
      /* @__PURE__ */ e.jsx(
        "input",
        {
          type: "text",
          value: U,
          onChange: (t) => $(t.target.value),
          placeholder: "Search uploads...",
          className: "bg-slate-800 border border-white/10 text-slate-200 rounded-lg px-3 py-1.5 text-sm w-48 focus:outline-none focus:border-blue-500/50"
        }
      )
    ] }),
    x && x.length > 0 && /* @__PURE__ */ e.jsx("div", { className: "flex flex-wrap gap-1.5 mb-6", children: x.map((t) => /* @__PURE__ */ e.jsxs(
      "button",
      {
        onClick: () => _(t.tag),
        className: `px-2 py-0.5 rounded-full text-[10px] font-bold border transition-all ${m === t.tag ? "bg-purple-500/20 border-purple-400/40 text-purple-300" : "border-white/10 text-slate-500 hover:text-slate-300 hover:border-white/15"}`,
        children: [
          "#",
          t.tag,
          /* @__PURE__ */ e.jsx("span", { className: "ml-1 opacity-50", children: t.count })
        ]
      },
      t.tag
    )) }),
    E ? /* @__PURE__ */ e.jsx(G, { variant: "card", count: 6 }) : v.length === 0 ? /* @__PURE__ */ e.jsx(H, { message: "No uploads found." }) : /* @__PURE__ */ e.jsx("div", { className: "grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4", children: v.map((t) => {
      const r = Z[t.category] || "text-slate-400 border-white/10 bg-white/5";
      return /* @__PURE__ */ e.jsxs(
        "div",
        {
          onClick: () => q(`#/uploads/${encodeURIComponent(t.id)}`),
          className: "glass-card rounded-xl p-5 border border-white/5 hover:border-white/10 hover:bg-white/[0.03] transition-all cursor-pointer group",
          children: [
            /* @__PURE__ */ e.jsxs("div", { className: "flex items-start justify-between gap-2 mb-3", children: [
              /* @__PURE__ */ e.jsxs("div", { className: "min-w-0", children: [
                /* @__PURE__ */ e.jsx("div", { className: "text-sm font-bold text-white truncate group-hover:text-blue-300 transition-colors", children: t.title || t.filename }),
                /* @__PURE__ */ e.jsx("div", { className: "text-[10px] text-slate-600 font-mono truncate mt-0.5", children: t.filename })
              ] }),
              /* @__PURE__ */ e.jsx("span", { className: `shrink-0 px-2 py-0.5 rounded-full text-[10px] font-bold uppercase border ${r}`, children: t.category })
            ] }),
            /* @__PURE__ */ e.jsxs("div", { className: "flex items-center gap-4 text-[10px] text-slate-500", children: [
              /* @__PURE__ */ e.jsx("span", { children: J(t.file_size_bytes) }),
              /* @__PURE__ */ e.jsxs("span", { children: [
                t.download_count,
                " downloads"
              ] }),
              /* @__PURE__ */ e.jsx("span", { className: "ml-auto", children: t.uploader_name || "Anonymous" })
            ] }),
            t.created_at && /* @__PURE__ */ e.jsx("div", { className: "text-[10px] text-slate-600 mt-1.5", children: new Date(t.created_at).toLocaleDateString() })
          ]
        },
        t.id
      );
    }) }),
    j > 1 && /* @__PURE__ */ e.jsxs("div", { className: "flex items-center justify-center gap-3 mt-8", children: [
      /* @__PURE__ */ e.jsx(
        "button",
        {
          onClick: () => i(Math.max(0, l - n)),
          disabled: l === 0,
          className: "px-3 py-1.5 rounded-lg text-xs font-bold border border-white/10 text-slate-400 hover:text-white hover:border-white/20 disabled:opacity-30 disabled:cursor-not-allowed transition-all",
          children: "Previous"
        }
      ),
      /* @__PURE__ */ e.jsxs("span", { className: "text-xs text-slate-500", children: [
        "Page ",
        M,
        " of ",
        j
      ] }),
      /* @__PURE__ */ e.jsx(
        "button",
        {
          onClick: () => i(l + n),
          disabled: l + n >= u,
          className: "px-3 py-1.5 rounded-lg text-xs font-bold border border-white/10 text-slate-400 hover:text-white hover:border-white/20 disabled:opacity-30 disabled:cursor-not-allowed transition-all",
          children: "Next"
        }
      )
    ] })
  ] });
}
export {
  te as default
};
