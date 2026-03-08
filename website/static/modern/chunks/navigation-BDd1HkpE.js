function o(n) {
  window.location.hash = n;
}
function a(n) {
  o(`#/profile?name=${encodeURIComponent(n)}`);
}
export {
  a,
  o as n
};
