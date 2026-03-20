function e(t) {
  return typeof t == "number" && !Number.isInteger(t) ? t.toFixed(2) : String(Math.round(t));
}
function r(t) {
  return new Date(t).toLocaleDateString();
}
export {
  r as a,
  e as f
};
