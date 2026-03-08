import { forwardRef as l, createElement as n } from "react";
const u = (...t) => t.filter((e, r, o) => !!e && e.trim() !== "" && o.indexOf(e) === r).join(" ").trim();
const w = (t) => t.replace(/([a-z0-9])([A-Z])/g, "$1-$2").toLowerCase();
const f = (t) => t.replace(
  /^([A-Z])|[\s-_]+(\w)/g,
  (e, r, o) => o ? o.toUpperCase() : r.toLowerCase()
);
const i = (t) => {
  const e = f(t);
  return e.charAt(0).toUpperCase() + e.slice(1);
};
var h = {
  xmlns: "http://www.w3.org/2000/svg",
  width: 24,
  height: 24,
  viewBox: "0 0 24 24",
  fill: "none",
  stroke: "currentColor",
  strokeWidth: 2,
  strokeLinecap: "round",
  strokeLinejoin: "round"
};
const g = (t) => {
  for (const e in t)
    if (e.startsWith("aria-") || e === "role" || e === "title")
      return !0;
  return !1;
};
const A = l(
  ({
    color: t = "currentColor",
    size: e = 24,
    strokeWidth: r = 2,
    absoluteStrokeWidth: o,
    className: s = "",
    children: a,
    iconNode: p,
    ...c
  }, m) => n(
    "svg",
    {
      ref: m,
      ...h,
      width: e,
      height: e,
      stroke: t,
      strokeWidth: o ? Number(r) * 24 / Number(e) : r,
      className: u("lucide", s),
      ...!a && !g(c) && { "aria-hidden": "true" },
      ...c
    },
    [
      ...p.map(([C, d]) => n(C, d)),
      ...Array.isArray(a) ? a : [a]
    ]
  )
);
const k = (t, e) => {
  const r = l(
    ({ className: o, ...s }, a) => n(A, {
      ref: a,
      iconNode: e,
      className: u(
        `lucide-${w(i(t))}`,
        `lucide-${t}`,
        o
      ),
      ...s
    })
  );
  return r.displayName = i(t), r;
};
export {
  k as c
};
