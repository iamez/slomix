import { jsx as x, jsxs as $ } from "react/jsx-runtime";
import { createRoot as gt } from "react-dom/client";
import * as xe from "react";
import { Component as yt, lazy as O, Suspense as vt } from "react";
var le = class {
  constructor() {
    this.listeners = /* @__PURE__ */ new Set(), this.subscribe = this.subscribe.bind(this);
  }
  subscribe(e) {
    return this.listeners.add(e), this.onSubscribe(), () => {
      this.listeners.delete(e), this.onUnsubscribe();
    };
  }
  hasListeners() {
    return this.listeners.size > 0;
  }
  onSubscribe() {
  }
  onUnsubscribe() {
  }
}, wt = {
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
  setTimeout: (e, t) => setTimeout(e, t),
  clearTimeout: (e) => clearTimeout(e),
  setInterval: (e, t) => setInterval(e, t),
  clearInterval: (e) => clearInterval(e)
}, xt = class {
  // We cannot have TimeoutManager<T> as we must instantiate it with a concrete
  // type at app boot; and if we leave that type, then any new timer provider
  // would need to support ReturnType<typeof setTimeout>, which is infeasible.
  //
  // We settle for type safety for the TimeoutProvider type, and accept that
  // this class is unsafe internally to allow for extension.
  #e = wt;
  #r = !1;
  setTimeoutProvider(e) {
    this.#e = e;
  }
  setTimeout(e, t) {
    return this.#e.setTimeout(e, t);
  }
  clearTimeout(e) {
    this.#e.clearTimeout(e);
  }
  setInterval(e, t) {
    return this.#e.setInterval(e, t);
  }
  clearInterval(e) {
    this.#e.clearInterval(e);
  }
}, be = new xt();
function kt(e) {
  setTimeout(e, 0);
}
var ce = typeof window > "u" || "Deno" in globalThis;
function q() {
}
function Ct(e, t) {
  return typeof e == "function" ? e(t) : e;
}
function St(e) {
  return typeof e == "number" && e >= 0 && e !== 1 / 0;
}
function Pt(e, t) {
  return Math.max(e + (t || 0) - Date.now(), 0);
}
function ge(e, t) {
  return typeof e == "function" ? e(t) : e;
}
function Ot(e, t) {
  return typeof e == "function" ? e(t) : e;
}
function Ee(e, t) {
  const {
    type: r = "all",
    exact: s,
    fetchStatus: o,
    predicate: n,
    queryKey: a,
    stale: i
  } = e;
  if (a) {
    if (s) {
      if (t.queryHash !== ke(a, t.options))
        return !1;
    } else if (!J(t.queryKey, a))
      return !1;
  }
  if (r !== "all") {
    const l = t.isActive();
    if (r === "active" && !l || r === "inactive" && l)
      return !1;
  }
  return !(typeof i == "boolean" && t.isStale() !== i || o && o !== t.state.fetchStatus || n && !n(t));
}
function je(e, t) {
  const { exact: r, status: s, predicate: o, mutationKey: n } = e;
  if (n) {
    if (!t.options.mutationKey)
      return !1;
    if (r) {
      if (Y(t.options.mutationKey) !== Y(n))
        return !1;
    } else if (!J(t.options.mutationKey, n))
      return !1;
  }
  return !(s && t.state.status !== s || o && !o(t));
}
function ke(e, t) {
  return (t?.queryKeyHashFn || Y)(e);
}
function Y(e) {
  return JSON.stringify(
    e,
    (t, r) => ye(r) ? Object.keys(r).sort().reduce((s, o) => (s[o] = r[o], s), {}) : r
  );
}
function J(e, t) {
  return e === t ? !0 : typeof e != typeof t ? !1 : e && t && typeof e == "object" && typeof t == "object" ? Object.keys(t).every((r) => J(e[r], t[r])) : !1;
}
var At = Object.prototype.hasOwnProperty;
function $e(e, t, r = 0) {
  if (e === t)
    return e;
  if (r > 500) return t;
  const s = qe(e) && qe(t);
  if (!s && !(ye(e) && ye(t))) return t;
  const n = (s ? e : Object.keys(e)).length, a = s ? t : Object.keys(t), i = a.length, l = s ? new Array(i) : {};
  let f = 0;
  for (let p = 0; p < i; p++) {
    const w = s ? p : a[p], v = e[w], k = t[w];
    if (v === k) {
      l[w] = v, (s ? p < n : At.call(e, w)) && f++;
      continue;
    }
    if (v === null || k === null || typeof v != "object" || typeof k != "object") {
      l[w] = k;
      continue;
    }
    const g = $e(v, k, r + 1);
    l[w] = g, g === v && f++;
  }
  return n === i && f === n ? e : l;
}
function _r(e, t) {
  if (!t || Object.keys(e).length !== Object.keys(t).length)
    return !1;
  for (const r in e)
    if (e[r] !== t[r])
      return !1;
  return !0;
}
function qe(e) {
  return Array.isArray(e) && e.length === Object.keys(e).length;
}
function ye(e) {
  if (!De(e))
    return !1;
  const t = e.constructor;
  if (t === void 0)
    return !0;
  const r = t.prototype;
  return !(!De(r) || !r.hasOwnProperty("isPrototypeOf") || Object.getPrototypeOf(e) !== Object.prototype);
}
function De(e) {
  return Object.prototype.toString.call(e) === "[object Object]";
}
function Ft(e) {
  return new Promise((t) => {
    be.setTimeout(t, e);
  });
}
function Mt(e, t, r) {
  return typeof r.structuralSharing == "function" ? r.structuralSharing(e, t) : r.structuralSharing !== !1 ? $e(e, t) : t;
}
function Rt(e, t, r = 0) {
  const s = [...e, t];
  return r && s.length > r ? s.slice(1) : s;
}
function Tt(e, t, r = 0) {
  const s = [t, ...e];
  return r && s.length > r ? s.slice(0, -1) : s;
}
var Ce = /* @__PURE__ */ Symbol();
function Ye(e, t) {
  return !e.queryFn && t?.initialPromise ? () => t.initialPromise : !e.queryFn || e.queryFn === Ce ? () => Promise.reject(new Error(`Missing queryFn: '${e.queryHash}'`)) : e.queryFn;
}
function Hr(e, t) {
  return typeof e == "function" ? e(...t) : !!e;
}
function zt(e, t, r) {
  let s = !1, o;
  return Object.defineProperty(e, "signal", {
    enumerable: !0,
    get: () => (o ??= t(), s || (s = !0, o.aborted ? r() : o.addEventListener("abort", r, { once: !0 })), o)
  }), e;
}
var It = class extends le {
  #e;
  #r;
  #t;
  constructor() {
    super(), this.#t = (e) => {
      if (!ce && window.addEventListener) {
        const t = () => e();
        return window.addEventListener("visibilitychange", t, !1), () => {
          window.removeEventListener("visibilitychange", t);
        };
      }
    };
  }
  onSubscribe() {
    this.#r || this.setEventListener(this.#t);
  }
  onUnsubscribe() {
    this.hasListeners() || (this.#r?.(), this.#r = void 0);
  }
  setEventListener(e) {
    this.#t = e, this.#r?.(), this.#r = e((t) => {
      typeof t == "boolean" ? this.setFocused(t) : this.onFocus();
    });
  }
  setFocused(e) {
    this.#e !== e && (this.#e = e, this.onFocus());
  }
  onFocus() {
    const e = this.isFocused();
    this.listeners.forEach((t) => {
      t(e);
    });
  }
  isFocused() {
    return typeof this.#e == "boolean" ? this.#e : globalThis.document?.visibilityState !== "hidden";
  }
}, Je = new It();
function Et() {
  let e, t;
  const r = new Promise((o, n) => {
    e = o, t = n;
  });
  r.status = "pending", r.catch(() => {
  });
  function s(o) {
    Object.assign(r, o), delete r.resolve, delete r.reject;
  }
  return r.resolve = (o) => {
    s({
      status: "fulfilled",
      value: o
    }), e(o);
  }, r.reject = (o) => {
    s({
      status: "rejected",
      reason: o
    }), t(o);
  }, r;
}
var jt = kt;
function qt() {
  let e = [], t = 0, r = (i) => {
    i();
  }, s = (i) => {
    i();
  }, o = jt;
  const n = (i) => {
    t ? e.push(i) : o(() => {
      r(i);
    });
  }, a = () => {
    const i = e;
    e = [], i.length && o(() => {
      s(() => {
        i.forEach((l) => {
          r(l);
        });
      });
    });
  };
  return {
    batch: (i) => {
      let l;
      t++;
      try {
        l = i();
      } finally {
        t--, t || a();
      }
      return l;
    },
    /**
     * All calls to the wrapped function will be batched.
     */
    batchCalls: (i) => (...l) => {
      n(() => {
        i(...l);
      });
    },
    schedule: n,
    /**
     * Use this method to set a custom notify function.
     * This can be used to for example wrap notifications with `React.act` while running tests.
     */
    setNotifyFunction: (i) => {
      r = i;
    },
    /**
     * Use this method to set a custom function to batch notifications together into a single tick.
     * By default React Query will use the batch function provided by ReactDOM or React Native.
     */
    setBatchNotifyFunction: (i) => {
      s = i;
    },
    setScheduler: (i) => {
      o = i;
    }
  };
}
var M = qt(), Dt = class extends le {
  #e = !0;
  #r;
  #t;
  constructor() {
    super(), this.#t = (e) => {
      if (!ce && window.addEventListener) {
        const t = () => e(!0), r = () => e(!1);
        return window.addEventListener("online", t, !1), window.addEventListener("offline", r, !1), () => {
          window.removeEventListener("online", t), window.removeEventListener("offline", r);
        };
      }
    };
  }
  onSubscribe() {
    this.#r || this.setEventListener(this.#t);
  }
  onUnsubscribe() {
    this.hasListeners() || (this.#r?.(), this.#r = void 0);
  }
  setEventListener(e) {
    this.#t = e, this.#r?.(), this.#r = e(this.setOnline.bind(this));
  }
  setOnline(e) {
    this.#e !== e && (this.#e = e, this.listeners.forEach((r) => {
      r(e);
    }));
  }
  isOnline() {
    return this.#e;
  }
}, ie = new Dt();
function Qt(e) {
  return Math.min(1e3 * 2 ** e, 3e4);
}
function Xe(e) {
  return (e ?? "online") === "online" ? ie.isOnline() : !0;
}
var ve = class extends Error {
  constructor(e) {
    super("CancelledError"), this.revert = e?.revert, this.silent = e?.silent;
  }
};
function Ze(e) {
  let t = !1, r = 0, s;
  const o = Et(), n = () => o.status !== "pending", a = (b) => {
    if (!n()) {
      const y = new ve(b);
      v(y), e.onCancel?.(y);
    }
  }, i = () => {
    t = !0;
  }, l = () => {
    t = !1;
  }, f = () => Je.isFocused() && (e.networkMode === "always" || ie.isOnline()) && e.canRun(), p = () => Xe(e.networkMode) && e.canRun(), w = (b) => {
    n() || (s?.(), o.resolve(b));
  }, v = (b) => {
    n() || (s?.(), o.reject(b));
  }, k = () => new Promise((b) => {
    s = (y) => {
      (n() || f()) && b(y);
    }, e.onPause?.();
  }).then(() => {
    s = void 0, n() || e.onContinue?.();
  }), g = () => {
    if (n())
      return;
    let b;
    const y = r === 0 ? e.initialPromise : void 0;
    try {
      b = y ?? e.fn();
    } catch (S) {
      b = Promise.reject(S);
    }
    Promise.resolve(b).then(w).catch((S) => {
      if (n())
        return;
      const T = e.retry ?? (ce ? 0 : 3), z = e.retryDelay ?? Qt, I = typeof z == "function" ? z(r, S) : z, E = T === !0 || typeof T == "number" && r < T || typeof T == "function" && T(r, S);
      if (t || !E) {
        v(S);
        return;
      }
      r++, e.onFail?.(r, S), Ft(I).then(() => f() ? void 0 : k()).then(() => {
        t ? v(S) : g();
      });
    });
  };
  return {
    promise: o,
    status: () => o.status,
    cancel: a,
    continue: () => (s?.(), o),
    cancelRetry: i,
    continueRetry: l,
    canStart: p,
    start: () => (p() ? g() : k().then(g), o)
  };
}
var et = class {
  #e;
  destroy() {
    this.clearGcTimeout();
  }
  scheduleGc() {
    this.clearGcTimeout(), St(this.gcTime) && (this.#e = be.setTimeout(() => {
      this.optionalRemove();
    }, this.gcTime));
  }
  updateGcTime(e) {
    this.gcTime = Math.max(
      this.gcTime || 0,
      e ?? (ce ? 1 / 0 : 300 * 1e3)
    );
  }
  clearGcTimeout() {
    this.#e && (be.clearTimeout(this.#e), this.#e = void 0);
  }
}, Nt = class extends et {
  #e;
  #r;
  #t;
  #o;
  #s;
  #i;
  #a;
  constructor(e) {
    super(), this.#a = !1, this.#i = e.defaultOptions, this.setOptions(e.options), this.observers = [], this.#o = e.client, this.#t = this.#o.getQueryCache(), this.queryKey = e.queryKey, this.queryHash = e.queryHash, this.#e = Ne(this.options), this.state = e.state ?? this.#e, this.scheduleGc();
  }
  get meta() {
    return this.options.meta;
  }
  get promise() {
    return this.#s?.promise;
  }
  setOptions(e) {
    if (this.options = { ...this.#i, ...e }, this.updateGcTime(this.options.gcTime), this.state && this.state.data === void 0) {
      const t = Ne(this.options);
      t.data !== void 0 && (this.setState(
        Qe(t.data, t.dataUpdatedAt)
      ), this.#e = t);
    }
  }
  optionalRemove() {
    !this.observers.length && this.state.fetchStatus === "idle" && this.#t.remove(this);
  }
  setData(e, t) {
    const r = Mt(this.state.data, e, this.options);
    return this.#n({
      data: r,
      type: "success",
      dataUpdatedAt: t?.updatedAt,
      manual: t?.manual
    }), r;
  }
  setState(e, t) {
    this.#n({ type: "setState", state: e, setStateOptions: t });
  }
  cancel(e) {
    const t = this.#s?.promise;
    return this.#s?.cancel(e), t ? t.then(q).catch(q) : Promise.resolve();
  }
  destroy() {
    super.destroy(), this.cancel({ silent: !0 });
  }
  reset() {
    this.destroy(), this.setState(this.#e);
  }
  isActive() {
    return this.observers.some(
      (e) => Ot(e.options.enabled, this) !== !1
    );
  }
  isDisabled() {
    return this.getObserversCount() > 0 ? !this.isActive() : this.options.queryFn === Ce || this.state.dataUpdateCount + this.state.errorUpdateCount === 0;
  }
  isStatic() {
    return this.getObserversCount() > 0 ? this.observers.some(
      (e) => ge(e.options.staleTime, this) === "static"
    ) : !1;
  }
  isStale() {
    return this.getObserversCount() > 0 ? this.observers.some(
      (e) => e.getCurrentResult().isStale
    ) : this.state.data === void 0 || this.state.isInvalidated;
  }
  isStaleByTime(e = 0) {
    return this.state.data === void 0 ? !0 : e === "static" ? !1 : this.state.isInvalidated ? !0 : !Pt(this.state.dataUpdatedAt, e);
  }
  onFocus() {
    this.observers.find((t) => t.shouldFetchOnWindowFocus())?.refetch({ cancelRefetch: !1 }), this.#s?.continue();
  }
  onOnline() {
    this.observers.find((t) => t.shouldFetchOnReconnect())?.refetch({ cancelRefetch: !1 }), this.#s?.continue();
  }
  addObserver(e) {
    this.observers.includes(e) || (this.observers.push(e), this.clearGcTimeout(), this.#t.notify({ type: "observerAdded", query: this, observer: e }));
  }
  removeObserver(e) {
    this.observers.includes(e) && (this.observers = this.observers.filter((t) => t !== e), this.observers.length || (this.#s && (this.#a ? this.#s.cancel({ revert: !0 }) : this.#s.cancelRetry()), this.scheduleGc()), this.#t.notify({ type: "observerRemoved", query: this, observer: e }));
  }
  getObserversCount() {
    return this.observers.length;
  }
  invalidate() {
    this.state.isInvalidated || this.#n({ type: "invalidate" });
  }
  async fetch(e, t) {
    if (this.state.fetchStatus !== "idle" && // If the promise in the retryer is already rejected, we have to definitely
    // re-start the fetch; there is a chance that the query is still in a
    // pending state when that happens
    this.#s?.status() !== "rejected") {
      if (this.state.data !== void 0 && t?.cancelRefetch)
        this.cancel({ silent: !0 });
      else if (this.#s)
        return this.#s.continueRetry(), this.#s.promise;
    }
    if (e && this.setOptions(e), !this.options.queryFn) {
      const i = this.observers.find((l) => l.options.queryFn);
      i && this.setOptions(i.options);
    }
    const r = new AbortController(), s = (i) => {
      Object.defineProperty(i, "signal", {
        enumerable: !0,
        get: () => (this.#a = !0, r.signal)
      });
    }, o = () => {
      const i = Ye(this.options, t), f = (() => {
        const p = {
          client: this.#o,
          queryKey: this.queryKey,
          meta: this.meta
        };
        return s(p), p;
      })();
      return this.#a = !1, this.options.persister ? this.options.persister(
        i,
        f,
        this
      ) : i(f);
    }, a = (() => {
      const i = {
        fetchOptions: t,
        options: this.options,
        queryKey: this.queryKey,
        client: this.#o,
        state: this.state,
        fetchFn: o
      };
      return s(i), i;
    })();
    this.options.behavior?.onFetch(a, this), this.#r = this.state, (this.state.fetchStatus === "idle" || this.state.fetchMeta !== a.fetchOptions?.meta) && this.#n({ type: "fetch", meta: a.fetchOptions?.meta }), this.#s = Ze({
      initialPromise: t?.initialPromise,
      fn: a.fetchFn,
      onCancel: (i) => {
        i instanceof ve && i.revert && this.setState({
          ...this.#r,
          fetchStatus: "idle"
        }), r.abort();
      },
      onFail: (i, l) => {
        this.#n({ type: "failed", failureCount: i, error: l });
      },
      onPause: () => {
        this.#n({ type: "pause" });
      },
      onContinue: () => {
        this.#n({ type: "continue" });
      },
      retry: a.options.retry,
      retryDelay: a.options.retryDelay,
      networkMode: a.options.networkMode,
      canRun: () => !0
    });
    try {
      const i = await this.#s.start();
      if (i === void 0)
        throw new Error(`${this.queryHash} data is undefined`);
      return this.setData(i), this.#t.config.onSuccess?.(i, this), this.#t.config.onSettled?.(
        i,
        this.state.error,
        this
      ), i;
    } catch (i) {
      if (i instanceof ve) {
        if (i.silent)
          return this.#s.promise;
        if (i.revert) {
          if (this.state.data === void 0)
            throw i;
          return this.state.data;
        }
      }
      throw this.#n({
        type: "error",
        error: i
      }), this.#t.config.onError?.(
        i,
        this
      ), this.#t.config.onSettled?.(
        this.state.data,
        i,
        this
      ), i;
    } finally {
      this.scheduleGc();
    }
  }
  #n(e) {
    const t = (r) => {
      switch (e.type) {
        case "failed":
          return {
            ...r,
            fetchFailureCount: e.failureCount,
            fetchFailureReason: e.error
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
            ...Gt(r.data, this.options),
            fetchMeta: e.meta ?? null
          };
        case "success":
          const s = {
            ...r,
            ...Qe(e.data, e.dataUpdatedAt),
            dataUpdateCount: r.dataUpdateCount + 1,
            ...!e.manual && {
              fetchStatus: "idle",
              fetchFailureCount: 0,
              fetchFailureReason: null
            }
          };
          return this.#r = e.manual ? s : void 0, s;
        case "error":
          const o = e.error;
          return {
            ...r,
            error: o,
            errorUpdateCount: r.errorUpdateCount + 1,
            errorUpdatedAt: Date.now(),
            fetchFailureCount: r.fetchFailureCount + 1,
            fetchFailureReason: o,
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
            ...e.state
          };
      }
    };
    this.state = t(this.state), M.batch(() => {
      this.observers.forEach((r) => {
        r.onQueryUpdate();
      }), this.#t.notify({ query: this, type: "updated", action: e });
    });
  }
};
function Gt(e, t) {
  return {
    fetchFailureCount: 0,
    fetchFailureReason: null,
    fetchStatus: Xe(t.networkMode) ? "fetching" : "paused",
    ...e === void 0 && {
      error: null,
      status: "pending"
    }
  };
}
function Qe(e, t) {
  return {
    data: e,
    dataUpdatedAt: t ?? Date.now(),
    error: null,
    isInvalidated: !1,
    status: "success"
  };
}
function Ne(e) {
  const t = typeof e.initialData == "function" ? e.initialData() : e.initialData, r = t !== void 0, s = r ? typeof e.initialDataUpdatedAt == "function" ? e.initialDataUpdatedAt() : e.initialDataUpdatedAt : 0;
  return {
    data: t,
    dataUpdateCount: 0,
    dataUpdatedAt: r ? s ?? Date.now() : 0,
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
function Ge(e) {
  return {
    onFetch: (t, r) => {
      const s = t.options, o = t.fetchOptions?.meta?.fetchMore?.direction, n = t.state.data?.pages || [], a = t.state.data?.pageParams || [];
      let i = { pages: [], pageParams: [] }, l = 0;
      const f = async () => {
        let p = !1;
        const w = (g) => {
          zt(
            g,
            () => t.signal,
            () => p = !0
          );
        }, v = Ye(t.options, t.fetchOptions), k = async (g, b, y) => {
          if (p)
            return Promise.reject();
          if (b == null && g.pages.length)
            return Promise.resolve(g);
          const T = (() => {
            const D = {
              client: t.client,
              queryKey: t.queryKey,
              pageParam: b,
              direction: y ? "backward" : "forward",
              meta: t.options.meta
            };
            return w(D), D;
          })(), z = await v(T), { maxPages: I } = t.options, E = y ? Tt : Rt;
          return {
            pages: E(g.pages, z, I),
            pageParams: E(g.pageParams, b, I)
          };
        };
        if (o && n.length) {
          const g = o === "backward", b = g ? Lt : Le, y = {
            pages: n,
            pageParams: a
          }, S = b(s, y);
          i = await k(y, S, g);
        } else {
          const g = e ?? n.length;
          do {
            const b = l === 0 ? a[0] ?? s.initialPageParam : Le(s, i);
            if (l > 0 && b == null)
              break;
            i = await k(i, b), l++;
          } while (l < g);
        }
        return i;
      };
      t.options.persister ? t.fetchFn = () => t.options.persister?.(
        f,
        {
          client: t.client,
          queryKey: t.queryKey,
          meta: t.options.meta,
          signal: t.signal
        },
        r
      ) : t.fetchFn = f;
    }
  };
}
function Le(e, { pages: t, pageParams: r }) {
  const s = t.length - 1;
  return t.length > 0 ? e.getNextPageParam(
    t[s],
    t,
    r[s],
    r
  ) : void 0;
}
function Lt(e, { pages: t, pageParams: r }) {
  return t.length > 0 ? e.getPreviousPageParam?.(t[0], t, r[0], r) : void 0;
}
var Ut = class extends et {
  #e;
  #r;
  #t;
  #o;
  constructor(e) {
    super(), this.#e = e.client, this.mutationId = e.mutationId, this.#t = e.mutationCache, this.#r = [], this.state = e.state || Kt(), this.setOptions(e.options), this.scheduleGc();
  }
  setOptions(e) {
    this.options = e, this.updateGcTime(this.options.gcTime);
  }
  get meta() {
    return this.options.meta;
  }
  addObserver(e) {
    this.#r.includes(e) || (this.#r.push(e), this.clearGcTimeout(), this.#t.notify({
      type: "observerAdded",
      mutation: this,
      observer: e
    }));
  }
  removeObserver(e) {
    this.#r = this.#r.filter((t) => t !== e), this.scheduleGc(), this.#t.notify({
      type: "observerRemoved",
      mutation: this,
      observer: e
    });
  }
  optionalRemove() {
    this.#r.length || (this.state.status === "pending" ? this.scheduleGc() : this.#t.remove(this));
  }
  continue() {
    return this.#o?.continue() ?? // continuing a mutation assumes that variables are set, mutation must have been dehydrated before
    this.execute(this.state.variables);
  }
  async execute(e) {
    const t = () => {
      this.#s({ type: "continue" });
    }, r = {
      client: this.#e,
      meta: this.options.meta,
      mutationKey: this.options.mutationKey
    };
    this.#o = Ze({
      fn: () => this.options.mutationFn ? this.options.mutationFn(e, r) : Promise.reject(new Error("No mutationFn found")),
      onFail: (n, a) => {
        this.#s({ type: "failed", failureCount: n, error: a });
      },
      onPause: () => {
        this.#s({ type: "pause" });
      },
      onContinue: t,
      retry: this.options.retry ?? 0,
      retryDelay: this.options.retryDelay,
      networkMode: this.options.networkMode,
      canRun: () => this.#t.canRun(this)
    });
    const s = this.state.status === "pending", o = !this.#o.canStart();
    try {
      if (s)
        t();
      else {
        this.#s({ type: "pending", variables: e, isPaused: o }), this.#t.config.onMutate && await this.#t.config.onMutate(
          e,
          this,
          r
        );
        const a = await this.options.onMutate?.(
          e,
          r
        );
        a !== this.state.context && this.#s({
          type: "pending",
          context: a,
          variables: e,
          isPaused: o
        });
      }
      const n = await this.#o.start();
      return await this.#t.config.onSuccess?.(
        n,
        e,
        this.state.context,
        this,
        r
      ), await this.options.onSuccess?.(
        n,
        e,
        this.state.context,
        r
      ), await this.#t.config.onSettled?.(
        n,
        null,
        this.state.variables,
        this.state.context,
        this,
        r
      ), await this.options.onSettled?.(
        n,
        null,
        e,
        this.state.context,
        r
      ), this.#s({ type: "success", data: n }), n;
    } catch (n) {
      try {
        await this.#t.config.onError?.(
          n,
          e,
          this.state.context,
          this,
          r
        );
      } catch (a) {
        Promise.reject(a);
      }
      try {
        await this.options.onError?.(
          n,
          e,
          this.state.context,
          r
        );
      } catch (a) {
        Promise.reject(a);
      }
      try {
        await this.#t.config.onSettled?.(
          void 0,
          n,
          this.state.variables,
          this.state.context,
          this,
          r
        );
      } catch (a) {
        Promise.reject(a);
      }
      try {
        await this.options.onSettled?.(
          void 0,
          n,
          e,
          this.state.context,
          r
        );
      } catch (a) {
        Promise.reject(a);
      }
      throw this.#s({ type: "error", error: n }), n;
    } finally {
      this.#t.runNext(this);
    }
  }
  #s(e) {
    const t = (r) => {
      switch (e.type) {
        case "failed":
          return {
            ...r,
            failureCount: e.failureCount,
            failureReason: e.error
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
            context: e.context,
            data: void 0,
            failureCount: 0,
            failureReason: null,
            error: null,
            isPaused: e.isPaused,
            status: "pending",
            variables: e.variables,
            submittedAt: Date.now()
          };
        case "success":
          return {
            ...r,
            data: e.data,
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
            error: e.error,
            failureCount: r.failureCount + 1,
            failureReason: e.error,
            isPaused: !1,
            status: "error"
          };
      }
    };
    this.state = t(this.state), M.batch(() => {
      this.#r.forEach((r) => {
        r.onMutationUpdate(e);
      }), this.#t.notify({
        mutation: this,
        type: "updated",
        action: e
      });
    });
  }
};
function Kt() {
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
var Bt = class extends le {
  constructor(e = {}) {
    super(), this.config = e, this.#e = /* @__PURE__ */ new Set(), this.#r = /* @__PURE__ */ new Map(), this.#t = 0;
  }
  #e;
  #r;
  #t;
  build(e, t, r) {
    const s = new Ut({
      client: e,
      mutationCache: this,
      mutationId: ++this.#t,
      options: e.defaultMutationOptions(t),
      state: r
    });
    return this.add(s), s;
  }
  add(e) {
    this.#e.add(e);
    const t = se(e);
    if (typeof t == "string") {
      const r = this.#r.get(t);
      r ? r.push(e) : this.#r.set(t, [e]);
    }
    this.notify({ type: "added", mutation: e });
  }
  remove(e) {
    if (this.#e.delete(e)) {
      const t = se(e);
      if (typeof t == "string") {
        const r = this.#r.get(t);
        if (r)
          if (r.length > 1) {
            const s = r.indexOf(e);
            s !== -1 && r.splice(s, 1);
          } else r[0] === e && this.#r.delete(t);
      }
    }
    this.notify({ type: "removed", mutation: e });
  }
  canRun(e) {
    const t = se(e);
    if (typeof t == "string") {
      const s = this.#r.get(t)?.find(
        (o) => o.state.status === "pending"
      );
      return !s || s === e;
    } else
      return !0;
  }
  runNext(e) {
    const t = se(e);
    return typeof t == "string" ? this.#r.get(t)?.find((s) => s !== e && s.state.isPaused)?.continue() ?? Promise.resolve() : Promise.resolve();
  }
  clear() {
    M.batch(() => {
      this.#e.forEach((e) => {
        this.notify({ type: "removed", mutation: e });
      }), this.#e.clear(), this.#r.clear();
    });
  }
  getAll() {
    return Array.from(this.#e);
  }
  find(e) {
    const t = { exact: !0, ...e };
    return this.getAll().find(
      (r) => je(t, r)
    );
  }
  findAll(e = {}) {
    return this.getAll().filter((t) => je(e, t));
  }
  notify(e) {
    M.batch(() => {
      this.listeners.forEach((t) => {
        t(e);
      });
    });
  }
  resumePausedMutations() {
    const e = this.getAll().filter((t) => t.state.isPaused);
    return M.batch(
      () => Promise.all(
        e.map((t) => t.continue().catch(q))
      )
    );
  }
};
function se(e) {
  return e.options.scope?.id;
}
var Vt = class extends le {
  constructor(e = {}) {
    super(), this.config = e, this.#e = /* @__PURE__ */ new Map();
  }
  #e;
  build(e, t, r) {
    const s = t.queryKey, o = t.queryHash ?? ke(s, t);
    let n = this.get(o);
    return n || (n = new Nt({
      client: e,
      queryKey: s,
      queryHash: o,
      options: e.defaultQueryOptions(t),
      state: r,
      defaultOptions: e.getQueryDefaults(s)
    }), this.add(n)), n;
  }
  add(e) {
    this.#e.has(e.queryHash) || (this.#e.set(e.queryHash, e), this.notify({
      type: "added",
      query: e
    }));
  }
  remove(e) {
    const t = this.#e.get(e.queryHash);
    t && (e.destroy(), t === e && this.#e.delete(e.queryHash), this.notify({ type: "removed", query: e }));
  }
  clear() {
    M.batch(() => {
      this.getAll().forEach((e) => {
        this.remove(e);
      });
    });
  }
  get(e) {
    return this.#e.get(e);
  }
  getAll() {
    return [...this.#e.values()];
  }
  find(e) {
    const t = { exact: !0, ...e };
    return this.getAll().find(
      (r) => Ee(t, r)
    );
  }
  findAll(e = {}) {
    const t = this.getAll();
    return Object.keys(e).length > 0 ? t.filter((r) => Ee(e, r)) : t;
  }
  notify(e) {
    M.batch(() => {
      this.listeners.forEach((t) => {
        t(e);
      });
    });
  }
  onFocus() {
    M.batch(() => {
      this.getAll().forEach((e) => {
        e.onFocus();
      });
    });
  }
  onOnline() {
    M.batch(() => {
      this.getAll().forEach((e) => {
        e.onOnline();
      });
    });
  }
}, Wt = class {
  #e;
  #r;
  #t;
  #o;
  #s;
  #i;
  #a;
  #n;
  constructor(e = {}) {
    this.#e = e.queryCache || new Vt(), this.#r = e.mutationCache || new Bt(), this.#t = e.defaultOptions || {}, this.#o = /* @__PURE__ */ new Map(), this.#s = /* @__PURE__ */ new Map(), this.#i = 0;
  }
  mount() {
    this.#i++, this.#i === 1 && (this.#a = Je.subscribe(async (e) => {
      e && (await this.resumePausedMutations(), this.#e.onFocus());
    }), this.#n = ie.subscribe(async (e) => {
      e && (await this.resumePausedMutations(), this.#e.onOnline());
    }));
  }
  unmount() {
    this.#i--, this.#i === 0 && (this.#a?.(), this.#a = void 0, this.#n?.(), this.#n = void 0);
  }
  isFetching(e) {
    return this.#e.findAll({ ...e, fetchStatus: "fetching" }).length;
  }
  isMutating(e) {
    return this.#r.findAll({ ...e, status: "pending" }).length;
  }
  /**
   * Imperative (non-reactive) way to retrieve data for a QueryKey.
   * Should only be used in callbacks or functions where reading the latest data is necessary, e.g. for optimistic updates.
   *
   * Hint: Do not use this function inside a component, because it won't receive updates.
   * Use `useQuery` to create a `QueryObserver` that subscribes to changes.
   */
  getQueryData(e) {
    const t = this.defaultQueryOptions({ queryKey: e });
    return this.#e.get(t.queryHash)?.state.data;
  }
  ensureQueryData(e) {
    const t = this.defaultQueryOptions(e), r = this.#e.build(this, t), s = r.state.data;
    return s === void 0 ? this.fetchQuery(e) : (e.revalidateIfStale && r.isStaleByTime(ge(t.staleTime, r)) && this.prefetchQuery(t), Promise.resolve(s));
  }
  getQueriesData(e) {
    return this.#e.findAll(e).map(({ queryKey: t, state: r }) => {
      const s = r.data;
      return [t, s];
    });
  }
  setQueryData(e, t, r) {
    const s = this.defaultQueryOptions({ queryKey: e }), n = this.#e.get(
      s.queryHash
    )?.state.data, a = Ct(t, n);
    if (a !== void 0)
      return this.#e.build(this, s).setData(a, { ...r, manual: !0 });
  }
  setQueriesData(e, t, r) {
    return M.batch(
      () => this.#e.findAll(e).map(({ queryKey: s }) => [
        s,
        this.setQueryData(s, t, r)
      ])
    );
  }
  getQueryState(e) {
    const t = this.defaultQueryOptions({ queryKey: e });
    return this.#e.get(
      t.queryHash
    )?.state;
  }
  removeQueries(e) {
    const t = this.#e;
    M.batch(() => {
      t.findAll(e).forEach((r) => {
        t.remove(r);
      });
    });
  }
  resetQueries(e, t) {
    const r = this.#e;
    return M.batch(() => (r.findAll(e).forEach((s) => {
      s.reset();
    }), this.refetchQueries(
      {
        type: "active",
        ...e
      },
      t
    )));
  }
  cancelQueries(e, t = {}) {
    const r = { revert: !0, ...t }, s = M.batch(
      () => this.#e.findAll(e).map((o) => o.cancel(r))
    );
    return Promise.all(s).then(q).catch(q);
  }
  invalidateQueries(e, t = {}) {
    return M.batch(() => (this.#e.findAll(e).forEach((r) => {
      r.invalidate();
    }), e?.refetchType === "none" ? Promise.resolve() : this.refetchQueries(
      {
        ...e,
        type: e?.refetchType ?? e?.type ?? "active"
      },
      t
    )));
  }
  refetchQueries(e, t = {}) {
    const r = {
      ...t,
      cancelRefetch: t.cancelRefetch ?? !0
    }, s = M.batch(
      () => this.#e.findAll(e).filter((o) => !o.isDisabled() && !o.isStatic()).map((o) => {
        let n = o.fetch(void 0, r);
        return r.throwOnError || (n = n.catch(q)), o.state.fetchStatus === "paused" ? Promise.resolve() : n;
      })
    );
    return Promise.all(s).then(q);
  }
  fetchQuery(e) {
    const t = this.defaultQueryOptions(e);
    t.retry === void 0 && (t.retry = !1);
    const r = this.#e.build(this, t);
    return r.isStaleByTime(
      ge(t.staleTime, r)
    ) ? r.fetch(t) : Promise.resolve(r.state.data);
  }
  prefetchQuery(e) {
    return this.fetchQuery(e).then(q).catch(q);
  }
  fetchInfiniteQuery(e) {
    return e.behavior = Ge(e.pages), this.fetchQuery(e);
  }
  prefetchInfiniteQuery(e) {
    return this.fetchInfiniteQuery(e).then(q).catch(q);
  }
  ensureInfiniteQueryData(e) {
    return e.behavior = Ge(e.pages), this.ensureQueryData(e);
  }
  resumePausedMutations() {
    return ie.isOnline() ? this.#r.resumePausedMutations() : Promise.resolve();
  }
  getQueryCache() {
    return this.#e;
  }
  getMutationCache() {
    return this.#r;
  }
  getDefaultOptions() {
    return this.#t;
  }
  setDefaultOptions(e) {
    this.#t = e;
  }
  setQueryDefaults(e, t) {
    this.#o.set(Y(e), {
      queryKey: e,
      defaultOptions: t
    });
  }
  getQueryDefaults(e) {
    const t = [...this.#o.values()], r = {};
    return t.forEach((s) => {
      J(e, s.queryKey) && Object.assign(r, s.defaultOptions);
    }), r;
  }
  setMutationDefaults(e, t) {
    this.#s.set(Y(e), {
      mutationKey: e,
      defaultOptions: t
    });
  }
  getMutationDefaults(e) {
    const t = [...this.#s.values()], r = {};
    return t.forEach((s) => {
      J(e, s.mutationKey) && Object.assign(r, s.defaultOptions);
    }), r;
  }
  defaultQueryOptions(e) {
    if (e._defaulted)
      return e;
    const t = {
      ...this.#t.queries,
      ...this.getQueryDefaults(e.queryKey),
      ...e,
      _defaulted: !0
    };
    return t.queryHash || (t.queryHash = ke(
      t.queryKey,
      t
    )), t.refetchOnReconnect === void 0 && (t.refetchOnReconnect = t.networkMode !== "always"), t.throwOnError === void 0 && (t.throwOnError = !!t.suspense), !t.networkMode && t.persister && (t.networkMode = "offlineFirst"), t.queryFn === Ce && (t.enabled = !1), t;
  }
  defaultMutationOptions(e) {
    return e?._defaulted ? e : {
      ...this.#t.mutations,
      ...e?.mutationKey && this.getMutationDefaults(e.mutationKey),
      ...e,
      _defaulted: !0
    };
  }
  clear() {
    this.#e.clear(), this.#r.clear();
  }
}, tt = xe.createContext(
  void 0
), $r = (e) => {
  const t = xe.useContext(tt);
  if (!t)
    throw new Error("No QueryClient set, use QueryClientProvider to set one");
  return t;
}, _t = ({
  client: e,
  children: t
}) => (xe.useEffect(() => (e.mount(), () => {
  e.unmount();
}), [e]), /* @__PURE__ */ x(tt.Provider, { value: e, children: t }));
class Ht extends yt {
  constructor(t) {
    super(t), this.state = { hasError: !1, error: null };
  }
  static getDerivedStateFromError(t) {
    return { hasError: !0, error: t };
  }
  componentDidCatch(t, r) {
    console.error(`[ErrorBoundary] ${this.props.viewId ?? "unknown"}:`, t, r);
  }
  render() {
    return this.state.hasError ? /* @__PURE__ */ $("div", { className: "glass-panel rounded-2xl p-8 mt-6 text-center", children: [
      /* @__PURE__ */ x("div", { className: "text-2xl font-bold text-red-400 mb-2", children: "Something went wrong" }),
      /* @__PURE__ */ $("p", { className: "text-slate-400 mb-4", children: [
        "Route: ",
        /* @__PURE__ */ x("code", { className: "text-slate-300", children: this.props.viewId ?? "unknown" })
      ] }),
      /* @__PURE__ */ x("pre", { className: "text-xs text-slate-500 bg-slate-950/80 rounded-xl p-4 overflow-auto text-left max-h-40", children: this.state.error?.message }),
      /* @__PURE__ */ x(
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
function rt(e) {
  var t, r, s = "";
  if (typeof e == "string" || typeof e == "number") s += e;
  else if (typeof e == "object") if (Array.isArray(e)) {
    var o = e.length;
    for (t = 0; t < o; t++) e[t] && (r = rt(e[t])) && (s && (s += " "), s += r);
  } else for (r in e) e[r] && (s && (s += " "), s += r);
  return s;
}
function $t() {
  for (var e, t, r = 0, s = "", o = arguments.length; r < o; r++) (e = arguments[r]) && (t = rt(e)) && (s && (s += " "), s += t);
  return s;
}
const Yt = (e, t) => {
  const r = new Array(e.length + t.length);
  for (let s = 0; s < e.length; s++)
    r[s] = e[s];
  for (let s = 0; s < t.length; s++)
    r[e.length + s] = t[s];
  return r;
}, Jt = (e, t) => ({
  classGroupId: e,
  validator: t
}), st = (e = /* @__PURE__ */ new Map(), t = null, r) => ({
  nextPart: e,
  validators: t,
  classGroupId: r
}), ae = "-", Ue = [], Xt = "arbitrary..", Zt = (e) => {
  const t = tr(e), {
    conflictingClassGroups: r,
    conflictingClassGroupModifiers: s
  } = e;
  return {
    getClassGroupId: (a) => {
      if (a.startsWith("[") && a.endsWith("]"))
        return er(a);
      const i = a.split(ae), l = i[0] === "" && i.length > 1 ? 1 : 0;
      return ot(i, l, t);
    },
    getConflictingClassGroupIds: (a, i) => {
      if (i) {
        const l = s[a], f = r[a];
        return l ? f ? Yt(f, l) : l : f || Ue;
      }
      return r[a] || Ue;
    }
  };
}, ot = (e, t, r) => {
  if (e.length - t === 0)
    return r.classGroupId;
  const o = e[t], n = r.nextPart.get(o);
  if (n) {
    const f = ot(e, t + 1, n);
    if (f) return f;
  }
  const a = r.validators;
  if (a === null)
    return;
  const i = t === 0 ? e.join(ae) : e.slice(t).join(ae), l = a.length;
  for (let f = 0; f < l; f++) {
    const p = a[f];
    if (p.validator(i))
      return p.classGroupId;
  }
}, er = (e) => e.slice(1, -1).indexOf(":") === -1 ? void 0 : (() => {
  const t = e.slice(1, -1), r = t.indexOf(":"), s = t.slice(0, r);
  return s ? Xt + s : void 0;
})(), tr = (e) => {
  const {
    theme: t,
    classGroups: r
  } = e;
  return rr(r, t);
}, rr = (e, t) => {
  const r = st();
  for (const s in e) {
    const o = e[s];
    Se(o, r, s, t);
  }
  return r;
}, Se = (e, t, r, s) => {
  const o = e.length;
  for (let n = 0; n < o; n++) {
    const a = e[n];
    sr(a, t, r, s);
  }
}, sr = (e, t, r, s) => {
  if (typeof e == "string") {
    or(e, t, r);
    return;
  }
  if (typeof e == "function") {
    nr(e, t, r, s);
    return;
  }
  ir(e, t, r, s);
}, or = (e, t, r) => {
  const s = e === "" ? t : nt(t, e);
  s.classGroupId = r;
}, nr = (e, t, r, s) => {
  if (ar(e)) {
    Se(e(s), t, r, s);
    return;
  }
  t.validators === null && (t.validators = []), t.validators.push(Jt(r, e));
}, ir = (e, t, r, s) => {
  const o = Object.entries(e), n = o.length;
  for (let a = 0; a < n; a++) {
    const [i, l] = o[a];
    Se(l, nt(t, i), r, s);
  }
}, nt = (e, t) => {
  let r = e;
  const s = t.split(ae), o = s.length;
  for (let n = 0; n < o; n++) {
    const a = s[n];
    let i = r.nextPart.get(a);
    i || (i = st(), r.nextPart.set(a, i)), r = i;
  }
  return r;
}, ar = (e) => "isThemeGetter" in e && e.isThemeGetter === !0, lr = (e) => {
  if (e < 1)
    return {
      get: () => {
      },
      set: () => {
      }
    };
  let t = 0, r = /* @__PURE__ */ Object.create(null), s = /* @__PURE__ */ Object.create(null);
  const o = (n, a) => {
    r[n] = a, t++, t > e && (t = 0, s = r, r = /* @__PURE__ */ Object.create(null));
  };
  return {
    get(n) {
      let a = r[n];
      if (a !== void 0)
        return a;
      if ((a = s[n]) !== void 0)
        return o(n, a), a;
    },
    set(n, a) {
      n in r ? r[n] = a : o(n, a);
    }
  };
}, we = "!", Ke = ":", cr = [], Be = (e, t, r, s, o) => ({
  modifiers: e,
  hasImportantModifier: t,
  baseClassName: r,
  maybePostfixModifierPosition: s,
  isExternal: o
}), ur = (e) => {
  const {
    prefix: t,
    experimentalParseClassName: r
  } = e;
  let s = (o) => {
    const n = [];
    let a = 0, i = 0, l = 0, f;
    const p = o.length;
    for (let b = 0; b < p; b++) {
      const y = o[b];
      if (a === 0 && i === 0) {
        if (y === Ke) {
          n.push(o.slice(l, b)), l = b + 1;
          continue;
        }
        if (y === "/") {
          f = b;
          continue;
        }
      }
      y === "[" ? a++ : y === "]" ? a-- : y === "(" ? i++ : y === ")" && i--;
    }
    const w = n.length === 0 ? o : o.slice(l);
    let v = w, k = !1;
    w.endsWith(we) ? (v = w.slice(0, -1), k = !0) : (
      /**
       * In Tailwind CSS v3 the important modifier was at the start of the base class name. This is still supported for legacy reasons.
       * @see https://github.com/dcastil/tailwind-merge/issues/513#issuecomment-2614029864
       */
      w.startsWith(we) && (v = w.slice(1), k = !0)
    );
    const g = f && f > l ? f - l : void 0;
    return Be(n, k, v, g);
  };
  if (t) {
    const o = t + Ke, n = s;
    s = (a) => a.startsWith(o) ? n(a.slice(o.length)) : Be(cr, !1, a, void 0, !0);
  }
  if (r) {
    const o = s;
    s = (n) => r({
      className: n,
      parseClassName: o
    });
  }
  return s;
}, dr = (e) => {
  const t = /* @__PURE__ */ new Map();
  return e.orderSensitiveModifiers.forEach((r, s) => {
    t.set(r, 1e6 + s);
  }), (r) => {
    const s = [];
    let o = [];
    for (let n = 0; n < r.length; n++) {
      const a = r[n], i = a[0] === "[", l = t.has(a);
      i || l ? (o.length > 0 && (o.sort(), s.push(...o), o = []), s.push(a)) : o.push(a);
    }
    return o.length > 0 && (o.sort(), s.push(...o)), s;
  };
}, hr = (e) => ({
  cache: lr(e.cacheSize),
  parseClassName: ur(e),
  sortModifiers: dr(e),
  ...Zt(e)
}), fr = /\s+/, mr = (e, t) => {
  const {
    parseClassName: r,
    getClassGroupId: s,
    getConflictingClassGroupIds: o,
    sortModifiers: n
  } = t, a = [], i = e.trim().split(fr);
  let l = "";
  for (let f = i.length - 1; f >= 0; f -= 1) {
    const p = i[f], {
      isExternal: w,
      modifiers: v,
      hasImportantModifier: k,
      baseClassName: g,
      maybePostfixModifierPosition: b
    } = r(p);
    if (w) {
      l = p + (l.length > 0 ? " " + l : l);
      continue;
    }
    let y = !!b, S = s(y ? g.substring(0, b) : g);
    if (!S) {
      if (!y) {
        l = p + (l.length > 0 ? " " + l : l);
        continue;
      }
      if (S = s(g), !S) {
        l = p + (l.length > 0 ? " " + l : l);
        continue;
      }
      y = !1;
    }
    const T = v.length === 0 ? "" : v.length === 1 ? v[0] : n(v).join(":"), z = k ? T + we : T, I = z + S;
    if (a.indexOf(I) > -1)
      continue;
    a.push(I);
    const E = o(S, y);
    for (let D = 0; D < E.length; ++D) {
      const W = E[D];
      a.push(z + W);
    }
    l = p + (l.length > 0 ? " " + l : l);
  }
  return l;
}, pr = (...e) => {
  let t = 0, r, s, o = "";
  for (; t < e.length; )
    (r = e[t++]) && (s = it(r)) && (o && (o += " "), o += s);
  return o;
}, it = (e) => {
  if (typeof e == "string")
    return e;
  let t, r = "";
  for (let s = 0; s < e.length; s++)
    e[s] && (t = it(e[s])) && (r && (r += " "), r += t);
  return r;
}, br = (e, ...t) => {
  let r, s, o, n;
  const a = (l) => {
    const f = t.reduce((p, w) => w(p), e());
    return r = hr(f), s = r.cache.get, o = r.cache.set, n = i, i(l);
  }, i = (l) => {
    const f = s(l);
    if (f)
      return f;
    const p = mr(l, r);
    return o(l, p), p;
  };
  return n = a, (...l) => n(pr(...l));
}, gr = [], C = (e) => {
  const t = (r) => r[e] || gr;
  return t.isThemeGetter = !0, t;
}, at = /^\[(?:(\w[\w-]*):)?(.+)\]$/i, lt = /^\((?:(\w[\w-]*):)?(.+)\)$/i, yr = /^\d+(?:\.\d+)?\/\d+(?:\.\d+)?$/, vr = /^(\d+(\.\d+)?)?(xs|sm|md|lg|xl)$/, wr = /\d+(%|px|r?em|[sdl]?v([hwib]|min|max)|pt|pc|in|cm|mm|cap|ch|ex|r?lh|cq(w|h|i|b|min|max))|\b(calc|min|max|clamp)\(.+\)|^0$/, xr = /^(rgba?|hsla?|hwb|(ok)?(lab|lch)|color-mix)\(.+\)$/, kr = /^(inset_)?-?((\d+)?\.?(\d+)[a-z]+|0)_-?((\d+)?\.?(\d+)[a-z]+|0)/, Cr = /^(url|image|image-set|cross-fade|element|(repeating-)?(linear|radial|conic)-gradient)\(.+\)$/, N = (e) => yr.test(e), m = (e) => !!e && !Number.isNaN(Number(e)), G = (e) => !!e && Number.isInteger(Number(e)), pe = (e) => e.endsWith("%") && m(e.slice(0, -1)), Q = (e) => vr.test(e), ct = () => !0, Sr = (e) => (
  // `colorFunctionRegex` check is necessary because color functions can have percentages in them which which would be incorrectly classified as lengths.
  // For example, `hsl(0 0% 0%)` would be classified as a length without this check.
  // I could also use lookbehind assertion in `lengthUnitRegex` but that isn't supported widely enough.
  wr.test(e) && !xr.test(e)
), Pe = () => !1, Pr = (e) => kr.test(e), Or = (e) => Cr.test(e), Ar = (e) => !c(e) && !u(e), Fr = (e) => L(e, ht, Pe), c = (e) => at.test(e), K = (e) => L(e, ft, Sr), Ve = (e) => L(e, qr, m), Mr = (e) => L(e, pt, ct), Rr = (e) => L(e, mt, Pe), We = (e) => L(e, ut, Pe), Tr = (e) => L(e, dt, Or), oe = (e) => L(e, bt, Pr), u = (e) => lt.test(e), _ = (e) => B(e, ft), zr = (e) => B(e, mt), _e = (e) => B(e, ut), Ir = (e) => B(e, ht), Er = (e) => B(e, dt), ne = (e) => B(e, bt, !0), jr = (e) => B(e, pt, !0), L = (e, t, r) => {
  const s = at.exec(e);
  return s ? s[1] ? t(s[1]) : r(s[2]) : !1;
}, B = (e, t, r = !1) => {
  const s = lt.exec(e);
  return s ? s[1] ? t(s[1]) : r : !1;
}, ut = (e) => e === "position" || e === "percentage", dt = (e) => e === "image" || e === "url", ht = (e) => e === "length" || e === "size" || e === "bg-size", ft = (e) => e === "length", qr = (e) => e === "number", mt = (e) => e === "family-name", pt = (e) => e === "number" || e === "weight", bt = (e) => e === "shadow", Dr = () => {
  const e = C("color"), t = C("font"), r = C("text"), s = C("font-weight"), o = C("tracking"), n = C("leading"), a = C("breakpoint"), i = C("container"), l = C("spacing"), f = C("radius"), p = C("shadow"), w = C("inset-shadow"), v = C("text-shadow"), k = C("drop-shadow"), g = C("blur"), b = C("perspective"), y = C("aspect"), S = C("ease"), T = C("animate"), z = () => ["auto", "avoid", "all", "avoid-page", "page", "left", "right", "column"], I = () => [
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
  ], E = () => [...I(), u, c], D = () => ["auto", "hidden", "clip", "visible", "scroll"], W = () => ["auto", "contain", "none"], d = () => [u, c, l], R = () => [N, "full", "auto", ...d()], Oe = () => [G, "none", "subgrid", u, c], Ae = () => ["auto", {
    span: ["full", G, u, c]
  }, G, u, c], X = () => [G, "auto", u, c], Fe = () => ["auto", "min", "max", "fr", u, c], ue = () => ["start", "end", "center", "between", "around", "evenly", "stretch", "baseline", "center-safe", "end-safe"], V = () => ["start", "end", "center", "stretch", "center-safe", "end-safe"], j = () => ["auto", ...d()], U = () => [N, "auto", "full", "dvw", "dvh", "lvw", "lvh", "svw", "svh", "min", "max", "fit", ...d()], de = () => [N, "screen", "full", "dvw", "lvw", "svw", "min", "max", "fit", ...d()], he = () => [N, "screen", "full", "lh", "dvh", "lvh", "svh", "min", "max", "fit", ...d()], h = () => [e, u, c], Me = () => [...I(), _e, We, {
    position: [u, c]
  }], Re = () => ["no-repeat", {
    repeat: ["", "x", "y", "space", "round"]
  }], Te = () => ["auto", "cover", "contain", Ir, Fr, {
    size: [u, c]
  }], fe = () => [pe, _, K], A = () => [
    // Deprecated since Tailwind CSS v4.0.0
    "",
    "none",
    "full",
    f,
    u,
    c
  ], F = () => ["", m, _, K], Z = () => ["solid", "dashed", "dotted", "double"], ze = () => ["normal", "multiply", "screen", "overlay", "darken", "lighten", "color-dodge", "color-burn", "hard-light", "soft-light", "difference", "exclusion", "hue", "saturation", "color", "luminosity"], P = () => [m, pe, _e, We], Ie = () => [
    // Deprecated since Tailwind CSS v4.0.0
    "",
    "none",
    g,
    u,
    c
  ], ee = () => ["none", m, u, c], te = () => ["none", m, u, c], me = () => [m, u, c], re = () => [N, "full", ...d()];
  return {
    cacheSize: 500,
    theme: {
      animate: ["spin", "ping", "pulse", "bounce"],
      aspect: ["video"],
      blur: [Q],
      breakpoint: [Q],
      color: [ct],
      container: [Q],
      "drop-shadow": [Q],
      ease: ["in", "out", "in-out"],
      font: [Ar],
      "font-weight": ["thin", "extralight", "light", "normal", "medium", "semibold", "bold", "extrabold", "black"],
      "inset-shadow": [Q],
      leading: ["none", "tight", "snug", "normal", "relaxed", "loose"],
      perspective: ["dramatic", "near", "normal", "midrange", "distant", "none"],
      radius: [Q],
      shadow: [Q],
      spacing: ["px", m],
      text: [Q],
      "text-shadow": [Q],
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
        aspect: ["auto", "square", N, c, u, y]
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
        columns: [m, c, u, i]
      }],
      /**
       * Break After
       * @see https://tailwindcss.com/docs/break-after
       */
      "break-after": [{
        "break-after": z()
      }],
      /**
       * Break Before
       * @see https://tailwindcss.com/docs/break-before
       */
      "break-before": [{
        "break-before": z()
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
        object: E()
      }],
      /**
       * Overflow
       * @see https://tailwindcss.com/docs/overflow
       */
      overflow: [{
        overflow: D()
      }],
      /**
       * Overflow X
       * @see https://tailwindcss.com/docs/overflow
       */
      "overflow-x": [{
        "overflow-x": D()
      }],
      /**
       * Overflow Y
       * @see https://tailwindcss.com/docs/overflow
       */
      "overflow-y": [{
        "overflow-y": D()
      }],
      /**
       * Overscroll Behavior
       * @see https://tailwindcss.com/docs/overscroll-behavior
       */
      overscroll: [{
        overscroll: W()
      }],
      /**
       * Overscroll Behavior X
       * @see https://tailwindcss.com/docs/overscroll-behavior
       */
      "overscroll-x": [{
        "overscroll-x": W()
      }],
      /**
       * Overscroll Behavior Y
       * @see https://tailwindcss.com/docs/overscroll-behavior
       */
      "overscroll-y": [{
        "overscroll-y": W()
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
        inset: R()
      }],
      /**
       * Inset Inline
       * @see https://tailwindcss.com/docs/top-right-bottom-left
       */
      "inset-x": [{
        "inset-x": R()
      }],
      /**
       * Inset Block
       * @see https://tailwindcss.com/docs/top-right-bottom-left
       */
      "inset-y": [{
        "inset-y": R()
      }],
      /**
       * Inset Inline Start
       * @see https://tailwindcss.com/docs/top-right-bottom-left
       * @todo class group will be renamed to `inset-s` in next major release
       */
      start: [{
        "inset-s": R(),
        /**
         * @deprecated since Tailwind CSS v4.2.0 in favor of `inset-s-*` utilities.
         * @see https://github.com/tailwindlabs/tailwindcss/pull/19613
         */
        start: R()
      }],
      /**
       * Inset Inline End
       * @see https://tailwindcss.com/docs/top-right-bottom-left
       * @todo class group will be renamed to `inset-e` in next major release
       */
      end: [{
        "inset-e": R(),
        /**
         * @deprecated since Tailwind CSS v4.2.0 in favor of `inset-e-*` utilities.
         * @see https://github.com/tailwindlabs/tailwindcss/pull/19613
         */
        end: R()
      }],
      /**
       * Inset Block Start
       * @see https://tailwindcss.com/docs/top-right-bottom-left
       */
      "inset-bs": [{
        "inset-bs": R()
      }],
      /**
       * Inset Block End
       * @see https://tailwindcss.com/docs/top-right-bottom-left
       */
      "inset-be": [{
        "inset-be": R()
      }],
      /**
       * Top
       * @see https://tailwindcss.com/docs/top-right-bottom-left
       */
      top: [{
        top: R()
      }],
      /**
       * Right
       * @see https://tailwindcss.com/docs/top-right-bottom-left
       */
      right: [{
        right: R()
      }],
      /**
       * Bottom
       * @see https://tailwindcss.com/docs/top-right-bottom-left
       */
      bottom: [{
        bottom: R()
      }],
      /**
       * Left
       * @see https://tailwindcss.com/docs/top-right-bottom-left
       */
      left: [{
        left: R()
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
        z: [G, "auto", u, c]
      }],
      // ------------------------
      // --- Flexbox and Grid ---
      // ------------------------
      /**
       * Flex Basis
       * @see https://tailwindcss.com/docs/flex-basis
       */
      basis: [{
        basis: [N, "full", "auto", i, ...d()]
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
        flex: [m, N, "auto", "initial", "none", c]
      }],
      /**
       * Flex Grow
       * @see https://tailwindcss.com/docs/flex-grow
       */
      grow: [{
        grow: ["", m, u, c]
      }],
      /**
       * Flex Shrink
       * @see https://tailwindcss.com/docs/flex-shrink
       */
      shrink: [{
        shrink: ["", m, u, c]
      }],
      /**
       * Order
       * @see https://tailwindcss.com/docs/order
       */
      order: [{
        order: [G, "first", "last", "none", u, c]
      }],
      /**
       * Grid Template Columns
       * @see https://tailwindcss.com/docs/grid-template-columns
       */
      "grid-cols": [{
        "grid-cols": Oe()
      }],
      /**
       * Grid Column Start / End
       * @see https://tailwindcss.com/docs/grid-column
       */
      "col-start-end": [{
        col: Ae()
      }],
      /**
       * Grid Column Start
       * @see https://tailwindcss.com/docs/grid-column
       */
      "col-start": [{
        "col-start": X()
      }],
      /**
       * Grid Column End
       * @see https://tailwindcss.com/docs/grid-column
       */
      "col-end": [{
        "col-end": X()
      }],
      /**
       * Grid Template Rows
       * @see https://tailwindcss.com/docs/grid-template-rows
       */
      "grid-rows": [{
        "grid-rows": Oe()
      }],
      /**
       * Grid Row Start / End
       * @see https://tailwindcss.com/docs/grid-row
       */
      "row-start-end": [{
        row: Ae()
      }],
      /**
       * Grid Row Start
       * @see https://tailwindcss.com/docs/grid-row
       */
      "row-start": [{
        "row-start": X()
      }],
      /**
       * Grid Row End
       * @see https://tailwindcss.com/docs/grid-row
       */
      "row-end": [{
        "row-end": X()
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
        "auto-cols": Fe()
      }],
      /**
       * Grid Auto Rows
       * @see https://tailwindcss.com/docs/grid-auto-rows
       */
      "auto-rows": [{
        "auto-rows": Fe()
      }],
      /**
       * Gap
       * @see https://tailwindcss.com/docs/gap
       */
      gap: [{
        gap: d()
      }],
      /**
       * Gap X
       * @see https://tailwindcss.com/docs/gap
       */
      "gap-x": [{
        "gap-x": d()
      }],
      /**
       * Gap Y
       * @see https://tailwindcss.com/docs/gap
       */
      "gap-y": [{
        "gap-y": d()
      }],
      /**
       * Justify Content
       * @see https://tailwindcss.com/docs/justify-content
       */
      "justify-content": [{
        justify: [...ue(), "normal"]
      }],
      /**
       * Justify Items
       * @see https://tailwindcss.com/docs/justify-items
       */
      "justify-items": [{
        "justify-items": [...V(), "normal"]
      }],
      /**
       * Justify Self
       * @see https://tailwindcss.com/docs/justify-self
       */
      "justify-self": [{
        "justify-self": ["auto", ...V()]
      }],
      /**
       * Align Content
       * @see https://tailwindcss.com/docs/align-content
       */
      "align-content": [{
        content: ["normal", ...ue()]
      }],
      /**
       * Align Items
       * @see https://tailwindcss.com/docs/align-items
       */
      "align-items": [{
        items: [...V(), {
          baseline: ["", "last"]
        }]
      }],
      /**
       * Align Self
       * @see https://tailwindcss.com/docs/align-self
       */
      "align-self": [{
        self: ["auto", ...V(), {
          baseline: ["", "last"]
        }]
      }],
      /**
       * Place Content
       * @see https://tailwindcss.com/docs/place-content
       */
      "place-content": [{
        "place-content": ue()
      }],
      /**
       * Place Items
       * @see https://tailwindcss.com/docs/place-items
       */
      "place-items": [{
        "place-items": [...V(), "baseline"]
      }],
      /**
       * Place Self
       * @see https://tailwindcss.com/docs/place-self
       */
      "place-self": [{
        "place-self": ["auto", ...V()]
      }],
      // Spacing
      /**
       * Padding
       * @see https://tailwindcss.com/docs/padding
       */
      p: [{
        p: d()
      }],
      /**
       * Padding Inline
       * @see https://tailwindcss.com/docs/padding
       */
      px: [{
        px: d()
      }],
      /**
       * Padding Block
       * @see https://tailwindcss.com/docs/padding
       */
      py: [{
        py: d()
      }],
      /**
       * Padding Inline Start
       * @see https://tailwindcss.com/docs/padding
       */
      ps: [{
        ps: d()
      }],
      /**
       * Padding Inline End
       * @see https://tailwindcss.com/docs/padding
       */
      pe: [{
        pe: d()
      }],
      /**
       * Padding Block Start
       * @see https://tailwindcss.com/docs/padding
       */
      pbs: [{
        pbs: d()
      }],
      /**
       * Padding Block End
       * @see https://tailwindcss.com/docs/padding
       */
      pbe: [{
        pbe: d()
      }],
      /**
       * Padding Top
       * @see https://tailwindcss.com/docs/padding
       */
      pt: [{
        pt: d()
      }],
      /**
       * Padding Right
       * @see https://tailwindcss.com/docs/padding
       */
      pr: [{
        pr: d()
      }],
      /**
       * Padding Bottom
       * @see https://tailwindcss.com/docs/padding
       */
      pb: [{
        pb: d()
      }],
      /**
       * Padding Left
       * @see https://tailwindcss.com/docs/padding
       */
      pl: [{
        pl: d()
      }],
      /**
       * Margin
       * @see https://tailwindcss.com/docs/margin
       */
      m: [{
        m: j()
      }],
      /**
       * Margin Inline
       * @see https://tailwindcss.com/docs/margin
       */
      mx: [{
        mx: j()
      }],
      /**
       * Margin Block
       * @see https://tailwindcss.com/docs/margin
       */
      my: [{
        my: j()
      }],
      /**
       * Margin Inline Start
       * @see https://tailwindcss.com/docs/margin
       */
      ms: [{
        ms: j()
      }],
      /**
       * Margin Inline End
       * @see https://tailwindcss.com/docs/margin
       */
      me: [{
        me: j()
      }],
      /**
       * Margin Block Start
       * @see https://tailwindcss.com/docs/margin
       */
      mbs: [{
        mbs: j()
      }],
      /**
       * Margin Block End
       * @see https://tailwindcss.com/docs/margin
       */
      mbe: [{
        mbe: j()
      }],
      /**
       * Margin Top
       * @see https://tailwindcss.com/docs/margin
       */
      mt: [{
        mt: j()
      }],
      /**
       * Margin Right
       * @see https://tailwindcss.com/docs/margin
       */
      mr: [{
        mr: j()
      }],
      /**
       * Margin Bottom
       * @see https://tailwindcss.com/docs/margin
       */
      mb: [{
        mb: j()
      }],
      /**
       * Margin Left
       * @see https://tailwindcss.com/docs/margin
       */
      ml: [{
        ml: j()
      }],
      /**
       * Space Between X
       * @see https://tailwindcss.com/docs/margin#adding-space-between-children
       */
      "space-x": [{
        "space-x": d()
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
        "space-y": d()
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
        inline: ["auto", ...de()]
      }],
      /**
       * Min-Inline Size
       * @see https://tailwindcss.com/docs/min-width
       */
      "min-inline-size": [{
        "min-inline": ["auto", ...de()]
      }],
      /**
       * Max-Inline Size
       * @see https://tailwindcss.com/docs/max-width
       */
      "max-inline-size": [{
        "max-inline": ["none", ...de()]
      }],
      /**
       * Block Size
       * @see https://tailwindcss.com/docs/height
       */
      "block-size": [{
        block: ["auto", ...he()]
      }],
      /**
       * Min-Block Size
       * @see https://tailwindcss.com/docs/min-height
       */
      "min-block-size": [{
        "min-block": ["auto", ...he()]
      }],
      /**
       * Max-Block Size
       * @see https://tailwindcss.com/docs/max-height
       */
      "max-block-size": [{
        "max-block": ["none", ...he()]
      }],
      /**
       * Width
       * @see https://tailwindcss.com/docs/width
       */
      w: [{
        w: [i, "screen", ...U()]
      }],
      /**
       * Min-Width
       * @see https://tailwindcss.com/docs/min-width
       */
      "min-w": [{
        "min-w": [
          i,
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
          i,
          "screen",
          "none",
          /** Deprecated since Tailwind CSS v4.0.0. @see https://github.com/tailwindlabs/tailwindcss.com/issues/2027#issuecomment-2620152757 */
          "prose",
          /** Deprecated since Tailwind CSS v4.0.0. @see https://github.com/tailwindlabs/tailwindcss.com/issues/2027#issuecomment-2620152757 */
          {
            screen: [a]
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
        text: ["base", r, _, K]
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
        font: [s, jr, Mr]
      }],
      /**
       * Font Stretch
       * @see https://tailwindcss.com/docs/font-stretch
       */
      "font-stretch": [{
        "font-stretch": ["ultra-condensed", "extra-condensed", "condensed", "semi-condensed", "normal", "semi-expanded", "expanded", "extra-expanded", "ultra-expanded", pe, c]
      }],
      /**
       * Font Family
       * @see https://tailwindcss.com/docs/font-family
       */
      "font-family": [{
        font: [zr, Rr, t]
      }],
      /**
       * Font Feature Settings
       * @see https://tailwindcss.com/docs/font-feature-settings
       */
      "font-features": [{
        "font-features": [c]
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
        tracking: [o, u, c]
      }],
      /**
       * Line Clamp
       * @see https://tailwindcss.com/docs/line-clamp
       */
      "line-clamp": [{
        "line-clamp": [m, "none", u, Ve]
      }],
      /**
       * Line Height
       * @see https://tailwindcss.com/docs/line-height
       */
      leading: [{
        leading: [
          /** Deprecated since Tailwind CSS v4.0.0. @see https://github.com/tailwindlabs/tailwindcss.com/issues/2027#issuecomment-2620152757 */
          n,
          ...d()
        ]
      }],
      /**
       * List Style Image
       * @see https://tailwindcss.com/docs/list-style-image
       */
      "list-image": [{
        "list-image": ["none", u, c]
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
        list: ["disc", "decimal", "none", u, c]
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
        placeholder: h()
      }],
      /**
       * Text Color
       * @see https://tailwindcss.com/docs/text-color
       */
      "text-color": [{
        text: h()
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
        decoration: [...Z(), "wavy"]
      }],
      /**
       * Text Decoration Thickness
       * @see https://tailwindcss.com/docs/text-decoration-thickness
       */
      "text-decoration-thickness": [{
        decoration: [m, "from-font", "auto", u, K]
      }],
      /**
       * Text Decoration Color
       * @see https://tailwindcss.com/docs/text-decoration-color
       */
      "text-decoration-color": [{
        decoration: h()
      }],
      /**
       * Text Underline Offset
       * @see https://tailwindcss.com/docs/text-underline-offset
       */
      "underline-offset": [{
        "underline-offset": [m, "auto", u, c]
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
        indent: d()
      }],
      /**
       * Vertical Alignment
       * @see https://tailwindcss.com/docs/vertical-align
       */
      "vertical-align": [{
        align: ["baseline", "top", "middle", "bottom", "text-top", "text-bottom", "sub", "super", u, c]
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
        content: ["none", u, c]
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
        bg: Me()
      }],
      /**
       * Background Repeat
       * @see https://tailwindcss.com/docs/background-repeat
       */
      "bg-repeat": [{
        bg: Re()
      }],
      /**
       * Background Size
       * @see https://tailwindcss.com/docs/background-size
       */
      "bg-size": [{
        bg: Te()
      }],
      /**
       * Background Image
       * @see https://tailwindcss.com/docs/background-image
       */
      "bg-image": [{
        bg: ["none", {
          linear: [{
            to: ["t", "tr", "r", "br", "b", "bl", "l", "tl"]
          }, G, u, c],
          radial: ["", u, c],
          conic: [G, u, c]
        }, Er, Tr]
      }],
      /**
       * Background Color
       * @see https://tailwindcss.com/docs/background-color
       */
      "bg-color": [{
        bg: h()
      }],
      /**
       * Gradient Color Stops From Position
       * @see https://tailwindcss.com/docs/gradient-color-stops
       */
      "gradient-from-pos": [{
        from: fe()
      }],
      /**
       * Gradient Color Stops Via Position
       * @see https://tailwindcss.com/docs/gradient-color-stops
       */
      "gradient-via-pos": [{
        via: fe()
      }],
      /**
       * Gradient Color Stops To Position
       * @see https://tailwindcss.com/docs/gradient-color-stops
       */
      "gradient-to-pos": [{
        to: fe()
      }],
      /**
       * Gradient Color Stops From
       * @see https://tailwindcss.com/docs/gradient-color-stops
       */
      "gradient-from": [{
        from: h()
      }],
      /**
       * Gradient Color Stops Via
       * @see https://tailwindcss.com/docs/gradient-color-stops
       */
      "gradient-via": [{
        via: h()
      }],
      /**
       * Gradient Color Stops To
       * @see https://tailwindcss.com/docs/gradient-color-stops
       */
      "gradient-to": [{
        to: h()
      }],
      // ---------------
      // --- Borders ---
      // ---------------
      /**
       * Border Radius
       * @see https://tailwindcss.com/docs/border-radius
       */
      rounded: [{
        rounded: A()
      }],
      /**
       * Border Radius Start
       * @see https://tailwindcss.com/docs/border-radius
       */
      "rounded-s": [{
        "rounded-s": A()
      }],
      /**
       * Border Radius End
       * @see https://tailwindcss.com/docs/border-radius
       */
      "rounded-e": [{
        "rounded-e": A()
      }],
      /**
       * Border Radius Top
       * @see https://tailwindcss.com/docs/border-radius
       */
      "rounded-t": [{
        "rounded-t": A()
      }],
      /**
       * Border Radius Right
       * @see https://tailwindcss.com/docs/border-radius
       */
      "rounded-r": [{
        "rounded-r": A()
      }],
      /**
       * Border Radius Bottom
       * @see https://tailwindcss.com/docs/border-radius
       */
      "rounded-b": [{
        "rounded-b": A()
      }],
      /**
       * Border Radius Left
       * @see https://tailwindcss.com/docs/border-radius
       */
      "rounded-l": [{
        "rounded-l": A()
      }],
      /**
       * Border Radius Start Start
       * @see https://tailwindcss.com/docs/border-radius
       */
      "rounded-ss": [{
        "rounded-ss": A()
      }],
      /**
       * Border Radius Start End
       * @see https://tailwindcss.com/docs/border-radius
       */
      "rounded-se": [{
        "rounded-se": A()
      }],
      /**
       * Border Radius End End
       * @see https://tailwindcss.com/docs/border-radius
       */
      "rounded-ee": [{
        "rounded-ee": A()
      }],
      /**
       * Border Radius End Start
       * @see https://tailwindcss.com/docs/border-radius
       */
      "rounded-es": [{
        "rounded-es": A()
      }],
      /**
       * Border Radius Top Left
       * @see https://tailwindcss.com/docs/border-radius
       */
      "rounded-tl": [{
        "rounded-tl": A()
      }],
      /**
       * Border Radius Top Right
       * @see https://tailwindcss.com/docs/border-radius
       */
      "rounded-tr": [{
        "rounded-tr": A()
      }],
      /**
       * Border Radius Bottom Right
       * @see https://tailwindcss.com/docs/border-radius
       */
      "rounded-br": [{
        "rounded-br": A()
      }],
      /**
       * Border Radius Bottom Left
       * @see https://tailwindcss.com/docs/border-radius
       */
      "rounded-bl": [{
        "rounded-bl": A()
      }],
      /**
       * Border Width
       * @see https://tailwindcss.com/docs/border-width
       */
      "border-w": [{
        border: F()
      }],
      /**
       * Border Width Inline
       * @see https://tailwindcss.com/docs/border-width
       */
      "border-w-x": [{
        "border-x": F()
      }],
      /**
       * Border Width Block
       * @see https://tailwindcss.com/docs/border-width
       */
      "border-w-y": [{
        "border-y": F()
      }],
      /**
       * Border Width Inline Start
       * @see https://tailwindcss.com/docs/border-width
       */
      "border-w-s": [{
        "border-s": F()
      }],
      /**
       * Border Width Inline End
       * @see https://tailwindcss.com/docs/border-width
       */
      "border-w-e": [{
        "border-e": F()
      }],
      /**
       * Border Width Block Start
       * @see https://tailwindcss.com/docs/border-width
       */
      "border-w-bs": [{
        "border-bs": F()
      }],
      /**
       * Border Width Block End
       * @see https://tailwindcss.com/docs/border-width
       */
      "border-w-be": [{
        "border-be": F()
      }],
      /**
       * Border Width Top
       * @see https://tailwindcss.com/docs/border-width
       */
      "border-w-t": [{
        "border-t": F()
      }],
      /**
       * Border Width Right
       * @see https://tailwindcss.com/docs/border-width
       */
      "border-w-r": [{
        "border-r": F()
      }],
      /**
       * Border Width Bottom
       * @see https://tailwindcss.com/docs/border-width
       */
      "border-w-b": [{
        "border-b": F()
      }],
      /**
       * Border Width Left
       * @see https://tailwindcss.com/docs/border-width
       */
      "border-w-l": [{
        "border-l": F()
      }],
      /**
       * Divide Width X
       * @see https://tailwindcss.com/docs/border-width#between-children
       */
      "divide-x": [{
        "divide-x": F()
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
        "divide-y": F()
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
        border: [...Z(), "hidden", "none"]
      }],
      /**
       * Divide Style
       * @see https://tailwindcss.com/docs/border-style#setting-the-divider-style
       */
      "divide-style": [{
        divide: [...Z(), "hidden", "none"]
      }],
      /**
       * Border Color
       * @see https://tailwindcss.com/docs/border-color
       */
      "border-color": [{
        border: h()
      }],
      /**
       * Border Color Inline
       * @see https://tailwindcss.com/docs/border-color
       */
      "border-color-x": [{
        "border-x": h()
      }],
      /**
       * Border Color Block
       * @see https://tailwindcss.com/docs/border-color
       */
      "border-color-y": [{
        "border-y": h()
      }],
      /**
       * Border Color Inline Start
       * @see https://tailwindcss.com/docs/border-color
       */
      "border-color-s": [{
        "border-s": h()
      }],
      /**
       * Border Color Inline End
       * @see https://tailwindcss.com/docs/border-color
       */
      "border-color-e": [{
        "border-e": h()
      }],
      /**
       * Border Color Block Start
       * @see https://tailwindcss.com/docs/border-color
       */
      "border-color-bs": [{
        "border-bs": h()
      }],
      /**
       * Border Color Block End
       * @see https://tailwindcss.com/docs/border-color
       */
      "border-color-be": [{
        "border-be": h()
      }],
      /**
       * Border Color Top
       * @see https://tailwindcss.com/docs/border-color
       */
      "border-color-t": [{
        "border-t": h()
      }],
      /**
       * Border Color Right
       * @see https://tailwindcss.com/docs/border-color
       */
      "border-color-r": [{
        "border-r": h()
      }],
      /**
       * Border Color Bottom
       * @see https://tailwindcss.com/docs/border-color
       */
      "border-color-b": [{
        "border-b": h()
      }],
      /**
       * Border Color Left
       * @see https://tailwindcss.com/docs/border-color
       */
      "border-color-l": [{
        "border-l": h()
      }],
      /**
       * Divide Color
       * @see https://tailwindcss.com/docs/divide-color
       */
      "divide-color": [{
        divide: h()
      }],
      /**
       * Outline Style
       * @see https://tailwindcss.com/docs/outline-style
       */
      "outline-style": [{
        outline: [...Z(), "none", "hidden"]
      }],
      /**
       * Outline Offset
       * @see https://tailwindcss.com/docs/outline-offset
       */
      "outline-offset": [{
        "outline-offset": [m, u, c]
      }],
      /**
       * Outline Width
       * @see https://tailwindcss.com/docs/outline-width
       */
      "outline-w": [{
        outline: ["", m, _, K]
      }],
      /**
       * Outline Color
       * @see https://tailwindcss.com/docs/outline-color
       */
      "outline-color": [{
        outline: h()
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
          p,
          ne,
          oe
        ]
      }],
      /**
       * Box Shadow Color
       * @see https://tailwindcss.com/docs/box-shadow#setting-the-shadow-color
       */
      "shadow-color": [{
        shadow: h()
      }],
      /**
       * Inset Box Shadow
       * @see https://tailwindcss.com/docs/box-shadow#adding-an-inset-shadow
       */
      "inset-shadow": [{
        "inset-shadow": ["none", w, ne, oe]
      }],
      /**
       * Inset Box Shadow Color
       * @see https://tailwindcss.com/docs/box-shadow#setting-the-inset-shadow-color
       */
      "inset-shadow-color": [{
        "inset-shadow": h()
      }],
      /**
       * Ring Width
       * @see https://tailwindcss.com/docs/box-shadow#adding-a-ring
       */
      "ring-w": [{
        ring: F()
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
        ring: h()
      }],
      /**
       * Ring Offset Width
       * @see https://v3.tailwindcss.com/docs/ring-offset-width
       * @deprecated since Tailwind CSS v4.0.0
       * @see https://github.com/tailwindlabs/tailwindcss/blob/v4.0.0/packages/tailwindcss/src/utilities.ts#L4158
       */
      "ring-offset-w": [{
        "ring-offset": [m, K]
      }],
      /**
       * Ring Offset Color
       * @see https://v3.tailwindcss.com/docs/ring-offset-color
       * @deprecated since Tailwind CSS v4.0.0
       * @see https://github.com/tailwindlabs/tailwindcss/blob/v4.0.0/packages/tailwindcss/src/utilities.ts#L4158
       */
      "ring-offset-color": [{
        "ring-offset": h()
      }],
      /**
       * Inset Ring Width
       * @see https://tailwindcss.com/docs/box-shadow#adding-an-inset-ring
       */
      "inset-ring-w": [{
        "inset-ring": F()
      }],
      /**
       * Inset Ring Color
       * @see https://tailwindcss.com/docs/box-shadow#setting-the-inset-ring-color
       */
      "inset-ring-color": [{
        "inset-ring": h()
      }],
      /**
       * Text Shadow
       * @see https://tailwindcss.com/docs/text-shadow
       */
      "text-shadow": [{
        "text-shadow": ["none", v, ne, oe]
      }],
      /**
       * Text Shadow Color
       * @see https://tailwindcss.com/docs/text-shadow#setting-the-shadow-color
       */
      "text-shadow-color": [{
        "text-shadow": h()
      }],
      /**
       * Opacity
       * @see https://tailwindcss.com/docs/opacity
       */
      opacity: [{
        opacity: [m, u, c]
      }],
      /**
       * Mix Blend Mode
       * @see https://tailwindcss.com/docs/mix-blend-mode
       */
      "mix-blend": [{
        "mix-blend": [...ze(), "plus-darker", "plus-lighter"]
      }],
      /**
       * Background Blend Mode
       * @see https://tailwindcss.com/docs/background-blend-mode
       */
      "bg-blend": [{
        "bg-blend": ze()
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
        "mask-linear": [m]
      }],
      "mask-image-linear-from-pos": [{
        "mask-linear-from": P()
      }],
      "mask-image-linear-to-pos": [{
        "mask-linear-to": P()
      }],
      "mask-image-linear-from-color": [{
        "mask-linear-from": h()
      }],
      "mask-image-linear-to-color": [{
        "mask-linear-to": h()
      }],
      "mask-image-t-from-pos": [{
        "mask-t-from": P()
      }],
      "mask-image-t-to-pos": [{
        "mask-t-to": P()
      }],
      "mask-image-t-from-color": [{
        "mask-t-from": h()
      }],
      "mask-image-t-to-color": [{
        "mask-t-to": h()
      }],
      "mask-image-r-from-pos": [{
        "mask-r-from": P()
      }],
      "mask-image-r-to-pos": [{
        "mask-r-to": P()
      }],
      "mask-image-r-from-color": [{
        "mask-r-from": h()
      }],
      "mask-image-r-to-color": [{
        "mask-r-to": h()
      }],
      "mask-image-b-from-pos": [{
        "mask-b-from": P()
      }],
      "mask-image-b-to-pos": [{
        "mask-b-to": P()
      }],
      "mask-image-b-from-color": [{
        "mask-b-from": h()
      }],
      "mask-image-b-to-color": [{
        "mask-b-to": h()
      }],
      "mask-image-l-from-pos": [{
        "mask-l-from": P()
      }],
      "mask-image-l-to-pos": [{
        "mask-l-to": P()
      }],
      "mask-image-l-from-color": [{
        "mask-l-from": h()
      }],
      "mask-image-l-to-color": [{
        "mask-l-to": h()
      }],
      "mask-image-x-from-pos": [{
        "mask-x-from": P()
      }],
      "mask-image-x-to-pos": [{
        "mask-x-to": P()
      }],
      "mask-image-x-from-color": [{
        "mask-x-from": h()
      }],
      "mask-image-x-to-color": [{
        "mask-x-to": h()
      }],
      "mask-image-y-from-pos": [{
        "mask-y-from": P()
      }],
      "mask-image-y-to-pos": [{
        "mask-y-to": P()
      }],
      "mask-image-y-from-color": [{
        "mask-y-from": h()
      }],
      "mask-image-y-to-color": [{
        "mask-y-to": h()
      }],
      "mask-image-radial": [{
        "mask-radial": [u, c]
      }],
      "mask-image-radial-from-pos": [{
        "mask-radial-from": P()
      }],
      "mask-image-radial-to-pos": [{
        "mask-radial-to": P()
      }],
      "mask-image-radial-from-color": [{
        "mask-radial-from": h()
      }],
      "mask-image-radial-to-color": [{
        "mask-radial-to": h()
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
        "mask-radial-at": I()
      }],
      "mask-image-conic-pos": [{
        "mask-conic": [m]
      }],
      "mask-image-conic-from-pos": [{
        "mask-conic-from": P()
      }],
      "mask-image-conic-to-pos": [{
        "mask-conic-to": P()
      }],
      "mask-image-conic-from-color": [{
        "mask-conic-from": h()
      }],
      "mask-image-conic-to-color": [{
        "mask-conic-to": h()
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
        mask: Me()
      }],
      /**
       * Mask Repeat
       * @see https://tailwindcss.com/docs/mask-repeat
       */
      "mask-repeat": [{
        mask: Re()
      }],
      /**
       * Mask Size
       * @see https://tailwindcss.com/docs/mask-size
       */
      "mask-size": [{
        mask: Te()
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
        mask: ["none", u, c]
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
          u,
          c
        ]
      }],
      /**
       * Blur
       * @see https://tailwindcss.com/docs/blur
       */
      blur: [{
        blur: Ie()
      }],
      /**
       * Brightness
       * @see https://tailwindcss.com/docs/brightness
       */
      brightness: [{
        brightness: [m, u, c]
      }],
      /**
       * Contrast
       * @see https://tailwindcss.com/docs/contrast
       */
      contrast: [{
        contrast: [m, u, c]
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
          k,
          ne,
          oe
        ]
      }],
      /**
       * Drop Shadow Color
       * @see https://tailwindcss.com/docs/filter-drop-shadow#setting-the-shadow-color
       */
      "drop-shadow-color": [{
        "drop-shadow": h()
      }],
      /**
       * Grayscale
       * @see https://tailwindcss.com/docs/grayscale
       */
      grayscale: [{
        grayscale: ["", m, u, c]
      }],
      /**
       * Hue Rotate
       * @see https://tailwindcss.com/docs/hue-rotate
       */
      "hue-rotate": [{
        "hue-rotate": [m, u, c]
      }],
      /**
       * Invert
       * @see https://tailwindcss.com/docs/invert
       */
      invert: [{
        invert: ["", m, u, c]
      }],
      /**
       * Saturate
       * @see https://tailwindcss.com/docs/saturate
       */
      saturate: [{
        saturate: [m, u, c]
      }],
      /**
       * Sepia
       * @see https://tailwindcss.com/docs/sepia
       */
      sepia: [{
        sepia: ["", m, u, c]
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
          u,
          c
        ]
      }],
      /**
       * Backdrop Blur
       * @see https://tailwindcss.com/docs/backdrop-blur
       */
      "backdrop-blur": [{
        "backdrop-blur": Ie()
      }],
      /**
       * Backdrop Brightness
       * @see https://tailwindcss.com/docs/backdrop-brightness
       */
      "backdrop-brightness": [{
        "backdrop-brightness": [m, u, c]
      }],
      /**
       * Backdrop Contrast
       * @see https://tailwindcss.com/docs/backdrop-contrast
       */
      "backdrop-contrast": [{
        "backdrop-contrast": [m, u, c]
      }],
      /**
       * Backdrop Grayscale
       * @see https://tailwindcss.com/docs/backdrop-grayscale
       */
      "backdrop-grayscale": [{
        "backdrop-grayscale": ["", m, u, c]
      }],
      /**
       * Backdrop Hue Rotate
       * @see https://tailwindcss.com/docs/backdrop-hue-rotate
       */
      "backdrop-hue-rotate": [{
        "backdrop-hue-rotate": [m, u, c]
      }],
      /**
       * Backdrop Invert
       * @see https://tailwindcss.com/docs/backdrop-invert
       */
      "backdrop-invert": [{
        "backdrop-invert": ["", m, u, c]
      }],
      /**
       * Backdrop Opacity
       * @see https://tailwindcss.com/docs/backdrop-opacity
       */
      "backdrop-opacity": [{
        "backdrop-opacity": [m, u, c]
      }],
      /**
       * Backdrop Saturate
       * @see https://tailwindcss.com/docs/backdrop-saturate
       */
      "backdrop-saturate": [{
        "backdrop-saturate": [m, u, c]
      }],
      /**
       * Backdrop Sepia
       * @see https://tailwindcss.com/docs/backdrop-sepia
       */
      "backdrop-sepia": [{
        "backdrop-sepia": ["", m, u, c]
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
        "border-spacing": d()
      }],
      /**
       * Border Spacing X
       * @see https://tailwindcss.com/docs/border-spacing
       */
      "border-spacing-x": [{
        "border-spacing-x": d()
      }],
      /**
       * Border Spacing Y
       * @see https://tailwindcss.com/docs/border-spacing
       */
      "border-spacing-y": [{
        "border-spacing-y": d()
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
        transition: ["", "all", "colors", "opacity", "shadow", "transform", "none", u, c]
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
        duration: [m, "initial", u, c]
      }],
      /**
       * Transition Timing Function
       * @see https://tailwindcss.com/docs/transition-timing-function
       */
      ease: [{
        ease: ["linear", "initial", S, u, c]
      }],
      /**
       * Transition Delay
       * @see https://tailwindcss.com/docs/transition-delay
       */
      delay: [{
        delay: [m, u, c]
      }],
      /**
       * Animation
       * @see https://tailwindcss.com/docs/animation
       */
      animate: [{
        animate: ["none", T, u, c]
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
        perspective: [b, u, c]
      }],
      /**
       * Perspective Origin
       * @see https://tailwindcss.com/docs/perspective-origin
       */
      "perspective-origin": [{
        "perspective-origin": E()
      }],
      /**
       * Rotate
       * @see https://tailwindcss.com/docs/rotate
       */
      rotate: [{
        rotate: ee()
      }],
      /**
       * Rotate X
       * @see https://tailwindcss.com/docs/rotate
       */
      "rotate-x": [{
        "rotate-x": ee()
      }],
      /**
       * Rotate Y
       * @see https://tailwindcss.com/docs/rotate
       */
      "rotate-y": [{
        "rotate-y": ee()
      }],
      /**
       * Rotate Z
       * @see https://tailwindcss.com/docs/rotate
       */
      "rotate-z": [{
        "rotate-z": ee()
      }],
      /**
       * Scale
       * @see https://tailwindcss.com/docs/scale
       */
      scale: [{
        scale: te()
      }],
      /**
       * Scale X
       * @see https://tailwindcss.com/docs/scale
       */
      "scale-x": [{
        "scale-x": te()
      }],
      /**
       * Scale Y
       * @see https://tailwindcss.com/docs/scale
       */
      "scale-y": [{
        "scale-y": te()
      }],
      /**
       * Scale Z
       * @see https://tailwindcss.com/docs/scale
       */
      "scale-z": [{
        "scale-z": te()
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
        skew: me()
      }],
      /**
       * Skew X
       * @see https://tailwindcss.com/docs/skew
       */
      "skew-x": [{
        "skew-x": me()
      }],
      /**
       * Skew Y
       * @see https://tailwindcss.com/docs/skew
       */
      "skew-y": [{
        "skew-y": me()
      }],
      /**
       * Transform
       * @see https://tailwindcss.com/docs/transform
       */
      transform: [{
        transform: [u, c, "", "none", "gpu", "cpu"]
      }],
      /**
       * Transform Origin
       * @see https://tailwindcss.com/docs/transform-origin
       */
      "transform-origin": [{
        origin: E()
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
        translate: re()
      }],
      /**
       * Translate X
       * @see https://tailwindcss.com/docs/translate
       */
      "translate-x": [{
        "translate-x": re()
      }],
      /**
       * Translate Y
       * @see https://tailwindcss.com/docs/translate
       */
      "translate-y": [{
        "translate-y": re()
      }],
      /**
       * Translate Z
       * @see https://tailwindcss.com/docs/translate
       */
      "translate-z": [{
        "translate-z": re()
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
        accent: h()
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
        caret: h()
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
        cursor: ["auto", "default", "pointer", "wait", "text", "move", "help", "not-allowed", "none", "context-menu", "progress", "cell", "crosshair", "vertical-text", "alias", "copy", "no-drop", "grab", "grabbing", "all-scroll", "col-resize", "row-resize", "n-resize", "e-resize", "s-resize", "w-resize", "ne-resize", "nw-resize", "se-resize", "sw-resize", "ew-resize", "ns-resize", "nesw-resize", "nwse-resize", "zoom-in", "zoom-out", u, c]
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
        "scroll-m": d()
      }],
      /**
       * Scroll Margin Inline
       * @see https://tailwindcss.com/docs/scroll-margin
       */
      "scroll-mx": [{
        "scroll-mx": d()
      }],
      /**
       * Scroll Margin Block
       * @see https://tailwindcss.com/docs/scroll-margin
       */
      "scroll-my": [{
        "scroll-my": d()
      }],
      /**
       * Scroll Margin Inline Start
       * @see https://tailwindcss.com/docs/scroll-margin
       */
      "scroll-ms": [{
        "scroll-ms": d()
      }],
      /**
       * Scroll Margin Inline End
       * @see https://tailwindcss.com/docs/scroll-margin
       */
      "scroll-me": [{
        "scroll-me": d()
      }],
      /**
       * Scroll Margin Block Start
       * @see https://tailwindcss.com/docs/scroll-margin
       */
      "scroll-mbs": [{
        "scroll-mbs": d()
      }],
      /**
       * Scroll Margin Block End
       * @see https://tailwindcss.com/docs/scroll-margin
       */
      "scroll-mbe": [{
        "scroll-mbe": d()
      }],
      /**
       * Scroll Margin Top
       * @see https://tailwindcss.com/docs/scroll-margin
       */
      "scroll-mt": [{
        "scroll-mt": d()
      }],
      /**
       * Scroll Margin Right
       * @see https://tailwindcss.com/docs/scroll-margin
       */
      "scroll-mr": [{
        "scroll-mr": d()
      }],
      /**
       * Scroll Margin Bottom
       * @see https://tailwindcss.com/docs/scroll-margin
       */
      "scroll-mb": [{
        "scroll-mb": d()
      }],
      /**
       * Scroll Margin Left
       * @see https://tailwindcss.com/docs/scroll-margin
       */
      "scroll-ml": [{
        "scroll-ml": d()
      }],
      /**
       * Scroll Padding
       * @see https://tailwindcss.com/docs/scroll-padding
       */
      "scroll-p": [{
        "scroll-p": d()
      }],
      /**
       * Scroll Padding Inline
       * @see https://tailwindcss.com/docs/scroll-padding
       */
      "scroll-px": [{
        "scroll-px": d()
      }],
      /**
       * Scroll Padding Block
       * @see https://tailwindcss.com/docs/scroll-padding
       */
      "scroll-py": [{
        "scroll-py": d()
      }],
      /**
       * Scroll Padding Inline Start
       * @see https://tailwindcss.com/docs/scroll-padding
       */
      "scroll-ps": [{
        "scroll-ps": d()
      }],
      /**
       * Scroll Padding Inline End
       * @see https://tailwindcss.com/docs/scroll-padding
       */
      "scroll-pe": [{
        "scroll-pe": d()
      }],
      /**
       * Scroll Padding Block Start
       * @see https://tailwindcss.com/docs/scroll-padding
       */
      "scroll-pbs": [{
        "scroll-pbs": d()
      }],
      /**
       * Scroll Padding Block End
       * @see https://tailwindcss.com/docs/scroll-padding
       */
      "scroll-pbe": [{
        "scroll-pbe": d()
      }],
      /**
       * Scroll Padding Top
       * @see https://tailwindcss.com/docs/scroll-padding
       */
      "scroll-pt": [{
        "scroll-pt": d()
      }],
      /**
       * Scroll Padding Right
       * @see https://tailwindcss.com/docs/scroll-padding
       */
      "scroll-pr": [{
        "scroll-pr": d()
      }],
      /**
       * Scroll Padding Bottom
       * @see https://tailwindcss.com/docs/scroll-padding
       */
      "scroll-pb": [{
        "scroll-pb": d()
      }],
      /**
       * Scroll Padding Left
       * @see https://tailwindcss.com/docs/scroll-padding
       */
      "scroll-pl": [{
        "scroll-pl": d()
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
        "will-change": ["auto", "scroll", "contents", "transform", u, c]
      }],
      // -----------
      // --- SVG ---
      // -----------
      /**
       * Fill
       * @see https://tailwindcss.com/docs/fill
       */
      fill: [{
        fill: ["none", ...h()]
      }],
      /**
       * Stroke Width
       * @see https://tailwindcss.com/docs/stroke-width
       */
      "stroke-w": [{
        stroke: [m, _, K, Ve]
      }],
      /**
       * Stroke
       * @see https://tailwindcss.com/docs/stroke
       */
      stroke: [{
        stroke: ["none", ...h()]
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
}, Qr = /* @__PURE__ */ br(Dr);
function He(...e) {
  return Qr($t(e));
}
function Nr() {
  return /* @__PURE__ */ $("div", { className: "glass-card rounded-xl p-6 border border-white/5 animate-pulse", children: [
    /* @__PURE__ */ $("div", { className: "flex items-center gap-3 mb-4", children: [
      /* @__PURE__ */ x("div", { className: "w-10 h-10 rounded-lg bg-slate-700/50" }),
      /* @__PURE__ */ x("div", { className: "h-4 w-24 rounded bg-slate-700/50" })
    ] }),
    /* @__PURE__ */ x("div", { className: "h-10 w-32 rounded bg-slate-700/50 mb-3" }),
    /* @__PURE__ */ x("div", { className: "h-3 w-20 rounded bg-slate-700/50" }),
    /* @__PURE__ */ $("div", { className: "mt-4 pt-4 border-t border-white/5 flex justify-between", children: [
      /* @__PURE__ */ x("div", { className: "h-4 w-28 rounded bg-slate-700/50" }),
      /* @__PURE__ */ x("div", { className: "h-4 w-16 rounded bg-slate-700/50" })
    ] })
  ] });
}
function Gr({ variant: e = "card", count: t = 1, className: r }) {
  const s = Array.from({ length: t }, (o, n) => n);
  return e === "card" ? /* @__PURE__ */ x("div", { className: He("grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4 gap-4", r), children: s.map((o) => /* @__PURE__ */ x(Nr, {}, o)) }) : /* @__PURE__ */ x("div", { className: He("space-y-3", r), children: s.map((o) => /* @__PURE__ */ x("div", { className: "h-4 rounded bg-slate-700/50 animate-pulse", style: { width: `${60 + Math.random() * 30}%` } }, o)) });
}
const Lr = new Wt({
  defaultOptions: { queries: { staleTime: 3e4, retry: 1 } }
}), Ur = {
  home: O(() => import("./Home-D6Pv4xyu.js")),
  records: O(() => import("./Records-BsOXBKXu.js")),
  leaderboards: O(() => import("./Leaderboards-2mUPlc7S.js")),
  maps: O(() => import("./Maps-BlJ2ZvoO.js")),
  "hall-of-fame": O(() => import("./HallOfFame-1cU1Z286.js")),
  awards: O(() => import("./Awards-BFmDnFpd.js")),
  sessions2: O(() => import("./Sessions2-BMmC7Moe.js")),
  profile: O(() => import("./Profile-BQ_hlrKh.js")),
  weapons: O(() => import("./Weapons-Cq-gGE8L.js")),
  "retro-viz": O(() => import("./RetroViz-DFZeB_fr.js")),
  "session-detail": O(() => import("./SessionDetail-C4FSrUgV.js")),
  uploads: O(() => import("./Uploads-D1oOOgUA.js")),
  "upload-detail": O(() => import("./UploadDetail-CVr30B3B.js")),
  greatshot: O(() => import("./Greatshot-CpOzC-8o.js")),
  "greatshot-demo": O(() => import("./GreatshotDemo-2mRTPtCf.js")),
  availability: O(() => import("./Availability-DxNUbg0s.js")),
  admin: O(() => import("./Admin-POSQf8W9.js")),
  proximity: O(() => import("./Proximity-7iTlLwTx.js"))
}, H = /* @__PURE__ */ new WeakMap();
function Kr({ viewId: e, params: t }) {
  const r = Ur[e];
  return r ? /* @__PURE__ */ x(Ht, { viewId: e, children: /* @__PURE__ */ x(_t, { client: Lr, children: /* @__PURE__ */ x(vt, { fallback: /* @__PURE__ */ x(Gr, { variant: "card", count: 4 }), children: /* @__PURE__ */ x(r, { params: t }) }) }) }) : /* @__PURE__ */ x("div", { className: "text-slate-400 text-center py-12", children: "Not yet migrated." });
}
async function Yr(e, t) {
  const r = H.get(e);
  r && (r.unmount(), H.delete(e));
  const s = gt(e);
  return s.render(/* @__PURE__ */ x(Kr, { viewId: t.viewId, params: t.params })), H.set(e, s), {
    unmount() {
      const o = H.get(e);
      o && (o.unmount(), H.delete(e));
    }
  };
}
export {
  Gr as S,
  le as a,
  ge as b,
  He as c,
  St as d,
  be as e,
  Je as f,
  Gt as g,
  Mt as h,
  ce as i,
  M as j,
  Hr as k,
  Yr as m,
  q as n,
  Et as p,
  Ot as r,
  _r as s,
  Pt as t,
  $r as u
};
