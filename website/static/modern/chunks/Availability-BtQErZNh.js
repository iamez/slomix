import { u as U, r as h, j as e, S as q } from "./route-host-Ba3v8uFM.js";
import { P as Y } from "./PageHeader-CQ7BTOQj.js";
import { G as V } from "./GlassPanel-C-uUmQaB.js";
import { G as P } from "./GlassCard-C53TzD-y.js";
import { O as z, P as H, G as W, L as D, Q as J, R as X } from "./hooks-CyQgvbI9.js";
const j = {
  LOOKING: { label: "Looking", short: "LFG", emoji: "🔍", color: "text-cyan-400", bg: "bg-cyan-500", border: "border-cyan-500/50", idle: "border-white/15 text-slate-300 hover:border-cyan-500/40" },
  AVAILABLE: { label: "Available", short: "IN", emoji: "✅", color: "text-emerald-400", bg: "bg-emerald-500", border: "border-emerald-500/50", idle: "border-white/15 text-slate-300 hover:border-emerald-500/40" },
  MAYBE: { label: "Maybe", short: "Maybe", emoji: "🤔", color: "text-amber-400", bg: "bg-amber-500", border: "border-amber-500/50", idle: "border-white/15 text-slate-300 hover:border-amber-500/40" },
  NOT_PLAYING: { label: "Not Playing", short: "Out", emoji: "❌", color: "text-rose-400", bg: "bg-rose-500", border: "border-rose-500/50", idle: "border-white/15 text-slate-300 hover:border-rose-500/40" }
}, E = ["LOOKING", "AVAILABLE", "MAYBE", "NOT_PLAYING"], F = 7;
function M(s) {
  return `${s.getFullYear()}-${String(s.getMonth() + 1).padStart(2, "0")}-${String(s.getDate()).padStart(2, "0")}`;
}
function K(s) {
  const a = s.match(/^(\d{4})-(\d{2})-(\d{2})$/);
  return a ? new Date(+a[1], +a[2] - 1, +a[3]) : null;
}
function $(s, a) {
  const n = new Date(s);
  return n.setDate(n.getDate() + a), n;
}
function R(s) {
  return new Date(s.getFullYear(), s.getMonth(), 1);
}
function Z(s) {
  const a = K(s);
  if (!a) return !0;
  const n = /* @__PURE__ */ new Date();
  return a < new Date(n.getFullYear(), n.getMonth(), n.getDate());
}
function B(s, a) {
  const n = K(s);
  return n ? n.toLocaleDateString(void 0, a) : s;
}
function Q({ counts: s, total: a, className: n = "h-1.5" }) {
  return a ? /* @__PURE__ */ e.jsx("div", { className: `flex ${n} rounded-full overflow-hidden bg-slate-800`, children: E.map((d) => {
    const o = ((s[d] || 0) / a * 100).toFixed(1);
    return /* @__PURE__ */ e.jsx("div", { className: j[d].bg, style: { width: `${o}%` } }, d);
  }) }) : /* @__PURE__ */ e.jsx("div", { className: `${n} rounded-full bg-slate-800` });
}
function I({ selected: s, dateIso: a, disabled: n, onSet: d }) {
  return /* @__PURE__ */ e.jsx("div", { className: "flex flex-wrap gap-2", children: E.map((o) => {
    const r = j[o], i = s === o;
    return /* @__PURE__ */ e.jsx(
      "button",
      {
        disabled: n,
        onClick: () => d(a, o),
        className: `px-2.5 py-1.5 rounded-lg text-[11px] font-bold border transition ${i ? `${r.border} ${r.color} bg-white/5` : r.idle} ${n ? "opacity-60 cursor-not-allowed" : ""}`,
        children: r.short
      },
      o
    );
  }) });
}
function ee({ month: s, days: a, selectedDate: n, onSelect: d }) {
  const o = h.useMemo(() => {
    const r = R(s), i = $(r, -r.getDay());
    return Array.from({ length: 42 }, (m, y) => {
      const u = $(i, y), x = M(u), c = a.get(x), b = u.getMonth() === s.getMonth(), v = x === M(/* @__PURE__ */ new Date());
      return { date: u, iso: x, entry: c, inMonth: b, isToday: v };
    });
  }, [s, a]);
  return /* @__PURE__ */ e.jsxs("div", { className: "grid grid-cols-7 gap-1", children: [
    ["Sun", "Mon", "Tue", "Wed", "Thu", "Fri", "Sat"].map((r) => /* @__PURE__ */ e.jsx("div", { className: "text-center text-[10px] text-slate-500 font-bold py-1", children: r }, r)),
    o.map(({ iso: r, date: i, entry: m, inMonth: y, isToday: u }) => {
      const x = m?.total ?? 0, c = m?.counts ?? { LOOKING: 0, AVAILABLE: 0, MAYBE: 0, NOT_PLAYING: 0 }, b = n === r;
      return /* @__PURE__ */ e.jsxs(
        "button",
        {
          onClick: () => d(r),
          className: `rounded-xl border p-2 text-left transition min-h-[80px] ${y ? "bg-slate-950/40 border-white/10 hover:border-cyan-500/40" : "bg-slate-950/20 border-white/5"} ${b ? "ring-2 ring-cyan-500/50 border-cyan-500/50" : ""} ${u ? "shadow-[0_0_0_1px_rgba(16,185,129,0.45)]" : ""}`,
          children: [
            /* @__PURE__ */ e.jsxs("div", { className: "flex items-center justify-between", children: [
              /* @__PURE__ */ e.jsx("span", { className: `text-xs font-semibold ${y ? "text-slate-100" : "text-slate-600"}`, children: i.getDate() }),
              x > 0 && /* @__PURE__ */ e.jsx("span", { className: "text-[10px] text-slate-400", children: x })
            ] }),
            /* @__PURE__ */ e.jsx("div", { className: "mt-2", children: /* @__PURE__ */ e.jsx(Q, { counts: c, total: x }) })
          ]
        },
        r
      );
    })
  ] });
}
function te({ days: s, selectedDate: a, onSelect: n }) {
  const d = h.useMemo(
    () => Array.from({ length: F }, (o, r) => {
      const i = $(/* @__PURE__ */ new Date(), r), m = M(i);
      return { iso: m, entry: s.get(m) };
    }),
    [s]
  );
  return /* @__PURE__ */ e.jsx("div", { className: "space-y-2", children: d.map(({ iso: o, entry: r }) => {
    const i = r?.counts ?? { LOOKING: 0, AVAILABLE: 0, MAYBE: 0, NOT_PLAYING: 0 }, m = r?.total ?? 0, y = a === o;
    return /* @__PURE__ */ e.jsxs(
      "button",
      {
        onClick: () => n(o),
        className: `w-full rounded-xl border p-3 text-left transition ${y ? "border-cyan-500/50 bg-cyan-500/10" : "border-white/10 bg-slate-950/30 hover:border-cyan-500/35"}`,
        children: [
          /* @__PURE__ */ e.jsxs("div", { className: "flex items-center justify-between mb-1", children: [
            /* @__PURE__ */ e.jsxs("div", { children: [
              /* @__PURE__ */ e.jsx("div", { className: "text-xs font-bold text-white", children: B(o, { weekday: "short" }) }),
              /* @__PURE__ */ e.jsx("div", { className: "text-[11px] text-slate-500", children: B(o, { month: "short", day: "numeric" }) })
            ] }),
            /* @__PURE__ */ e.jsxs("div", { className: "text-[11px] text-slate-300", children: [
              m,
              " total"
            ] })
          ] }),
          /* @__PURE__ */ e.jsxs("div", { className: "mt-1 grid grid-cols-2 gap-x-3 gap-y-0.5 text-[11px]", children: [
            /* @__PURE__ */ e.jsxs("span", { className: "text-cyan-400", children: [
              "Looking: ",
              i.LOOKING
            ] }),
            /* @__PURE__ */ e.jsxs("span", { className: "text-emerald-400", children: [
              "Available: ",
              i.AVAILABLE
            ] }),
            /* @__PURE__ */ e.jsxs("span", { className: "text-amber-400", children: [
              "Maybe: ",
              i.MAYBE
            ] }),
            /* @__PURE__ */ e.jsxs("span", { className: "text-rose-400", children: [
              "Not playing: ",
              i.NOT_PLAYING
            ] })
          ] }),
          /* @__PURE__ */ e.jsx("div", { className: "mt-2", children: /* @__PURE__ */ e.jsx(Q, { counts: i, total: m }) })
        ]
      },
      o
    );
  }) });
}
function se({ dateIso: s, entry: a, canSubmit: n, saving: d, onSetStatus: o }) {
  const r = a?.counts ?? { LOOKING: 0, AVAILABLE: 0, MAYBE: 0, NOT_PLAYING: 0 }, i = a?.total ?? 0, m = a?.my_status ?? null, y = a?.users_by_status, u = Z(s), x = n && !u && !d;
  return /* @__PURE__ */ e.jsxs(V, { children: [
    /* @__PURE__ */ e.jsx("div", { className: "text-lg font-bold text-white", children: B(s, { weekday: "long", month: "long", day: "numeric" }) }),
    /* @__PURE__ */ e.jsxs("div", { className: "text-[11px] text-slate-500 mt-1", children: [
      s,
      " · ",
      i,
      " response",
      i !== 1 ? "s" : ""
    ] }),
    /* @__PURE__ */ e.jsx("div", { className: "grid grid-cols-4 gap-2 mt-4", children: E.map((c) => /* @__PURE__ */ e.jsxs("div", { className: "rounded-lg border border-white/10 bg-slate-950/40 p-3 text-center", children: [
      /* @__PURE__ */ e.jsx("div", { className: "text-[10px] text-slate-500", children: j[c].short }),
      /* @__PURE__ */ e.jsx("div", { className: `text-2xl font-black ${j[c].color}`, children: r[c] })
    ] }, c)) }),
    x && /* @__PURE__ */ e.jsxs("div", { className: "mt-4", children: [
      /* @__PURE__ */ e.jsx("div", { className: "text-[11px] text-slate-500 mb-2", children: "Set your status" }),
      /* @__PURE__ */ e.jsx(I, { selected: m, dateIso: s, disabled: d, onSet: o })
    ] }),
    u && /* @__PURE__ */ e.jsx("div", { className: "mt-4 text-[11px] text-slate-500", children: "Past days are read-only." }),
    !n && !u && /* @__PURE__ */ e.jsx("div", { className: "mt-4 text-[11px] text-amber-400", children: "Log in and link Discord to set availability." }),
    y && /* @__PURE__ */ e.jsx("div", { className: "mt-4 space-y-1 text-xs text-slate-400", children: E.map((c) => {
      const b = y[c];
      return b?.length ? /* @__PURE__ */ e.jsxs("div", { children: [
        /* @__PURE__ */ e.jsxs("span", { className: j[c].color, children: [
          j[c].emoji,
          " ",
          j[c].short,
          ":"
        ] }),
        " ",
        b.slice(0, 8).map((v) => v.display_name).join(", ")
      ] }, c) : null;
    }) })
  ] });
}
function ae({ canSubmit: s, canPromote: a }) {
  const { data: n, refetch: d } = X(s), [o, r] = h.useState(!1), [i, m] = h.useState(!1), [y, u] = h.useState(""), [x, c] = h.useState(""), [b, v] = h.useState(/* @__PURE__ */ new Map()), g = n?.session, N = n?.participants ?? [], w = n?.unlocked ?? !1, _ = h.useCallback(async (t, p) => {
    m(!0), u("");
    try {
      await t(), u(p), d();
    } catch (l) {
      u(l instanceof Error ? l.message : "Action failed");
    } finally {
      m(!1);
    }
  }, [d]);
  if (!s) return null;
  if (!g && !w)
    return /* @__PURE__ */ e.jsx(P, { children: /* @__PURE__ */ e.jsxs("div", { className: "text-xs text-slate-500", children: [
      "Planning room locked. Waiting for Looking threshold: ",
      n?.session_ready?.looking_count ?? 0,
      "/",
      n?.session_ready?.threshold ?? 6
    ] }) });
  const k = s && g && (a || n?.viewer?.website_user_id === g.created_by_user_id);
  function O(t) {
    v((p) => {
      const l = new Map(p), f = l.get(t) ?? "";
      return f === "A" ? l.set(t, "B") : f === "B" ? l.delete(t) : l.set(t, "A"), l;
    });
  }
  function A() {
    const t = N.map((l) => l.user_id).filter(Boolean);
    for (let l = t.length - 1; l > 0; l--) {
      const f = Math.floor(Math.random() * (l + 1));
      [t[l], t[f]] = [t[f], t[l]];
    }
    const p = /* @__PURE__ */ new Map();
    t.forEach((l, f) => p.set(l, f % 2 === 0 ? "A" : "B")), v(p), u("Auto draft generated. Save to persist.");
  }
  return /* @__PURE__ */ e.jsxs(V, { children: [
    /* @__PURE__ */ e.jsxs("div", { className: "flex items-center justify-between", children: [
      /* @__PURE__ */ e.jsx("div", { className: "text-xs font-bold uppercase tracking-widest text-purple-400", children: "Planning Room" }),
      g ? /* @__PURE__ */ e.jsx("button", { onClick: () => r(!o), className: "text-xs text-slate-400 hover:text-white transition", children: o ? "Hide" : "Open" }) : /* @__PURE__ */ e.jsx(
        "button",
        {
          disabled: i,
          onClick: () => _(() => D.postPlanning("/today/create", {}), "Planning room created."),
          className: "px-3 py-1.5 rounded-lg text-xs font-bold border border-purple-500/50 text-purple-400 hover:bg-purple-500/10 transition disabled:opacity-60",
          children: "Create Room"
        }
      )
    ] }),
    g && /* @__PURE__ */ e.jsxs("div", { className: "text-[11px] text-slate-400 mt-1", children: [
      "Session for ",
      g.date,
      " (",
      N.length,
      " participants)"
    ] }),
    y && /* @__PURE__ */ e.jsx("div", { className: "text-[11px] text-cyan-400 mt-2", children: y }),
    o && g && /* @__PURE__ */ e.jsxs("div", { className: "mt-4 space-y-4", children: [
      /* @__PURE__ */ e.jsxs("div", { className: "space-y-1", children: [
        /* @__PURE__ */ e.jsx("div", { className: "text-[11px] text-slate-500 font-bold", children: "Participants" }),
        N.map((t) => /* @__PURE__ */ e.jsxs("div", { className: "flex items-center justify-between rounded-lg border border-white/10 bg-slate-950/35 px-2.5 py-1.5", children: [
          /* @__PURE__ */ e.jsx("span", { className: "text-xs text-slate-200", children: t.display_name }),
          /* @__PURE__ */ e.jsx("span", { className: `text-[11px] font-semibold ${t.status === "LOOKING" ? "text-cyan-400" : t.status === "AVAILABLE" ? "text-emerald-400" : "text-amber-400"}`, children: t.status })
        ] }, t.user_id))
      ] }),
      /* @__PURE__ */ e.jsxs("div", { className: "space-y-1", children: [
        /* @__PURE__ */ e.jsx("div", { className: "text-[11px] text-slate-500 font-bold", children: "Suggestions" }),
        (g.suggestions ?? []).map((t) => /* @__PURE__ */ e.jsxs("div", { className: "rounded-lg border border-white/10 bg-slate-950/30 px-2.5 py-2", children: [
          /* @__PURE__ */ e.jsxs("div", { className: "flex items-center justify-between", children: [
            /* @__PURE__ */ e.jsxs("div", { children: [
              /* @__PURE__ */ e.jsx("div", { className: "text-sm font-semibold text-slate-100", children: t.name }),
              /* @__PURE__ */ e.jsxs("div", { className: "text-[11px] text-slate-500", children: [
                "by ",
                t.suggested_by_name
              ] })
            ] }),
            /* @__PURE__ */ e.jsxs("div", { className: "text-xs text-slate-300 font-semibold", children: [
              t.votes,
              " vote",
              t.votes !== 1 ? "s" : ""
            ] })
          ] }),
          /* @__PURE__ */ e.jsx(
            "button",
            {
              disabled: i,
              onClick: () => _(() => D.postPlanning("/today/vote", { suggestion_id: t.id }), "Vote saved."),
              className: `mt-2 px-2.5 py-1 rounded-lg text-[11px] font-bold border transition ${t.voted_by_me ? "border-purple-500/50 text-purple-400 bg-purple-500/10" : "border-white/15 text-slate-300 hover:border-purple-500/40"}`,
              children: t.voted_by_me ? "Voted" : "Vote"
            }
          )
        ] }, t.id)),
        /* @__PURE__ */ e.jsxs("div", { className: "flex gap-2 mt-2", children: [
          /* @__PURE__ */ e.jsx(
            "input",
            {
              value: x,
              onChange: (t) => c(t.target.value),
              placeholder: "Suggest a map...",
              className: "flex-1 rounded-lg border border-white/10 bg-slate-950/50 px-2.5 py-1.5 text-xs text-white placeholder-slate-500 outline-none focus:border-purple-500/50"
            }
          ),
          /* @__PURE__ */ e.jsx(
            "button",
            {
              disabled: i || x.length < 2,
              onClick: () => {
                _(() => D.postPlanning("/today/suggestions", { name: x }), "Suggestion added."), c("");
              },
              className: "px-3 py-1.5 rounded-lg text-xs font-bold border border-purple-500/50 text-purple-400 hover:bg-purple-500/10 transition disabled:opacity-60",
              children: "Add"
            }
          )
        ] })
      ] }),
      k && /* @__PURE__ */ e.jsxs("div", { className: "space-y-2", children: [
        /* @__PURE__ */ e.jsx("div", { className: "text-[11px] text-slate-500 font-bold", children: "Team Draft" }),
        /* @__PURE__ */ e.jsx("div", { className: "flex flex-wrap gap-1.5", children: N.map((t) => {
          const p = b.get(t.user_id) ?? "";
          return /* @__PURE__ */ e.jsxs(
            "button",
            {
              onClick: () => O(t.user_id),
              className: `px-2.5 py-1 rounded-full text-[11px] font-semibold border transition ${p === "A" ? "border-cyan-500/50 text-cyan-400 bg-cyan-500/10" : p === "B" ? "border-emerald-500/50 text-emerald-400 bg-emerald-500/10" : "border-white/15 text-slate-300 bg-slate-950/40"}`,
              children: [
                t.display_name,
                p ? ` · ${p}` : ""
              ]
            },
            t.user_id
          );
        }) }),
        /* @__PURE__ */ e.jsxs("div", { className: "flex gap-2", children: [
          /* @__PURE__ */ e.jsx("button", { onClick: A, className: "px-3 py-1.5 rounded-lg text-xs font-bold border border-white/10 text-slate-300 hover:border-cyan-500/40 transition", children: "Auto Draft" }),
          /* @__PURE__ */ e.jsx(
            "button",
            {
              disabled: i,
              onClick: () => {
                const t = N.filter((l) => b.get(l.user_id) === "A").map((l) => l.user_id), p = N.filter((l) => b.get(l.user_id) === "B").map((l) => l.user_id);
                _(() => D.postPlanning("/today/teams", {
                  side_a: t,
                  side_b: p,
                  captain_a: t[0] ?? null,
                  captain_b: p[0] ?? null
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
function ne({ canSubmit: s }) {
  const { data: a, refetch: n } = J(s), [d, o] = h.useState(!1), [r, i] = h.useState(""), [m, y] = h.useState(!0), [u, x] = h.useState(!0), [c, b] = h.useState(!1);
  if (a && !c && (y(a.discord_notify), x(a.get_ready_sound), b(!0)), !s || !a) return null;
  async function v() {
    o(!0), i("");
    try {
      await D.saveAvailabilitySettings({
        sound_enabled: u,
        sound_cooldown_seconds: a.sound_cooldown_seconds,
        availability_reminders_enabled: a.availability_reminders_enabled,
        timezone: a.timezone,
        discord_notify: m,
        telegram_notify: a.telegram_notify,
        signal_notify: a.signal_notify
      }), i("Settings saved."), n();
    } catch (g) {
      i(g instanceof Error ? g.message : "Save failed");
    } finally {
      o(!1);
    }
  }
  return /* @__PURE__ */ e.jsxs(P, { children: [
    /* @__PURE__ */ e.jsx("div", { className: "text-xs font-bold uppercase tracking-widest text-slate-400 mb-3", children: "Preferences" }),
    /* @__PURE__ */ e.jsxs("div", { className: "space-y-2", children: [
      /* @__PURE__ */ e.jsxs("label", { className: "flex items-center gap-2 text-xs text-slate-300", children: [
        /* @__PURE__ */ e.jsx("input", { type: "checkbox", checked: m, onChange: (g) => y(g.target.checked), className: "rounded" }),
        "Discord notifications"
      ] }),
      /* @__PURE__ */ e.jsxs("label", { className: "flex items-center gap-2 text-xs text-slate-300", children: [
        /* @__PURE__ */ e.jsx("input", { type: "checkbox", checked: u, onChange: (g) => x(g.target.checked), className: "rounded" }),
        "Get-ready sound"
      ] })
    ] }),
    /* @__PURE__ */ e.jsx(
      "button",
      {
        disabled: d,
        onClick: v,
        className: "mt-3 px-4 py-1.5 rounded-lg text-xs font-bold border border-cyan-500/50 text-cyan-400 hover:bg-cyan-500/10 transition disabled:opacity-60",
        children: "Save"
      }
    ),
    r && /* @__PURE__ */ e.jsx("div", { className: "mt-2 text-[11px] text-cyan-400", children: r })
  ] });
}
function ce() {
  const s = M(/* @__PURE__ */ new Date()), a = s, n = M($(/* @__PURE__ */ new Date(), 60)), { data: d, isLoading: o } = z(), { data: r, isLoading: i, refetch: m } = H(a, n, d?.can_submit ?? !1), { data: y } = W(), u = U(), [x, c] = h.useState(s), [b, v] = h.useState(R(/* @__PURE__ */ new Date())), [g, N] = h.useState(!1), [w, _] = h.useState(!1), [k, O] = h.useState(null), A = h.useMemo(() => {
    const C = /* @__PURE__ */ new Map();
    for (const L of r?.days ?? []) C.set(L.date, L);
    return C;
  }, [r]), t = d?.can_submit ?? !1, p = r?.session_ready, l = h.useCallback(async (C, L) => {
    if (!(!t || w)) {
      _(!0), O(null);
      try {
        await D.setAvailability(C, L), O({ text: `Saved ${j[L]?.label ?? L} for ${C}.`, error: !1 }), m(), u.invalidateQueries({ queryKey: ["planning-state"] });
      } catch (T) {
        O({ text: T instanceof Error ? T.message : "Save failed", error: !0 });
      } finally {
        _(!1);
      }
    }
  }, [t, w, m, u]);
  if (o || i) return /* @__PURE__ */ e.jsx(q, { variant: "card", count: 3 });
  if (!d?.authenticated || !y)
    return /* @__PURE__ */ e.jsxs("div", { className: "page-shell", children: [
      /* @__PURE__ */ e.jsx(Y, { title: "Availability", subtitle: "Planning and coordination for community sessions.", eyebrow: "Advanced" }),
      /* @__PURE__ */ e.jsxs("div", { className: "text-center py-16", children: [
        /* @__PURE__ */ e.jsx("div", { className: "text-4xl mb-4", children: "🔒" }),
        /* @__PURE__ */ e.jsx("p", { className: "text-slate-400 text-lg mb-4", children: "Log in with Discord to set your availability and view the queue." }),
        /* @__PURE__ */ e.jsx(
          "a",
          {
            href: "/auth/discord",
            className: "inline-block px-6 py-2 rounded-xl bg-indigo-600 text-white font-bold text-sm hover:bg-indigo-500 transition",
            children: "Login with Discord"
          }
        )
      ] })
    ] });
  const f = A.get(s), G = M($(/* @__PURE__ */ new Date(), 1)), S = A.get(G);
  return /* @__PURE__ */ e.jsxs("div", { className: "page-shell", children: [
    /* @__PURE__ */ e.jsx(Y, { title: "Availability", subtitle: "Coordinate game sessions with the community.", eyebrow: "Advanced" }),
    k && /* @__PURE__ */ e.jsx("div", { className: `mb-4 rounded-xl border px-4 py-2 text-sm ${k.error ? "border-rose-500/30 bg-rose-500/10 text-rose-400" : "border-emerald-500/30 bg-emerald-500/10 text-emerald-400"}`, children: k.text }),
    p?.ready && /* @__PURE__ */ e.jsxs("div", { className: "mb-4 rounded-xl border border-emerald-500/30 bg-emerald-500/10 px-4 py-3", children: [
      /* @__PURE__ */ e.jsx("div", { className: "text-sm font-bold text-emerald-400", children: "Session Ready!" }),
      /* @__PURE__ */ e.jsxs("div", { className: "text-xs text-slate-300 mt-1", children: [
        p.looking_count,
        "/",
        p.threshold,
        " players marked Looking for ",
        p.date
      ] })
    ] }),
    /* @__PURE__ */ e.jsxs("div", { className: "grid grid-cols-1 md:grid-cols-2 gap-4 mb-6", children: [
      /* @__PURE__ */ e.jsxs(P, { children: [
        /* @__PURE__ */ e.jsxs("div", { className: "flex items-start justify-between mb-3", children: [
          /* @__PURE__ */ e.jsxs("div", { children: [
            /* @__PURE__ */ e.jsx("div", { className: "text-sm font-bold text-white", children: "Today" }),
            /* @__PURE__ */ e.jsx("div", { className: "text-[11px] text-slate-500", children: B(s, { weekday: "short", month: "short", day: "numeric" }) })
          ] }),
          /* @__PURE__ */ e.jsx("div", { className: "text-[11px] text-slate-400", children: f?.my_status ? `${j[f.my_status]?.emoji ?? ""} ${j[f.my_status]?.label ?? f.my_status}` : "Not set" })
        ] }),
        t && /* @__PURE__ */ e.jsx(I, { selected: f?.my_status, dateIso: s, disabled: w, onSet: l }),
        /* @__PURE__ */ e.jsxs("div", { className: "text-[11px] text-slate-500 mt-3", children: [
          f?.total ?? 0,
          " responses"
        ] })
      ] }),
      /* @__PURE__ */ e.jsxs(P, { children: [
        /* @__PURE__ */ e.jsxs("div", { className: "flex items-start justify-between mb-3", children: [
          /* @__PURE__ */ e.jsxs("div", { children: [
            /* @__PURE__ */ e.jsx("div", { className: "text-sm font-bold text-white", children: "Tomorrow" }),
            /* @__PURE__ */ e.jsx("div", { className: "text-[11px] text-slate-500", children: B(G, { weekday: "short", month: "short", day: "numeric" }) })
          ] }),
          /* @__PURE__ */ e.jsx("div", { className: "text-[11px] text-slate-400", children: S?.my_status ? `${j[S.my_status]?.emoji ?? ""} ${j[S.my_status]?.label ?? S.my_status}` : "Not set" })
        ] }),
        t && /* @__PURE__ */ e.jsx(I, { selected: S?.my_status, dateIso: G, disabled: w, onSet: l }),
        /* @__PURE__ */ e.jsxs("div", { className: "text-[11px] text-slate-500 mt-3", children: [
          S?.total ?? 0,
          " responses"
        ] })
      ] })
    ] }),
    /* @__PURE__ */ e.jsxs("div", { className: "grid grid-cols-1 lg:grid-cols-3 gap-6", children: [
      /* @__PURE__ */ e.jsxs("div", { children: [
        /* @__PURE__ */ e.jsxs("div", { className: "text-xs font-bold uppercase tracking-widest text-slate-400 mb-3", children: [
          "Upcoming ",
          F,
          " Days"
        ] }),
        /* @__PURE__ */ e.jsx(te, { days: A, selectedDate: x, onSelect: c })
      ] }),
      /* @__PURE__ */ e.jsx("div", { children: /* @__PURE__ */ e.jsx(
        se,
        {
          dateIso: x,
          entry: A.get(x),
          canSubmit: t,
          saving: w,
          onSetStatus: l
        }
      ) }),
      /* @__PURE__ */ e.jsxs("div", { className: "space-y-4", children: [
        /* @__PURE__ */ e.jsxs(P, { children: [
          /* @__PURE__ */ e.jsx("div", { className: "flex items-center justify-between mb-3", children: /* @__PURE__ */ e.jsx("button", { onClick: () => N(!g), className: "text-xs font-bold uppercase tracking-widest text-slate-400 hover:text-white transition", children: g ? "Close Calendar" : "Open Calendar" }) }),
          g && /* @__PURE__ */ e.jsxs(e.Fragment, { children: [
            /* @__PURE__ */ e.jsxs("div", { className: "flex items-center justify-between mb-3", children: [
              /* @__PURE__ */ e.jsx("button", { onClick: () => v(new Date(b.getFullYear(), b.getMonth() - 1, 1)), className: "text-slate-400 hover:text-white text-sm", children: "←" }),
              /* @__PURE__ */ e.jsx("span", { className: "text-sm font-semibold text-white", children: b.toLocaleDateString(void 0, { month: "long", year: "numeric" }) }),
              /* @__PURE__ */ e.jsx("button", { onClick: () => v(new Date(b.getFullYear(), b.getMonth() + 1, 1)), className: "text-slate-400 hover:text-white text-sm", children: "→" })
            ] }),
            /* @__PURE__ */ e.jsx(ee, { month: b, days: A, selectedDate: x, onSelect: c })
          ] })
        ] }),
        /* @__PURE__ */ e.jsx(ne, { canSubmit: t })
      ] })
    ] }),
    /* @__PURE__ */ e.jsx("div", { className: "mt-6", children: /* @__PURE__ */ e.jsx(ae, { canSubmit: t, canPromote: d?.can_promote ?? !1 }) }),
    d?.authenticated && !d?.linked_discord && /* @__PURE__ */ e.jsx("div", { className: "mt-6 rounded-xl border border-amber-500/30 bg-amber-500/10 px-4 py-3 text-sm text-amber-400", children: "Link your Discord account to set availability and participate in planning." })
  ] });
}
export {
  ce as default
};
