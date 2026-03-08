import { jsx as e, jsxs as t } from "react/jsx-runtime";
import { l as N, m as w } from "./hooks-UFUMZFGB.js";
import { D as y } from "./DataTable-C9DYv6yb.js";
import { P as x } from "./PageHeader-D4CVo02x.js";
import { S as k, c as m } from "./route-host-CUL1oI6Z.js";
import { a as f, f as o } from "./format-BM7Gaq4w.js";
import { w as p, m as b } from "./game-assets-CWuRxGFH.js";
import { S as _ } from "./skull-BdPXKOvx.js";
import { S as P } from "./shield-DGUf4YlK.js";
import { C as D } from "./crosshair-BCiyTdpP.js";
import { Z as h, T as u } from "./zap-DJKgNY7d.js";
import { a as S, S as R } from "./swords-CDpW6o_n.js";
import { G as j } from "./gamepad-2-CX3iu8NC.js";
import { C } from "./crown-BFDJEIu0.js";
import { C as L } from "./clock-v5cg8EyG.js";
function n({ label: a, value: r, icon: s, color: c }) {
  return /* @__PURE__ */ t("div", { className: "glass-card rounded-xl p-4", children: [
    /* @__PURE__ */ t("div", { className: "flex items-center gap-2 mb-1", children: [
      /* @__PURE__ */ e(s, { className: m("w-4 h-4", c) }),
      /* @__PURE__ */ e("span", { className: "text-xs text-slate-500 uppercase font-bold", children: a })
    ] }),
    /* @__PURE__ */ e("div", { className: "text-2xl font-black text-white", children: r })
  ] });
}
function T({ achievement: a }) {
  return /* @__PURE__ */ t("div", { className: m(
    "flex items-center gap-3 p-3 rounded-lg border transition",
    a.unlocked ? "bg-amber-400/10 border-amber-400/20" : "bg-slate-800/50 border-white/5 opacity-50"
  ), children: [
    /* @__PURE__ */ e("span", { className: "text-2xl", children: a.icon }),
    /* @__PURE__ */ t("div", { className: "min-w-0", children: [
      /* @__PURE__ */ e("div", { className: m("font-bold text-sm", a.unlocked ? "text-white" : "text-slate-500"), children: a.name }),
      /* @__PURE__ */ e("div", { className: "text-xs text-slate-500", children: a.description })
    ] })
  ] });
}
const F = [
  {
    key: "round_date",
    label: "Date",
    className: "text-slate-400 text-xs",
    render: (a) => f(a.round_date)
  },
  {
    key: "map_name",
    label: "Map",
    render: (a) => /* @__PURE__ */ t("span", { className: "text-white font-medium inline-flex items-center gap-2", children: [
      /* @__PURE__ */ e("img", { src: b(a.map_name), alt: "", className: "w-5 h-5 rounded-sm object-cover bg-slate-700", onError: (r) => {
        r.currentTarget.style.display = "none";
      } }),
      a.map_name
    ] })
  },
  {
    key: "round_number",
    label: "R#",
    className: "text-slate-400 text-center w-12"
  },
  {
    key: "kills",
    label: "Kills",
    sortable: !0,
    sortValue: (a) => a.kills,
    className: "text-emerald-400 font-mono"
  },
  {
    key: "deaths",
    label: "Deaths",
    sortable: !0,
    sortValue: (a) => a.deaths,
    className: "text-rose-400 font-mono"
  },
  {
    key: "damage_given",
    label: "Damage",
    sortable: !0,
    sortValue: (a) => a.damage_given,
    className: "text-amber-400 font-mono",
    render: (a) => o(a.damage_given)
  },
  {
    key: "dpm",
    label: "DPM",
    sortable: !0,
    sortValue: (a) => a.dpm,
    className: "text-brand-cyan font-mono",
    render: (a) => a.dpm?.toFixed(1) ?? "-"
  },
  {
    key: "result",
    label: "Result",
    render: (a) => {
      const r = a.team === a.winner_team && a.winner_team !== 0, s = a.team !== a.winner_team && a.winner_team !== 0;
      return r ? /* @__PURE__ */ e("span", { className: "text-emerald-400 text-xs font-bold", children: "WIN" }) : s ? /* @__PURE__ */ e("span", { className: "text-rose-400 text-xs font-bold", children: "LOSS" }) : /* @__PURE__ */ e("span", { className: "text-slate-500 text-xs", children: "-" });
    }
  }
];
function M() {
  const a = window.location.hash.split("?")[1] ?? "";
  return new URLSearchParams(a).get("name") ?? "";
}
function z({ params: a }) {
  const r = a?.name || M(), { data: s, isLoading: c, isError: g } = N(r), { data: d } = w(r);
  if (!r)
    return /* @__PURE__ */ e("div", { className: "mt-6 text-center text-slate-400 py-12", children: "No player selected. Use search or click a player name." });
  if (c)
    return /* @__PURE__ */ t("div", { className: "mt-6", children: [
      /* @__PURE__ */ e(x, { title: r, subtitle: "Player profile" }),
      /* @__PURE__ */ e(k, { variant: "card", count: 6 })
    ] });
  if (g || !s)
    return /* @__PURE__ */ t("div", { className: "mt-6", children: [
      /* @__PURE__ */ e(x, { title: r, subtitle: "Player profile" }),
      /* @__PURE__ */ e("div", { className: "text-center text-red-400 py-12", children: "Player not found or failed to load." })
    ] });
  const l = s.stats, v = s.name.substring(0, 2).toUpperCase();
  return /* @__PURE__ */ t("div", { className: "mt-6", children: [
    /* @__PURE__ */ t("div", { className: "flex items-center gap-4 mb-8", children: [
      /* @__PURE__ */ e("div", { className: "w-16 h-16 rounded-xl bg-gradient-to-br from-blue-500 to-purple-500 flex items-center justify-center text-2xl font-black text-white", children: v }),
      /* @__PURE__ */ t("div", { children: [
        /* @__PURE__ */ e("h1", { className: "text-3xl font-black text-white tracking-tight", children: s.name }),
        /* @__PURE__ */ t("div", { className: "flex items-center gap-3 mt-1", children: [
          s.discord_linked && /* @__PURE__ */ e("span", { className: "px-2 py-0.5 rounded-full bg-indigo-500/20 text-indigo-400 text-xs font-bold", children: "Discord Linked" }),
          s.aliases.length > 0 && /* @__PURE__ */ t("span", { className: "text-xs text-slate-500", children: [
            "aka ",
            s.aliases.join(", ")
          ] }),
          /* @__PURE__ */ t("span", { className: "text-xs text-slate-500", children: [
            "Last seen: ",
            l.last_seen ? f(l.last_seen) : "Unknown"
          ] })
        ] })
      ] })
    ] }),
    /* @__PURE__ */ t("div", { className: "grid grid-cols-2 md:grid-cols-3 lg:grid-cols-4 xl:grid-cols-6 gap-4 mb-6", children: [
      /* @__PURE__ */ e(n, { label: "Kills", value: o(l.kills), icon: _, color: "text-rose-500" }),
      /* @__PURE__ */ e(n, { label: "Deaths", value: o(l.deaths), icon: P, color: "text-slate-400" }),
      /* @__PURE__ */ e(n, { label: "K/D Ratio", value: l.kd.toFixed(2), icon: D, color: "text-purple-500" }),
      /* @__PURE__ */ e(n, { label: "DPM", value: o(l.dpm), icon: h, color: "text-blue-500" }),
      /* @__PURE__ */ e(n, { label: "Damage", value: o(l.damage), icon: S, color: "text-amber-400" }),
      /* @__PURE__ */ e(n, { label: "Total XP", value: o(l.total_xp), icon: R, color: "text-amber-300" }),
      /* @__PURE__ */ e(n, { label: "Rounds", value: o(l.games), icon: j, color: "text-indigo-400" }),
      /* @__PURE__ */ e(n, { label: "Win Rate", value: `${l.win_rate}%`, icon: C, color: "text-emerald-400" }),
      /* @__PURE__ */ e(n, { label: "Playtime", value: `${l.playtime_hours}h`, icon: L, color: "text-cyan-500" }),
      l.favorite_weapon && /* @__PURE__ */ t("div", { className: "glass-card rounded-xl p-4", children: [
        /* @__PURE__ */ t("div", { className: "flex items-center gap-2 mb-1", children: [
          p(l.favorite_weapon) ? /* @__PURE__ */ e("img", { src: p(l.favorite_weapon), alt: "", className: "h-4 object-contain opacity-70", style: { filter: "brightness(1.6)" } }) : /* @__PURE__ */ e(u, { className: "w-4 h-4 text-orange-400" }),
          /* @__PURE__ */ e("span", { className: "text-xs text-slate-500 uppercase font-bold", children: "Fav Weapon" })
        ] }),
        /* @__PURE__ */ e("div", { className: "text-2xl font-black text-white", children: l.favorite_weapon })
      ] }),
      l.favorite_map && /* @__PURE__ */ t("div", { className: "glass-card rounded-xl p-4 relative overflow-hidden", children: [
        /* @__PURE__ */ e("img", { src: b(l.favorite_map), alt: "", className: "absolute inset-0 w-full h-full object-cover opacity-20", onError: (i) => {
          i.currentTarget.style.display = "none";
        } }),
        /* @__PURE__ */ t("div", { className: "relative", children: [
          /* @__PURE__ */ t("div", { className: "flex items-center gap-2 mb-1", children: [
            /* @__PURE__ */ e(u, { className: "w-4 h-4 text-green-400" }),
            /* @__PURE__ */ e("span", { className: "text-xs text-slate-500 uppercase font-bold", children: "Fav Map" })
          ] }),
          /* @__PURE__ */ e("div", { className: "text-2xl font-black text-white", children: l.favorite_map })
        ] })
      ] }),
      l.highest_dpm != null && /* @__PURE__ */ e(n, { label: "Peak DPM", value: o(l.highest_dpm), icon: h, color: "text-red-400" })
    ] }),
    /* @__PURE__ */ t("div", { className: "glass-panel rounded-xl p-5 mb-6", children: [
      /* @__PURE__ */ e("h3", { className: "text-sm font-bold text-slate-400 uppercase mb-3", children: "Win / Loss" }),
      /* @__PURE__ */ t("div", { className: "flex items-center gap-4", children: [
        /* @__PURE__ */ t("div", { className: "flex-1", children: [
          /* @__PURE__ */ t("div", { className: "flex items-center justify-between text-sm mb-1", children: [
            /* @__PURE__ */ t("span", { className: "text-emerald-400 font-bold", children: [
              l.wins,
              " W"
            ] }),
            /* @__PURE__ */ t("span", { className: "text-rose-400 font-bold", children: [
              l.losses,
              " L"
            ] })
          ] }),
          /* @__PURE__ */ t("div", { className: "h-3 rounded-full bg-slate-700 overflow-hidden flex", children: [
            /* @__PURE__ */ e("div", { className: "bg-emerald-500 h-full", style: { width: `${l.win_rate}%` } }),
            /* @__PURE__ */ e("div", { className: "bg-rose-500 h-full", style: { width: `${100 - l.win_rate}%` } })
          ] })
        ] }),
        /* @__PURE__ */ t("div", { className: "text-2xl font-black text-white", children: [
          l.win_rate,
          "%"
        ] })
      ] })
    ] }),
    s.achievements.length > 0 && /* @__PURE__ */ t("div", { className: "glass-panel rounded-xl p-5 mb-6", children: [
      /* @__PURE__ */ t("h3", { className: "text-sm font-bold text-slate-400 uppercase mb-3", children: [
        "Achievements (",
        s.achievements.filter((i) => i.unlocked).length,
        "/",
        s.achievements.length,
        ")"
      ] }),
      /* @__PURE__ */ e("div", { className: "grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-3", children: s.achievements.map((i) => /* @__PURE__ */ e(T, { achievement: i }, i.name)) })
    ] }),
    d && d.length > 0 && /* @__PURE__ */ t("div", { className: "glass-panel rounded-xl p-5", children: [
      /* @__PURE__ */ e("h3", { className: "text-sm font-bold text-slate-400 uppercase mb-3", children: "Recent Rounds" }),
      /* @__PURE__ */ e(
        y,
        {
          columns: F,
          data: d,
          keyFn: (i) => `${i.round_id}`,
          defaultSort: { key: "round_date", dir: "desc" }
        }
      )
    ] })
  ] });
}
export {
  z as default
};
