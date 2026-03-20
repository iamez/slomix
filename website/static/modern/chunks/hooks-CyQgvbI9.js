import { u as r } from "./useQuery-CHhIv7cp.js";
const u = "/api", d = /* @__PURE__ */ new Map();
function f(e) {
  const t = new Headers(e);
  return t.delete("if-none-match"), t.delete("If-None-Match"), t.delete("if-modified-since"), t.delete("If-Modified-Since"), t;
}
async function a(e, t = {}) {
  const s = `${t.method ?? "GET"}:${e}`, o = `${u}${e}`, i = await fetch(o, t);
  if (i.status === 304) {
    const g = d.get(s);
    if (g !== void 0) return g;
    const c = await fetch(o, {
      ...t,
      cache: "no-store",
      headers: f(t.headers)
    });
    if (!c.ok) throw new Error(`API ${c.status}: ${e}`);
    const m = await c.json();
    return d.set(s, m), m;
  }
  if (!i.ok) throw new Error(`API ${i.status}: ${e}`);
  const y = await i.json();
  return d.set(s, y), y;
}
function l(e, t) {
  const s = new URLSearchParams();
  return e?.session_date && s.set("session_date", e.session_date), e?.map_name && s.set("map_name", e.map_name), e?.round_number != null && s.set("round_number", String(e.round_number)), e?.round_start_unix != null && s.set("round_start_unix", String(e.round_start_unix)), e?.range_days != null && s.set("range_days", String(e.range_days)), t && Object.entries(t).forEach(([o, i]) => {
    i != null && s.set(o, String(i));
  }), s.toString();
}
const n = {
  // Home / Overview
  getOverview: () => a("/stats/overview", { cache: "no-store" }),
  getLiveStatus: () => a("/live-status", { cache: "no-store" }),
  getTrends: (e = 14) => a(`/stats/trends?days=${e}`),
  getSeason: () => a("/seasons/current", { cache: "no-store" }),
  // Records
  getRecords: (e) => a(
    `/stats/records?limit=5${e ? `&map_name=${encodeURIComponent(e)}` : ""}`
  ),
  getMaps: () => a("/stats/maps").then((e) => e.map((t) => t.name)),
  // Leaderboard
  getLeaderboard: (e = "dpm", t = "30d", s = 50) => a(`/stats/leaderboard?stat=${e}&period=${t}&limit=${s}`),
  getQuickLeaders: () => a("/stats/quick-leaders"),
  // Maps
  getMapStats: () => a("/stats/maps"),
  // Hall of Fame
  getHallOfFame: (e = "all_time", t = 10) => a(`/hall-of-fame?period=${e}&limit=${t}`),
  // Awards
  getAwardsLeaderboard: (e) => {
    const t = new URLSearchParams();
    e?.days && t.set("days", e.days), e?.award_type && t.set("award_type", e.award_type), e?.limit && t.set("limit", String(e.limit));
    const s = t.toString();
    return a(`/awards/leaderboard${s ? `?${s}` : ""}`);
  },
  getAwards: (e) => {
    const t = new URLSearchParams();
    e?.days && t.set("days", e.days), e?.award_type && t.set("award_type", e.award_type), e?.limit && t.set("limit", String(e.limit)), e?.offset && t.set("offset", String(e.offset));
    const s = t.toString();
    return a(`/awards${s ? `?${s}` : ""}`);
  },
  getPlayerAwards: (e, t = 12) => a(`/players/${encodeURIComponent(e)}/awards?limit=${t}`),
  // Player Profile
  getPlayerProfile: (e) => a(`/stats/player/${encodeURIComponent(e)}`),
  getPlayerForm: (e) => a(`/stats/player/${encodeURIComponent(e)}/form`),
  getPlayerRounds: (e, t = 20) => a(`/stats/player/${encodeURIComponent(e)}/rounds?limit=${t}`),
  // Weapons
  getWeapons: (e = "all", t = 200) => a(`/stats/weapons?period=${e}&limit=${t}`),
  getWeaponHoF: (e = "all") => a(`/stats/weapons/hall-of-fame?period=${e}`),
  getWeaponsByPlayer: (e = "all", t = 24, s = 4, o, i) => a(
    `/stats/weapons/by-player?period=${e}&player_limit=${t}&weapon_limit=${s}${o ? `&player_guid=${encodeURIComponent(o)}` : ""}${i ? `&gaming_session_id=${i}` : ""}`
  ),
  // Round Viz
  getRecentRounds: (e = 50) => a(`/rounds/recent?limit=${e}`),
  getRoundViz: (e) => a(`/rounds/${e}/viz`),
  getRoundPlayerDetails: (e, t) => a(`/rounds/${e}/player/${encodeURIComponent(t)}/details`),
  // Session Detail
  getSessionDetail: (e) => a(`/stats/session/${e}/detail`),
  getSessionByDate: (e) => a(`/sessions/${encodeURIComponent(e)}`),
  getSessionGraphs: (e, t) => a(
    `/sessions/${encodeURIComponent(e)}/graphs${t ? `?gaming_session_id=${t}` : ""}`
  ),
  getProximityTradeSummary: (e) => a(`/proximity/trades/summary${l(e) ? `?${l(e)}` : ""}`),
  getProximityTradeEvents: (e, t = 250) => a(`/proximity/trades/events?${l(e, { limit: t })}`),
  getProximityDuos: (e, t = 8) => a(`/proximity/duos?${l(e, { limit: t })}`),
  getProximityTeamplay: (e) => a(`/proximity/teamplay${l(e) ? `?${l(e)}` : ""}`),
  getProximityMovers: (e, t = 5) => a(`/proximity/movers?${l(e, { limit: t })}`),
  // Proximity Player Profile
  getProximityPlayerProfile: (e, t = 90) => a(`/proximity/player/${encodeURIComponent(e)}/profile?range_days=${t}`),
  getProximityPlayerRadar: (e, t = 90) => a(`/proximity/player/${encodeURIComponent(e)}/radar?range_days=${t}`),
  // Proximity Round
  getProximityRoundTimeline: (e) => a(`/proximity/round/${e}/timeline`),
  getProximityRoundTracks: (e) => a(`/proximity/round/${e}/tracks`),
  getProximityRoundTeamComparison: (e) => a(`/proximity/round/${e}/team-comparison`),
  // Proximity Leaderboards
  getProximityLeaderboards: (e = "power", t = 30, s = 10) => a(
    `/proximity/leaderboards?category=${e}&range_days=${t}&limit=${s}`
  ),
  getProximitySessionScores: (e) => a(
    `/proximity/session-scores${e ? `?session_date=${e}` : ""}`
  ),
  // Weapon Accuracy
  getProximityWeaponAccuracy: (e) => {
    const t = new URLSearchParams();
    return e?.player_guid && t.set("player_guid", e.player_guid), e?.map_name && t.set("map_name", e.map_name), e?.limit && t.set("limit", String(e.limit)), a(`/proximity/weapon-accuracy?${t.toString()}`);
  },
  // VS Stats
  getPlayerVsStats: (e, t = "all", s, o, i = 5) => {
    const y = new URLSearchParams();
    return y.set("scope", t), s && y.set("session_id", String(s)), o && y.set("round_id", String(o)), y.set("limit", String(i)), a(`/player/${encodeURIComponent(e)}/vs-stats?${y.toString()}`);
  },
  // Sessions
  getSessions: (e) => {
    const t = new URLSearchParams();
    return e?.limit && t.set("limit", String(e.limit)), e?.offset && t.set("offset", String(e.offset)), e?.search && t.set("search", e.search), a(`/stats/sessions?${t.toString()}`);
  },
  // Uploads
  getUploads: (e) => {
    const t = new URLSearchParams();
    return e?.category && t.set("category", e.category), e?.tag && t.set("tag", e.tag), e?.search && t.set("search", e.search), e?.limit && t.set("limit", String(e.limit)), e?.offset && t.set("offset", String(e.offset)), a(`/uploads?${t.toString()}`);
  },
  getUpload: (e) => a(`/uploads/${encodeURIComponent(e)}`),
  getPopularTags: (e = 15) => a(`/uploads/tags/popular?limit=${e}`),
  // Greatshot (auth-required)
  getGreatshotDemos: () => a("/greatshot"),
  getGreatshotDetail: (e) => a(`/greatshot/${encodeURIComponent(e)}`),
  getGreatshotStatus: (e) => a(`/greatshot/${encodeURIComponent(e)}/status`),
  getGreatshotCrossref: (e) => a(`/greatshot/${encodeURIComponent(e)}/crossref`),
  queueGreatshotRender: async (e, t) => {
    const s = await fetch(`${u}/greatshot/${encodeURIComponent(e)}/highlights/render`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ highlight_id: t })
    });
    if (!s.ok) throw new Error(`API ${s.status}`);
    return s.json();
  },
  // Availability
  getAvailabilityAccess: () => a("/availability/access"),
  getAvailabilityRange: (e, t, s = !1) => {
    const o = new URLSearchParams();
    return e && o.set("from", e), t && o.set("to", t), s && o.set("include_users", "true"), a(`/availability?${o.toString()}`);
  },
  setAvailability: async (e, t) => {
    const s = await fetch(`${u}/availability`, {
      method: "POST",
      headers: { "Content-Type": "application/json", "X-Requested-With": "XMLHttpRequest" },
      credentials: "same-origin",
      body: JSON.stringify({ date: e, status: t })
    });
    if (!s.ok) {
      const o = await s.json().catch(() => null);
      throw new Error(o?.detail || `HTTP ${s.status}`);
    }
    return s.json();
  },
  getAvailabilitySettings: () => a("/availability/settings"),
  saveAvailabilitySettings: async (e) => {
    const t = await fetch(`${u}/availability/settings`, {
      method: "POST",
      headers: { "Content-Type": "application/json", "X-Requested-With": "XMLHttpRequest" },
      credentials: "same-origin",
      body: JSON.stringify(e)
    });
    if (!t.ok) {
      const s = await t.json().catch(() => null);
      throw new Error(s?.detail || `HTTP ${t.status}`);
    }
    return t.json();
  },
  getPlanningState: () => a("/availability/planning/today"),
  postPlanning: async (e, t = {}) => {
    const s = await fetch(`${u}/availability/planning${e}`, {
      method: "POST",
      headers: { "Content-Type": "application/json", "X-Requested-With": "XMLHttpRequest" },
      credentials: "same-origin",
      body: JSON.stringify(t)
    });
    if (!s.ok) {
      const o = await s.json().catch(() => null);
      throw new Error(o?.detail || `HTTP ${s.status}`);
    }
    return s.json();
  },
  getPromotionPreview: (e = !0, t = !1) => a(
    `/availability/promotions/preview?include_available=${e}&include_maybe=${t}`
  ),
  schedulePromotion: async (e) => {
    const t = await fetch(`${u}/availability/promotions/campaigns`, {
      method: "POST",
      headers: { "Content-Type": "application/json", "X-Requested-With": "XMLHttpRequest" },
      credentials: "same-origin",
      body: JSON.stringify(e)
    });
    if (!t.ok) {
      const s = await t.json().catch(() => null);
      throw new Error(s?.detail || `HTTP ${t.status}`);
    }
    return t.json();
  },
  // Auth
  getAuthMe: async () => {
    try {
      const e = await fetch("/auth/me");
      return e.ok ? e.json() : null;
    } catch {
      return null;
    }
  }
}, p = () => r({
  queryKey: ["overview"],
  queryFn: n.getOverview,
  staleTime: 6e4
}), h = () => r({
  queryKey: ["live-status"],
  queryFn: n.getLiveStatus,
  staleTime: 3e4,
  refetchInterval: 6e4
}), $ = (e = 14) => r({
  queryKey: ["trends", e],
  queryFn: () => n.getTrends(e),
  staleTime: 12e4
}), S = () => r({
  queryKey: ["season"],
  queryFn: n.getSeason,
  staleTime: 3e5
}), P = (e) => r({
  queryKey: ["records", e],
  queryFn: () => n.getRecords(e),
  staleTime: 6e4
}), T = () => r({
  queryKey: ["maps"],
  queryFn: n.getMaps,
  staleTime: 3e5
}), w = (e = "dpm", t = "30d", s = 50) => r({
  queryKey: ["leaderboard", e, t, s],
  queryFn: () => n.getLeaderboard(e, t, s),
  staleTime: 6e4
}), b = () => r({
  queryKey: ["quick-leaders"],
  queryFn: n.getQuickLeaders,
  staleTime: 6e4
}), v = () => r({
  queryKey: ["map-stats"],
  queryFn: n.getMapStats,
  staleTime: 12e4
}), R = (e = "all_time", t = 10) => r({
  queryKey: ["hall-of-fame", e, t],
  queryFn: () => n.getHallOfFame(e, t),
  staleTime: 12e4
}), F = (e) => r({
  queryKey: ["awards-leaderboard", e],
  queryFn: () => n.getAwardsLeaderboard(e),
  staleTime: 6e4
}), x = (e) => r({
  queryKey: ["awards", e],
  queryFn: () => n.getAwards(e),
  staleTime: 6e4
}), _ = (e) => r({
  queryKey: ["player-profile", e],
  queryFn: () => n.getPlayerProfile(e),
  enabled: !!e,
  staleTime: 6e4
}), K = (e) => r({
  queryKey: ["player-form", e],
  queryFn: () => n.getPlayerForm(e),
  enabled: !!e,
  staleTime: 12e4
}), A = (e, t = 20) => r({
  queryKey: ["player-rounds", e, t],
  queryFn: () => n.getPlayerRounds(e, t),
  enabled: !!e,
  staleTime: 6e4
}), U = (e = "all") => r({
  queryKey: ["weapons", e],
  queryFn: () => n.getWeapons(e),
  staleTime: 6e4
}), C = (e = "all") => r({
  queryKey: ["weapon-hof", e],
  queryFn: () => n.getWeaponHoF(e),
  staleTime: 12e4
}), L = (e = "all", t, s = t ? 1 : 24, o = t ? 8 : 4, i = !0, y) => r({
  queryKey: ["weapons-by-player", e, t, s, o, y],
  queryFn: () => n.getWeaponsByPlayer(e, s, o, t ?? void 0, y),
  staleTime: 6e4,
  enabled: i && (t === void 0 || !!t)
}), M = (e = 50) => r({
  queryKey: ["recent-rounds", e],
  queryFn: () => n.getRecentRounds(e),
  staleTime: 6e4
}), j = (e) => r({
  queryKey: ["round-viz", e],
  queryFn: () => n.getRoundViz(e),
  enabled: e !== null && e > 0,
  staleTime: 3e5
}), O = (e, t, s = !0) => r({
  queryKey: ["round-player-details", e, t],
  queryFn: () => n.getRoundPlayerDetails(e, t),
  enabled: s && e !== null && e > 0 && !!t,
  staleTime: 3e5
}), D = (e) => r({
  queryKey: ["session-detail", e],
  queryFn: () => n.getSessionDetail(e),
  enabled: e !== null && e > 0,
  staleTime: 6e4
}), H = (e) => r({
  queryKey: ["session-by-date", e],
  queryFn: () => n.getSessionByDate(e),
  enabled: !!e,
  staleTime: 6e4
}), k = (e, t, s = !0) => r({
  queryKey: ["session-graphs", e, t],
  queryFn: () => n.getSessionGraphs(e, t),
  enabled: s && !!e,
  staleTime: 6e4
}), E = (e, t = !0) => r({
  queryKey: ["proximity-trade-summary", e],
  queryFn: () => n.getProximityTradeSummary(e),
  enabled: t,
  staleTime: 3e4
}), W = (e, t = 250, s = !0) => r({
  queryKey: ["proximity-trade-events", e, t],
  queryFn: () => n.getProximityTradeEvents(e, t),
  enabled: s,
  staleTime: 3e4
}), I = (e, t = 8, s = !0) => r({
  queryKey: ["proximity-duos", e, t],
  queryFn: () => n.getProximityDuos(e, t),
  enabled: s,
  staleTime: 3e4
}), B = (e, t = !0) => r({
  queryKey: ["proximity-teamplay", e],
  queryFn: () => n.getProximityTeamplay(e),
  enabled: t,
  staleTime: 3e4
}), G = (e, t = 5, s = !0) => r({
  queryKey: ["proximity-movers", e, t],
  queryFn: () => n.getProximityMovers(e, t),
  enabled: s,
  staleTime: 3e4
}), X = (e = "power", t = 30, s = 10) => r({
  queryKey: ["proximity-leaderboards", e, t, s],
  queryFn: () => n.getProximityLeaderboards(e, t, s),
  staleTime: 6e4
}), z = (e) => r({
  queryKey: ["proximity-session-scores", e],
  queryFn: () => n.getProximitySessionScores(e),
  staleTime: 6e4
}), J = (e, t = "all", s, o, i = !0) => r({
  queryKey: ["player-vs-stats", e, t, s, o],
  queryFn: () => n.getPlayerVsStats(e, t, s, o),
  enabled: i && !!e,
  staleTime: 6e4
}), Q = (e) => r({
  queryKey: ["sessions", e],
  queryFn: () => n.getSessions(e),
  staleTime: 3e4
}), V = () => r({
  queryKey: ["latest-session"],
  queryFn: async () => (await n.getSessions({ limit: 1 }))[0] ?? null,
  staleTime: 3e4
}), N = (e = !0) => r({
  queryKey: ["greatshot-demos"],
  queryFn: n.getGreatshotDemos,
  enabled: e,
  staleTime: 3e4
}), Y = (e) => r({
  queryKey: ["greatshot-detail", e],
  queryFn: () => n.getGreatshotDetail(e),
  enabled: !!e,
  staleTime: 3e4
}), Z = (e, t = !0) => r({
  queryKey: ["greatshot-crossref", e],
  queryFn: () => n.getGreatshotCrossref(e),
  enabled: !!e && t,
  staleTime: 12e4
}), ee = (e) => r({
  queryKey: ["uploads", e],
  queryFn: () => n.getUploads(e),
  staleTime: 3e4
}), te = (e) => r({
  queryKey: ["upload", e],
  queryFn: () => n.getUpload(e),
  enabled: !!e,
  staleTime: 6e4
}), se = (e = 15) => r({
  queryKey: ["popular-tags", e],
  queryFn: () => n.getPopularTags(e),
  staleTime: 12e4
}), ae = () => r({
  queryKey: ["auth-me"],
  queryFn: n.getAuthMe,
  staleTime: 3e5,
  retry: !1
}), re = () => r({
  queryKey: ["availability-access"],
  queryFn: n.getAvailabilityAccess,
  staleTime: 6e4
}), ne = (e, t, s = !1) => r({
  queryKey: ["availability-range", e, t, s],
  queryFn: () => n.getAvailabilityRange(e, t, s),
  staleTime: 3e4,
  refetchInterval: 45e3
}), oe = (e = !0) => r({
  queryKey: ["availability-settings"],
  queryFn: n.getAvailabilitySettings,
  enabled: e,
  staleTime: 12e4,
  retry: !1
}), ie = (e = !0) => r({
  queryKey: ["planning-state"],
  queryFn: n.getPlanningState,
  enabled: e,
  staleTime: 3e4,
  refetchInterval: 45e3,
  retry: !1
});
export {
  J as A,
  E as B,
  W as C,
  I as D,
  B as E,
  G as F,
  ae as G,
  ee as H,
  se as I,
  te as J,
  N as K,
  n as L,
  Y as M,
  Z as N,
  re as O,
  ne as P,
  oe as Q,
  ie as R,
  z as S,
  X as T,
  S as a,
  p as b,
  h as c,
  $ as d,
  b as e,
  P as f,
  T as g,
  w as h,
  v as i,
  R as j,
  F as k,
  x as l,
  Q as m,
  _ as n,
  A as o,
  K as p,
  U as q,
  C as r,
  L as s,
  M as t,
  V as u,
  j as v,
  D as w,
  H as x,
  k as y,
  O as z
};
