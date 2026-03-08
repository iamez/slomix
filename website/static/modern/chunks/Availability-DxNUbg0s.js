import { jsx as e, jsxs as t, Fragment as T } from "react/jsx-runtime";
import { useState as f, useMemo as F, useCallback as R } from "react";
import { u as W, S as J } from "./route-host-CUL1oI6Z.js";
import { P as K } from "./PageHeader-D4CVo02x.js";
import { G as U } from "./GlassPanel-S_ADyiYR.js";
import { G as B } from "./GlassCard-DKnnuJMt.js";
import { D as X, E as Z, v as ee, A as M, F as te, G as ae } from "./hooks-UFUMZFGB.js";
const N = {
  LOOKING: { label: "Looking", short: "LFG", emoji: "🔍", color: "text-cyan-400", bg: "bg-cyan-500", border: "border-cyan-500/50", idle: "border-white/15 text-slate-300 hover:border-cyan-500/40" },
  AVAILABLE: { label: "Available", short: "IN", emoji: "✅", color: "text-emerald-400", bg: "bg-emerald-500", border: "border-emerald-500/50", idle: "border-white/15 text-slate-300 hover:border-emerald-500/40" },
  MAYBE: { label: "Maybe", short: "Maybe", emoji: "🤔", color: "text-amber-400", bg: "bg-amber-500", border: "border-amber-500/50", idle: "border-white/15 text-slate-300 hover:border-amber-500/40" },
  NOT_PLAYING: { label: "Not Playing", short: "Out", emoji: "❌", color: "text-rose-400", bg: "bg-rose-500", border: "border-rose-500/50", idle: "border-white/15 text-slate-300 hover:border-rose-500/40" }
}, I = ["LOOKING", "AVAILABLE", "MAYBE", "NOT_PLAYING"], q = 7;
function O(s) {
  return `${s.getFullYear()}-${String(s.getMonth() + 1).padStart(2, "0")}-${String(s.getDate()).padStart(2, "0")}`;
}
function Q(s) {
  const n = s.match(/^(\d{4})-(\d{2})-(\d{2})$/);
  return n ? new Date(+n[1], +n[2] - 1, +n[3]) : null;
}
function E(s, n) {
  const r = new Date(s);
  return r.setDate(r.getDate() + n), r;
}
function z(s) {
  return new Date(s.getFullYear(), s.getMonth(), 1);
}
function se(s) {
  const n = Q(s);
  if (!n) return !0;
  const r = /* @__PURE__ */ new Date();
  return n < new Date(r.getFullYear(), r.getMonth(), r.getDate());
}
function G(s, n) {
  const r = Q(s);
  return r ? r.toLocaleDateString(void 0, n) : s;
}
function H({ counts: s, total: n, className: r = "h-1.5" }) {
  return n ? /* @__PURE__ */ e("div", { className: `flex ${r} rounded-full overflow-hidden bg-slate-800`, children: I.map((c) => {
    const o = ((s[c] || 0) / n * 100).toFixed(1);
    return /* @__PURE__ */ e("div", { className: N[c].bg, style: { width: `${o}%` } }, c);
  }) }) : /* @__PURE__ */ e("div", { className: `${r} rounded-full bg-slate-800` });
}
function Y({ selected: s, dateIso: n, disabled: r, onSet: c }) {
  return /* @__PURE__ */ e("div", { className: "flex flex-wrap gap-2", children: I.map((o) => {
    const l = N[o];
    return /* @__PURE__ */ e(
      "button",
      {
        disabled: r,
        onClick: () => c(n, o),
        className: `px-2.5 py-1.5 rounded-lg text-[11px] font-bold border transition ${s === o ? `${l.border} ${l.color} bg-white/5` : l.idle} ${r ? "opacity-60 cursor-not-allowed" : ""}`,
        children: l.short
      },
      o
    );
  }) });
}
function ne({ month: s, days: n, selectedDate: r, onSelect: c }) {
  const o = F(() => {
    const l = z(s), d = E(l, -l.getDay());
    return Array.from({ length: 42 }, (u, y) => {
      const h = E(d, y), x = O(h), m = n.get(x), p = h.getMonth() === s.getMonth(), w = x === O(/* @__PURE__ */ new Date());
      return { date: h, iso: x, entry: m, inMonth: p, isToday: w };
    });
  }, [s, n]);
  return /* @__PURE__ */ t("div", { className: "grid grid-cols-7 gap-1", children: [
    ["Sun", "Mon", "Tue", "Wed", "Thu", "Fri", "Sat"].map((l) => /* @__PURE__ */ e("div", { className: "text-center text-[10px] text-slate-500 font-bold py-1", children: l }, l)),
    o.map(({ iso: l, date: d, entry: u, inMonth: y, isToday: h }) => {
      const x = u?.total ?? 0, m = u?.counts ?? { LOOKING: 0, AVAILABLE: 0, MAYBE: 0, NOT_PLAYING: 0 };
      return /* @__PURE__ */ t(
        "button",
        {
          onClick: () => c(l),
          className: `rounded-xl border p-2 text-left transition min-h-[80px] ${y ? "bg-slate-950/40 border-white/10 hover:border-cyan-500/40" : "bg-slate-950/20 border-white/5"} ${r === l ? "ring-2 ring-cyan-500/50 border-cyan-500/50" : ""} ${h ? "shadow-[0_0_0_1px_rgba(16,185,129,0.45)]" : ""}`,
          children: [
            /* @__PURE__ */ t("div", { className: "flex items-center justify-between", children: [
              /* @__PURE__ */ e("span", { className: `text-xs font-semibold ${y ? "text-slate-100" : "text-slate-600"}`, children: d.getDate() }),
              x > 0 && /* @__PURE__ */ e("span", { className: "text-[10px] text-slate-400", children: x })
            ] }),
            /* @__PURE__ */ e("div", { className: "mt-2", children: /* @__PURE__ */ e(H, { counts: m, total: x }) })
          ]
        },
        l
      );
    })
  ] });
}
function re({ days: s, selectedDate: n, onSelect: r }) {
  const c = F(
    () => Array.from({ length: q }, (o, l) => {
      const d = E(/* @__PURE__ */ new Date(), l), u = O(d);
      return { iso: u, entry: s.get(u) };
    }),
    [s]
  );
  return /* @__PURE__ */ e("div", { className: "space-y-2", children: c.map(({ iso: o, entry: l }) => {
    const d = l?.counts ?? { LOOKING: 0, AVAILABLE: 0, MAYBE: 0, NOT_PLAYING: 0 }, u = l?.total ?? 0;
    return /* @__PURE__ */ t(
      "button",
      {
        onClick: () => r(o),
        className: `w-full rounded-xl border p-3 text-left transition ${n === o ? "border-cyan-500/50 bg-cyan-500/10" : "border-white/10 bg-slate-950/30 hover:border-cyan-500/35"}`,
        children: [
          /* @__PURE__ */ t("div", { className: "flex items-center justify-between mb-1", children: [
            /* @__PURE__ */ t("div", { children: [
              /* @__PURE__ */ e("div", { className: "text-xs font-bold text-white", children: G(o, { weekday: "short" }) }),
              /* @__PURE__ */ e("div", { className: "text-[11px] text-slate-500", children: G(o, { month: "short", day: "numeric" }) })
            ] }),
            /* @__PURE__ */ t("div", { className: "text-[11px] text-slate-300", children: [
              u,
              " total"
            ] })
          ] }),
          /* @__PURE__ */ t("div", { className: "mt-1 grid grid-cols-2 gap-x-3 gap-y-0.5 text-[11px]", children: [
            /* @__PURE__ */ t("span", { className: "text-cyan-400", children: [
              "Looking: ",
              d.LOOKING
            ] }),
            /* @__PURE__ */ t("span", { className: "text-emerald-400", children: [
              "Available: ",
              d.AVAILABLE
            ] }),
            /* @__PURE__ */ t("span", { className: "text-amber-400", children: [
              "Maybe: ",
              d.MAYBE
            ] }),
            /* @__PURE__ */ t("span", { className: "text-rose-400", children: [
              "Not playing: ",
              d.NOT_PLAYING
            ] })
          ] }),
          /* @__PURE__ */ e("div", { className: "mt-2", children: /* @__PURE__ */ e(H, { counts: d, total: u }) })
        ]
      },
      o
    );
  }) });
}
function le({ dateIso: s, entry: n, canSubmit: r, saving: c, onSetStatus: o }) {
  const l = n?.counts ?? { LOOKING: 0, AVAILABLE: 0, MAYBE: 0, NOT_PLAYING: 0 }, d = n?.total ?? 0, u = n?.my_status ?? null, y = n?.users_by_status, h = se(s), x = r && !h && !c;
  return /* @__PURE__ */ t(U, { children: [
    /* @__PURE__ */ e("div", { className: "text-lg font-bold text-white", children: G(s, { weekday: "long", month: "long", day: "numeric" }) }),
    /* @__PURE__ */ t("div", { className: "text-[11px] text-slate-500 mt-1", children: [
      s,
      " · ",
      d,
      " response",
      d !== 1 ? "s" : ""
    ] }),
    /* @__PURE__ */ e("div", { className: "grid grid-cols-4 gap-2 mt-4", children: I.map((m) => /* @__PURE__ */ t("div", { className: "rounded-lg border border-white/10 bg-slate-950/40 p-3 text-center", children: [
      /* @__PURE__ */ e("div", { className: "text-[10px] text-slate-500", children: N[m].short }),
      /* @__PURE__ */ e("div", { className: `text-2xl font-black ${N[m].color}`, children: l[m] })
    ] }, m)) }),
    x && /* @__PURE__ */ t("div", { className: "mt-4", children: [
      /* @__PURE__ */ e("div", { className: "text-[11px] text-slate-500 mb-2", children: "Set your status" }),
      /* @__PURE__ */ e(Y, { selected: u, dateIso: s, disabled: c, onSet: o })
    ] }),
    h && /* @__PURE__ */ e("div", { className: "mt-4 text-[11px] text-slate-500", children: "Past days are read-only." }),
    !r && !h && /* @__PURE__ */ e("div", { className: "mt-4 text-[11px] text-amber-400", children: "Log in and link Discord to set availability." }),
    y && /* @__PURE__ */ e("div", { className: "mt-4 space-y-1 text-xs text-slate-400", children: I.map((m) => {
      const p = y[m];
      return p?.length ? /* @__PURE__ */ t("div", { children: [
        /* @__PURE__ */ t("span", { className: N[m].color, children: [
          N[m].emoji,
          " ",
          N[m].short,
          ":"
        ] }),
        " ",
        p.slice(0, 8).map((w) => w.display_name).join(", ")
      ] }, m) : null;
    }) })
  ] });
}
function ie({ canSubmit: s, canPromote: n }) {
  const { data: r, refetch: c } = ae(s), [o, l] = f(!1), [d, u] = f(!1), [y, h] = f(""), [x, m] = f(""), [p, w] = f(/* @__PURE__ */ new Map()), b = r?.session, _ = r?.participants ?? [], A = r?.unlocked ?? !1, S = R(async (a, g) => {
    u(!0), h("");
    try {
      await a(), h(g), c();
    } catch (i) {
      h(i instanceof Error ? i.message : "Action failed");
    } finally {
      u(!1);
    }
  }, [c]);
  if (!s) return null;
  if (!b && !A)
    return /* @__PURE__ */ e(B, { children: /* @__PURE__ */ t("div", { className: "text-xs text-slate-500", children: [
      "Planning room locked. Waiting for Looking threshold: ",
      r?.session_ready?.looking_count ?? 0,
      "/",
      r?.session_ready?.threshold ?? 6
    ] }) });
  const C = s && b && (n || r?.viewer?.website_user_id === b.created_by_user_id);
  function $(a) {
    w((g) => {
      const i = new Map(g), v = i.get(a) ?? "";
      return v === "A" ? i.set(a, "B") : v === "B" ? i.delete(a) : i.set(a, "A"), i;
    });
  }
  function L() {
    const a = _.map((i) => i.user_id).filter(Boolean);
    for (let i = a.length - 1; i > 0; i--) {
      const v = Math.floor(Math.random() * (i + 1));
      [a[i], a[v]] = [a[v], a[i]];
    }
    const g = /* @__PURE__ */ new Map();
    a.forEach((i, v) => g.set(i, v % 2 === 0 ? "A" : "B")), w(g), h("Auto draft generated. Save to persist.");
  }
  return /* @__PURE__ */ t(U, { children: [
    /* @__PURE__ */ t("div", { className: "flex items-center justify-between", children: [
      /* @__PURE__ */ e("div", { className: "text-xs font-bold uppercase tracking-widest text-purple-400", children: "Planning Room" }),
      b ? /* @__PURE__ */ e("button", { onClick: () => l(!o), className: "text-xs text-slate-400 hover:text-white transition", children: o ? "Hide" : "Open" }) : /* @__PURE__ */ e(
        "button",
        {
          disabled: d,
          onClick: () => S(() => M.postPlanning("/today/create", {}), "Planning room created."),
          className: "px-3 py-1.5 rounded-lg text-xs font-bold border border-purple-500/50 text-purple-400 hover:bg-purple-500/10 transition disabled:opacity-60",
          children: "Create Room"
        }
      )
    ] }),
    b && /* @__PURE__ */ t("div", { className: "text-[11px] text-slate-400 mt-1", children: [
      "Session for ",
      b.date,
      " (",
      _.length,
      " participants)"
    ] }),
    y && /* @__PURE__ */ e("div", { className: "text-[11px] text-cyan-400 mt-2", children: y }),
    o && b && /* @__PURE__ */ t("div", { className: "mt-4 space-y-4", children: [
      /* @__PURE__ */ t("div", { className: "space-y-1", children: [
        /* @__PURE__ */ e("div", { className: "text-[11px] text-slate-500 font-bold", children: "Participants" }),
        _.map((a) => /* @__PURE__ */ t("div", { className: "flex items-center justify-between rounded-lg border border-white/10 bg-slate-950/35 px-2.5 py-1.5", children: [
          /* @__PURE__ */ e("span", { className: "text-xs text-slate-200", children: a.display_name }),
          /* @__PURE__ */ e("span", { className: `text-[11px] font-semibold ${a.status === "LOOKING" ? "text-cyan-400" : a.status === "AVAILABLE" ? "text-emerald-400" : "text-amber-400"}`, children: a.status })
        ] }, a.user_id))
      ] }),
      /* @__PURE__ */ t("div", { className: "space-y-1", children: [
        /* @__PURE__ */ e("div", { className: "text-[11px] text-slate-500 font-bold", children: "Suggestions" }),
        (b.suggestions ?? []).map((a) => /* @__PURE__ */ t("div", { className: "rounded-lg border border-white/10 bg-slate-950/30 px-2.5 py-2", children: [
          /* @__PURE__ */ t("div", { className: "flex items-center justify-between", children: [
            /* @__PURE__ */ t("div", { children: [
              /* @__PURE__ */ e("div", { className: "text-sm font-semibold text-slate-100", children: a.name }),
              /* @__PURE__ */ t("div", { className: "text-[11px] text-slate-500", children: [
                "by ",
                a.suggested_by_name
              ] })
            ] }),
            /* @__PURE__ */ t("div", { className: "text-xs text-slate-300 font-semibold", children: [
              a.votes,
              " vote",
              a.votes !== 1 ? "s" : ""
            ] })
          ] }),
          /* @__PURE__ */ e(
            "button",
            {
              disabled: d,
              onClick: () => S(() => M.postPlanning("/today/vote", { suggestion_id: a.id }), "Vote saved."),
              className: `mt-2 px-2.5 py-1 rounded-lg text-[11px] font-bold border transition ${a.voted_by_me ? "border-purple-500/50 text-purple-400 bg-purple-500/10" : "border-white/15 text-slate-300 hover:border-purple-500/40"}`,
              children: a.voted_by_me ? "Voted" : "Vote"
            }
          )
        ] }, a.id)),
        /* @__PURE__ */ t("div", { className: "flex gap-2 mt-2", children: [
          /* @__PURE__ */ e(
            "input",
            {
              value: x,
              onChange: (a) => m(a.target.value),
              placeholder: "Suggest a map...",
              className: "flex-1 rounded-lg border border-white/10 bg-slate-950/50 px-2.5 py-1.5 text-xs text-white placeholder-slate-500 outline-none focus:border-purple-500/50"
            }
          ),
          /* @__PURE__ */ e(
            "button",
            {
              disabled: d || x.length < 2,
              onClick: () => {
                S(() => M.postPlanning("/today/suggestions", { name: x }), "Suggestion added."), m("");
              },
              className: "px-3 py-1.5 rounded-lg text-xs font-bold border border-purple-500/50 text-purple-400 hover:bg-purple-500/10 transition disabled:opacity-60",
              children: "Add"
            }
          )
        ] })
      ] }),
      C && /* @__PURE__ */ t("div", { className: "space-y-2", children: [
        /* @__PURE__ */ e("div", { className: "text-[11px] text-slate-500 font-bold", children: "Team Draft" }),
        /* @__PURE__ */ e("div", { className: "flex flex-wrap gap-1.5", children: _.map((a) => {
          const g = p.get(a.user_id) ?? "";
          return /* @__PURE__ */ t(
            "button",
            {
              onClick: () => $(a.user_id),
              className: `px-2.5 py-1 rounded-full text-[11px] font-semibold border transition ${g === "A" ? "border-cyan-500/50 text-cyan-400 bg-cyan-500/10" : g === "B" ? "border-emerald-500/50 text-emerald-400 bg-emerald-500/10" : "border-white/15 text-slate-300 bg-slate-950/40"}`,
              children: [
                a.display_name,
                g ? ` · ${g}` : ""
              ]
            },
            a.user_id
          );
        }) }),
        /* @__PURE__ */ t("div", { className: "flex gap-2", children: [
          /* @__PURE__ */ e("button", { onClick: L, className: "px-3 py-1.5 rounded-lg text-xs font-bold border border-white/10 text-slate-300 hover:border-cyan-500/40 transition", children: "Auto Draft" }),
          /* @__PURE__ */ e(
            "button",
            {
              disabled: d,
              onClick: () => {
                const a = _.filter((i) => p.get(i.user_id) === "A").map((i) => i.user_id), g = _.filter((i) => p.get(i.user_id) === "B").map((i) => i.user_id);
                S(() => M.postPlanning("/today/teams", {
                  side_a: a,
                  side_b: g,
                  captain_a: a[0] ?? null,
                  captain_b: g[0] ?? null
                }), "Teams saved.");
              },
              className: "px-3 py-1.5 rounded-lg text-xs font-bold border border-emerald-500/50 text-emerald-400 hover:bg-emerald-500/10 transition disabled:opacity-60",
              children: "Save Teams"
            }
          )
        ] })
      ] })
    ] })
  ] });
}
function oe({ canSubmit: s }) {
  const { data: n, refetch: r } = te(s), [c, o] = f(!1), [l, d] = f(""), [u, y] = f(!0), [h, x] = f(!0), [m, p] = f(!1);
  if (n && !m && (y(n.discord_notify), x(n.get_ready_sound), p(!0)), !s || !n) return null;
  async function w() {
    o(!0), d("");
    try {
      await M.saveAvailabilitySettings({
        sound_enabled: h,
        sound_cooldown_seconds: n.sound_cooldown_seconds,
        availability_reminders_enabled: n.availability_reminders_enabled,
        timezone: n.timezone,
        discord_notify: u,
        telegram_notify: n.telegram_notify,
        signal_notify: n.signal_notify
      }), d("Settings saved."), r();
    } catch (b) {
      d(b instanceof Error ? b.message : "Save failed");
    } finally {
      o(!1);
    }
  }
  return /* @__PURE__ */ t(B, { children: [
    /* @__PURE__ */ e("div", { className: "text-xs font-bold uppercase tracking-widest text-slate-400 mb-3", children: "Preferences" }),
    /* @__PURE__ */ t("div", { className: "space-y-2", children: [
      /* @__PURE__ */ t("label", { className: "flex items-center gap-2 text-xs text-slate-300", children: [
        /* @__PURE__ */ e("input", { type: "checkbox", checked: u, onChange: (b) => y(b.target.checked), className: "rounded" }),
        "Discord notifications"
      ] }),
      /* @__PURE__ */ t("label", { className: "flex items-center gap-2 text-xs text-slate-300", children: [
        /* @__PURE__ */ e("input", { type: "checkbox", checked: h, onChange: (b) => x(b.target.checked), className: "rounded" }),
        "Get-ready sound"
      ] })
    ] }),
    /* @__PURE__ */ e(
      "button",
      {
        disabled: c,
        onClick: w,
        className: "mt-3 px-4 py-1.5 rounded-lg text-xs font-bold border border-cyan-500/50 text-cyan-400 hover:bg-cyan-500/10 transition disabled:opacity-60",
        children: "Save"
      }
    ),
    l && /* @__PURE__ */ e("div", { className: "mt-2 text-[11px] text-cyan-400", children: l })
  ] });
}
function ge() {
  const s = O(/* @__PURE__ */ new Date()), n = s, r = O(E(/* @__PURE__ */ new Date(), 60)), { data: c, isLoading: o } = X(), { data: l, isLoading: d, refetch: u } = Z(n, r, c?.can_submit ?? !1), { data: y } = ee(), h = W(), [x, m] = f(s), [p, w] = f(z(/* @__PURE__ */ new Date())), [b, _] = f(!1), [A, S] = f(!1), [C, $] = f(null), L = F(() => {
    const P = /* @__PURE__ */ new Map();
    for (const k of l?.days ?? []) P.set(k.date, k);
    return P;
  }, [l]), a = c?.can_submit ?? !1, g = l?.session_ready, i = R(async (P, k) => {
    if (!(!a || A)) {
      S(!0), $(null);
      try {
        await M.setAvailability(P, k), $({ text: `Saved ${N[k]?.label ?? k} for ${P}.`, error: !1 }), u(), h.invalidateQueries({ queryKey: ["planning-state"] });
      } catch (V) {
        $({ text: V instanceof Error ? V.message : "Save failed", error: !0 });
      } finally {
        S(!1);
      }
    }
  }, [a, A, u, h]);
  if (o || d) return /* @__PURE__ */ e(J, { variant: "card", count: 3 });
  if (!c?.authenticated || !y)
    return /* @__PURE__ */ t(T, { children: [
      /* @__PURE__ */ e(K, { title: "Availability", subtitle: "See when players are looking to play" }),
      /* @__PURE__ */ t("div", { className: "text-center py-16", children: [
        /* @__PURE__ */ e("div", { className: "text-4xl mb-4", children: "🔒" }),
        /* @__PURE__ */ e("p", { className: "text-slate-400 text-lg mb-4", children: "Log in with Discord to set your availability and view the queue." }),
        /* @__PURE__ */ e(
          "a",
          {
            href: "/auth/discord",
            className: "inline-block px-6 py-2 rounded-xl bg-indigo-600 text-white font-bold text-sm hover:bg-indigo-500 transition",
            children: "Login with Discord"
          }
        )
      ] })
    ] });
  const v = L.get(s), j = O(E(/* @__PURE__ */ new Date(), 1)), D = L.get(j);
  return /* @__PURE__ */ t(T, { children: [
    /* @__PURE__ */ e(K, { title: "Availability", subtitle: "Coordinate game sessions with the community" }),
    C && /* @__PURE__ */ e("div", { className: `mb-4 rounded-xl border px-4 py-2 text-sm ${C.error ? "border-rose-500/30 bg-rose-500/10 text-rose-400" : "border-emerald-500/30 bg-emerald-500/10 text-emerald-400"}`, children: C.text }),
    g?.ready && /* @__PURE__ */ t("div", { className: "mb-4 rounded-xl border border-emerald-500/30 bg-emerald-500/10 px-4 py-3", children: [
      /* @__PURE__ */ e("div", { className: "text-sm font-bold text-emerald-400", children: "Session Ready!" }),
      /* @__PURE__ */ t("div", { className: "text-xs text-slate-300 mt-1", children: [
        g.looking_count,
        "/",
        g.threshold,
        " players marked Looking for ",
        g.date
      ] })
    ] }),
    /* @__PURE__ */ t("div", { className: "grid grid-cols-1 md:grid-cols-2 gap-4 mb-6", children: [
      /* @__PURE__ */ t(B, { children: [
        /* @__PURE__ */ t("div", { className: "flex items-start justify-between mb-3", children: [
          /* @__PURE__ */ t("div", { children: [
            /* @__PURE__ */ e("div", { className: "text-sm font-bold text-white", children: "Today" }),
            /* @__PURE__ */ e("div", { className: "text-[11px] text-slate-500", children: G(s, { weekday: "short", month: "short", day: "numeric" }) })
          ] }),
          /* @__PURE__ */ e("div", { className: "text-[11px] text-slate-400", children: v?.my_status ? `${N[v.my_status]?.emoji ?? ""} ${N[v.my_status]?.label ?? v.my_status}` : "Not set" })
        ] }),
        a && /* @__PURE__ */ e(Y, { selected: v?.my_status, dateIso: s, disabled: A, onSet: i }),
        /* @__PURE__ */ t("div", { className: "text-[11px] text-slate-500 mt-3", children: [
          v?.total ?? 0,
          " responses"
        ] })
      ] }),
      /* @__PURE__ */ t(B, { children: [
        /* @__PURE__ */ t("div", { className: "flex items-start justify-between mb-3", children: [
          /* @__PURE__ */ t("div", { children: [
            /* @__PURE__ */ e("div", { className: "text-sm font-bold text-white", children: "Tomorrow" }),
            /* @__PURE__ */ e("div", { className: "text-[11px] text-slate-500", children: G(j, { weekday: "short", month: "short", day: "numeric" }) })
          ] }),
          /* @__PURE__ */ e("div", { className: "text-[11px] text-slate-400", children: D?.my_status ? `${N[D.my_status]?.emoji ?? ""} ${N[D.my_status]?.label ?? D.my_status}` : "Not set" })
        ] }),
        a && /* @__PURE__ */ e(Y, { selected: D?.my_status, dateIso: j, disabled: A, onSet: i }),
        /* @__PURE__ */ t("div", { className: "text-[11px] text-slate-500 mt-3", children: [
          D?.total ?? 0,
          " responses"
        ] })
      ] })
    ] }),
    /* @__PURE__ */ t("div", { className: "grid grid-cols-1 lg:grid-cols-3 gap-6", children: [
      /* @__PURE__ */ t("div", { children: [
        /* @__PURE__ */ t("div", { className: "text-xs font-bold uppercase tracking-widest text-slate-400 mb-3", children: [
          "Upcoming ",
          q,
          " Days"
        ] }),
        /* @__PURE__ */ e(re, { days: L, selectedDate: x, onSelect: m })
      ] }),
      /* @__PURE__ */ e("div", { children: /* @__PURE__ */ e(
        le,
        {
          dateIso: x,
          entry: L.get(x),
          canSubmit: a,
          saving: A,
          onSetStatus: i
        }
      ) }),
      /* @__PURE__ */ t("div", { className: "space-y-4", children: [
        /* @__PURE__ */ t(B, { children: [
          /* @__PURE__ */ e("div", { className: "flex items-center justify-between mb-3", children: /* @__PURE__ */ e("button", { onClick: () => _(!b), className: "text-xs font-bold uppercase tracking-widest text-slate-400 hover:text-white transition", children: b ? "Close Calendar" : "Open Calendar" }) }),
          b && /* @__PURE__ */ t(T, { children: [
            /* @__PURE__ */ t("div", { className: "flex items-center justify-between mb-3", children: [
              /* @__PURE__ */ e("button", { onClick: () => w(new Date(p.getFullYear(), p.getMonth() - 1, 1)), className: "text-slate-400 hover:text-white text-sm", children: "←" }),
              /* @__PURE__ */ e("span", { className: "text-sm font-semibold text-white", children: p.toLocaleDateString(void 0, { month: "long", year: "numeric" }) }),
              /* @__PURE__ */ e("button", { onClick: () => w(new Date(p.getFullYear(), p.getMonth() + 1, 1)), className: "text-slate-400 hover:text-white text-sm", children: "→" })
            ] }),
            /* @__PURE__ */ e(ne, { month: p, days: L, selectedDate: x, onSelect: m })
          ] })
        ] }),
        /* @__PURE__ */ e(oe, { canSubmit: a })
      ] })
    ] }),
    /* @__PURE__ */ e("div", { className: "mt-6", children: /* @__PURE__ */ e(ie, { canSubmit: a, canPromote: c?.can_promote ?? !1 }) }),
    c?.authenticated && !c?.linked_discord && /* @__PURE__ */ e("div", { className: "mt-6 rounded-xl border border-amber-500/30 bg-amber-500/10 px-4 py-3 text-sm text-amber-400", children: "Link your Discord account to set availability and participate in planning." })
  ] });
}
export {
  ge as default
};
