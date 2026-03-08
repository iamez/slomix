import { u as n } from "./useQuery-C94yztTO.js";
const i = "/api";
async function s(e) {
  const t = await fetch(`${i}${e}`);
  if (!t.ok) throw new Error(`API ${t.status}: ${e}`);
  return t.json();
}
const o = {
  // Home / Overview
  getOverview: () => s("/stats/overview"),
  getLiveStatus: () => s("/live-status"),
  getTrends: (e = 14) => s(`/stats/trends?days=${e}`),
  getSeason: () => s("/seasons/current"),
  // Records
  getRecords: (e) => s(
    `/stats/records?limit=5${e ? `&map_name=${encodeURIComponent(e)}` : ""}`
  ),
  getMaps: () => s("/stats/maps").then((e) => e.map((t) => t.name)),
  // Leaderboard
  getLeaderboard: (e = "dpm", t = "30d", a = 50) => s(`/stats/leaderboard?stat=${e}&period=${t}&limit=${a}`),
  getQuickLeaders: () => s("/stats/quick-leaders"),
  // Maps
  getMapStats: () => s("/stats/maps"),
  // Hall of Fame
  getHallOfFame: (e = "all_time", t = 10) => s(`/hall-of-fame?period=${e}&limit=${t}`),
  // Awards
  getAwardsLeaderboard: (e) => {
    const t = new URLSearchParams();
    e?.days && t.set("days", e.days), e?.award_type && t.set("award_type", e.award_type), e?.limit && t.set("limit", String(e.limit));
    const a = t.toString();
    return s(`/awards/leaderboard${a ? `?${a}` : ""}`);
  },
  getAwards: (e) => {
    const t = new URLSearchParams();
    e?.days && t.set("days", e.days), e?.award_type && t.set("award_type", e.award_type), e?.limit && t.set("limit", String(e.limit)), e?.offset && t.set("offset", String(e.offset));
    const a = t.toString();
    return s(`/awards${a ? `?${a}` : ""}`);
  },
  getPlayerAwards: (e, t = 12) => s(`/players/${encodeURIComponent(e)}/awards?limit=${t}`),
  // Player Profile
  getPlayerProfile: (e) => s(`/stats/player/${encodeURIComponent(e)}`),
  getPlayerForm: (e) => s(`/stats/player/${encodeURIComponent(e)}/form`),
  getPlayerRounds: (e, t = 20) => s(`/stats/player/${encodeURIComponent(e)}/rounds?limit=${t}`),
  // Weapons
  getWeapons: (e = "all", t = 200) => s(`/stats/weapons?period=${e}&limit=${t}`),
  getWeaponHoF: (e = "all") => s(`/stats/weapons/hall-of-fame?period=${e}`),
  getWeaponsByPlayer: (e = "all", t = 24, a = 4) => s(
    `/stats/weapons/by-player?period=${e}&player_limit=${t}&weapon_limit=${a}`
  ),
  // Round Viz
  getRecentRounds: (e = 50) => s(`/rounds/recent?limit=${e}`),
  getRoundViz: (e) => s(`/rounds/${e}/viz`),
  // Session Detail
  getSessionDetail: (e) => s(`/stats/session/${e}/detail`),
  getSessionByDate: (e) => s(`/sessions/${encodeURIComponent(e)}`),
  // Sessions
  getSessions: (e) => {
    const t = new URLSearchParams();
    return e?.limit && t.set("limit", String(e.limit)), e?.offset && t.set("offset", String(e.offset)), e?.search && t.set("search", e.search), s(`/stats/sessions?${t.toString()}`);
  },
  // Uploads
  getUploads: (e) => {
    const t = new URLSearchParams();
    return e?.category && t.set("category", e.category), e?.tag && t.set("tag", e.tag), e?.search && t.set("search", e.search), e?.limit && t.set("limit", String(e.limit)), e?.offset && t.set("offset", String(e.offset)), s(`/uploads?${t.toString()}`);
  },
  getUpload: (e) => s(`/uploads/${encodeURIComponent(e)}`),
  getPopularTags: (e = 15) => s(`/uploads/tags/popular?limit=${e}`),
  // Greatshot (auth-required)
  getGreatshotDemos: () => s("/greatshot"),
  getGreatshotDetail: (e) => s(`/greatshot/${encodeURIComponent(e)}`),
  getGreatshotStatus: (e) => s(`/greatshot/${encodeURIComponent(e)}/status`),
  getGreatshotCrossref: (e) => s(`/greatshot/${encodeURIComponent(e)}/crossref`),
  queueGreatshotRender: async (e, t) => {
    const a = await fetch(`${i}/greatshot/${encodeURIComponent(e)}/highlights/render`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ highlight_id: t })
    });
    if (!a.ok) throw new Error(`API ${a.status}`);
    return a.json();
  },
  // Availability
  getAvailabilityAccess: () => s("/availability/access"),
  getAvailabilityRange: (e, t, a = !1) => {
    const r = new URLSearchParams();
    return e && r.set("from", e), t && r.set("to", t), a && r.set("include_users", "true"), s(`/availability?${r.toString()}`);
  },
  setAvailability: async (e, t) => {
    const a = await fetch(`${i}/availability`, {
      method: "POST",
      headers: { "Content-Type": "application/json", "X-Requested-With": "XMLHttpRequest" },
      credentials: "same-origin",
      body: JSON.stringify({ date: e, status: t })
    });
    if (!a.ok) {
      const r = await a.json().catch(() => null);
      throw new Error(r?.detail || `HTTP ${a.status}`);
    }
    return a.json();
  },
  getAvailabilitySettings: () => s("/availability/settings"),
  saveAvailabilitySettings: async (e) => {
    const t = await fetch(`${i}/availability/settings`, {
      method: "POST",
      headers: { "Content-Type": "application/json", "X-Requested-With": "XMLHttpRequest" },
      credentials: "same-origin",
      body: JSON.stringify(e)
    });
    if (!t.ok) {
      const a = await t.json().catch(() => null);
      throw new Error(a?.detail || `HTTP ${t.status}`);
    }
    return t.json();
  },
  getPlanningState: () => s("/availability/planning/today"),
  postPlanning: async (e, t = {}) => {
    const a = await fetch(`${i}/availability/planning${e}`, {
      method: "POST",
      headers: { "Content-Type": "application/json", "X-Requested-With": "XMLHttpRequest" },
      credentials: "same-origin",
      body: JSON.stringify(t)
    });
    if (!a.ok) {
      const r = await a.json().catch(() => null);
      throw new Error(r?.detail || `HTTP ${a.status}`);
    }
    return a.json();
  },
  getPromotionPreview: (e = !0, t = !1) => s(
    `/availability/promotions/preview?include_available=${e}&include_maybe=${t}`
  ),
  schedulePromotion: async (e) => {
    const t = await fetch(`${i}/availability/promotions/campaigns`, {
      method: "POST",
      headers: { "Content-Type": "application/json", "X-Requested-With": "XMLHttpRequest" },
      credentials: "same-origin",
      body: JSON.stringify(e)
    });
    if (!t.ok) {
      const a = await t.json().catch(() => null);
      throw new Error(a?.detail || `HTTP ${t.status}`);
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
}, y = () => n({
  queryKey: ["overview"],
  queryFn: o.getOverview,
  staleTime: 6e4
}), u = () => n({
  queryKey: ["live-status"],
  queryFn: o.getLiveStatus,
  staleTime: 3e4,
  refetchInterval: 6e4
}), c = (e = 14) => n({
  queryKey: ["trends", e],
  queryFn: () => o.getTrends(e),
  staleTime: 12e4
}), g = () => n({
  queryKey: ["season"],
  queryFn: o.getSeason,
  staleTime: 3e5
}), d = (e) => n({
  queryKey: ["records", e],
  queryFn: () => o.getRecords(e),
  staleTime: 6e4
}), f = () => n({
  queryKey: ["maps"],
  queryFn: o.getMaps,
  staleTime: 3e5
}), h = (e = "dpm", t = "30d", a = 50) => n({
  queryKey: ["leaderboard", e, t, a],
  queryFn: () => o.getLeaderboard(e, t, a),
  staleTime: 6e4
}), q = () => n({
  queryKey: ["map-stats"],
  queryFn: o.getMapStats,
  staleTime: 12e4
}), p = (e = "all_time", t = 10) => n({
  queryKey: ["hall-of-fame", e, t],
  queryFn: () => o.getHallOfFame(e, t),
  staleTime: 12e4
}), m = (e) => n({
  queryKey: ["awards-leaderboard", e],
  queryFn: () => o.getAwardsLeaderboard(e),
  staleTime: 6e4
}), w = (e) => n({
  queryKey: ["awards", e],
  queryFn: () => o.getAwards(e),
  staleTime: 6e4
}), T = (e) => n({
  queryKey: ["player-profile", e],
  queryFn: () => o.getPlayerProfile(e),
  enabled: !!e,
  staleTime: 6e4
}), b = (e, t = 20) => n({
  queryKey: ["player-rounds", e, t],
  queryFn: () => o.getPlayerRounds(e, t),
  enabled: !!e,
  staleTime: 6e4
}), S = (e = "all") => n({
  queryKey: ["weapons", e],
  queryFn: () => o.getWeapons(e),
  staleTime: 6e4
}), $ = (e = "all") => n({
  queryKey: ["weapon-hof", e],
  queryFn: () => o.getWeaponHoF(e),
  staleTime: 12e4
}), v = (e = "all") => n({
  queryKey: ["weapons-by-player", e],
  queryFn: () => o.getWeaponsByPlayer(e),
  staleTime: 6e4
}), R = (e = 50) => n({
  queryKey: ["recent-rounds", e],
  queryFn: () => o.getRecentRounds(e),
  staleTime: 6e4
}), P = (e) => n({
  queryKey: ["round-viz", e],
  queryFn: () => o.getRoundViz(e),
  enabled: e !== null && e > 0,
  staleTime: 3e5
}), F = (e) => n({
  queryKey: ["session-detail", e],
  queryFn: () => o.getSessionDetail(e),
  enabled: e !== null && e > 0,
  staleTime: 6e4
}), K = (e) => n({
  queryKey: ["session-by-date", e],
  queryFn: () => o.getSessionByDate(e),
  enabled: !!e,
  staleTime: 6e4
}), A = (e) => n({
  queryKey: ["sessions", e],
  queryFn: () => o.getSessions(e),
  staleTime: 3e4
}), U = (e = !0) => n({
  queryKey: ["greatshot-demos"],
  queryFn: o.getGreatshotDemos,
  enabled: e,
  staleTime: 3e4
}), C = (e) => n({
  queryKey: ["greatshot-detail", e],
  queryFn: () => o.getGreatshotDetail(e),
  enabled: !!e,
  staleTime: 3e4
}), L = (e, t = !0) => n({
  queryKey: ["greatshot-crossref", e],
  queryFn: () => o.getGreatshotCrossref(e),
  enabled: !!e && t,
  staleTime: 12e4
}), j = (e) => n({
  queryKey: ["uploads", e],
  queryFn: () => o.getUploads(e),
  staleTime: 3e4
}), O = (e) => n({
  queryKey: ["upload", e],
  queryFn: () => o.getUpload(e),
  enabled: !!e,
  staleTime: 6e4
}), _ = (e = 15) => n({
  queryKey: ["popular-tags", e],
  queryFn: () => o.getPopularTags(e),
  staleTime: 12e4
}), H = () => n({
  queryKey: ["auth-me"],
  queryFn: o.getAuthMe,
  staleTime: 3e5,
  retry: !1
}), D = () => n({
  queryKey: ["availability-access"],
  queryFn: o.getAvailabilityAccess,
  staleTime: 6e4
}), M = (e, t, a = !1) => n({
  queryKey: ["availability-range", e, t, a],
  queryFn: () => o.getAvailabilityRange(e, t, a),
  staleTime: 3e4,
  refetchInterval: 45e3
}), W = (e = !0) => n({
  queryKey: ["availability-settings"],
  queryFn: o.getAvailabilitySettings,
  enabled: e,
  staleTime: 12e4,
  retry: !1
}), G = (e = !0) => n({
  queryKey: ["planning-state"],
  queryFn: o.getPlanningState,
  enabled: e,
  staleTime: 3e4,
  refetchInterval: 45e3,
  retry: !1
});
export {
  o as A,
  C as B,
  L as C,
  D,
  M as E,
  W as F,
  G,
  u as a,
  g as b,
  c,
  d,
  f as e,
  h as f,
  q as g,
  p as h,
  m as i,
  w as j,
  A as k,
  T as l,
  b as m,
  S as n,
  $ as o,
  v as p,
  R as q,
  P as r,
  F as s,
  K as t,
  y as u,
  H as v,
  j as w,
  _ as x,
  O as y,
  U as z
};
