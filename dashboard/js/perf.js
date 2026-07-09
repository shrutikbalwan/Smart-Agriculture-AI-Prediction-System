/* ============================================
   Smart Agriculture Dashboard - Performance Utils
   Memoization, RAF batching, lazy loading, debounce
   ============================================ */

const Perf = {
  _rafQueue: new Map(),
  _rafId: null,
  _memoStore: new WeakMap(),
  _lazyObservers: [],
  _idleCallbacks: [],

  memoize(fn, resolver = (...args) => args.join('|')) {
    const cache = new Map();
    return (...args) => {
      const key = resolver(...args);
      if (cache.has(key)) return cache.get(key);
      const result = fn(...args);
      cache.set(key, result);
      return result;
    };
  },

  memoizeAsync(fn, resolver = (...args) => args.join('|'), ttl = 5000) {
    const cache = new Map();
    return async (...args) => {
      const key = resolver(...args);
      const entry = cache.get(key);
      if (entry && Date.now() - entry.time < ttl) return entry.data;
      const result = await fn(...args);
      cache.set(key, { data: result, time: Date.now() });
      return result;
    };
  },

  batchDOM(callback, key = '_default') {
    if (this._rafQueue.has(key)) return;
    this._rafQueue.set(key, callback);
    if (!this._rafId) {
      this._rafId = requestAnimationFrame(() => {
        const id = this._rafId;
        this._rafId = null;
        for (const [k, cb] of this._rafQueue) {
          try { cb(); } catch (e) { console.warn('RAF batch error:', k, e); }
        }
        this._rafQueue.clear();
      });
    }
  },

  cancelBatch(key) {
    this._rafQueue.delete(key);
    if (this._rafQueue.size === 0 && this._rafId) {
      cancelAnimationFrame(this._rafId);
      this._rafId = null;
    }
  },

  debounce(fn, wait = 200) {
    let timer;
    const debounced = (...args) => {
      clearTimeout(timer);
      timer = setTimeout(() => fn(...args), wait);
    };
    debounced.cancel = () => { clearTimeout(timer); };
    return debounced;
  },

  throttle(fn, limit = 100) {
    let inThrottle = false;
    let lastArgs = null;
    return (...args) => {
      if (inThrottle) { lastArgs = args; return; }
      inThrottle = true;
      fn(...args);
      setTimeout(() => {
        inThrottle = false;
        if (lastArgs) { fn(...lastArgs); lastArgs = null; }
      }, limit);
    };
  },

  lazyRender(element, renderFn, options = {}) {
    const { rootMargin = '100px', once = true } = options;
    if ('IntersectionObserver' in window) {
      const observer = new IntersectionObserver((entries) => {
        entries.forEach(entry => {
          if (entry.isIntersecting) {
            renderFn(element);
            if (once) observer.unobserve(element);
          }
        });
      }, { rootMargin });
      observer.observe(element);
      this._lazyObservers.push(observer);
      return observer;
    }
    renderFn(element);
    return null;
  },

  lazyLoadScript(src) {
    return new Promise((resolve, reject) => {
      if (document.querySelector(`script[src="${src}"]`)) { resolve(); return; }
      const script = document.createElement('script');
      script.src = src;
      script.async = true;
      script.onload = () => resolve();
      script.onerror = () => reject(new Error(`Failed to load: ${src}`));
      document.body.appendChild(script);
    });
  },

  scheduleIdle(callback, timeout = 2000) {
    if ('requestIdleCallback' in window) {
      return requestIdleCallback(callback, { timeout });
    }
    const id = setTimeout(callback, 1);
    this._idleCallbacks.push(id);
    return id;
  },

  cancelIdle(id) {
    if ('cancelIdleCallback' in window) cancelIdleCallback(id);
    else clearTimeout(id);
  },

  destroy() {
    this._lazyObservers.forEach(o => o.disconnect());
    this._lazyObservers = [];
    this._idleCallbacks.forEach(id => this.cancelIdle(id));
    this._idleCallbacks = [];
    if (this._rafId) cancelAnimationFrame(this._rafId);
    this._rafQueue.clear();
  },
};
