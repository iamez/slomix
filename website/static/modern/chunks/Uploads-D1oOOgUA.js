import { jsxs as a, jsx as t } from "react/jsx-runtime";
import { useState as r, useRef as G, useCallback as R } from "react";
import { P as z } from "./PageHeader-D4CVo02x.js";
import { G as B } from "./GlassPanel-S_ADyiYR.js";
import { S as H } from "./route-host-CUL1oI6Z.js";
import { E as L } from "./EmptyState-DvtQr4qR.js";
import { v as q, w as K, x as Z } from "./hooks-UFUMZFGB.js";
import { n as J } from "./navigation-BDd1HkpE.js";
const Q = [
  { value: "", label: "All" },
  { value: "config", label: "Config", color: "text-cyan-400 border-cyan-400/30 bg-cyan-400/10" },
  { value: "hud", label: "HUD", color: "text-purple-400 border-purple-400/30 bg-purple-400/10" },
  { value: "archive", label: "Archive", color: "text-amber-400 border-amber-400/30 bg-amber-400/10" },
  { value: "clip", label: "Clip", color: "text-emerald-400 border-emerald-400/30 bg-emerald-400/10" }
], V = {
  config: "text-cyan-400 border-cyan-400/30 bg-cyan-400/10",
  hud: "text-purple-400 border-purple-400/30 bg-purple-400/10",
  archive: "text-amber-400 border-amber-400/30 bg-amber-400/10",
  clip: "text-emerald-400 border-emerald-400/30 bg-emerald-400/10"
};
function W(l) {
  return l < 1024 ? `${l} B` : l < 1024 * 1024 ? `${(l / 1024).toFixed(1)} KB` : `${(l / (1024 * 1024)).toFixed(1)} MB`;
}
const i = 50;
function se() {
  const [l, C] = r(""), [U, k] = r(""), [h, S] = r(""), [o, d] = r(0), [x, f] = r(!1), [c, p] = r(null), g = G(void 0), [T, P] = r(""), { data: $ } = q(), { data: v, isLoading: A, refetch: E } = K({
    category: l || void 0,
    tag: h || void 0,
    search: U || void 0,
    limit: i,
    offset: o
  }), { data: u } = Z(), _ = R((e) => {
    P(e), clearTimeout(g.current), g.current = setTimeout(() => {
      k(e), d(0);
    }, 400);
  }, []), D = (e) => {
    C(e), d(0);
  }, M = (e) => {
    S((s) => s === e ? "" : e), d(0);
  }, j = async (e) => {
    e.preventDefault();
    const s = e.currentTarget, N = new FormData(s), b = N.get("file");
    if (!(!b || b.size === 0)) {
      f(!0), p(null);
      try {
        const n = await fetch("/api/uploads", { method: "POST", body: N });
        if (!n.ok) {
          const O = await n.json().catch(() => ({ detail: "Upload failed" }));
          throw new Error(O.detail || "Upload failed");
        }
        const I = await n.json();
        p({ text: `Uploaded: ${I.filename || b.name}`, type: "success" }), s.reset(), E();
      } catch (n) {
        p({ text: n instanceof Error ? n.message : "Upload failed", type: "error" });
      } finally {
        f(!1);
      }
    }
  }, w = v?.items ?? [], m = v?.total ?? 0, y = Math.ceil(m / i), F = Math.floor(o / i) + 1;
  return /* @__PURE__ */ a("div", { children: [
    /* @__PURE__ */ t(z, { title: "Uploads", subtitle: `${m} community files` }),
    $ && /* @__PURE__ */ a(B, { className: "mb-6", children: [
      /* @__PURE__ */ t("div", { className: "text-xs font-bold uppercase tracking-widest text-slate-500 mb-3", children: "Upload a file" }),
      /* @__PURE__ */ a("form", { onSubmit: j, className: "flex flex-col sm:flex-row items-start sm:items-end gap-3", children: [
        /* @__PURE__ */ a("label", { className: "flex-1 min-w-0", children: [
          /* @__PURE__ */ t("span", { className: "text-xs text-slate-400 mb-1 block", children: "File" }),
          /* @__PURE__ */ t(
            "input",
            {
              type: "file",
              name: "file",
              required: !0,
              className: "w-full text-sm text-slate-300 file:mr-3 file:py-2 file:px-4 file:rounded-lg file:border-0 file:text-sm file:font-bold file:bg-slate-700 file:text-slate-200 hover:file:bg-slate-600 cursor-pointer"
            }
          )
        ] }),
        /* @__PURE__ */ a("label", { children: [
          /* @__PURE__ */ t("span", { className: "text-xs text-slate-400 mb-1 block", children: "Category" }),
          /* @__PURE__ */ a(
            "select",
            {
              name: "category",
              required: !0,
              className: "bg-slate-800 border border-white/10 text-slate-200 rounded-lg px-3 py-2 text-sm focus:outline-none focus:border-blue-500/50",
              children: [
                /* @__PURE__ */ t("option", { value: "config", children: "Config" }),
                /* @__PURE__ */ t("option", { value: "hud", children: "HUD" }),
                /* @__PURE__ */ t("option", { value: "archive", children: "Archive" }),
                /* @__PURE__ */ t("option", { value: "clip", children: "Clip" })
              ]
            }
          )
        ] }),
        /* @__PURE__ */ a("label", { className: "flex-1 min-w-0", children: [
          /* @__PURE__ */ t("span", { className: "text-xs text-slate-400 mb-1 block", children: "Title (optional)" }),
          /* @__PURE__ */ t(
            "input",
            {
              type: "text",
              name: "title",
              placeholder: "File title...",
              className: "w-full bg-slate-800 border border-white/10 text-slate-200 rounded-lg px-3 py-2 text-sm focus:outline-none focus:border-blue-500/50"
            }
          )
        ] }),
        /* @__PURE__ */ t(
          "button",
          {
            type: "submit",
            disabled: x,
            className: "px-5 py-2 bg-blue-600 hover:bg-blue-500 disabled:bg-slate-700 disabled:text-slate-500 text-white text-sm font-bold rounded-lg transition-colors",
            children: x ? "Uploading..." : "Upload"
          }
        )
      ] }),
      c && /* @__PURE__ */ t("div", { className: `mt-3 text-sm font-medium ${c.type === "success" ? "text-emerald-400" : "text-rose-400"}`, children: c.text })
    ] }),
    /* @__PURE__ */ a("div", { className: "flex flex-wrap items-center gap-2 mb-4", children: [
      Q.map((e) => /* @__PURE__ */ t(
        "button",
        {
          onClick: () => D(e.value),
          className: `px-3 py-1.5 rounded-lg text-xs font-bold uppercase tracking-wider border transition-all ${l === e.value ? "bg-white/10 border-white/20 text-white" : "border-white/5 text-slate-400 hover:border-white/10 hover:text-slate-200"}`,
          children: e.label
        },
        e.value
      )),
      /* @__PURE__ */ t("div", { className: "flex-1" }),
      /* @__PURE__ */ t(
        "input",
        {
          type: "text",
          value: T,
          onChange: (e) => _(e.target.value),
          placeholder: "Search uploads...",
          className: "bg-slate-800 border border-white/10 text-slate-200 rounded-lg px-3 py-1.5 text-sm w-48 focus:outline-none focus:border-blue-500/50"
        }
      )
    ] }),
    u && u.length > 0 && /* @__PURE__ */ t("div", { className: "flex flex-wrap gap-1.5 mb-6", children: u.map((e) => /* @__PURE__ */ a(
      "button",
      {
        onClick: () => M(e.tag),
        className: `px-2 py-0.5 rounded-full text-[10px] font-bold border transition-all ${h === e.tag ? "bg-purple-500/20 border-purple-400/40 text-purple-300" : "border-white/10 text-slate-500 hover:text-slate-300 hover:border-white/15"}`,
        children: [
          "#",
          e.tag,
          /* @__PURE__ */ t("span", { className: "ml-1 opacity-50", children: e.count })
        ]
      },
      e.tag
    )) }),
    A ? /* @__PURE__ */ t(H, { variant: "card", count: 6 }) : w.length === 0 ? /* @__PURE__ */ t(L, { message: "No uploads found." }) : /* @__PURE__ */ t("div", { className: "grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4", children: w.map((e) => {
      const s = V[e.category] || "text-slate-400 border-white/10 bg-white/5";
      return /* @__PURE__ */ a(
        "div",
        {
          onClick: () => J(`#/uploads/${encodeURIComponent(e.id)}`),
          className: "glass-card rounded-xl p-5 border border-white/5 hover:border-white/10 hover:bg-white/[0.03] transition-all cursor-pointer group",
          children: [
            /* @__PURE__ */ a("div", { className: "flex items-start justify-between gap-2 mb-3", children: [
              /* @__PURE__ */ a("div", { className: "min-w-0", children: [
                /* @__PURE__ */ t("div", { className: "text-sm font-bold text-white truncate group-hover:text-blue-300 transition-colors", children: e.title || e.filename }),
                /* @__PURE__ */ t("div", { className: "text-[10px] text-slate-600 font-mono truncate mt-0.5", children: e.filename })
              ] }),
              /* @__PURE__ */ t("span", { className: `shrink-0 px-2 py-0.5 rounded-full text-[10px] font-bold uppercase border ${s}`, children: e.category })
            ] }),
            /* @__PURE__ */ a("div", { className: "flex items-center gap-4 text-[10px] text-slate-500", children: [
              /* @__PURE__ */ t("span", { children: W(e.file_size_bytes) }),
              /* @__PURE__ */ a("span", { children: [
                e.download_count,
                " downloads"
              ] }),
              /* @__PURE__ */ t("span", { className: "ml-auto", children: e.uploader_name || "Anonymous" })
            ] }),
            e.created_at && /* @__PURE__ */ t("div", { className: "text-[10px] text-slate-600 mt-1.5", children: new Date(e.created_at).toLocaleDateString() })
          ]
        },
        e.id
      );
    }) }),
    y > 1 && /* @__PURE__ */ a("div", { className: "flex items-center justify-center gap-3 mt-8", children: [
      /* @__PURE__ */ t(
        "button",
        {
          onClick: () => d(Math.max(0, o - i)),
          disabled: o === 0,
          className: "px-3 py-1.5 rounded-lg text-xs font-bold border border-white/10 text-slate-400 hover:text-white hover:border-white/20 disabled:opacity-30 disabled:cursor-not-allowed transition-all",
          children: "Previous"
        }
      ),
      /* @__PURE__ */ a("span", { className: "text-xs text-slate-500", children: [
        "Page ",
        F,
        " of ",
        y
      ] }),
      /* @__PURE__ */ t(
        "button",
        {
          onClick: () => d(o + i),
          disabled: o + i >= m,
          className: "px-3 py-1.5 rounded-lg text-xs font-bold border border-white/10 text-slate-400 hover:text-white hover:border-white/20 disabled:opacity-30 disabled:cursor-not-allowed transition-all",
          children: "Next"
        }
      )
    ] })
  ] });
}
export {
  se as default
};
