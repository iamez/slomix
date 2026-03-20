var xf = { exports: {} }, qn = {};
var Jd;
function sv() {
  if (Jd) return qn;
  Jd = 1;
  var i = /* @__PURE__ */ Symbol.for("react.transitional.element"), f = /* @__PURE__ */ Symbol.for("react.fragment");
  function r(o, p, O) {
    var C = null;
    if (O !== void 0 && (C = "" + O), p.key !== void 0 && (C = "" + p.key), "key" in p) {
      O = {};
      for (var D in p)
        D !== "key" && (O[D] = p[D]);
    } else O = p;
    return p = O.ref, {
      $$typeof: i,
      type: o,
      key: C,
      ref: p !== void 0 ? p : null,
      props: O
    };
  }
  return qn.Fragment = f, qn.jsx = r, qn.jsxs = r, qn;
}
var kd;
function ov() {
  return kd || (kd = 1, xf.exports = sv()), xf.exports;
}
var Tt = ov(), Cf = { exports: {} }, jn = {}, Uf = { exports: {} }, Rf = {};
var Fd;
function rv() {
  return Fd || (Fd = 1, (function(i) {
    function f(T, U) {
      var V = T.length;
      T.push(U);
      t: for (; 0 < V; ) {
        var rt = V - 1 >>> 1, R = T[rt];
        if (0 < p(R, U))
          T[rt] = U, T[V] = R, V = rt;
        else break t;
      }
    }
    function r(T) {
      return T.length === 0 ? null : T[0];
    }
    function o(T) {
      if (T.length === 0) return null;
      var U = T[0], V = T.pop();
      if (V !== U) {
        T[0] = V;
        t: for (var rt = 0, R = T.length, m = R >>> 1; rt < m; ) {
          var x = 2 * (rt + 1) - 1, N = T[x], q = x + 1, w = T[q];
          if (0 > p(N, V))
            q < R && 0 > p(w, N) ? (T[rt] = w, T[q] = V, rt = q) : (T[rt] = N, T[x] = V, rt = x);
          else if (q < R && 0 > p(w, V))
            T[rt] = w, T[q] = V, rt = q;
          else break t;
        }
      }
      return U;
    }
    function p(T, U) {
      var V = T.sortIndex - U.sortIndex;
      return V !== 0 ? V : T.id - U.id;
    }
    if (i.unstable_now = void 0, typeof performance == "object" && typeof performance.now == "function") {
      var O = performance;
      i.unstable_now = function() {
        return O.now();
      };
    } else {
      var C = Date, D = C.now();
      i.unstable_now = function() {
        return C.now() - D;
      };
    }
    var A = [], S = [], G = 1, H = null, J = 3, st = !1, $ = !1, k = !1, nt = !1, ot = typeof setTimeout == "function" ? setTimeout : null, Nt = typeof clearTimeout == "function" ? clearTimeout : null, gt = typeof setImmediate < "u" ? setImmediate : null;
    function _t(T) {
      for (var U = r(S); U !== null; ) {
        if (U.callback === null) o(S);
        else if (U.startTime <= T)
          o(S), U.sortIndex = U.expirationTime, f(A, U);
        else break;
        U = r(S);
      }
    }
    function Ct(T) {
      if (k = !1, _t(T), !$)
        if (r(A) !== null)
          $ = !0, Et || (Et = !0, Yt());
        else {
          var U = r(S);
          U !== null && Zt(Ct, U.startTime - T);
        }
    }
    var Et = !1, I = -1, j = 5, Dt = -1;
    function Ye() {
      return nt ? !0 : !(i.unstable_now() - Dt < j);
    }
    function fe() {
      if (nt = !1, Et) {
        var T = i.unstable_now();
        Dt = T;
        var U = !0;
        try {
          t: {
            $ = !1, k && (k = !1, Nt(I), I = -1), st = !0;
            var V = J;
            try {
              e: {
                for (_t(T), H = r(A); H !== null && !(H.expirationTime > T && Ye()); ) {
                  var rt = H.callback;
                  if (typeof rt == "function") {
                    H.callback = null, J = H.priorityLevel;
                    var R = rt(
                      H.expirationTime <= T
                    );
                    if (T = i.unstable_now(), typeof R == "function") {
                      H.callback = R, _t(T), U = !0;
                      break e;
                    }
                    H === r(A) && o(A), _t(T);
                  } else o(A);
                  H = r(A);
                }
                if (H !== null) U = !0;
                else {
                  var m = r(S);
                  m !== null && Zt(
                    Ct,
                    m.startTime - T
                  ), U = !1;
                }
              }
              break t;
            } finally {
              H = null, J = V, st = !1;
            }
            U = void 0;
          }
        } finally {
          U ? Yt() : Et = !1;
        }
      }
    }
    var Yt;
    if (typeof gt == "function")
      Yt = function() {
        gt(fe);
      };
    else if (typeof MessageChannel < "u") {
      var qe = new MessageChannel(), se = qe.port2;
      qe.port1.onmessage = fe, Yt = function() {
        se.postMessage(null);
      };
    } else
      Yt = function() {
        ot(fe, 0);
      };
    function Zt(T, U) {
      I = ot(function() {
        T(i.unstable_now());
      }, U);
    }
    i.unstable_IdlePriority = 5, i.unstable_ImmediatePriority = 1, i.unstable_LowPriority = 4, i.unstable_NormalPriority = 3, i.unstable_Profiling = null, i.unstable_UserBlockingPriority = 2, i.unstable_cancelCallback = function(T) {
      T.callback = null;
    }, i.unstable_forceFrameRate = function(T) {
      0 > T || 125 < T ? console.error(
        "forceFrameRate takes a positive int between 0 and 125, forcing frame rates higher than 125 fps is not supported"
      ) : j = 0 < T ? Math.floor(1e3 / T) : 5;
    }, i.unstable_getCurrentPriorityLevel = function() {
      return J;
    }, i.unstable_next = function(T) {
      switch (J) {
        case 1:
        case 2:
        case 3:
          var U = 3;
          break;
        default:
          U = J;
      }
      var V = J;
      J = U;
      try {
        return T();
      } finally {
        J = V;
      }
    }, i.unstable_requestPaint = function() {
      nt = !0;
    }, i.unstable_runWithPriority = function(T, U) {
      switch (T) {
        case 1:
        case 2:
        case 3:
        case 4:
        case 5:
          break;
        default:
          T = 3;
      }
      var V = J;
      J = T;
      try {
        return U();
      } finally {
        J = V;
      }
    }, i.unstable_scheduleCallback = function(T, U, V) {
      var rt = i.unstable_now();
      switch (typeof V == "object" && V !== null ? (V = V.delay, V = typeof V == "number" && 0 < V ? rt + V : rt) : V = rt, T) {
        case 1:
          var R = -1;
          break;
        case 2:
          R = 250;
          break;
        case 5:
          R = 1073741823;
          break;
        case 4:
          R = 1e4;
          break;
        default:
          R = 5e3;
      }
      return R = V + R, T = {
        id: G++,
        callback: U,
        priorityLevel: T,
        startTime: V,
        expirationTime: R,
        sortIndex: -1
      }, V > rt ? (T.sortIndex = V, f(S, T), r(A) === null && T === r(S) && (k ? (Nt(I), I = -1) : k = !0, Zt(Ct, V - rt))) : (T.sortIndex = R, f(A, T), $ || st || ($ = !0, Et || (Et = !0, Yt()))), T;
    }, i.unstable_shouldYield = Ye, i.unstable_wrapCallback = function(T) {
      var U = J;
      return function() {
        var V = J;
        J = U;
        try {
          return T.apply(this, arguments);
        } finally {
          J = V;
        }
      };
    };
  })(Rf)), Rf;
}
var Wd;
function dv() {
  return Wd || (Wd = 1, Uf.exports = rv()), Uf.exports;
}
var Nf = { exports: {} }, F = {};
var $d;
function hv() {
  if ($d) return F;
  $d = 1;
  var i = /* @__PURE__ */ Symbol.for("react.transitional.element"), f = /* @__PURE__ */ Symbol.for("react.portal"), r = /* @__PURE__ */ Symbol.for("react.fragment"), o = /* @__PURE__ */ Symbol.for("react.strict_mode"), p = /* @__PURE__ */ Symbol.for("react.profiler"), O = /* @__PURE__ */ Symbol.for("react.consumer"), C = /* @__PURE__ */ Symbol.for("react.context"), D = /* @__PURE__ */ Symbol.for("react.forward_ref"), A = /* @__PURE__ */ Symbol.for("react.suspense"), S = /* @__PURE__ */ Symbol.for("react.memo"), G = /* @__PURE__ */ Symbol.for("react.lazy"), H = /* @__PURE__ */ Symbol.for("react.activity"), J = Symbol.iterator;
  function st(m) {
    return m === null || typeof m != "object" ? null : (m = J && m[J] || m["@@iterator"], typeof m == "function" ? m : null);
  }
  var $ = {
    isMounted: function() {
      return !1;
    },
    enqueueForceUpdate: function() {
    },
    enqueueReplaceState: function() {
    },
    enqueueSetState: function() {
    }
  }, k = Object.assign, nt = {};
  function ot(m, x, N) {
    this.props = m, this.context = x, this.refs = nt, this.updater = N || $;
  }
  ot.prototype.isReactComponent = {}, ot.prototype.setState = function(m, x) {
    if (typeof m != "object" && typeof m != "function" && m != null)
      throw Error(
        "takes an object of state variables to update or a function which returns an object of state variables."
      );
    this.updater.enqueueSetState(this, m, x, "setState");
  }, ot.prototype.forceUpdate = function(m) {
    this.updater.enqueueForceUpdate(this, m, "forceUpdate");
  };
  function Nt() {
  }
  Nt.prototype = ot.prototype;
  function gt(m, x, N) {
    this.props = m, this.context = x, this.refs = nt, this.updater = N || $;
  }
  var _t = gt.prototype = new Nt();
  _t.constructor = gt, k(_t, ot.prototype), _t.isPureReactComponent = !0;
  var Ct = Array.isArray;
  function Et() {
  }
  var I = { H: null, A: null, T: null, S: null }, j = Object.prototype.hasOwnProperty;
  function Dt(m, x, N) {
    var q = N.ref;
    return {
      $$typeof: i,
      type: m,
      key: x,
      ref: q !== void 0 ? q : null,
      props: N
    };
  }
  function Ye(m, x) {
    return Dt(m.type, x, m.props);
  }
  function fe(m) {
    return typeof m == "object" && m !== null && m.$$typeof === i;
  }
  function Yt(m) {
    var x = { "=": "=0", ":": "=2" };
    return "$" + m.replace(/[=:]/g, function(N) {
      return x[N];
    });
  }
  var qe = /\/+/g;
  function se(m, x) {
    return typeof m == "object" && m !== null && m.key != null ? Yt("" + m.key) : x.toString(36);
  }
  function Zt(m) {
    switch (m.status) {
      case "fulfilled":
        return m.value;
      case "rejected":
        throw m.reason;
      default:
        switch (typeof m.status == "string" ? m.then(Et, Et) : (m.status = "pending", m.then(
          function(x) {
            m.status === "pending" && (m.status = "fulfilled", m.value = x);
          },
          function(x) {
            m.status === "pending" && (m.status = "rejected", m.reason = x);
          }
        )), m.status) {
          case "fulfilled":
            return m.value;
          case "rejected":
            throw m.reason;
        }
    }
    throw m;
  }
  function T(m, x, N, q, w) {
    var L = typeof m;
    (L === "undefined" || L === "boolean") && (m = null);
    var ct = !1;
    if (m === null) ct = !0;
    else
      switch (L) {
        case "bigint":
        case "string":
        case "number":
          ct = !0;
          break;
        case "object":
          switch (m.$$typeof) {
            case i:
            case f:
              ct = !0;
              break;
            case G:
              return ct = m._init, T(
                ct(m._payload),
                x,
                N,
                q,
                w
              );
          }
      }
    if (ct)
      return w = w(m), ct = q === "" ? "." + se(m, 0) : q, Ct(w) ? (N = "", ct != null && (N = ct.replace(qe, "$&/") + "/"), T(w, x, N, "", function(cl) {
        return cl;
      })) : w != null && (fe(w) && (w = Ye(
        w,
        N + (w.key == null || m && m.key === w.key ? "" : ("" + w.key).replace(
          qe,
          "$&/"
        ) + "/") + ct
      )), x.push(w)), 1;
    ct = 0;
    var Lt = q === "" ? "." : q + ":";
    if (Ct(m))
      for (var tt = 0; tt < m.length; tt++)
        q = m[tt], L = Lt + se(q, tt), ct += T(
          q,
          x,
          N,
          L,
          w
        );
    else if (tt = st(m), typeof tt == "function")
      for (m = tt.call(m), tt = 0; !(q = m.next()).done; )
        q = q.value, L = Lt + se(q, tt++), ct += T(
          q,
          x,
          N,
          L,
          w
        );
    else if (L === "object") {
      if (typeof m.then == "function")
        return T(
          Zt(m),
          x,
          N,
          q,
          w
        );
      throw x = String(m), Error(
        "Objects are not valid as a React child (found: " + (x === "[object Object]" ? "object with keys {" + Object.keys(m).join(", ") + "}" : x) + "). If you meant to render a collection of children, use an array instead."
      );
    }
    return ct;
  }
  function U(m, x, N) {
    if (m == null) return m;
    var q = [], w = 0;
    return T(m, q, "", "", function(L) {
      return x.call(N, L, w++);
    }), q;
  }
  function V(m) {
    if (m._status === -1) {
      var x = m._result;
      x = x(), x.then(
        function(N) {
          (m._status === 0 || m._status === -1) && (m._status = 1, m._result = N);
        },
        function(N) {
          (m._status === 0 || m._status === -1) && (m._status = 2, m._result = N);
        }
      ), m._status === -1 && (m._status = 0, m._result = x);
    }
    if (m._status === 1) return m._result.default;
    throw m._result;
  }
  var rt = typeof reportError == "function" ? reportError : function(m) {
    if (typeof window == "object" && typeof window.ErrorEvent == "function") {
      var x = new window.ErrorEvent("error", {
        bubbles: !0,
        cancelable: !0,
        message: typeof m == "object" && m !== null && typeof m.message == "string" ? String(m.message) : String(m),
        error: m
      });
      if (!window.dispatchEvent(x)) return;
    } else if (typeof process == "object" && typeof process.emit == "function") {
      process.emit("uncaughtException", m);
      return;
    }
    console.error(m);
  }, R = {
    map: U,
    forEach: function(m, x, N) {
      U(
        m,
        function() {
          x.apply(this, arguments);
        },
        N
      );
    },
    count: function(m) {
      var x = 0;
      return U(m, function() {
        x++;
      }), x;
    },
    toArray: function(m) {
      return U(m, function(x) {
        return x;
      }) || [];
    },
    only: function(m) {
      if (!fe(m))
        throw Error(
          "React.Children.only expected to receive a single React element child."
        );
      return m;
    }
  };
  return F.Activity = H, F.Children = R, F.Component = ot, F.Fragment = r, F.Profiler = p, F.PureComponent = gt, F.StrictMode = o, F.Suspense = A, F.__CLIENT_INTERNALS_DO_NOT_USE_OR_WARN_USERS_THEY_CANNOT_UPGRADE = I, F.__COMPILER_RUNTIME = {
    __proto__: null,
    c: function(m) {
      return I.H.useMemoCache(m);
    }
  }, F.cache = function(m) {
    return function() {
      return m.apply(null, arguments);
    };
  }, F.cacheSignal = function() {
    return null;
  }, F.cloneElement = function(m, x, N) {
    if (m == null)
      throw Error(
        "The argument must be a React element, but you passed " + m + "."
      );
    var q = k({}, m.props), w = m.key;
    if (x != null)
      for (L in x.key !== void 0 && (w = "" + x.key), x)
        !j.call(x, L) || L === "key" || L === "__self" || L === "__source" || L === "ref" && x.ref === void 0 || (q[L] = x[L]);
    var L = arguments.length - 2;
    if (L === 1) q.children = N;
    else if (1 < L) {
      for (var ct = Array(L), Lt = 0; Lt < L; Lt++)
        ct[Lt] = arguments[Lt + 2];
      q.children = ct;
    }
    return Dt(m.type, w, q);
  }, F.createContext = function(m) {
    return m = {
      $$typeof: C,
      _currentValue: m,
      _currentValue2: m,
      _threadCount: 0,
      Provider: null,
      Consumer: null
    }, m.Provider = m, m.Consumer = {
      $$typeof: O,
      _context: m
    }, m;
  }, F.createElement = function(m, x, N) {
    var q, w = {}, L = null;
    if (x != null)
      for (q in x.key !== void 0 && (L = "" + x.key), x)
        j.call(x, q) && q !== "key" && q !== "__self" && q !== "__source" && (w[q] = x[q]);
    var ct = arguments.length - 2;
    if (ct === 1) w.children = N;
    else if (1 < ct) {
      for (var Lt = Array(ct), tt = 0; tt < ct; tt++)
        Lt[tt] = arguments[tt + 2];
      w.children = Lt;
    }
    if (m && m.defaultProps)
      for (q in ct = m.defaultProps, ct)
        w[q] === void 0 && (w[q] = ct[q]);
    return Dt(m, L, w);
  }, F.createRef = function() {
    return { current: null };
  }, F.forwardRef = function(m) {
    return { $$typeof: D, render: m };
  }, F.isValidElement = fe, F.lazy = function(m) {
    return {
      $$typeof: G,
      _payload: { _status: -1, _result: m },
      _init: V
    };
  }, F.memo = function(m, x) {
    return {
      $$typeof: S,
      type: m,
      compare: x === void 0 ? null : x
    };
  }, F.startTransition = function(m) {
    var x = I.T, N = {};
    I.T = N;
    try {
      var q = m(), w = I.S;
      w !== null && w(N, q), typeof q == "object" && q !== null && typeof q.then == "function" && q.then(Et, rt);
    } catch (L) {
      rt(L);
    } finally {
      x !== null && N.types !== null && (x.types = N.types), I.T = x;
    }
  }, F.unstable_useCacheRefresh = function() {
    return I.H.useCacheRefresh();
  }, F.use = function(m) {
    return I.H.use(m);
  }, F.useActionState = function(m, x, N) {
    return I.H.useActionState(m, x, N);
  }, F.useCallback = function(m, x) {
    return I.H.useCallback(m, x);
  }, F.useContext = function(m) {
    return I.H.useContext(m);
  }, F.useDebugValue = function() {
  }, F.useDeferredValue = function(m, x) {
    return I.H.useDeferredValue(m, x);
  }, F.useEffect = function(m, x) {
    return I.H.useEffect(m, x);
  }, F.useEffectEvent = function(m) {
    return I.H.useEffectEvent(m);
  }, F.useId = function() {
    return I.H.useId();
  }, F.useImperativeHandle = function(m, x, N) {
    return I.H.useImperativeHandle(m, x, N);
  }, F.useInsertionEffect = function(m, x) {
    return I.H.useInsertionEffect(m, x);
  }, F.useLayoutEffect = function(m, x) {
    return I.H.useLayoutEffect(m, x);
  }, F.useMemo = function(m, x) {
    return I.H.useMemo(m, x);
  }, F.useOptimistic = function(m, x) {
    return I.H.useOptimistic(m, x);
  }, F.useReducer = function(m, x, N) {
    return I.H.useReducer(m, x, N);
  }, F.useRef = function(m) {
    return I.H.useRef(m);
  }, F.useState = function(m) {
    return I.H.useState(m);
  }, F.useSyncExternalStore = function(m, x, N) {
    return I.H.useSyncExternalStore(
      m,
      x,
      N
    );
  }, F.useTransition = function() {
    return I.H.useTransition();
  }, F.version = "19.2.4", F;
}
var Id;
function Xf() {
  return Id || (Id = 1, Nf.exports = hv()), Nf.exports;
}
var Hf = { exports: {} }, It = {};
var Pd;
function mv() {
  if (Pd) return It;
  Pd = 1;
  var i = Xf();
  function f(A) {
    var S = "https://react.dev/errors/" + A;
    if (1 < arguments.length) {
      S += "?args[]=" + encodeURIComponent(arguments[1]);
      for (var G = 2; G < arguments.length; G++)
        S += "&args[]=" + encodeURIComponent(arguments[G]);
    }
    return "Minified React error #" + A + "; visit " + S + " for the full message or use the non-minified dev environment for full errors and additional helpful warnings.";
  }
  function r() {
  }
  var o = {
    d: {
      f: r,
      r: function() {
        throw Error(f(522));
      },
      D: r,
      C: r,
      L: r,
      m: r,
      X: r,
      S: r,
      M: r
    },
    p: 0,
    findDOMNode: null
  }, p = /* @__PURE__ */ Symbol.for("react.portal");
  function O(A, S, G) {
    var H = 3 < arguments.length && arguments[3] !== void 0 ? arguments[3] : null;
    return {
      $$typeof: p,
      key: H == null ? null : "" + H,
      children: A,
      containerInfo: S,
      implementation: G
    };
  }
  var C = i.__CLIENT_INTERNALS_DO_NOT_USE_OR_WARN_USERS_THEY_CANNOT_UPGRADE;
  function D(A, S) {
    if (A === "font") return "";
    if (typeof S == "string")
      return S === "use-credentials" ? S : "";
  }
  return It.__DOM_INTERNALS_DO_NOT_USE_OR_WARN_USERS_THEY_CANNOT_UPGRADE = o, It.createPortal = function(A, S) {
    var G = 2 < arguments.length && arguments[2] !== void 0 ? arguments[2] : null;
    if (!S || S.nodeType !== 1 && S.nodeType !== 9 && S.nodeType !== 11)
      throw Error(f(299));
    return O(A, S, null, G);
  }, It.flushSync = function(A) {
    var S = C.T, G = o.p;
    try {
      if (C.T = null, o.p = 2, A) return A();
    } finally {
      C.T = S, o.p = G, o.d.f();
    }
  }, It.preconnect = function(A, S) {
    typeof A == "string" && (S ? (S = S.crossOrigin, S = typeof S == "string" ? S === "use-credentials" ? S : "" : void 0) : S = null, o.d.C(A, S));
  }, It.prefetchDNS = function(A) {
    typeof A == "string" && o.d.D(A);
  }, It.preinit = function(A, S) {
    if (typeof A == "string" && S && typeof S.as == "string") {
      var G = S.as, H = D(G, S.crossOrigin), J = typeof S.integrity == "string" ? S.integrity : void 0, st = typeof S.fetchPriority == "string" ? S.fetchPriority : void 0;
      G === "style" ? o.d.S(
        A,
        typeof S.precedence == "string" ? S.precedence : void 0,
        {
          crossOrigin: H,
          integrity: J,
          fetchPriority: st
        }
      ) : G === "script" && o.d.X(A, {
        crossOrigin: H,
        integrity: J,
        fetchPriority: st,
        nonce: typeof S.nonce == "string" ? S.nonce : void 0
      });
    }
  }, It.preinitModule = function(A, S) {
    if (typeof A == "string")
      if (typeof S == "object" && S !== null) {
        if (S.as == null || S.as === "script") {
          var G = D(
            S.as,
            S.crossOrigin
          );
          o.d.M(A, {
            crossOrigin: G,
            integrity: typeof S.integrity == "string" ? S.integrity : void 0,
            nonce: typeof S.nonce == "string" ? S.nonce : void 0
          });
        }
      } else S == null && o.d.M(A);
  }, It.preload = function(A, S) {
    if (typeof A == "string" && typeof S == "object" && S !== null && typeof S.as == "string") {
      var G = S.as, H = D(G, S.crossOrigin);
      o.d.L(A, G, {
        crossOrigin: H,
        integrity: typeof S.integrity == "string" ? S.integrity : void 0,
        nonce: typeof S.nonce == "string" ? S.nonce : void 0,
        type: typeof S.type == "string" ? S.type : void 0,
        fetchPriority: typeof S.fetchPriority == "string" ? S.fetchPriority : void 0,
        referrerPolicy: typeof S.referrerPolicy == "string" ? S.referrerPolicy : void 0,
        imageSrcSet: typeof S.imageSrcSet == "string" ? S.imageSrcSet : void 0,
        imageSizes: typeof S.imageSizes == "string" ? S.imageSizes : void 0,
        media: typeof S.media == "string" ? S.media : void 0
      });
    }
  }, It.preloadModule = function(A, S) {
    if (typeof A == "string")
      if (S) {
        var G = D(S.as, S.crossOrigin);
        o.d.m(A, {
          as: typeof S.as == "string" && S.as !== "script" ? S.as : void 0,
          crossOrigin: G,
          integrity: typeof S.integrity == "string" ? S.integrity : void 0
        });
      } else o.d.m(A);
  }, It.requestFormReset = function(A) {
    o.d.r(A);
  }, It.unstable_batchedUpdates = function(A, S) {
    return A(S);
  }, It.useFormState = function(A, S, G) {
    return C.H.useFormState(A, S, G);
  }, It.useFormStatus = function() {
    return C.H.useHostTransitionStatus();
  }, It.version = "19.2.4", It;
}
var th;
function yv() {
  if (th) return Hf.exports;
  th = 1;
  function i() {
    if (!(typeof __REACT_DEVTOOLS_GLOBAL_HOOK__ > "u" || typeof __REACT_DEVTOOLS_GLOBAL_HOOK__.checkDCE != "function"))
      try {
        __REACT_DEVTOOLS_GLOBAL_HOOK__.checkDCE(i);
      } catch (f) {
        console.error(f);
      }
  }
  return i(), Hf.exports = mv(), Hf.exports;
}
var eh;
function vv() {
  if (eh) return jn;
  eh = 1;
  var i = dv(), f = Xf(), r = yv();
  function o(t) {
    var e = "https://react.dev/errors/" + t;
    if (1 < arguments.length) {
      e += "?args[]=" + encodeURIComponent(arguments[1]);
      for (var l = 2; l < arguments.length; l++)
        e += "&args[]=" + encodeURIComponent(arguments[l]);
    }
    return "Minified React error #" + t + "; visit " + e + " for the full message or use the non-minified dev environment for full errors and additional helpful warnings.";
  }
  function p(t) {
    return !(!t || t.nodeType !== 1 && t.nodeType !== 9 && t.nodeType !== 11);
  }
  function O(t) {
    var e = t, l = t;
    if (t.alternate) for (; e.return; ) e = e.return;
    else {
      t = e;
      do
        e = t, (e.flags & 4098) !== 0 && (l = e.return), t = e.return;
      while (t);
    }
    return e.tag === 3 ? l : null;
  }
  function C(t) {
    if (t.tag === 13) {
      var e = t.memoizedState;
      if (e === null && (t = t.alternate, t !== null && (e = t.memoizedState)), e !== null) return e.dehydrated;
    }
    return null;
  }
  function D(t) {
    if (t.tag === 31) {
      var e = t.memoizedState;
      if (e === null && (t = t.alternate, t !== null && (e = t.memoizedState)), e !== null) return e.dehydrated;
    }
    return null;
  }
  function A(t) {
    if (O(t) !== t)
      throw Error(o(188));
  }
  function S(t) {
    var e = t.alternate;
    if (!e) {
      if (e = O(t), e === null) throw Error(o(188));
      return e !== t ? null : t;
    }
    for (var l = t, a = e; ; ) {
      var n = l.return;
      if (n === null) break;
      var u = n.alternate;
      if (u === null) {
        if (a = n.return, a !== null) {
          l = a;
          continue;
        }
        break;
      }
      if (n.child === u.child) {
        for (u = n.child; u; ) {
          if (u === l) return A(n), t;
          if (u === a) return A(n), e;
          u = u.sibling;
        }
        throw Error(o(188));
      }
      if (l.return !== a.return) l = n, a = u;
      else {
        for (var c = !1, s = n.child; s; ) {
          if (s === l) {
            c = !0, l = n, a = u;
            break;
          }
          if (s === a) {
            c = !0, a = n, l = u;
            break;
          }
          s = s.sibling;
        }
        if (!c) {
          for (s = u.child; s; ) {
            if (s === l) {
              c = !0, l = u, a = n;
              break;
            }
            if (s === a) {
              c = !0, a = u, l = n;
              break;
            }
            s = s.sibling;
          }
          if (!c) throw Error(o(189));
        }
      }
      if (l.alternate !== a) throw Error(o(190));
    }
    if (l.tag !== 3) throw Error(o(188));
    return l.stateNode.current === l ? t : e;
  }
  function G(t) {
    var e = t.tag;
    if (e === 5 || e === 26 || e === 27 || e === 6) return t;
    for (t = t.child; t !== null; ) {
      if (e = G(t), e !== null) return e;
      t = t.sibling;
    }
    return null;
  }
  var H = Object.assign, J = /* @__PURE__ */ Symbol.for("react.element"), st = /* @__PURE__ */ Symbol.for("react.transitional.element"), $ = /* @__PURE__ */ Symbol.for("react.portal"), k = /* @__PURE__ */ Symbol.for("react.fragment"), nt = /* @__PURE__ */ Symbol.for("react.strict_mode"), ot = /* @__PURE__ */ Symbol.for("react.profiler"), Nt = /* @__PURE__ */ Symbol.for("react.consumer"), gt = /* @__PURE__ */ Symbol.for("react.context"), _t = /* @__PURE__ */ Symbol.for("react.forward_ref"), Ct = /* @__PURE__ */ Symbol.for("react.suspense"), Et = /* @__PURE__ */ Symbol.for("react.suspense_list"), I = /* @__PURE__ */ Symbol.for("react.memo"), j = /* @__PURE__ */ Symbol.for("react.lazy"), Dt = /* @__PURE__ */ Symbol.for("react.activity"), Ye = /* @__PURE__ */ Symbol.for("react.memo_cache_sentinel"), fe = Symbol.iterator;
  function Yt(t) {
    return t === null || typeof t != "object" ? null : (t = fe && t[fe] || t["@@iterator"], typeof t == "function" ? t : null);
  }
  var qe = /* @__PURE__ */ Symbol.for("react.client.reference");
  function se(t) {
    if (t == null) return null;
    if (typeof t == "function")
      return t.$$typeof === qe ? null : t.displayName || t.name || null;
    if (typeof t == "string") return t;
    switch (t) {
      case k:
        return "Fragment";
      case ot:
        return "Profiler";
      case nt:
        return "StrictMode";
      case Ct:
        return "Suspense";
      case Et:
        return "SuspenseList";
      case Dt:
        return "Activity";
    }
    if (typeof t == "object")
      switch (t.$$typeof) {
        case $:
          return "Portal";
        case gt:
          return t.displayName || "Context";
        case Nt:
          return (t._context.displayName || "Context") + ".Consumer";
        case _t:
          var e = t.render;
          return t = t.displayName, t || (t = e.displayName || e.name || "", t = t !== "" ? "ForwardRef(" + t + ")" : "ForwardRef"), t;
        case I:
          return e = t.displayName || null, e !== null ? e : se(t.type) || "Memo";
        case j:
          e = t._payload, t = t._init;
          try {
            return se(t(e));
          } catch {
          }
      }
    return null;
  }
  var Zt = Array.isArray, T = f.__CLIENT_INTERNALS_DO_NOT_USE_OR_WARN_USERS_THEY_CANNOT_UPGRADE, U = r.__DOM_INTERNALS_DO_NOT_USE_OR_WARN_USERS_THEY_CANNOT_UPGRADE, V = {
    pending: !1,
    data: null,
    method: null,
    action: null
  }, rt = [], R = -1;
  function m(t) {
    return { current: t };
  }
  function x(t) {
    0 > R || (t.current = rt[R], rt[R] = null, R--);
  }
  function N(t, e) {
    R++, rt[R] = t.current, t.current = e;
  }
  var q = m(null), w = m(null), L = m(null), ct = m(null);
  function Lt(t, e) {
    switch (N(L, e), N(w, t), N(q, null), e.nodeType) {
      case 9:
      case 11:
        t = (t = e.documentElement) && (t = t.namespaceURI) ? vd(t) : 0;
        break;
      default:
        if (t = e.tagName, e = e.namespaceURI)
          e = vd(e), t = gd(e, t);
        else
          switch (t) {
            case "svg":
              t = 1;
              break;
            case "math":
              t = 2;
              break;
            default:
              t = 0;
          }
    }
    x(q), N(q, t);
  }
  function tt() {
    x(q), x(w), x(L);
  }
  function cl(t) {
    t.memoizedState !== null && N(ct, t);
    var e = q.current, l = gd(e, t.type);
    e !== l && (N(w, t), N(q, l));
  }
  function Xe(t) {
    w.current === t && (x(q), x(w)), ct.current === t && (x(ct), Un._currentValue = V);
  }
  var fl, aa;
  function Se(t) {
    if (fl === void 0)
      try {
        throw Error();
      } catch (l) {
        var e = l.stack.trim().match(/\n( *(at )?)/);
        fl = e && e[1] || "", aa = -1 < l.stack.indexOf(`
    at`) ? " (<anonymous>)" : -1 < l.stack.indexOf("@") ? "@unknown:0:0" : "";
      }
    return `
` + fl + t + aa;
  }
  var ri = !1;
  function di(t, e) {
    if (!t || ri) return "";
    ri = !0;
    var l = Error.prepareStackTrace;
    Error.prepareStackTrace = void 0;
    try {
      var a = {
        DetermineComponentFrameRoot: function() {
          try {
            if (e) {
              var _ = function() {
                throw Error();
              };
              if (Object.defineProperty(_.prototype, "props", {
                set: function() {
                  throw Error();
                }
              }), typeof Reflect == "object" && Reflect.construct) {
                try {
                  Reflect.construct(_, []);
                } catch (z) {
                  var b = z;
                }
                Reflect.construct(t, [], _);
              } else {
                try {
                  _.call();
                } catch (z) {
                  b = z;
                }
                t.call(_.prototype);
              }
            } else {
              try {
                throw Error();
              } catch (z) {
                b = z;
              }
              (_ = t()) && typeof _.catch == "function" && _.catch(function() {
              });
            }
          } catch (z) {
            if (z && b && typeof z.stack == "string")
              return [z.stack, b.stack];
          }
          return [null, null];
        }
      };
      a.DetermineComponentFrameRoot.displayName = "DetermineComponentFrameRoot";
      var n = Object.getOwnPropertyDescriptor(
        a.DetermineComponentFrameRoot,
        "name"
      );
      n && n.configurable && Object.defineProperty(
        a.DetermineComponentFrameRoot,
        "name",
        { value: "DetermineComponentFrameRoot" }
      );
      var u = a.DetermineComponentFrameRoot(), c = u[0], s = u[1];
      if (c && s) {
        var d = c.split(`
`), g = s.split(`
`);
        for (n = a = 0; a < d.length && !d[a].includes("DetermineComponentFrameRoot"); )
          a++;
        for (; n < g.length && !g[n].includes(
          "DetermineComponentFrameRoot"
        ); )
          n++;
        if (a === d.length || n === g.length)
          for (a = d.length - 1, n = g.length - 1; 1 <= a && 0 <= n && d[a] !== g[n]; )
            n--;
        for (; 1 <= a && 0 <= n; a--, n--)
          if (d[a] !== g[n]) {
            if (a !== 1 || n !== 1)
              do
                if (a--, n--, 0 > n || d[a] !== g[n]) {
                  var E = `
` + d[a].replace(" at new ", " at ");
                  return t.displayName && E.includes("<anonymous>") && (E = E.replace("<anonymous>", t.displayName)), E;
                }
              while (1 <= a && 0 <= n);
            break;
          }
      }
    } finally {
      ri = !1, Error.prepareStackTrace = l;
    }
    return (l = t ? t.displayName || t.name : "") ? Se(l) : "";
  }
  function Yh(t, e) {
    switch (t.tag) {
      case 26:
      case 27:
      case 5:
        return Se(t.type);
      case 16:
        return Se("Lazy");
      case 13:
        return t.child !== e && e !== null ? Se("Suspense Fallback") : Se("Suspense");
      case 19:
        return Se("SuspenseList");
      case 0:
      case 15:
        return di(t.type, !1);
      case 11:
        return di(t.type.render, !1);
      case 1:
        return di(t.type, !0);
      case 31:
        return Se("Activity");
      default:
        return "";
    }
  }
  function Kf(t) {
    try {
      var e = "", l = null;
      do
        e += Yh(t, l), l = t, t = t.return;
      while (t);
      return e;
    } catch (a) {
      return `
Error generating stack: ` + a.message + `
` + a.stack;
    }
  }
  var hi = Object.prototype.hasOwnProperty, mi = i.unstable_scheduleCallback, yi = i.unstable_cancelCallback, Xh = i.unstable_shouldYield, wh = i.unstable_requestPaint, oe = i.unstable_now, Zh = i.unstable_getCurrentPriorityLevel, Jf = i.unstable_ImmediatePriority, kf = i.unstable_UserBlockingPriority, Xn = i.unstable_NormalPriority, Lh = i.unstable_LowPriority, Ff = i.unstable_IdlePriority, Vh = i.log, Kh = i.unstable_setDisableYieldValue, wa = null, re = null;
  function sl(t) {
    if (typeof Vh == "function" && Kh(t), re && typeof re.setStrictMode == "function")
      try {
        re.setStrictMode(wa, t);
      } catch {
      }
  }
  var de = Math.clz32 ? Math.clz32 : Fh, Jh = Math.log, kh = Math.LN2;
  function Fh(t) {
    return t >>>= 0, t === 0 ? 32 : 31 - (Jh(t) / kh | 0) | 0;
  }
  var wn = 256, Zn = 262144, Ln = 4194304;
  function Bl(t) {
    var e = t & 42;
    if (e !== 0) return e;
    switch (t & -t) {
      case 1:
        return 1;
      case 2:
        return 2;
      case 4:
        return 4;
      case 8:
        return 8;
      case 16:
        return 16;
      case 32:
        return 32;
      case 64:
        return 64;
      case 128:
        return 128;
      case 256:
      case 512:
      case 1024:
      case 2048:
      case 4096:
      case 8192:
      case 16384:
      case 32768:
      case 65536:
      case 131072:
        return t & 261888;
      case 262144:
      case 524288:
      case 1048576:
      case 2097152:
        return t & 3932160;
      case 4194304:
      case 8388608:
      case 16777216:
      case 33554432:
        return t & 62914560;
      case 67108864:
        return 67108864;
      case 134217728:
        return 134217728;
      case 268435456:
        return 268435456;
      case 536870912:
        return 536870912;
      case 1073741824:
        return 0;
      default:
        return t;
    }
  }
  function Vn(t, e, l) {
    var a = t.pendingLanes;
    if (a === 0) return 0;
    var n = 0, u = t.suspendedLanes, c = t.pingedLanes;
    t = t.warmLanes;
    var s = a & 134217727;
    return s !== 0 ? (a = s & ~u, a !== 0 ? n = Bl(a) : (c &= s, c !== 0 ? n = Bl(c) : l || (l = s & ~t, l !== 0 && (n = Bl(l))))) : (s = a & ~u, s !== 0 ? n = Bl(s) : c !== 0 ? n = Bl(c) : l || (l = a & ~t, l !== 0 && (n = Bl(l)))), n === 0 ? 0 : e !== 0 && e !== n && (e & u) === 0 && (u = n & -n, l = e & -e, u >= l || u === 32 && (l & 4194048) !== 0) ? e : n;
  }
  function Za(t, e) {
    return (t.pendingLanes & ~(t.suspendedLanes & ~t.pingedLanes) & e) === 0;
  }
  function Wh(t, e) {
    switch (t) {
      case 1:
      case 2:
      case 4:
      case 8:
      case 64:
        return e + 250;
      case 16:
      case 32:
      case 128:
      case 256:
      case 512:
      case 1024:
      case 2048:
      case 4096:
      case 8192:
      case 16384:
      case 32768:
      case 65536:
      case 131072:
      case 262144:
      case 524288:
      case 1048576:
      case 2097152:
        return e + 5e3;
      case 4194304:
      case 8388608:
      case 16777216:
      case 33554432:
        return -1;
      case 67108864:
      case 134217728:
      case 268435456:
      case 536870912:
      case 1073741824:
        return -1;
      default:
        return -1;
    }
  }
  function Wf() {
    var t = Ln;
    return Ln <<= 1, (Ln & 62914560) === 0 && (Ln = 4194304), t;
  }
  function vi(t) {
    for (var e = [], l = 0; 31 > l; l++) e.push(t);
    return e;
  }
  function La(t, e) {
    t.pendingLanes |= e, e !== 268435456 && (t.suspendedLanes = 0, t.pingedLanes = 0, t.warmLanes = 0);
  }
  function $h(t, e, l, a, n, u) {
    var c = t.pendingLanes;
    t.pendingLanes = l, t.suspendedLanes = 0, t.pingedLanes = 0, t.warmLanes = 0, t.expiredLanes &= l, t.entangledLanes &= l, t.errorRecoveryDisabledLanes &= l, t.shellSuspendCounter = 0;
    var s = t.entanglements, d = t.expirationTimes, g = t.hiddenUpdates;
    for (l = c & ~l; 0 < l; ) {
      var E = 31 - de(l), _ = 1 << E;
      s[E] = 0, d[E] = -1;
      var b = g[E];
      if (b !== null)
        for (g[E] = null, E = 0; E < b.length; E++) {
          var z = b[E];
          z !== null && (z.lane &= -536870913);
        }
      l &= ~_;
    }
    a !== 0 && $f(t, a, 0), u !== 0 && n === 0 && t.tag !== 0 && (t.suspendedLanes |= u & ~(c & ~e));
  }
  function $f(t, e, l) {
    t.pendingLanes |= e, t.suspendedLanes &= ~e;
    var a = 31 - de(e);
    t.entangledLanes |= e, t.entanglements[a] = t.entanglements[a] | 1073741824 | l & 261930;
  }
  function If(t, e) {
    var l = t.entangledLanes |= e;
    for (t = t.entanglements; l; ) {
      var a = 31 - de(l), n = 1 << a;
      n & e | t[a] & e && (t[a] |= e), l &= ~n;
    }
  }
  function Pf(t, e) {
    var l = e & -e;
    return l = (l & 42) !== 0 ? 1 : gi(l), (l & (t.suspendedLanes | e)) !== 0 ? 0 : l;
  }
  function gi(t) {
    switch (t) {
      case 2:
        t = 1;
        break;
      case 8:
        t = 4;
        break;
      case 32:
        t = 16;
        break;
      case 256:
      case 512:
      case 1024:
      case 2048:
      case 4096:
      case 8192:
      case 16384:
      case 32768:
      case 65536:
      case 131072:
      case 262144:
      case 524288:
      case 1048576:
      case 2097152:
      case 4194304:
      case 8388608:
      case 16777216:
      case 33554432:
        t = 128;
        break;
      case 268435456:
        t = 134217728;
        break;
      default:
        t = 0;
    }
    return t;
  }
  function bi(t) {
    return t &= -t, 2 < t ? 8 < t ? (t & 134217727) !== 0 ? 32 : 268435456 : 8 : 2;
  }
  function ts() {
    var t = U.p;
    return t !== 0 ? t : (t = window.event, t === void 0 ? 32 : Yd(t.type));
  }
  function es(t, e) {
    var l = U.p;
    try {
      return U.p = t, e();
    } finally {
      U.p = l;
    }
  }
  var ol = Math.random().toString(36).slice(2), Jt = "__reactFiber$" + ol, ee = "__reactProps$" + ol, na = "__reactContainer$" + ol, pi = "__reactEvents$" + ol, Ih = "__reactListeners$" + ol, Ph = "__reactHandles$" + ol, ls = "__reactResources$" + ol, Va = "__reactMarker$" + ol;
  function Si(t) {
    delete t[Jt], delete t[ee], delete t[pi], delete t[Ih], delete t[Ph];
  }
  function ua(t) {
    var e = t[Jt];
    if (e) return e;
    for (var l = t.parentNode; l; ) {
      if (e = l[na] || l[Jt]) {
        if (l = e.alternate, e.child !== null || l !== null && l.child !== null)
          for (t = Ed(t); t !== null; ) {
            if (l = t[Jt]) return l;
            t = Ed(t);
          }
        return e;
      }
      t = l, l = t.parentNode;
    }
    return null;
  }
  function ia(t) {
    if (t = t[Jt] || t[na]) {
      var e = t.tag;
      if (e === 5 || e === 6 || e === 13 || e === 31 || e === 26 || e === 27 || e === 3)
        return t;
    }
    return null;
  }
  function Ka(t) {
    var e = t.tag;
    if (e === 5 || e === 26 || e === 27 || e === 6) return t.stateNode;
    throw Error(o(33));
  }
  function ca(t) {
    var e = t[ls];
    return e || (e = t[ls] = { hoistableStyles: /* @__PURE__ */ new Map(), hoistableScripts: /* @__PURE__ */ new Map() }), e;
  }
  function Vt(t) {
    t[Va] = !0;
  }
  var as = /* @__PURE__ */ new Set(), ns = {};
  function Ql(t, e) {
    fa(t, e), fa(t + "Capture", e);
  }
  function fa(t, e) {
    for (ns[t] = e, t = 0; t < e.length; t++)
      as.add(e[t]);
  }
  var tm = RegExp(
    "^[:A-Z_a-z\\u00C0-\\u00D6\\u00D8-\\u00F6\\u00F8-\\u02FF\\u0370-\\u037D\\u037F-\\u1FFF\\u200C-\\u200D\\u2070-\\u218F\\u2C00-\\u2FEF\\u3001-\\uD7FF\\uF900-\\uFDCF\\uFDF0-\\uFFFD][:A-Z_a-z\\u00C0-\\u00D6\\u00D8-\\u00F6\\u00F8-\\u02FF\\u0370-\\u037D\\u037F-\\u1FFF\\u200C-\\u200D\\u2070-\\u218F\\u2C00-\\u2FEF\\u3001-\\uD7FF\\uF900-\\uFDCF\\uFDF0-\\uFFFD\\-.0-9\\u00B7\\u0300-\\u036F\\u203F-\\u2040]*$"
  ), us = {}, is = {};
  function em(t) {
    return hi.call(is, t) ? !0 : hi.call(us, t) ? !1 : tm.test(t) ? is[t] = !0 : (us[t] = !0, !1);
  }
  function Kn(t, e, l) {
    if (em(e))
      if (l === null) t.removeAttribute(e);
      else {
        switch (typeof l) {
          case "undefined":
          case "function":
          case "symbol":
            t.removeAttribute(e);
            return;
          case "boolean":
            var a = e.toLowerCase().slice(0, 5);
            if (a !== "data-" && a !== "aria-") {
              t.removeAttribute(e);
              return;
            }
        }
        t.setAttribute(e, "" + l);
      }
  }
  function Jn(t, e, l) {
    if (l === null) t.removeAttribute(e);
    else {
      switch (typeof l) {
        case "undefined":
        case "function":
        case "symbol":
        case "boolean":
          t.removeAttribute(e);
          return;
      }
      t.setAttribute(e, "" + l);
    }
  }
  function we(t, e, l, a) {
    if (a === null) t.removeAttribute(l);
    else {
      switch (typeof a) {
        case "undefined":
        case "function":
        case "symbol":
        case "boolean":
          t.removeAttribute(l);
          return;
      }
      t.setAttributeNS(e, l, "" + a);
    }
  }
  function ze(t) {
    switch (typeof t) {
      case "bigint":
      case "boolean":
      case "number":
      case "string":
      case "undefined":
        return t;
      case "object":
        return t;
      default:
        return "";
    }
  }
  function cs(t) {
    var e = t.type;
    return (t = t.nodeName) && t.toLowerCase() === "input" && (e === "checkbox" || e === "radio");
  }
  function lm(t, e, l) {
    var a = Object.getOwnPropertyDescriptor(
      t.constructor.prototype,
      e
    );
    if (!t.hasOwnProperty(e) && typeof a < "u" && typeof a.get == "function" && typeof a.set == "function") {
      var n = a.get, u = a.set;
      return Object.defineProperty(t, e, {
        configurable: !0,
        get: function() {
          return n.call(this);
        },
        set: function(c) {
          l = "" + c, u.call(this, c);
        }
      }), Object.defineProperty(t, e, {
        enumerable: a.enumerable
      }), {
        getValue: function() {
          return l;
        },
        setValue: function(c) {
          l = "" + c;
        },
        stopTracking: function() {
          t._valueTracker = null, delete t[e];
        }
      };
    }
  }
  function zi(t) {
    if (!t._valueTracker) {
      var e = cs(t) ? "checked" : "value";
      t._valueTracker = lm(
        t,
        e,
        "" + t[e]
      );
    }
  }
  function fs(t) {
    if (!t) return !1;
    var e = t._valueTracker;
    if (!e) return !0;
    var l = e.getValue(), a = "";
    return t && (a = cs(t) ? t.checked ? "true" : "false" : t.value), t = a, t !== l ? (e.setValue(t), !0) : !1;
  }
  function kn(t) {
    if (t = t || (typeof document < "u" ? document : void 0), typeof t > "u") return null;
    try {
      return t.activeElement || t.body;
    } catch {
      return t.body;
    }
  }
  var am = /[\n"\\]/g;
  function Te(t) {
    return t.replace(
      am,
      function(e) {
        return "\\" + e.charCodeAt(0).toString(16) + " ";
      }
    );
  }
  function Ti(t, e, l, a, n, u, c, s) {
    t.name = "", c != null && typeof c != "function" && typeof c != "symbol" && typeof c != "boolean" ? t.type = c : t.removeAttribute("type"), e != null ? c === "number" ? (e === 0 && t.value === "" || t.value != e) && (t.value = "" + ze(e)) : t.value !== "" + ze(e) && (t.value = "" + ze(e)) : c !== "submit" && c !== "reset" || t.removeAttribute("value"), e != null ? Ai(t, c, ze(e)) : l != null ? Ai(t, c, ze(l)) : a != null && t.removeAttribute("value"), n == null && u != null && (t.defaultChecked = !!u), n != null && (t.checked = n && typeof n != "function" && typeof n != "symbol"), s != null && typeof s != "function" && typeof s != "symbol" && typeof s != "boolean" ? t.name = "" + ze(s) : t.removeAttribute("name");
  }
  function ss(t, e, l, a, n, u, c, s) {
    if (u != null && typeof u != "function" && typeof u != "symbol" && typeof u != "boolean" && (t.type = u), e != null || l != null) {
      if (!(u !== "submit" && u !== "reset" || e != null)) {
        zi(t);
        return;
      }
      l = l != null ? "" + ze(l) : "", e = e != null ? "" + ze(e) : l, s || e === t.value || (t.value = e), t.defaultValue = e;
    }
    a = a ?? n, a = typeof a != "function" && typeof a != "symbol" && !!a, t.checked = s ? t.checked : !!a, t.defaultChecked = !!a, c != null && typeof c != "function" && typeof c != "symbol" && typeof c != "boolean" && (t.name = c), zi(t);
  }
  function Ai(t, e, l) {
    e === "number" && kn(t.ownerDocument) === t || t.defaultValue === "" + l || (t.defaultValue = "" + l);
  }
  function sa(t, e, l, a) {
    if (t = t.options, e) {
      e = {};
      for (var n = 0; n < l.length; n++)
        e["$" + l[n]] = !0;
      for (l = 0; l < t.length; l++)
        n = e.hasOwnProperty("$" + t[l].value), t[l].selected !== n && (t[l].selected = n), n && a && (t[l].defaultSelected = !0);
    } else {
      for (l = "" + ze(l), e = null, n = 0; n < t.length; n++) {
        if (t[n].value === l) {
          t[n].selected = !0, a && (t[n].defaultSelected = !0);
          return;
        }
        e !== null || t[n].disabled || (e = t[n]);
      }
      e !== null && (e.selected = !0);
    }
  }
  function os(t, e, l) {
    if (e != null && (e = "" + ze(e), e !== t.value && (t.value = e), l == null)) {
      t.defaultValue !== e && (t.defaultValue = e);
      return;
    }
    t.defaultValue = l != null ? "" + ze(l) : "";
  }
  function rs(t, e, l, a) {
    if (e == null) {
      if (a != null) {
        if (l != null) throw Error(o(92));
        if (Zt(a)) {
          if (1 < a.length) throw Error(o(93));
          a = a[0];
        }
        l = a;
      }
      l == null && (l = ""), e = l;
    }
    l = ze(e), t.defaultValue = l, a = t.textContent, a === l && a !== "" && a !== null && (t.value = a), zi(t);
  }
  function oa(t, e) {
    if (e) {
      var l = t.firstChild;
      if (l && l === t.lastChild && l.nodeType === 3) {
        l.nodeValue = e;
        return;
      }
    }
    t.textContent = e;
  }
  var nm = new Set(
    "animationIterationCount aspectRatio borderImageOutset borderImageSlice borderImageWidth boxFlex boxFlexGroup boxOrdinalGroup columnCount columns flex flexGrow flexPositive flexShrink flexNegative flexOrder gridArea gridRow gridRowEnd gridRowSpan gridRowStart gridColumn gridColumnEnd gridColumnSpan gridColumnStart fontWeight lineClamp lineHeight opacity order orphans scale tabSize widows zIndex zoom fillOpacity floodOpacity stopOpacity strokeDasharray strokeDashoffset strokeMiterlimit strokeOpacity strokeWidth MozAnimationIterationCount MozBoxFlex MozBoxFlexGroup MozLineClamp msAnimationIterationCount msFlex msZoom msFlexGrow msFlexNegative msFlexOrder msFlexPositive msFlexShrink msGridColumn msGridColumnSpan msGridRow msGridRowSpan WebkitAnimationIterationCount WebkitBoxFlex WebKitBoxFlexGroup WebkitBoxOrdinalGroup WebkitColumnCount WebkitColumns WebkitFlex WebkitFlexGrow WebkitFlexPositive WebkitFlexShrink WebkitLineClamp".split(
      " "
    )
  );
  function ds(t, e, l) {
    var a = e.indexOf("--") === 0;
    l == null || typeof l == "boolean" || l === "" ? a ? t.setProperty(e, "") : e === "float" ? t.cssFloat = "" : t[e] = "" : a ? t.setProperty(e, l) : typeof l != "number" || l === 0 || nm.has(e) ? e === "float" ? t.cssFloat = l : t[e] = ("" + l).trim() : t[e] = l + "px";
  }
  function hs(t, e, l) {
    if (e != null && typeof e != "object")
      throw Error(o(62));
    if (t = t.style, l != null) {
      for (var a in l)
        !l.hasOwnProperty(a) || e != null && e.hasOwnProperty(a) || (a.indexOf("--") === 0 ? t.setProperty(a, "") : a === "float" ? t.cssFloat = "" : t[a] = "");
      for (var n in e)
        a = e[n], e.hasOwnProperty(n) && l[n] !== a && ds(t, n, a);
    } else
      for (var u in e)
        e.hasOwnProperty(u) && ds(t, u, e[u]);
  }
  function Ei(t) {
    if (t.indexOf("-") === -1) return !1;
    switch (t) {
      case "annotation-xml":
      case "color-profile":
      case "font-face":
      case "font-face-src":
      case "font-face-uri":
      case "font-face-format":
      case "font-face-name":
      case "missing-glyph":
        return !1;
      default:
        return !0;
    }
  }
  var um = /* @__PURE__ */ new Map([
    ["acceptCharset", "accept-charset"],
    ["htmlFor", "for"],
    ["httpEquiv", "http-equiv"],
    ["crossOrigin", "crossorigin"],
    ["accentHeight", "accent-height"],
    ["alignmentBaseline", "alignment-baseline"],
    ["arabicForm", "arabic-form"],
    ["baselineShift", "baseline-shift"],
    ["capHeight", "cap-height"],
    ["clipPath", "clip-path"],
    ["clipRule", "clip-rule"],
    ["colorInterpolation", "color-interpolation"],
    ["colorInterpolationFilters", "color-interpolation-filters"],
    ["colorProfile", "color-profile"],
    ["colorRendering", "color-rendering"],
    ["dominantBaseline", "dominant-baseline"],
    ["enableBackground", "enable-background"],
    ["fillOpacity", "fill-opacity"],
    ["fillRule", "fill-rule"],
    ["floodColor", "flood-color"],
    ["floodOpacity", "flood-opacity"],
    ["fontFamily", "font-family"],
    ["fontSize", "font-size"],
    ["fontSizeAdjust", "font-size-adjust"],
    ["fontStretch", "font-stretch"],
    ["fontStyle", "font-style"],
    ["fontVariant", "font-variant"],
    ["fontWeight", "font-weight"],
    ["glyphName", "glyph-name"],
    ["glyphOrientationHorizontal", "glyph-orientation-horizontal"],
    ["glyphOrientationVertical", "glyph-orientation-vertical"],
    ["horizAdvX", "horiz-adv-x"],
    ["horizOriginX", "horiz-origin-x"],
    ["imageRendering", "image-rendering"],
    ["letterSpacing", "letter-spacing"],
    ["lightingColor", "lighting-color"],
    ["markerEnd", "marker-end"],
    ["markerMid", "marker-mid"],
    ["markerStart", "marker-start"],
    ["overlinePosition", "overline-position"],
    ["overlineThickness", "overline-thickness"],
    ["paintOrder", "paint-order"],
    ["panose-1", "panose-1"],
    ["pointerEvents", "pointer-events"],
    ["renderingIntent", "rendering-intent"],
    ["shapeRendering", "shape-rendering"],
    ["stopColor", "stop-color"],
    ["stopOpacity", "stop-opacity"],
    ["strikethroughPosition", "strikethrough-position"],
    ["strikethroughThickness", "strikethrough-thickness"],
    ["strokeDasharray", "stroke-dasharray"],
    ["strokeDashoffset", "stroke-dashoffset"],
    ["strokeLinecap", "stroke-linecap"],
    ["strokeLinejoin", "stroke-linejoin"],
    ["strokeMiterlimit", "stroke-miterlimit"],
    ["strokeOpacity", "stroke-opacity"],
    ["strokeWidth", "stroke-width"],
    ["textAnchor", "text-anchor"],
    ["textDecoration", "text-decoration"],
    ["textRendering", "text-rendering"],
    ["transformOrigin", "transform-origin"],
    ["underlinePosition", "underline-position"],
    ["underlineThickness", "underline-thickness"],
    ["unicodeBidi", "unicode-bidi"],
    ["unicodeRange", "unicode-range"],
    ["unitsPerEm", "units-per-em"],
    ["vAlphabetic", "v-alphabetic"],
    ["vHanging", "v-hanging"],
    ["vIdeographic", "v-ideographic"],
    ["vMathematical", "v-mathematical"],
    ["vectorEffect", "vector-effect"],
    ["vertAdvY", "vert-adv-y"],
    ["vertOriginX", "vert-origin-x"],
    ["vertOriginY", "vert-origin-y"],
    ["wordSpacing", "word-spacing"],
    ["writingMode", "writing-mode"],
    ["xmlnsXlink", "xmlns:xlink"],
    ["xHeight", "x-height"]
  ]), im = /^[\u0000-\u001F ]*j[\r\n\t]*a[\r\n\t]*v[\r\n\t]*a[\r\n\t]*s[\r\n\t]*c[\r\n\t]*r[\r\n\t]*i[\r\n\t]*p[\r\n\t]*t[\r\n\t]*:/i;
  function Fn(t) {
    return im.test("" + t) ? "javascript:throw new Error('React has blocked a javascript: URL as a security precaution.')" : t;
  }
  function Ze() {
  }
  var Oi = null;
  function Mi(t) {
    return t = t.target || t.srcElement || window, t.correspondingUseElement && (t = t.correspondingUseElement), t.nodeType === 3 ? t.parentNode : t;
  }
  var ra = null, da = null;
  function ms(t) {
    var e = ia(t);
    if (e && (t = e.stateNode)) {
      var l = t[ee] || null;
      t: switch (t = e.stateNode, e.type) {
        case "input":
          if (Ti(
            t,
            l.value,
            l.defaultValue,
            l.defaultValue,
            l.checked,
            l.defaultChecked,
            l.type,
            l.name
          ), e = l.name, l.type === "radio" && e != null) {
            for (l = t; l.parentNode; ) l = l.parentNode;
            for (l = l.querySelectorAll(
              'input[name="' + Te(
                "" + e
              ) + '"][type="radio"]'
            ), e = 0; e < l.length; e++) {
              var a = l[e];
              if (a !== t && a.form === t.form) {
                var n = a[ee] || null;
                if (!n) throw Error(o(90));
                Ti(
                  a,
                  n.value,
                  n.defaultValue,
                  n.defaultValue,
                  n.checked,
                  n.defaultChecked,
                  n.type,
                  n.name
                );
              }
            }
            for (e = 0; e < l.length; e++)
              a = l[e], a.form === t.form && fs(a);
          }
          break t;
        case "textarea":
          os(t, l.value, l.defaultValue);
          break t;
        case "select":
          e = l.value, e != null && sa(t, !!l.multiple, e, !1);
      }
    }
  }
  var _i = !1;
  function ys(t, e, l) {
    if (_i) return t(e, l);
    _i = !0;
    try {
      var a = t(e);
      return a;
    } finally {
      if (_i = !1, (ra !== null || da !== null) && (ju(), ra && (e = ra, t = da, da = ra = null, ms(e), t)))
        for (e = 0; e < t.length; e++) ms(t[e]);
    }
  }
  function Ja(t, e) {
    var l = t.stateNode;
    if (l === null) return null;
    var a = l[ee] || null;
    if (a === null) return null;
    l = a[e];
    t: switch (e) {
      case "onClick":
      case "onClickCapture":
      case "onDoubleClick":
      case "onDoubleClickCapture":
      case "onMouseDown":
      case "onMouseDownCapture":
      case "onMouseMove":
      case "onMouseMoveCapture":
      case "onMouseUp":
      case "onMouseUpCapture":
      case "onMouseEnter":
        (a = !a.disabled) || (t = t.type, a = !(t === "button" || t === "input" || t === "select" || t === "textarea")), t = !a;
        break t;
      default:
        t = !1;
    }
    if (t) return null;
    if (l && typeof l != "function")
      throw Error(
        o(231, e, typeof l)
      );
    return l;
  }
  var Le = !(typeof window > "u" || typeof window.document > "u" || typeof window.document.createElement > "u"), Di = !1;
  if (Le)
    try {
      var ka = {};
      Object.defineProperty(ka, "passive", {
        get: function() {
          Di = !0;
        }
      }), window.addEventListener("test", ka, ka), window.removeEventListener("test", ka, ka);
    } catch {
      Di = !1;
    }
  var rl = null, xi = null, Wn = null;
  function vs() {
    if (Wn) return Wn;
    var t, e = xi, l = e.length, a, n = "value" in rl ? rl.value : rl.textContent, u = n.length;
    for (t = 0; t < l && e[t] === n[t]; t++) ;
    var c = l - t;
    for (a = 1; a <= c && e[l - a] === n[u - a]; a++) ;
    return Wn = n.slice(t, 1 < a ? 1 - a : void 0);
  }
  function $n(t) {
    var e = t.keyCode;
    return "charCode" in t ? (t = t.charCode, t === 0 && e === 13 && (t = 13)) : t = e, t === 10 && (t = 13), 32 <= t || t === 13 ? t : 0;
  }
  function In() {
    return !0;
  }
  function gs() {
    return !1;
  }
  function le(t) {
    function e(l, a, n, u, c) {
      this._reactName = l, this._targetInst = n, this.type = a, this.nativeEvent = u, this.target = c, this.currentTarget = null;
      for (var s in t)
        t.hasOwnProperty(s) && (l = t[s], this[s] = l ? l(u) : u[s]);
      return this.isDefaultPrevented = (u.defaultPrevented != null ? u.defaultPrevented : u.returnValue === !1) ? In : gs, this.isPropagationStopped = gs, this;
    }
    return H(e.prototype, {
      preventDefault: function() {
        this.defaultPrevented = !0;
        var l = this.nativeEvent;
        l && (l.preventDefault ? l.preventDefault() : typeof l.returnValue != "unknown" && (l.returnValue = !1), this.isDefaultPrevented = In);
      },
      stopPropagation: function() {
        var l = this.nativeEvent;
        l && (l.stopPropagation ? l.stopPropagation() : typeof l.cancelBubble != "unknown" && (l.cancelBubble = !0), this.isPropagationStopped = In);
      },
      persist: function() {
      },
      isPersistent: In
    }), e;
  }
  var Gl = {
    eventPhase: 0,
    bubbles: 0,
    cancelable: 0,
    timeStamp: function(t) {
      return t.timeStamp || Date.now();
    },
    defaultPrevented: 0,
    isTrusted: 0
  }, Pn = le(Gl), Fa = H({}, Gl, { view: 0, detail: 0 }), cm = le(Fa), Ci, Ui, Wa, tu = H({}, Fa, {
    screenX: 0,
    screenY: 0,
    clientX: 0,
    clientY: 0,
    pageX: 0,
    pageY: 0,
    ctrlKey: 0,
    shiftKey: 0,
    altKey: 0,
    metaKey: 0,
    getModifierState: Ni,
    button: 0,
    buttons: 0,
    relatedTarget: function(t) {
      return t.relatedTarget === void 0 ? t.fromElement === t.srcElement ? t.toElement : t.fromElement : t.relatedTarget;
    },
    movementX: function(t) {
      return "movementX" in t ? t.movementX : (t !== Wa && (Wa && t.type === "mousemove" ? (Ci = t.screenX - Wa.screenX, Ui = t.screenY - Wa.screenY) : Ui = Ci = 0, Wa = t), Ci);
    },
    movementY: function(t) {
      return "movementY" in t ? t.movementY : Ui;
    }
  }), bs = le(tu), fm = H({}, tu, { dataTransfer: 0 }), sm = le(fm), om = H({}, Fa, { relatedTarget: 0 }), Ri = le(om), rm = H({}, Gl, {
    animationName: 0,
    elapsedTime: 0,
    pseudoElement: 0
  }), dm = le(rm), hm = H({}, Gl, {
    clipboardData: function(t) {
      return "clipboardData" in t ? t.clipboardData : window.clipboardData;
    }
  }), mm = le(hm), ym = H({}, Gl, { data: 0 }), ps = le(ym), vm = {
    Esc: "Escape",
    Spacebar: " ",
    Left: "ArrowLeft",
    Up: "ArrowUp",
    Right: "ArrowRight",
    Down: "ArrowDown",
    Del: "Delete",
    Win: "OS",
    Menu: "ContextMenu",
    Apps: "ContextMenu",
    Scroll: "ScrollLock",
    MozPrintableKey: "Unidentified"
  }, gm = {
    8: "Backspace",
    9: "Tab",
    12: "Clear",
    13: "Enter",
    16: "Shift",
    17: "Control",
    18: "Alt",
    19: "Pause",
    20: "CapsLock",
    27: "Escape",
    32: " ",
    33: "PageUp",
    34: "PageDown",
    35: "End",
    36: "Home",
    37: "ArrowLeft",
    38: "ArrowUp",
    39: "ArrowRight",
    40: "ArrowDown",
    45: "Insert",
    46: "Delete",
    112: "F1",
    113: "F2",
    114: "F3",
    115: "F4",
    116: "F5",
    117: "F6",
    118: "F7",
    119: "F8",
    120: "F9",
    121: "F10",
    122: "F11",
    123: "F12",
    144: "NumLock",
    145: "ScrollLock",
    224: "Meta"
  }, bm = {
    Alt: "altKey",
    Control: "ctrlKey",
    Meta: "metaKey",
    Shift: "shiftKey"
  };
  function pm(t) {
    var e = this.nativeEvent;
    return e.getModifierState ? e.getModifierState(t) : (t = bm[t]) ? !!e[t] : !1;
  }
  function Ni() {
    return pm;
  }
  var Sm = H({}, Fa, {
    key: function(t) {
      if (t.key) {
        var e = vm[t.key] || t.key;
        if (e !== "Unidentified") return e;
      }
      return t.type === "keypress" ? (t = $n(t), t === 13 ? "Enter" : String.fromCharCode(t)) : t.type === "keydown" || t.type === "keyup" ? gm[t.keyCode] || "Unidentified" : "";
    },
    code: 0,
    location: 0,
    ctrlKey: 0,
    shiftKey: 0,
    altKey: 0,
    metaKey: 0,
    repeat: 0,
    locale: 0,
    getModifierState: Ni,
    charCode: function(t) {
      return t.type === "keypress" ? $n(t) : 0;
    },
    keyCode: function(t) {
      return t.type === "keydown" || t.type === "keyup" ? t.keyCode : 0;
    },
    which: function(t) {
      return t.type === "keypress" ? $n(t) : t.type === "keydown" || t.type === "keyup" ? t.keyCode : 0;
    }
  }), zm = le(Sm), Tm = H({}, tu, {
    pointerId: 0,
    width: 0,
    height: 0,
    pressure: 0,
    tangentialPressure: 0,
    tiltX: 0,
    tiltY: 0,
    twist: 0,
    pointerType: 0,
    isPrimary: 0
  }), Ss = le(Tm), Am = H({}, Fa, {
    touches: 0,
    targetTouches: 0,
    changedTouches: 0,
    altKey: 0,
    metaKey: 0,
    ctrlKey: 0,
    shiftKey: 0,
    getModifierState: Ni
  }), Em = le(Am), Om = H({}, Gl, {
    propertyName: 0,
    elapsedTime: 0,
    pseudoElement: 0
  }), Mm = le(Om), _m = H({}, tu, {
    deltaX: function(t) {
      return "deltaX" in t ? t.deltaX : "wheelDeltaX" in t ? -t.wheelDeltaX : 0;
    },
    deltaY: function(t) {
      return "deltaY" in t ? t.deltaY : "wheelDeltaY" in t ? -t.wheelDeltaY : "wheelDelta" in t ? -t.wheelDelta : 0;
    },
    deltaZ: 0,
    deltaMode: 0
  }), Dm = le(_m), xm = H({}, Gl, {
    newState: 0,
    oldState: 0
  }), Cm = le(xm), Um = [9, 13, 27, 32], Hi = Le && "CompositionEvent" in window, $a = null;
  Le && "documentMode" in document && ($a = document.documentMode);
  var Rm = Le && "TextEvent" in window && !$a, zs = Le && (!Hi || $a && 8 < $a && 11 >= $a), Ts = " ", As = !1;
  function Es(t, e) {
    switch (t) {
      case "keyup":
        return Um.indexOf(e.keyCode) !== -1;
      case "keydown":
        return e.keyCode !== 229;
      case "keypress":
      case "mousedown":
      case "focusout":
        return !0;
      default:
        return !1;
    }
  }
  function Os(t) {
    return t = t.detail, typeof t == "object" && "data" in t ? t.data : null;
  }
  var ha = !1;
  function Nm(t, e) {
    switch (t) {
      case "compositionend":
        return Os(e);
      case "keypress":
        return e.which !== 32 ? null : (As = !0, Ts);
      case "textInput":
        return t = e.data, t === Ts && As ? null : t;
      default:
        return null;
    }
  }
  function Hm(t, e) {
    if (ha)
      return t === "compositionend" || !Hi && Es(t, e) ? (t = vs(), Wn = xi = rl = null, ha = !1, t) : null;
    switch (t) {
      case "paste":
        return null;
      case "keypress":
        if (!(e.ctrlKey || e.altKey || e.metaKey) || e.ctrlKey && e.altKey) {
          if (e.char && 1 < e.char.length)
            return e.char;
          if (e.which) return String.fromCharCode(e.which);
        }
        return null;
      case "compositionend":
        return zs && e.locale !== "ko" ? null : e.data;
      default:
        return null;
    }
  }
  var qm = {
    color: !0,
    date: !0,
    datetime: !0,
    "datetime-local": !0,
    email: !0,
    month: !0,
    number: !0,
    password: !0,
    range: !0,
    search: !0,
    tel: !0,
    text: !0,
    time: !0,
    url: !0,
    week: !0
  };
  function Ms(t) {
    var e = t && t.nodeName && t.nodeName.toLowerCase();
    return e === "input" ? !!qm[t.type] : e === "textarea";
  }
  function _s(t, e, l, a) {
    ra ? da ? da.push(a) : da = [a] : ra = a, e = Zu(e, "onChange"), 0 < e.length && (l = new Pn(
      "onChange",
      "change",
      null,
      l,
      a
    ), t.push({ event: l, listeners: e }));
  }
  var Ia = null, Pa = null;
  function jm(t) {
    od(t, 0);
  }
  function eu(t) {
    var e = Ka(t);
    if (fs(e)) return t;
  }
  function Ds(t, e) {
    if (t === "change") return e;
  }
  var xs = !1;
  if (Le) {
    var qi;
    if (Le) {
      var ji = "oninput" in document;
      if (!ji) {
        var Cs = document.createElement("div");
        Cs.setAttribute("oninput", "return;"), ji = typeof Cs.oninput == "function";
      }
      qi = ji;
    } else qi = !1;
    xs = qi && (!document.documentMode || 9 < document.documentMode);
  }
  function Us() {
    Ia && (Ia.detachEvent("onpropertychange", Rs), Pa = Ia = null);
  }
  function Rs(t) {
    if (t.propertyName === "value" && eu(Pa)) {
      var e = [];
      _s(
        e,
        Pa,
        t,
        Mi(t)
      ), ys(jm, e);
    }
  }
  function Bm(t, e, l) {
    t === "focusin" ? (Us(), Ia = e, Pa = l, Ia.attachEvent("onpropertychange", Rs)) : t === "focusout" && Us();
  }
  function Qm(t) {
    if (t === "selectionchange" || t === "keyup" || t === "keydown")
      return eu(Pa);
  }
  function Gm(t, e) {
    if (t === "click") return eu(e);
  }
  function Ym(t, e) {
    if (t === "input" || t === "change")
      return eu(e);
  }
  function Xm(t, e) {
    return t === e && (t !== 0 || 1 / t === 1 / e) || t !== t && e !== e;
  }
  var he = typeof Object.is == "function" ? Object.is : Xm;
  function tn(t, e) {
    if (he(t, e)) return !0;
    if (typeof t != "object" || t === null || typeof e != "object" || e === null)
      return !1;
    var l = Object.keys(t), a = Object.keys(e);
    if (l.length !== a.length) return !1;
    for (a = 0; a < l.length; a++) {
      var n = l[a];
      if (!hi.call(e, n) || !he(t[n], e[n]))
        return !1;
    }
    return !0;
  }
  function Ns(t) {
    for (; t && t.firstChild; ) t = t.firstChild;
    return t;
  }
  function Hs(t, e) {
    var l = Ns(t);
    t = 0;
    for (var a; l; ) {
      if (l.nodeType === 3) {
        if (a = t + l.textContent.length, t <= e && a >= e)
          return { node: l, offset: e - t };
        t = a;
      }
      t: {
        for (; l; ) {
          if (l.nextSibling) {
            l = l.nextSibling;
            break t;
          }
          l = l.parentNode;
        }
        l = void 0;
      }
      l = Ns(l);
    }
  }
  function qs(t, e) {
    return t && e ? t === e ? !0 : t && t.nodeType === 3 ? !1 : e && e.nodeType === 3 ? qs(t, e.parentNode) : "contains" in t ? t.contains(e) : t.compareDocumentPosition ? !!(t.compareDocumentPosition(e) & 16) : !1 : !1;
  }
  function js(t) {
    t = t != null && t.ownerDocument != null && t.ownerDocument.defaultView != null ? t.ownerDocument.defaultView : window;
    for (var e = kn(t.document); e instanceof t.HTMLIFrameElement; ) {
      try {
        var l = typeof e.contentWindow.location.href == "string";
      } catch {
        l = !1;
      }
      if (l) t = e.contentWindow;
      else break;
      e = kn(t.document);
    }
    return e;
  }
  function Bi(t) {
    var e = t && t.nodeName && t.nodeName.toLowerCase();
    return e && (e === "input" && (t.type === "text" || t.type === "search" || t.type === "tel" || t.type === "url" || t.type === "password") || e === "textarea" || t.contentEditable === "true");
  }
  var wm = Le && "documentMode" in document && 11 >= document.documentMode, ma = null, Qi = null, en = null, Gi = !1;
  function Bs(t, e, l) {
    var a = l.window === l ? l.document : l.nodeType === 9 ? l : l.ownerDocument;
    Gi || ma == null || ma !== kn(a) || (a = ma, "selectionStart" in a && Bi(a) ? a = { start: a.selectionStart, end: a.selectionEnd } : (a = (a.ownerDocument && a.ownerDocument.defaultView || window).getSelection(), a = {
      anchorNode: a.anchorNode,
      anchorOffset: a.anchorOffset,
      focusNode: a.focusNode,
      focusOffset: a.focusOffset
    }), en && tn(en, a) || (en = a, a = Zu(Qi, "onSelect"), 0 < a.length && (e = new Pn(
      "onSelect",
      "select",
      null,
      e,
      l
    ), t.push({ event: e, listeners: a }), e.target = ma)));
  }
  function Yl(t, e) {
    var l = {};
    return l[t.toLowerCase()] = e.toLowerCase(), l["Webkit" + t] = "webkit" + e, l["Moz" + t] = "moz" + e, l;
  }
  var ya = {
    animationend: Yl("Animation", "AnimationEnd"),
    animationiteration: Yl("Animation", "AnimationIteration"),
    animationstart: Yl("Animation", "AnimationStart"),
    transitionrun: Yl("Transition", "TransitionRun"),
    transitionstart: Yl("Transition", "TransitionStart"),
    transitioncancel: Yl("Transition", "TransitionCancel"),
    transitionend: Yl("Transition", "TransitionEnd")
  }, Yi = {}, Qs = {};
  Le && (Qs = document.createElement("div").style, "AnimationEvent" in window || (delete ya.animationend.animation, delete ya.animationiteration.animation, delete ya.animationstart.animation), "TransitionEvent" in window || delete ya.transitionend.transition);
  function Xl(t) {
    if (Yi[t]) return Yi[t];
    if (!ya[t]) return t;
    var e = ya[t], l;
    for (l in e)
      if (e.hasOwnProperty(l) && l in Qs)
        return Yi[t] = e[l];
    return t;
  }
  var Gs = Xl("animationend"), Ys = Xl("animationiteration"), Xs = Xl("animationstart"), Zm = Xl("transitionrun"), Lm = Xl("transitionstart"), Vm = Xl("transitioncancel"), ws = Xl("transitionend"), Zs = /* @__PURE__ */ new Map(), Xi = "abort auxClick beforeToggle cancel canPlay canPlayThrough click close contextMenu copy cut drag dragEnd dragEnter dragExit dragLeave dragOver dragStart drop durationChange emptied encrypted ended error gotPointerCapture input invalid keyDown keyPress keyUp load loadedData loadedMetadata loadStart lostPointerCapture mouseDown mouseMove mouseOut mouseOver mouseUp paste pause play playing pointerCancel pointerDown pointerMove pointerOut pointerOver pointerUp progress rateChange reset resize seeked seeking stalled submit suspend timeUpdate touchCancel touchEnd touchStart volumeChange scroll toggle touchMove waiting wheel".split(
    " "
  );
  Xi.push("scrollEnd");
  function Ue(t, e) {
    Zs.set(t, e), Ql(e, [t]);
  }
  var lu = typeof reportError == "function" ? reportError : function(t) {
    if (typeof window == "object" && typeof window.ErrorEvent == "function") {
      var e = new window.ErrorEvent("error", {
        bubbles: !0,
        cancelable: !0,
        message: typeof t == "object" && t !== null && typeof t.message == "string" ? String(t.message) : String(t),
        error: t
      });
      if (!window.dispatchEvent(e)) return;
    } else if (typeof process == "object" && typeof process.emit == "function") {
      process.emit("uncaughtException", t);
      return;
    }
    console.error(t);
  }, Ae = [], va = 0, wi = 0;
  function au() {
    for (var t = va, e = wi = va = 0; e < t; ) {
      var l = Ae[e];
      Ae[e++] = null;
      var a = Ae[e];
      Ae[e++] = null;
      var n = Ae[e];
      Ae[e++] = null;
      var u = Ae[e];
      if (Ae[e++] = null, a !== null && n !== null) {
        var c = a.pending;
        c === null ? n.next = n : (n.next = c.next, c.next = n), a.pending = n;
      }
      u !== 0 && Ls(l, n, u);
    }
  }
  function nu(t, e, l, a) {
    Ae[va++] = t, Ae[va++] = e, Ae[va++] = l, Ae[va++] = a, wi |= a, t.lanes |= a, t = t.alternate, t !== null && (t.lanes |= a);
  }
  function Zi(t, e, l, a) {
    return nu(t, e, l, a), uu(t);
  }
  function wl(t, e) {
    return nu(t, null, null, e), uu(t);
  }
  function Ls(t, e, l) {
    t.lanes |= l;
    var a = t.alternate;
    a !== null && (a.lanes |= l);
    for (var n = !1, u = t.return; u !== null; )
      u.childLanes |= l, a = u.alternate, a !== null && (a.childLanes |= l), u.tag === 22 && (t = u.stateNode, t === null || t._visibility & 1 || (n = !0)), t = u, u = u.return;
    return t.tag === 3 ? (u = t.stateNode, n && e !== null && (n = 31 - de(l), t = u.hiddenUpdates, a = t[n], a === null ? t[n] = [e] : a.push(e), e.lane = l | 536870912), u) : null;
  }
  function uu(t) {
    if (50 < En)
      throw En = 0, Ic = null, Error(o(185));
    for (var e = t.return; e !== null; )
      t = e, e = t.return;
    return t.tag === 3 ? t.stateNode : null;
  }
  var ga = {};
  function Km(t, e, l, a) {
    this.tag = t, this.key = l, this.sibling = this.child = this.return = this.stateNode = this.type = this.elementType = null, this.index = 0, this.refCleanup = this.ref = null, this.pendingProps = e, this.dependencies = this.memoizedState = this.updateQueue = this.memoizedProps = null, this.mode = a, this.subtreeFlags = this.flags = 0, this.deletions = null, this.childLanes = this.lanes = 0, this.alternate = null;
  }
  function me(t, e, l, a) {
    return new Km(t, e, l, a);
  }
  function Li(t) {
    return t = t.prototype, !(!t || !t.isReactComponent);
  }
  function Ve(t, e) {
    var l = t.alternate;
    return l === null ? (l = me(
      t.tag,
      e,
      t.key,
      t.mode
    ), l.elementType = t.elementType, l.type = t.type, l.stateNode = t.stateNode, l.alternate = t, t.alternate = l) : (l.pendingProps = e, l.type = t.type, l.flags = 0, l.subtreeFlags = 0, l.deletions = null), l.flags = t.flags & 65011712, l.childLanes = t.childLanes, l.lanes = t.lanes, l.child = t.child, l.memoizedProps = t.memoizedProps, l.memoizedState = t.memoizedState, l.updateQueue = t.updateQueue, e = t.dependencies, l.dependencies = e === null ? null : { lanes: e.lanes, firstContext: e.firstContext }, l.sibling = t.sibling, l.index = t.index, l.ref = t.ref, l.refCleanup = t.refCleanup, l;
  }
  function Vs(t, e) {
    t.flags &= 65011714;
    var l = t.alternate;
    return l === null ? (t.childLanes = 0, t.lanes = e, t.child = null, t.subtreeFlags = 0, t.memoizedProps = null, t.memoizedState = null, t.updateQueue = null, t.dependencies = null, t.stateNode = null) : (t.childLanes = l.childLanes, t.lanes = l.lanes, t.child = l.child, t.subtreeFlags = 0, t.deletions = null, t.memoizedProps = l.memoizedProps, t.memoizedState = l.memoizedState, t.updateQueue = l.updateQueue, t.type = l.type, e = l.dependencies, t.dependencies = e === null ? null : {
      lanes: e.lanes,
      firstContext: e.firstContext
    }), t;
  }
  function iu(t, e, l, a, n, u) {
    var c = 0;
    if (a = t, typeof t == "function") Li(t) && (c = 1);
    else if (typeof t == "string")
      c = $y(
        t,
        l,
        q.current
      ) ? 26 : t === "html" || t === "head" || t === "body" ? 27 : 5;
    else
      t: switch (t) {
        case Dt:
          return t = me(31, l, e, n), t.elementType = Dt, t.lanes = u, t;
        case k:
          return Zl(l.children, n, u, e);
        case nt:
          c = 8, n |= 24;
          break;
        case ot:
          return t = me(12, l, e, n | 2), t.elementType = ot, t.lanes = u, t;
        case Ct:
          return t = me(13, l, e, n), t.elementType = Ct, t.lanes = u, t;
        case Et:
          return t = me(19, l, e, n), t.elementType = Et, t.lanes = u, t;
        default:
          if (typeof t == "object" && t !== null)
            switch (t.$$typeof) {
              case gt:
                c = 10;
                break t;
              case Nt:
                c = 9;
                break t;
              case _t:
                c = 11;
                break t;
              case I:
                c = 14;
                break t;
              case j:
                c = 16, a = null;
                break t;
            }
          c = 29, l = Error(
            o(130, t === null ? "null" : typeof t, "")
          ), a = null;
      }
    return e = me(c, l, e, n), e.elementType = t, e.type = a, e.lanes = u, e;
  }
  function Zl(t, e, l, a) {
    return t = me(7, t, a, e), t.lanes = l, t;
  }
  function Vi(t, e, l) {
    return t = me(6, t, null, e), t.lanes = l, t;
  }
  function Ks(t) {
    var e = me(18, null, null, 0);
    return e.stateNode = t, e;
  }
  function Ki(t, e, l) {
    return e = me(
      4,
      t.children !== null ? t.children : [],
      t.key,
      e
    ), e.lanes = l, e.stateNode = {
      containerInfo: t.containerInfo,
      pendingChildren: null,
      implementation: t.implementation
    }, e;
  }
  var Js = /* @__PURE__ */ new WeakMap();
  function Ee(t, e) {
    if (typeof t == "object" && t !== null) {
      var l = Js.get(t);
      return l !== void 0 ? l : (e = {
        value: t,
        source: e,
        stack: Kf(e)
      }, Js.set(t, e), e);
    }
    return {
      value: t,
      source: e,
      stack: Kf(e)
    };
  }
  var ba = [], pa = 0, cu = null, ln = 0, Oe = [], Me = 0, dl = null, je = 1, Be = "";
  function Ke(t, e) {
    ba[pa++] = ln, ba[pa++] = cu, cu = t, ln = e;
  }
  function ks(t, e, l) {
    Oe[Me++] = je, Oe[Me++] = Be, Oe[Me++] = dl, dl = t;
    var a = je;
    t = Be;
    var n = 32 - de(a) - 1;
    a &= ~(1 << n), l += 1;
    var u = 32 - de(e) + n;
    if (30 < u) {
      var c = n - n % 5;
      u = (a & (1 << c) - 1).toString(32), a >>= c, n -= c, je = 1 << 32 - de(e) + n | l << n | a, Be = u + t;
    } else
      je = 1 << u | l << n | a, Be = t;
  }
  function Ji(t) {
    t.return !== null && (Ke(t, 1), ks(t, 1, 0));
  }
  function ki(t) {
    for (; t === cu; )
      cu = ba[--pa], ba[pa] = null, ln = ba[--pa], ba[pa] = null;
    for (; t === dl; )
      dl = Oe[--Me], Oe[Me] = null, Be = Oe[--Me], Oe[Me] = null, je = Oe[--Me], Oe[Me] = null;
  }
  function Fs(t, e) {
    Oe[Me++] = je, Oe[Me++] = Be, Oe[Me++] = dl, je = e.id, Be = e.overflow, dl = t;
  }
  var kt = null, Ot = null, ft = !1, hl = null, _e = !1, Fi = Error(o(519));
  function ml(t) {
    var e = Error(
      o(
        418,
        1 < arguments.length && arguments[1] !== void 0 && arguments[1] ? "text" : "HTML",
        ""
      )
    );
    throw an(Ee(e, t)), Fi;
  }
  function Ws(t) {
    var e = t.stateNode, l = t.type, a = t.memoizedProps;
    switch (e[Jt] = t, e[ee] = a, l) {
      case "dialog":
        at("cancel", e), at("close", e);
        break;
      case "iframe":
      case "object":
      case "embed":
        at("load", e);
        break;
      case "video":
      case "audio":
        for (l = 0; l < Mn.length; l++)
          at(Mn[l], e);
        break;
      case "source":
        at("error", e);
        break;
      case "img":
      case "image":
      case "link":
        at("error", e), at("load", e);
        break;
      case "details":
        at("toggle", e);
        break;
      case "input":
        at("invalid", e), ss(
          e,
          a.value,
          a.defaultValue,
          a.checked,
          a.defaultChecked,
          a.type,
          a.name,
          !0
        );
        break;
      case "select":
        at("invalid", e);
        break;
      case "textarea":
        at("invalid", e), rs(e, a.value, a.defaultValue, a.children);
    }
    l = a.children, typeof l != "string" && typeof l != "number" && typeof l != "bigint" || e.textContent === "" + l || a.suppressHydrationWarning === !0 || md(e.textContent, l) ? (a.popover != null && (at("beforetoggle", e), at("toggle", e)), a.onScroll != null && at("scroll", e), a.onScrollEnd != null && at("scrollend", e), a.onClick != null && (e.onclick = Ze), e = !0) : e = !1, e || ml(t, !0);
  }
  function $s(t) {
    for (kt = t.return; kt; )
      switch (kt.tag) {
        case 5:
        case 31:
        case 13:
          _e = !1;
          return;
        case 27:
        case 3:
          _e = !0;
          return;
        default:
          kt = kt.return;
      }
  }
  function Sa(t) {
    if (t !== kt) return !1;
    if (!ft) return $s(t), ft = !0, !1;
    var e = t.tag, l;
    if ((l = e !== 3 && e !== 27) && ((l = e === 5) && (l = t.type, l = !(l !== "form" && l !== "button") || mf(t.type, t.memoizedProps)), l = !l), l && Ot && ml(t), $s(t), e === 13) {
      if (t = t.memoizedState, t = t !== null ? t.dehydrated : null, !t) throw Error(o(317));
      Ot = Ad(t);
    } else if (e === 31) {
      if (t = t.memoizedState, t = t !== null ? t.dehydrated : null, !t) throw Error(o(317));
      Ot = Ad(t);
    } else
      e === 27 ? (e = Ot, Dl(t.type) ? (t = pf, pf = null, Ot = t) : Ot = e) : Ot = kt ? xe(t.stateNode.nextSibling) : null;
    return !0;
  }
  function Ll() {
    Ot = kt = null, ft = !1;
  }
  function Wi() {
    var t = hl;
    return t !== null && (ie === null ? ie = t : ie.push.apply(
      ie,
      t
    ), hl = null), t;
  }
  function an(t) {
    hl === null ? hl = [t] : hl.push(t);
  }
  var $i = m(null), Vl = null, Je = null;
  function yl(t, e, l) {
    N($i, e._currentValue), e._currentValue = l;
  }
  function ke(t) {
    t._currentValue = $i.current, x($i);
  }
  function Ii(t, e, l) {
    for (; t !== null; ) {
      var a = t.alternate;
      if ((t.childLanes & e) !== e ? (t.childLanes |= e, a !== null && (a.childLanes |= e)) : a !== null && (a.childLanes & e) !== e && (a.childLanes |= e), t === l) break;
      t = t.return;
    }
  }
  function Pi(t, e, l, a) {
    var n = t.child;
    for (n !== null && (n.return = t); n !== null; ) {
      var u = n.dependencies;
      if (u !== null) {
        var c = n.child;
        u = u.firstContext;
        t: for (; u !== null; ) {
          var s = u;
          u = n;
          for (var d = 0; d < e.length; d++)
            if (s.context === e[d]) {
              u.lanes |= l, s = u.alternate, s !== null && (s.lanes |= l), Ii(
                u.return,
                l,
                t
              ), a || (c = null);
              break t;
            }
          u = s.next;
        }
      } else if (n.tag === 18) {
        if (c = n.return, c === null) throw Error(o(341));
        c.lanes |= l, u = c.alternate, u !== null && (u.lanes |= l), Ii(c, l, t), c = null;
      } else c = n.child;
      if (c !== null) c.return = n;
      else
        for (c = n; c !== null; ) {
          if (c === t) {
            c = null;
            break;
          }
          if (n = c.sibling, n !== null) {
            n.return = c.return, c = n;
            break;
          }
          c = c.return;
        }
      n = c;
    }
  }
  function za(t, e, l, a) {
    t = null;
    for (var n = e, u = !1; n !== null; ) {
      if (!u) {
        if ((n.flags & 524288) !== 0) u = !0;
        else if ((n.flags & 262144) !== 0) break;
      }
      if (n.tag === 10) {
        var c = n.alternate;
        if (c === null) throw Error(o(387));
        if (c = c.memoizedProps, c !== null) {
          var s = n.type;
          he(n.pendingProps.value, c.value) || (t !== null ? t.push(s) : t = [s]);
        }
      } else if (n === ct.current) {
        if (c = n.alternate, c === null) throw Error(o(387));
        c.memoizedState.memoizedState !== n.memoizedState.memoizedState && (t !== null ? t.push(Un) : t = [Un]);
      }
      n = n.return;
    }
    t !== null && Pi(
      e,
      t,
      l,
      a
    ), e.flags |= 262144;
  }
  function fu(t) {
    for (t = t.firstContext; t !== null; ) {
      if (!he(
        t.context._currentValue,
        t.memoizedValue
      ))
        return !0;
      t = t.next;
    }
    return !1;
  }
  function Kl(t) {
    Vl = t, Je = null, t = t.dependencies, t !== null && (t.firstContext = null);
  }
  function Ft(t) {
    return Is(Vl, t);
  }
  function su(t, e) {
    return Vl === null && Kl(t), Is(t, e);
  }
  function Is(t, e) {
    var l = e._currentValue;
    if (e = { context: e, memoizedValue: l, next: null }, Je === null) {
      if (t === null) throw Error(o(308));
      Je = e, t.dependencies = { lanes: 0, firstContext: e }, t.flags |= 524288;
    } else Je = Je.next = e;
    return l;
  }
  var Jm = typeof AbortController < "u" ? AbortController : function() {
    var t = [], e = this.signal = {
      aborted: !1,
      addEventListener: function(l, a) {
        t.push(a);
      }
    };
    this.abort = function() {
      e.aborted = !0, t.forEach(function(l) {
        return l();
      });
    };
  }, km = i.unstable_scheduleCallback, Fm = i.unstable_NormalPriority, jt = {
    $$typeof: gt,
    Consumer: null,
    Provider: null,
    _currentValue: null,
    _currentValue2: null,
    _threadCount: 0
  };
  function tc() {
    return {
      controller: new Jm(),
      data: /* @__PURE__ */ new Map(),
      refCount: 0
    };
  }
  function nn(t) {
    t.refCount--, t.refCount === 0 && km(Fm, function() {
      t.controller.abort();
    });
  }
  var un = null, ec = 0, Ta = 0, Aa = null;
  function Wm(t, e) {
    if (un === null) {
      var l = un = [];
      ec = 0, Ta = nf(), Aa = {
        status: "pending",
        value: void 0,
        then: function(a) {
          l.push(a);
        }
      };
    }
    return ec++, e.then(Ps, Ps), e;
  }
  function Ps() {
    if (--ec === 0 && un !== null) {
      Aa !== null && (Aa.status = "fulfilled");
      var t = un;
      un = null, Ta = 0, Aa = null;
      for (var e = 0; e < t.length; e++) (0, t[e])();
    }
  }
  function $m(t, e) {
    var l = [], a = {
      status: "pending",
      value: null,
      reason: null,
      then: function(n) {
        l.push(n);
      }
    };
    return t.then(
      function() {
        a.status = "fulfilled", a.value = e;
        for (var n = 0; n < l.length; n++) (0, l[n])(e);
      },
      function(n) {
        for (a.status = "rejected", a.reason = n, n = 0; n < l.length; n++)
          (0, l[n])(void 0);
      }
    ), a;
  }
  var to = T.S;
  T.S = function(t, e) {
    Qr = oe(), typeof e == "object" && e !== null && typeof e.then == "function" && Wm(t, e), to !== null && to(t, e);
  };
  var Jl = m(null);
  function lc() {
    var t = Jl.current;
    return t !== null ? t : zt.pooledCache;
  }
  function ou(t, e) {
    e === null ? N(Jl, Jl.current) : N(Jl, e.pool);
  }
  function eo() {
    var t = lc();
    return t === null ? null : { parent: jt._currentValue, pool: t };
  }
  var Ea = Error(o(460)), ac = Error(o(474)), ru = Error(o(542)), du = { then: function() {
  } };
  function lo(t) {
    return t = t.status, t === "fulfilled" || t === "rejected";
  }
  function ao(t, e, l) {
    switch (l = t[l], l === void 0 ? t.push(e) : l !== e && (e.then(Ze, Ze), e = l), e.status) {
      case "fulfilled":
        return e.value;
      case "rejected":
        throw t = e.reason, uo(t), t;
      default:
        if (typeof e.status == "string") e.then(Ze, Ze);
        else {
          if (t = zt, t !== null && 100 < t.shellSuspendCounter)
            throw Error(o(482));
          t = e, t.status = "pending", t.then(
            function(a) {
              if (e.status === "pending") {
                var n = e;
                n.status = "fulfilled", n.value = a;
              }
            },
            function(a) {
              if (e.status === "pending") {
                var n = e;
                n.status = "rejected", n.reason = a;
              }
            }
          );
        }
        switch (e.status) {
          case "fulfilled":
            return e.value;
          case "rejected":
            throw t = e.reason, uo(t), t;
        }
        throw Fl = e, Ea;
    }
  }
  function kl(t) {
    try {
      var e = t._init;
      return e(t._payload);
    } catch (l) {
      throw l !== null && typeof l == "object" && typeof l.then == "function" ? (Fl = l, Ea) : l;
    }
  }
  var Fl = null;
  function no() {
    if (Fl === null) throw Error(o(459));
    var t = Fl;
    return Fl = null, t;
  }
  function uo(t) {
    if (t === Ea || t === ru)
      throw Error(o(483));
  }
  var Oa = null, cn = 0;
  function hu(t) {
    var e = cn;
    return cn += 1, Oa === null && (Oa = []), ao(Oa, t, e);
  }
  function fn(t, e) {
    e = e.props.ref, t.ref = e !== void 0 ? e : null;
  }
  function mu(t, e) {
    throw e.$$typeof === J ? Error(o(525)) : (t = Object.prototype.toString.call(e), Error(
      o(
        31,
        t === "[object Object]" ? "object with keys {" + Object.keys(e).join(", ") + "}" : t
      )
    ));
  }
  function io(t) {
    function e(y, h) {
      if (t) {
        var v = y.deletions;
        v === null ? (y.deletions = [h], y.flags |= 16) : v.push(h);
      }
    }
    function l(y, h) {
      if (!t) return null;
      for (; h !== null; )
        e(y, h), h = h.sibling;
      return null;
    }
    function a(y) {
      for (var h = /* @__PURE__ */ new Map(); y !== null; )
        y.key !== null ? h.set(y.key, y) : h.set(y.index, y), y = y.sibling;
      return h;
    }
    function n(y, h) {
      return y = Ve(y, h), y.index = 0, y.sibling = null, y;
    }
    function u(y, h, v) {
      return y.index = v, t ? (v = y.alternate, v !== null ? (v = v.index, v < h ? (y.flags |= 67108866, h) : v) : (y.flags |= 67108866, h)) : (y.flags |= 1048576, h);
    }
    function c(y) {
      return t && y.alternate === null && (y.flags |= 67108866), y;
    }
    function s(y, h, v, M) {
      return h === null || h.tag !== 6 ? (h = Vi(v, y.mode, M), h.return = y, h) : (h = n(h, v), h.return = y, h);
    }
    function d(y, h, v, M) {
      var Z = v.type;
      return Z === k ? E(
        y,
        h,
        v.props.children,
        M,
        v.key
      ) : h !== null && (h.elementType === Z || typeof Z == "object" && Z !== null && Z.$$typeof === j && kl(Z) === h.type) ? (h = n(h, v.props), fn(h, v), h.return = y, h) : (h = iu(
        v.type,
        v.key,
        v.props,
        null,
        y.mode,
        M
      ), fn(h, v), h.return = y, h);
    }
    function g(y, h, v, M) {
      return h === null || h.tag !== 4 || h.stateNode.containerInfo !== v.containerInfo || h.stateNode.implementation !== v.implementation ? (h = Ki(v, y.mode, M), h.return = y, h) : (h = n(h, v.children || []), h.return = y, h);
    }
    function E(y, h, v, M, Z) {
      return h === null || h.tag !== 7 ? (h = Zl(
        v,
        y.mode,
        M,
        Z
      ), h.return = y, h) : (h = n(h, v), h.return = y, h);
    }
    function _(y, h, v) {
      if (typeof h == "string" && h !== "" || typeof h == "number" || typeof h == "bigint")
        return h = Vi(
          "" + h,
          y.mode,
          v
        ), h.return = y, h;
      if (typeof h == "object" && h !== null) {
        switch (h.$$typeof) {
          case st:
            return v = iu(
              h.type,
              h.key,
              h.props,
              null,
              y.mode,
              v
            ), fn(v, h), v.return = y, v;
          case $:
            return h = Ki(
              h,
              y.mode,
              v
            ), h.return = y, h;
          case j:
            return h = kl(h), _(y, h, v);
        }
        if (Zt(h) || Yt(h))
          return h = Zl(
            h,
            y.mode,
            v,
            null
          ), h.return = y, h;
        if (typeof h.then == "function")
          return _(y, hu(h), v);
        if (h.$$typeof === gt)
          return _(
            y,
            su(y, h),
            v
          );
        mu(y, h);
      }
      return null;
    }
    function b(y, h, v, M) {
      var Z = h !== null ? h.key : null;
      if (typeof v == "string" && v !== "" || typeof v == "number" || typeof v == "bigint")
        return Z !== null ? null : s(y, h, "" + v, M);
      if (typeof v == "object" && v !== null) {
        switch (v.$$typeof) {
          case st:
            return v.key === Z ? d(y, h, v, M) : null;
          case $:
            return v.key === Z ? g(y, h, v, M) : null;
          case j:
            return v = kl(v), b(y, h, v, M);
        }
        if (Zt(v) || Yt(v))
          return Z !== null ? null : E(y, h, v, M, null);
        if (typeof v.then == "function")
          return b(
            y,
            h,
            hu(v),
            M
          );
        if (v.$$typeof === gt)
          return b(
            y,
            h,
            su(y, v),
            M
          );
        mu(y, v);
      }
      return null;
    }
    function z(y, h, v, M, Z) {
      if (typeof M == "string" && M !== "" || typeof M == "number" || typeof M == "bigint")
        return y = y.get(v) || null, s(h, y, "" + M, Z);
      if (typeof M == "object" && M !== null) {
        switch (M.$$typeof) {
          case st:
            return y = y.get(
              M.key === null ? v : M.key
            ) || null, d(h, y, M, Z);
          case $:
            return y = y.get(
              M.key === null ? v : M.key
            ) || null, g(h, y, M, Z);
          case j:
            return M = kl(M), z(
              y,
              h,
              v,
              M,
              Z
            );
        }
        if (Zt(M) || Yt(M))
          return y = y.get(v) || null, E(h, y, M, Z, null);
        if (typeof M.then == "function")
          return z(
            y,
            h,
            v,
            hu(M),
            Z
          );
        if (M.$$typeof === gt)
          return z(
            y,
            h,
            v,
            su(h, M),
            Z
          );
        mu(h, M);
      }
      return null;
    }
    function B(y, h, v, M) {
      for (var Z = null, dt = null, X = h, P = h = 0, it = null; X !== null && P < v.length; P++) {
        X.index > P ? (it = X, X = null) : it = X.sibling;
        var ht = b(
          y,
          X,
          v[P],
          M
        );
        if (ht === null) {
          X === null && (X = it);
          break;
        }
        t && X && ht.alternate === null && e(y, X), h = u(ht, h, P), dt === null ? Z = ht : dt.sibling = ht, dt = ht, X = it;
      }
      if (P === v.length)
        return l(y, X), ft && Ke(y, P), Z;
      if (X === null) {
        for (; P < v.length; P++)
          X = _(y, v[P], M), X !== null && (h = u(
            X,
            h,
            P
          ), dt === null ? Z = X : dt.sibling = X, dt = X);
        return ft && Ke(y, P), Z;
      }
      for (X = a(X); P < v.length; P++)
        it = z(
          X,
          y,
          P,
          v[P],
          M
        ), it !== null && (t && it.alternate !== null && X.delete(
          it.key === null ? P : it.key
        ), h = u(
          it,
          h,
          P
        ), dt === null ? Z = it : dt.sibling = it, dt = it);
      return t && X.forEach(function(Nl) {
        return e(y, Nl);
      }), ft && Ke(y, P), Z;
    }
    function K(y, h, v, M) {
      if (v == null) throw Error(o(151));
      for (var Z = null, dt = null, X = h, P = h = 0, it = null, ht = v.next(); X !== null && !ht.done; P++, ht = v.next()) {
        X.index > P ? (it = X, X = null) : it = X.sibling;
        var Nl = b(y, X, ht.value, M);
        if (Nl === null) {
          X === null && (X = it);
          break;
        }
        t && X && Nl.alternate === null && e(y, X), h = u(Nl, h, P), dt === null ? Z = Nl : dt.sibling = Nl, dt = Nl, X = it;
      }
      if (ht.done)
        return l(y, X), ft && Ke(y, P), Z;
      if (X === null) {
        for (; !ht.done; P++, ht = v.next())
          ht = _(y, ht.value, M), ht !== null && (h = u(ht, h, P), dt === null ? Z = ht : dt.sibling = ht, dt = ht);
        return ft && Ke(y, P), Z;
      }
      for (X = a(X); !ht.done; P++, ht = v.next())
        ht = z(X, y, P, ht.value, M), ht !== null && (t && ht.alternate !== null && X.delete(ht.key === null ? P : ht.key), h = u(ht, h, P), dt === null ? Z = ht : dt.sibling = ht, dt = ht);
      return t && X.forEach(function(fv) {
        return e(y, fv);
      }), ft && Ke(y, P), Z;
    }
    function St(y, h, v, M) {
      if (typeof v == "object" && v !== null && v.type === k && v.key === null && (v = v.props.children), typeof v == "object" && v !== null) {
        switch (v.$$typeof) {
          case st:
            t: {
              for (var Z = v.key; h !== null; ) {
                if (h.key === Z) {
                  if (Z = v.type, Z === k) {
                    if (h.tag === 7) {
                      l(
                        y,
                        h.sibling
                      ), M = n(
                        h,
                        v.props.children
                      ), M.return = y, y = M;
                      break t;
                    }
                  } else if (h.elementType === Z || typeof Z == "object" && Z !== null && Z.$$typeof === j && kl(Z) === h.type) {
                    l(
                      y,
                      h.sibling
                    ), M = n(h, v.props), fn(M, v), M.return = y, y = M;
                    break t;
                  }
                  l(y, h);
                  break;
                } else e(y, h);
                h = h.sibling;
              }
              v.type === k ? (M = Zl(
                v.props.children,
                y.mode,
                M,
                v.key
              ), M.return = y, y = M) : (M = iu(
                v.type,
                v.key,
                v.props,
                null,
                y.mode,
                M
              ), fn(M, v), M.return = y, y = M);
            }
            return c(y);
          case $:
            t: {
              for (Z = v.key; h !== null; ) {
                if (h.key === Z)
                  if (h.tag === 4 && h.stateNode.containerInfo === v.containerInfo && h.stateNode.implementation === v.implementation) {
                    l(
                      y,
                      h.sibling
                    ), M = n(h, v.children || []), M.return = y, y = M;
                    break t;
                  } else {
                    l(y, h);
                    break;
                  }
                else e(y, h);
                h = h.sibling;
              }
              M = Ki(v, y.mode, M), M.return = y, y = M;
            }
            return c(y);
          case j:
            return v = kl(v), St(
              y,
              h,
              v,
              M
            );
        }
        if (Zt(v))
          return B(
            y,
            h,
            v,
            M
          );
        if (Yt(v)) {
          if (Z = Yt(v), typeof Z != "function") throw Error(o(150));
          return v = Z.call(v), K(
            y,
            h,
            v,
            M
          );
        }
        if (typeof v.then == "function")
          return St(
            y,
            h,
            hu(v),
            M
          );
        if (v.$$typeof === gt)
          return St(
            y,
            h,
            su(y, v),
            M
          );
        mu(y, v);
      }
      return typeof v == "string" && v !== "" || typeof v == "number" || typeof v == "bigint" ? (v = "" + v, h !== null && h.tag === 6 ? (l(y, h.sibling), M = n(h, v), M.return = y, y = M) : (l(y, h), M = Vi(v, y.mode, M), M.return = y, y = M), c(y)) : l(y, h);
    }
    return function(y, h, v, M) {
      try {
        cn = 0;
        var Z = St(
          y,
          h,
          v,
          M
        );
        return Oa = null, Z;
      } catch (X) {
        if (X === Ea || X === ru) throw X;
        var dt = me(29, X, null, y.mode);
        return dt.lanes = M, dt.return = y, dt;
      }
    };
  }
  var Wl = io(!0), co = io(!1), vl = !1;
  function nc(t) {
    t.updateQueue = {
      baseState: t.memoizedState,
      firstBaseUpdate: null,
      lastBaseUpdate: null,
      shared: { pending: null, lanes: 0, hiddenCallbacks: null },
      callbacks: null
    };
  }
  function uc(t, e) {
    t = t.updateQueue, e.updateQueue === t && (e.updateQueue = {
      baseState: t.baseState,
      firstBaseUpdate: t.firstBaseUpdate,
      lastBaseUpdate: t.lastBaseUpdate,
      shared: t.shared,
      callbacks: null
    });
  }
  function gl(t) {
    return { lane: t, tag: 0, payload: null, callback: null, next: null };
  }
  function bl(t, e, l) {
    var a = t.updateQueue;
    if (a === null) return null;
    if (a = a.shared, (mt & 2) !== 0) {
      var n = a.pending;
      return n === null ? e.next = e : (e.next = n.next, n.next = e), a.pending = e, e = uu(t), Ls(t, null, l), e;
    }
    return nu(t, a, e, l), uu(t);
  }
  function sn(t, e, l) {
    if (e = e.updateQueue, e !== null && (e = e.shared, (l & 4194048) !== 0)) {
      var a = e.lanes;
      a &= t.pendingLanes, l |= a, e.lanes = l, If(t, l);
    }
  }
  function ic(t, e) {
    var l = t.updateQueue, a = t.alternate;
    if (a !== null && (a = a.updateQueue, l === a)) {
      var n = null, u = null;
      if (l = l.firstBaseUpdate, l !== null) {
        do {
          var c = {
            lane: l.lane,
            tag: l.tag,
            payload: l.payload,
            callback: null,
            next: null
          };
          u === null ? n = u = c : u = u.next = c, l = l.next;
        } while (l !== null);
        u === null ? n = u = e : u = u.next = e;
      } else n = u = e;
      l = {
        baseState: a.baseState,
        firstBaseUpdate: n,
        lastBaseUpdate: u,
        shared: a.shared,
        callbacks: a.callbacks
      }, t.updateQueue = l;
      return;
    }
    t = l.lastBaseUpdate, t === null ? l.firstBaseUpdate = e : t.next = e, l.lastBaseUpdate = e;
  }
  var cc = !1;
  function on() {
    if (cc) {
      var t = Aa;
      if (t !== null) throw t;
    }
  }
  function rn(t, e, l, a) {
    cc = !1;
    var n = t.updateQueue;
    vl = !1;
    var u = n.firstBaseUpdate, c = n.lastBaseUpdate, s = n.shared.pending;
    if (s !== null) {
      n.shared.pending = null;
      var d = s, g = d.next;
      d.next = null, c === null ? u = g : c.next = g, c = d;
      var E = t.alternate;
      E !== null && (E = E.updateQueue, s = E.lastBaseUpdate, s !== c && (s === null ? E.firstBaseUpdate = g : s.next = g, E.lastBaseUpdate = d));
    }
    if (u !== null) {
      var _ = n.baseState;
      c = 0, E = g = d = null, s = u;
      do {
        var b = s.lane & -536870913, z = b !== s.lane;
        if (z ? (ut & b) === b : (a & b) === b) {
          b !== 0 && b === Ta && (cc = !0), E !== null && (E = E.next = {
            lane: 0,
            tag: s.tag,
            payload: s.payload,
            callback: null,
            next: null
          });
          t: {
            var B = t, K = s;
            b = e;
            var St = l;
            switch (K.tag) {
              case 1:
                if (B = K.payload, typeof B == "function") {
                  _ = B.call(St, _, b);
                  break t;
                }
                _ = B;
                break t;
              case 3:
                B.flags = B.flags & -65537 | 128;
              case 0:
                if (B = K.payload, b = typeof B == "function" ? B.call(St, _, b) : B, b == null) break t;
                _ = H({}, _, b);
                break t;
              case 2:
                vl = !0;
            }
          }
          b = s.callback, b !== null && (t.flags |= 64, z && (t.flags |= 8192), z = n.callbacks, z === null ? n.callbacks = [b] : z.push(b));
        } else
          z = {
            lane: b,
            tag: s.tag,
            payload: s.payload,
            callback: s.callback,
            next: null
          }, E === null ? (g = E = z, d = _) : E = E.next = z, c |= b;
        if (s = s.next, s === null) {
          if (s = n.shared.pending, s === null)
            break;
          z = s, s = z.next, z.next = null, n.lastBaseUpdate = z, n.shared.pending = null;
        }
      } while (!0);
      E === null && (d = _), n.baseState = d, n.firstBaseUpdate = g, n.lastBaseUpdate = E, u === null && (n.shared.lanes = 0), Al |= c, t.lanes = c, t.memoizedState = _;
    }
  }
  function fo(t, e) {
    if (typeof t != "function")
      throw Error(o(191, t));
    t.call(e);
  }
  function so(t, e) {
    var l = t.callbacks;
    if (l !== null)
      for (t.callbacks = null, t = 0; t < l.length; t++)
        fo(l[t], e);
  }
  var Ma = m(null), yu = m(0);
  function oo(t, e) {
    t = al, N(yu, t), N(Ma, e), al = t | e.baseLanes;
  }
  function fc() {
    N(yu, al), N(Ma, Ma.current);
  }
  function sc() {
    al = yu.current, x(Ma), x(yu);
  }
  var ye = m(null), De = null;
  function pl(t) {
    var e = t.alternate;
    N(Ht, Ht.current & 1), N(ye, t), De === null && (e === null || Ma.current !== null || e.memoizedState !== null) && (De = t);
  }
  function oc(t) {
    N(Ht, Ht.current), N(ye, t), De === null && (De = t);
  }
  function ro(t) {
    t.tag === 22 ? (N(Ht, Ht.current), N(ye, t), De === null && (De = t)) : Sl();
  }
  function Sl() {
    N(Ht, Ht.current), N(ye, ye.current);
  }
  function ve(t) {
    x(ye), De === t && (De = null), x(Ht);
  }
  var Ht = m(0);
  function vu(t) {
    for (var e = t; e !== null; ) {
      if (e.tag === 13) {
        var l = e.memoizedState;
        if (l !== null && (l = l.dehydrated, l === null || gf(l) || bf(l)))
          return e;
      } else if (e.tag === 19 && (e.memoizedProps.revealOrder === "forwards" || e.memoizedProps.revealOrder === "backwards" || e.memoizedProps.revealOrder === "unstable_legacy-backwards" || e.memoizedProps.revealOrder === "together")) {
        if ((e.flags & 128) !== 0) return e;
      } else if (e.child !== null) {
        e.child.return = e, e = e.child;
        continue;
      }
      if (e === t) break;
      for (; e.sibling === null; ) {
        if (e.return === null || e.return === t) return null;
        e = e.return;
      }
      e.sibling.return = e.return, e = e.sibling;
    }
    return null;
  }
  var Fe = 0, W = null, bt = null, Bt = null, gu = !1, _a = !1, $l = !1, bu = 0, dn = 0, Da = null, Im = 0;
  function Ut() {
    throw Error(o(321));
  }
  function rc(t, e) {
    if (e === null) return !1;
    for (var l = 0; l < e.length && l < t.length; l++)
      if (!he(t[l], e[l])) return !1;
    return !0;
  }
  function dc(t, e, l, a, n, u) {
    return Fe = u, W = e, e.memoizedState = null, e.updateQueue = null, e.lanes = 0, T.H = t === null || t.memoizedState === null ? Fo : _c, $l = !1, u = l(a, n), $l = !1, _a && (u = mo(
      e,
      l,
      a,
      n
    )), ho(t), u;
  }
  function ho(t) {
    T.H = yn;
    var e = bt !== null && bt.next !== null;
    if (Fe = 0, Bt = bt = W = null, gu = !1, dn = 0, Da = null, e) throw Error(o(300));
    t === null || Qt || (t = t.dependencies, t !== null && fu(t) && (Qt = !0));
  }
  function mo(t, e, l, a) {
    W = t;
    var n = 0;
    do {
      if (_a && (Da = null), dn = 0, _a = !1, 25 <= n) throw Error(o(301));
      if (n += 1, Bt = bt = null, t.updateQueue != null) {
        var u = t.updateQueue;
        u.lastEffect = null, u.events = null, u.stores = null, u.memoCache != null && (u.memoCache.index = 0);
      }
      T.H = Wo, u = e(l, a);
    } while (_a);
    return u;
  }
  function Pm() {
    var t = T.H, e = t.useState()[0];
    return e = typeof e.then == "function" ? hn(e) : e, t = t.useState()[0], (bt !== null ? bt.memoizedState : null) !== t && (W.flags |= 1024), e;
  }
  function hc() {
    var t = bu !== 0;
    return bu = 0, t;
  }
  function mc(t, e, l) {
    e.updateQueue = t.updateQueue, e.flags &= -2053, t.lanes &= ~l;
  }
  function yc(t) {
    if (gu) {
      for (t = t.memoizedState; t !== null; ) {
        var e = t.queue;
        e !== null && (e.pending = null), t = t.next;
      }
      gu = !1;
    }
    Fe = 0, Bt = bt = W = null, _a = !1, dn = bu = 0, Da = null;
  }
  function Pt() {
    var t = {
      memoizedState: null,
      baseState: null,
      baseQueue: null,
      queue: null,
      next: null
    };
    return Bt === null ? W.memoizedState = Bt = t : Bt = Bt.next = t, Bt;
  }
  function qt() {
    if (bt === null) {
      var t = W.alternate;
      t = t !== null ? t.memoizedState : null;
    } else t = bt.next;
    var e = Bt === null ? W.memoizedState : Bt.next;
    if (e !== null)
      Bt = e, bt = t;
    else {
      if (t === null)
        throw W.alternate === null ? Error(o(467)) : Error(o(310));
      bt = t, t = {
        memoizedState: bt.memoizedState,
        baseState: bt.baseState,
        baseQueue: bt.baseQueue,
        queue: bt.queue,
        next: null
      }, Bt === null ? W.memoizedState = Bt = t : Bt = Bt.next = t;
    }
    return Bt;
  }
  function pu() {
    return { lastEffect: null, events: null, stores: null, memoCache: null };
  }
  function hn(t) {
    var e = dn;
    return dn += 1, Da === null && (Da = []), t = ao(Da, t, e), e = W, (Bt === null ? e.memoizedState : Bt.next) === null && (e = e.alternate, T.H = e === null || e.memoizedState === null ? Fo : _c), t;
  }
  function Su(t) {
    if (t !== null && typeof t == "object") {
      if (typeof t.then == "function") return hn(t);
      if (t.$$typeof === gt) return Ft(t);
    }
    throw Error(o(438, String(t)));
  }
  function vc(t) {
    var e = null, l = W.updateQueue;
    if (l !== null && (e = l.memoCache), e == null) {
      var a = W.alternate;
      a !== null && (a = a.updateQueue, a !== null && (a = a.memoCache, a != null && (e = {
        data: a.data.map(function(n) {
          return n.slice();
        }),
        index: 0
      })));
    }
    if (e == null && (e = { data: [], index: 0 }), l === null && (l = pu(), W.updateQueue = l), l.memoCache = e, l = e.data[e.index], l === void 0)
      for (l = e.data[e.index] = Array(t), a = 0; a < t; a++)
        l[a] = Ye;
    return e.index++, l;
  }
  function We(t, e) {
    return typeof e == "function" ? e(t) : e;
  }
  function zu(t) {
    var e = qt();
    return gc(e, bt, t);
  }
  function gc(t, e, l) {
    var a = t.queue;
    if (a === null) throw Error(o(311));
    a.lastRenderedReducer = l;
    var n = t.baseQueue, u = a.pending;
    if (u !== null) {
      if (n !== null) {
        var c = n.next;
        n.next = u.next, u.next = c;
      }
      e.baseQueue = n = u, a.pending = null;
    }
    if (u = t.baseState, n === null) t.memoizedState = u;
    else {
      e = n.next;
      var s = c = null, d = null, g = e, E = !1;
      do {
        var _ = g.lane & -536870913;
        if (_ !== g.lane ? (ut & _) === _ : (Fe & _) === _) {
          var b = g.revertLane;
          if (b === 0)
            d !== null && (d = d.next = {
              lane: 0,
              revertLane: 0,
              gesture: null,
              action: g.action,
              hasEagerState: g.hasEagerState,
              eagerState: g.eagerState,
              next: null
            }), _ === Ta && (E = !0);
          else if ((Fe & b) === b) {
            g = g.next, b === Ta && (E = !0);
            continue;
          } else
            _ = {
              lane: 0,
              revertLane: g.revertLane,
              gesture: null,
              action: g.action,
              hasEagerState: g.hasEagerState,
              eagerState: g.eagerState,
              next: null
            }, d === null ? (s = d = _, c = u) : d = d.next = _, W.lanes |= b, Al |= b;
          _ = g.action, $l && l(u, _), u = g.hasEagerState ? g.eagerState : l(u, _);
        } else
          b = {
            lane: _,
            revertLane: g.revertLane,
            gesture: g.gesture,
            action: g.action,
            hasEagerState: g.hasEagerState,
            eagerState: g.eagerState,
            next: null
          }, d === null ? (s = d = b, c = u) : d = d.next = b, W.lanes |= _, Al |= _;
        g = g.next;
      } while (g !== null && g !== e);
      if (d === null ? c = u : d.next = s, !he(u, t.memoizedState) && (Qt = !0, E && (l = Aa, l !== null)))
        throw l;
      t.memoizedState = u, t.baseState = c, t.baseQueue = d, a.lastRenderedState = u;
    }
    return n === null && (a.lanes = 0), [t.memoizedState, a.dispatch];
  }
  function bc(t) {
    var e = qt(), l = e.queue;
    if (l === null) throw Error(o(311));
    l.lastRenderedReducer = t;
    var a = l.dispatch, n = l.pending, u = e.memoizedState;
    if (n !== null) {
      l.pending = null;
      var c = n = n.next;
      do
        u = t(u, c.action), c = c.next;
      while (c !== n);
      he(u, e.memoizedState) || (Qt = !0), e.memoizedState = u, e.baseQueue === null && (e.baseState = u), l.lastRenderedState = u;
    }
    return [u, a];
  }
  function yo(t, e, l) {
    var a = W, n = qt(), u = ft;
    if (u) {
      if (l === void 0) throw Error(o(407));
      l = l();
    } else l = e();
    var c = !he(
      (bt || n).memoizedState,
      l
    );
    if (c && (n.memoizedState = l, Qt = !0), n = n.queue, zc(bo.bind(null, a, n, t), [
      t
    ]), n.getSnapshot !== e || c || Bt !== null && Bt.memoizedState.tag & 1) {
      if (a.flags |= 2048, xa(
        9,
        { destroy: void 0 },
        go.bind(
          null,
          a,
          n,
          l,
          e
        ),
        null
      ), zt === null) throw Error(o(349));
      u || (Fe & 127) !== 0 || vo(a, e, l);
    }
    return l;
  }
  function vo(t, e, l) {
    t.flags |= 16384, t = { getSnapshot: e, value: l }, e = W.updateQueue, e === null ? (e = pu(), W.updateQueue = e, e.stores = [t]) : (l = e.stores, l === null ? e.stores = [t] : l.push(t));
  }
  function go(t, e, l, a) {
    e.value = l, e.getSnapshot = a, po(e) && So(t);
  }
  function bo(t, e, l) {
    return l(function() {
      po(e) && So(t);
    });
  }
  function po(t) {
    var e = t.getSnapshot;
    t = t.value;
    try {
      var l = e();
      return !he(t, l);
    } catch {
      return !0;
    }
  }
  function So(t) {
    var e = wl(t, 2);
    e !== null && ce(e, t, 2);
  }
  function pc(t) {
    var e = Pt();
    if (typeof t == "function") {
      var l = t;
      if (t = l(), $l) {
        sl(!0);
        try {
          l();
        } finally {
          sl(!1);
        }
      }
    }
    return e.memoizedState = e.baseState = t, e.queue = {
      pending: null,
      lanes: 0,
      dispatch: null,
      lastRenderedReducer: We,
      lastRenderedState: t
    }, e;
  }
  function zo(t, e, l, a) {
    return t.baseState = l, gc(
      t,
      bt,
      typeof a == "function" ? a : We
    );
  }
  function ty(t, e, l, a, n) {
    if (Eu(t)) throw Error(o(485));
    if (t = e.action, t !== null) {
      var u = {
        payload: n,
        action: t,
        next: null,
        isTransition: !0,
        status: "pending",
        value: null,
        reason: null,
        listeners: [],
        then: function(c) {
          u.listeners.push(c);
        }
      };
      T.T !== null ? l(!0) : u.isTransition = !1, a(u), l = e.pending, l === null ? (u.next = e.pending = u, To(e, u)) : (u.next = l.next, e.pending = l.next = u);
    }
  }
  function To(t, e) {
    var l = e.action, a = e.payload, n = t.state;
    if (e.isTransition) {
      var u = T.T, c = {};
      T.T = c;
      try {
        var s = l(n, a), d = T.S;
        d !== null && d(c, s), Ao(t, e, s);
      } catch (g) {
        Sc(t, e, g);
      } finally {
        u !== null && c.types !== null && (u.types = c.types), T.T = u;
      }
    } else
      try {
        u = l(n, a), Ao(t, e, u);
      } catch (g) {
        Sc(t, e, g);
      }
  }
  function Ao(t, e, l) {
    l !== null && typeof l == "object" && typeof l.then == "function" ? l.then(
      function(a) {
        Eo(t, e, a);
      },
      function(a) {
        return Sc(t, e, a);
      }
    ) : Eo(t, e, l);
  }
  function Eo(t, e, l) {
    e.status = "fulfilled", e.value = l, Oo(e), t.state = l, e = t.pending, e !== null && (l = e.next, l === e ? t.pending = null : (l = l.next, e.next = l, To(t, l)));
  }
  function Sc(t, e, l) {
    var a = t.pending;
    if (t.pending = null, a !== null) {
      a = a.next;
      do
        e.status = "rejected", e.reason = l, Oo(e), e = e.next;
      while (e !== a);
    }
    t.action = null;
  }
  function Oo(t) {
    t = t.listeners;
    for (var e = 0; e < t.length; e++) (0, t[e])();
  }
  function Mo(t, e) {
    return e;
  }
  function _o(t, e) {
    if (ft) {
      var l = zt.formState;
      if (l !== null) {
        t: {
          var a = W;
          if (ft) {
            if (Ot) {
              e: {
                for (var n = Ot, u = _e; n.nodeType !== 8; ) {
                  if (!u) {
                    n = null;
                    break e;
                  }
                  if (n = xe(
                    n.nextSibling
                  ), n === null) {
                    n = null;
                    break e;
                  }
                }
                u = n.data, n = u === "F!" || u === "F" ? n : null;
              }
              if (n) {
                Ot = xe(
                  n.nextSibling
                ), a = n.data === "F!";
                break t;
              }
            }
            ml(a);
          }
          a = !1;
        }
        a && (e = l[0]);
      }
    }
    return l = Pt(), l.memoizedState = l.baseState = e, a = {
      pending: null,
      lanes: 0,
      dispatch: null,
      lastRenderedReducer: Mo,
      lastRenderedState: e
    }, l.queue = a, l = Ko.bind(
      null,
      W,
      a
    ), a.dispatch = l, a = pc(!1), u = Mc.bind(
      null,
      W,
      !1,
      a.queue
    ), a = Pt(), n = {
      state: e,
      dispatch: null,
      action: t,
      pending: null
    }, a.queue = n, l = ty.bind(
      null,
      W,
      n,
      u,
      l
    ), n.dispatch = l, a.memoizedState = t, [e, l, !1];
  }
  function Do(t) {
    var e = qt();
    return xo(e, bt, t);
  }
  function xo(t, e, l) {
    if (e = gc(
      t,
      e,
      Mo
    )[0], t = zu(We)[0], typeof e == "object" && e !== null && typeof e.then == "function")
      try {
        var a = hn(e);
      } catch (c) {
        throw c === Ea ? ru : c;
      }
    else a = e;
    e = qt();
    var n = e.queue, u = n.dispatch;
    return l !== e.memoizedState && (W.flags |= 2048, xa(
      9,
      { destroy: void 0 },
      ey.bind(null, n, l),
      null
    )), [a, u, t];
  }
  function ey(t, e) {
    t.action = e;
  }
  function Co(t) {
    var e = qt(), l = bt;
    if (l !== null)
      return xo(e, l, t);
    qt(), e = e.memoizedState, l = qt();
    var a = l.queue.dispatch;
    return l.memoizedState = t, [e, a, !1];
  }
  function xa(t, e, l, a) {
    return t = { tag: t, create: l, deps: a, inst: e, next: null }, e = W.updateQueue, e === null && (e = pu(), W.updateQueue = e), l = e.lastEffect, l === null ? e.lastEffect = t.next = t : (a = l.next, l.next = t, t.next = a, e.lastEffect = t), t;
  }
  function Uo() {
    return qt().memoizedState;
  }
  function Tu(t, e, l, a) {
    var n = Pt();
    W.flags |= t, n.memoizedState = xa(
      1 | e,
      { destroy: void 0 },
      l,
      a === void 0 ? null : a
    );
  }
  function Au(t, e, l, a) {
    var n = qt();
    a = a === void 0 ? null : a;
    var u = n.memoizedState.inst;
    bt !== null && a !== null && rc(a, bt.memoizedState.deps) ? n.memoizedState = xa(e, u, l, a) : (W.flags |= t, n.memoizedState = xa(
      1 | e,
      u,
      l,
      a
    ));
  }
  function Ro(t, e) {
    Tu(8390656, 8, t, e);
  }
  function zc(t, e) {
    Au(2048, 8, t, e);
  }
  function ly(t) {
    W.flags |= 4;
    var e = W.updateQueue;
    if (e === null)
      e = pu(), W.updateQueue = e, e.events = [t];
    else {
      var l = e.events;
      l === null ? e.events = [t] : l.push(t);
    }
  }
  function No(t) {
    var e = qt().memoizedState;
    return ly({ ref: e, nextImpl: t }), function() {
      if ((mt & 2) !== 0) throw Error(o(440));
      return e.impl.apply(void 0, arguments);
    };
  }
  function Ho(t, e) {
    return Au(4, 2, t, e);
  }
  function qo(t, e) {
    return Au(4, 4, t, e);
  }
  function jo(t, e) {
    if (typeof e == "function") {
      t = t();
      var l = e(t);
      return function() {
        typeof l == "function" ? l() : e(null);
      };
    }
    if (e != null)
      return t = t(), e.current = t, function() {
        e.current = null;
      };
  }
  function Bo(t, e, l) {
    l = l != null ? l.concat([t]) : null, Au(4, 4, jo.bind(null, e, t), l);
  }
  function Tc() {
  }
  function Qo(t, e) {
    var l = qt();
    e = e === void 0 ? null : e;
    var a = l.memoizedState;
    return e !== null && rc(e, a[1]) ? a[0] : (l.memoizedState = [t, e], t);
  }
  function Go(t, e) {
    var l = qt();
    e = e === void 0 ? null : e;
    var a = l.memoizedState;
    if (e !== null && rc(e, a[1]))
      return a[0];
    if (a = t(), $l) {
      sl(!0);
      try {
        t();
      } finally {
        sl(!1);
      }
    }
    return l.memoizedState = [a, e], a;
  }
  function Ac(t, e, l) {
    return l === void 0 || (Fe & 1073741824) !== 0 && (ut & 261930) === 0 ? t.memoizedState = e : (t.memoizedState = l, t = Yr(), W.lanes |= t, Al |= t, l);
  }
  function Yo(t, e, l, a) {
    return he(l, e) ? l : Ma.current !== null ? (t = Ac(t, l, a), he(t, e) || (Qt = !0), t) : (Fe & 42) === 0 || (Fe & 1073741824) !== 0 && (ut & 261930) === 0 ? (Qt = !0, t.memoizedState = l) : (t = Yr(), W.lanes |= t, Al |= t, e);
  }
  function Xo(t, e, l, a, n) {
    var u = U.p;
    U.p = u !== 0 && 8 > u ? u : 8;
    var c = T.T, s = {};
    T.T = s, Mc(t, !1, e, l);
    try {
      var d = n(), g = T.S;
      if (g !== null && g(s, d), d !== null && typeof d == "object" && typeof d.then == "function") {
        var E = $m(
          d,
          a
        );
        mn(
          t,
          e,
          E,
          pe(t)
        );
      } else
        mn(
          t,
          e,
          a,
          pe(t)
        );
    } catch (_) {
      mn(
        t,
        e,
        { then: function() {
        }, status: "rejected", reason: _ },
        pe()
      );
    } finally {
      U.p = u, c !== null && s.types !== null && (c.types = s.types), T.T = c;
    }
  }
  function ay() {
  }
  function Ec(t, e, l, a) {
    if (t.tag !== 5) throw Error(o(476));
    var n = wo(t).queue;
    Xo(
      t,
      n,
      e,
      V,
      l === null ? ay : function() {
        return Zo(t), l(a);
      }
    );
  }
  function wo(t) {
    var e = t.memoizedState;
    if (e !== null) return e;
    e = {
      memoizedState: V,
      baseState: V,
      baseQueue: null,
      queue: {
        pending: null,
        lanes: 0,
        dispatch: null,
        lastRenderedReducer: We,
        lastRenderedState: V
      },
      next: null
    };
    var l = {};
    return e.next = {
      memoizedState: l,
      baseState: l,
      baseQueue: null,
      queue: {
        pending: null,
        lanes: 0,
        dispatch: null,
        lastRenderedReducer: We,
        lastRenderedState: l
      },
      next: null
    }, t.memoizedState = e, t = t.alternate, t !== null && (t.memoizedState = e), e;
  }
  function Zo(t) {
    var e = wo(t);
    e.next === null && (e = t.alternate.memoizedState), mn(
      t,
      e.next.queue,
      {},
      pe()
    );
  }
  function Oc() {
    return Ft(Un);
  }
  function Lo() {
    return qt().memoizedState;
  }
  function Vo() {
    return qt().memoizedState;
  }
  function ny(t) {
    for (var e = t.return; e !== null; ) {
      switch (e.tag) {
        case 24:
        case 3:
          var l = pe();
          t = gl(l);
          var a = bl(e, t, l);
          a !== null && (ce(a, e, l), sn(a, e, l)), e = { cache: tc() }, t.payload = e;
          return;
      }
      e = e.return;
    }
  }
  function uy(t, e, l) {
    var a = pe();
    l = {
      lane: a,
      revertLane: 0,
      gesture: null,
      action: l,
      hasEagerState: !1,
      eagerState: null,
      next: null
    }, Eu(t) ? Jo(e, l) : (l = Zi(t, e, l, a), l !== null && (ce(l, t, a), ko(l, e, a)));
  }
  function Ko(t, e, l) {
    var a = pe();
    mn(t, e, l, a);
  }
  function mn(t, e, l, a) {
    var n = {
      lane: a,
      revertLane: 0,
      gesture: null,
      action: l,
      hasEagerState: !1,
      eagerState: null,
      next: null
    };
    if (Eu(t)) Jo(e, n);
    else {
      var u = t.alternate;
      if (t.lanes === 0 && (u === null || u.lanes === 0) && (u = e.lastRenderedReducer, u !== null))
        try {
          var c = e.lastRenderedState, s = u(c, l);
          if (n.hasEagerState = !0, n.eagerState = s, he(s, c))
            return nu(t, e, n, 0), zt === null && au(), !1;
        } catch {
        }
      if (l = Zi(t, e, n, a), l !== null)
        return ce(l, t, a), ko(l, e, a), !0;
    }
    return !1;
  }
  function Mc(t, e, l, a) {
    if (a = {
      lane: 2,
      revertLane: nf(),
      gesture: null,
      action: a,
      hasEagerState: !1,
      eagerState: null,
      next: null
    }, Eu(t)) {
      if (e) throw Error(o(479));
    } else
      e = Zi(
        t,
        l,
        a,
        2
      ), e !== null && ce(e, t, 2);
  }
  function Eu(t) {
    var e = t.alternate;
    return t === W || e !== null && e === W;
  }
  function Jo(t, e) {
    _a = gu = !0;
    var l = t.pending;
    l === null ? e.next = e : (e.next = l.next, l.next = e), t.pending = e;
  }
  function ko(t, e, l) {
    if ((l & 4194048) !== 0) {
      var a = e.lanes;
      a &= t.pendingLanes, l |= a, e.lanes = l, If(t, l);
    }
  }
  var yn = {
    readContext: Ft,
    use: Su,
    useCallback: Ut,
    useContext: Ut,
    useEffect: Ut,
    useImperativeHandle: Ut,
    useLayoutEffect: Ut,
    useInsertionEffect: Ut,
    useMemo: Ut,
    useReducer: Ut,
    useRef: Ut,
    useState: Ut,
    useDebugValue: Ut,
    useDeferredValue: Ut,
    useTransition: Ut,
    useSyncExternalStore: Ut,
    useId: Ut,
    useHostTransitionStatus: Ut,
    useFormState: Ut,
    useActionState: Ut,
    useOptimistic: Ut,
    useMemoCache: Ut,
    useCacheRefresh: Ut
  };
  yn.useEffectEvent = Ut;
  var Fo = {
    readContext: Ft,
    use: Su,
    useCallback: function(t, e) {
      return Pt().memoizedState = [
        t,
        e === void 0 ? null : e
      ], t;
    },
    useContext: Ft,
    useEffect: Ro,
    useImperativeHandle: function(t, e, l) {
      l = l != null ? l.concat([t]) : null, Tu(
        4194308,
        4,
        jo.bind(null, e, t),
        l
      );
    },
    useLayoutEffect: function(t, e) {
      return Tu(4194308, 4, t, e);
    },
    useInsertionEffect: function(t, e) {
      Tu(4, 2, t, e);
    },
    useMemo: function(t, e) {
      var l = Pt();
      e = e === void 0 ? null : e;
      var a = t();
      if ($l) {
        sl(!0);
        try {
          t();
        } finally {
          sl(!1);
        }
      }
      return l.memoizedState = [a, e], a;
    },
    useReducer: function(t, e, l) {
      var a = Pt();
      if (l !== void 0) {
        var n = l(e);
        if ($l) {
          sl(!0);
          try {
            l(e);
          } finally {
            sl(!1);
          }
        }
      } else n = e;
      return a.memoizedState = a.baseState = n, t = {
        pending: null,
        lanes: 0,
        dispatch: null,
        lastRenderedReducer: t,
        lastRenderedState: n
      }, a.queue = t, t = t.dispatch = uy.bind(
        null,
        W,
        t
      ), [a.memoizedState, t];
    },
    useRef: function(t) {
      var e = Pt();
      return t = { current: t }, e.memoizedState = t;
    },
    useState: function(t) {
      t = pc(t);
      var e = t.queue, l = Ko.bind(null, W, e);
      return e.dispatch = l, [t.memoizedState, l];
    },
    useDebugValue: Tc,
    useDeferredValue: function(t, e) {
      var l = Pt();
      return Ac(l, t, e);
    },
    useTransition: function() {
      var t = pc(!1);
      return t = Xo.bind(
        null,
        W,
        t.queue,
        !0,
        !1
      ), Pt().memoizedState = t, [!1, t];
    },
    useSyncExternalStore: function(t, e, l) {
      var a = W, n = Pt();
      if (ft) {
        if (l === void 0)
          throw Error(o(407));
        l = l();
      } else {
        if (l = e(), zt === null)
          throw Error(o(349));
        (ut & 127) !== 0 || vo(a, e, l);
      }
      n.memoizedState = l;
      var u = { value: l, getSnapshot: e };
      return n.queue = u, Ro(bo.bind(null, a, u, t), [
        t
      ]), a.flags |= 2048, xa(
        9,
        { destroy: void 0 },
        go.bind(
          null,
          a,
          u,
          l,
          e
        ),
        null
      ), l;
    },
    useId: function() {
      var t = Pt(), e = zt.identifierPrefix;
      if (ft) {
        var l = Be, a = je;
        l = (a & ~(1 << 32 - de(a) - 1)).toString(32) + l, e = "_" + e + "R_" + l, l = bu++, 0 < l && (e += "H" + l.toString(32)), e += "_";
      } else
        l = Im++, e = "_" + e + "r_" + l.toString(32) + "_";
      return t.memoizedState = e;
    },
    useHostTransitionStatus: Oc,
    useFormState: _o,
    useActionState: _o,
    useOptimistic: function(t) {
      var e = Pt();
      e.memoizedState = e.baseState = t;
      var l = {
        pending: null,
        lanes: 0,
        dispatch: null,
        lastRenderedReducer: null,
        lastRenderedState: null
      };
      return e.queue = l, e = Mc.bind(
        null,
        W,
        !0,
        l
      ), l.dispatch = e, [t, e];
    },
    useMemoCache: vc,
    useCacheRefresh: function() {
      return Pt().memoizedState = ny.bind(
        null,
        W
      );
    },
    useEffectEvent: function(t) {
      var e = Pt(), l = { impl: t };
      return e.memoizedState = l, function() {
        if ((mt & 2) !== 0)
          throw Error(o(440));
        return l.impl.apply(void 0, arguments);
      };
    }
  }, _c = {
    readContext: Ft,
    use: Su,
    useCallback: Qo,
    useContext: Ft,
    useEffect: zc,
    useImperativeHandle: Bo,
    useInsertionEffect: Ho,
    useLayoutEffect: qo,
    useMemo: Go,
    useReducer: zu,
    useRef: Uo,
    useState: function() {
      return zu(We);
    },
    useDebugValue: Tc,
    useDeferredValue: function(t, e) {
      var l = qt();
      return Yo(
        l,
        bt.memoizedState,
        t,
        e
      );
    },
    useTransition: function() {
      var t = zu(We)[0], e = qt().memoizedState;
      return [
        typeof t == "boolean" ? t : hn(t),
        e
      ];
    },
    useSyncExternalStore: yo,
    useId: Lo,
    useHostTransitionStatus: Oc,
    useFormState: Do,
    useActionState: Do,
    useOptimistic: function(t, e) {
      var l = qt();
      return zo(l, bt, t, e);
    },
    useMemoCache: vc,
    useCacheRefresh: Vo
  };
  _c.useEffectEvent = No;
  var Wo = {
    readContext: Ft,
    use: Su,
    useCallback: Qo,
    useContext: Ft,
    useEffect: zc,
    useImperativeHandle: Bo,
    useInsertionEffect: Ho,
    useLayoutEffect: qo,
    useMemo: Go,
    useReducer: bc,
    useRef: Uo,
    useState: function() {
      return bc(We);
    },
    useDebugValue: Tc,
    useDeferredValue: function(t, e) {
      var l = qt();
      return bt === null ? Ac(l, t, e) : Yo(
        l,
        bt.memoizedState,
        t,
        e
      );
    },
    useTransition: function() {
      var t = bc(We)[0], e = qt().memoizedState;
      return [
        typeof t == "boolean" ? t : hn(t),
        e
      ];
    },
    useSyncExternalStore: yo,
    useId: Lo,
    useHostTransitionStatus: Oc,
    useFormState: Co,
    useActionState: Co,
    useOptimistic: function(t, e) {
      var l = qt();
      return bt !== null ? zo(l, bt, t, e) : (l.baseState = t, [t, l.queue.dispatch]);
    },
    useMemoCache: vc,
    useCacheRefresh: Vo
  };
  Wo.useEffectEvent = No;
  function Dc(t, e, l, a) {
    e = t.memoizedState, l = l(a, e), l = l == null ? e : H({}, e, l), t.memoizedState = l, t.lanes === 0 && (t.updateQueue.baseState = l);
  }
  var xc = {
    enqueueSetState: function(t, e, l) {
      t = t._reactInternals;
      var a = pe(), n = gl(a);
      n.payload = e, l != null && (n.callback = l), e = bl(t, n, a), e !== null && (ce(e, t, a), sn(e, t, a));
    },
    enqueueReplaceState: function(t, e, l) {
      t = t._reactInternals;
      var a = pe(), n = gl(a);
      n.tag = 1, n.payload = e, l != null && (n.callback = l), e = bl(t, n, a), e !== null && (ce(e, t, a), sn(e, t, a));
    },
    enqueueForceUpdate: function(t, e) {
      t = t._reactInternals;
      var l = pe(), a = gl(l);
      a.tag = 2, e != null && (a.callback = e), e = bl(t, a, l), e !== null && (ce(e, t, l), sn(e, t, l));
    }
  };
  function $o(t, e, l, a, n, u, c) {
    return t = t.stateNode, typeof t.shouldComponentUpdate == "function" ? t.shouldComponentUpdate(a, u, c) : e.prototype && e.prototype.isPureReactComponent ? !tn(l, a) || !tn(n, u) : !0;
  }
  function Io(t, e, l, a) {
    t = e.state, typeof e.componentWillReceiveProps == "function" && e.componentWillReceiveProps(l, a), typeof e.UNSAFE_componentWillReceiveProps == "function" && e.UNSAFE_componentWillReceiveProps(l, a), e.state !== t && xc.enqueueReplaceState(e, e.state, null);
  }
  function Il(t, e) {
    var l = e;
    if ("ref" in e) {
      l = {};
      for (var a in e)
        a !== "ref" && (l[a] = e[a]);
    }
    if (t = t.defaultProps) {
      l === e && (l = H({}, l));
      for (var n in t)
        l[n] === void 0 && (l[n] = t[n]);
    }
    return l;
  }
  function Po(t) {
    lu(t);
  }
  function tr(t) {
    console.error(t);
  }
  function er(t) {
    lu(t);
  }
  function Ou(t, e) {
    try {
      var l = t.onUncaughtError;
      l(e.value, { componentStack: e.stack });
    } catch (a) {
      setTimeout(function() {
        throw a;
      });
    }
  }
  function lr(t, e, l) {
    try {
      var a = t.onCaughtError;
      a(l.value, {
        componentStack: l.stack,
        errorBoundary: e.tag === 1 ? e.stateNode : null
      });
    } catch (n) {
      setTimeout(function() {
        throw n;
      });
    }
  }
  function Cc(t, e, l) {
    return l = gl(l), l.tag = 3, l.payload = { element: null }, l.callback = function() {
      Ou(t, e);
    }, l;
  }
  function ar(t) {
    return t = gl(t), t.tag = 3, t;
  }
  function nr(t, e, l, a) {
    var n = l.type.getDerivedStateFromError;
    if (typeof n == "function") {
      var u = a.value;
      t.payload = function() {
        return n(u);
      }, t.callback = function() {
        lr(e, l, a);
      };
    }
    var c = l.stateNode;
    c !== null && typeof c.componentDidCatch == "function" && (t.callback = function() {
      lr(e, l, a), typeof n != "function" && (El === null ? El = /* @__PURE__ */ new Set([this]) : El.add(this));
      var s = a.stack;
      this.componentDidCatch(a.value, {
        componentStack: s !== null ? s : ""
      });
    });
  }
  function iy(t, e, l, a, n) {
    if (l.flags |= 32768, a !== null && typeof a == "object" && typeof a.then == "function") {
      if (e = l.alternate, e !== null && za(
        e,
        l,
        n,
        !0
      ), l = ye.current, l !== null) {
        switch (l.tag) {
          case 31:
          case 13:
            return De === null ? Bu() : l.alternate === null && Rt === 0 && (Rt = 3), l.flags &= -257, l.flags |= 65536, l.lanes = n, a === du ? l.flags |= 16384 : (e = l.updateQueue, e === null ? l.updateQueue = /* @__PURE__ */ new Set([a]) : e.add(a), ef(t, a, n)), !1;
          case 22:
            return l.flags |= 65536, a === du ? l.flags |= 16384 : (e = l.updateQueue, e === null ? (e = {
              transitions: null,
              markerInstances: null,
              retryQueue: /* @__PURE__ */ new Set([a])
            }, l.updateQueue = e) : (l = e.retryQueue, l === null ? e.retryQueue = /* @__PURE__ */ new Set([a]) : l.add(a)), ef(t, a, n)), !1;
        }
        throw Error(o(435, l.tag));
      }
      return ef(t, a, n), Bu(), !1;
    }
    if (ft)
      return e = ye.current, e !== null ? ((e.flags & 65536) === 0 && (e.flags |= 256), e.flags |= 65536, e.lanes = n, a !== Fi && (t = Error(o(422), { cause: a }), an(Ee(t, l)))) : (a !== Fi && (e = Error(o(423), {
        cause: a
      }), an(
        Ee(e, l)
      )), t = t.current.alternate, t.flags |= 65536, n &= -n, t.lanes |= n, a = Ee(a, l), n = Cc(
        t.stateNode,
        a,
        n
      ), ic(t, n), Rt !== 4 && (Rt = 2)), !1;
    var u = Error(o(520), { cause: a });
    if (u = Ee(u, l), An === null ? An = [u] : An.push(u), Rt !== 4 && (Rt = 2), e === null) return !0;
    a = Ee(a, l), l = e;
    do {
      switch (l.tag) {
        case 3:
          return l.flags |= 65536, t = n & -n, l.lanes |= t, t = Cc(l.stateNode, a, t), ic(l, t), !1;
        case 1:
          if (e = l.type, u = l.stateNode, (l.flags & 128) === 0 && (typeof e.getDerivedStateFromError == "function" || u !== null && typeof u.componentDidCatch == "function" && (El === null || !El.has(u))))
            return l.flags |= 65536, n &= -n, l.lanes |= n, n = ar(n), nr(
              n,
              t,
              l,
              a
            ), ic(l, n), !1;
      }
      l = l.return;
    } while (l !== null);
    return !1;
  }
  var Uc = Error(o(461)), Qt = !1;
  function Wt(t, e, l, a) {
    e.child = t === null ? co(e, null, l, a) : Wl(
      e,
      t.child,
      l,
      a
    );
  }
  function ur(t, e, l, a, n) {
    l = l.render;
    var u = e.ref;
    if ("ref" in a) {
      var c = {};
      for (var s in a)
        s !== "ref" && (c[s] = a[s]);
    } else c = a;
    return Kl(e), a = dc(
      t,
      e,
      l,
      c,
      u,
      n
    ), s = hc(), t !== null && !Qt ? (mc(t, e, n), $e(t, e, n)) : (ft && s && Ji(e), e.flags |= 1, Wt(t, e, a, n), e.child);
  }
  function ir(t, e, l, a, n) {
    if (t === null) {
      var u = l.type;
      return typeof u == "function" && !Li(u) && u.defaultProps === void 0 && l.compare === null ? (e.tag = 15, e.type = u, cr(
        t,
        e,
        u,
        a,
        n
      )) : (t = iu(
        l.type,
        null,
        a,
        e,
        e.mode,
        n
      ), t.ref = e.ref, t.return = e, e.child = t);
    }
    if (u = t.child, !Gc(t, n)) {
      var c = u.memoizedProps;
      if (l = l.compare, l = l !== null ? l : tn, l(c, a) && t.ref === e.ref)
        return $e(t, e, n);
    }
    return e.flags |= 1, t = Ve(u, a), t.ref = e.ref, t.return = e, e.child = t;
  }
  function cr(t, e, l, a, n) {
    if (t !== null) {
      var u = t.memoizedProps;
      if (tn(u, a) && t.ref === e.ref)
        if (Qt = !1, e.pendingProps = a = u, Gc(t, n))
          (t.flags & 131072) !== 0 && (Qt = !0);
        else
          return e.lanes = t.lanes, $e(t, e, n);
    }
    return Rc(
      t,
      e,
      l,
      a,
      n
    );
  }
  function fr(t, e, l, a) {
    var n = a.children, u = t !== null ? t.memoizedState : null;
    if (t === null && e.stateNode === null && (e.stateNode = {
      _visibility: 1,
      _pendingMarkers: null,
      _retryCache: null,
      _transitions: null
    }), a.mode === "hidden") {
      if ((e.flags & 128) !== 0) {
        if (u = u !== null ? u.baseLanes | l : l, t !== null) {
          for (a = e.child = t.child, n = 0; a !== null; )
            n = n | a.lanes | a.childLanes, a = a.sibling;
          a = n & ~u;
        } else a = 0, e.child = null;
        return sr(
          t,
          e,
          u,
          l,
          a
        );
      }
      if ((l & 536870912) !== 0)
        e.memoizedState = { baseLanes: 0, cachePool: null }, t !== null && ou(
          e,
          u !== null ? u.cachePool : null
        ), u !== null ? oo(e, u) : fc(), ro(e);
      else
        return a = e.lanes = 536870912, sr(
          t,
          e,
          u !== null ? u.baseLanes | l : l,
          l,
          a
        );
    } else
      u !== null ? (ou(e, u.cachePool), oo(e, u), Sl(), e.memoizedState = null) : (t !== null && ou(e, null), fc(), Sl());
    return Wt(t, e, n, l), e.child;
  }
  function vn(t, e) {
    return t !== null && t.tag === 22 || e.stateNode !== null || (e.stateNode = {
      _visibility: 1,
      _pendingMarkers: null,
      _retryCache: null,
      _transitions: null
    }), e.sibling;
  }
  function sr(t, e, l, a, n) {
    var u = lc();
    return u = u === null ? null : { parent: jt._currentValue, pool: u }, e.memoizedState = {
      baseLanes: l,
      cachePool: u
    }, t !== null && ou(e, null), fc(), ro(e), t !== null && za(t, e, a, !0), e.childLanes = n, null;
  }
  function Mu(t, e) {
    return e = Du(
      { mode: e.mode, children: e.children },
      t.mode
    ), e.ref = t.ref, t.child = e, e.return = t, e;
  }
  function or(t, e, l) {
    return Wl(e, t.child, null, l), t = Mu(e, e.pendingProps), t.flags |= 2, ve(e), e.memoizedState = null, t;
  }
  function cy(t, e, l) {
    var a = e.pendingProps, n = (e.flags & 128) !== 0;
    if (e.flags &= -129, t === null) {
      if (ft) {
        if (a.mode === "hidden")
          return t = Mu(e, a), e.lanes = 536870912, vn(null, t);
        if (oc(e), (t = Ot) ? (t = Td(
          t,
          _e
        ), t = t !== null && t.data === "&" ? t : null, t !== null && (e.memoizedState = {
          dehydrated: t,
          treeContext: dl !== null ? { id: je, overflow: Be } : null,
          retryLane: 536870912,
          hydrationErrors: null
        }, l = Ks(t), l.return = e, e.child = l, kt = e, Ot = null)) : t = null, t === null) throw ml(e);
        return e.lanes = 536870912, null;
      }
      return Mu(e, a);
    }
    var u = t.memoizedState;
    if (u !== null) {
      var c = u.dehydrated;
      if (oc(e), n)
        if (e.flags & 256)
          e.flags &= -257, e = or(
            t,
            e,
            l
          );
        else if (e.memoizedState !== null)
          e.child = t.child, e.flags |= 128, e = null;
        else throw Error(o(558));
      else if (Qt || za(t, e, l, !1), n = (l & t.childLanes) !== 0, Qt || n) {
        if (a = zt, a !== null && (c = Pf(a, l), c !== 0 && c !== u.retryLane))
          throw u.retryLane = c, wl(t, c), ce(a, t, c), Uc;
        Bu(), e = or(
          t,
          e,
          l
        );
      } else
        t = u.treeContext, Ot = xe(c.nextSibling), kt = e, ft = !0, hl = null, _e = !1, t !== null && Fs(e, t), e = Mu(e, a), e.flags |= 4096;
      return e;
    }
    return t = Ve(t.child, {
      mode: a.mode,
      children: a.children
    }), t.ref = e.ref, e.child = t, t.return = e, t;
  }
  function _u(t, e) {
    var l = e.ref;
    if (l === null)
      t !== null && t.ref !== null && (e.flags |= 4194816);
    else {
      if (typeof l != "function" && typeof l != "object")
        throw Error(o(284));
      (t === null || t.ref !== l) && (e.flags |= 4194816);
    }
  }
  function Rc(t, e, l, a, n) {
    return Kl(e), l = dc(
      t,
      e,
      l,
      a,
      void 0,
      n
    ), a = hc(), t !== null && !Qt ? (mc(t, e, n), $e(t, e, n)) : (ft && a && Ji(e), e.flags |= 1, Wt(t, e, l, n), e.child);
  }
  function rr(t, e, l, a, n, u) {
    return Kl(e), e.updateQueue = null, l = mo(
      e,
      a,
      l,
      n
    ), ho(t), a = hc(), t !== null && !Qt ? (mc(t, e, u), $e(t, e, u)) : (ft && a && Ji(e), e.flags |= 1, Wt(t, e, l, u), e.child);
  }
  function dr(t, e, l, a, n) {
    if (Kl(e), e.stateNode === null) {
      var u = ga, c = l.contextType;
      typeof c == "object" && c !== null && (u = Ft(c)), u = new l(a, u), e.memoizedState = u.state !== null && u.state !== void 0 ? u.state : null, u.updater = xc, e.stateNode = u, u._reactInternals = e, u = e.stateNode, u.props = a, u.state = e.memoizedState, u.refs = {}, nc(e), c = l.contextType, u.context = typeof c == "object" && c !== null ? Ft(c) : ga, u.state = e.memoizedState, c = l.getDerivedStateFromProps, typeof c == "function" && (Dc(
        e,
        l,
        c,
        a
      ), u.state = e.memoizedState), typeof l.getDerivedStateFromProps == "function" || typeof u.getSnapshotBeforeUpdate == "function" || typeof u.UNSAFE_componentWillMount != "function" && typeof u.componentWillMount != "function" || (c = u.state, typeof u.componentWillMount == "function" && u.componentWillMount(), typeof u.UNSAFE_componentWillMount == "function" && u.UNSAFE_componentWillMount(), c !== u.state && xc.enqueueReplaceState(u, u.state, null), rn(e, a, u, n), on(), u.state = e.memoizedState), typeof u.componentDidMount == "function" && (e.flags |= 4194308), a = !0;
    } else if (t === null) {
      u = e.stateNode;
      var s = e.memoizedProps, d = Il(l, s);
      u.props = d;
      var g = u.context, E = l.contextType;
      c = ga, typeof E == "object" && E !== null && (c = Ft(E));
      var _ = l.getDerivedStateFromProps;
      E = typeof _ == "function" || typeof u.getSnapshotBeforeUpdate == "function", s = e.pendingProps !== s, E || typeof u.UNSAFE_componentWillReceiveProps != "function" && typeof u.componentWillReceiveProps != "function" || (s || g !== c) && Io(
        e,
        u,
        a,
        c
      ), vl = !1;
      var b = e.memoizedState;
      u.state = b, rn(e, a, u, n), on(), g = e.memoizedState, s || b !== g || vl ? (typeof _ == "function" && (Dc(
        e,
        l,
        _,
        a
      ), g = e.memoizedState), (d = vl || $o(
        e,
        l,
        d,
        a,
        b,
        g,
        c
      )) ? (E || typeof u.UNSAFE_componentWillMount != "function" && typeof u.componentWillMount != "function" || (typeof u.componentWillMount == "function" && u.componentWillMount(), typeof u.UNSAFE_componentWillMount == "function" && u.UNSAFE_componentWillMount()), typeof u.componentDidMount == "function" && (e.flags |= 4194308)) : (typeof u.componentDidMount == "function" && (e.flags |= 4194308), e.memoizedProps = a, e.memoizedState = g), u.props = a, u.state = g, u.context = c, a = d) : (typeof u.componentDidMount == "function" && (e.flags |= 4194308), a = !1);
    } else {
      u = e.stateNode, uc(t, e), c = e.memoizedProps, E = Il(l, c), u.props = E, _ = e.pendingProps, b = u.context, g = l.contextType, d = ga, typeof g == "object" && g !== null && (d = Ft(g)), s = l.getDerivedStateFromProps, (g = typeof s == "function" || typeof u.getSnapshotBeforeUpdate == "function") || typeof u.UNSAFE_componentWillReceiveProps != "function" && typeof u.componentWillReceiveProps != "function" || (c !== _ || b !== d) && Io(
        e,
        u,
        a,
        d
      ), vl = !1, b = e.memoizedState, u.state = b, rn(e, a, u, n), on();
      var z = e.memoizedState;
      c !== _ || b !== z || vl || t !== null && t.dependencies !== null && fu(t.dependencies) ? (typeof s == "function" && (Dc(
        e,
        l,
        s,
        a
      ), z = e.memoizedState), (E = vl || $o(
        e,
        l,
        E,
        a,
        b,
        z,
        d
      ) || t !== null && t.dependencies !== null && fu(t.dependencies)) ? (g || typeof u.UNSAFE_componentWillUpdate != "function" && typeof u.componentWillUpdate != "function" || (typeof u.componentWillUpdate == "function" && u.componentWillUpdate(a, z, d), typeof u.UNSAFE_componentWillUpdate == "function" && u.UNSAFE_componentWillUpdate(
        a,
        z,
        d
      )), typeof u.componentDidUpdate == "function" && (e.flags |= 4), typeof u.getSnapshotBeforeUpdate == "function" && (e.flags |= 1024)) : (typeof u.componentDidUpdate != "function" || c === t.memoizedProps && b === t.memoizedState || (e.flags |= 4), typeof u.getSnapshotBeforeUpdate != "function" || c === t.memoizedProps && b === t.memoizedState || (e.flags |= 1024), e.memoizedProps = a, e.memoizedState = z), u.props = a, u.state = z, u.context = d, a = E) : (typeof u.componentDidUpdate != "function" || c === t.memoizedProps && b === t.memoizedState || (e.flags |= 4), typeof u.getSnapshotBeforeUpdate != "function" || c === t.memoizedProps && b === t.memoizedState || (e.flags |= 1024), a = !1);
    }
    return u = a, _u(t, e), a = (e.flags & 128) !== 0, u || a ? (u = e.stateNode, l = a && typeof l.getDerivedStateFromError != "function" ? null : u.render(), e.flags |= 1, t !== null && a ? (e.child = Wl(
      e,
      t.child,
      null,
      n
    ), e.child = Wl(
      e,
      null,
      l,
      n
    )) : Wt(t, e, l, n), e.memoizedState = u.state, t = e.child) : t = $e(
      t,
      e,
      n
    ), t;
  }
  function hr(t, e, l, a) {
    return Ll(), e.flags |= 256, Wt(t, e, l, a), e.child;
  }
  var Nc = {
    dehydrated: null,
    treeContext: null,
    retryLane: 0,
    hydrationErrors: null
  };
  function Hc(t) {
    return { baseLanes: t, cachePool: eo() };
  }
  function qc(t, e, l) {
    return t = t !== null ? t.childLanes & ~l : 0, e && (t |= be), t;
  }
  function mr(t, e, l) {
    var a = e.pendingProps, n = !1, u = (e.flags & 128) !== 0, c;
    if ((c = u) || (c = t !== null && t.memoizedState === null ? !1 : (Ht.current & 2) !== 0), c && (n = !0, e.flags &= -129), c = (e.flags & 32) !== 0, e.flags &= -33, t === null) {
      if (ft) {
        if (n ? pl(e) : Sl(), (t = Ot) ? (t = Td(
          t,
          _e
        ), t = t !== null && t.data !== "&" ? t : null, t !== null && (e.memoizedState = {
          dehydrated: t,
          treeContext: dl !== null ? { id: je, overflow: Be } : null,
          retryLane: 536870912,
          hydrationErrors: null
        }, l = Ks(t), l.return = e, e.child = l, kt = e, Ot = null)) : t = null, t === null) throw ml(e);
        return bf(t) ? e.lanes = 32 : e.lanes = 536870912, null;
      }
      var s = a.children;
      return a = a.fallback, n ? (Sl(), n = e.mode, s = Du(
        { mode: "hidden", children: s },
        n
      ), a = Zl(
        a,
        n,
        l,
        null
      ), s.return = e, a.return = e, s.sibling = a, e.child = s, a = e.child, a.memoizedState = Hc(l), a.childLanes = qc(
        t,
        c,
        l
      ), e.memoizedState = Nc, vn(null, a)) : (pl(e), jc(e, s));
    }
    var d = t.memoizedState;
    if (d !== null && (s = d.dehydrated, s !== null)) {
      if (u)
        e.flags & 256 ? (pl(e), e.flags &= -257, e = Bc(
          t,
          e,
          l
        )) : e.memoizedState !== null ? (Sl(), e.child = t.child, e.flags |= 128, e = null) : (Sl(), s = a.fallback, n = e.mode, a = Du(
          { mode: "visible", children: a.children },
          n
        ), s = Zl(
          s,
          n,
          l,
          null
        ), s.flags |= 2, a.return = e, s.return = e, a.sibling = s, e.child = a, Wl(
          e,
          t.child,
          null,
          l
        ), a = e.child, a.memoizedState = Hc(l), a.childLanes = qc(
          t,
          c,
          l
        ), e.memoizedState = Nc, e = vn(null, a));
      else if (pl(e), bf(s)) {
        if (c = s.nextSibling && s.nextSibling.dataset, c) var g = c.dgst;
        c = g, a = Error(o(419)), a.stack = "", a.digest = c, an({ value: a, source: null, stack: null }), e = Bc(
          t,
          e,
          l
        );
      } else if (Qt || za(t, e, l, !1), c = (l & t.childLanes) !== 0, Qt || c) {
        if (c = zt, c !== null && (a = Pf(c, l), a !== 0 && a !== d.retryLane))
          throw d.retryLane = a, wl(t, a), ce(c, t, a), Uc;
        gf(s) || Bu(), e = Bc(
          t,
          e,
          l
        );
      } else
        gf(s) ? (e.flags |= 192, e.child = t.child, e = null) : (t = d.treeContext, Ot = xe(
          s.nextSibling
        ), kt = e, ft = !0, hl = null, _e = !1, t !== null && Fs(e, t), e = jc(
          e,
          a.children
        ), e.flags |= 4096);
      return e;
    }
    return n ? (Sl(), s = a.fallback, n = e.mode, d = t.child, g = d.sibling, a = Ve(d, {
      mode: "hidden",
      children: a.children
    }), a.subtreeFlags = d.subtreeFlags & 65011712, g !== null ? s = Ve(
      g,
      s
    ) : (s = Zl(
      s,
      n,
      l,
      null
    ), s.flags |= 2), s.return = e, a.return = e, a.sibling = s, e.child = a, vn(null, a), a = e.child, s = t.child.memoizedState, s === null ? s = Hc(l) : (n = s.cachePool, n !== null ? (d = jt._currentValue, n = n.parent !== d ? { parent: d, pool: d } : n) : n = eo(), s = {
      baseLanes: s.baseLanes | l,
      cachePool: n
    }), a.memoizedState = s, a.childLanes = qc(
      t,
      c,
      l
    ), e.memoizedState = Nc, vn(t.child, a)) : (pl(e), l = t.child, t = l.sibling, l = Ve(l, {
      mode: "visible",
      children: a.children
    }), l.return = e, l.sibling = null, t !== null && (c = e.deletions, c === null ? (e.deletions = [t], e.flags |= 16) : c.push(t)), e.child = l, e.memoizedState = null, l);
  }
  function jc(t, e) {
    return e = Du(
      { mode: "visible", children: e },
      t.mode
    ), e.return = t, t.child = e;
  }
  function Du(t, e) {
    return t = me(22, t, null, e), t.lanes = 0, t;
  }
  function Bc(t, e, l) {
    return Wl(e, t.child, null, l), t = jc(
      e,
      e.pendingProps.children
    ), t.flags |= 2, e.memoizedState = null, t;
  }
  function yr(t, e, l) {
    t.lanes |= e;
    var a = t.alternate;
    a !== null && (a.lanes |= e), Ii(t.return, e, l);
  }
  function Qc(t, e, l, a, n, u) {
    var c = t.memoizedState;
    c === null ? t.memoizedState = {
      isBackwards: e,
      rendering: null,
      renderingStartTime: 0,
      last: a,
      tail: l,
      tailMode: n,
      treeForkCount: u
    } : (c.isBackwards = e, c.rendering = null, c.renderingStartTime = 0, c.last = a, c.tail = l, c.tailMode = n, c.treeForkCount = u);
  }
  function vr(t, e, l) {
    var a = e.pendingProps, n = a.revealOrder, u = a.tail;
    a = a.children;
    var c = Ht.current, s = (c & 2) !== 0;
    if (s ? (c = c & 1 | 2, e.flags |= 128) : c &= 1, N(Ht, c), Wt(t, e, a, l), a = ft ? ln : 0, !s && t !== null && (t.flags & 128) !== 0)
      t: for (t = e.child; t !== null; ) {
        if (t.tag === 13)
          t.memoizedState !== null && yr(t, l, e);
        else if (t.tag === 19)
          yr(t, l, e);
        else if (t.child !== null) {
          t.child.return = t, t = t.child;
          continue;
        }
        if (t === e) break t;
        for (; t.sibling === null; ) {
          if (t.return === null || t.return === e)
            break t;
          t = t.return;
        }
        t.sibling.return = t.return, t = t.sibling;
      }
    switch (n) {
      case "forwards":
        for (l = e.child, n = null; l !== null; )
          t = l.alternate, t !== null && vu(t) === null && (n = l), l = l.sibling;
        l = n, l === null ? (n = e.child, e.child = null) : (n = l.sibling, l.sibling = null), Qc(
          e,
          !1,
          n,
          l,
          u,
          a
        );
        break;
      case "backwards":
      case "unstable_legacy-backwards":
        for (l = null, n = e.child, e.child = null; n !== null; ) {
          if (t = n.alternate, t !== null && vu(t) === null) {
            e.child = n;
            break;
          }
          t = n.sibling, n.sibling = l, l = n, n = t;
        }
        Qc(
          e,
          !0,
          l,
          null,
          u,
          a
        );
        break;
      case "together":
        Qc(
          e,
          !1,
          null,
          null,
          void 0,
          a
        );
        break;
      default:
        e.memoizedState = null;
    }
    return e.child;
  }
  function $e(t, e, l) {
    if (t !== null && (e.dependencies = t.dependencies), Al |= e.lanes, (l & e.childLanes) === 0)
      if (t !== null) {
        if (za(
          t,
          e,
          l,
          !1
        ), (l & e.childLanes) === 0)
          return null;
      } else return null;
    if (t !== null && e.child !== t.child)
      throw Error(o(153));
    if (e.child !== null) {
      for (t = e.child, l = Ve(t, t.pendingProps), e.child = l, l.return = e; t.sibling !== null; )
        t = t.sibling, l = l.sibling = Ve(t, t.pendingProps), l.return = e;
      l.sibling = null;
    }
    return e.child;
  }
  function Gc(t, e) {
    return (t.lanes & e) !== 0 ? !0 : (t = t.dependencies, !!(t !== null && fu(t)));
  }
  function fy(t, e, l) {
    switch (e.tag) {
      case 3:
        Lt(e, e.stateNode.containerInfo), yl(e, jt, t.memoizedState.cache), Ll();
        break;
      case 27:
      case 5:
        cl(e);
        break;
      case 4:
        Lt(e, e.stateNode.containerInfo);
        break;
      case 10:
        yl(
          e,
          e.type,
          e.memoizedProps.value
        );
        break;
      case 31:
        if (e.memoizedState !== null)
          return e.flags |= 128, oc(e), null;
        break;
      case 13:
        var a = e.memoizedState;
        if (a !== null)
          return a.dehydrated !== null ? (pl(e), e.flags |= 128, null) : (l & e.child.childLanes) !== 0 ? mr(t, e, l) : (pl(e), t = $e(
            t,
            e,
            l
          ), t !== null ? t.sibling : null);
        pl(e);
        break;
      case 19:
        var n = (t.flags & 128) !== 0;
        if (a = (l & e.childLanes) !== 0, a || (za(
          t,
          e,
          l,
          !1
        ), a = (l & e.childLanes) !== 0), n) {
          if (a)
            return vr(
              t,
              e,
              l
            );
          e.flags |= 128;
        }
        if (n = e.memoizedState, n !== null && (n.rendering = null, n.tail = null, n.lastEffect = null), N(Ht, Ht.current), a) break;
        return null;
      case 22:
        return e.lanes = 0, fr(
          t,
          e,
          l,
          e.pendingProps
        );
      case 24:
        yl(e, jt, t.memoizedState.cache);
    }
    return $e(t, e, l);
  }
  function gr(t, e, l) {
    if (t !== null)
      if (t.memoizedProps !== e.pendingProps)
        Qt = !0;
      else {
        if (!Gc(t, l) && (e.flags & 128) === 0)
          return Qt = !1, fy(
            t,
            e,
            l
          );
        Qt = (t.flags & 131072) !== 0;
      }
    else
      Qt = !1, ft && (e.flags & 1048576) !== 0 && ks(e, ln, e.index);
    switch (e.lanes = 0, e.tag) {
      case 16:
        t: {
          var a = e.pendingProps;
          if (t = kl(e.elementType), e.type = t, typeof t == "function")
            Li(t) ? (a = Il(t, a), e.tag = 1, e = dr(
              null,
              e,
              t,
              a,
              l
            )) : (e.tag = 0, e = Rc(
              null,
              e,
              t,
              a,
              l
            ));
          else {
            if (t != null) {
              var n = t.$$typeof;
              if (n === _t) {
                e.tag = 11, e = ur(
                  null,
                  e,
                  t,
                  a,
                  l
                );
                break t;
              } else if (n === I) {
                e.tag = 14, e = ir(
                  null,
                  e,
                  t,
                  a,
                  l
                );
                break t;
              }
            }
            throw e = se(t) || t, Error(o(306, e, ""));
          }
        }
        return e;
      case 0:
        return Rc(
          t,
          e,
          e.type,
          e.pendingProps,
          l
        );
      case 1:
        return a = e.type, n = Il(
          a,
          e.pendingProps
        ), dr(
          t,
          e,
          a,
          n,
          l
        );
      case 3:
        t: {
          if (Lt(
            e,
            e.stateNode.containerInfo
          ), t === null) throw Error(o(387));
          a = e.pendingProps;
          var u = e.memoizedState;
          n = u.element, uc(t, e), rn(e, a, null, l);
          var c = e.memoizedState;
          if (a = c.cache, yl(e, jt, a), a !== u.cache && Pi(
            e,
            [jt],
            l,
            !0
          ), on(), a = c.element, u.isDehydrated)
            if (u = {
              element: a,
              isDehydrated: !1,
              cache: c.cache
            }, e.updateQueue.baseState = u, e.memoizedState = u, e.flags & 256) {
              e = hr(
                t,
                e,
                a,
                l
              );
              break t;
            } else if (a !== n) {
              n = Ee(
                Error(o(424)),
                e
              ), an(n), e = hr(
                t,
                e,
                a,
                l
              );
              break t;
            } else
              for (t = e.stateNode.containerInfo, t.nodeType === 9 ? t = t.body : t = t.nodeName === "HTML" ? t.ownerDocument.body : t, Ot = xe(t.firstChild), kt = e, ft = !0, hl = null, _e = !0, l = co(
                e,
                null,
                a,
                l
              ), e.child = l; l; )
                l.flags = l.flags & -3 | 4096, l = l.sibling;
          else {
            if (Ll(), a === n) {
              e = $e(
                t,
                e,
                l
              );
              break t;
            }
            Wt(t, e, a, l);
          }
          e = e.child;
        }
        return e;
      case 26:
        return _u(t, e), t === null ? (l = Dd(
          e.type,
          null,
          e.pendingProps,
          null
        )) ? e.memoizedState = l : ft || (l = e.type, t = e.pendingProps, a = Lu(
          L.current
        ).createElement(l), a[Jt] = e, a[ee] = t, $t(a, l, t), Vt(a), e.stateNode = a) : e.memoizedState = Dd(
          e.type,
          t.memoizedProps,
          e.pendingProps,
          t.memoizedState
        ), null;
      case 27:
        return cl(e), t === null && ft && (a = e.stateNode = Od(
          e.type,
          e.pendingProps,
          L.current
        ), kt = e, _e = !0, n = Ot, Dl(e.type) ? (pf = n, Ot = xe(a.firstChild)) : Ot = n), Wt(
          t,
          e,
          e.pendingProps.children,
          l
        ), _u(t, e), t === null && (e.flags |= 4194304), e.child;
      case 5:
        return t === null && ft && ((n = a = Ot) && (a = Qy(
          a,
          e.type,
          e.pendingProps,
          _e
        ), a !== null ? (e.stateNode = a, kt = e, Ot = xe(a.firstChild), _e = !1, n = !0) : n = !1), n || ml(e)), cl(e), n = e.type, u = e.pendingProps, c = t !== null ? t.memoizedProps : null, a = u.children, mf(n, u) ? a = null : c !== null && mf(n, c) && (e.flags |= 32), e.memoizedState !== null && (n = dc(
          t,
          e,
          Pm,
          null,
          null,
          l
        ), Un._currentValue = n), _u(t, e), Wt(t, e, a, l), e.child;
      case 6:
        return t === null && ft && ((t = l = Ot) && (l = Gy(
          l,
          e.pendingProps,
          _e
        ), l !== null ? (e.stateNode = l, kt = e, Ot = null, t = !0) : t = !1), t || ml(e)), null;
      case 13:
        return mr(t, e, l);
      case 4:
        return Lt(
          e,
          e.stateNode.containerInfo
        ), a = e.pendingProps, t === null ? e.child = Wl(
          e,
          null,
          a,
          l
        ) : Wt(t, e, a, l), e.child;
      case 11:
        return ur(
          t,
          e,
          e.type,
          e.pendingProps,
          l
        );
      case 7:
        return Wt(
          t,
          e,
          e.pendingProps,
          l
        ), e.child;
      case 8:
        return Wt(
          t,
          e,
          e.pendingProps.children,
          l
        ), e.child;
      case 12:
        return Wt(
          t,
          e,
          e.pendingProps.children,
          l
        ), e.child;
      case 10:
        return a = e.pendingProps, yl(e, e.type, a.value), Wt(t, e, a.children, l), e.child;
      case 9:
        return n = e.type._context, a = e.pendingProps.children, Kl(e), n = Ft(n), a = a(n), e.flags |= 1, Wt(t, e, a, l), e.child;
      case 14:
        return ir(
          t,
          e,
          e.type,
          e.pendingProps,
          l
        );
      case 15:
        return cr(
          t,
          e,
          e.type,
          e.pendingProps,
          l
        );
      case 19:
        return vr(t, e, l);
      case 31:
        return cy(t, e, l);
      case 22:
        return fr(
          t,
          e,
          l,
          e.pendingProps
        );
      case 24:
        return Kl(e), a = Ft(jt), t === null ? (n = lc(), n === null && (n = zt, u = tc(), n.pooledCache = u, u.refCount++, u !== null && (n.pooledCacheLanes |= l), n = u), e.memoizedState = { parent: a, cache: n }, nc(e), yl(e, jt, n)) : ((t.lanes & l) !== 0 && (uc(t, e), rn(e, null, null, l), on()), n = t.memoizedState, u = e.memoizedState, n.parent !== a ? (n = { parent: a, cache: a }, e.memoizedState = n, e.lanes === 0 && (e.memoizedState = e.updateQueue.baseState = n), yl(e, jt, a)) : (a = u.cache, yl(e, jt, a), a !== n.cache && Pi(
          e,
          [jt],
          l,
          !0
        ))), Wt(
          t,
          e,
          e.pendingProps.children,
          l
        ), e.child;
      case 29:
        throw e.pendingProps;
    }
    throw Error(o(156, e.tag));
  }
  function Ie(t) {
    t.flags |= 4;
  }
  function Yc(t, e, l, a, n) {
    if ((e = (t.mode & 32) !== 0) && (e = !1), e) {
      if (t.flags |= 16777216, (n & 335544128) === n)
        if (t.stateNode.complete) t.flags |= 8192;
        else if (Lr()) t.flags |= 8192;
        else
          throw Fl = du, ac;
    } else t.flags &= -16777217;
  }
  function br(t, e) {
    if (e.type !== "stylesheet" || (e.state.loading & 4) !== 0)
      t.flags &= -16777217;
    else if (t.flags |= 16777216, !Nd(e))
      if (Lr()) t.flags |= 8192;
      else
        throw Fl = du, ac;
  }
  function xu(t, e) {
    e !== null && (t.flags |= 4), t.flags & 16384 && (e = t.tag !== 22 ? Wf() : 536870912, t.lanes |= e, Na |= e);
  }
  function gn(t, e) {
    if (!ft)
      switch (t.tailMode) {
        case "hidden":
          e = t.tail;
          for (var l = null; e !== null; )
            e.alternate !== null && (l = e), e = e.sibling;
          l === null ? t.tail = null : l.sibling = null;
          break;
        case "collapsed":
          l = t.tail;
          for (var a = null; l !== null; )
            l.alternate !== null && (a = l), l = l.sibling;
          a === null ? e || t.tail === null ? t.tail = null : t.tail.sibling = null : a.sibling = null;
      }
  }
  function Mt(t) {
    var e = t.alternate !== null && t.alternate.child === t.child, l = 0, a = 0;
    if (e)
      for (var n = t.child; n !== null; )
        l |= n.lanes | n.childLanes, a |= n.subtreeFlags & 65011712, a |= n.flags & 65011712, n.return = t, n = n.sibling;
    else
      for (n = t.child; n !== null; )
        l |= n.lanes | n.childLanes, a |= n.subtreeFlags, a |= n.flags, n.return = t, n = n.sibling;
    return t.subtreeFlags |= a, t.childLanes = l, e;
  }
  function sy(t, e, l) {
    var a = e.pendingProps;
    switch (ki(e), e.tag) {
      case 16:
      case 15:
      case 0:
      case 11:
      case 7:
      case 8:
      case 12:
      case 9:
      case 14:
        return Mt(e), null;
      case 1:
        return Mt(e), null;
      case 3:
        return l = e.stateNode, a = null, t !== null && (a = t.memoizedState.cache), e.memoizedState.cache !== a && (e.flags |= 2048), ke(jt), tt(), l.pendingContext && (l.context = l.pendingContext, l.pendingContext = null), (t === null || t.child === null) && (Sa(e) ? Ie(e) : t === null || t.memoizedState.isDehydrated && (e.flags & 256) === 0 || (e.flags |= 1024, Wi())), Mt(e), null;
      case 26:
        var n = e.type, u = e.memoizedState;
        return t === null ? (Ie(e), u !== null ? (Mt(e), br(e, u)) : (Mt(e), Yc(
          e,
          n,
          null,
          a,
          l
        ))) : u ? u !== t.memoizedState ? (Ie(e), Mt(e), br(e, u)) : (Mt(e), e.flags &= -16777217) : (t = t.memoizedProps, t !== a && Ie(e), Mt(e), Yc(
          e,
          n,
          t,
          a,
          l
        )), null;
      case 27:
        if (Xe(e), l = L.current, n = e.type, t !== null && e.stateNode != null)
          t.memoizedProps !== a && Ie(e);
        else {
          if (!a) {
            if (e.stateNode === null)
              throw Error(o(166));
            return Mt(e), null;
          }
          t = q.current, Sa(e) ? Ws(e) : (t = Od(n, a, l), e.stateNode = t, Ie(e));
        }
        return Mt(e), null;
      case 5:
        if (Xe(e), n = e.type, t !== null && e.stateNode != null)
          t.memoizedProps !== a && Ie(e);
        else {
          if (!a) {
            if (e.stateNode === null)
              throw Error(o(166));
            return Mt(e), null;
          }
          if (u = q.current, Sa(e))
            Ws(e);
          else {
            var c = Lu(
              L.current
            );
            switch (u) {
              case 1:
                u = c.createElementNS(
                  "http://www.w3.org/2000/svg",
                  n
                );
                break;
              case 2:
                u = c.createElementNS(
                  "http://www.w3.org/1998/Math/MathML",
                  n
                );
                break;
              default:
                switch (n) {
                  case "svg":
                    u = c.createElementNS(
                      "http://www.w3.org/2000/svg",
                      n
                    );
                    break;
                  case "math":
                    u = c.createElementNS(
                      "http://www.w3.org/1998/Math/MathML",
                      n
                    );
                    break;
                  case "script":
                    u = c.createElement("div"), u.innerHTML = "<script><\/script>", u = u.removeChild(
                      u.firstChild
                    );
                    break;
                  case "select":
                    u = typeof a.is == "string" ? c.createElement("select", {
                      is: a.is
                    }) : c.createElement("select"), a.multiple ? u.multiple = !0 : a.size && (u.size = a.size);
                    break;
                  default:
                    u = typeof a.is == "string" ? c.createElement(n, { is: a.is }) : c.createElement(n);
                }
            }
            u[Jt] = e, u[ee] = a;
            t: for (c = e.child; c !== null; ) {
              if (c.tag === 5 || c.tag === 6)
                u.appendChild(c.stateNode);
              else if (c.tag !== 4 && c.tag !== 27 && c.child !== null) {
                c.child.return = c, c = c.child;
                continue;
              }
              if (c === e) break t;
              for (; c.sibling === null; ) {
                if (c.return === null || c.return === e)
                  break t;
                c = c.return;
              }
              c.sibling.return = c.return, c = c.sibling;
            }
            e.stateNode = u;
            t: switch ($t(u, n, a), n) {
              case "button":
              case "input":
              case "select":
              case "textarea":
                a = !!a.autoFocus;
                break t;
              case "img":
                a = !0;
                break t;
              default:
                a = !1;
            }
            a && Ie(e);
          }
        }
        return Mt(e), Yc(
          e,
          e.type,
          t === null ? null : t.memoizedProps,
          e.pendingProps,
          l
        ), null;
      case 6:
        if (t && e.stateNode != null)
          t.memoizedProps !== a && Ie(e);
        else {
          if (typeof a != "string" && e.stateNode === null)
            throw Error(o(166));
          if (t = L.current, Sa(e)) {
            if (t = e.stateNode, l = e.memoizedProps, a = null, n = kt, n !== null)
              switch (n.tag) {
                case 27:
                case 5:
                  a = n.memoizedProps;
              }
            t[Jt] = e, t = !!(t.nodeValue === l || a !== null && a.suppressHydrationWarning === !0 || md(t.nodeValue, l)), t || ml(e, !0);
          } else
            t = Lu(t).createTextNode(
              a
            ), t[Jt] = e, e.stateNode = t;
        }
        return Mt(e), null;
      case 31:
        if (l = e.memoizedState, t === null || t.memoizedState !== null) {
          if (a = Sa(e), l !== null) {
            if (t === null) {
              if (!a) throw Error(o(318));
              if (t = e.memoizedState, t = t !== null ? t.dehydrated : null, !t) throw Error(o(557));
              t[Jt] = e;
            } else
              Ll(), (e.flags & 128) === 0 && (e.memoizedState = null), e.flags |= 4;
            Mt(e), t = !1;
          } else
            l = Wi(), t !== null && t.memoizedState !== null && (t.memoizedState.hydrationErrors = l), t = !0;
          if (!t)
            return e.flags & 256 ? (ve(e), e) : (ve(e), null);
          if ((e.flags & 128) !== 0)
            throw Error(o(558));
        }
        return Mt(e), null;
      case 13:
        if (a = e.memoizedState, t === null || t.memoizedState !== null && t.memoizedState.dehydrated !== null) {
          if (n = Sa(e), a !== null && a.dehydrated !== null) {
            if (t === null) {
              if (!n) throw Error(o(318));
              if (n = e.memoizedState, n = n !== null ? n.dehydrated : null, !n) throw Error(o(317));
              n[Jt] = e;
            } else
              Ll(), (e.flags & 128) === 0 && (e.memoizedState = null), e.flags |= 4;
            Mt(e), n = !1;
          } else
            n = Wi(), t !== null && t.memoizedState !== null && (t.memoizedState.hydrationErrors = n), n = !0;
          if (!n)
            return e.flags & 256 ? (ve(e), e) : (ve(e), null);
        }
        return ve(e), (e.flags & 128) !== 0 ? (e.lanes = l, e) : (l = a !== null, t = t !== null && t.memoizedState !== null, l && (a = e.child, n = null, a.alternate !== null && a.alternate.memoizedState !== null && a.alternate.memoizedState.cachePool !== null && (n = a.alternate.memoizedState.cachePool.pool), u = null, a.memoizedState !== null && a.memoizedState.cachePool !== null && (u = a.memoizedState.cachePool.pool), u !== n && (a.flags |= 2048)), l !== t && l && (e.child.flags |= 8192), xu(e, e.updateQueue), Mt(e), null);
      case 4:
        return tt(), t === null && sf(e.stateNode.containerInfo), Mt(e), null;
      case 10:
        return ke(e.type), Mt(e), null;
      case 19:
        if (x(Ht), a = e.memoizedState, a === null) return Mt(e), null;
        if (n = (e.flags & 128) !== 0, u = a.rendering, u === null)
          if (n) gn(a, !1);
          else {
            if (Rt !== 0 || t !== null && (t.flags & 128) !== 0)
              for (t = e.child; t !== null; ) {
                if (u = vu(t), u !== null) {
                  for (e.flags |= 128, gn(a, !1), t = u.updateQueue, e.updateQueue = t, xu(e, t), e.subtreeFlags = 0, t = l, l = e.child; l !== null; )
                    Vs(l, t), l = l.sibling;
                  return N(
                    Ht,
                    Ht.current & 1 | 2
                  ), ft && Ke(e, a.treeForkCount), e.child;
                }
                t = t.sibling;
              }
            a.tail !== null && oe() > Hu && (e.flags |= 128, n = !0, gn(a, !1), e.lanes = 4194304);
          }
        else {
          if (!n)
            if (t = vu(u), t !== null) {
              if (e.flags |= 128, n = !0, t = t.updateQueue, e.updateQueue = t, xu(e, t), gn(a, !0), a.tail === null && a.tailMode === "hidden" && !u.alternate && !ft)
                return Mt(e), null;
            } else
              2 * oe() - a.renderingStartTime > Hu && l !== 536870912 && (e.flags |= 128, n = !0, gn(a, !1), e.lanes = 4194304);
          a.isBackwards ? (u.sibling = e.child, e.child = u) : (t = a.last, t !== null ? t.sibling = u : e.child = u, a.last = u);
        }
        return a.tail !== null ? (t = a.tail, a.rendering = t, a.tail = t.sibling, a.renderingStartTime = oe(), t.sibling = null, l = Ht.current, N(
          Ht,
          n ? l & 1 | 2 : l & 1
        ), ft && Ke(e, a.treeForkCount), t) : (Mt(e), null);
      case 22:
      case 23:
        return ve(e), sc(), a = e.memoizedState !== null, t !== null ? t.memoizedState !== null !== a && (e.flags |= 8192) : a && (e.flags |= 8192), a ? (l & 536870912) !== 0 && (e.flags & 128) === 0 && (Mt(e), e.subtreeFlags & 6 && (e.flags |= 8192)) : Mt(e), l = e.updateQueue, l !== null && xu(e, l.retryQueue), l = null, t !== null && t.memoizedState !== null && t.memoizedState.cachePool !== null && (l = t.memoizedState.cachePool.pool), a = null, e.memoizedState !== null && e.memoizedState.cachePool !== null && (a = e.memoizedState.cachePool.pool), a !== l && (e.flags |= 2048), t !== null && x(Jl), null;
      case 24:
        return l = null, t !== null && (l = t.memoizedState.cache), e.memoizedState.cache !== l && (e.flags |= 2048), ke(jt), Mt(e), null;
      case 25:
        return null;
      case 30:
        return null;
    }
    throw Error(o(156, e.tag));
  }
  function oy(t, e) {
    switch (ki(e), e.tag) {
      case 1:
        return t = e.flags, t & 65536 ? (e.flags = t & -65537 | 128, e) : null;
      case 3:
        return ke(jt), tt(), t = e.flags, (t & 65536) !== 0 && (t & 128) === 0 ? (e.flags = t & -65537 | 128, e) : null;
      case 26:
      case 27:
      case 5:
        return Xe(e), null;
      case 31:
        if (e.memoizedState !== null) {
          if (ve(e), e.alternate === null)
            throw Error(o(340));
          Ll();
        }
        return t = e.flags, t & 65536 ? (e.flags = t & -65537 | 128, e) : null;
      case 13:
        if (ve(e), t = e.memoizedState, t !== null && t.dehydrated !== null) {
          if (e.alternate === null)
            throw Error(o(340));
          Ll();
        }
        return t = e.flags, t & 65536 ? (e.flags = t & -65537 | 128, e) : null;
      case 19:
        return x(Ht), null;
      case 4:
        return tt(), null;
      case 10:
        return ke(e.type), null;
      case 22:
      case 23:
        return ve(e), sc(), t !== null && x(Jl), t = e.flags, t & 65536 ? (e.flags = t & -65537 | 128, e) : null;
      case 24:
        return ke(jt), null;
      case 25:
        return null;
      default:
        return null;
    }
  }
  function pr(t, e) {
    switch (ki(e), e.tag) {
      case 3:
        ke(jt), tt();
        break;
      case 26:
      case 27:
      case 5:
        Xe(e);
        break;
      case 4:
        tt();
        break;
      case 31:
        e.memoizedState !== null && ve(e);
        break;
      case 13:
        ve(e);
        break;
      case 19:
        x(Ht);
        break;
      case 10:
        ke(e.type);
        break;
      case 22:
      case 23:
        ve(e), sc(), t !== null && x(Jl);
        break;
      case 24:
        ke(jt);
    }
  }
  function bn(t, e) {
    try {
      var l = e.updateQueue, a = l !== null ? l.lastEffect : null;
      if (a !== null) {
        var n = a.next;
        l = n;
        do {
          if ((l.tag & t) === t) {
            a = void 0;
            var u = l.create, c = l.inst;
            a = u(), c.destroy = a;
          }
          l = l.next;
        } while (l !== n);
      }
    } catch (s) {
      vt(e, e.return, s);
    }
  }
  function zl(t, e, l) {
    try {
      var a = e.updateQueue, n = a !== null ? a.lastEffect : null;
      if (n !== null) {
        var u = n.next;
        a = u;
        do {
          if ((a.tag & t) === t) {
            var c = a.inst, s = c.destroy;
            if (s !== void 0) {
              c.destroy = void 0, n = e;
              var d = l, g = s;
              try {
                g();
              } catch (E) {
                vt(
                  n,
                  d,
                  E
                );
              }
            }
          }
          a = a.next;
        } while (a !== u);
      }
    } catch (E) {
      vt(e, e.return, E);
    }
  }
  function Sr(t) {
    var e = t.updateQueue;
    if (e !== null) {
      var l = t.stateNode;
      try {
        so(e, l);
      } catch (a) {
        vt(t, t.return, a);
      }
    }
  }
  function zr(t, e, l) {
    l.props = Il(
      t.type,
      t.memoizedProps
    ), l.state = t.memoizedState;
    try {
      l.componentWillUnmount();
    } catch (a) {
      vt(t, e, a);
    }
  }
  function pn(t, e) {
    try {
      var l = t.ref;
      if (l !== null) {
        switch (t.tag) {
          case 26:
          case 27:
          case 5:
            var a = t.stateNode;
            break;
          case 30:
            a = t.stateNode;
            break;
          default:
            a = t.stateNode;
        }
        typeof l == "function" ? t.refCleanup = l(a) : l.current = a;
      }
    } catch (n) {
      vt(t, e, n);
    }
  }
  function Qe(t, e) {
    var l = t.ref, a = t.refCleanup;
    if (l !== null)
      if (typeof a == "function")
        try {
          a();
        } catch (n) {
          vt(t, e, n);
        } finally {
          t.refCleanup = null, t = t.alternate, t != null && (t.refCleanup = null);
        }
      else if (typeof l == "function")
        try {
          l(null);
        } catch (n) {
          vt(t, e, n);
        }
      else l.current = null;
  }
  function Tr(t) {
    var e = t.type, l = t.memoizedProps, a = t.stateNode;
    try {
      t: switch (e) {
        case "button":
        case "input":
        case "select":
        case "textarea":
          l.autoFocus && a.focus();
          break t;
        case "img":
          l.src ? a.src = l.src : l.srcSet && (a.srcset = l.srcSet);
      }
    } catch (n) {
      vt(t, t.return, n);
    }
  }
  function Xc(t, e, l) {
    try {
      var a = t.stateNode;
      Ry(a, t.type, l, e), a[ee] = e;
    } catch (n) {
      vt(t, t.return, n);
    }
  }
  function Ar(t) {
    return t.tag === 5 || t.tag === 3 || t.tag === 26 || t.tag === 27 && Dl(t.type) || t.tag === 4;
  }
  function wc(t) {
    t: for (; ; ) {
      for (; t.sibling === null; ) {
        if (t.return === null || Ar(t.return)) return null;
        t = t.return;
      }
      for (t.sibling.return = t.return, t = t.sibling; t.tag !== 5 && t.tag !== 6 && t.tag !== 18; ) {
        if (t.tag === 27 && Dl(t.type) || t.flags & 2 || t.child === null || t.tag === 4) continue t;
        t.child.return = t, t = t.child;
      }
      if (!(t.flags & 2)) return t.stateNode;
    }
  }
  function Zc(t, e, l) {
    var a = t.tag;
    if (a === 5 || a === 6)
      t = t.stateNode, e ? (l.nodeType === 9 ? l.body : l.nodeName === "HTML" ? l.ownerDocument.body : l).insertBefore(t, e) : (e = l.nodeType === 9 ? l.body : l.nodeName === "HTML" ? l.ownerDocument.body : l, e.appendChild(t), l = l._reactRootContainer, l != null || e.onclick !== null || (e.onclick = Ze));
    else if (a !== 4 && (a === 27 && Dl(t.type) && (l = t.stateNode, e = null), t = t.child, t !== null))
      for (Zc(t, e, l), t = t.sibling; t !== null; )
        Zc(t, e, l), t = t.sibling;
  }
  function Cu(t, e, l) {
    var a = t.tag;
    if (a === 5 || a === 6)
      t = t.stateNode, e ? l.insertBefore(t, e) : l.appendChild(t);
    else if (a !== 4 && (a === 27 && Dl(t.type) && (l = t.stateNode), t = t.child, t !== null))
      for (Cu(t, e, l), t = t.sibling; t !== null; )
        Cu(t, e, l), t = t.sibling;
  }
  function Er(t) {
    var e = t.stateNode, l = t.memoizedProps;
    try {
      for (var a = t.type, n = e.attributes; n.length; )
        e.removeAttributeNode(n[0]);
      $t(e, a, l), e[Jt] = t, e[ee] = l;
    } catch (u) {
      vt(t, t.return, u);
    }
  }
  var Pe = !1, Gt = !1, Lc = !1, Or = typeof WeakSet == "function" ? WeakSet : Set, Kt = null;
  function ry(t, e) {
    if (t = t.containerInfo, df = $u, t = js(t), Bi(t)) {
      if ("selectionStart" in t)
        var l = {
          start: t.selectionStart,
          end: t.selectionEnd
        };
      else
        t: {
          l = (l = t.ownerDocument) && l.defaultView || window;
          var a = l.getSelection && l.getSelection();
          if (a && a.rangeCount !== 0) {
            l = a.anchorNode;
            var n = a.anchorOffset, u = a.focusNode;
            a = a.focusOffset;
            try {
              l.nodeType, u.nodeType;
            } catch {
              l = null;
              break t;
            }
            var c = 0, s = -1, d = -1, g = 0, E = 0, _ = t, b = null;
            e: for (; ; ) {
              for (var z; _ !== l || n !== 0 && _.nodeType !== 3 || (s = c + n), _ !== u || a !== 0 && _.nodeType !== 3 || (d = c + a), _.nodeType === 3 && (c += _.nodeValue.length), (z = _.firstChild) !== null; )
                b = _, _ = z;
              for (; ; ) {
                if (_ === t) break e;
                if (b === l && ++g === n && (s = c), b === u && ++E === a && (d = c), (z = _.nextSibling) !== null) break;
                _ = b, b = _.parentNode;
              }
              _ = z;
            }
            l = s === -1 || d === -1 ? null : { start: s, end: d };
          } else l = null;
        }
      l = l || { start: 0, end: 0 };
    } else l = null;
    for (hf = { focusedElem: t, selectionRange: l }, $u = !1, Kt = e; Kt !== null; )
      if (e = Kt, t = e.child, (e.subtreeFlags & 1028) !== 0 && t !== null)
        t.return = e, Kt = t;
      else
        for (; Kt !== null; ) {
          switch (e = Kt, u = e.alternate, t = e.flags, e.tag) {
            case 0:
              if ((t & 4) !== 0 && (t = e.updateQueue, t = t !== null ? t.events : null, t !== null))
                for (l = 0; l < t.length; l++)
                  n = t[l], n.ref.impl = n.nextImpl;
              break;
            case 11:
            case 15:
              break;
            case 1:
              if ((t & 1024) !== 0 && u !== null) {
                t = void 0, l = e, n = u.memoizedProps, u = u.memoizedState, a = l.stateNode;
                try {
                  var B = Il(
                    l.type,
                    n
                  );
                  t = a.getSnapshotBeforeUpdate(
                    B,
                    u
                  ), a.__reactInternalSnapshotBeforeUpdate = t;
                } catch (K) {
                  vt(
                    l,
                    l.return,
                    K
                  );
                }
              }
              break;
            case 3:
              if ((t & 1024) !== 0) {
                if (t = e.stateNode.containerInfo, l = t.nodeType, l === 9)
                  vf(t);
                else if (l === 1)
                  switch (t.nodeName) {
                    case "HEAD":
                    case "HTML":
                    case "BODY":
                      vf(t);
                      break;
                    default:
                      t.textContent = "";
                  }
              }
              break;
            case 5:
            case 26:
            case 27:
            case 6:
            case 4:
            case 17:
              break;
            default:
              if ((t & 1024) !== 0) throw Error(o(163));
          }
          if (t = e.sibling, t !== null) {
            t.return = e.return, Kt = t;
            break;
          }
          Kt = e.return;
        }
  }
  function Mr(t, e, l) {
    var a = l.flags;
    switch (l.tag) {
      case 0:
      case 11:
      case 15:
        el(t, l), a & 4 && bn(5, l);
        break;
      case 1:
        if (el(t, l), a & 4)
          if (t = l.stateNode, e === null)
            try {
              t.componentDidMount();
            } catch (c) {
              vt(l, l.return, c);
            }
          else {
            var n = Il(
              l.type,
              e.memoizedProps
            );
            e = e.memoizedState;
            try {
              t.componentDidUpdate(
                n,
                e,
                t.__reactInternalSnapshotBeforeUpdate
              );
            } catch (c) {
              vt(
                l,
                l.return,
                c
              );
            }
          }
        a & 64 && Sr(l), a & 512 && pn(l, l.return);
        break;
      case 3:
        if (el(t, l), a & 64 && (t = l.updateQueue, t !== null)) {
          if (e = null, l.child !== null)
            switch (l.child.tag) {
              case 27:
              case 5:
                e = l.child.stateNode;
                break;
              case 1:
                e = l.child.stateNode;
            }
          try {
            so(t, e);
          } catch (c) {
            vt(l, l.return, c);
          }
        }
        break;
      case 27:
        e === null && a & 4 && Er(l);
      case 26:
      case 5:
        el(t, l), e === null && a & 4 && Tr(l), a & 512 && pn(l, l.return);
        break;
      case 12:
        el(t, l);
        break;
      case 31:
        el(t, l), a & 4 && xr(t, l);
        break;
      case 13:
        el(t, l), a & 4 && Cr(t, l), a & 64 && (t = l.memoizedState, t !== null && (t = t.dehydrated, t !== null && (l = Sy.bind(
          null,
          l
        ), Yy(t, l))));
        break;
      case 22:
        if (a = l.memoizedState !== null || Pe, !a) {
          e = e !== null && e.memoizedState !== null || Gt, n = Pe;
          var u = Gt;
          Pe = a, (Gt = e) && !u ? ll(
            t,
            l,
            (l.subtreeFlags & 8772) !== 0
          ) : el(t, l), Pe = n, Gt = u;
        }
        break;
      case 30:
        break;
      default:
        el(t, l);
    }
  }
  function _r(t) {
    var e = t.alternate;
    e !== null && (t.alternate = null, _r(e)), t.child = null, t.deletions = null, t.sibling = null, t.tag === 5 && (e = t.stateNode, e !== null && Si(e)), t.stateNode = null, t.return = null, t.dependencies = null, t.memoizedProps = null, t.memoizedState = null, t.pendingProps = null, t.stateNode = null, t.updateQueue = null;
  }
  var xt = null, ae = !1;
  function tl(t, e, l) {
    for (l = l.child; l !== null; )
      Dr(t, e, l), l = l.sibling;
  }
  function Dr(t, e, l) {
    if (re && typeof re.onCommitFiberUnmount == "function")
      try {
        re.onCommitFiberUnmount(wa, l);
      } catch {
      }
    switch (l.tag) {
      case 26:
        Gt || Qe(l, e), tl(
          t,
          e,
          l
        ), l.memoizedState ? l.memoizedState.count-- : l.stateNode && (l = l.stateNode, l.parentNode.removeChild(l));
        break;
      case 27:
        Gt || Qe(l, e);
        var a = xt, n = ae;
        Dl(l.type) && (xt = l.stateNode, ae = !1), tl(
          t,
          e,
          l
        ), Dn(l.stateNode), xt = a, ae = n;
        break;
      case 5:
        Gt || Qe(l, e);
      case 6:
        if (a = xt, n = ae, xt = null, tl(
          t,
          e,
          l
        ), xt = a, ae = n, xt !== null)
          if (ae)
            try {
              (xt.nodeType === 9 ? xt.body : xt.nodeName === "HTML" ? xt.ownerDocument.body : xt).removeChild(l.stateNode);
            } catch (u) {
              vt(
                l,
                e,
                u
              );
            }
          else
            try {
              xt.removeChild(l.stateNode);
            } catch (u) {
              vt(
                l,
                e,
                u
              );
            }
        break;
      case 18:
        xt !== null && (ae ? (t = xt, Sd(
          t.nodeType === 9 ? t.body : t.nodeName === "HTML" ? t.ownerDocument.body : t,
          l.stateNode
        ), Xa(t)) : Sd(xt, l.stateNode));
        break;
      case 4:
        a = xt, n = ae, xt = l.stateNode.containerInfo, ae = !0, tl(
          t,
          e,
          l
        ), xt = a, ae = n;
        break;
      case 0:
      case 11:
      case 14:
      case 15:
        zl(2, l, e), Gt || zl(4, l, e), tl(
          t,
          e,
          l
        );
        break;
      case 1:
        Gt || (Qe(l, e), a = l.stateNode, typeof a.componentWillUnmount == "function" && zr(
          l,
          e,
          a
        )), tl(
          t,
          e,
          l
        );
        break;
      case 21:
        tl(
          t,
          e,
          l
        );
        break;
      case 22:
        Gt = (a = Gt) || l.memoizedState !== null, tl(
          t,
          e,
          l
        ), Gt = a;
        break;
      default:
        tl(
          t,
          e,
          l
        );
    }
  }
  function xr(t, e) {
    if (e.memoizedState === null && (t = e.alternate, t !== null && (t = t.memoizedState, t !== null))) {
      t = t.dehydrated;
      try {
        Xa(t);
      } catch (l) {
        vt(e, e.return, l);
      }
    }
  }
  function Cr(t, e) {
    if (e.memoizedState === null && (t = e.alternate, t !== null && (t = t.memoizedState, t !== null && (t = t.dehydrated, t !== null))))
      try {
        Xa(t);
      } catch (l) {
        vt(e, e.return, l);
      }
  }
  function dy(t) {
    switch (t.tag) {
      case 31:
      case 13:
      case 19:
        var e = t.stateNode;
        return e === null && (e = t.stateNode = new Or()), e;
      case 22:
        return t = t.stateNode, e = t._retryCache, e === null && (e = t._retryCache = new Or()), e;
      default:
        throw Error(o(435, t.tag));
    }
  }
  function Uu(t, e) {
    var l = dy(t);
    e.forEach(function(a) {
      if (!l.has(a)) {
        l.add(a);
        var n = zy.bind(null, t, a);
        a.then(n, n);
      }
    });
  }
  function ne(t, e) {
    var l = e.deletions;
    if (l !== null)
      for (var a = 0; a < l.length; a++) {
        var n = l[a], u = t, c = e, s = c;
        t: for (; s !== null; ) {
          switch (s.tag) {
            case 27:
              if (Dl(s.type)) {
                xt = s.stateNode, ae = !1;
                break t;
              }
              break;
            case 5:
              xt = s.stateNode, ae = !1;
              break t;
            case 3:
            case 4:
              xt = s.stateNode.containerInfo, ae = !0;
              break t;
          }
          s = s.return;
        }
        if (xt === null) throw Error(o(160));
        Dr(u, c, n), xt = null, ae = !1, u = n.alternate, u !== null && (u.return = null), n.return = null;
      }
    if (e.subtreeFlags & 13886)
      for (e = e.child; e !== null; )
        Ur(e, t), e = e.sibling;
  }
  var Re = null;
  function Ur(t, e) {
    var l = t.alternate, a = t.flags;
    switch (t.tag) {
      case 0:
      case 11:
      case 14:
      case 15:
        ne(e, t), ue(t), a & 4 && (zl(3, t, t.return), bn(3, t), zl(5, t, t.return));
        break;
      case 1:
        ne(e, t), ue(t), a & 512 && (Gt || l === null || Qe(l, l.return)), a & 64 && Pe && (t = t.updateQueue, t !== null && (a = t.callbacks, a !== null && (l = t.shared.hiddenCallbacks, t.shared.hiddenCallbacks = l === null ? a : l.concat(a))));
        break;
      case 26:
        var n = Re;
        if (ne(e, t), ue(t), a & 512 && (Gt || l === null || Qe(l, l.return)), a & 4) {
          var u = l !== null ? l.memoizedState : null;
          if (a = t.memoizedState, l === null)
            if (a === null)
              if (t.stateNode === null) {
                t: {
                  a = t.type, l = t.memoizedProps, n = n.ownerDocument || n;
                  e: switch (a) {
                    case "title":
                      u = n.getElementsByTagName("title")[0], (!u || u[Va] || u[Jt] || u.namespaceURI === "http://www.w3.org/2000/svg" || u.hasAttribute("itemprop")) && (u = n.createElement(a), n.head.insertBefore(
                        u,
                        n.querySelector("head > title")
                      )), $t(u, a, l), u[Jt] = t, Vt(u), a = u;
                      break t;
                    case "link":
                      var c = Ud(
                        "link",
                        "href",
                        n
                      ).get(a + (l.href || ""));
                      if (c) {
                        for (var s = 0; s < c.length; s++)
                          if (u = c[s], u.getAttribute("href") === (l.href == null || l.href === "" ? null : l.href) && u.getAttribute("rel") === (l.rel == null ? null : l.rel) && u.getAttribute("title") === (l.title == null ? null : l.title) && u.getAttribute("crossorigin") === (l.crossOrigin == null ? null : l.crossOrigin)) {
                            c.splice(s, 1);
                            break e;
                          }
                      }
                      u = n.createElement(a), $t(u, a, l), n.head.appendChild(u);
                      break;
                    case "meta":
                      if (c = Ud(
                        "meta",
                        "content",
                        n
                      ).get(a + (l.content || ""))) {
                        for (s = 0; s < c.length; s++)
                          if (u = c[s], u.getAttribute("content") === (l.content == null ? null : "" + l.content) && u.getAttribute("name") === (l.name == null ? null : l.name) && u.getAttribute("property") === (l.property == null ? null : l.property) && u.getAttribute("http-equiv") === (l.httpEquiv == null ? null : l.httpEquiv) && u.getAttribute("charset") === (l.charSet == null ? null : l.charSet)) {
                            c.splice(s, 1);
                            break e;
                          }
                      }
                      u = n.createElement(a), $t(u, a, l), n.head.appendChild(u);
                      break;
                    default:
                      throw Error(o(468, a));
                  }
                  u[Jt] = t, Vt(u), a = u;
                }
                t.stateNode = a;
              } else
                Rd(
                  n,
                  t.type,
                  t.stateNode
                );
            else
              t.stateNode = Cd(
                n,
                a,
                t.memoizedProps
              );
          else
            u !== a ? (u === null ? l.stateNode !== null && (l = l.stateNode, l.parentNode.removeChild(l)) : u.count--, a === null ? Rd(
              n,
              t.type,
              t.stateNode
            ) : Cd(
              n,
              a,
              t.memoizedProps
            )) : a === null && t.stateNode !== null && Xc(
              t,
              t.memoizedProps,
              l.memoizedProps
            );
        }
        break;
      case 27:
        ne(e, t), ue(t), a & 512 && (Gt || l === null || Qe(l, l.return)), l !== null && a & 4 && Xc(
          t,
          t.memoizedProps,
          l.memoizedProps
        );
        break;
      case 5:
        if (ne(e, t), ue(t), a & 512 && (Gt || l === null || Qe(l, l.return)), t.flags & 32) {
          n = t.stateNode;
          try {
            oa(n, "");
          } catch (B) {
            vt(t, t.return, B);
          }
        }
        a & 4 && t.stateNode != null && (n = t.memoizedProps, Xc(
          t,
          n,
          l !== null ? l.memoizedProps : n
        )), a & 1024 && (Lc = !0);
        break;
      case 6:
        if (ne(e, t), ue(t), a & 4) {
          if (t.stateNode === null)
            throw Error(o(162));
          a = t.memoizedProps, l = t.stateNode;
          try {
            l.nodeValue = a;
          } catch (B) {
            vt(t, t.return, B);
          }
        }
        break;
      case 3:
        if (Ju = null, n = Re, Re = Vu(e.containerInfo), ne(e, t), Re = n, ue(t), a & 4 && l !== null && l.memoizedState.isDehydrated)
          try {
            Xa(e.containerInfo);
          } catch (B) {
            vt(t, t.return, B);
          }
        Lc && (Lc = !1, Rr(t));
        break;
      case 4:
        a = Re, Re = Vu(
          t.stateNode.containerInfo
        ), ne(e, t), ue(t), Re = a;
        break;
      case 12:
        ne(e, t), ue(t);
        break;
      case 31:
        ne(e, t), ue(t), a & 4 && (a = t.updateQueue, a !== null && (t.updateQueue = null, Uu(t, a)));
        break;
      case 13:
        ne(e, t), ue(t), t.child.flags & 8192 && t.memoizedState !== null != (l !== null && l.memoizedState !== null) && (Nu = oe()), a & 4 && (a = t.updateQueue, a !== null && (t.updateQueue = null, Uu(t, a)));
        break;
      case 22:
        n = t.memoizedState !== null;
        var d = l !== null && l.memoizedState !== null, g = Pe, E = Gt;
        if (Pe = g || n, Gt = E || d, ne(e, t), Gt = E, Pe = g, ue(t), a & 8192)
          t: for (e = t.stateNode, e._visibility = n ? e._visibility & -2 : e._visibility | 1, n && (l === null || d || Pe || Gt || Pl(t)), l = null, e = t; ; ) {
            if (e.tag === 5 || e.tag === 26) {
              if (l === null) {
                d = l = e;
                try {
                  if (u = d.stateNode, n)
                    c = u.style, typeof c.setProperty == "function" ? c.setProperty("display", "none", "important") : c.display = "none";
                  else {
                    s = d.stateNode;
                    var _ = d.memoizedProps.style, b = _ != null && _.hasOwnProperty("display") ? _.display : null;
                    s.style.display = b == null || typeof b == "boolean" ? "" : ("" + b).trim();
                  }
                } catch (B) {
                  vt(d, d.return, B);
                }
              }
            } else if (e.tag === 6) {
              if (l === null) {
                d = e;
                try {
                  d.stateNode.nodeValue = n ? "" : d.memoizedProps;
                } catch (B) {
                  vt(d, d.return, B);
                }
              }
            } else if (e.tag === 18) {
              if (l === null) {
                d = e;
                try {
                  var z = d.stateNode;
                  n ? zd(z, !0) : zd(d.stateNode, !1);
                } catch (B) {
                  vt(d, d.return, B);
                }
              }
            } else if ((e.tag !== 22 && e.tag !== 23 || e.memoizedState === null || e === t) && e.child !== null) {
              e.child.return = e, e = e.child;
              continue;
            }
            if (e === t) break t;
            for (; e.sibling === null; ) {
              if (e.return === null || e.return === t) break t;
              l === e && (l = null), e = e.return;
            }
            l === e && (l = null), e.sibling.return = e.return, e = e.sibling;
          }
        a & 4 && (a = t.updateQueue, a !== null && (l = a.retryQueue, l !== null && (a.retryQueue = null, Uu(t, l))));
        break;
      case 19:
        ne(e, t), ue(t), a & 4 && (a = t.updateQueue, a !== null && (t.updateQueue = null, Uu(t, a)));
        break;
      case 30:
        break;
      case 21:
        break;
      default:
        ne(e, t), ue(t);
    }
  }
  function ue(t) {
    var e = t.flags;
    if (e & 2) {
      try {
        for (var l, a = t.return; a !== null; ) {
          if (Ar(a)) {
            l = a;
            break;
          }
          a = a.return;
        }
        if (l == null) throw Error(o(160));
        switch (l.tag) {
          case 27:
            var n = l.stateNode, u = wc(t);
            Cu(t, u, n);
            break;
          case 5:
            var c = l.stateNode;
            l.flags & 32 && (oa(c, ""), l.flags &= -33);
            var s = wc(t);
            Cu(t, s, c);
            break;
          case 3:
          case 4:
            var d = l.stateNode.containerInfo, g = wc(t);
            Zc(
              t,
              g,
              d
            );
            break;
          default:
            throw Error(o(161));
        }
      } catch (E) {
        vt(t, t.return, E);
      }
      t.flags &= -3;
    }
    e & 4096 && (t.flags &= -4097);
  }
  function Rr(t) {
    if (t.subtreeFlags & 1024)
      for (t = t.child; t !== null; ) {
        var e = t;
        Rr(e), e.tag === 5 && e.flags & 1024 && e.stateNode.reset(), t = t.sibling;
      }
  }
  function el(t, e) {
    if (e.subtreeFlags & 8772)
      for (e = e.child; e !== null; )
        Mr(t, e.alternate, e), e = e.sibling;
  }
  function Pl(t) {
    for (t = t.child; t !== null; ) {
      var e = t;
      switch (e.tag) {
        case 0:
        case 11:
        case 14:
        case 15:
          zl(4, e, e.return), Pl(e);
          break;
        case 1:
          Qe(e, e.return);
          var l = e.stateNode;
          typeof l.componentWillUnmount == "function" && zr(
            e,
            e.return,
            l
          ), Pl(e);
          break;
        case 27:
          Dn(e.stateNode);
        case 26:
        case 5:
          Qe(e, e.return), Pl(e);
          break;
        case 22:
          e.memoizedState === null && Pl(e);
          break;
        case 30:
          Pl(e);
          break;
        default:
          Pl(e);
      }
      t = t.sibling;
    }
  }
  function ll(t, e, l) {
    for (l = l && (e.subtreeFlags & 8772) !== 0, e = e.child; e !== null; ) {
      var a = e.alternate, n = t, u = e, c = u.flags;
      switch (u.tag) {
        case 0:
        case 11:
        case 15:
          ll(
            n,
            u,
            l
          ), bn(4, u);
          break;
        case 1:
          if (ll(
            n,
            u,
            l
          ), a = u, n = a.stateNode, typeof n.componentDidMount == "function")
            try {
              n.componentDidMount();
            } catch (g) {
              vt(a, a.return, g);
            }
          if (a = u, n = a.updateQueue, n !== null) {
            var s = a.stateNode;
            try {
              var d = n.shared.hiddenCallbacks;
              if (d !== null)
                for (n.shared.hiddenCallbacks = null, n = 0; n < d.length; n++)
                  fo(d[n], s);
            } catch (g) {
              vt(a, a.return, g);
            }
          }
          l && c & 64 && Sr(u), pn(u, u.return);
          break;
        case 27:
          Er(u);
        case 26:
        case 5:
          ll(
            n,
            u,
            l
          ), l && a === null && c & 4 && Tr(u), pn(u, u.return);
          break;
        case 12:
          ll(
            n,
            u,
            l
          );
          break;
        case 31:
          ll(
            n,
            u,
            l
          ), l && c & 4 && xr(n, u);
          break;
        case 13:
          ll(
            n,
            u,
            l
          ), l && c & 4 && Cr(n, u);
          break;
        case 22:
          u.memoizedState === null && ll(
            n,
            u,
            l
          ), pn(u, u.return);
          break;
        case 30:
          break;
        default:
          ll(
            n,
            u,
            l
          );
      }
      e = e.sibling;
    }
  }
  function Vc(t, e) {
    var l = null;
    t !== null && t.memoizedState !== null && t.memoizedState.cachePool !== null && (l = t.memoizedState.cachePool.pool), t = null, e.memoizedState !== null && e.memoizedState.cachePool !== null && (t = e.memoizedState.cachePool.pool), t !== l && (t != null && t.refCount++, l != null && nn(l));
  }
  function Kc(t, e) {
    t = null, e.alternate !== null && (t = e.alternate.memoizedState.cache), e = e.memoizedState.cache, e !== t && (e.refCount++, t != null && nn(t));
  }
  function Ne(t, e, l, a) {
    if (e.subtreeFlags & 10256)
      for (e = e.child; e !== null; )
        Nr(
          t,
          e,
          l,
          a
        ), e = e.sibling;
  }
  function Nr(t, e, l, a) {
    var n = e.flags;
    switch (e.tag) {
      case 0:
      case 11:
      case 15:
        Ne(
          t,
          e,
          l,
          a
        ), n & 2048 && bn(9, e);
        break;
      case 1:
        Ne(
          t,
          e,
          l,
          a
        );
        break;
      case 3:
        Ne(
          t,
          e,
          l,
          a
        ), n & 2048 && (t = null, e.alternate !== null && (t = e.alternate.memoizedState.cache), e = e.memoizedState.cache, e !== t && (e.refCount++, t != null && nn(t)));
        break;
      case 12:
        if (n & 2048) {
          Ne(
            t,
            e,
            l,
            a
          ), t = e.stateNode;
          try {
            var u = e.memoizedProps, c = u.id, s = u.onPostCommit;
            typeof s == "function" && s(
              c,
              e.alternate === null ? "mount" : "update",
              t.passiveEffectDuration,
              -0
            );
          } catch (d) {
            vt(e, e.return, d);
          }
        } else
          Ne(
            t,
            e,
            l,
            a
          );
        break;
      case 31:
        Ne(
          t,
          e,
          l,
          a
        );
        break;
      case 13:
        Ne(
          t,
          e,
          l,
          a
        );
        break;
      case 23:
        break;
      case 22:
        u = e.stateNode, c = e.alternate, e.memoizedState !== null ? u._visibility & 2 ? Ne(
          t,
          e,
          l,
          a
        ) : Sn(t, e) : u._visibility & 2 ? Ne(
          t,
          e,
          l,
          a
        ) : (u._visibility |= 2, Ca(
          t,
          e,
          l,
          a,
          (e.subtreeFlags & 10256) !== 0 || !1
        )), n & 2048 && Vc(c, e);
        break;
      case 24:
        Ne(
          t,
          e,
          l,
          a
        ), n & 2048 && Kc(e.alternate, e);
        break;
      default:
        Ne(
          t,
          e,
          l,
          a
        );
    }
  }
  function Ca(t, e, l, a, n) {
    for (n = n && ((e.subtreeFlags & 10256) !== 0 || !1), e = e.child; e !== null; ) {
      var u = t, c = e, s = l, d = a, g = c.flags;
      switch (c.tag) {
        case 0:
        case 11:
        case 15:
          Ca(
            u,
            c,
            s,
            d,
            n
          ), bn(8, c);
          break;
        case 23:
          break;
        case 22:
          var E = c.stateNode;
          c.memoizedState !== null ? E._visibility & 2 ? Ca(
            u,
            c,
            s,
            d,
            n
          ) : Sn(
            u,
            c
          ) : (E._visibility |= 2, Ca(
            u,
            c,
            s,
            d,
            n
          )), n && g & 2048 && Vc(
            c.alternate,
            c
          );
          break;
        case 24:
          Ca(
            u,
            c,
            s,
            d,
            n
          ), n && g & 2048 && Kc(c.alternate, c);
          break;
        default:
          Ca(
            u,
            c,
            s,
            d,
            n
          );
      }
      e = e.sibling;
    }
  }
  function Sn(t, e) {
    if (e.subtreeFlags & 10256)
      for (e = e.child; e !== null; ) {
        var l = t, a = e, n = a.flags;
        switch (a.tag) {
          case 22:
            Sn(l, a), n & 2048 && Vc(
              a.alternate,
              a
            );
            break;
          case 24:
            Sn(l, a), n & 2048 && Kc(a.alternate, a);
            break;
          default:
            Sn(l, a);
        }
        e = e.sibling;
      }
  }
  var zn = 8192;
  function Ua(t, e, l) {
    if (t.subtreeFlags & zn)
      for (t = t.child; t !== null; )
        Hr(
          t,
          e,
          l
        ), t = t.sibling;
  }
  function Hr(t, e, l) {
    switch (t.tag) {
      case 26:
        Ua(
          t,
          e,
          l
        ), t.flags & zn && t.memoizedState !== null && Iy(
          l,
          Re,
          t.memoizedState,
          t.memoizedProps
        );
        break;
      case 5:
        Ua(
          t,
          e,
          l
        );
        break;
      case 3:
      case 4:
        var a = Re;
        Re = Vu(t.stateNode.containerInfo), Ua(
          t,
          e,
          l
        ), Re = a;
        break;
      case 22:
        t.memoizedState === null && (a = t.alternate, a !== null && a.memoizedState !== null ? (a = zn, zn = 16777216, Ua(
          t,
          e,
          l
        ), zn = a) : Ua(
          t,
          e,
          l
        ));
        break;
      default:
        Ua(
          t,
          e,
          l
        );
    }
  }
  function qr(t) {
    var e = t.alternate;
    if (e !== null && (t = e.child, t !== null)) {
      e.child = null;
      do
        e = t.sibling, t.sibling = null, t = e;
      while (t !== null);
    }
  }
  function Tn(t) {
    var e = t.deletions;
    if ((t.flags & 16) !== 0) {
      if (e !== null)
        for (var l = 0; l < e.length; l++) {
          var a = e[l];
          Kt = a, Br(
            a,
            t
          );
        }
      qr(t);
    }
    if (t.subtreeFlags & 10256)
      for (t = t.child; t !== null; )
        jr(t), t = t.sibling;
  }
  function jr(t) {
    switch (t.tag) {
      case 0:
      case 11:
      case 15:
        Tn(t), t.flags & 2048 && zl(9, t, t.return);
        break;
      case 3:
        Tn(t);
        break;
      case 12:
        Tn(t);
        break;
      case 22:
        var e = t.stateNode;
        t.memoizedState !== null && e._visibility & 2 && (t.return === null || t.return.tag !== 13) ? (e._visibility &= -3, Ru(t)) : Tn(t);
        break;
      default:
        Tn(t);
    }
  }
  function Ru(t) {
    var e = t.deletions;
    if ((t.flags & 16) !== 0) {
      if (e !== null)
        for (var l = 0; l < e.length; l++) {
          var a = e[l];
          Kt = a, Br(
            a,
            t
          );
        }
      qr(t);
    }
    for (t = t.child; t !== null; ) {
      switch (e = t, e.tag) {
        case 0:
        case 11:
        case 15:
          zl(8, e, e.return), Ru(e);
          break;
        case 22:
          l = e.stateNode, l._visibility & 2 && (l._visibility &= -3, Ru(e));
          break;
        default:
          Ru(e);
      }
      t = t.sibling;
    }
  }
  function Br(t, e) {
    for (; Kt !== null; ) {
      var l = Kt;
      switch (l.tag) {
        case 0:
        case 11:
        case 15:
          zl(8, l, e);
          break;
        case 23:
        case 22:
          if (l.memoizedState !== null && l.memoizedState.cachePool !== null) {
            var a = l.memoizedState.cachePool.pool;
            a != null && a.refCount++;
          }
          break;
        case 24:
          nn(l.memoizedState.cache);
      }
      if (a = l.child, a !== null) a.return = l, Kt = a;
      else
        t: for (l = t; Kt !== null; ) {
          a = Kt;
          var n = a.sibling, u = a.return;
          if (_r(a), a === l) {
            Kt = null;
            break t;
          }
          if (n !== null) {
            n.return = u, Kt = n;
            break t;
          }
          Kt = u;
        }
    }
  }
  var hy = {
    getCacheForType: function(t) {
      var e = Ft(jt), l = e.data.get(t);
      return l === void 0 && (l = t(), e.data.set(t, l)), l;
    },
    cacheSignal: function() {
      return Ft(jt).controller.signal;
    }
  }, my = typeof WeakMap == "function" ? WeakMap : Map, mt = 0, zt = null, lt = null, ut = 0, yt = 0, ge = null, Tl = !1, Ra = !1, Jc = !1, al = 0, Rt = 0, Al = 0, ta = 0, kc = 0, be = 0, Na = 0, An = null, ie = null, Fc = !1, Nu = 0, Qr = 0, Hu = 1 / 0, qu = null, El = null, Xt = 0, Ol = null, Ha = null, nl = 0, Wc = 0, $c = null, Gr = null, En = 0, Ic = null;
  function pe() {
    return (mt & 2) !== 0 && ut !== 0 ? ut & -ut : T.T !== null ? nf() : ts();
  }
  function Yr() {
    if (be === 0)
      if ((ut & 536870912) === 0 || ft) {
        var t = Zn;
        Zn <<= 1, (Zn & 3932160) === 0 && (Zn = 262144), be = t;
      } else be = 536870912;
    return t = ye.current, t !== null && (t.flags |= 32), be;
  }
  function ce(t, e, l) {
    (t === zt && (yt === 2 || yt === 9) || t.cancelPendingCommit !== null) && (qa(t, 0), Ml(
      t,
      ut,
      be,
      !1
    )), La(t, l), ((mt & 2) === 0 || t !== zt) && (t === zt && ((mt & 2) === 0 && (ta |= l), Rt === 4 && Ml(
      t,
      ut,
      be,
      !1
    )), Ge(t));
  }
  function Xr(t, e, l) {
    if ((mt & 6) !== 0) throw Error(o(327));
    var a = !l && (e & 127) === 0 && (e & t.expiredLanes) === 0 || Za(t, e), n = a ? gy(t, e) : tf(t, e, !0), u = a;
    do {
      if (n === 0) {
        Ra && !a && Ml(t, e, 0, !1);
        break;
      } else {
        if (l = t.current.alternate, u && !yy(l)) {
          n = tf(t, e, !1), u = !1;
          continue;
        }
        if (n === 2) {
          if (u = e, t.errorRecoveryDisabledLanes & u)
            var c = 0;
          else
            c = t.pendingLanes & -536870913, c = c !== 0 ? c : c & 536870912 ? 536870912 : 0;
          if (c !== 0) {
            e = c;
            t: {
              var s = t;
              n = An;
              var d = s.current.memoizedState.isDehydrated;
              if (d && (qa(s, c).flags |= 256), c = tf(
                s,
                c,
                !1
              ), c !== 2) {
                if (Jc && !d) {
                  s.errorRecoveryDisabledLanes |= u, ta |= u, n = 4;
                  break t;
                }
                u = ie, ie = n, u !== null && (ie === null ? ie = u : ie.push.apply(
                  ie,
                  u
                ));
              }
              n = c;
            }
            if (u = !1, n !== 2) continue;
          }
        }
        if (n === 1) {
          qa(t, 0), Ml(t, e, 0, !0);
          break;
        }
        t: {
          switch (a = t, u = n, u) {
            case 0:
            case 1:
              throw Error(o(345));
            case 4:
              if ((e & 4194048) !== e) break;
            case 6:
              Ml(
                a,
                e,
                be,
                !Tl
              );
              break t;
            case 2:
              ie = null;
              break;
            case 3:
            case 5:
              break;
            default:
              throw Error(o(329));
          }
          if ((e & 62914560) === e && (n = Nu + 300 - oe(), 10 < n)) {
            if (Ml(
              a,
              e,
              be,
              !Tl
            ), Vn(a, 0, !0) !== 0) break t;
            nl = e, a.timeoutHandle = bd(
              wr.bind(
                null,
                a,
                l,
                ie,
                qu,
                Fc,
                e,
                be,
                ta,
                Na,
                Tl,
                u,
                "Throttled",
                -0,
                0
              ),
              n
            );
            break t;
          }
          wr(
            a,
            l,
            ie,
            qu,
            Fc,
            e,
            be,
            ta,
            Na,
            Tl,
            u,
            null,
            -0,
            0
          );
        }
      }
      break;
    } while (!0);
    Ge(t);
  }
  function wr(t, e, l, a, n, u, c, s, d, g, E, _, b, z) {
    if (t.timeoutHandle = -1, _ = e.subtreeFlags, _ & 8192 || (_ & 16785408) === 16785408) {
      _ = {
        stylesheets: null,
        count: 0,
        imgCount: 0,
        imgBytes: 0,
        suspenseyImages: [],
        waitingForImages: !0,
        waitingForViewTransition: !1,
        unsuspend: Ze
      }, Hr(
        e,
        u,
        _
      );
      var B = (u & 62914560) === u ? Nu - oe() : (u & 4194048) === u ? Qr - oe() : 0;
      if (B = Py(
        _,
        B
      ), B !== null) {
        nl = u, t.cancelPendingCommit = B(
          Wr.bind(
            null,
            t,
            e,
            u,
            l,
            a,
            n,
            c,
            s,
            d,
            E,
            _,
            null,
            b,
            z
          )
        ), Ml(t, u, c, !g);
        return;
      }
    }
    Wr(
      t,
      e,
      u,
      l,
      a,
      n,
      c,
      s,
      d
    );
  }
  function yy(t) {
    for (var e = t; ; ) {
      var l = e.tag;
      if ((l === 0 || l === 11 || l === 15) && e.flags & 16384 && (l = e.updateQueue, l !== null && (l = l.stores, l !== null)))
        for (var a = 0; a < l.length; a++) {
          var n = l[a], u = n.getSnapshot;
          n = n.value;
          try {
            if (!he(u(), n)) return !1;
          } catch {
            return !1;
          }
        }
      if (l = e.child, e.subtreeFlags & 16384 && l !== null)
        l.return = e, e = l;
      else {
        if (e === t) break;
        for (; e.sibling === null; ) {
          if (e.return === null || e.return === t) return !0;
          e = e.return;
        }
        e.sibling.return = e.return, e = e.sibling;
      }
    }
    return !0;
  }
  function Ml(t, e, l, a) {
    e &= ~kc, e &= ~ta, t.suspendedLanes |= e, t.pingedLanes &= ~e, a && (t.warmLanes |= e), a = t.expirationTimes;
    for (var n = e; 0 < n; ) {
      var u = 31 - de(n), c = 1 << u;
      a[u] = -1, n &= ~c;
    }
    l !== 0 && $f(t, l, e);
  }
  function ju() {
    return (mt & 6) === 0 ? (On(0), !1) : !0;
  }
  function Pc() {
    if (lt !== null) {
      if (yt === 0)
        var t = lt.return;
      else
        t = lt, Je = Vl = null, yc(t), Oa = null, cn = 0, t = lt;
      for (; t !== null; )
        pr(t.alternate, t), t = t.return;
      lt = null;
    }
  }
  function qa(t, e) {
    var l = t.timeoutHandle;
    l !== -1 && (t.timeoutHandle = -1, qy(l)), l = t.cancelPendingCommit, l !== null && (t.cancelPendingCommit = null, l()), nl = 0, Pc(), zt = t, lt = l = Ve(t.current, null), ut = e, yt = 0, ge = null, Tl = !1, Ra = Za(t, e), Jc = !1, Na = be = kc = ta = Al = Rt = 0, ie = An = null, Fc = !1, (e & 8) !== 0 && (e |= e & 32);
    var a = t.entangledLanes;
    if (a !== 0)
      for (t = t.entanglements, a &= e; 0 < a; ) {
        var n = 31 - de(a), u = 1 << n;
        e |= t[n], a &= ~u;
      }
    return al = e, au(), l;
  }
  function Zr(t, e) {
    W = null, T.H = yn, e === Ea || e === ru ? (e = no(), yt = 3) : e === ac ? (e = no(), yt = 4) : yt = e === Uc ? 8 : e !== null && typeof e == "object" && typeof e.then == "function" ? 6 : 1, ge = e, lt === null && (Rt = 1, Ou(
      t,
      Ee(e, t.current)
    ));
  }
  function Lr() {
    var t = ye.current;
    return t === null ? !0 : (ut & 4194048) === ut ? De === null : (ut & 62914560) === ut || (ut & 536870912) !== 0 ? t === De : !1;
  }
  function Vr() {
    var t = T.H;
    return T.H = yn, t === null ? yn : t;
  }
  function Kr() {
    var t = T.A;
    return T.A = hy, t;
  }
  function Bu() {
    Rt = 4, Tl || (ut & 4194048) !== ut && ye.current !== null || (Ra = !0), (Al & 134217727) === 0 && (ta & 134217727) === 0 || zt === null || Ml(
      zt,
      ut,
      be,
      !1
    );
  }
  function tf(t, e, l) {
    var a = mt;
    mt |= 2;
    var n = Vr(), u = Kr();
    (zt !== t || ut !== e) && (qu = null, qa(t, e)), e = !1;
    var c = Rt;
    t: do
      try {
        if (yt !== 0 && lt !== null) {
          var s = lt, d = ge;
          switch (yt) {
            case 8:
              Pc(), c = 6;
              break t;
            case 3:
            case 2:
            case 9:
            case 6:
              ye.current === null && (e = !0);
              var g = yt;
              if (yt = 0, ge = null, ja(t, s, d, g), l && Ra) {
                c = 0;
                break t;
              }
              break;
            default:
              g = yt, yt = 0, ge = null, ja(t, s, d, g);
          }
        }
        vy(), c = Rt;
        break;
      } catch (E) {
        Zr(t, E);
      }
    while (!0);
    return e && t.shellSuspendCounter++, Je = Vl = null, mt = a, T.H = n, T.A = u, lt === null && (zt = null, ut = 0, au()), c;
  }
  function vy() {
    for (; lt !== null; ) Jr(lt);
  }
  function gy(t, e) {
    var l = mt;
    mt |= 2;
    var a = Vr(), n = Kr();
    zt !== t || ut !== e ? (qu = null, Hu = oe() + 500, qa(t, e)) : Ra = Za(
      t,
      e
    );
    t: do
      try {
        if (yt !== 0 && lt !== null) {
          e = lt;
          var u = ge;
          e: switch (yt) {
            case 1:
              yt = 0, ge = null, ja(t, e, u, 1);
              break;
            case 2:
            case 9:
              if (lo(u)) {
                yt = 0, ge = null, kr(e);
                break;
              }
              e = function() {
                yt !== 2 && yt !== 9 || zt !== t || (yt = 7), Ge(t);
              }, u.then(e, e);
              break t;
            case 3:
              yt = 7;
              break t;
            case 4:
              yt = 5;
              break t;
            case 7:
              lo(u) ? (yt = 0, ge = null, kr(e)) : (yt = 0, ge = null, ja(t, e, u, 7));
              break;
            case 5:
              var c = null;
              switch (lt.tag) {
                case 26:
                  c = lt.memoizedState;
                case 5:
                case 27:
                  var s = lt;
                  if (c ? Nd(c) : s.stateNode.complete) {
                    yt = 0, ge = null;
                    var d = s.sibling;
                    if (d !== null) lt = d;
                    else {
                      var g = s.return;
                      g !== null ? (lt = g, Qu(g)) : lt = null;
                    }
                    break e;
                  }
              }
              yt = 0, ge = null, ja(t, e, u, 5);
              break;
            case 6:
              yt = 0, ge = null, ja(t, e, u, 6);
              break;
            case 8:
              Pc(), Rt = 6;
              break t;
            default:
              throw Error(o(462));
          }
        }
        by();
        break;
      } catch (E) {
        Zr(t, E);
      }
    while (!0);
    return Je = Vl = null, T.H = a, T.A = n, mt = l, lt !== null ? 0 : (zt = null, ut = 0, au(), Rt);
  }
  function by() {
    for (; lt !== null && !Xh(); )
      Jr(lt);
  }
  function Jr(t) {
    var e = gr(t.alternate, t, al);
    t.memoizedProps = t.pendingProps, e === null ? Qu(t) : lt = e;
  }
  function kr(t) {
    var e = t, l = e.alternate;
    switch (e.tag) {
      case 15:
      case 0:
        e = rr(
          l,
          e,
          e.pendingProps,
          e.type,
          void 0,
          ut
        );
        break;
      case 11:
        e = rr(
          l,
          e,
          e.pendingProps,
          e.type.render,
          e.ref,
          ut
        );
        break;
      case 5:
        yc(e);
      default:
        pr(l, e), e = lt = Vs(e, al), e = gr(l, e, al);
    }
    t.memoizedProps = t.pendingProps, e === null ? Qu(t) : lt = e;
  }
  function ja(t, e, l, a) {
    Je = Vl = null, yc(e), Oa = null, cn = 0;
    var n = e.return;
    try {
      if (iy(
        t,
        n,
        e,
        l,
        ut
      )) {
        Rt = 1, Ou(
          t,
          Ee(l, t.current)
        ), lt = null;
        return;
      }
    } catch (u) {
      if (n !== null) throw lt = n, u;
      Rt = 1, Ou(
        t,
        Ee(l, t.current)
      ), lt = null;
      return;
    }
    e.flags & 32768 ? (ft || a === 1 ? t = !0 : Ra || (ut & 536870912) !== 0 ? t = !1 : (Tl = t = !0, (a === 2 || a === 9 || a === 3 || a === 6) && (a = ye.current, a !== null && a.tag === 13 && (a.flags |= 16384))), Fr(e, t)) : Qu(e);
  }
  function Qu(t) {
    var e = t;
    do {
      if ((e.flags & 32768) !== 0) {
        Fr(
          e,
          Tl
        );
        return;
      }
      t = e.return;
      var l = sy(
        e.alternate,
        e,
        al
      );
      if (l !== null) {
        lt = l;
        return;
      }
      if (e = e.sibling, e !== null) {
        lt = e;
        return;
      }
      lt = e = t;
    } while (e !== null);
    Rt === 0 && (Rt = 5);
  }
  function Fr(t, e) {
    do {
      var l = oy(t.alternate, t);
      if (l !== null) {
        l.flags &= 32767, lt = l;
        return;
      }
      if (l = t.return, l !== null && (l.flags |= 32768, l.subtreeFlags = 0, l.deletions = null), !e && (t = t.sibling, t !== null)) {
        lt = t;
        return;
      }
      lt = t = l;
    } while (t !== null);
    Rt = 6, lt = null;
  }
  function Wr(t, e, l, a, n, u, c, s, d) {
    t.cancelPendingCommit = null;
    do
      Gu();
    while (Xt !== 0);
    if ((mt & 6) !== 0) throw Error(o(327));
    if (e !== null) {
      if (e === t.current) throw Error(o(177));
      if (u = e.lanes | e.childLanes, u |= wi, $h(
        t,
        l,
        u,
        c,
        s,
        d
      ), t === zt && (lt = zt = null, ut = 0), Ha = e, Ol = t, nl = l, Wc = u, $c = n, Gr = a, (e.subtreeFlags & 10256) !== 0 || (e.flags & 10256) !== 0 ? (t.callbackNode = null, t.callbackPriority = 0, Ty(Xn, function() {
        return ed(), null;
      })) : (t.callbackNode = null, t.callbackPriority = 0), a = (e.flags & 13878) !== 0, (e.subtreeFlags & 13878) !== 0 || a) {
        a = T.T, T.T = null, n = U.p, U.p = 2, c = mt, mt |= 4;
        try {
          ry(t, e, l);
        } finally {
          mt = c, U.p = n, T.T = a;
        }
      }
      Xt = 1, $r(), Ir(), Pr();
    }
  }
  function $r() {
    if (Xt === 1) {
      Xt = 0;
      var t = Ol, e = Ha, l = (e.flags & 13878) !== 0;
      if ((e.subtreeFlags & 13878) !== 0 || l) {
        l = T.T, T.T = null;
        var a = U.p;
        U.p = 2;
        var n = mt;
        mt |= 4;
        try {
          Ur(e, t);
          var u = hf, c = js(t.containerInfo), s = u.focusedElem, d = u.selectionRange;
          if (c !== s && s && s.ownerDocument && qs(
            s.ownerDocument.documentElement,
            s
          )) {
            if (d !== null && Bi(s)) {
              var g = d.start, E = d.end;
              if (E === void 0 && (E = g), "selectionStart" in s)
                s.selectionStart = g, s.selectionEnd = Math.min(
                  E,
                  s.value.length
                );
              else {
                var _ = s.ownerDocument || document, b = _ && _.defaultView || window;
                if (b.getSelection) {
                  var z = b.getSelection(), B = s.textContent.length, K = Math.min(d.start, B), St = d.end === void 0 ? K : Math.min(d.end, B);
                  !z.extend && K > St && (c = St, St = K, K = c);
                  var y = Hs(
                    s,
                    K
                  ), h = Hs(
                    s,
                    St
                  );
                  if (y && h && (z.rangeCount !== 1 || z.anchorNode !== y.node || z.anchorOffset !== y.offset || z.focusNode !== h.node || z.focusOffset !== h.offset)) {
                    var v = _.createRange();
                    v.setStart(y.node, y.offset), z.removeAllRanges(), K > St ? (z.addRange(v), z.extend(h.node, h.offset)) : (v.setEnd(h.node, h.offset), z.addRange(v));
                  }
                }
              }
            }
            for (_ = [], z = s; z = z.parentNode; )
              z.nodeType === 1 && _.push({
                element: z,
                left: z.scrollLeft,
                top: z.scrollTop
              });
            for (typeof s.focus == "function" && s.focus(), s = 0; s < _.length; s++) {
              var M = _[s];
              M.element.scrollLeft = M.left, M.element.scrollTop = M.top;
            }
          }
          $u = !!df, hf = df = null;
        } finally {
          mt = n, U.p = a, T.T = l;
        }
      }
      t.current = e, Xt = 2;
    }
  }
  function Ir() {
    if (Xt === 2) {
      Xt = 0;
      var t = Ol, e = Ha, l = (e.flags & 8772) !== 0;
      if ((e.subtreeFlags & 8772) !== 0 || l) {
        l = T.T, T.T = null;
        var a = U.p;
        U.p = 2;
        var n = mt;
        mt |= 4;
        try {
          Mr(t, e.alternate, e);
        } finally {
          mt = n, U.p = a, T.T = l;
        }
      }
      Xt = 3;
    }
  }
  function Pr() {
    if (Xt === 4 || Xt === 3) {
      Xt = 0, wh();
      var t = Ol, e = Ha, l = nl, a = Gr;
      (e.subtreeFlags & 10256) !== 0 || (e.flags & 10256) !== 0 ? Xt = 5 : (Xt = 0, Ha = Ol = null, td(t, t.pendingLanes));
      var n = t.pendingLanes;
      if (n === 0 && (El = null), bi(l), e = e.stateNode, re && typeof re.onCommitFiberRoot == "function")
        try {
          re.onCommitFiberRoot(
            wa,
            e,
            void 0,
            (e.current.flags & 128) === 128
          );
        } catch {
        }
      if (a !== null) {
        e = T.T, n = U.p, U.p = 2, T.T = null;
        try {
          for (var u = t.onRecoverableError, c = 0; c < a.length; c++) {
            var s = a[c];
            u(s.value, {
              componentStack: s.stack
            });
          }
        } finally {
          T.T = e, U.p = n;
        }
      }
      (nl & 3) !== 0 && Gu(), Ge(t), n = t.pendingLanes, (l & 261930) !== 0 && (n & 42) !== 0 ? t === Ic ? En++ : (En = 0, Ic = t) : En = 0, On(0);
    }
  }
  function td(t, e) {
    (t.pooledCacheLanes &= e) === 0 && (e = t.pooledCache, e != null && (t.pooledCache = null, nn(e)));
  }
  function Gu() {
    return $r(), Ir(), Pr(), ed();
  }
  function ed() {
    if (Xt !== 5) return !1;
    var t = Ol, e = Wc;
    Wc = 0;
    var l = bi(nl), a = T.T, n = U.p;
    try {
      U.p = 32 > l ? 32 : l, T.T = null, l = $c, $c = null;
      var u = Ol, c = nl;
      if (Xt = 0, Ha = Ol = null, nl = 0, (mt & 6) !== 0) throw Error(o(331));
      var s = mt;
      if (mt |= 4, jr(u.current), Nr(
        u,
        u.current,
        c,
        l
      ), mt = s, On(0, !1), re && typeof re.onPostCommitFiberRoot == "function")
        try {
          re.onPostCommitFiberRoot(wa, u);
        } catch {
        }
      return !0;
    } finally {
      U.p = n, T.T = a, td(t, e);
    }
  }
  function ld(t, e, l) {
    e = Ee(l, e), e = Cc(t.stateNode, e, 2), t = bl(t, e, 2), t !== null && (La(t, 2), Ge(t));
  }
  function vt(t, e, l) {
    if (t.tag === 3)
      ld(t, t, l);
    else
      for (; e !== null; ) {
        if (e.tag === 3) {
          ld(
            e,
            t,
            l
          );
          break;
        } else if (e.tag === 1) {
          var a = e.stateNode;
          if (typeof e.type.getDerivedStateFromError == "function" || typeof a.componentDidCatch == "function" && (El === null || !El.has(a))) {
            t = Ee(l, t), l = ar(2), a = bl(e, l, 2), a !== null && (nr(
              l,
              a,
              e,
              t
            ), La(a, 2), Ge(a));
            break;
          }
        }
        e = e.return;
      }
  }
  function ef(t, e, l) {
    var a = t.pingCache;
    if (a === null) {
      a = t.pingCache = new my();
      var n = /* @__PURE__ */ new Set();
      a.set(e, n);
    } else
      n = a.get(e), n === void 0 && (n = /* @__PURE__ */ new Set(), a.set(e, n));
    n.has(l) || (Jc = !0, n.add(l), t = py.bind(null, t, e, l), e.then(t, t));
  }
  function py(t, e, l) {
    var a = t.pingCache;
    a !== null && a.delete(e), t.pingedLanes |= t.suspendedLanes & l, t.warmLanes &= ~l, zt === t && (ut & l) === l && (Rt === 4 || Rt === 3 && (ut & 62914560) === ut && 300 > oe() - Nu ? (mt & 2) === 0 && qa(t, 0) : kc |= l, Na === ut && (Na = 0)), Ge(t);
  }
  function ad(t, e) {
    e === 0 && (e = Wf()), t = wl(t, e), t !== null && (La(t, e), Ge(t));
  }
  function Sy(t) {
    var e = t.memoizedState, l = 0;
    e !== null && (l = e.retryLane), ad(t, l);
  }
  function zy(t, e) {
    var l = 0;
    switch (t.tag) {
      case 31:
      case 13:
        var a = t.stateNode, n = t.memoizedState;
        n !== null && (l = n.retryLane);
        break;
      case 19:
        a = t.stateNode;
        break;
      case 22:
        a = t.stateNode._retryCache;
        break;
      default:
        throw Error(o(314));
    }
    a !== null && a.delete(e), ad(t, l);
  }
  function Ty(t, e) {
    return mi(t, e);
  }
  var Yu = null, Ba = null, lf = !1, Xu = !1, af = !1, _l = 0;
  function Ge(t) {
    t !== Ba && t.next === null && (Ba === null ? Yu = Ba = t : Ba = Ba.next = t), Xu = !0, lf || (lf = !0, Ey());
  }
  function On(t, e) {
    if (!af && Xu) {
      af = !0;
      do
        for (var l = !1, a = Yu; a !== null; ) {
          if (t !== 0) {
            var n = a.pendingLanes;
            if (n === 0) var u = 0;
            else {
              var c = a.suspendedLanes, s = a.pingedLanes;
              u = (1 << 31 - de(42 | t) + 1) - 1, u &= n & ~(c & ~s), u = u & 201326741 ? u & 201326741 | 1 : u ? u | 2 : 0;
            }
            u !== 0 && (l = !0, cd(a, u));
          } else
            u = ut, u = Vn(
              a,
              a === zt ? u : 0,
              a.cancelPendingCommit !== null || a.timeoutHandle !== -1
            ), (u & 3) === 0 || Za(a, u) || (l = !0, cd(a, u));
          a = a.next;
        }
      while (l);
      af = !1;
    }
  }
  function Ay() {
    nd();
  }
  function nd() {
    Xu = lf = !1;
    var t = 0;
    _l !== 0 && Hy() && (t = _l);
    for (var e = oe(), l = null, a = Yu; a !== null; ) {
      var n = a.next, u = ud(a, e);
      u === 0 ? (a.next = null, l === null ? Yu = n : l.next = n, n === null && (Ba = l)) : (l = a, (t !== 0 || (u & 3) !== 0) && (Xu = !0)), a = n;
    }
    Xt !== 0 && Xt !== 5 || On(t), _l !== 0 && (_l = 0);
  }
  function ud(t, e) {
    for (var l = t.suspendedLanes, a = t.pingedLanes, n = t.expirationTimes, u = t.pendingLanes & -62914561; 0 < u; ) {
      var c = 31 - de(u), s = 1 << c, d = n[c];
      d === -1 ? ((s & l) === 0 || (s & a) !== 0) && (n[c] = Wh(s, e)) : d <= e && (t.expiredLanes |= s), u &= ~s;
    }
    if (e = zt, l = ut, l = Vn(
      t,
      t === e ? l : 0,
      t.cancelPendingCommit !== null || t.timeoutHandle !== -1
    ), a = t.callbackNode, l === 0 || t === e && (yt === 2 || yt === 9) || t.cancelPendingCommit !== null)
      return a !== null && a !== null && yi(a), t.callbackNode = null, t.callbackPriority = 0;
    if ((l & 3) === 0 || Za(t, l)) {
      if (e = l & -l, e === t.callbackPriority) return e;
      switch (a !== null && yi(a), bi(l)) {
        case 2:
        case 8:
          l = kf;
          break;
        case 32:
          l = Xn;
          break;
        case 268435456:
          l = Ff;
          break;
        default:
          l = Xn;
      }
      return a = id.bind(null, t), l = mi(l, a), t.callbackPriority = e, t.callbackNode = l, e;
    }
    return a !== null && a !== null && yi(a), t.callbackPriority = 2, t.callbackNode = null, 2;
  }
  function id(t, e) {
    if (Xt !== 0 && Xt !== 5)
      return t.callbackNode = null, t.callbackPriority = 0, null;
    var l = t.callbackNode;
    if (Gu() && t.callbackNode !== l)
      return null;
    var a = ut;
    return a = Vn(
      t,
      t === zt ? a : 0,
      t.cancelPendingCommit !== null || t.timeoutHandle !== -1
    ), a === 0 ? null : (Xr(t, a, e), ud(t, oe()), t.callbackNode != null && t.callbackNode === l ? id.bind(null, t) : null);
  }
  function cd(t, e) {
    if (Gu()) return null;
    Xr(t, e, !0);
  }
  function Ey() {
    jy(function() {
      (mt & 6) !== 0 ? mi(
        Jf,
        Ay
      ) : nd();
    });
  }
  function nf() {
    if (_l === 0) {
      var t = Ta;
      t === 0 && (t = wn, wn <<= 1, (wn & 261888) === 0 && (wn = 256)), _l = t;
    }
    return _l;
  }
  function fd(t) {
    return t == null || typeof t == "symbol" || typeof t == "boolean" ? null : typeof t == "function" ? t : Fn("" + t);
  }
  function sd(t, e) {
    var l = e.ownerDocument.createElement("input");
    return l.name = e.name, l.value = e.value, t.id && l.setAttribute("form", t.id), e.parentNode.insertBefore(l, e), t = new FormData(t), l.parentNode.removeChild(l), t;
  }
  function Oy(t, e, l, a, n) {
    if (e === "submit" && l && l.stateNode === n) {
      var u = fd(
        (n[ee] || null).action
      ), c = a.submitter;
      c && (e = (e = c[ee] || null) ? fd(e.formAction) : c.getAttribute("formAction"), e !== null && (u = e, c = null));
      var s = new Pn(
        "action",
        "action",
        null,
        a,
        n
      );
      t.push({
        event: s,
        listeners: [
          {
            instance: null,
            listener: function() {
              if (a.defaultPrevented) {
                if (_l !== 0) {
                  var d = c ? sd(n, c) : new FormData(n);
                  Ec(
                    l,
                    {
                      pending: !0,
                      data: d,
                      method: n.method,
                      action: u
                    },
                    null,
                    d
                  );
                }
              } else
                typeof u == "function" && (s.preventDefault(), d = c ? sd(n, c) : new FormData(n), Ec(
                  l,
                  {
                    pending: !0,
                    data: d,
                    method: n.method,
                    action: u
                  },
                  u,
                  d
                ));
            },
            currentTarget: n
          }
        ]
      });
    }
  }
  for (var uf = 0; uf < Xi.length; uf++) {
    var cf = Xi[uf], My = cf.toLowerCase(), _y = cf[0].toUpperCase() + cf.slice(1);
    Ue(
      My,
      "on" + _y
    );
  }
  Ue(Gs, "onAnimationEnd"), Ue(Ys, "onAnimationIteration"), Ue(Xs, "onAnimationStart"), Ue("dblclick", "onDoubleClick"), Ue("focusin", "onFocus"), Ue("focusout", "onBlur"), Ue(Zm, "onTransitionRun"), Ue(Lm, "onTransitionStart"), Ue(Vm, "onTransitionCancel"), Ue(ws, "onTransitionEnd"), fa("onMouseEnter", ["mouseout", "mouseover"]), fa("onMouseLeave", ["mouseout", "mouseover"]), fa("onPointerEnter", ["pointerout", "pointerover"]), fa("onPointerLeave", ["pointerout", "pointerover"]), Ql(
    "onChange",
    "change click focusin focusout input keydown keyup selectionchange".split(" ")
  ), Ql(
    "onSelect",
    "focusout contextmenu dragend focusin keydown keyup mousedown mouseup selectionchange".split(
      " "
    )
  ), Ql("onBeforeInput", [
    "compositionend",
    "keypress",
    "textInput",
    "paste"
  ]), Ql(
    "onCompositionEnd",
    "compositionend focusout keydown keypress keyup mousedown".split(" ")
  ), Ql(
    "onCompositionStart",
    "compositionstart focusout keydown keypress keyup mousedown".split(" ")
  ), Ql(
    "onCompositionUpdate",
    "compositionupdate focusout keydown keypress keyup mousedown".split(" ")
  );
  var Mn = "abort canplay canplaythrough durationchange emptied encrypted ended error loadeddata loadedmetadata loadstart pause play playing progress ratechange resize seeked seeking stalled suspend timeupdate volumechange waiting".split(
    " "
  ), Dy = new Set(
    "beforetoggle cancel close invalid load scroll scrollend toggle".split(" ").concat(Mn)
  );
  function od(t, e) {
    e = (e & 4) !== 0;
    for (var l = 0; l < t.length; l++) {
      var a = t[l], n = a.event;
      a = a.listeners;
      t: {
        var u = void 0;
        if (e)
          for (var c = a.length - 1; 0 <= c; c--) {
            var s = a[c], d = s.instance, g = s.currentTarget;
            if (s = s.listener, d !== u && n.isPropagationStopped())
              break t;
            u = s, n.currentTarget = g;
            try {
              u(n);
            } catch (E) {
              lu(E);
            }
            n.currentTarget = null, u = d;
          }
        else
          for (c = 0; c < a.length; c++) {
            if (s = a[c], d = s.instance, g = s.currentTarget, s = s.listener, d !== u && n.isPropagationStopped())
              break t;
            u = s, n.currentTarget = g;
            try {
              u(n);
            } catch (E) {
              lu(E);
            }
            n.currentTarget = null, u = d;
          }
      }
    }
  }
  function at(t, e) {
    var l = e[pi];
    l === void 0 && (l = e[pi] = /* @__PURE__ */ new Set());
    var a = t + "__bubble";
    l.has(a) || (rd(e, t, 2, !1), l.add(a));
  }
  function ff(t, e, l) {
    var a = 0;
    e && (a |= 4), rd(
      l,
      t,
      a,
      e
    );
  }
  var wu = "_reactListening" + Math.random().toString(36).slice(2);
  function sf(t) {
    if (!t[wu]) {
      t[wu] = !0, as.forEach(function(l) {
        l !== "selectionchange" && (Dy.has(l) || ff(l, !1, t), ff(l, !0, t));
      });
      var e = t.nodeType === 9 ? t : t.ownerDocument;
      e === null || e[wu] || (e[wu] = !0, ff("selectionchange", !1, e));
    }
  }
  function rd(t, e, l, a) {
    switch (Yd(e)) {
      case 2:
        var n = lv;
        break;
      case 8:
        n = av;
        break;
      default:
        n = Ef;
    }
    l = n.bind(
      null,
      e,
      l,
      t
    ), n = void 0, !Di || e !== "touchstart" && e !== "touchmove" && e !== "wheel" || (n = !0), a ? n !== void 0 ? t.addEventListener(e, l, {
      capture: !0,
      passive: n
    }) : t.addEventListener(e, l, !0) : n !== void 0 ? t.addEventListener(e, l, {
      passive: n
    }) : t.addEventListener(e, l, !1);
  }
  function of(t, e, l, a, n) {
    var u = a;
    if ((e & 1) === 0 && (e & 2) === 0 && a !== null)
      t: for (; ; ) {
        if (a === null) return;
        var c = a.tag;
        if (c === 3 || c === 4) {
          var s = a.stateNode.containerInfo;
          if (s === n) break;
          if (c === 4)
            for (c = a.return; c !== null; ) {
              var d = c.tag;
              if ((d === 3 || d === 4) && c.stateNode.containerInfo === n)
                return;
              c = c.return;
            }
          for (; s !== null; ) {
            if (c = ua(s), c === null) return;
            if (d = c.tag, d === 5 || d === 6 || d === 26 || d === 27) {
              a = u = c;
              continue t;
            }
            s = s.parentNode;
          }
        }
        a = a.return;
      }
    ys(function() {
      var g = u, E = Mi(l), _ = [];
      t: {
        var b = Zs.get(t);
        if (b !== void 0) {
          var z = Pn, B = t;
          switch (t) {
            case "keypress":
              if ($n(l) === 0) break t;
            case "keydown":
            case "keyup":
              z = zm;
              break;
            case "focusin":
              B = "focus", z = Ri;
              break;
            case "focusout":
              B = "blur", z = Ri;
              break;
            case "beforeblur":
            case "afterblur":
              z = Ri;
              break;
            case "click":
              if (l.button === 2) break t;
            case "auxclick":
            case "dblclick":
            case "mousedown":
            case "mousemove":
            case "mouseup":
            case "mouseout":
            case "mouseover":
            case "contextmenu":
              z = bs;
              break;
            case "drag":
            case "dragend":
            case "dragenter":
            case "dragexit":
            case "dragleave":
            case "dragover":
            case "dragstart":
            case "drop":
              z = sm;
              break;
            case "touchcancel":
            case "touchend":
            case "touchmove":
            case "touchstart":
              z = Em;
              break;
            case Gs:
            case Ys:
            case Xs:
              z = dm;
              break;
            case ws:
              z = Mm;
              break;
            case "scroll":
            case "scrollend":
              z = cm;
              break;
            case "wheel":
              z = Dm;
              break;
            case "copy":
            case "cut":
            case "paste":
              z = mm;
              break;
            case "gotpointercapture":
            case "lostpointercapture":
            case "pointercancel":
            case "pointerdown":
            case "pointermove":
            case "pointerout":
            case "pointerover":
            case "pointerup":
              z = Ss;
              break;
            case "toggle":
            case "beforetoggle":
              z = Cm;
          }
          var K = (e & 4) !== 0, St = !K && (t === "scroll" || t === "scrollend"), y = K ? b !== null ? b + "Capture" : null : b;
          K = [];
          for (var h = g, v; h !== null; ) {
            var M = h;
            if (v = M.stateNode, M = M.tag, M !== 5 && M !== 26 && M !== 27 || v === null || y === null || (M = Ja(h, y), M != null && K.push(
              _n(h, M, v)
            )), St) break;
            h = h.return;
          }
          0 < K.length && (b = new z(
            b,
            B,
            null,
            l,
            E
          ), _.push({ event: b, listeners: K }));
        }
      }
      if ((e & 7) === 0) {
        t: {
          if (b = t === "mouseover" || t === "pointerover", z = t === "mouseout" || t === "pointerout", b && l !== Oi && (B = l.relatedTarget || l.fromElement) && (ua(B) || B[na]))
            break t;
          if ((z || b) && (b = E.window === E ? E : (b = E.ownerDocument) ? b.defaultView || b.parentWindow : window, z ? (B = l.relatedTarget || l.toElement, z = g, B = B ? ua(B) : null, B !== null && (St = O(B), K = B.tag, B !== St || K !== 5 && K !== 27 && K !== 6) && (B = null)) : (z = null, B = g), z !== B)) {
            if (K = bs, M = "onMouseLeave", y = "onMouseEnter", h = "mouse", (t === "pointerout" || t === "pointerover") && (K = Ss, M = "onPointerLeave", y = "onPointerEnter", h = "pointer"), St = z == null ? b : Ka(z), v = B == null ? b : Ka(B), b = new K(
              M,
              h + "leave",
              z,
              l,
              E
            ), b.target = St, b.relatedTarget = v, M = null, ua(E) === g && (K = new K(
              y,
              h + "enter",
              B,
              l,
              E
            ), K.target = v, K.relatedTarget = St, M = K), St = M, z && B)
              e: {
                for (K = xy, y = z, h = B, v = 0, M = y; M; M = K(M))
                  v++;
                M = 0;
                for (var Z = h; Z; Z = K(Z))
                  M++;
                for (; 0 < v - M; )
                  y = K(y), v--;
                for (; 0 < M - v; )
                  h = K(h), M--;
                for (; v--; ) {
                  if (y === h || h !== null && y === h.alternate) {
                    K = y;
                    break e;
                  }
                  y = K(y), h = K(h);
                }
                K = null;
              }
            else K = null;
            z !== null && dd(
              _,
              b,
              z,
              K,
              !1
            ), B !== null && St !== null && dd(
              _,
              St,
              B,
              K,
              !0
            );
          }
        }
        t: {
          if (b = g ? Ka(g) : window, z = b.nodeName && b.nodeName.toLowerCase(), z === "select" || z === "input" && b.type === "file")
            var dt = Ds;
          else if (Ms(b))
            if (xs)
              dt = Ym;
            else {
              dt = Qm;
              var X = Bm;
            }
          else
            z = b.nodeName, !z || z.toLowerCase() !== "input" || b.type !== "checkbox" && b.type !== "radio" ? g && Ei(g.elementType) && (dt = Ds) : dt = Gm;
          if (dt && (dt = dt(t, g))) {
            _s(
              _,
              dt,
              l,
              E
            );
            break t;
          }
          X && X(t, b, g), t === "focusout" && g && b.type === "number" && g.memoizedProps.value != null && Ai(b, "number", b.value);
        }
        switch (X = g ? Ka(g) : window, t) {
          case "focusin":
            (Ms(X) || X.contentEditable === "true") && (ma = X, Qi = g, en = null);
            break;
          case "focusout":
            en = Qi = ma = null;
            break;
          case "mousedown":
            Gi = !0;
            break;
          case "contextmenu":
          case "mouseup":
          case "dragend":
            Gi = !1, Bs(_, l, E);
            break;
          case "selectionchange":
            if (wm) break;
          case "keydown":
          case "keyup":
            Bs(_, l, E);
        }
        var P;
        if (Hi)
          t: {
            switch (t) {
              case "compositionstart":
                var it = "onCompositionStart";
                break t;
              case "compositionend":
                it = "onCompositionEnd";
                break t;
              case "compositionupdate":
                it = "onCompositionUpdate";
                break t;
            }
            it = void 0;
          }
        else
          ha ? Es(t, l) && (it = "onCompositionEnd") : t === "keydown" && l.keyCode === 229 && (it = "onCompositionStart");
        it && (zs && l.locale !== "ko" && (ha || it !== "onCompositionStart" ? it === "onCompositionEnd" && ha && (P = vs()) : (rl = E, xi = "value" in rl ? rl.value : rl.textContent, ha = !0)), X = Zu(g, it), 0 < X.length && (it = new ps(
          it,
          t,
          null,
          l,
          E
        ), _.push({ event: it, listeners: X }), P ? it.data = P : (P = Os(l), P !== null && (it.data = P)))), (P = Rm ? Nm(t, l) : Hm(t, l)) && (it = Zu(g, "onBeforeInput"), 0 < it.length && (X = new ps(
          "onBeforeInput",
          "beforeinput",
          null,
          l,
          E
        ), _.push({
          event: X,
          listeners: it
        }), X.data = P)), Oy(
          _,
          t,
          g,
          l,
          E
        );
      }
      od(_, e);
    });
  }
  function _n(t, e, l) {
    return {
      instance: t,
      listener: e,
      currentTarget: l
    };
  }
  function Zu(t, e) {
    for (var l = e + "Capture", a = []; t !== null; ) {
      var n = t, u = n.stateNode;
      if (n = n.tag, n !== 5 && n !== 26 && n !== 27 || u === null || (n = Ja(t, l), n != null && a.unshift(
        _n(t, n, u)
      ), n = Ja(t, e), n != null && a.push(
        _n(t, n, u)
      )), t.tag === 3) return a;
      t = t.return;
    }
    return [];
  }
  function xy(t) {
    if (t === null) return null;
    do
      t = t.return;
    while (t && t.tag !== 5 && t.tag !== 27);
    return t || null;
  }
  function dd(t, e, l, a, n) {
    for (var u = e._reactName, c = []; l !== null && l !== a; ) {
      var s = l, d = s.alternate, g = s.stateNode;
      if (s = s.tag, d !== null && d === a) break;
      s !== 5 && s !== 26 && s !== 27 || g === null || (d = g, n ? (g = Ja(l, u), g != null && c.unshift(
        _n(l, g, d)
      )) : n || (g = Ja(l, u), g != null && c.push(
        _n(l, g, d)
      ))), l = l.return;
    }
    c.length !== 0 && t.push({ event: e, listeners: c });
  }
  var Cy = /\r\n?/g, Uy = /\u0000|\uFFFD/g;
  function hd(t) {
    return (typeof t == "string" ? t : "" + t).replace(Cy, `
`).replace(Uy, "");
  }
  function md(t, e) {
    return e = hd(e), hd(t) === e;
  }
  function pt(t, e, l, a, n, u) {
    switch (l) {
      case "children":
        typeof a == "string" ? e === "body" || e === "textarea" && a === "" || oa(t, a) : (typeof a == "number" || typeof a == "bigint") && e !== "body" && oa(t, "" + a);
        break;
      case "className":
        Jn(t, "class", a);
        break;
      case "tabIndex":
        Jn(t, "tabindex", a);
        break;
      case "dir":
      case "role":
      case "viewBox":
      case "width":
      case "height":
        Jn(t, l, a);
        break;
      case "style":
        hs(t, a, u);
        break;
      case "data":
        if (e !== "object") {
          Jn(t, "data", a);
          break;
        }
      case "src":
      case "href":
        if (a === "" && (e !== "a" || l !== "href")) {
          t.removeAttribute(l);
          break;
        }
        if (a == null || typeof a == "function" || typeof a == "symbol" || typeof a == "boolean") {
          t.removeAttribute(l);
          break;
        }
        a = Fn("" + a), t.setAttribute(l, a);
        break;
      case "action":
      case "formAction":
        if (typeof a == "function") {
          t.setAttribute(
            l,
            "javascript:throw new Error('A React form was unexpectedly submitted. If you called form.submit() manually, consider using form.requestSubmit() instead. If you\\'re trying to use event.stopPropagation() in a submit event handler, consider also calling event.preventDefault().')"
          );
          break;
        } else
          typeof u == "function" && (l === "formAction" ? (e !== "input" && pt(t, e, "name", n.name, n, null), pt(
            t,
            e,
            "formEncType",
            n.formEncType,
            n,
            null
          ), pt(
            t,
            e,
            "formMethod",
            n.formMethod,
            n,
            null
          ), pt(
            t,
            e,
            "formTarget",
            n.formTarget,
            n,
            null
          )) : (pt(t, e, "encType", n.encType, n, null), pt(t, e, "method", n.method, n, null), pt(t, e, "target", n.target, n, null)));
        if (a == null || typeof a == "symbol" || typeof a == "boolean") {
          t.removeAttribute(l);
          break;
        }
        a = Fn("" + a), t.setAttribute(l, a);
        break;
      case "onClick":
        a != null && (t.onclick = Ze);
        break;
      case "onScroll":
        a != null && at("scroll", t);
        break;
      case "onScrollEnd":
        a != null && at("scrollend", t);
        break;
      case "dangerouslySetInnerHTML":
        if (a != null) {
          if (typeof a != "object" || !("__html" in a))
            throw Error(o(61));
          if (l = a.__html, l != null) {
            if (n.children != null) throw Error(o(60));
            t.innerHTML = l;
          }
        }
        break;
      case "multiple":
        t.multiple = a && typeof a != "function" && typeof a != "symbol";
        break;
      case "muted":
        t.muted = a && typeof a != "function" && typeof a != "symbol";
        break;
      case "suppressContentEditableWarning":
      case "suppressHydrationWarning":
      case "defaultValue":
      case "defaultChecked":
      case "innerHTML":
      case "ref":
        break;
      case "autoFocus":
        break;
      case "xlinkHref":
        if (a == null || typeof a == "function" || typeof a == "boolean" || typeof a == "symbol") {
          t.removeAttribute("xlink:href");
          break;
        }
        l = Fn("" + a), t.setAttributeNS(
          "http://www.w3.org/1999/xlink",
          "xlink:href",
          l
        );
        break;
      case "contentEditable":
      case "spellCheck":
      case "draggable":
      case "value":
      case "autoReverse":
      case "externalResourcesRequired":
      case "focusable":
      case "preserveAlpha":
        a != null && typeof a != "function" && typeof a != "symbol" ? t.setAttribute(l, "" + a) : t.removeAttribute(l);
        break;
      case "inert":
      case "allowFullScreen":
      case "async":
      case "autoPlay":
      case "controls":
      case "default":
      case "defer":
      case "disabled":
      case "disablePictureInPicture":
      case "disableRemotePlayback":
      case "formNoValidate":
      case "hidden":
      case "loop":
      case "noModule":
      case "noValidate":
      case "open":
      case "playsInline":
      case "readOnly":
      case "required":
      case "reversed":
      case "scoped":
      case "seamless":
      case "itemScope":
        a && typeof a != "function" && typeof a != "symbol" ? t.setAttribute(l, "") : t.removeAttribute(l);
        break;
      case "capture":
      case "download":
        a === !0 ? t.setAttribute(l, "") : a !== !1 && a != null && typeof a != "function" && typeof a != "symbol" ? t.setAttribute(l, a) : t.removeAttribute(l);
        break;
      case "cols":
      case "rows":
      case "size":
      case "span":
        a != null && typeof a != "function" && typeof a != "symbol" && !isNaN(a) && 1 <= a ? t.setAttribute(l, a) : t.removeAttribute(l);
        break;
      case "rowSpan":
      case "start":
        a == null || typeof a == "function" || typeof a == "symbol" || isNaN(a) ? t.removeAttribute(l) : t.setAttribute(l, a);
        break;
      case "popover":
        at("beforetoggle", t), at("toggle", t), Kn(t, "popover", a);
        break;
      case "xlinkActuate":
        we(
          t,
          "http://www.w3.org/1999/xlink",
          "xlink:actuate",
          a
        );
        break;
      case "xlinkArcrole":
        we(
          t,
          "http://www.w3.org/1999/xlink",
          "xlink:arcrole",
          a
        );
        break;
      case "xlinkRole":
        we(
          t,
          "http://www.w3.org/1999/xlink",
          "xlink:role",
          a
        );
        break;
      case "xlinkShow":
        we(
          t,
          "http://www.w3.org/1999/xlink",
          "xlink:show",
          a
        );
        break;
      case "xlinkTitle":
        we(
          t,
          "http://www.w3.org/1999/xlink",
          "xlink:title",
          a
        );
        break;
      case "xlinkType":
        we(
          t,
          "http://www.w3.org/1999/xlink",
          "xlink:type",
          a
        );
        break;
      case "xmlBase":
        we(
          t,
          "http://www.w3.org/XML/1998/namespace",
          "xml:base",
          a
        );
        break;
      case "xmlLang":
        we(
          t,
          "http://www.w3.org/XML/1998/namespace",
          "xml:lang",
          a
        );
        break;
      case "xmlSpace":
        we(
          t,
          "http://www.w3.org/XML/1998/namespace",
          "xml:space",
          a
        );
        break;
      case "is":
        Kn(t, "is", a);
        break;
      case "innerText":
      case "textContent":
        break;
      default:
        (!(2 < l.length) || l[0] !== "o" && l[0] !== "O" || l[1] !== "n" && l[1] !== "N") && (l = um.get(l) || l, Kn(t, l, a));
    }
  }
  function rf(t, e, l, a, n, u) {
    switch (l) {
      case "style":
        hs(t, a, u);
        break;
      case "dangerouslySetInnerHTML":
        if (a != null) {
          if (typeof a != "object" || !("__html" in a))
            throw Error(o(61));
          if (l = a.__html, l != null) {
            if (n.children != null) throw Error(o(60));
            t.innerHTML = l;
          }
        }
        break;
      case "children":
        typeof a == "string" ? oa(t, a) : (typeof a == "number" || typeof a == "bigint") && oa(t, "" + a);
        break;
      case "onScroll":
        a != null && at("scroll", t);
        break;
      case "onScrollEnd":
        a != null && at("scrollend", t);
        break;
      case "onClick":
        a != null && (t.onclick = Ze);
        break;
      case "suppressContentEditableWarning":
      case "suppressHydrationWarning":
      case "innerHTML":
      case "ref":
        break;
      case "innerText":
      case "textContent":
        break;
      default:
        if (!ns.hasOwnProperty(l))
          t: {
            if (l[0] === "o" && l[1] === "n" && (n = l.endsWith("Capture"), e = l.slice(2, n ? l.length - 7 : void 0), u = t[ee] || null, u = u != null ? u[l] : null, typeof u == "function" && t.removeEventListener(e, u, n), typeof a == "function")) {
              typeof u != "function" && u !== null && (l in t ? t[l] = null : t.hasAttribute(l) && t.removeAttribute(l)), t.addEventListener(e, a, n);
              break t;
            }
            l in t ? t[l] = a : a === !0 ? t.setAttribute(l, "") : Kn(t, l, a);
          }
    }
  }
  function $t(t, e, l) {
    switch (e) {
      case "div":
      case "span":
      case "svg":
      case "path":
      case "a":
      case "g":
      case "p":
      case "li":
        break;
      case "img":
        at("error", t), at("load", t);
        var a = !1, n = !1, u;
        for (u in l)
          if (l.hasOwnProperty(u)) {
            var c = l[u];
            if (c != null)
              switch (u) {
                case "src":
                  a = !0;
                  break;
                case "srcSet":
                  n = !0;
                  break;
                case "children":
                case "dangerouslySetInnerHTML":
                  throw Error(o(137, e));
                default:
                  pt(t, e, u, c, l, null);
              }
          }
        n && pt(t, e, "srcSet", l.srcSet, l, null), a && pt(t, e, "src", l.src, l, null);
        return;
      case "input":
        at("invalid", t);
        var s = u = c = n = null, d = null, g = null;
        for (a in l)
          if (l.hasOwnProperty(a)) {
            var E = l[a];
            if (E != null)
              switch (a) {
                case "name":
                  n = E;
                  break;
                case "type":
                  c = E;
                  break;
                case "checked":
                  d = E;
                  break;
                case "defaultChecked":
                  g = E;
                  break;
                case "value":
                  u = E;
                  break;
                case "defaultValue":
                  s = E;
                  break;
                case "children":
                case "dangerouslySetInnerHTML":
                  if (E != null)
                    throw Error(o(137, e));
                  break;
                default:
                  pt(t, e, a, E, l, null);
              }
          }
        ss(
          t,
          u,
          s,
          d,
          g,
          c,
          n,
          !1
        );
        return;
      case "select":
        at("invalid", t), a = c = u = null;
        for (n in l)
          if (l.hasOwnProperty(n) && (s = l[n], s != null))
            switch (n) {
              case "value":
                u = s;
                break;
              case "defaultValue":
                c = s;
                break;
              case "multiple":
                a = s;
              default:
                pt(t, e, n, s, l, null);
            }
        e = u, l = c, t.multiple = !!a, e != null ? sa(t, !!a, e, !1) : l != null && sa(t, !!a, l, !0);
        return;
      case "textarea":
        at("invalid", t), u = n = a = null;
        for (c in l)
          if (l.hasOwnProperty(c) && (s = l[c], s != null))
            switch (c) {
              case "value":
                a = s;
                break;
              case "defaultValue":
                n = s;
                break;
              case "children":
                u = s;
                break;
              case "dangerouslySetInnerHTML":
                if (s != null) throw Error(o(91));
                break;
              default:
                pt(t, e, c, s, l, null);
            }
        rs(t, a, n, u);
        return;
      case "option":
        for (d in l)
          l.hasOwnProperty(d) && (a = l[d], a != null) && (d === "selected" ? t.selected = a && typeof a != "function" && typeof a != "symbol" : pt(t, e, d, a, l, null));
        return;
      case "dialog":
        at("beforetoggle", t), at("toggle", t), at("cancel", t), at("close", t);
        break;
      case "iframe":
      case "object":
        at("load", t);
        break;
      case "video":
      case "audio":
        for (a = 0; a < Mn.length; a++)
          at(Mn[a], t);
        break;
      case "image":
        at("error", t), at("load", t);
        break;
      case "details":
        at("toggle", t);
        break;
      case "embed":
      case "source":
      case "link":
        at("error", t), at("load", t);
      case "area":
      case "base":
      case "br":
      case "col":
      case "hr":
      case "keygen":
      case "meta":
      case "param":
      case "track":
      case "wbr":
      case "menuitem":
        for (g in l)
          if (l.hasOwnProperty(g) && (a = l[g], a != null))
            switch (g) {
              case "children":
              case "dangerouslySetInnerHTML":
                throw Error(o(137, e));
              default:
                pt(t, e, g, a, l, null);
            }
        return;
      default:
        if (Ei(e)) {
          for (E in l)
            l.hasOwnProperty(E) && (a = l[E], a !== void 0 && rf(
              t,
              e,
              E,
              a,
              l,
              void 0
            ));
          return;
        }
    }
    for (s in l)
      l.hasOwnProperty(s) && (a = l[s], a != null && pt(t, e, s, a, l, null));
  }
  function Ry(t, e, l, a) {
    switch (e) {
      case "div":
      case "span":
      case "svg":
      case "path":
      case "a":
      case "g":
      case "p":
      case "li":
        break;
      case "input":
        var n = null, u = null, c = null, s = null, d = null, g = null, E = null;
        for (z in l) {
          var _ = l[z];
          if (l.hasOwnProperty(z) && _ != null)
            switch (z) {
              case "checked":
                break;
              case "value":
                break;
              case "defaultValue":
                d = _;
              default:
                a.hasOwnProperty(z) || pt(t, e, z, null, a, _);
            }
        }
        for (var b in a) {
          var z = a[b];
          if (_ = l[b], a.hasOwnProperty(b) && (z != null || _ != null))
            switch (b) {
              case "type":
                u = z;
                break;
              case "name":
                n = z;
                break;
              case "checked":
                g = z;
                break;
              case "defaultChecked":
                E = z;
                break;
              case "value":
                c = z;
                break;
              case "defaultValue":
                s = z;
                break;
              case "children":
              case "dangerouslySetInnerHTML":
                if (z != null)
                  throw Error(o(137, e));
                break;
              default:
                z !== _ && pt(
                  t,
                  e,
                  b,
                  z,
                  a,
                  _
                );
            }
        }
        Ti(
          t,
          c,
          s,
          d,
          g,
          E,
          u,
          n
        );
        return;
      case "select":
        z = c = s = b = null;
        for (u in l)
          if (d = l[u], l.hasOwnProperty(u) && d != null)
            switch (u) {
              case "value":
                break;
              case "multiple":
                z = d;
              default:
                a.hasOwnProperty(u) || pt(
                  t,
                  e,
                  u,
                  null,
                  a,
                  d
                );
            }
        for (n in a)
          if (u = a[n], d = l[n], a.hasOwnProperty(n) && (u != null || d != null))
            switch (n) {
              case "value":
                b = u;
                break;
              case "defaultValue":
                s = u;
                break;
              case "multiple":
                c = u;
              default:
                u !== d && pt(
                  t,
                  e,
                  n,
                  u,
                  a,
                  d
                );
            }
        e = s, l = c, a = z, b != null ? sa(t, !!l, b, !1) : !!a != !!l && (e != null ? sa(t, !!l, e, !0) : sa(t, !!l, l ? [] : "", !1));
        return;
      case "textarea":
        z = b = null;
        for (s in l)
          if (n = l[s], l.hasOwnProperty(s) && n != null && !a.hasOwnProperty(s))
            switch (s) {
              case "value":
                break;
              case "children":
                break;
              default:
                pt(t, e, s, null, a, n);
            }
        for (c in a)
          if (n = a[c], u = l[c], a.hasOwnProperty(c) && (n != null || u != null))
            switch (c) {
              case "value":
                b = n;
                break;
              case "defaultValue":
                z = n;
                break;
              case "children":
                break;
              case "dangerouslySetInnerHTML":
                if (n != null) throw Error(o(91));
                break;
              default:
                n !== u && pt(t, e, c, n, a, u);
            }
        os(t, b, z);
        return;
      case "option":
        for (var B in l)
          b = l[B], l.hasOwnProperty(B) && b != null && !a.hasOwnProperty(B) && (B === "selected" ? t.selected = !1 : pt(
            t,
            e,
            B,
            null,
            a,
            b
          ));
        for (d in a)
          b = a[d], z = l[d], a.hasOwnProperty(d) && b !== z && (b != null || z != null) && (d === "selected" ? t.selected = b && typeof b != "function" && typeof b != "symbol" : pt(
            t,
            e,
            d,
            b,
            a,
            z
          ));
        return;
      case "img":
      case "link":
      case "area":
      case "base":
      case "br":
      case "col":
      case "embed":
      case "hr":
      case "keygen":
      case "meta":
      case "param":
      case "source":
      case "track":
      case "wbr":
      case "menuitem":
        for (var K in l)
          b = l[K], l.hasOwnProperty(K) && b != null && !a.hasOwnProperty(K) && pt(t, e, K, null, a, b);
        for (g in a)
          if (b = a[g], z = l[g], a.hasOwnProperty(g) && b !== z && (b != null || z != null))
            switch (g) {
              case "children":
              case "dangerouslySetInnerHTML":
                if (b != null)
                  throw Error(o(137, e));
                break;
              default:
                pt(
                  t,
                  e,
                  g,
                  b,
                  a,
                  z
                );
            }
        return;
      default:
        if (Ei(e)) {
          for (var St in l)
            b = l[St], l.hasOwnProperty(St) && b !== void 0 && !a.hasOwnProperty(St) && rf(
              t,
              e,
              St,
              void 0,
              a,
              b
            );
          for (E in a)
            b = a[E], z = l[E], !a.hasOwnProperty(E) || b === z || b === void 0 && z === void 0 || rf(
              t,
              e,
              E,
              b,
              a,
              z
            );
          return;
        }
    }
    for (var y in l)
      b = l[y], l.hasOwnProperty(y) && b != null && !a.hasOwnProperty(y) && pt(t, e, y, null, a, b);
    for (_ in a)
      b = a[_], z = l[_], !a.hasOwnProperty(_) || b === z || b == null && z == null || pt(t, e, _, b, a, z);
  }
  function yd(t) {
    switch (t) {
      case "css":
      case "script":
      case "font":
      case "img":
      case "image":
      case "input":
      case "link":
        return !0;
      default:
        return !1;
    }
  }
  function Ny() {
    if (typeof performance.getEntriesByType == "function") {
      for (var t = 0, e = 0, l = performance.getEntriesByType("resource"), a = 0; a < l.length; a++) {
        var n = l[a], u = n.transferSize, c = n.initiatorType, s = n.duration;
        if (u && s && yd(c)) {
          for (c = 0, s = n.responseEnd, a += 1; a < l.length; a++) {
            var d = l[a], g = d.startTime;
            if (g > s) break;
            var E = d.transferSize, _ = d.initiatorType;
            E && yd(_) && (d = d.responseEnd, c += E * (d < s ? 1 : (s - g) / (d - g)));
          }
          if (--a, e += 8 * (u + c) / (n.duration / 1e3), t++, 10 < t) break;
        }
      }
      if (0 < t) return e / t / 1e6;
    }
    return navigator.connection && (t = navigator.connection.downlink, typeof t == "number") ? t : 5;
  }
  var df = null, hf = null;
  function Lu(t) {
    return t.nodeType === 9 ? t : t.ownerDocument;
  }
  function vd(t) {
    switch (t) {
      case "http://www.w3.org/2000/svg":
        return 1;
      case "http://www.w3.org/1998/Math/MathML":
        return 2;
      default:
        return 0;
    }
  }
  function gd(t, e) {
    if (t === 0)
      switch (e) {
        case "svg":
          return 1;
        case "math":
          return 2;
        default:
          return 0;
      }
    return t === 1 && e === "foreignObject" ? 0 : t;
  }
  function mf(t, e) {
    return t === "textarea" || t === "noscript" || typeof e.children == "string" || typeof e.children == "number" || typeof e.children == "bigint" || typeof e.dangerouslySetInnerHTML == "object" && e.dangerouslySetInnerHTML !== null && e.dangerouslySetInnerHTML.__html != null;
  }
  var yf = null;
  function Hy() {
    var t = window.event;
    return t && t.type === "popstate" ? t === yf ? !1 : (yf = t, !0) : (yf = null, !1);
  }
  var bd = typeof setTimeout == "function" ? setTimeout : void 0, qy = typeof clearTimeout == "function" ? clearTimeout : void 0, pd = typeof Promise == "function" ? Promise : void 0, jy = typeof queueMicrotask == "function" ? queueMicrotask : typeof pd < "u" ? function(t) {
    return pd.resolve(null).then(t).catch(By);
  } : bd;
  function By(t) {
    setTimeout(function() {
      throw t;
    });
  }
  function Dl(t) {
    return t === "head";
  }
  function Sd(t, e) {
    var l = e, a = 0;
    do {
      var n = l.nextSibling;
      if (t.removeChild(l), n && n.nodeType === 8)
        if (l = n.data, l === "/$" || l === "/&") {
          if (a === 0) {
            t.removeChild(n), Xa(e);
            return;
          }
          a--;
        } else if (l === "$" || l === "$?" || l === "$~" || l === "$!" || l === "&")
          a++;
        else if (l === "html")
          Dn(t.ownerDocument.documentElement);
        else if (l === "head") {
          l = t.ownerDocument.head, Dn(l);
          for (var u = l.firstChild; u; ) {
            var c = u.nextSibling, s = u.nodeName;
            u[Va] || s === "SCRIPT" || s === "STYLE" || s === "LINK" && u.rel.toLowerCase() === "stylesheet" || l.removeChild(u), u = c;
          }
        } else
          l === "body" && Dn(t.ownerDocument.body);
      l = n;
    } while (l);
    Xa(e);
  }
  function zd(t, e) {
    var l = t;
    t = 0;
    do {
      var a = l.nextSibling;
      if (l.nodeType === 1 ? e ? (l._stashedDisplay = l.style.display, l.style.display = "none") : (l.style.display = l._stashedDisplay || "", l.getAttribute("style") === "" && l.removeAttribute("style")) : l.nodeType === 3 && (e ? (l._stashedText = l.nodeValue, l.nodeValue = "") : l.nodeValue = l._stashedText || ""), a && a.nodeType === 8)
        if (l = a.data, l === "/$") {
          if (t === 0) break;
          t--;
        } else
          l !== "$" && l !== "$?" && l !== "$~" && l !== "$!" || t++;
      l = a;
    } while (l);
  }
  function vf(t) {
    var e = t.firstChild;
    for (e && e.nodeType === 10 && (e = e.nextSibling); e; ) {
      var l = e;
      switch (e = e.nextSibling, l.nodeName) {
        case "HTML":
        case "HEAD":
        case "BODY":
          vf(l), Si(l);
          continue;
        case "SCRIPT":
        case "STYLE":
          continue;
        case "LINK":
          if (l.rel.toLowerCase() === "stylesheet") continue;
      }
      t.removeChild(l);
    }
  }
  function Qy(t, e, l, a) {
    for (; t.nodeType === 1; ) {
      var n = l;
      if (t.nodeName.toLowerCase() !== e.toLowerCase()) {
        if (!a && (t.nodeName !== "INPUT" || t.type !== "hidden"))
          break;
      } else if (a) {
        if (!t[Va])
          switch (e) {
            case "meta":
              if (!t.hasAttribute("itemprop")) break;
              return t;
            case "link":
              if (u = t.getAttribute("rel"), u === "stylesheet" && t.hasAttribute("data-precedence"))
                break;
              if (u !== n.rel || t.getAttribute("href") !== (n.href == null || n.href === "" ? null : n.href) || t.getAttribute("crossorigin") !== (n.crossOrigin == null ? null : n.crossOrigin) || t.getAttribute("title") !== (n.title == null ? null : n.title))
                break;
              return t;
            case "style":
              if (t.hasAttribute("data-precedence")) break;
              return t;
            case "script":
              if (u = t.getAttribute("src"), (u !== (n.src == null ? null : n.src) || t.getAttribute("type") !== (n.type == null ? null : n.type) || t.getAttribute("crossorigin") !== (n.crossOrigin == null ? null : n.crossOrigin)) && u && t.hasAttribute("async") && !t.hasAttribute("itemprop"))
                break;
              return t;
            default:
              return t;
          }
      } else if (e === "input" && t.type === "hidden") {
        var u = n.name == null ? null : "" + n.name;
        if (n.type === "hidden" && t.getAttribute("name") === u)
          return t;
      } else return t;
      if (t = xe(t.nextSibling), t === null) break;
    }
    return null;
  }
  function Gy(t, e, l) {
    if (e === "") return null;
    for (; t.nodeType !== 3; )
      if ((t.nodeType !== 1 || t.nodeName !== "INPUT" || t.type !== "hidden") && !l || (t = xe(t.nextSibling), t === null)) return null;
    return t;
  }
  function Td(t, e) {
    for (; t.nodeType !== 8; )
      if ((t.nodeType !== 1 || t.nodeName !== "INPUT" || t.type !== "hidden") && !e || (t = xe(t.nextSibling), t === null)) return null;
    return t;
  }
  function gf(t) {
    return t.data === "$?" || t.data === "$~";
  }
  function bf(t) {
    return t.data === "$!" || t.data === "$?" && t.ownerDocument.readyState !== "loading";
  }
  function Yy(t, e) {
    var l = t.ownerDocument;
    if (t.data === "$~") t._reactRetry = e;
    else if (t.data !== "$?" || l.readyState !== "loading")
      e();
    else {
      var a = function() {
        e(), l.removeEventListener("DOMContentLoaded", a);
      };
      l.addEventListener("DOMContentLoaded", a), t._reactRetry = a;
    }
  }
  function xe(t) {
    for (; t != null; t = t.nextSibling) {
      var e = t.nodeType;
      if (e === 1 || e === 3) break;
      if (e === 8) {
        if (e = t.data, e === "$" || e === "$!" || e === "$?" || e === "$~" || e === "&" || e === "F!" || e === "F")
          break;
        if (e === "/$" || e === "/&") return null;
      }
    }
    return t;
  }
  var pf = null;
  function Ad(t) {
    t = t.nextSibling;
    for (var e = 0; t; ) {
      if (t.nodeType === 8) {
        var l = t.data;
        if (l === "/$" || l === "/&") {
          if (e === 0)
            return xe(t.nextSibling);
          e--;
        } else
          l !== "$" && l !== "$!" && l !== "$?" && l !== "$~" && l !== "&" || e++;
      }
      t = t.nextSibling;
    }
    return null;
  }
  function Ed(t) {
    t = t.previousSibling;
    for (var e = 0; t; ) {
      if (t.nodeType === 8) {
        var l = t.data;
        if (l === "$" || l === "$!" || l === "$?" || l === "$~" || l === "&") {
          if (e === 0) return t;
          e--;
        } else l !== "/$" && l !== "/&" || e++;
      }
      t = t.previousSibling;
    }
    return null;
  }
  function Od(t, e, l) {
    switch (e = Lu(l), t) {
      case "html":
        if (t = e.documentElement, !t) throw Error(o(452));
        return t;
      case "head":
        if (t = e.head, !t) throw Error(o(453));
        return t;
      case "body":
        if (t = e.body, !t) throw Error(o(454));
        return t;
      default:
        throw Error(o(451));
    }
  }
  function Dn(t) {
    for (var e = t.attributes; e.length; )
      t.removeAttributeNode(e[0]);
    Si(t);
  }
  var Ce = /* @__PURE__ */ new Map(), Md = /* @__PURE__ */ new Set();
  function Vu(t) {
    return typeof t.getRootNode == "function" ? t.getRootNode() : t.nodeType === 9 ? t : t.ownerDocument;
  }
  var ul = U.d;
  U.d = {
    f: Xy,
    r: wy,
    D: Zy,
    C: Ly,
    L: Vy,
    m: Ky,
    X: ky,
    S: Jy,
    M: Fy
  };
  function Xy() {
    var t = ul.f(), e = ju();
    return t || e;
  }
  function wy(t) {
    var e = ia(t);
    e !== null && e.tag === 5 && e.type === "form" ? Zo(e) : ul.r(t);
  }
  var Qa = typeof document > "u" ? null : document;
  function _d(t, e, l) {
    var a = Qa;
    if (a && typeof e == "string" && e) {
      var n = Te(e);
      n = 'link[rel="' + t + '"][href="' + n + '"]', typeof l == "string" && (n += '[crossorigin="' + l + '"]'), Md.has(n) || (Md.add(n), t = { rel: t, crossOrigin: l, href: e }, a.querySelector(n) === null && (e = a.createElement("link"), $t(e, "link", t), Vt(e), a.head.appendChild(e)));
    }
  }
  function Zy(t) {
    ul.D(t), _d("dns-prefetch", t, null);
  }
  function Ly(t, e) {
    ul.C(t, e), _d("preconnect", t, e);
  }
  function Vy(t, e, l) {
    ul.L(t, e, l);
    var a = Qa;
    if (a && t && e) {
      var n = 'link[rel="preload"][as="' + Te(e) + '"]';
      e === "image" && l && l.imageSrcSet ? (n += '[imagesrcset="' + Te(
        l.imageSrcSet
      ) + '"]', typeof l.imageSizes == "string" && (n += '[imagesizes="' + Te(
        l.imageSizes
      ) + '"]')) : n += '[href="' + Te(t) + '"]';
      var u = n;
      switch (e) {
        case "style":
          u = Ga(t);
          break;
        case "script":
          u = Ya(t);
      }
      Ce.has(u) || (t = H(
        {
          rel: "preload",
          href: e === "image" && l && l.imageSrcSet ? void 0 : t,
          as: e
        },
        l
      ), Ce.set(u, t), a.querySelector(n) !== null || e === "style" && a.querySelector(xn(u)) || e === "script" && a.querySelector(Cn(u)) || (e = a.createElement("link"), $t(e, "link", t), Vt(e), a.head.appendChild(e)));
    }
  }
  function Ky(t, e) {
    ul.m(t, e);
    var l = Qa;
    if (l && t) {
      var a = e && typeof e.as == "string" ? e.as : "script", n = 'link[rel="modulepreload"][as="' + Te(a) + '"][href="' + Te(t) + '"]', u = n;
      switch (a) {
        case "audioworklet":
        case "paintworklet":
        case "serviceworker":
        case "sharedworker":
        case "worker":
        case "script":
          u = Ya(t);
      }
      if (!Ce.has(u) && (t = H({ rel: "modulepreload", href: t }, e), Ce.set(u, t), l.querySelector(n) === null)) {
        switch (a) {
          case "audioworklet":
          case "paintworklet":
          case "serviceworker":
          case "sharedworker":
          case "worker":
          case "script":
            if (l.querySelector(Cn(u)))
              return;
        }
        a = l.createElement("link"), $t(a, "link", t), Vt(a), l.head.appendChild(a);
      }
    }
  }
  function Jy(t, e, l) {
    ul.S(t, e, l);
    var a = Qa;
    if (a && t) {
      var n = ca(a).hoistableStyles, u = Ga(t);
      e = e || "default";
      var c = n.get(u);
      if (!c) {
        var s = { loading: 0, preload: null };
        if (c = a.querySelector(
          xn(u)
        ))
          s.loading = 5;
        else {
          t = H(
            { rel: "stylesheet", href: t, "data-precedence": e },
            l
          ), (l = Ce.get(u)) && Sf(t, l);
          var d = c = a.createElement("link");
          Vt(d), $t(d, "link", t), d._p = new Promise(function(g, E) {
            d.onload = g, d.onerror = E;
          }), d.addEventListener("load", function() {
            s.loading |= 1;
          }), d.addEventListener("error", function() {
            s.loading |= 2;
          }), s.loading |= 4, Ku(c, e, a);
        }
        c = {
          type: "stylesheet",
          instance: c,
          count: 1,
          state: s
        }, n.set(u, c);
      }
    }
  }
  function ky(t, e) {
    ul.X(t, e);
    var l = Qa;
    if (l && t) {
      var a = ca(l).hoistableScripts, n = Ya(t), u = a.get(n);
      u || (u = l.querySelector(Cn(n)), u || (t = H({ src: t, async: !0 }, e), (e = Ce.get(n)) && zf(t, e), u = l.createElement("script"), Vt(u), $t(u, "link", t), l.head.appendChild(u)), u = {
        type: "script",
        instance: u,
        count: 1,
        state: null
      }, a.set(n, u));
    }
  }
  function Fy(t, e) {
    ul.M(t, e);
    var l = Qa;
    if (l && t) {
      var a = ca(l).hoistableScripts, n = Ya(t), u = a.get(n);
      u || (u = l.querySelector(Cn(n)), u || (t = H({ src: t, async: !0, type: "module" }, e), (e = Ce.get(n)) && zf(t, e), u = l.createElement("script"), Vt(u), $t(u, "link", t), l.head.appendChild(u)), u = {
        type: "script",
        instance: u,
        count: 1,
        state: null
      }, a.set(n, u));
    }
  }
  function Dd(t, e, l, a) {
    var n = (n = L.current) ? Vu(n) : null;
    if (!n) throw Error(o(446));
    switch (t) {
      case "meta":
      case "title":
        return null;
      case "style":
        return typeof l.precedence == "string" && typeof l.href == "string" ? (e = Ga(l.href), l = ca(
          n
        ).hoistableStyles, a = l.get(e), a || (a = {
          type: "style",
          instance: null,
          count: 0,
          state: null
        }, l.set(e, a)), a) : { type: "void", instance: null, count: 0, state: null };
      case "link":
        if (l.rel === "stylesheet" && typeof l.href == "string" && typeof l.precedence == "string") {
          t = Ga(l.href);
          var u = ca(
            n
          ).hoistableStyles, c = u.get(t);
          if (c || (n = n.ownerDocument || n, c = {
            type: "stylesheet",
            instance: null,
            count: 0,
            state: { loading: 0, preload: null }
          }, u.set(t, c), (u = n.querySelector(
            xn(t)
          )) && !u._p && (c.instance = u, c.state.loading = 5), Ce.has(t) || (l = {
            rel: "preload",
            as: "style",
            href: l.href,
            crossOrigin: l.crossOrigin,
            integrity: l.integrity,
            media: l.media,
            hrefLang: l.hrefLang,
            referrerPolicy: l.referrerPolicy
          }, Ce.set(t, l), u || Wy(
            n,
            t,
            l,
            c.state
          ))), e && a === null)
            throw Error(o(528, ""));
          return c;
        }
        if (e && a !== null)
          throw Error(o(529, ""));
        return null;
      case "script":
        return e = l.async, l = l.src, typeof l == "string" && e && typeof e != "function" && typeof e != "symbol" ? (e = Ya(l), l = ca(
          n
        ).hoistableScripts, a = l.get(e), a || (a = {
          type: "script",
          instance: null,
          count: 0,
          state: null
        }, l.set(e, a)), a) : { type: "void", instance: null, count: 0, state: null };
      default:
        throw Error(o(444, t));
    }
  }
  function Ga(t) {
    return 'href="' + Te(t) + '"';
  }
  function xn(t) {
    return 'link[rel="stylesheet"][' + t + "]";
  }
  function xd(t) {
    return H({}, t, {
      "data-precedence": t.precedence,
      precedence: null
    });
  }
  function Wy(t, e, l, a) {
    t.querySelector('link[rel="preload"][as="style"][' + e + "]") ? a.loading = 1 : (e = t.createElement("link"), a.preload = e, e.addEventListener("load", function() {
      return a.loading |= 1;
    }), e.addEventListener("error", function() {
      return a.loading |= 2;
    }), $t(e, "link", l), Vt(e), t.head.appendChild(e));
  }
  function Ya(t) {
    return '[src="' + Te(t) + '"]';
  }
  function Cn(t) {
    return "script[async]" + t;
  }
  function Cd(t, e, l) {
    if (e.count++, e.instance === null)
      switch (e.type) {
        case "style":
          var a = t.querySelector(
            'style[data-href~="' + Te(l.href) + '"]'
          );
          if (a)
            return e.instance = a, Vt(a), a;
          var n = H({}, l, {
            "data-href": l.href,
            "data-precedence": l.precedence,
            href: null,
            precedence: null
          });
          return a = (t.ownerDocument || t).createElement(
            "style"
          ), Vt(a), $t(a, "style", n), Ku(a, l.precedence, t), e.instance = a;
        case "stylesheet":
          n = Ga(l.href);
          var u = t.querySelector(
            xn(n)
          );
          if (u)
            return e.state.loading |= 4, e.instance = u, Vt(u), u;
          a = xd(l), (n = Ce.get(n)) && Sf(a, n), u = (t.ownerDocument || t).createElement("link"), Vt(u);
          var c = u;
          return c._p = new Promise(function(s, d) {
            c.onload = s, c.onerror = d;
          }), $t(u, "link", a), e.state.loading |= 4, Ku(u, l.precedence, t), e.instance = u;
        case "script":
          return u = Ya(l.src), (n = t.querySelector(
            Cn(u)
          )) ? (e.instance = n, Vt(n), n) : (a = l, (n = Ce.get(u)) && (a = H({}, l), zf(a, n)), t = t.ownerDocument || t, n = t.createElement("script"), Vt(n), $t(n, "link", a), t.head.appendChild(n), e.instance = n);
        case "void":
          return null;
        default:
          throw Error(o(443, e.type));
      }
    else
      e.type === "stylesheet" && (e.state.loading & 4) === 0 && (a = e.instance, e.state.loading |= 4, Ku(a, l.precedence, t));
    return e.instance;
  }
  function Ku(t, e, l) {
    for (var a = l.querySelectorAll(
      'link[rel="stylesheet"][data-precedence],style[data-precedence]'
    ), n = a.length ? a[a.length - 1] : null, u = n, c = 0; c < a.length; c++) {
      var s = a[c];
      if (s.dataset.precedence === e) u = s;
      else if (u !== n) break;
    }
    u ? u.parentNode.insertBefore(t, u.nextSibling) : (e = l.nodeType === 9 ? l.head : l, e.insertBefore(t, e.firstChild));
  }
  function Sf(t, e) {
    t.crossOrigin == null && (t.crossOrigin = e.crossOrigin), t.referrerPolicy == null && (t.referrerPolicy = e.referrerPolicy), t.title == null && (t.title = e.title);
  }
  function zf(t, e) {
    t.crossOrigin == null && (t.crossOrigin = e.crossOrigin), t.referrerPolicy == null && (t.referrerPolicy = e.referrerPolicy), t.integrity == null && (t.integrity = e.integrity);
  }
  var Ju = null;
  function Ud(t, e, l) {
    if (Ju === null) {
      var a = /* @__PURE__ */ new Map(), n = Ju = /* @__PURE__ */ new Map();
      n.set(l, a);
    } else
      n = Ju, a = n.get(l), a || (a = /* @__PURE__ */ new Map(), n.set(l, a));
    if (a.has(t)) return a;
    for (a.set(t, null), l = l.getElementsByTagName(t), n = 0; n < l.length; n++) {
      var u = l[n];
      if (!(u[Va] || u[Jt] || t === "link" && u.getAttribute("rel") === "stylesheet") && u.namespaceURI !== "http://www.w3.org/2000/svg") {
        var c = u.getAttribute(e) || "";
        c = t + c;
        var s = a.get(c);
        s ? s.push(u) : a.set(c, [u]);
      }
    }
    return a;
  }
  function Rd(t, e, l) {
    t = t.ownerDocument || t, t.head.insertBefore(
      l,
      e === "title" ? t.querySelector("head > title") : null
    );
  }
  function $y(t, e, l) {
    if (l === 1 || e.itemProp != null) return !1;
    switch (t) {
      case "meta":
      case "title":
        return !0;
      case "style":
        if (typeof e.precedence != "string" || typeof e.href != "string" || e.href === "")
          break;
        return !0;
      case "link":
        if (typeof e.rel != "string" || typeof e.href != "string" || e.href === "" || e.onLoad || e.onError)
          break;
        return e.rel === "stylesheet" ? (t = e.disabled, typeof e.precedence == "string" && t == null) : !0;
      case "script":
        if (e.async && typeof e.async != "function" && typeof e.async != "symbol" && !e.onLoad && !e.onError && e.src && typeof e.src == "string")
          return !0;
    }
    return !1;
  }
  function Nd(t) {
    return !(t.type === "stylesheet" && (t.state.loading & 3) === 0);
  }
  function Iy(t, e, l, a) {
    if (l.type === "stylesheet" && (typeof a.media != "string" || matchMedia(a.media).matches !== !1) && (l.state.loading & 4) === 0) {
      if (l.instance === null) {
        var n = Ga(a.href), u = e.querySelector(
          xn(n)
        );
        if (u) {
          e = u._p, e !== null && typeof e == "object" && typeof e.then == "function" && (t.count++, t = ku.bind(t), e.then(t, t)), l.state.loading |= 4, l.instance = u, Vt(u);
          return;
        }
        u = e.ownerDocument || e, a = xd(a), (n = Ce.get(n)) && Sf(a, n), u = u.createElement("link"), Vt(u);
        var c = u;
        c._p = new Promise(function(s, d) {
          c.onload = s, c.onerror = d;
        }), $t(u, "link", a), l.instance = u;
      }
      t.stylesheets === null && (t.stylesheets = /* @__PURE__ */ new Map()), t.stylesheets.set(l, e), (e = l.state.preload) && (l.state.loading & 3) === 0 && (t.count++, l = ku.bind(t), e.addEventListener("load", l), e.addEventListener("error", l));
    }
  }
  var Tf = 0;
  function Py(t, e) {
    return t.stylesheets && t.count === 0 && Wu(t, t.stylesheets), 0 < t.count || 0 < t.imgCount ? function(l) {
      var a = setTimeout(function() {
        if (t.stylesheets && Wu(t, t.stylesheets), t.unsuspend) {
          var u = t.unsuspend;
          t.unsuspend = null, u();
        }
      }, 6e4 + e);
      0 < t.imgBytes && Tf === 0 && (Tf = 62500 * Ny());
      var n = setTimeout(
        function() {
          if (t.waitingForImages = !1, t.count === 0 && (t.stylesheets && Wu(t, t.stylesheets), t.unsuspend)) {
            var u = t.unsuspend;
            t.unsuspend = null, u();
          }
        },
        (t.imgBytes > Tf ? 50 : 800) + e
      );
      return t.unsuspend = l, function() {
        t.unsuspend = null, clearTimeout(a), clearTimeout(n);
      };
    } : null;
  }
  function ku() {
    if (this.count--, this.count === 0 && (this.imgCount === 0 || !this.waitingForImages)) {
      if (this.stylesheets) Wu(this, this.stylesheets);
      else if (this.unsuspend) {
        var t = this.unsuspend;
        this.unsuspend = null, t();
      }
    }
  }
  var Fu = null;
  function Wu(t, e) {
    t.stylesheets = null, t.unsuspend !== null && (t.count++, Fu = /* @__PURE__ */ new Map(), e.forEach(tv, t), Fu = null, ku.call(t));
  }
  function tv(t, e) {
    if (!(e.state.loading & 4)) {
      var l = Fu.get(t);
      if (l) var a = l.get(null);
      else {
        l = /* @__PURE__ */ new Map(), Fu.set(t, l);
        for (var n = t.querySelectorAll(
          "link[data-precedence],style[data-precedence]"
        ), u = 0; u < n.length; u++) {
          var c = n[u];
          (c.nodeName === "LINK" || c.getAttribute("media") !== "not all") && (l.set(c.dataset.precedence, c), a = c);
        }
        a && l.set(null, a);
      }
      n = e.instance, c = n.getAttribute("data-precedence"), u = l.get(c) || a, u === a && l.set(null, n), l.set(c, n), this.count++, a = ku.bind(this), n.addEventListener("load", a), n.addEventListener("error", a), u ? u.parentNode.insertBefore(n, u.nextSibling) : (t = t.nodeType === 9 ? t.head : t, t.insertBefore(n, t.firstChild)), e.state.loading |= 4;
    }
  }
  var Un = {
    $$typeof: gt,
    Provider: null,
    Consumer: null,
    _currentValue: V,
    _currentValue2: V,
    _threadCount: 0
  };
  function ev(t, e, l, a, n, u, c, s, d) {
    this.tag = 1, this.containerInfo = t, this.pingCache = this.current = this.pendingChildren = null, this.timeoutHandle = -1, this.callbackNode = this.next = this.pendingContext = this.context = this.cancelPendingCommit = null, this.callbackPriority = 0, this.expirationTimes = vi(-1), this.entangledLanes = this.shellSuspendCounter = this.errorRecoveryDisabledLanes = this.expiredLanes = this.warmLanes = this.pingedLanes = this.suspendedLanes = this.pendingLanes = 0, this.entanglements = vi(0), this.hiddenUpdates = vi(null), this.identifierPrefix = a, this.onUncaughtError = n, this.onCaughtError = u, this.onRecoverableError = c, this.pooledCache = null, this.pooledCacheLanes = 0, this.formState = d, this.incompleteTransitions = /* @__PURE__ */ new Map();
  }
  function Hd(t, e, l, a, n, u, c, s, d, g, E, _) {
    return t = new ev(
      t,
      e,
      l,
      c,
      d,
      g,
      E,
      _,
      s
    ), e = 1, u === !0 && (e |= 24), u = me(3, null, null, e), t.current = u, u.stateNode = t, e = tc(), e.refCount++, t.pooledCache = e, e.refCount++, u.memoizedState = {
      element: a,
      isDehydrated: l,
      cache: e
    }, nc(u), t;
  }
  function qd(t) {
    return t ? (t = ga, t) : ga;
  }
  function jd(t, e, l, a, n, u) {
    n = qd(n), a.context === null ? a.context = n : a.pendingContext = n, a = gl(e), a.payload = { element: l }, u = u === void 0 ? null : u, u !== null && (a.callback = u), l = bl(t, a, e), l !== null && (ce(l, t, e), sn(l, t, e));
  }
  function Bd(t, e) {
    if (t = t.memoizedState, t !== null && t.dehydrated !== null) {
      var l = t.retryLane;
      t.retryLane = l !== 0 && l < e ? l : e;
    }
  }
  function Af(t, e) {
    Bd(t, e), (t = t.alternate) && Bd(t, e);
  }
  function Qd(t) {
    if (t.tag === 13 || t.tag === 31) {
      var e = wl(t, 67108864);
      e !== null && ce(e, t, 67108864), Af(t, 67108864);
    }
  }
  function Gd(t) {
    if (t.tag === 13 || t.tag === 31) {
      var e = pe();
      e = gi(e);
      var l = wl(t, e);
      l !== null && ce(l, t, e), Af(t, e);
    }
  }
  var $u = !0;
  function lv(t, e, l, a) {
    var n = T.T;
    T.T = null;
    var u = U.p;
    try {
      U.p = 2, Ef(t, e, l, a);
    } finally {
      U.p = u, T.T = n;
    }
  }
  function av(t, e, l, a) {
    var n = T.T;
    T.T = null;
    var u = U.p;
    try {
      U.p = 8, Ef(t, e, l, a);
    } finally {
      U.p = u, T.T = n;
    }
  }
  function Ef(t, e, l, a) {
    if ($u) {
      var n = Of(a);
      if (n === null)
        of(
          t,
          e,
          a,
          Iu,
          l
        ), Xd(t, a);
      else if (uv(
        n,
        t,
        e,
        l,
        a
      ))
        a.stopPropagation();
      else if (Xd(t, a), e & 4 && -1 < nv.indexOf(t)) {
        for (; n !== null; ) {
          var u = ia(n);
          if (u !== null)
            switch (u.tag) {
              case 3:
                if (u = u.stateNode, u.current.memoizedState.isDehydrated) {
                  var c = Bl(u.pendingLanes);
                  if (c !== 0) {
                    var s = u;
                    for (s.pendingLanes |= 2, s.entangledLanes |= 2; c; ) {
                      var d = 1 << 31 - de(c);
                      s.entanglements[1] |= d, c &= ~d;
                    }
                    Ge(u), (mt & 6) === 0 && (Hu = oe() + 500, On(0));
                  }
                }
                break;
              case 31:
              case 13:
                s = wl(u, 2), s !== null && ce(s, u, 2), ju(), Af(u, 2);
            }
          if (u = Of(a), u === null && of(
            t,
            e,
            a,
            Iu,
            l
          ), u === n) break;
          n = u;
        }
        n !== null && a.stopPropagation();
      } else
        of(
          t,
          e,
          a,
          null,
          l
        );
    }
  }
  function Of(t) {
    return t = Mi(t), Mf(t);
  }
  var Iu = null;
  function Mf(t) {
    if (Iu = null, t = ua(t), t !== null) {
      var e = O(t);
      if (e === null) t = null;
      else {
        var l = e.tag;
        if (l === 13) {
          if (t = C(e), t !== null) return t;
          t = null;
        } else if (l === 31) {
          if (t = D(e), t !== null) return t;
          t = null;
        } else if (l === 3) {
          if (e.stateNode.current.memoizedState.isDehydrated)
            return e.tag === 3 ? e.stateNode.containerInfo : null;
          t = null;
        } else e !== t && (t = null);
      }
    }
    return Iu = t, null;
  }
  function Yd(t) {
    switch (t) {
      case "beforetoggle":
      case "cancel":
      case "click":
      case "close":
      case "contextmenu":
      case "copy":
      case "cut":
      case "auxclick":
      case "dblclick":
      case "dragend":
      case "dragstart":
      case "drop":
      case "focusin":
      case "focusout":
      case "input":
      case "invalid":
      case "keydown":
      case "keypress":
      case "keyup":
      case "mousedown":
      case "mouseup":
      case "paste":
      case "pause":
      case "play":
      case "pointercancel":
      case "pointerdown":
      case "pointerup":
      case "ratechange":
      case "reset":
      case "resize":
      case "seeked":
      case "submit":
      case "toggle":
      case "touchcancel":
      case "touchend":
      case "touchstart":
      case "volumechange":
      case "change":
      case "selectionchange":
      case "textInput":
      case "compositionstart":
      case "compositionend":
      case "compositionupdate":
      case "beforeblur":
      case "afterblur":
      case "beforeinput":
      case "blur":
      case "fullscreenchange":
      case "focus":
      case "hashchange":
      case "popstate":
      case "select":
      case "selectstart":
        return 2;
      case "drag":
      case "dragenter":
      case "dragexit":
      case "dragleave":
      case "dragover":
      case "mousemove":
      case "mouseout":
      case "mouseover":
      case "pointermove":
      case "pointerout":
      case "pointerover":
      case "scroll":
      case "touchmove":
      case "wheel":
      case "mouseenter":
      case "mouseleave":
      case "pointerenter":
      case "pointerleave":
        return 8;
      case "message":
        switch (Zh()) {
          case Jf:
            return 2;
          case kf:
            return 8;
          case Xn:
          case Lh:
            return 32;
          case Ff:
            return 268435456;
          default:
            return 32;
        }
      default:
        return 32;
    }
  }
  var _f = !1, xl = null, Cl = null, Ul = null, Rn = /* @__PURE__ */ new Map(), Nn = /* @__PURE__ */ new Map(), Rl = [], nv = "mousedown mouseup touchcancel touchend touchstart auxclick dblclick pointercancel pointerdown pointerup dragend dragstart drop compositionend compositionstart keydown keypress keyup input textInput copy cut paste click change contextmenu reset".split(
    " "
  );
  function Xd(t, e) {
    switch (t) {
      case "focusin":
      case "focusout":
        xl = null;
        break;
      case "dragenter":
      case "dragleave":
        Cl = null;
        break;
      case "mouseover":
      case "mouseout":
        Ul = null;
        break;
      case "pointerover":
      case "pointerout":
        Rn.delete(e.pointerId);
        break;
      case "gotpointercapture":
      case "lostpointercapture":
        Nn.delete(e.pointerId);
    }
  }
  function Hn(t, e, l, a, n, u) {
    return t === null || t.nativeEvent !== u ? (t = {
      blockedOn: e,
      domEventName: l,
      eventSystemFlags: a,
      nativeEvent: u,
      targetContainers: [n]
    }, e !== null && (e = ia(e), e !== null && Qd(e)), t) : (t.eventSystemFlags |= a, e = t.targetContainers, n !== null && e.indexOf(n) === -1 && e.push(n), t);
  }
  function uv(t, e, l, a, n) {
    switch (e) {
      case "focusin":
        return xl = Hn(
          xl,
          t,
          e,
          l,
          a,
          n
        ), !0;
      case "dragenter":
        return Cl = Hn(
          Cl,
          t,
          e,
          l,
          a,
          n
        ), !0;
      case "mouseover":
        return Ul = Hn(
          Ul,
          t,
          e,
          l,
          a,
          n
        ), !0;
      case "pointerover":
        var u = n.pointerId;
        return Rn.set(
          u,
          Hn(
            Rn.get(u) || null,
            t,
            e,
            l,
            a,
            n
          )
        ), !0;
      case "gotpointercapture":
        return u = n.pointerId, Nn.set(
          u,
          Hn(
            Nn.get(u) || null,
            t,
            e,
            l,
            a,
            n
          )
        ), !0;
    }
    return !1;
  }
  function wd(t) {
    var e = ua(t.target);
    if (e !== null) {
      var l = O(e);
      if (l !== null) {
        if (e = l.tag, e === 13) {
          if (e = C(l), e !== null) {
            t.blockedOn = e, es(t.priority, function() {
              Gd(l);
            });
            return;
          }
        } else if (e === 31) {
          if (e = D(l), e !== null) {
            t.blockedOn = e, es(t.priority, function() {
              Gd(l);
            });
            return;
          }
        } else if (e === 3 && l.stateNode.current.memoizedState.isDehydrated) {
          t.blockedOn = l.tag === 3 ? l.stateNode.containerInfo : null;
          return;
        }
      }
    }
    t.blockedOn = null;
  }
  function Pu(t) {
    if (t.blockedOn !== null) return !1;
    for (var e = t.targetContainers; 0 < e.length; ) {
      var l = Of(t.nativeEvent);
      if (l === null) {
        l = t.nativeEvent;
        var a = new l.constructor(
          l.type,
          l
        );
        Oi = a, l.target.dispatchEvent(a), Oi = null;
      } else
        return e = ia(l), e !== null && Qd(e), t.blockedOn = l, !1;
      e.shift();
    }
    return !0;
  }
  function Zd(t, e, l) {
    Pu(t) && l.delete(e);
  }
  function iv() {
    _f = !1, xl !== null && Pu(xl) && (xl = null), Cl !== null && Pu(Cl) && (Cl = null), Ul !== null && Pu(Ul) && (Ul = null), Rn.forEach(Zd), Nn.forEach(Zd);
  }
  function ti(t, e) {
    t.blockedOn === e && (t.blockedOn = null, _f || (_f = !0, i.unstable_scheduleCallback(
      i.unstable_NormalPriority,
      iv
    )));
  }
  var ei = null;
  function Ld(t) {
    ei !== t && (ei = t, i.unstable_scheduleCallback(
      i.unstable_NormalPriority,
      function() {
        ei === t && (ei = null);
        for (var e = 0; e < t.length; e += 3) {
          var l = t[e], a = t[e + 1], n = t[e + 2];
          if (typeof a != "function") {
            if (Mf(a || l) === null)
              continue;
            break;
          }
          var u = ia(l);
          u !== null && (t.splice(e, 3), e -= 3, Ec(
            u,
            {
              pending: !0,
              data: n,
              method: l.method,
              action: a
            },
            a,
            n
          ));
        }
      }
    ));
  }
  function Xa(t) {
    function e(d) {
      return ti(d, t);
    }
    xl !== null && ti(xl, t), Cl !== null && ti(Cl, t), Ul !== null && ti(Ul, t), Rn.forEach(e), Nn.forEach(e);
    for (var l = 0; l < Rl.length; l++) {
      var a = Rl[l];
      a.blockedOn === t && (a.blockedOn = null);
    }
    for (; 0 < Rl.length && (l = Rl[0], l.blockedOn === null); )
      wd(l), l.blockedOn === null && Rl.shift();
    if (l = (t.ownerDocument || t).$$reactFormReplay, l != null)
      for (a = 0; a < l.length; a += 3) {
        var n = l[a], u = l[a + 1], c = n[ee] || null;
        if (typeof u == "function")
          c || Ld(l);
        else if (c) {
          var s = null;
          if (u && u.hasAttribute("formAction")) {
            if (n = u, c = u[ee] || null)
              s = c.formAction;
            else if (Mf(n) !== null) continue;
          } else s = c.action;
          typeof s == "function" ? l[a + 1] = s : (l.splice(a, 3), a -= 3), Ld(l);
        }
      }
  }
  function Vd() {
    function t(u) {
      u.canIntercept && u.info === "react-transition" && u.intercept({
        handler: function() {
          return new Promise(function(c) {
            return n = c;
          });
        },
        focusReset: "manual",
        scroll: "manual"
      });
    }
    function e() {
      n !== null && (n(), n = null), a || setTimeout(l, 20);
    }
    function l() {
      if (!a && !navigation.transition) {
        var u = navigation.currentEntry;
        u && u.url != null && navigation.navigate(u.url, {
          state: u.getState(),
          info: "react-transition",
          history: "replace"
        });
      }
    }
    if (typeof navigation == "object") {
      var a = !1, n = null;
      return navigation.addEventListener("navigate", t), navigation.addEventListener("navigatesuccess", e), navigation.addEventListener("navigateerror", e), setTimeout(l, 100), function() {
        a = !0, navigation.removeEventListener("navigate", t), navigation.removeEventListener("navigatesuccess", e), navigation.removeEventListener("navigateerror", e), n !== null && (n(), n = null);
      };
    }
  }
  function Df(t) {
    this._internalRoot = t;
  }
  li.prototype.render = Df.prototype.render = function(t) {
    var e = this._internalRoot;
    if (e === null) throw Error(o(409));
    var l = e.current, a = pe();
    jd(l, a, t, e, null, null);
  }, li.prototype.unmount = Df.prototype.unmount = function() {
    var t = this._internalRoot;
    if (t !== null) {
      this._internalRoot = null;
      var e = t.containerInfo;
      jd(t.current, 2, null, t, null, null), ju(), e[na] = null;
    }
  };
  function li(t) {
    this._internalRoot = t;
  }
  li.prototype.unstable_scheduleHydration = function(t) {
    if (t) {
      var e = ts();
      t = { blockedOn: null, target: t, priority: e };
      for (var l = 0; l < Rl.length && e !== 0 && e < Rl[l].priority; l++) ;
      Rl.splice(l, 0, t), l === 0 && wd(t);
    }
  };
  var Kd = f.version;
  if (Kd !== "19.2.4")
    throw Error(
      o(
        527,
        Kd,
        "19.2.4"
      )
    );
  U.findDOMNode = function(t) {
    var e = t._reactInternals;
    if (e === void 0)
      throw typeof t.render == "function" ? Error(o(188)) : (t = Object.keys(t).join(","), Error(o(268, t)));
    return t = S(e), t = t !== null ? G(t) : null, t = t === null ? null : t.stateNode, t;
  };
  var cv = {
    bundleType: 0,
    version: "19.2.4",
    rendererPackageName: "react-dom",
    currentDispatcherRef: T,
    reconcilerVersion: "19.2.4"
  };
  if (typeof __REACT_DEVTOOLS_GLOBAL_HOOK__ < "u") {
    var ai = __REACT_DEVTOOLS_GLOBAL_HOOK__;
    if (!ai.isDisabled && ai.supportsFiber)
      try {
        wa = ai.inject(
          cv
        ), re = ai;
      } catch {
      }
  }
  return jn.createRoot = function(t, e) {
    if (!p(t)) throw Error(o(299));
    var l = !1, a = "", n = Po, u = tr, c = er;
    return e != null && (e.unstable_strictMode === !0 && (l = !0), e.identifierPrefix !== void 0 && (a = e.identifierPrefix), e.onUncaughtError !== void 0 && (n = e.onUncaughtError), e.onCaughtError !== void 0 && (u = e.onCaughtError), e.onRecoverableError !== void 0 && (c = e.onRecoverableError)), e = Hd(
      t,
      1,
      !1,
      null,
      null,
      l,
      a,
      null,
      n,
      u,
      c,
      Vd
    ), t[na] = e.current, sf(t), new Df(e);
  }, jn.hydrateRoot = function(t, e, l) {
    if (!p(t)) throw Error(o(299));
    var a = !1, n = "", u = Po, c = tr, s = er, d = null;
    return l != null && (l.unstable_strictMode === !0 && (a = !0), l.identifierPrefix !== void 0 && (n = l.identifierPrefix), l.onUncaughtError !== void 0 && (u = l.onUncaughtError), l.onCaughtError !== void 0 && (c = l.onCaughtError), l.onRecoverableError !== void 0 && (s = l.onRecoverableError), l.formState !== void 0 && (d = l.formState)), e = Hd(
      t,
      1,
      !0,
      e,
      l ?? null,
      a,
      n,
      d,
      u,
      c,
      s,
      Vd
    ), e.context = qd(null), l = e.current, a = pe(), a = gi(a), n = gl(a), n.callback = null, bl(l, n, a), l = a, e.current.lanes = l, La(e, l), Ge(e), t[na] = e.current, sf(t), new li(e);
  }, jn.version = "19.2.4", jn;
}
var lh;
function gv() {
  if (lh) return Cf.exports;
  lh = 1;
  function i() {
    if (!(typeof __REACT_DEVTOOLS_GLOBAL_HOOK__ > "u" || typeof __REACT_DEVTOOLS_GLOBAL_HOOK__.checkDCE != "function"))
      try {
        __REACT_DEVTOOLS_GLOBAL_HOOK__.checkDCE(i);
      } catch (f) {
        console.error(f);
      }
  }
  return i(), Cf.exports = vv(), Cf.exports;
}
var bv = gv(), si = class {
  constructor() {
    this.listeners = /* @__PURE__ */ new Set(), this.subscribe = this.subscribe.bind(this);
  }
  subscribe(i) {
    return this.listeners.add(i), this.onSubscribe(), () => {
      this.listeners.delete(i), this.onUnsubscribe();
    };
  }
  hasListeners() {
    return this.listeners.size > 0;
  }
  onSubscribe() {
  }
  onUnsubscribe() {
  }
}, pv = {
  // We need the wrapper function syntax below instead of direct references to
  // global setTimeout etc.
  //
  // BAD: `setTimeout: setTimeout`
  // GOOD: `setTimeout: (cb, delay) => setTimeout(cb, delay)`
  //
  // If we use direct references here, then anything that wants to spy on or
  // replace the global setTimeout (like tests) won't work since we'll already
  // have a hard reference to the original implementation at the time when this
  // file was imported.
  setTimeout: (i, f) => setTimeout(i, f),
  clearTimeout: (i) => clearTimeout(i),
  setInterval: (i, f) => setInterval(i, f),
  clearInterval: (i) => clearInterval(i)
}, Sv = class {
  // We cannot have TimeoutManager<T> as we must instantiate it with a concrete
  // type at app boot; and if we leave that type, then any new timer provider
  // would need to support ReturnType<typeof setTimeout>, which is infeasible.
  //
  // We settle for type safety for the TimeoutProvider type, and accept that
  // this class is unsafe internally to allow for extension.
  #t = pv;
  #l = !1;
  setTimeoutProvider(i) {
    this.#t = i;
  }
  setTimeout(i, f) {
    return this.#t.setTimeout(i, f);
  }
  clearTimeout(i) {
    this.#t.clearTimeout(i);
  }
  setInterval(i, f) {
    return this.#t.setInterval(i, f);
  }
  clearInterval(i) {
    this.#t.clearInterval(i);
  }
}, jf = new Sv();
function zv(i) {
  setTimeout(i, 0);
}
var oi = typeof window > "u" || "Deno" in globalThis;
function He() {
}
function Tv(i, f) {
  return typeof i == "function" ? i(f) : i;
}
function Av(i) {
  return typeof i == "number" && i >= 0 && i !== 1 / 0;
}
function Ev(i, f) {
  return Math.max(i + (f || 0) - Date.now(), 0);
}
function Bf(i, f) {
  return typeof i == "function" ? i(f) : i;
}
function Ov(i, f) {
  return typeof i == "function" ? i(f) : i;
}
function ah(i, f) {
  const {
    type: r = "all",
    exact: o,
    fetchStatus: p,
    predicate: O,
    queryKey: C,
    stale: D
  } = i;
  if (C) {
    if (o) {
      if (f.queryHash !== wf(C, f.options))
        return !1;
    } else if (!Yn(f.queryKey, C))
      return !1;
  }
  if (r !== "all") {
    const A = f.isActive();
    if (r === "active" && !A || r === "inactive" && A)
      return !1;
  }
  return !(typeof D == "boolean" && f.isStale() !== D || p && p !== f.state.fetchStatus || O && !O(f));
}
function nh(i, f) {
  const { exact: r, status: o, predicate: p, mutationKey: O } = i;
  if (O) {
    if (!f.options.mutationKey)
      return !1;
    if (r) {
      if (Gn(f.options.mutationKey) !== Gn(O))
        return !1;
    } else if (!Yn(f.options.mutationKey, O))
      return !1;
  }
  return !(o && f.state.status !== o || p && !p(f));
}
function wf(i, f) {
  return (f?.queryKeyHashFn || Gn)(i);
}
function Gn(i) {
  return JSON.stringify(
    i,
    (f, r) => Qf(r) ? Object.keys(r).sort().reduce((o, p) => (o[p] = r[p], o), {}) : r
  );
}
function Yn(i, f) {
  return i === f ? !0 : typeof i != typeof f ? !1 : i && f && typeof i == "object" && typeof f == "object" ? Object.keys(f).every((r) => Yn(i[r], f[r])) : !1;
}
var Mv = Object.prototype.hasOwnProperty;
function bh(i, f, r = 0) {
  if (i === f)
    return i;
  if (r > 500) return f;
  const o = uh(i) && uh(f);
  if (!o && !(Qf(i) && Qf(f))) return f;
  const O = (o ? i : Object.keys(i)).length, C = o ? f : Object.keys(f), D = C.length, A = o ? new Array(D) : {};
  let S = 0;
  for (let G = 0; G < D; G++) {
    const H = o ? G : C[G], J = i[H], st = f[H];
    if (J === st) {
      A[H] = J, (o ? G < O : Mv.call(i, H)) && S++;
      continue;
    }
    if (J === null || st === null || typeof J != "object" || typeof st != "object") {
      A[H] = st;
      continue;
    }
    const $ = bh(J, st, r + 1);
    A[H] = $, $ === J && S++;
  }
  return O === D && S === O ? i : A;
}
function Z0(i, f) {
  if (!f || Object.keys(i).length !== Object.keys(f).length)
    return !1;
  for (const r in i)
    if (i[r] !== f[r])
      return !1;
  return !0;
}
function uh(i) {
  return Array.isArray(i) && i.length === Object.keys(i).length;
}
function Qf(i) {
  if (!ih(i))
    return !1;
  const f = i.constructor;
  if (f === void 0)
    return !0;
  const r = f.prototype;
  return !(!ih(r) || !r.hasOwnProperty("isPrototypeOf") || Object.getPrototypeOf(i) !== Object.prototype);
}
function ih(i) {
  return Object.prototype.toString.call(i) === "[object Object]";
}
function _v(i) {
  return new Promise((f) => {
    jf.setTimeout(f, i);
  });
}
function Dv(i, f, r) {
  return typeof r.structuralSharing == "function" ? r.structuralSharing(i, f) : r.structuralSharing !== !1 ? bh(i, f) : f;
}
function xv(i, f, r = 0) {
  const o = [...i, f];
  return r && o.length > r ? o.slice(1) : o;
}
function Cv(i, f, r = 0) {
  const o = [f, ...i];
  return r && o.length > r ? o.slice(0, -1) : o;
}
var Zf = /* @__PURE__ */ Symbol();
function ph(i, f) {
  return !i.queryFn && f?.initialPromise ? () => f.initialPromise : !i.queryFn || i.queryFn === Zf ? () => Promise.reject(new Error(`Missing queryFn: '${i.queryHash}'`)) : i.queryFn;
}
function L0(i, f) {
  return typeof i == "function" ? i(...f) : !!i;
}
function Uv(i, f, r) {
  let o = !1, p;
  return Object.defineProperty(i, "signal", {
    enumerable: !0,
    get: () => (p ??= f(), o || (o = !0, p.aborted ? r() : p.addEventListener("abort", r, { once: !0 })), p)
  }), i;
}
var Rv = class extends si {
  #t;
  #l;
  #e;
  constructor() {
    super(), this.#e = (i) => {
      if (!oi && window.addEventListener) {
        const f = () => i();
        return window.addEventListener("visibilitychange", f, !1), () => {
          window.removeEventListener("visibilitychange", f);
        };
      }
    };
  }
  onSubscribe() {
    this.#l || this.setEventListener(this.#e);
  }
  onUnsubscribe() {
    this.hasListeners() || (this.#l?.(), this.#l = void 0);
  }
  setEventListener(i) {
    this.#e = i, this.#l?.(), this.#l = i((f) => {
      typeof f == "boolean" ? this.setFocused(f) : this.onFocus();
    });
  }
  setFocused(i) {
    this.#t !== i && (this.#t = i, this.onFocus());
  }
  onFocus() {
    const i = this.isFocused();
    this.listeners.forEach((f) => {
      f(i);
    });
  }
  isFocused() {
    return typeof this.#t == "boolean" ? this.#t : globalThis.document?.visibilityState !== "hidden";
  }
}, Sh = new Rv();
function Nv() {
  let i, f;
  const r = new Promise((p, O) => {
    i = p, f = O;
  });
  r.status = "pending", r.catch(() => {
  });
  function o(p) {
    Object.assign(r, p), delete r.resolve, delete r.reject;
  }
  return r.resolve = (p) => {
    o({
      status: "fulfilled",
      value: p
    }), i(p);
  }, r.reject = (p) => {
    o({
      status: "rejected",
      reason: p
    }), f(p);
  }, r;
}
var Hv = zv;
function qv() {
  let i = [], f = 0, r = (D) => {
    D();
  }, o = (D) => {
    D();
  }, p = Hv;
  const O = (D) => {
    f ? i.push(D) : p(() => {
      r(D);
    });
  }, C = () => {
    const D = i;
    i = [], D.length && p(() => {
      o(() => {
        D.forEach((A) => {
          r(A);
        });
      });
    });
  };
  return {
    batch: (D) => {
      let A;
      f++;
      try {
        A = D();
      } finally {
        f--, f || C();
      }
      return A;
    },
    /**
     * All calls to the wrapped function will be batched.
     */
    batchCalls: (D) => (...A) => {
      O(() => {
        D(...A);
      });
    },
    schedule: O,
    /**
     * Use this method to set a custom notify function.
     * This can be used to for example wrap notifications with `React.act` while running tests.
     */
    setNotifyFunction: (D) => {
      r = D;
    },
    /**
     * Use this method to set a custom function to batch notifications together into a single tick.
     * By default React Query will use the batch function provided by ReactDOM or React Native.
     */
    setBatchNotifyFunction: (D) => {
      o = D;
    },
    setScheduler: (D) => {
      p = D;
    }
  };
}
var te = qv(), jv = class extends si {
  #t = !0;
  #l;
  #e;
  constructor() {
    super(), this.#e = (i) => {
      if (!oi && window.addEventListener) {
        const f = () => i(!0), r = () => i(!1);
        return window.addEventListener("online", f, !1), window.addEventListener("offline", r, !1), () => {
          window.removeEventListener("online", f), window.removeEventListener("offline", r);
        };
      }
    };
  }
  onSubscribe() {
    this.#l || this.setEventListener(this.#e);
  }
  onUnsubscribe() {
    this.hasListeners() || (this.#l?.(), this.#l = void 0);
  }
  setEventListener(i) {
    this.#e = i, this.#l?.(), this.#l = i(this.setOnline.bind(this));
  }
  setOnline(i) {
    this.#t !== i && (this.#t = i, this.listeners.forEach((r) => {
      r(i);
    }));
  }
  isOnline() {
    return this.#t;
  }
}, ci = new jv();
function Bv(i) {
  return Math.min(1e3 * 2 ** i, 3e4);
}
function zh(i) {
  return (i ?? "online") === "online" ? ci.isOnline() : !0;
}
var Gf = class extends Error {
  constructor(i) {
    super("CancelledError"), this.revert = i?.revert, this.silent = i?.silent;
  }
};
function Th(i) {
  let f = !1, r = 0, o;
  const p = Nv(), O = () => p.status !== "pending", C = (k) => {
    if (!O()) {
      const nt = new Gf(k);
      J(nt), i.onCancel?.(nt);
    }
  }, D = () => {
    f = !0;
  }, A = () => {
    f = !1;
  }, S = () => Sh.isFocused() && (i.networkMode === "always" || ci.isOnline()) && i.canRun(), G = () => zh(i.networkMode) && i.canRun(), H = (k) => {
    O() || (o?.(), p.resolve(k));
  }, J = (k) => {
    O() || (o?.(), p.reject(k));
  }, st = () => new Promise((k) => {
    o = (nt) => {
      (O() || S()) && k(nt);
    }, i.onPause?.();
  }).then(() => {
    o = void 0, O() || i.onContinue?.();
  }), $ = () => {
    if (O())
      return;
    let k;
    const nt = r === 0 ? i.initialPromise : void 0;
    try {
      k = nt ?? i.fn();
    } catch (ot) {
      k = Promise.reject(ot);
    }
    Promise.resolve(k).then(H).catch((ot) => {
      if (O())
        return;
      const Nt = i.retry ?? (oi ? 0 : 3), gt = i.retryDelay ?? Bv, _t = typeof gt == "function" ? gt(r, ot) : gt, Ct = Nt === !0 || typeof Nt == "number" && r < Nt || typeof Nt == "function" && Nt(r, ot);
      if (f || !Ct) {
        J(ot);
        return;
      }
      r++, i.onFail?.(r, ot), _v(_t).then(() => S() ? void 0 : st()).then(() => {
        f ? J(ot) : $();
      });
    });
  };
  return {
    promise: p,
    status: () => p.status,
    cancel: C,
    continue: () => (o?.(), p),
    cancelRetry: D,
    continueRetry: A,
    canStart: G,
    start: () => (G() ? $() : st().then($), p)
  };
}
var Ah = class {
  #t;
  destroy() {
    this.clearGcTimeout();
  }
  scheduleGc() {
    this.clearGcTimeout(), Av(this.gcTime) && (this.#t = jf.setTimeout(() => {
      this.optionalRemove();
    }, this.gcTime));
  }
  updateGcTime(i) {
    this.gcTime = Math.max(
      this.gcTime || 0,
      i ?? (oi ? 1 / 0 : 300 * 1e3)
    );
  }
  clearGcTimeout() {
    this.#t && (jf.clearTimeout(this.#t), this.#t = void 0);
  }
}, Qv = class extends Ah {
  #t;
  #l;
  #e;
  #n;
  #a;
  #i;
  #c;
  constructor(i) {
    super(), this.#c = !1, this.#i = i.defaultOptions, this.setOptions(i.options), this.observers = [], this.#n = i.client, this.#e = this.#n.getQueryCache(), this.queryKey = i.queryKey, this.queryHash = i.queryHash, this.#t = fh(this.options), this.state = i.state ?? this.#t, this.scheduleGc();
  }
  get meta() {
    return this.options.meta;
  }
  get promise() {
    return this.#a?.promise;
  }
  setOptions(i) {
    if (this.options = { ...this.#i, ...i }, this.updateGcTime(this.options.gcTime), this.state && this.state.data === void 0) {
      const f = fh(this.options);
      f.data !== void 0 && (this.setState(
        ch(f.data, f.dataUpdatedAt)
      ), this.#t = f);
    }
  }
  optionalRemove() {
    !this.observers.length && this.state.fetchStatus === "idle" && this.#e.remove(this);
  }
  setData(i, f) {
    const r = Dv(this.state.data, i, this.options);
    return this.#u({
      data: r,
      type: "success",
      dataUpdatedAt: f?.updatedAt,
      manual: f?.manual
    }), r;
  }
  setState(i, f) {
    this.#u({ type: "setState", state: i, setStateOptions: f });
  }
  cancel(i) {
    const f = this.#a?.promise;
    return this.#a?.cancel(i), f ? f.then(He).catch(He) : Promise.resolve();
  }
  destroy() {
    super.destroy(), this.cancel({ silent: !0 });
  }
  reset() {
    this.destroy(), this.setState(this.#t);
  }
  isActive() {
    return this.observers.some(
      (i) => Ov(i.options.enabled, this) !== !1
    );
  }
  isDisabled() {
    return this.getObserversCount() > 0 ? !this.isActive() : this.options.queryFn === Zf || this.state.dataUpdateCount + this.state.errorUpdateCount === 0;
  }
  isStatic() {
    return this.getObserversCount() > 0 ? this.observers.some(
      (i) => Bf(i.options.staleTime, this) === "static"
    ) : !1;
  }
  isStale() {
    return this.getObserversCount() > 0 ? this.observers.some(
      (i) => i.getCurrentResult().isStale
    ) : this.state.data === void 0 || this.state.isInvalidated;
  }
  isStaleByTime(i = 0) {
    return this.state.data === void 0 ? !0 : i === "static" ? !1 : this.state.isInvalidated ? !0 : !Ev(this.state.dataUpdatedAt, i);
  }
  onFocus() {
    this.observers.find((f) => f.shouldFetchOnWindowFocus())?.refetch({ cancelRefetch: !1 }), this.#a?.continue();
  }
  onOnline() {
    this.observers.find((f) => f.shouldFetchOnReconnect())?.refetch({ cancelRefetch: !1 }), this.#a?.continue();
  }
  addObserver(i) {
    this.observers.includes(i) || (this.observers.push(i), this.clearGcTimeout(), this.#e.notify({ type: "observerAdded", query: this, observer: i }));
  }
  removeObserver(i) {
    this.observers.includes(i) && (this.observers = this.observers.filter((f) => f !== i), this.observers.length || (this.#a && (this.#c ? this.#a.cancel({ revert: !0 }) : this.#a.cancelRetry()), this.scheduleGc()), this.#e.notify({ type: "observerRemoved", query: this, observer: i }));
  }
  getObserversCount() {
    return this.observers.length;
  }
  invalidate() {
    this.state.isInvalidated || this.#u({ type: "invalidate" });
  }
  async fetch(i, f) {
    if (this.state.fetchStatus !== "idle" && // If the promise in the retryer is already rejected, we have to definitely
    // re-start the fetch; there is a chance that the query is still in a
    // pending state when that happens
    this.#a?.status() !== "rejected") {
      if (this.state.data !== void 0 && f?.cancelRefetch)
        this.cancel({ silent: !0 });
      else if (this.#a)
        return this.#a.continueRetry(), this.#a.promise;
    }
    if (i && this.setOptions(i), !this.options.queryFn) {
      const D = this.observers.find((A) => A.options.queryFn);
      D && this.setOptions(D.options);
    }
    const r = new AbortController(), o = (D) => {
      Object.defineProperty(D, "signal", {
        enumerable: !0,
        get: () => (this.#c = !0, r.signal)
      });
    }, p = () => {
      const D = ph(this.options, f), S = (() => {
        const G = {
          client: this.#n,
          queryKey: this.queryKey,
          meta: this.meta
        };
        return o(G), G;
      })();
      return this.#c = !1, this.options.persister ? this.options.persister(
        D,
        S,
        this
      ) : D(S);
    }, C = (() => {
      const D = {
        fetchOptions: f,
        options: this.options,
        queryKey: this.queryKey,
        client: this.#n,
        state: this.state,
        fetchFn: p
      };
      return o(D), D;
    })();
    this.options.behavior?.onFetch(C, this), this.#l = this.state, (this.state.fetchStatus === "idle" || this.state.fetchMeta !== C.fetchOptions?.meta) && this.#u({ type: "fetch", meta: C.fetchOptions?.meta }), this.#a = Th({
      initialPromise: f?.initialPromise,
      fn: C.fetchFn,
      onCancel: (D) => {
        D instanceof Gf && D.revert && this.setState({
          ...this.#l,
          fetchStatus: "idle"
        }), r.abort();
      },
      onFail: (D, A) => {
        this.#u({ type: "failed", failureCount: D, error: A });
      },
      onPause: () => {
        this.#u({ type: "pause" });
      },
      onContinue: () => {
        this.#u({ type: "continue" });
      },
      retry: C.options.retry,
      retryDelay: C.options.retryDelay,
      networkMode: C.options.networkMode,
      canRun: () => !0
    });
    try {
      const D = await this.#a.start();
      if (D === void 0)
        throw new Error(`${this.queryHash} data is undefined`);
      return this.setData(D), this.#e.config.onSuccess?.(D, this), this.#e.config.onSettled?.(
        D,
        this.state.error,
        this
      ), D;
    } catch (D) {
      if (D instanceof Gf) {
        if (D.silent)
          return this.#a.promise;
        if (D.revert) {
          if (this.state.data === void 0)
            throw D;
          return this.state.data;
        }
      }
      throw this.#u({
        type: "error",
        error: D
      }), this.#e.config.onError?.(
        D,
        this
      ), this.#e.config.onSettled?.(
        this.state.data,
        D,
        this
      ), D;
    } finally {
      this.scheduleGc();
    }
  }
  #u(i) {
    const f = (r) => {
      switch (i.type) {
        case "failed":
          return {
            ...r,
            fetchFailureCount: i.failureCount,
            fetchFailureReason: i.error
          };
        case "pause":
          return {
            ...r,
            fetchStatus: "paused"
          };
        case "continue":
          return {
            ...r,
            fetchStatus: "fetching"
          };
        case "fetch":
          return {
            ...r,
            ...Gv(r.data, this.options),
            fetchMeta: i.meta ?? null
          };
        case "success":
          const o = {
            ...r,
            ...ch(i.data, i.dataUpdatedAt),
            dataUpdateCount: r.dataUpdateCount + 1,
            ...!i.manual && {
              fetchStatus: "idle",
              fetchFailureCount: 0,
              fetchFailureReason: null
            }
          };
          return this.#l = i.manual ? o : void 0, o;
        case "error":
          const p = i.error;
          return {
            ...r,
            error: p,
            errorUpdateCount: r.errorUpdateCount + 1,
            errorUpdatedAt: Date.now(),
            fetchFailureCount: r.fetchFailureCount + 1,
            fetchFailureReason: p,
            fetchStatus: "idle",
            status: "error",
            // flag existing data as invalidated if we get a background error
            // note that "no data" always means stale so we can set unconditionally here
            isInvalidated: !0
          };
        case "invalidate":
          return {
            ...r,
            isInvalidated: !0
          };
        case "setState":
          return {
            ...r,
            ...i.state
          };
      }
    };
    this.state = f(this.state), te.batch(() => {
      this.observers.forEach((r) => {
        r.onQueryUpdate();
      }), this.#e.notify({ query: this, type: "updated", action: i });
    });
  }
};
function Gv(i, f) {
  return {
    fetchFailureCount: 0,
    fetchFailureReason: null,
    fetchStatus: zh(f.networkMode) ? "fetching" : "paused",
    ...i === void 0 && {
      error: null,
      status: "pending"
    }
  };
}
function ch(i, f) {
  return {
    data: i,
    dataUpdatedAt: f ?? Date.now(),
    error: null,
    isInvalidated: !1,
    status: "success"
  };
}
function fh(i) {
  const f = typeof i.initialData == "function" ? i.initialData() : i.initialData, r = f !== void 0, o = r ? typeof i.initialDataUpdatedAt == "function" ? i.initialDataUpdatedAt() : i.initialDataUpdatedAt : 0;
  return {
    data: f,
    dataUpdateCount: 0,
    dataUpdatedAt: r ? o ?? Date.now() : 0,
    error: null,
    errorUpdateCount: 0,
    errorUpdatedAt: 0,
    fetchFailureCount: 0,
    fetchFailureReason: null,
    fetchMeta: null,
    isInvalidated: !1,
    status: r ? "success" : "pending",
    fetchStatus: "idle"
  };
}
function sh(i) {
  return {
    onFetch: (f, r) => {
      const o = f.options, p = f.fetchOptions?.meta?.fetchMore?.direction, O = f.state.data?.pages || [], C = f.state.data?.pageParams || [];
      let D = { pages: [], pageParams: [] }, A = 0;
      const S = async () => {
        let G = !1;
        const H = ($) => {
          Uv(
            $,
            () => f.signal,
            () => G = !0
          );
        }, J = ph(f.options, f.fetchOptions), st = async ($, k, nt) => {
          if (G)
            return Promise.reject();
          if (k == null && $.pages.length)
            return Promise.resolve($);
          const Nt = (() => {
            const Et = {
              client: f.client,
              queryKey: f.queryKey,
              pageParam: k,
              direction: nt ? "backward" : "forward",
              meta: f.options.meta
            };
            return H(Et), Et;
          })(), gt = await J(Nt), { maxPages: _t } = f.options, Ct = nt ? Cv : xv;
          return {
            pages: Ct($.pages, gt, _t),
            pageParams: Ct($.pageParams, k, _t)
          };
        };
        if (p && O.length) {
          const $ = p === "backward", k = $ ? Yv : oh, nt = {
            pages: O,
            pageParams: C
          }, ot = k(o, nt);
          D = await st(nt, ot, $);
        } else {
          const $ = i ?? O.length;
          do {
            const k = A === 0 ? C[0] ?? o.initialPageParam : oh(o, D);
            if (A > 0 && k == null)
              break;
            D = await st(D, k), A++;
          } while (A < $);
        }
        return D;
      };
      f.options.persister ? f.fetchFn = () => f.options.persister?.(
        S,
        {
          client: f.client,
          queryKey: f.queryKey,
          meta: f.options.meta,
          signal: f.signal
        },
        r
      ) : f.fetchFn = S;
    }
  };
}
function oh(i, { pages: f, pageParams: r }) {
  const o = f.length - 1;
  return f.length > 0 ? i.getNextPageParam(
    f[o],
    f,
    r[o],
    r
  ) : void 0;
}
function Yv(i, { pages: f, pageParams: r }) {
  return f.length > 0 ? i.getPreviousPageParam?.(f[0], f, r[0], r) : void 0;
}
var Xv = class extends Ah {
  #t;
  #l;
  #e;
  #n;
  constructor(i) {
    super(), this.#t = i.client, this.mutationId = i.mutationId, this.#e = i.mutationCache, this.#l = [], this.state = i.state || wv(), this.setOptions(i.options), this.scheduleGc();
  }
  setOptions(i) {
    this.options = i, this.updateGcTime(this.options.gcTime);
  }
  get meta() {
    return this.options.meta;
  }
  addObserver(i) {
    this.#l.includes(i) || (this.#l.push(i), this.clearGcTimeout(), this.#e.notify({
      type: "observerAdded",
      mutation: this,
      observer: i
    }));
  }
  removeObserver(i) {
    this.#l = this.#l.filter((f) => f !== i), this.scheduleGc(), this.#e.notify({
      type: "observerRemoved",
      mutation: this,
      observer: i
    });
  }
  optionalRemove() {
    this.#l.length || (this.state.status === "pending" ? this.scheduleGc() : this.#e.remove(this));
  }
  continue() {
    return this.#n?.continue() ?? // continuing a mutation assumes that variables are set, mutation must have been dehydrated before
    this.execute(this.state.variables);
  }
  async execute(i) {
    const f = () => {
      this.#a({ type: "continue" });
    }, r = {
      client: this.#t,
      meta: this.options.meta,
      mutationKey: this.options.mutationKey
    };
    this.#n = Th({
      fn: () => this.options.mutationFn ? this.options.mutationFn(i, r) : Promise.reject(new Error("No mutationFn found")),
      onFail: (O, C) => {
        this.#a({ type: "failed", failureCount: O, error: C });
      },
      onPause: () => {
        this.#a({ type: "pause" });
      },
      onContinue: f,
      retry: this.options.retry ?? 0,
      retryDelay: this.options.retryDelay,
      networkMode: this.options.networkMode,
      canRun: () => this.#e.canRun(this)
    });
    const o = this.state.status === "pending", p = !this.#n.canStart();
    try {
      if (o)
        f();
      else {
        this.#a({ type: "pending", variables: i, isPaused: p }), this.#e.config.onMutate && await this.#e.config.onMutate(
          i,
          this,
          r
        );
        const C = await this.options.onMutate?.(
          i,
          r
        );
        C !== this.state.context && this.#a({
          type: "pending",
          context: C,
          variables: i,
          isPaused: p
        });
      }
      const O = await this.#n.start();
      return await this.#e.config.onSuccess?.(
        O,
        i,
        this.state.context,
        this,
        r
      ), await this.options.onSuccess?.(
        O,
        i,
        this.state.context,
        r
      ), await this.#e.config.onSettled?.(
        O,
        null,
        this.state.variables,
        this.state.context,
        this,
        r
      ), await this.options.onSettled?.(
        O,
        null,
        i,
        this.state.context,
        r
      ), this.#a({ type: "success", data: O }), O;
    } catch (O) {
      try {
        await this.#e.config.onError?.(
          O,
          i,
          this.state.context,
          this,
          r
        );
      } catch (C) {
        Promise.reject(C);
      }
      try {
        await this.options.onError?.(
          O,
          i,
          this.state.context,
          r
        );
      } catch (C) {
        Promise.reject(C);
      }
      try {
        await this.#e.config.onSettled?.(
          void 0,
          O,
          this.state.variables,
          this.state.context,
          this,
          r
        );
      } catch (C) {
        Promise.reject(C);
      }
      try {
        await this.options.onSettled?.(
          void 0,
          O,
          i,
          this.state.context,
          r
        );
      } catch (C) {
        Promise.reject(C);
      }
      throw this.#a({ type: "error", error: O }), O;
    } finally {
      this.#e.runNext(this);
    }
  }
  #a(i) {
    const f = (r) => {
      switch (i.type) {
        case "failed":
          return {
            ...r,
            failureCount: i.failureCount,
            failureReason: i.error
          };
        case "pause":
          return {
            ...r,
            isPaused: !0
          };
        case "continue":
          return {
            ...r,
            isPaused: !1
          };
        case "pending":
          return {
            ...r,
            context: i.context,
            data: void 0,
            failureCount: 0,
            failureReason: null,
            error: null,
            isPaused: i.isPaused,
            status: "pending",
            variables: i.variables,
            submittedAt: Date.now()
          };
        case "success":
          return {
            ...r,
            data: i.data,
            failureCount: 0,
            failureReason: null,
            error: null,
            status: "success",
            isPaused: !1
          };
        case "error":
          return {
            ...r,
            data: void 0,
            error: i.error,
            failureCount: r.failureCount + 1,
            failureReason: i.error,
            isPaused: !1,
            status: "error"
          };
      }
    };
    this.state = f(this.state), te.batch(() => {
      this.#l.forEach((r) => {
        r.onMutationUpdate(i);
      }), this.#e.notify({
        mutation: this,
        type: "updated",
        action: i
      });
    });
  }
};
function wv() {
  return {
    context: void 0,
    data: void 0,
    error: null,
    failureCount: 0,
    failureReason: null,
    isPaused: !1,
    status: "idle",
    variables: void 0,
    submittedAt: 0
  };
}
var Zv = class extends si {
  constructor(i = {}) {
    super(), this.config = i, this.#t = /* @__PURE__ */ new Set(), this.#l = /* @__PURE__ */ new Map(), this.#e = 0;
  }
  #t;
  #l;
  #e;
  build(i, f, r) {
    const o = new Xv({
      client: i,
      mutationCache: this,
      mutationId: ++this.#e,
      options: i.defaultMutationOptions(f),
      state: r
    });
    return this.add(o), o;
  }
  add(i) {
    this.#t.add(i);
    const f = ni(i);
    if (typeof f == "string") {
      const r = this.#l.get(f);
      r ? r.push(i) : this.#l.set(f, [i]);
    }
    this.notify({ type: "added", mutation: i });
  }
  remove(i) {
    if (this.#t.delete(i)) {
      const f = ni(i);
      if (typeof f == "string") {
        const r = this.#l.get(f);
        if (r)
          if (r.length > 1) {
            const o = r.indexOf(i);
            o !== -1 && r.splice(o, 1);
          } else r[0] === i && this.#l.delete(f);
      }
    }
    this.notify({ type: "removed", mutation: i });
  }
  canRun(i) {
    const f = ni(i);
    if (typeof f == "string") {
      const o = this.#l.get(f)?.find(
        (p) => p.state.status === "pending"
      );
      return !o || o === i;
    } else
      return !0;
  }
  runNext(i) {
    const f = ni(i);
    return typeof f == "string" ? this.#l.get(f)?.find((o) => o !== i && o.state.isPaused)?.continue() ?? Promise.resolve() : Promise.resolve();
  }
  clear() {
    te.batch(() => {
      this.#t.forEach((i) => {
        this.notify({ type: "removed", mutation: i });
      }), this.#t.clear(), this.#l.clear();
    });
  }
  getAll() {
    return Array.from(this.#t);
  }
  find(i) {
    const f = { exact: !0, ...i };
    return this.getAll().find(
      (r) => nh(f, r)
    );
  }
  findAll(i = {}) {
    return this.getAll().filter((f) => nh(i, f));
  }
  notify(i) {
    te.batch(() => {
      this.listeners.forEach((f) => {
        f(i);
      });
    });
  }
  resumePausedMutations() {
    const i = this.getAll().filter((f) => f.state.isPaused);
    return te.batch(
      () => Promise.all(
        i.map((f) => f.continue().catch(He))
      )
    );
  }
};
function ni(i) {
  return i.options.scope?.id;
}
var Lv = class extends si {
  constructor(i = {}) {
    super(), this.config = i, this.#t = /* @__PURE__ */ new Map();
  }
  #t;
  build(i, f, r) {
    const o = f.queryKey, p = f.queryHash ?? wf(o, f);
    let O = this.get(p);
    return O || (O = new Qv({
      client: i,
      queryKey: o,
      queryHash: p,
      options: i.defaultQueryOptions(f),
      state: r,
      defaultOptions: i.getQueryDefaults(o)
    }), this.add(O)), O;
  }
  add(i) {
    this.#t.has(i.queryHash) || (this.#t.set(i.queryHash, i), this.notify({
      type: "added",
      query: i
    }));
  }
  remove(i) {
    const f = this.#t.get(i.queryHash);
    f && (i.destroy(), f === i && this.#t.delete(i.queryHash), this.notify({ type: "removed", query: i }));
  }
  clear() {
    te.batch(() => {
      this.getAll().forEach((i) => {
        this.remove(i);
      });
    });
  }
  get(i) {
    return this.#t.get(i);
  }
  getAll() {
    return [...this.#t.values()];
  }
  find(i) {
    const f = { exact: !0, ...i };
    return this.getAll().find(
      (r) => ah(f, r)
    );
  }
  findAll(i = {}) {
    const f = this.getAll();
    return Object.keys(i).length > 0 ? f.filter((r) => ah(i, r)) : f;
  }
  notify(i) {
    te.batch(() => {
      this.listeners.forEach((f) => {
        f(i);
      });
    });
  }
  onFocus() {
    te.batch(() => {
      this.getAll().forEach((i) => {
        i.onFocus();
      });
    });
  }
  onOnline() {
    te.batch(() => {
      this.getAll().forEach((i) => {
        i.onOnline();
      });
    });
  }
}, Vv = class {
  #t;
  #l;
  #e;
  #n;
  #a;
  #i;
  #c;
  #u;
  constructor(i = {}) {
    this.#t = i.queryCache || new Lv(), this.#l = i.mutationCache || new Zv(), this.#e = i.defaultOptions || {}, this.#n = /* @__PURE__ */ new Map(), this.#a = /* @__PURE__ */ new Map(), this.#i = 0;
  }
  mount() {
    this.#i++, this.#i === 1 && (this.#c = Sh.subscribe(async (i) => {
      i && (await this.resumePausedMutations(), this.#t.onFocus());
    }), this.#u = ci.subscribe(async (i) => {
      i && (await this.resumePausedMutations(), this.#t.onOnline());
    }));
  }
  unmount() {
    this.#i--, this.#i === 0 && (this.#c?.(), this.#c = void 0, this.#u?.(), this.#u = void 0);
  }
  isFetching(i) {
    return this.#t.findAll({ ...i, fetchStatus: "fetching" }).length;
  }
  isMutating(i) {
    return this.#l.findAll({ ...i, status: "pending" }).length;
  }
  /**
   * Imperative (non-reactive) way to retrieve data for a QueryKey.
   * Should only be used in callbacks or functions where reading the latest data is necessary, e.g. for optimistic updates.
   *
   * Hint: Do not use this function inside a component, because it won't receive updates.
   * Use `useQuery` to create a `QueryObserver` that subscribes to changes.
   */
  getQueryData(i) {
    const f = this.defaultQueryOptions({ queryKey: i });
    return this.#t.get(f.queryHash)?.state.data;
  }
  ensureQueryData(i) {
    const f = this.defaultQueryOptions(i), r = this.#t.build(this, f), o = r.state.data;
    return o === void 0 ? this.fetchQuery(i) : (i.revalidateIfStale && r.isStaleByTime(Bf(f.staleTime, r)) && this.prefetchQuery(f), Promise.resolve(o));
  }
  getQueriesData(i) {
    return this.#t.findAll(i).map(({ queryKey: f, state: r }) => {
      const o = r.data;
      return [f, o];
    });
  }
  setQueryData(i, f, r) {
    const o = this.defaultQueryOptions({ queryKey: i }), O = this.#t.get(
      o.queryHash
    )?.state.data, C = Tv(f, O);
    if (C !== void 0)
      return this.#t.build(this, o).setData(C, { ...r, manual: !0 });
  }
  setQueriesData(i, f, r) {
    return te.batch(
      () => this.#t.findAll(i).map(({ queryKey: o }) => [
        o,
        this.setQueryData(o, f, r)
      ])
    );
  }
  getQueryState(i) {
    const f = this.defaultQueryOptions({ queryKey: i });
    return this.#t.get(
      f.queryHash
    )?.state;
  }
  removeQueries(i) {
    const f = this.#t;
    te.batch(() => {
      f.findAll(i).forEach((r) => {
        f.remove(r);
      });
    });
  }
  resetQueries(i, f) {
    const r = this.#t;
    return te.batch(() => (r.findAll(i).forEach((o) => {
      o.reset();
    }), this.refetchQueries(
      {
        type: "active",
        ...i
      },
      f
    )));
  }
  cancelQueries(i, f = {}) {
    const r = { revert: !0, ...f }, o = te.batch(
      () => this.#t.findAll(i).map((p) => p.cancel(r))
    );
    return Promise.all(o).then(He).catch(He);
  }
  invalidateQueries(i, f = {}) {
    return te.batch(() => (this.#t.findAll(i).forEach((r) => {
      r.invalidate();
    }), i?.refetchType === "none" ? Promise.resolve() : this.refetchQueries(
      {
        ...i,
        type: i?.refetchType ?? i?.type ?? "active"
      },
      f
    )));
  }
  refetchQueries(i, f = {}) {
    const r = {
      ...f,
      cancelRefetch: f.cancelRefetch ?? !0
    }, o = te.batch(
      () => this.#t.findAll(i).filter((p) => !p.isDisabled() && !p.isStatic()).map((p) => {
        let O = p.fetch(void 0, r);
        return r.throwOnError || (O = O.catch(He)), p.state.fetchStatus === "paused" ? Promise.resolve() : O;
      })
    );
    return Promise.all(o).then(He);
  }
  fetchQuery(i) {
    const f = this.defaultQueryOptions(i);
    f.retry === void 0 && (f.retry = !1);
    const r = this.#t.build(this, f);
    return r.isStaleByTime(
      Bf(f.staleTime, r)
    ) ? r.fetch(f) : Promise.resolve(r.state.data);
  }
  prefetchQuery(i) {
    return this.fetchQuery(i).then(He).catch(He);
  }
  fetchInfiniteQuery(i) {
    return i.behavior = sh(i.pages), this.fetchQuery(i);
  }
  prefetchInfiniteQuery(i) {
    return this.fetchInfiniteQuery(i).then(He).catch(He);
  }
  ensureInfiniteQueryData(i) {
    return i.behavior = sh(i.pages), this.ensureQueryData(i);
  }
  resumePausedMutations() {
    return ci.isOnline() ? this.#l.resumePausedMutations() : Promise.resolve();
  }
  getQueryCache() {
    return this.#t;
  }
  getMutationCache() {
    return this.#l;
  }
  getDefaultOptions() {
    return this.#e;
  }
  setDefaultOptions(i) {
    this.#e = i;
  }
  setQueryDefaults(i, f) {
    this.#n.set(Gn(i), {
      queryKey: i,
      defaultOptions: f
    });
  }
  getQueryDefaults(i) {
    const f = [...this.#n.values()], r = {};
    return f.forEach((o) => {
      Yn(i, o.queryKey) && Object.assign(r, o.defaultOptions);
    }), r;
  }
  setMutationDefaults(i, f) {
    this.#a.set(Gn(i), {
      mutationKey: i,
      defaultOptions: f
    });
  }
  getMutationDefaults(i) {
    const f = [...this.#a.values()], r = {};
    return f.forEach((o) => {
      Yn(i, o.mutationKey) && Object.assign(r, o.defaultOptions);
    }), r;
  }
  defaultQueryOptions(i) {
    if (i._defaulted)
      return i;
    const f = {
      ...this.#e.queries,
      ...this.getQueryDefaults(i.queryKey),
      ...i,
      _defaulted: !0
    };
    return f.queryHash || (f.queryHash = wf(
      f.queryKey,
      f
    )), f.refetchOnReconnect === void 0 && (f.refetchOnReconnect = f.networkMode !== "always"), f.throwOnError === void 0 && (f.throwOnError = !!f.suspense), !f.networkMode && f.persister && (f.networkMode = "offlineFirst"), f.queryFn === Zf && (f.enabled = !1), f;
  }
  defaultMutationOptions(i) {
    return i?._defaulted ? i : {
      ...this.#e.mutations,
      ...i?.mutationKey && this.getMutationDefaults(i.mutationKey),
      ...i,
      _defaulted: !0
    };
  }
  clear() {
    this.#t.clear(), this.#l.clear();
  }
}, At = Xf(), Eh = At.createContext(
  void 0
), V0 = (i) => {
  const f = At.useContext(Eh);
  if (!f)
    throw new Error("No QueryClient set, use QueryClientProvider to set one");
  return f;
}, Kv = ({
  client: i,
  children: f
}) => (At.useEffect(() => (i.mount(), () => {
  i.unmount();
}), [i]), /* @__PURE__ */ Tt.jsx(Eh.Provider, { value: i, children: f }));
class Jv extends At.Component {
  constructor(f) {
    super(f), this.state = { hasError: !1, error: null };
  }
  static getDerivedStateFromError(f) {
    return { hasError: !0, error: f };
  }
  componentDidCatch(f, r) {
    console.error(`[ErrorBoundary] ${this.props.viewId ?? "unknown"}:`, f, r);
  }
  render() {
    return this.state.hasError ? /* @__PURE__ */ Tt.jsxs("div", { className: "glass-panel rounded-2xl p-8 mt-6 text-center", children: [
      /* @__PURE__ */ Tt.jsx("div", { className: "text-2xl font-bold text-red-400 mb-2", children: "Something went wrong" }),
      /* @__PURE__ */ Tt.jsxs("p", { className: "text-slate-400 mb-4", children: [
        "Route: ",
        /* @__PURE__ */ Tt.jsx("code", { className: "text-slate-300", children: this.props.viewId ?? "unknown" })
      ] }),
      /* @__PURE__ */ Tt.jsx("pre", { className: "text-xs text-slate-500 bg-slate-950/80 rounded-xl p-4 overflow-auto text-left max-h-40", children: this.state.error?.message }),
      /* @__PURE__ */ Tt.jsx(
        "button",
        {
          className: "mt-4 px-4 py-2 bg-brand-blue/20 text-brand-blue rounded-lg hover:bg-brand-blue/30 transition",
          onClick: () => this.setState({ hasError: !1, error: null }),
          children: "Try again"
        }
      )
    ] }) : this.props.children;
  }
}
function Oh(i) {
  var f, r, o = "";
  if (typeof i == "string" || typeof i == "number") o += i;
  else if (typeof i == "object") if (Array.isArray(i)) {
    var p = i.length;
    for (f = 0; f < p; f++) i[f] && (r = Oh(i[f])) && (o && (o += " "), o += r);
  } else for (r in i) i[r] && (o && (o += " "), o += r);
  return o;
}
function kv() {
  for (var i, f, r = 0, o = "", p = arguments.length; r < p; r++) (i = arguments[r]) && (f = Oh(i)) && (o && (o += " "), o += f);
  return o;
}
const Fv = (i, f) => {
  const r = new Array(i.length + f.length);
  for (let o = 0; o < i.length; o++)
    r[o] = i[o];
  for (let o = 0; o < f.length; o++)
    r[i.length + o] = f[o];
  return r;
}, Wv = (i, f) => ({
  classGroupId: i,
  validator: f
}), Mh = (i = /* @__PURE__ */ new Map(), f = null, r) => ({
  nextPart: i,
  validators: f,
  classGroupId: r
}), fi = "-", rh = [], $v = "arbitrary..", Iv = (i) => {
  const f = t0(i), {
    conflictingClassGroups: r,
    conflictingClassGroupModifiers: o
  } = i;
  return {
    getClassGroupId: (C) => {
      if (C.startsWith("[") && C.endsWith("]"))
        return Pv(C);
      const D = C.split(fi), A = D[0] === "" && D.length > 1 ? 1 : 0;
      return _h(D, A, f);
    },
    getConflictingClassGroupIds: (C, D) => {
      if (D) {
        const A = o[C], S = r[C];
        return A ? S ? Fv(S, A) : A : S || rh;
      }
      return r[C] || rh;
    }
  };
}, _h = (i, f, r) => {
  if (i.length - f === 0)
    return r.classGroupId;
  const p = i[f], O = r.nextPart.get(p);
  if (O) {
    const S = _h(i, f + 1, O);
    if (S) return S;
  }
  const C = r.validators;
  if (C === null)
    return;
  const D = f === 0 ? i.join(fi) : i.slice(f).join(fi), A = C.length;
  for (let S = 0; S < A; S++) {
    const G = C[S];
    if (G.validator(D))
      return G.classGroupId;
  }
}, Pv = (i) => i.slice(1, -1).indexOf(":") === -1 ? void 0 : (() => {
  const f = i.slice(1, -1), r = f.indexOf(":"), o = f.slice(0, r);
  return o ? $v + o : void 0;
})(), t0 = (i) => {
  const {
    theme: f,
    classGroups: r
  } = i;
  return e0(r, f);
}, e0 = (i, f) => {
  const r = Mh();
  for (const o in i) {
    const p = i[o];
    Lf(p, r, o, f);
  }
  return r;
}, Lf = (i, f, r, o) => {
  const p = i.length;
  for (let O = 0; O < p; O++) {
    const C = i[O];
    l0(C, f, r, o);
  }
}, l0 = (i, f, r, o) => {
  if (typeof i == "string") {
    a0(i, f, r);
    return;
  }
  if (typeof i == "function") {
    n0(i, f, r, o);
    return;
  }
  u0(i, f, r, o);
}, a0 = (i, f, r) => {
  const o = i === "" ? f : Dh(f, i);
  o.classGroupId = r;
}, n0 = (i, f, r, o) => {
  if (i0(i)) {
    Lf(i(o), f, r, o);
    return;
  }
  f.validators === null && (f.validators = []), f.validators.push(Wv(r, i));
}, u0 = (i, f, r, o) => {
  const p = Object.entries(i), O = p.length;
  for (let C = 0; C < O; C++) {
    const [D, A] = p[C];
    Lf(A, Dh(f, D), r, o);
  }
}, Dh = (i, f) => {
  let r = i;
  const o = f.split(fi), p = o.length;
  for (let O = 0; O < p; O++) {
    const C = o[O];
    let D = r.nextPart.get(C);
    D || (D = Mh(), r.nextPart.set(C, D)), r = D;
  }
  return r;
}, i0 = (i) => "isThemeGetter" in i && i.isThemeGetter === !0, c0 = (i) => {
  if (i < 1)
    return {
      get: () => {
      },
      set: () => {
      }
    };
  let f = 0, r = /* @__PURE__ */ Object.create(null), o = /* @__PURE__ */ Object.create(null);
  const p = (O, C) => {
    r[O] = C, f++, f > i && (f = 0, o = r, r = /* @__PURE__ */ Object.create(null));
  };
  return {
    get(O) {
      let C = r[O];
      if (C !== void 0)
        return C;
      if ((C = o[O]) !== void 0)
        return p(O, C), C;
    },
    set(O, C) {
      O in r ? r[O] = C : p(O, C);
    }
  };
}, Yf = "!", dh = ":", f0 = [], hh = (i, f, r, o, p) => ({
  modifiers: i,
  hasImportantModifier: f,
  baseClassName: r,
  maybePostfixModifierPosition: o,
  isExternal: p
}), s0 = (i) => {
  const {
    prefix: f,
    experimentalParseClassName: r
  } = i;
  let o = (p) => {
    const O = [];
    let C = 0, D = 0, A = 0, S;
    const G = p.length;
    for (let k = 0; k < G; k++) {
      const nt = p[k];
      if (C === 0 && D === 0) {
        if (nt === dh) {
          O.push(p.slice(A, k)), A = k + 1;
          continue;
        }
        if (nt === "/") {
          S = k;
          continue;
        }
      }
      nt === "[" ? C++ : nt === "]" ? C-- : nt === "(" ? D++ : nt === ")" && D--;
    }
    const H = O.length === 0 ? p : p.slice(A);
    let J = H, st = !1;
    H.endsWith(Yf) ? (J = H.slice(0, -1), st = !0) : (
      /**
       * In Tailwind CSS v3 the important modifier was at the start of the base class name. This is still supported for legacy reasons.
       * @see https://github.com/dcastil/tailwind-merge/issues/513#issuecomment-2614029864
       */
      H.startsWith(Yf) && (J = H.slice(1), st = !0)
    );
    const $ = S && S > A ? S - A : void 0;
    return hh(O, st, J, $);
  };
  if (f) {
    const p = f + dh, O = o;
    o = (C) => C.startsWith(p) ? O(C.slice(p.length)) : hh(f0, !1, C, void 0, !0);
  }
  if (r) {
    const p = o;
    o = (O) => r({
      className: O,
      parseClassName: p
    });
  }
  return o;
}, o0 = (i) => {
  const f = /* @__PURE__ */ new Map();
  return i.orderSensitiveModifiers.forEach((r, o) => {
    f.set(r, 1e6 + o);
  }), (r) => {
    const o = [];
    let p = [];
    for (let O = 0; O < r.length; O++) {
      const C = r[O], D = C[0] === "[", A = f.has(C);
      D || A ? (p.length > 0 && (p.sort(), o.push(...p), p = []), o.push(C)) : p.push(C);
    }
    return p.length > 0 && (p.sort(), o.push(...p)), o;
  };
}, r0 = (i) => ({
  cache: c0(i.cacheSize),
  parseClassName: s0(i),
  sortModifiers: o0(i),
  ...Iv(i)
}), d0 = /\s+/, h0 = (i, f) => {
  const {
    parseClassName: r,
    getClassGroupId: o,
    getConflictingClassGroupIds: p,
    sortModifiers: O
  } = f, C = [], D = i.trim().split(d0);
  let A = "";
  for (let S = D.length - 1; S >= 0; S -= 1) {
    const G = D[S], {
      isExternal: H,
      modifiers: J,
      hasImportantModifier: st,
      baseClassName: $,
      maybePostfixModifierPosition: k
    } = r(G);
    if (H) {
      A = G + (A.length > 0 ? " " + A : A);
      continue;
    }
    let nt = !!k, ot = o(nt ? $.substring(0, k) : $);
    if (!ot) {
      if (!nt) {
        A = G + (A.length > 0 ? " " + A : A);
        continue;
      }
      if (ot = o($), !ot) {
        A = G + (A.length > 0 ? " " + A : A);
        continue;
      }
      nt = !1;
    }
    const Nt = J.length === 0 ? "" : J.length === 1 ? J[0] : O(J).join(":"), gt = st ? Nt + Yf : Nt, _t = gt + ot;
    if (C.indexOf(_t) > -1)
      continue;
    C.push(_t);
    const Ct = p(ot, nt);
    for (let Et = 0; Et < Ct.length; ++Et) {
      const I = Ct[Et];
      C.push(gt + I);
    }
    A = G + (A.length > 0 ? " " + A : A);
  }
  return A;
}, m0 = (...i) => {
  let f = 0, r, o, p = "";
  for (; f < i.length; )
    (r = i[f++]) && (o = xh(r)) && (p && (p += " "), p += o);
  return p;
}, xh = (i) => {
  if (typeof i == "string")
    return i;
  let f, r = "";
  for (let o = 0; o < i.length; o++)
    i[o] && (f = xh(i[o])) && (r && (r += " "), r += f);
  return r;
}, y0 = (i, ...f) => {
  let r, o, p, O;
  const C = (A) => {
    const S = f.reduce((G, H) => H(G), i());
    return r = r0(S), o = r.cache.get, p = r.cache.set, O = D, D(A);
  }, D = (A) => {
    const S = o(A);
    if (S)
      return S;
    const G = h0(A, r);
    return p(A, G), G;
  };
  return O = C, (...A) => O(m0(...A));
}, v0 = [], wt = (i) => {
  const f = (r) => r[i] || v0;
  return f.isThemeGetter = !0, f;
}, Ch = /^\[(?:(\w[\w-]*):)?(.+)\]$/i, Uh = /^\((?:(\w[\w-]*):)?(.+)\)$/i, g0 = /^\d+(?:\.\d+)?\/\d+(?:\.\d+)?$/, b0 = /^(\d+(\.\d+)?)?(xs|sm|md|lg|xl)$/, p0 = /\d+(%|px|r?em|[sdl]?v([hwib]|min|max)|pt|pc|in|cm|mm|cap|ch|ex|r?lh|cq(w|h|i|b|min|max))|\b(calc|min|max|clamp)\(.+\)|^0$/, S0 = /^(rgba?|hsla?|hwb|(ok)?(lab|lch)|color-mix)\(.+\)$/, z0 = /^(inset_)?-?((\d+)?\.?(\d+)[a-z]+|0)_-?((\d+)?\.?(\d+)[a-z]+|0)/, T0 = /^(url|image|image-set|cross-fade|element|(repeating-)?(linear|radial|conic)-gradient)\(.+\)$/, Hl = (i) => g0.test(i), et = (i) => !!i && !Number.isNaN(Number(i)), ql = (i) => !!i && Number.isInteger(Number(i)), qf = (i) => i.endsWith("%") && et(i.slice(0, -1)), il = (i) => b0.test(i), Rh = () => !0, A0 = (i) => (
  // `colorFunctionRegex` check is necessary because color functions can have percentages in them which which would be incorrectly classified as lengths.
  // For example, `hsl(0 0% 0%)` would be classified as a length without this check.
  // I could also use lookbehind assertion in `lengthUnitRegex` but that isn't supported widely enough.
  p0.test(i) && !S0.test(i)
), Vf = () => !1, E0 = (i) => z0.test(i), O0 = (i) => T0.test(i), M0 = (i) => !Q(i) && !Y(i), _0 = (i) => jl(i, qh, Vf), Q = (i) => Ch.test(i), ea = (i) => jl(i, jh, A0), mh = (i) => jl(i, q0, et), D0 = (i) => jl(i, Qh, Rh), x0 = (i) => jl(i, Bh, Vf), yh = (i) => jl(i, Nh, Vf), C0 = (i) => jl(i, Hh, O0), ui = (i) => jl(i, Gh, E0), Y = (i) => Uh.test(i), Bn = (i) => la(i, jh), U0 = (i) => la(i, Bh), vh = (i) => la(i, Nh), R0 = (i) => la(i, qh), N0 = (i) => la(i, Hh), ii = (i) => la(i, Gh, !0), H0 = (i) => la(i, Qh, !0), jl = (i, f, r) => {
  const o = Ch.exec(i);
  return o ? o[1] ? f(o[1]) : r(o[2]) : !1;
}, la = (i, f, r = !1) => {
  const o = Uh.exec(i);
  return o ? o[1] ? f(o[1]) : r : !1;
}, Nh = (i) => i === "position" || i === "percentage", Hh = (i) => i === "image" || i === "url", qh = (i) => i === "length" || i === "size" || i === "bg-size", jh = (i) => i === "length", q0 = (i) => i === "number", Bh = (i) => i === "family-name", Qh = (i) => i === "number" || i === "weight", Gh = (i) => i === "shadow", j0 = () => {
  const i = wt("color"), f = wt("font"), r = wt("text"), o = wt("font-weight"), p = wt("tracking"), O = wt("leading"), C = wt("breakpoint"), D = wt("container"), A = wt("spacing"), S = wt("radius"), G = wt("shadow"), H = wt("inset-shadow"), J = wt("text-shadow"), st = wt("drop-shadow"), $ = wt("blur"), k = wt("perspective"), nt = wt("aspect"), ot = wt("ease"), Nt = wt("animate"), gt = () => ["auto", "avoid", "all", "avoid-page", "page", "left", "right", "column"], _t = () => [
    "center",
    "top",
    "bottom",
    "left",
    "right",
    "top-left",
    // Deprecated since Tailwind CSS v4.1.0, see https://github.com/tailwindlabs/tailwindcss/pull/17378
    "left-top",
    "top-right",
    // Deprecated since Tailwind CSS v4.1.0, see https://github.com/tailwindlabs/tailwindcss/pull/17378
    "right-top",
    "bottom-right",
    // Deprecated since Tailwind CSS v4.1.0, see https://github.com/tailwindlabs/tailwindcss/pull/17378
    "right-bottom",
    "bottom-left",
    // Deprecated since Tailwind CSS v4.1.0, see https://github.com/tailwindlabs/tailwindcss/pull/17378
    "left-bottom"
  ], Ct = () => [..._t(), Y, Q], Et = () => ["auto", "hidden", "clip", "visible", "scroll"], I = () => ["auto", "contain", "none"], j = () => [Y, Q, A], Dt = () => [Hl, "full", "auto", ...j()], Ye = () => [ql, "none", "subgrid", Y, Q], fe = () => ["auto", {
    span: ["full", ql, Y, Q]
  }, ql, Y, Q], Yt = () => [ql, "auto", Y, Q], qe = () => ["auto", "min", "max", "fr", Y, Q], se = () => ["start", "end", "center", "between", "around", "evenly", "stretch", "baseline", "center-safe", "end-safe"], Zt = () => ["start", "end", "center", "stretch", "center-safe", "end-safe"], T = () => ["auto", ...j()], U = () => [Hl, "auto", "full", "dvw", "dvh", "lvw", "lvh", "svw", "svh", "min", "max", "fit", ...j()], V = () => [Hl, "screen", "full", "dvw", "lvw", "svw", "min", "max", "fit", ...j()], rt = () => [Hl, "screen", "full", "lh", "dvh", "lvh", "svh", "min", "max", "fit", ...j()], R = () => [i, Y, Q], m = () => [..._t(), vh, yh, {
    position: [Y, Q]
  }], x = () => ["no-repeat", {
    repeat: ["", "x", "y", "space", "round"]
  }], N = () => ["auto", "cover", "contain", R0, _0, {
    size: [Y, Q]
  }], q = () => [qf, Bn, ea], w = () => [
    // Deprecated since Tailwind CSS v4.0.0
    "",
    "none",
    "full",
    S,
    Y,
    Q
  ], L = () => ["", et, Bn, ea], ct = () => ["solid", "dashed", "dotted", "double"], Lt = () => ["normal", "multiply", "screen", "overlay", "darken", "lighten", "color-dodge", "color-burn", "hard-light", "soft-light", "difference", "exclusion", "hue", "saturation", "color", "luminosity"], tt = () => [et, qf, vh, yh], cl = () => [
    // Deprecated since Tailwind CSS v4.0.0
    "",
    "none",
    $,
    Y,
    Q
  ], Xe = () => ["none", et, Y, Q], fl = () => ["none", et, Y, Q], aa = () => [et, Y, Q], Se = () => [Hl, "full", ...j()];
  return {
    cacheSize: 500,
    theme: {
      animate: ["spin", "ping", "pulse", "bounce"],
      aspect: ["video"],
      blur: [il],
      breakpoint: [il],
      color: [Rh],
      container: [il],
      "drop-shadow": [il],
      ease: ["in", "out", "in-out"],
      font: [M0],
      "font-weight": ["thin", "extralight", "light", "normal", "medium", "semibold", "bold", "extrabold", "black"],
      "inset-shadow": [il],
      leading: ["none", "tight", "snug", "normal", "relaxed", "loose"],
      perspective: ["dramatic", "near", "normal", "midrange", "distant", "none"],
      radius: [il],
      shadow: [il],
      spacing: ["px", et],
      text: [il],
      "text-shadow": [il],
      tracking: ["tighter", "tight", "normal", "wide", "wider", "widest"]
    },
    classGroups: {
      // --------------
      // --- Layout ---
      // --------------
      /**
       * Aspect Ratio
       * @see https://tailwindcss.com/docs/aspect-ratio
       */
      aspect: [{
        aspect: ["auto", "square", Hl, Q, Y, nt]
      }],
      /**
       * Container
       * @see https://tailwindcss.com/docs/container
       * @deprecated since Tailwind CSS v4.0.0
       */
      container: ["container"],
      /**
       * Columns
       * @see https://tailwindcss.com/docs/columns
       */
      columns: [{
        columns: [et, Q, Y, D]
      }],
      /**
       * Break After
       * @see https://tailwindcss.com/docs/break-after
       */
      "break-after": [{
        "break-after": gt()
      }],
      /**
       * Break Before
       * @see https://tailwindcss.com/docs/break-before
       */
      "break-before": [{
        "break-before": gt()
      }],
      /**
       * Break Inside
       * @see https://tailwindcss.com/docs/break-inside
       */
      "break-inside": [{
        "break-inside": ["auto", "avoid", "avoid-page", "avoid-column"]
      }],
      /**
       * Box Decoration Break
       * @see https://tailwindcss.com/docs/box-decoration-break
       */
      "box-decoration": [{
        "box-decoration": ["slice", "clone"]
      }],
      /**
       * Box Sizing
       * @see https://tailwindcss.com/docs/box-sizing
       */
      box: [{
        box: ["border", "content"]
      }],
      /**
       * Display
       * @see https://tailwindcss.com/docs/display
       */
      display: ["block", "inline-block", "inline", "flex", "inline-flex", "table", "inline-table", "table-caption", "table-cell", "table-column", "table-column-group", "table-footer-group", "table-header-group", "table-row-group", "table-row", "flow-root", "grid", "inline-grid", "contents", "list-item", "hidden"],
      /**
       * Screen Reader Only
       * @see https://tailwindcss.com/docs/display#screen-reader-only
       */
      sr: ["sr-only", "not-sr-only"],
      /**
       * Floats
       * @see https://tailwindcss.com/docs/float
       */
      float: [{
        float: ["right", "left", "none", "start", "end"]
      }],
      /**
       * Clear
       * @see https://tailwindcss.com/docs/clear
       */
      clear: [{
        clear: ["left", "right", "both", "none", "start", "end"]
      }],
      /**
       * Isolation
       * @see https://tailwindcss.com/docs/isolation
       */
      isolation: ["isolate", "isolation-auto"],
      /**
       * Object Fit
       * @see https://tailwindcss.com/docs/object-fit
       */
      "object-fit": [{
        object: ["contain", "cover", "fill", "none", "scale-down"]
      }],
      /**
       * Object Position
       * @see https://tailwindcss.com/docs/object-position
       */
      "object-position": [{
        object: Ct()
      }],
      /**
       * Overflow
       * @see https://tailwindcss.com/docs/overflow
       */
      overflow: [{
        overflow: Et()
      }],
      /**
       * Overflow X
       * @see https://tailwindcss.com/docs/overflow
       */
      "overflow-x": [{
        "overflow-x": Et()
      }],
      /**
       * Overflow Y
       * @see https://tailwindcss.com/docs/overflow
       */
      "overflow-y": [{
        "overflow-y": Et()
      }],
      /**
       * Overscroll Behavior
       * @see https://tailwindcss.com/docs/overscroll-behavior
       */
      overscroll: [{
        overscroll: I()
      }],
      /**
       * Overscroll Behavior X
       * @see https://tailwindcss.com/docs/overscroll-behavior
       */
      "overscroll-x": [{
        "overscroll-x": I()
      }],
      /**
       * Overscroll Behavior Y
       * @see https://tailwindcss.com/docs/overscroll-behavior
       */
      "overscroll-y": [{
        "overscroll-y": I()
      }],
      /**
       * Position
       * @see https://tailwindcss.com/docs/position
       */
      position: ["static", "fixed", "absolute", "relative", "sticky"],
      /**
       * Inset
       * @see https://tailwindcss.com/docs/top-right-bottom-left
       */
      inset: [{
        inset: Dt()
      }],
      /**
       * Inset Inline
       * @see https://tailwindcss.com/docs/top-right-bottom-left
       */
      "inset-x": [{
        "inset-x": Dt()
      }],
      /**
       * Inset Block
       * @see https://tailwindcss.com/docs/top-right-bottom-left
       */
      "inset-y": [{
        "inset-y": Dt()
      }],
      /**
       * Inset Inline Start
       * @see https://tailwindcss.com/docs/top-right-bottom-left
       * @todo class group will be renamed to `inset-s` in next major release
       */
      start: [{
        "inset-s": Dt(),
        /**
         * @deprecated since Tailwind CSS v4.2.0 in favor of `inset-s-*` utilities.
         * @see https://github.com/tailwindlabs/tailwindcss/pull/19613
         */
        start: Dt()
      }],
      /**
       * Inset Inline End
       * @see https://tailwindcss.com/docs/top-right-bottom-left
       * @todo class group will be renamed to `inset-e` in next major release
       */
      end: [{
        "inset-e": Dt(),
        /**
         * @deprecated since Tailwind CSS v4.2.0 in favor of `inset-e-*` utilities.
         * @see https://github.com/tailwindlabs/tailwindcss/pull/19613
         */
        end: Dt()
      }],
      /**
       * Inset Block Start
       * @see https://tailwindcss.com/docs/top-right-bottom-left
       */
      "inset-bs": [{
        "inset-bs": Dt()
      }],
      /**
       * Inset Block End
       * @see https://tailwindcss.com/docs/top-right-bottom-left
       */
      "inset-be": [{
        "inset-be": Dt()
      }],
      /**
       * Top
       * @see https://tailwindcss.com/docs/top-right-bottom-left
       */
      top: [{
        top: Dt()
      }],
      /**
       * Right
       * @see https://tailwindcss.com/docs/top-right-bottom-left
       */
      right: [{
        right: Dt()
      }],
      /**
       * Bottom
       * @see https://tailwindcss.com/docs/top-right-bottom-left
       */
      bottom: [{
        bottom: Dt()
      }],
      /**
       * Left
       * @see https://tailwindcss.com/docs/top-right-bottom-left
       */
      left: [{
        left: Dt()
      }],
      /**
       * Visibility
       * @see https://tailwindcss.com/docs/visibility
       */
      visibility: ["visible", "invisible", "collapse"],
      /**
       * Z-Index
       * @see https://tailwindcss.com/docs/z-index
       */
      z: [{
        z: [ql, "auto", Y, Q]
      }],
      // ------------------------
      // --- Flexbox and Grid ---
      // ------------------------
      /**
       * Flex Basis
       * @see https://tailwindcss.com/docs/flex-basis
       */
      basis: [{
        basis: [Hl, "full", "auto", D, ...j()]
      }],
      /**
       * Flex Direction
       * @see https://tailwindcss.com/docs/flex-direction
       */
      "flex-direction": [{
        flex: ["row", "row-reverse", "col", "col-reverse"]
      }],
      /**
       * Flex Wrap
       * @see https://tailwindcss.com/docs/flex-wrap
       */
      "flex-wrap": [{
        flex: ["nowrap", "wrap", "wrap-reverse"]
      }],
      /**
       * Flex
       * @see https://tailwindcss.com/docs/flex
       */
      flex: [{
        flex: [et, Hl, "auto", "initial", "none", Q]
      }],
      /**
       * Flex Grow
       * @see https://tailwindcss.com/docs/flex-grow
       */
      grow: [{
        grow: ["", et, Y, Q]
      }],
      /**
       * Flex Shrink
       * @see https://tailwindcss.com/docs/flex-shrink
       */
      shrink: [{
        shrink: ["", et, Y, Q]
      }],
      /**
       * Order
       * @see https://tailwindcss.com/docs/order
       */
      order: [{
        order: [ql, "first", "last", "none", Y, Q]
      }],
      /**
       * Grid Template Columns
       * @see https://tailwindcss.com/docs/grid-template-columns
       */
      "grid-cols": [{
        "grid-cols": Ye()
      }],
      /**
       * Grid Column Start / End
       * @see https://tailwindcss.com/docs/grid-column
       */
      "col-start-end": [{
        col: fe()
      }],
      /**
       * Grid Column Start
       * @see https://tailwindcss.com/docs/grid-column
       */
      "col-start": [{
        "col-start": Yt()
      }],
      /**
       * Grid Column End
       * @see https://tailwindcss.com/docs/grid-column
       */
      "col-end": [{
        "col-end": Yt()
      }],
      /**
       * Grid Template Rows
       * @see https://tailwindcss.com/docs/grid-template-rows
       */
      "grid-rows": [{
        "grid-rows": Ye()
      }],
      /**
       * Grid Row Start / End
       * @see https://tailwindcss.com/docs/grid-row
       */
      "row-start-end": [{
        row: fe()
      }],
      /**
       * Grid Row Start
       * @see https://tailwindcss.com/docs/grid-row
       */
      "row-start": [{
        "row-start": Yt()
      }],
      /**
       * Grid Row End
       * @see https://tailwindcss.com/docs/grid-row
       */
      "row-end": [{
        "row-end": Yt()
      }],
      /**
       * Grid Auto Flow
       * @see https://tailwindcss.com/docs/grid-auto-flow
       */
      "grid-flow": [{
        "grid-flow": ["row", "col", "dense", "row-dense", "col-dense"]
      }],
      /**
       * Grid Auto Columns
       * @see https://tailwindcss.com/docs/grid-auto-columns
       */
      "auto-cols": [{
        "auto-cols": qe()
      }],
      /**
       * Grid Auto Rows
       * @see https://tailwindcss.com/docs/grid-auto-rows
       */
      "auto-rows": [{
        "auto-rows": qe()
      }],
      /**
       * Gap
       * @see https://tailwindcss.com/docs/gap
       */
      gap: [{
        gap: j()
      }],
      /**
       * Gap X
       * @see https://tailwindcss.com/docs/gap
       */
      "gap-x": [{
        "gap-x": j()
      }],
      /**
       * Gap Y
       * @see https://tailwindcss.com/docs/gap
       */
      "gap-y": [{
        "gap-y": j()
      }],
      /**
       * Justify Content
       * @see https://tailwindcss.com/docs/justify-content
       */
      "justify-content": [{
        justify: [...se(), "normal"]
      }],
      /**
       * Justify Items
       * @see https://tailwindcss.com/docs/justify-items
       */
      "justify-items": [{
        "justify-items": [...Zt(), "normal"]
      }],
      /**
       * Justify Self
       * @see https://tailwindcss.com/docs/justify-self
       */
      "justify-self": [{
        "justify-self": ["auto", ...Zt()]
      }],
      /**
       * Align Content
       * @see https://tailwindcss.com/docs/align-content
       */
      "align-content": [{
        content: ["normal", ...se()]
      }],
      /**
       * Align Items
       * @see https://tailwindcss.com/docs/align-items
       */
      "align-items": [{
        items: [...Zt(), {
          baseline: ["", "last"]
        }]
      }],
      /**
       * Align Self
       * @see https://tailwindcss.com/docs/align-self
       */
      "align-self": [{
        self: ["auto", ...Zt(), {
          baseline: ["", "last"]
        }]
      }],
      /**
       * Place Content
       * @see https://tailwindcss.com/docs/place-content
       */
      "place-content": [{
        "place-content": se()
      }],
      /**
       * Place Items
       * @see https://tailwindcss.com/docs/place-items
       */
      "place-items": [{
        "place-items": [...Zt(), "baseline"]
      }],
      /**
       * Place Self
       * @see https://tailwindcss.com/docs/place-self
       */
      "place-self": [{
        "place-self": ["auto", ...Zt()]
      }],
      // Spacing
      /**
       * Padding
       * @see https://tailwindcss.com/docs/padding
       */
      p: [{
        p: j()
      }],
      /**
       * Padding Inline
       * @see https://tailwindcss.com/docs/padding
       */
      px: [{
        px: j()
      }],
      /**
       * Padding Block
       * @see https://tailwindcss.com/docs/padding
       */
      py: [{
        py: j()
      }],
      /**
       * Padding Inline Start
       * @see https://tailwindcss.com/docs/padding
       */
      ps: [{
        ps: j()
      }],
      /**
       * Padding Inline End
       * @see https://tailwindcss.com/docs/padding
       */
      pe: [{
        pe: j()
      }],
      /**
       * Padding Block Start
       * @see https://tailwindcss.com/docs/padding
       */
      pbs: [{
        pbs: j()
      }],
      /**
       * Padding Block End
       * @see https://tailwindcss.com/docs/padding
       */
      pbe: [{
        pbe: j()
      }],
      /**
       * Padding Top
       * @see https://tailwindcss.com/docs/padding
       */
      pt: [{
        pt: j()
      }],
      /**
       * Padding Right
       * @see https://tailwindcss.com/docs/padding
       */
      pr: [{
        pr: j()
      }],
      /**
       * Padding Bottom
       * @see https://tailwindcss.com/docs/padding
       */
      pb: [{
        pb: j()
      }],
      /**
       * Padding Left
       * @see https://tailwindcss.com/docs/padding
       */
      pl: [{
        pl: j()
      }],
      /**
       * Margin
       * @see https://tailwindcss.com/docs/margin
       */
      m: [{
        m: T()
      }],
      /**
       * Margin Inline
       * @see https://tailwindcss.com/docs/margin
       */
      mx: [{
        mx: T()
      }],
      /**
       * Margin Block
       * @see https://tailwindcss.com/docs/margin
       */
      my: [{
        my: T()
      }],
      /**
       * Margin Inline Start
       * @see https://tailwindcss.com/docs/margin
       */
      ms: [{
        ms: T()
      }],
      /**
       * Margin Inline End
       * @see https://tailwindcss.com/docs/margin
       */
      me: [{
        me: T()
      }],
      /**
       * Margin Block Start
       * @see https://tailwindcss.com/docs/margin
       */
      mbs: [{
        mbs: T()
      }],
      /**
       * Margin Block End
       * @see https://tailwindcss.com/docs/margin
       */
      mbe: [{
        mbe: T()
      }],
      /**
       * Margin Top
       * @see https://tailwindcss.com/docs/margin
       */
      mt: [{
        mt: T()
      }],
      /**
       * Margin Right
       * @see https://tailwindcss.com/docs/margin
       */
      mr: [{
        mr: T()
      }],
      /**
       * Margin Bottom
       * @see https://tailwindcss.com/docs/margin
       */
      mb: [{
        mb: T()
      }],
      /**
       * Margin Left
       * @see https://tailwindcss.com/docs/margin
       */
      ml: [{
        ml: T()
      }],
      /**
       * Space Between X
       * @see https://tailwindcss.com/docs/margin#adding-space-between-children
       */
      "space-x": [{
        "space-x": j()
      }],
      /**
       * Space Between X Reverse
       * @see https://tailwindcss.com/docs/margin#adding-space-between-children
       */
      "space-x-reverse": ["space-x-reverse"],
      /**
       * Space Between Y
       * @see https://tailwindcss.com/docs/margin#adding-space-between-children
       */
      "space-y": [{
        "space-y": j()
      }],
      /**
       * Space Between Y Reverse
       * @see https://tailwindcss.com/docs/margin#adding-space-between-children
       */
      "space-y-reverse": ["space-y-reverse"],
      // --------------
      // --- Sizing ---
      // --------------
      /**
       * Size
       * @see https://tailwindcss.com/docs/width#setting-both-width-and-height
       */
      size: [{
        size: U()
      }],
      /**
       * Inline Size
       * @see https://tailwindcss.com/docs/width
       */
      "inline-size": [{
        inline: ["auto", ...V()]
      }],
      /**
       * Min-Inline Size
       * @see https://tailwindcss.com/docs/min-width
       */
      "min-inline-size": [{
        "min-inline": ["auto", ...V()]
      }],
      /**
       * Max-Inline Size
       * @see https://tailwindcss.com/docs/max-width
       */
      "max-inline-size": [{
        "max-inline": ["none", ...V()]
      }],
      /**
       * Block Size
       * @see https://tailwindcss.com/docs/height
       */
      "block-size": [{
        block: ["auto", ...rt()]
      }],
      /**
       * Min-Block Size
       * @see https://tailwindcss.com/docs/min-height
       */
      "min-block-size": [{
        "min-block": ["auto", ...rt()]
      }],
      /**
       * Max-Block Size
       * @see https://tailwindcss.com/docs/max-height
       */
      "max-block-size": [{
        "max-block": ["none", ...rt()]
      }],
      /**
       * Width
       * @see https://tailwindcss.com/docs/width
       */
      w: [{
        w: [D, "screen", ...U()]
      }],
      /**
       * Min-Width
       * @see https://tailwindcss.com/docs/min-width
       */
      "min-w": [{
        "min-w": [
          D,
          "screen",
          /** Deprecated. @see https://github.com/tailwindlabs/tailwindcss.com/issues/2027#issuecomment-2620152757 */
          "none",
          ...U()
        ]
      }],
      /**
       * Max-Width
       * @see https://tailwindcss.com/docs/max-width
       */
      "max-w": [{
        "max-w": [
          D,
          "screen",
          "none",
          /** Deprecated since Tailwind CSS v4.0.0. @see https://github.com/tailwindlabs/tailwindcss.com/issues/2027#issuecomment-2620152757 */
          "prose",
          /** Deprecated since Tailwind CSS v4.0.0. @see https://github.com/tailwindlabs/tailwindcss.com/issues/2027#issuecomment-2620152757 */
          {
            screen: [C]
          },
          ...U()
        ]
      }],
      /**
       * Height
       * @see https://tailwindcss.com/docs/height
       */
      h: [{
        h: ["screen", "lh", ...U()]
      }],
      /**
       * Min-Height
       * @see https://tailwindcss.com/docs/min-height
       */
      "min-h": [{
        "min-h": ["screen", "lh", "none", ...U()]
      }],
      /**
       * Max-Height
       * @see https://tailwindcss.com/docs/max-height
       */
      "max-h": [{
        "max-h": ["screen", "lh", ...U()]
      }],
      // ------------------
      // --- Typography ---
      // ------------------
      /**
       * Font Size
       * @see https://tailwindcss.com/docs/font-size
       */
      "font-size": [{
        text: ["base", r, Bn, ea]
      }],
      /**
       * Font Smoothing
       * @see https://tailwindcss.com/docs/font-smoothing
       */
      "font-smoothing": ["antialiased", "subpixel-antialiased"],
      /**
       * Font Style
       * @see https://tailwindcss.com/docs/font-style
       */
      "font-style": ["italic", "not-italic"],
      /**
       * Font Weight
       * @see https://tailwindcss.com/docs/font-weight
       */
      "font-weight": [{
        font: [o, H0, D0]
      }],
      /**
       * Font Stretch
       * @see https://tailwindcss.com/docs/font-stretch
       */
      "font-stretch": [{
        "font-stretch": ["ultra-condensed", "extra-condensed", "condensed", "semi-condensed", "normal", "semi-expanded", "expanded", "extra-expanded", "ultra-expanded", qf, Q]
      }],
      /**
       * Font Family
       * @see https://tailwindcss.com/docs/font-family
       */
      "font-family": [{
        font: [U0, x0, f]
      }],
      /**
       * Font Feature Settings
       * @see https://tailwindcss.com/docs/font-feature-settings
       */
      "font-features": [{
        "font-features": [Q]
      }],
      /**
       * Font Variant Numeric
       * @see https://tailwindcss.com/docs/font-variant-numeric
       */
      "fvn-normal": ["normal-nums"],
      /**
       * Font Variant Numeric
       * @see https://tailwindcss.com/docs/font-variant-numeric
       */
      "fvn-ordinal": ["ordinal"],
      /**
       * Font Variant Numeric
       * @see https://tailwindcss.com/docs/font-variant-numeric
       */
      "fvn-slashed-zero": ["slashed-zero"],
      /**
       * Font Variant Numeric
       * @see https://tailwindcss.com/docs/font-variant-numeric
       */
      "fvn-figure": ["lining-nums", "oldstyle-nums"],
      /**
       * Font Variant Numeric
       * @see https://tailwindcss.com/docs/font-variant-numeric
       */
      "fvn-spacing": ["proportional-nums", "tabular-nums"],
      /**
       * Font Variant Numeric
       * @see https://tailwindcss.com/docs/font-variant-numeric
       */
      "fvn-fraction": ["diagonal-fractions", "stacked-fractions"],
      /**
       * Letter Spacing
       * @see https://tailwindcss.com/docs/letter-spacing
       */
      tracking: [{
        tracking: [p, Y, Q]
      }],
      /**
       * Line Clamp
       * @see https://tailwindcss.com/docs/line-clamp
       */
      "line-clamp": [{
        "line-clamp": [et, "none", Y, mh]
      }],
      /**
       * Line Height
       * @see https://tailwindcss.com/docs/line-height
       */
      leading: [{
        leading: [
          /** Deprecated since Tailwind CSS v4.0.0. @see https://github.com/tailwindlabs/tailwindcss.com/issues/2027#issuecomment-2620152757 */
          O,
          ...j()
        ]
      }],
      /**
       * List Style Image
       * @see https://tailwindcss.com/docs/list-style-image
       */
      "list-image": [{
        "list-image": ["none", Y, Q]
      }],
      /**
       * List Style Position
       * @see https://tailwindcss.com/docs/list-style-position
       */
      "list-style-position": [{
        list: ["inside", "outside"]
      }],
      /**
       * List Style Type
       * @see https://tailwindcss.com/docs/list-style-type
       */
      "list-style-type": [{
        list: ["disc", "decimal", "none", Y, Q]
      }],
      /**
       * Text Alignment
       * @see https://tailwindcss.com/docs/text-align
       */
      "text-alignment": [{
        text: ["left", "center", "right", "justify", "start", "end"]
      }],
      /**
       * Placeholder Color
       * @deprecated since Tailwind CSS v3.0.0
       * @see https://v3.tailwindcss.com/docs/placeholder-color
       */
      "placeholder-color": [{
        placeholder: R()
      }],
      /**
       * Text Color
       * @see https://tailwindcss.com/docs/text-color
       */
      "text-color": [{
        text: R()
      }],
      /**
       * Text Decoration
       * @see https://tailwindcss.com/docs/text-decoration
       */
      "text-decoration": ["underline", "overline", "line-through", "no-underline"],
      /**
       * Text Decoration Style
       * @see https://tailwindcss.com/docs/text-decoration-style
       */
      "text-decoration-style": [{
        decoration: [...ct(), "wavy"]
      }],
      /**
       * Text Decoration Thickness
       * @see https://tailwindcss.com/docs/text-decoration-thickness
       */
      "text-decoration-thickness": [{
        decoration: [et, "from-font", "auto", Y, ea]
      }],
      /**
       * Text Decoration Color
       * @see https://tailwindcss.com/docs/text-decoration-color
       */
      "text-decoration-color": [{
        decoration: R()
      }],
      /**
       * Text Underline Offset
       * @see https://tailwindcss.com/docs/text-underline-offset
       */
      "underline-offset": [{
        "underline-offset": [et, "auto", Y, Q]
      }],
      /**
       * Text Transform
       * @see https://tailwindcss.com/docs/text-transform
       */
      "text-transform": ["uppercase", "lowercase", "capitalize", "normal-case"],
      /**
       * Text Overflow
       * @see https://tailwindcss.com/docs/text-overflow
       */
      "text-overflow": ["truncate", "text-ellipsis", "text-clip"],
      /**
       * Text Wrap
       * @see https://tailwindcss.com/docs/text-wrap
       */
      "text-wrap": [{
        text: ["wrap", "nowrap", "balance", "pretty"]
      }],
      /**
       * Text Indent
       * @see https://tailwindcss.com/docs/text-indent
       */
      indent: [{
        indent: j()
      }],
      /**
       * Vertical Alignment
       * @see https://tailwindcss.com/docs/vertical-align
       */
      "vertical-align": [{
        align: ["baseline", "top", "middle", "bottom", "text-top", "text-bottom", "sub", "super", Y, Q]
      }],
      /**
       * Whitespace
       * @see https://tailwindcss.com/docs/whitespace
       */
      whitespace: [{
        whitespace: ["normal", "nowrap", "pre", "pre-line", "pre-wrap", "break-spaces"]
      }],
      /**
       * Word Break
       * @see https://tailwindcss.com/docs/word-break
       */
      break: [{
        break: ["normal", "words", "all", "keep"]
      }],
      /**
       * Overflow Wrap
       * @see https://tailwindcss.com/docs/overflow-wrap
       */
      wrap: [{
        wrap: ["break-word", "anywhere", "normal"]
      }],
      /**
       * Hyphens
       * @see https://tailwindcss.com/docs/hyphens
       */
      hyphens: [{
        hyphens: ["none", "manual", "auto"]
      }],
      /**
       * Content
       * @see https://tailwindcss.com/docs/content
       */
      content: [{
        content: ["none", Y, Q]
      }],
      // -------------------
      // --- Backgrounds ---
      // -------------------
      /**
       * Background Attachment
       * @see https://tailwindcss.com/docs/background-attachment
       */
      "bg-attachment": [{
        bg: ["fixed", "local", "scroll"]
      }],
      /**
       * Background Clip
       * @see https://tailwindcss.com/docs/background-clip
       */
      "bg-clip": [{
        "bg-clip": ["border", "padding", "content", "text"]
      }],
      /**
       * Background Origin
       * @see https://tailwindcss.com/docs/background-origin
       */
      "bg-origin": [{
        "bg-origin": ["border", "padding", "content"]
      }],
      /**
       * Background Position
       * @see https://tailwindcss.com/docs/background-position
       */
      "bg-position": [{
        bg: m()
      }],
      /**
       * Background Repeat
       * @see https://tailwindcss.com/docs/background-repeat
       */
      "bg-repeat": [{
        bg: x()
      }],
      /**
       * Background Size
       * @see https://tailwindcss.com/docs/background-size
       */
      "bg-size": [{
        bg: N()
      }],
      /**
       * Background Image
       * @see https://tailwindcss.com/docs/background-image
       */
      "bg-image": [{
        bg: ["none", {
          linear: [{
            to: ["t", "tr", "r", "br", "b", "bl", "l", "tl"]
          }, ql, Y, Q],
          radial: ["", Y, Q],
          conic: [ql, Y, Q]
        }, N0, C0]
      }],
      /**
       * Background Color
       * @see https://tailwindcss.com/docs/background-color
       */
      "bg-color": [{
        bg: R()
      }],
      /**
       * Gradient Color Stops From Position
       * @see https://tailwindcss.com/docs/gradient-color-stops
       */
      "gradient-from-pos": [{
        from: q()
      }],
      /**
       * Gradient Color Stops Via Position
       * @see https://tailwindcss.com/docs/gradient-color-stops
       */
      "gradient-via-pos": [{
        via: q()
      }],
      /**
       * Gradient Color Stops To Position
       * @see https://tailwindcss.com/docs/gradient-color-stops
       */
      "gradient-to-pos": [{
        to: q()
      }],
      /**
       * Gradient Color Stops From
       * @see https://tailwindcss.com/docs/gradient-color-stops
       */
      "gradient-from": [{
        from: R()
      }],
      /**
       * Gradient Color Stops Via
       * @see https://tailwindcss.com/docs/gradient-color-stops
       */
      "gradient-via": [{
        via: R()
      }],
      /**
       * Gradient Color Stops To
       * @see https://tailwindcss.com/docs/gradient-color-stops
       */
      "gradient-to": [{
        to: R()
      }],
      // ---------------
      // --- Borders ---
      // ---------------
      /**
       * Border Radius
       * @see https://tailwindcss.com/docs/border-radius
       */
      rounded: [{
        rounded: w()
      }],
      /**
       * Border Radius Start
       * @see https://tailwindcss.com/docs/border-radius
       */
      "rounded-s": [{
        "rounded-s": w()
      }],
      /**
       * Border Radius End
       * @see https://tailwindcss.com/docs/border-radius
       */
      "rounded-e": [{
        "rounded-e": w()
      }],
      /**
       * Border Radius Top
       * @see https://tailwindcss.com/docs/border-radius
       */
      "rounded-t": [{
        "rounded-t": w()
      }],
      /**
       * Border Radius Right
       * @see https://tailwindcss.com/docs/border-radius
       */
      "rounded-r": [{
        "rounded-r": w()
      }],
      /**
       * Border Radius Bottom
       * @see https://tailwindcss.com/docs/border-radius
       */
      "rounded-b": [{
        "rounded-b": w()
      }],
      /**
       * Border Radius Left
       * @see https://tailwindcss.com/docs/border-radius
       */
      "rounded-l": [{
        "rounded-l": w()
      }],
      /**
       * Border Radius Start Start
       * @see https://tailwindcss.com/docs/border-radius
       */
      "rounded-ss": [{
        "rounded-ss": w()
      }],
      /**
       * Border Radius Start End
       * @see https://tailwindcss.com/docs/border-radius
       */
      "rounded-se": [{
        "rounded-se": w()
      }],
      /**
       * Border Radius End End
       * @see https://tailwindcss.com/docs/border-radius
       */
      "rounded-ee": [{
        "rounded-ee": w()
      }],
      /**
       * Border Radius End Start
       * @see https://tailwindcss.com/docs/border-radius
       */
      "rounded-es": [{
        "rounded-es": w()
      }],
      /**
       * Border Radius Top Left
       * @see https://tailwindcss.com/docs/border-radius
       */
      "rounded-tl": [{
        "rounded-tl": w()
      }],
      /**
       * Border Radius Top Right
       * @see https://tailwindcss.com/docs/border-radius
       */
      "rounded-tr": [{
        "rounded-tr": w()
      }],
      /**
       * Border Radius Bottom Right
       * @see https://tailwindcss.com/docs/border-radius
       */
      "rounded-br": [{
        "rounded-br": w()
      }],
      /**
       * Border Radius Bottom Left
       * @see https://tailwindcss.com/docs/border-radius
       */
      "rounded-bl": [{
        "rounded-bl": w()
      }],
      /**
       * Border Width
       * @see https://tailwindcss.com/docs/border-width
       */
      "border-w": [{
        border: L()
      }],
      /**
       * Border Width Inline
       * @see https://tailwindcss.com/docs/border-width
       */
      "border-w-x": [{
        "border-x": L()
      }],
      /**
       * Border Width Block
       * @see https://tailwindcss.com/docs/border-width
       */
      "border-w-y": [{
        "border-y": L()
      }],
      /**
       * Border Width Inline Start
       * @see https://tailwindcss.com/docs/border-width
       */
      "border-w-s": [{
        "border-s": L()
      }],
      /**
       * Border Width Inline End
       * @see https://tailwindcss.com/docs/border-width
       */
      "border-w-e": [{
        "border-e": L()
      }],
      /**
       * Border Width Block Start
       * @see https://tailwindcss.com/docs/border-width
       */
      "border-w-bs": [{
        "border-bs": L()
      }],
      /**
       * Border Width Block End
       * @see https://tailwindcss.com/docs/border-width
       */
      "border-w-be": [{
        "border-be": L()
      }],
      /**
       * Border Width Top
       * @see https://tailwindcss.com/docs/border-width
       */
      "border-w-t": [{
        "border-t": L()
      }],
      /**
       * Border Width Right
       * @see https://tailwindcss.com/docs/border-width
       */
      "border-w-r": [{
        "border-r": L()
      }],
      /**
       * Border Width Bottom
       * @see https://tailwindcss.com/docs/border-width
       */
      "border-w-b": [{
        "border-b": L()
      }],
      /**
       * Border Width Left
       * @see https://tailwindcss.com/docs/border-width
       */
      "border-w-l": [{
        "border-l": L()
      }],
      /**
       * Divide Width X
       * @see https://tailwindcss.com/docs/border-width#between-children
       */
      "divide-x": [{
        "divide-x": L()
      }],
      /**
       * Divide Width X Reverse
       * @see https://tailwindcss.com/docs/border-width#between-children
       */
      "divide-x-reverse": ["divide-x-reverse"],
      /**
       * Divide Width Y
       * @see https://tailwindcss.com/docs/border-width#between-children
       */
      "divide-y": [{
        "divide-y": L()
      }],
      /**
       * Divide Width Y Reverse
       * @see https://tailwindcss.com/docs/border-width#between-children
       */
      "divide-y-reverse": ["divide-y-reverse"],
      /**
       * Border Style
       * @see https://tailwindcss.com/docs/border-style
       */
      "border-style": [{
        border: [...ct(), "hidden", "none"]
      }],
      /**
       * Divide Style
       * @see https://tailwindcss.com/docs/border-style#setting-the-divider-style
       */
      "divide-style": [{
        divide: [...ct(), "hidden", "none"]
      }],
      /**
       * Border Color
       * @see https://tailwindcss.com/docs/border-color
       */
      "border-color": [{
        border: R()
      }],
      /**
       * Border Color Inline
       * @see https://tailwindcss.com/docs/border-color
       */
      "border-color-x": [{
        "border-x": R()
      }],
      /**
       * Border Color Block
       * @see https://tailwindcss.com/docs/border-color
       */
      "border-color-y": [{
        "border-y": R()
      }],
      /**
       * Border Color Inline Start
       * @see https://tailwindcss.com/docs/border-color
       */
      "border-color-s": [{
        "border-s": R()
      }],
      /**
       * Border Color Inline End
       * @see https://tailwindcss.com/docs/border-color
       */
      "border-color-e": [{
        "border-e": R()
      }],
      /**
       * Border Color Block Start
       * @see https://tailwindcss.com/docs/border-color
       */
      "border-color-bs": [{
        "border-bs": R()
      }],
      /**
       * Border Color Block End
       * @see https://tailwindcss.com/docs/border-color
       */
      "border-color-be": [{
        "border-be": R()
      }],
      /**
       * Border Color Top
       * @see https://tailwindcss.com/docs/border-color
       */
      "border-color-t": [{
        "border-t": R()
      }],
      /**
       * Border Color Right
       * @see https://tailwindcss.com/docs/border-color
       */
      "border-color-r": [{
        "border-r": R()
      }],
      /**
       * Border Color Bottom
       * @see https://tailwindcss.com/docs/border-color
       */
      "border-color-b": [{
        "border-b": R()
      }],
      /**
       * Border Color Left
       * @see https://tailwindcss.com/docs/border-color
       */
      "border-color-l": [{
        "border-l": R()
      }],
      /**
       * Divide Color
       * @see https://tailwindcss.com/docs/divide-color
       */
      "divide-color": [{
        divide: R()
      }],
      /**
       * Outline Style
       * @see https://tailwindcss.com/docs/outline-style
       */
      "outline-style": [{
        outline: [...ct(), "none", "hidden"]
      }],
      /**
       * Outline Offset
       * @see https://tailwindcss.com/docs/outline-offset
       */
      "outline-offset": [{
        "outline-offset": [et, Y, Q]
      }],
      /**
       * Outline Width
       * @see https://tailwindcss.com/docs/outline-width
       */
      "outline-w": [{
        outline: ["", et, Bn, ea]
      }],
      /**
       * Outline Color
       * @see https://tailwindcss.com/docs/outline-color
       */
      "outline-color": [{
        outline: R()
      }],
      // ---------------
      // --- Effects ---
      // ---------------
      /**
       * Box Shadow
       * @see https://tailwindcss.com/docs/box-shadow
       */
      shadow: [{
        shadow: [
          // Deprecated since Tailwind CSS v4.0.0
          "",
          "none",
          G,
          ii,
          ui
        ]
      }],
      /**
       * Box Shadow Color
       * @see https://tailwindcss.com/docs/box-shadow#setting-the-shadow-color
       */
      "shadow-color": [{
        shadow: R()
      }],
      /**
       * Inset Box Shadow
       * @see https://tailwindcss.com/docs/box-shadow#adding-an-inset-shadow
       */
      "inset-shadow": [{
        "inset-shadow": ["none", H, ii, ui]
      }],
      /**
       * Inset Box Shadow Color
       * @see https://tailwindcss.com/docs/box-shadow#setting-the-inset-shadow-color
       */
      "inset-shadow-color": [{
        "inset-shadow": R()
      }],
      /**
       * Ring Width
       * @see https://tailwindcss.com/docs/box-shadow#adding-a-ring
       */
      "ring-w": [{
        ring: L()
      }],
      /**
       * Ring Width Inset
       * @see https://v3.tailwindcss.com/docs/ring-width#inset-rings
       * @deprecated since Tailwind CSS v4.0.0
       * @see https://github.com/tailwindlabs/tailwindcss/blob/v4.0.0/packages/tailwindcss/src/utilities.ts#L4158
       */
      "ring-w-inset": ["ring-inset"],
      /**
       * Ring Color
       * @see https://tailwindcss.com/docs/box-shadow#setting-the-ring-color
       */
      "ring-color": [{
        ring: R()
      }],
      /**
       * Ring Offset Width
       * @see https://v3.tailwindcss.com/docs/ring-offset-width
       * @deprecated since Tailwind CSS v4.0.0
       * @see https://github.com/tailwindlabs/tailwindcss/blob/v4.0.0/packages/tailwindcss/src/utilities.ts#L4158
       */
      "ring-offset-w": [{
        "ring-offset": [et, ea]
      }],
      /**
       * Ring Offset Color
       * @see https://v3.tailwindcss.com/docs/ring-offset-color
       * @deprecated since Tailwind CSS v4.0.0
       * @see https://github.com/tailwindlabs/tailwindcss/blob/v4.0.0/packages/tailwindcss/src/utilities.ts#L4158
       */
      "ring-offset-color": [{
        "ring-offset": R()
      }],
      /**
       * Inset Ring Width
       * @see https://tailwindcss.com/docs/box-shadow#adding-an-inset-ring
       */
      "inset-ring-w": [{
        "inset-ring": L()
      }],
      /**
       * Inset Ring Color
       * @see https://tailwindcss.com/docs/box-shadow#setting-the-inset-ring-color
       */
      "inset-ring-color": [{
        "inset-ring": R()
      }],
      /**
       * Text Shadow
       * @see https://tailwindcss.com/docs/text-shadow
       */
      "text-shadow": [{
        "text-shadow": ["none", J, ii, ui]
      }],
      /**
       * Text Shadow Color
       * @see https://tailwindcss.com/docs/text-shadow#setting-the-shadow-color
       */
      "text-shadow-color": [{
        "text-shadow": R()
      }],
      /**
       * Opacity
       * @see https://tailwindcss.com/docs/opacity
       */
      opacity: [{
        opacity: [et, Y, Q]
      }],
      /**
       * Mix Blend Mode
       * @see https://tailwindcss.com/docs/mix-blend-mode
       */
      "mix-blend": [{
        "mix-blend": [...Lt(), "plus-darker", "plus-lighter"]
      }],
      /**
       * Background Blend Mode
       * @see https://tailwindcss.com/docs/background-blend-mode
       */
      "bg-blend": [{
        "bg-blend": Lt()
      }],
      /**
       * Mask Clip
       * @see https://tailwindcss.com/docs/mask-clip
       */
      "mask-clip": [{
        "mask-clip": ["border", "padding", "content", "fill", "stroke", "view"]
      }, "mask-no-clip"],
      /**
       * Mask Composite
       * @see https://tailwindcss.com/docs/mask-composite
       */
      "mask-composite": [{
        mask: ["add", "subtract", "intersect", "exclude"]
      }],
      /**
       * Mask Image
       * @see https://tailwindcss.com/docs/mask-image
       */
      "mask-image-linear-pos": [{
        "mask-linear": [et]
      }],
      "mask-image-linear-from-pos": [{
        "mask-linear-from": tt()
      }],
      "mask-image-linear-to-pos": [{
        "mask-linear-to": tt()
      }],
      "mask-image-linear-from-color": [{
        "mask-linear-from": R()
      }],
      "mask-image-linear-to-color": [{
        "mask-linear-to": R()
      }],
      "mask-image-t-from-pos": [{
        "mask-t-from": tt()
      }],
      "mask-image-t-to-pos": [{
        "mask-t-to": tt()
      }],
      "mask-image-t-from-color": [{
        "mask-t-from": R()
      }],
      "mask-image-t-to-color": [{
        "mask-t-to": R()
      }],
      "mask-image-r-from-pos": [{
        "mask-r-from": tt()
      }],
      "mask-image-r-to-pos": [{
        "mask-r-to": tt()
      }],
      "mask-image-r-from-color": [{
        "mask-r-from": R()
      }],
      "mask-image-r-to-color": [{
        "mask-r-to": R()
      }],
      "mask-image-b-from-pos": [{
        "mask-b-from": tt()
      }],
      "mask-image-b-to-pos": [{
        "mask-b-to": tt()
      }],
      "mask-image-b-from-color": [{
        "mask-b-from": R()
      }],
      "mask-image-b-to-color": [{
        "mask-b-to": R()
      }],
      "mask-image-l-from-pos": [{
        "mask-l-from": tt()
      }],
      "mask-image-l-to-pos": [{
        "mask-l-to": tt()
      }],
      "mask-image-l-from-color": [{
        "mask-l-from": R()
      }],
      "mask-image-l-to-color": [{
        "mask-l-to": R()
      }],
      "mask-image-x-from-pos": [{
        "mask-x-from": tt()
      }],
      "mask-image-x-to-pos": [{
        "mask-x-to": tt()
      }],
      "mask-image-x-from-color": [{
        "mask-x-from": R()
      }],
      "mask-image-x-to-color": [{
        "mask-x-to": R()
      }],
      "mask-image-y-from-pos": [{
        "mask-y-from": tt()
      }],
      "mask-image-y-to-pos": [{
        "mask-y-to": tt()
      }],
      "mask-image-y-from-color": [{
        "mask-y-from": R()
      }],
      "mask-image-y-to-color": [{
        "mask-y-to": R()
      }],
      "mask-image-radial": [{
        "mask-radial": [Y, Q]
      }],
      "mask-image-radial-from-pos": [{
        "mask-radial-from": tt()
      }],
      "mask-image-radial-to-pos": [{
        "mask-radial-to": tt()
      }],
      "mask-image-radial-from-color": [{
        "mask-radial-from": R()
      }],
      "mask-image-radial-to-color": [{
        "mask-radial-to": R()
      }],
      "mask-image-radial-shape": [{
        "mask-radial": ["circle", "ellipse"]
      }],
      "mask-image-radial-size": [{
        "mask-radial": [{
          closest: ["side", "corner"],
          farthest: ["side", "corner"]
        }]
      }],
      "mask-image-radial-pos": [{
        "mask-radial-at": _t()
      }],
      "mask-image-conic-pos": [{
        "mask-conic": [et]
      }],
      "mask-image-conic-from-pos": [{
        "mask-conic-from": tt()
      }],
      "mask-image-conic-to-pos": [{
        "mask-conic-to": tt()
      }],
      "mask-image-conic-from-color": [{
        "mask-conic-from": R()
      }],
      "mask-image-conic-to-color": [{
        "mask-conic-to": R()
      }],
      /**
       * Mask Mode
       * @see https://tailwindcss.com/docs/mask-mode
       */
      "mask-mode": [{
        mask: ["alpha", "luminance", "match"]
      }],
      /**
       * Mask Origin
       * @see https://tailwindcss.com/docs/mask-origin
       */
      "mask-origin": [{
        "mask-origin": ["border", "padding", "content", "fill", "stroke", "view"]
      }],
      /**
       * Mask Position
       * @see https://tailwindcss.com/docs/mask-position
       */
      "mask-position": [{
        mask: m()
      }],
      /**
       * Mask Repeat
       * @see https://tailwindcss.com/docs/mask-repeat
       */
      "mask-repeat": [{
        mask: x()
      }],
      /**
       * Mask Size
       * @see https://tailwindcss.com/docs/mask-size
       */
      "mask-size": [{
        mask: N()
      }],
      /**
       * Mask Type
       * @see https://tailwindcss.com/docs/mask-type
       */
      "mask-type": [{
        "mask-type": ["alpha", "luminance"]
      }],
      /**
       * Mask Image
       * @see https://tailwindcss.com/docs/mask-image
       */
      "mask-image": [{
        mask: ["none", Y, Q]
      }],
      // ---------------
      // --- Filters ---
      // ---------------
      /**
       * Filter
       * @see https://tailwindcss.com/docs/filter
       */
      filter: [{
        filter: [
          // Deprecated since Tailwind CSS v3.0.0
          "",
          "none",
          Y,
          Q
        ]
      }],
      /**
       * Blur
       * @see https://tailwindcss.com/docs/blur
       */
      blur: [{
        blur: cl()
      }],
      /**
       * Brightness
       * @see https://tailwindcss.com/docs/brightness
       */
      brightness: [{
        brightness: [et, Y, Q]
      }],
      /**
       * Contrast
       * @see https://tailwindcss.com/docs/contrast
       */
      contrast: [{
        contrast: [et, Y, Q]
      }],
      /**
       * Drop Shadow
       * @see https://tailwindcss.com/docs/drop-shadow
       */
      "drop-shadow": [{
        "drop-shadow": [
          // Deprecated since Tailwind CSS v4.0.0
          "",
          "none",
          st,
          ii,
          ui
        ]
      }],
      /**
       * Drop Shadow Color
       * @see https://tailwindcss.com/docs/filter-drop-shadow#setting-the-shadow-color
       */
      "drop-shadow-color": [{
        "drop-shadow": R()
      }],
      /**
       * Grayscale
       * @see https://tailwindcss.com/docs/grayscale
       */
      grayscale: [{
        grayscale: ["", et, Y, Q]
      }],
      /**
       * Hue Rotate
       * @see https://tailwindcss.com/docs/hue-rotate
       */
      "hue-rotate": [{
        "hue-rotate": [et, Y, Q]
      }],
      /**
       * Invert
       * @see https://tailwindcss.com/docs/invert
       */
      invert: [{
        invert: ["", et, Y, Q]
      }],
      /**
       * Saturate
       * @see https://tailwindcss.com/docs/saturate
       */
      saturate: [{
        saturate: [et, Y, Q]
      }],
      /**
       * Sepia
       * @see https://tailwindcss.com/docs/sepia
       */
      sepia: [{
        sepia: ["", et, Y, Q]
      }],
      /**
       * Backdrop Filter
       * @see https://tailwindcss.com/docs/backdrop-filter
       */
      "backdrop-filter": [{
        "backdrop-filter": [
          // Deprecated since Tailwind CSS v3.0.0
          "",
          "none",
          Y,
          Q
        ]
      }],
      /**
       * Backdrop Blur
       * @see https://tailwindcss.com/docs/backdrop-blur
       */
      "backdrop-blur": [{
        "backdrop-blur": cl()
      }],
      /**
       * Backdrop Brightness
       * @see https://tailwindcss.com/docs/backdrop-brightness
       */
      "backdrop-brightness": [{
        "backdrop-brightness": [et, Y, Q]
      }],
      /**
       * Backdrop Contrast
       * @see https://tailwindcss.com/docs/backdrop-contrast
       */
      "backdrop-contrast": [{
        "backdrop-contrast": [et, Y, Q]
      }],
      /**
       * Backdrop Grayscale
       * @see https://tailwindcss.com/docs/backdrop-grayscale
       */
      "backdrop-grayscale": [{
        "backdrop-grayscale": ["", et, Y, Q]
      }],
      /**
       * Backdrop Hue Rotate
       * @see https://tailwindcss.com/docs/backdrop-hue-rotate
       */
      "backdrop-hue-rotate": [{
        "backdrop-hue-rotate": [et, Y, Q]
      }],
      /**
       * Backdrop Invert
       * @see https://tailwindcss.com/docs/backdrop-invert
       */
      "backdrop-invert": [{
        "backdrop-invert": ["", et, Y, Q]
      }],
      /**
       * Backdrop Opacity
       * @see https://tailwindcss.com/docs/backdrop-opacity
       */
      "backdrop-opacity": [{
        "backdrop-opacity": [et, Y, Q]
      }],
      /**
       * Backdrop Saturate
       * @see https://tailwindcss.com/docs/backdrop-saturate
       */
      "backdrop-saturate": [{
        "backdrop-saturate": [et, Y, Q]
      }],
      /**
       * Backdrop Sepia
       * @see https://tailwindcss.com/docs/backdrop-sepia
       */
      "backdrop-sepia": [{
        "backdrop-sepia": ["", et, Y, Q]
      }],
      // --------------
      // --- Tables ---
      // --------------
      /**
       * Border Collapse
       * @see https://tailwindcss.com/docs/border-collapse
       */
      "border-collapse": [{
        border: ["collapse", "separate"]
      }],
      /**
       * Border Spacing
       * @see https://tailwindcss.com/docs/border-spacing
       */
      "border-spacing": [{
        "border-spacing": j()
      }],
      /**
       * Border Spacing X
       * @see https://tailwindcss.com/docs/border-spacing
       */
      "border-spacing-x": [{
        "border-spacing-x": j()
      }],
      /**
       * Border Spacing Y
       * @see https://tailwindcss.com/docs/border-spacing
       */
      "border-spacing-y": [{
        "border-spacing-y": j()
      }],
      /**
       * Table Layout
       * @see https://tailwindcss.com/docs/table-layout
       */
      "table-layout": [{
        table: ["auto", "fixed"]
      }],
      /**
       * Caption Side
       * @see https://tailwindcss.com/docs/caption-side
       */
      caption: [{
        caption: ["top", "bottom"]
      }],
      // ---------------------------------
      // --- Transitions and Animation ---
      // ---------------------------------
      /**
       * Transition Property
       * @see https://tailwindcss.com/docs/transition-property
       */
      transition: [{
        transition: ["", "all", "colors", "opacity", "shadow", "transform", "none", Y, Q]
      }],
      /**
       * Transition Behavior
       * @see https://tailwindcss.com/docs/transition-behavior
       */
      "transition-behavior": [{
        transition: ["normal", "discrete"]
      }],
      /**
       * Transition Duration
       * @see https://tailwindcss.com/docs/transition-duration
       */
      duration: [{
        duration: [et, "initial", Y, Q]
      }],
      /**
       * Transition Timing Function
       * @see https://tailwindcss.com/docs/transition-timing-function
       */
      ease: [{
        ease: ["linear", "initial", ot, Y, Q]
      }],
      /**
       * Transition Delay
       * @see https://tailwindcss.com/docs/transition-delay
       */
      delay: [{
        delay: [et, Y, Q]
      }],
      /**
       * Animation
       * @see https://tailwindcss.com/docs/animation
       */
      animate: [{
        animate: ["none", Nt, Y, Q]
      }],
      // ------------------
      // --- Transforms ---
      // ------------------
      /**
       * Backface Visibility
       * @see https://tailwindcss.com/docs/backface-visibility
       */
      backface: [{
        backface: ["hidden", "visible"]
      }],
      /**
       * Perspective
       * @see https://tailwindcss.com/docs/perspective
       */
      perspective: [{
        perspective: [k, Y, Q]
      }],
      /**
       * Perspective Origin
       * @see https://tailwindcss.com/docs/perspective-origin
       */
      "perspective-origin": [{
        "perspective-origin": Ct()
      }],
      /**
       * Rotate
       * @see https://tailwindcss.com/docs/rotate
       */
      rotate: [{
        rotate: Xe()
      }],
      /**
       * Rotate X
       * @see https://tailwindcss.com/docs/rotate
       */
      "rotate-x": [{
        "rotate-x": Xe()
      }],
      /**
       * Rotate Y
       * @see https://tailwindcss.com/docs/rotate
       */
      "rotate-y": [{
        "rotate-y": Xe()
      }],
      /**
       * Rotate Z
       * @see https://tailwindcss.com/docs/rotate
       */
      "rotate-z": [{
        "rotate-z": Xe()
      }],
      /**
       * Scale
       * @see https://tailwindcss.com/docs/scale
       */
      scale: [{
        scale: fl()
      }],
      /**
       * Scale X
       * @see https://tailwindcss.com/docs/scale
       */
      "scale-x": [{
        "scale-x": fl()
      }],
      /**
       * Scale Y
       * @see https://tailwindcss.com/docs/scale
       */
      "scale-y": [{
        "scale-y": fl()
      }],
      /**
       * Scale Z
       * @see https://tailwindcss.com/docs/scale
       */
      "scale-z": [{
        "scale-z": fl()
      }],
      /**
       * Scale 3D
       * @see https://tailwindcss.com/docs/scale
       */
      "scale-3d": ["scale-3d"],
      /**
       * Skew
       * @see https://tailwindcss.com/docs/skew
       */
      skew: [{
        skew: aa()
      }],
      /**
       * Skew X
       * @see https://tailwindcss.com/docs/skew
       */
      "skew-x": [{
        "skew-x": aa()
      }],
      /**
       * Skew Y
       * @see https://tailwindcss.com/docs/skew
       */
      "skew-y": [{
        "skew-y": aa()
      }],
      /**
       * Transform
       * @see https://tailwindcss.com/docs/transform
       */
      transform: [{
        transform: [Y, Q, "", "none", "gpu", "cpu"]
      }],
      /**
       * Transform Origin
       * @see https://tailwindcss.com/docs/transform-origin
       */
      "transform-origin": [{
        origin: Ct()
      }],
      /**
       * Transform Style
       * @see https://tailwindcss.com/docs/transform-style
       */
      "transform-style": [{
        transform: ["3d", "flat"]
      }],
      /**
       * Translate
       * @see https://tailwindcss.com/docs/translate
       */
      translate: [{
        translate: Se()
      }],
      /**
       * Translate X
       * @see https://tailwindcss.com/docs/translate
       */
      "translate-x": [{
        "translate-x": Se()
      }],
      /**
       * Translate Y
       * @see https://tailwindcss.com/docs/translate
       */
      "translate-y": [{
        "translate-y": Se()
      }],
      /**
       * Translate Z
       * @see https://tailwindcss.com/docs/translate
       */
      "translate-z": [{
        "translate-z": Se()
      }],
      /**
       * Translate None
       * @see https://tailwindcss.com/docs/translate
       */
      "translate-none": ["translate-none"],
      // ---------------------
      // --- Interactivity ---
      // ---------------------
      /**
       * Accent Color
       * @see https://tailwindcss.com/docs/accent-color
       */
      accent: [{
        accent: R()
      }],
      /**
       * Appearance
       * @see https://tailwindcss.com/docs/appearance
       */
      appearance: [{
        appearance: ["none", "auto"]
      }],
      /**
       * Caret Color
       * @see https://tailwindcss.com/docs/just-in-time-mode#caret-color-utilities
       */
      "caret-color": [{
        caret: R()
      }],
      /**
       * Color Scheme
       * @see https://tailwindcss.com/docs/color-scheme
       */
      "color-scheme": [{
        scheme: ["normal", "dark", "light", "light-dark", "only-dark", "only-light"]
      }],
      /**
       * Cursor
       * @see https://tailwindcss.com/docs/cursor
       */
      cursor: [{
        cursor: ["auto", "default", "pointer", "wait", "text", "move", "help", "not-allowed", "none", "context-menu", "progress", "cell", "crosshair", "vertical-text", "alias", "copy", "no-drop", "grab", "grabbing", "all-scroll", "col-resize", "row-resize", "n-resize", "e-resize", "s-resize", "w-resize", "ne-resize", "nw-resize", "se-resize", "sw-resize", "ew-resize", "ns-resize", "nesw-resize", "nwse-resize", "zoom-in", "zoom-out", Y, Q]
      }],
      /**
       * Field Sizing
       * @see https://tailwindcss.com/docs/field-sizing
       */
      "field-sizing": [{
        "field-sizing": ["fixed", "content"]
      }],
      /**
       * Pointer Events
       * @see https://tailwindcss.com/docs/pointer-events
       */
      "pointer-events": [{
        "pointer-events": ["auto", "none"]
      }],
      /**
       * Resize
       * @see https://tailwindcss.com/docs/resize
       */
      resize: [{
        resize: ["none", "", "y", "x"]
      }],
      /**
       * Scroll Behavior
       * @see https://tailwindcss.com/docs/scroll-behavior
       */
      "scroll-behavior": [{
        scroll: ["auto", "smooth"]
      }],
      /**
       * Scroll Margin
       * @see https://tailwindcss.com/docs/scroll-margin
       */
      "scroll-m": [{
        "scroll-m": j()
      }],
      /**
       * Scroll Margin Inline
       * @see https://tailwindcss.com/docs/scroll-margin
       */
      "scroll-mx": [{
        "scroll-mx": j()
      }],
      /**
       * Scroll Margin Block
       * @see https://tailwindcss.com/docs/scroll-margin
       */
      "scroll-my": [{
        "scroll-my": j()
      }],
      /**
       * Scroll Margin Inline Start
       * @see https://tailwindcss.com/docs/scroll-margin
       */
      "scroll-ms": [{
        "scroll-ms": j()
      }],
      /**
       * Scroll Margin Inline End
       * @see https://tailwindcss.com/docs/scroll-margin
       */
      "scroll-me": [{
        "scroll-me": j()
      }],
      /**
       * Scroll Margin Block Start
       * @see https://tailwindcss.com/docs/scroll-margin
       */
      "scroll-mbs": [{
        "scroll-mbs": j()
      }],
      /**
       * Scroll Margin Block End
       * @see https://tailwindcss.com/docs/scroll-margin
       */
      "scroll-mbe": [{
        "scroll-mbe": j()
      }],
      /**
       * Scroll Margin Top
       * @see https://tailwindcss.com/docs/scroll-margin
       */
      "scroll-mt": [{
        "scroll-mt": j()
      }],
      /**
       * Scroll Margin Right
       * @see https://tailwindcss.com/docs/scroll-margin
       */
      "scroll-mr": [{
        "scroll-mr": j()
      }],
      /**
       * Scroll Margin Bottom
       * @see https://tailwindcss.com/docs/scroll-margin
       */
      "scroll-mb": [{
        "scroll-mb": j()
      }],
      /**
       * Scroll Margin Left
       * @see https://tailwindcss.com/docs/scroll-margin
       */
      "scroll-ml": [{
        "scroll-ml": j()
      }],
      /**
       * Scroll Padding
       * @see https://tailwindcss.com/docs/scroll-padding
       */
      "scroll-p": [{
        "scroll-p": j()
      }],
      /**
       * Scroll Padding Inline
       * @see https://tailwindcss.com/docs/scroll-padding
       */
      "scroll-px": [{
        "scroll-px": j()
      }],
      /**
       * Scroll Padding Block
       * @see https://tailwindcss.com/docs/scroll-padding
       */
      "scroll-py": [{
        "scroll-py": j()
      }],
      /**
       * Scroll Padding Inline Start
       * @see https://tailwindcss.com/docs/scroll-padding
       */
      "scroll-ps": [{
        "scroll-ps": j()
      }],
      /**
       * Scroll Padding Inline End
       * @see https://tailwindcss.com/docs/scroll-padding
       */
      "scroll-pe": [{
        "scroll-pe": j()
      }],
      /**
       * Scroll Padding Block Start
       * @see https://tailwindcss.com/docs/scroll-padding
       */
      "scroll-pbs": [{
        "scroll-pbs": j()
      }],
      /**
       * Scroll Padding Block End
       * @see https://tailwindcss.com/docs/scroll-padding
       */
      "scroll-pbe": [{
        "scroll-pbe": j()
      }],
      /**
       * Scroll Padding Top
       * @see https://tailwindcss.com/docs/scroll-padding
       */
      "scroll-pt": [{
        "scroll-pt": j()
      }],
      /**
       * Scroll Padding Right
       * @see https://tailwindcss.com/docs/scroll-padding
       */
      "scroll-pr": [{
        "scroll-pr": j()
      }],
      /**
       * Scroll Padding Bottom
       * @see https://tailwindcss.com/docs/scroll-padding
       */
      "scroll-pb": [{
        "scroll-pb": j()
      }],
      /**
       * Scroll Padding Left
       * @see https://tailwindcss.com/docs/scroll-padding
       */
      "scroll-pl": [{
        "scroll-pl": j()
      }],
      /**
       * Scroll Snap Align
       * @see https://tailwindcss.com/docs/scroll-snap-align
       */
      "snap-align": [{
        snap: ["start", "end", "center", "align-none"]
      }],
      /**
       * Scroll Snap Stop
       * @see https://tailwindcss.com/docs/scroll-snap-stop
       */
      "snap-stop": [{
        snap: ["normal", "always"]
      }],
      /**
       * Scroll Snap Type
       * @see https://tailwindcss.com/docs/scroll-snap-type
       */
      "snap-type": [{
        snap: ["none", "x", "y", "both"]
      }],
      /**
       * Scroll Snap Type Strictness
       * @see https://tailwindcss.com/docs/scroll-snap-type
       */
      "snap-strictness": [{
        snap: ["mandatory", "proximity"]
      }],
      /**
       * Touch Action
       * @see https://tailwindcss.com/docs/touch-action
       */
      touch: [{
        touch: ["auto", "none", "manipulation"]
      }],
      /**
       * Touch Action X
       * @see https://tailwindcss.com/docs/touch-action
       */
      "touch-x": [{
        "touch-pan": ["x", "left", "right"]
      }],
      /**
       * Touch Action Y
       * @see https://tailwindcss.com/docs/touch-action
       */
      "touch-y": [{
        "touch-pan": ["y", "up", "down"]
      }],
      /**
       * Touch Action Pinch Zoom
       * @see https://tailwindcss.com/docs/touch-action
       */
      "touch-pz": ["touch-pinch-zoom"],
      /**
       * User Select
       * @see https://tailwindcss.com/docs/user-select
       */
      select: [{
        select: ["none", "text", "all", "auto"]
      }],
      /**
       * Will Change
       * @see https://tailwindcss.com/docs/will-change
       */
      "will-change": [{
        "will-change": ["auto", "scroll", "contents", "transform", Y, Q]
      }],
      // -----------
      // --- SVG ---
      // -----------
      /**
       * Fill
       * @see https://tailwindcss.com/docs/fill
       */
      fill: [{
        fill: ["none", ...R()]
      }],
      /**
       * Stroke Width
       * @see https://tailwindcss.com/docs/stroke-width
       */
      "stroke-w": [{
        stroke: [et, Bn, ea, mh]
      }],
      /**
       * Stroke
       * @see https://tailwindcss.com/docs/stroke
       */
      stroke: [{
        stroke: ["none", ...R()]
      }],
      // ---------------------
      // --- Accessibility ---
      // ---------------------
      /**
       * Forced Color Adjust
       * @see https://tailwindcss.com/docs/forced-color-adjust
       */
      "forced-color-adjust": [{
        "forced-color-adjust": ["auto", "none"]
      }]
    },
    conflictingClassGroups: {
      overflow: ["overflow-x", "overflow-y"],
      overscroll: ["overscroll-x", "overscroll-y"],
      inset: ["inset-x", "inset-y", "inset-bs", "inset-be", "start", "end", "top", "right", "bottom", "left"],
      "inset-x": ["right", "left"],
      "inset-y": ["top", "bottom"],
      flex: ["basis", "grow", "shrink"],
      gap: ["gap-x", "gap-y"],
      p: ["px", "py", "ps", "pe", "pbs", "pbe", "pt", "pr", "pb", "pl"],
      px: ["pr", "pl"],
      py: ["pt", "pb"],
      m: ["mx", "my", "ms", "me", "mbs", "mbe", "mt", "mr", "mb", "ml"],
      mx: ["mr", "ml"],
      my: ["mt", "mb"],
      size: ["w", "h"],
      "font-size": ["leading"],
      "fvn-normal": ["fvn-ordinal", "fvn-slashed-zero", "fvn-figure", "fvn-spacing", "fvn-fraction"],
      "fvn-ordinal": ["fvn-normal"],
      "fvn-slashed-zero": ["fvn-normal"],
      "fvn-figure": ["fvn-normal"],
      "fvn-spacing": ["fvn-normal"],
      "fvn-fraction": ["fvn-normal"],
      "line-clamp": ["display", "overflow"],
      rounded: ["rounded-s", "rounded-e", "rounded-t", "rounded-r", "rounded-b", "rounded-l", "rounded-ss", "rounded-se", "rounded-ee", "rounded-es", "rounded-tl", "rounded-tr", "rounded-br", "rounded-bl"],
      "rounded-s": ["rounded-ss", "rounded-es"],
      "rounded-e": ["rounded-se", "rounded-ee"],
      "rounded-t": ["rounded-tl", "rounded-tr"],
      "rounded-r": ["rounded-tr", "rounded-br"],
      "rounded-b": ["rounded-br", "rounded-bl"],
      "rounded-l": ["rounded-tl", "rounded-bl"],
      "border-spacing": ["border-spacing-x", "border-spacing-y"],
      "border-w": ["border-w-x", "border-w-y", "border-w-s", "border-w-e", "border-w-bs", "border-w-be", "border-w-t", "border-w-r", "border-w-b", "border-w-l"],
      "border-w-x": ["border-w-r", "border-w-l"],
      "border-w-y": ["border-w-t", "border-w-b"],
      "border-color": ["border-color-x", "border-color-y", "border-color-s", "border-color-e", "border-color-bs", "border-color-be", "border-color-t", "border-color-r", "border-color-b", "border-color-l"],
      "border-color-x": ["border-color-r", "border-color-l"],
      "border-color-y": ["border-color-t", "border-color-b"],
      translate: ["translate-x", "translate-y", "translate-none"],
      "translate-none": ["translate", "translate-x", "translate-y", "translate-z"],
      "scroll-m": ["scroll-mx", "scroll-my", "scroll-ms", "scroll-me", "scroll-mbs", "scroll-mbe", "scroll-mt", "scroll-mr", "scroll-mb", "scroll-ml"],
      "scroll-mx": ["scroll-mr", "scroll-ml"],
      "scroll-my": ["scroll-mt", "scroll-mb"],
      "scroll-p": ["scroll-px", "scroll-py", "scroll-ps", "scroll-pe", "scroll-pbs", "scroll-pbe", "scroll-pt", "scroll-pr", "scroll-pb", "scroll-pl"],
      "scroll-px": ["scroll-pr", "scroll-pl"],
      "scroll-py": ["scroll-pt", "scroll-pb"],
      touch: ["touch-x", "touch-y", "touch-pz"],
      "touch-x": ["touch"],
      "touch-y": ["touch"],
      "touch-pz": ["touch"]
    },
    conflictingClassGroupModifiers: {
      "font-size": ["leading"]
    },
    orderSensitiveModifiers: ["*", "**", "after", "backdrop", "before", "details-content", "file", "first-letter", "first-line", "marker", "placeholder", "selection"]
  };
}, B0 = /* @__PURE__ */ y0(j0);
function gh(...i) {
  return B0(kv(i));
}
function Q0() {
  return /* @__PURE__ */ Tt.jsxs("div", { className: "glass-card rounded-xl p-6 border border-white/5 animate-pulse", children: [
    /* @__PURE__ */ Tt.jsxs("div", { className: "flex items-center gap-3 mb-4", children: [
      /* @__PURE__ */ Tt.jsx("div", { className: "w-10 h-10 rounded-lg bg-slate-700/50" }),
      /* @__PURE__ */ Tt.jsx("div", { className: "h-4 w-24 rounded bg-slate-700/50" })
    ] }),
    /* @__PURE__ */ Tt.jsx("div", { className: "h-10 w-32 rounded bg-slate-700/50 mb-3" }),
    /* @__PURE__ */ Tt.jsx("div", { className: "h-3 w-20 rounded bg-slate-700/50" }),
    /* @__PURE__ */ Tt.jsxs("div", { className: "mt-4 pt-4 border-t border-white/5 flex justify-between", children: [
      /* @__PURE__ */ Tt.jsx("div", { className: "h-4 w-28 rounded bg-slate-700/50" }),
      /* @__PURE__ */ Tt.jsx("div", { className: "h-4 w-16 rounded bg-slate-700/50" })
    ] })
  ] });
}
function G0({ variant: i = "card", count: f = 1, className: r }) {
  const o = Array.from({ length: f }, (p, O) => O);
  return i === "card" ? /* @__PURE__ */ Tt.jsx("div", { className: gh("grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4 gap-4", r), children: o.map((p) => /* @__PURE__ */ Tt.jsx(Q0, {}, p)) }) : /* @__PURE__ */ Tt.jsx("div", { className: gh("space-y-3", r), children: o.map((p) => /* @__PURE__ */ Tt.jsx("div", { className: "h-4 rounded bg-slate-700/50 animate-pulse", style: { width: `${60 + Math.random() * 30}%` } }, p)) });
}
const Y0 = new Vv({
  defaultOptions: { queries: { staleTime: 3e4, retry: 1 } }
}), X0 = {
  home: At.lazy(() => import("./Home-Ad_hkBEk.js")),
  records: At.lazy(() => import("./Records-ncBqfo4o.js")),
  leaderboards: At.lazy(() => import("./Leaderboards-gufM0274.js")),
  maps: At.lazy(() => import("./Maps-_Avwrax1.js")),
  "hall-of-fame": At.lazy(() => import("./HallOfFame-CkotlByT.js")),
  awards: At.lazy(() => import("./Awards-FcoL1eoU.js")),
  sessions2: At.lazy(() => import("./Sessions2-7pdJdRnD.js")),
  profile: At.lazy(() => import("./Profile-B4IoJMsq.js")),
  weapons: At.lazy(() => import("./Weapons-DVnxlwJ2.js")),
  "retro-viz": At.lazy(() => import("./RetroViz-Tjtwmpem.js")),
  "session-detail": At.lazy(() => import("./SessionDetail-Bsh9n6QK.js")),
  uploads: At.lazy(() => import("./Uploads-BN1UpKBT.js")),
  "upload-detail": At.lazy(() => import("./UploadDetail-BgIDCIFw.js")),
  greatshot: At.lazy(() => import("./Greatshot-BTQZ6Aoi.js")),
  "greatshot-demo": At.lazy(() => import("./GreatshotDemo-DwJc4UYl.js")),
  availability: At.lazy(() => import("./Availability-BtQErZNh.js")),
  admin: At.lazy(() => import("./Admin-DxKXMAz7.js")),
  proximity: At.lazy(() => import("./Proximity-BZpxT02q.js")),
  "proximity-player": At.lazy(() => import("./ProximityPlayer-DZer7H30.js")),
  "proximity-replay": At.lazy(() => import("./ProximityReplay-MwE3YS7d.js")),
  "proximity-teams": At.lazy(() => import("./ProximityTeams-BHP3OLs-.js"))
}, Qn = /* @__PURE__ */ new WeakMap();
function w0({ viewId: i, params: f }) {
  const r = X0[i];
  return r ? /* @__PURE__ */ Tt.jsx(Jv, { viewId: i, children: /* @__PURE__ */ Tt.jsx(Kv, { client: Y0, children: /* @__PURE__ */ Tt.jsx(At.Suspense, { fallback: /* @__PURE__ */ Tt.jsx(G0, { variant: "card", count: 4 }), children: /* @__PURE__ */ Tt.jsx(r, { params: f }) }) }) }) : /* @__PURE__ */ Tt.jsx("div", { className: "text-slate-400 text-center py-12", children: "Not yet migrated." });
}
async function K0(i, f) {
  const r = Qn.get(i);
  r && (r.unmount(), Qn.delete(i));
  const o = bv.createRoot(i);
  return o.render(/* @__PURE__ */ Tt.jsx(w0, { viewId: f.viewId, params: f.params })), Qn.set(i, o), {
    unmount() {
      const p = Qn.get(i);
      p && (p.unmount(), Qn.delete(i));
    }
  };
}
export {
  G0 as S,
  si as a,
  Ov as b,
  gh as c,
  Bf as d,
  Av as e,
  jf as f,
  Sh as g,
  Gv as h,
  oi as i,
  Tt as j,
  Dv as k,
  te as l,
  L0 as m,
  He as n,
  K0 as o,
  Nv as p,
  At as r,
  Z0 as s,
  Ev as t,
  V0 as u
};
