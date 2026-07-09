/* ============================================
   Smart Agriculture Dashboard - API Layer
   with response caching & stale-while-revalidate
   ============================================ */

const API_URL = "http://127.0.0.1:5000";

const APICache = {
  _store: new Map(),
  _defaultTTL: 30000,

  get(key) {
    const entry = this._store.get(key);
    if (!entry) return null;
    const now = Date.now();
    if (now < entry.expiry) return entry.data;
    if (entry.refresh && now < entry.stale) {
      entry.refresh();
      return entry.data;
    }
    this._store.delete(key);
    return null;
  },

  set(key, data, ttl) {
    const duration = ttl || this._defaultTTL;
    const expiry = Date.now() + duration;
    this._store.set(key, { data, expiry, stale: expiry + duration * 3 });
  },

  async fetch(key, fetcher, ttl) {
    const cached = this.get(key);
    if (cached !== null) return cached;

    const data = await fetcher();
    this.set(key, data, ttl);

    this._store.get(key).refresh = async () => {
      try {
        const fresh = await fetcher();
        this.set(key, fresh, ttl);
      } catch {}
    };

    return data;
  },

  invalidate(pattern) {
    if (!pattern) { this._store.clear(); return; }
    for (const key of this._store.keys()) {
      if (key.startsWith(pattern)) this._store.delete(key);
    }
  },
};

const API = {
    async predictFarm(data) {
        try {
            const response = await fetch(`${API_URL}/predict`, {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify(data)
            });
            if (!response.ok) throw new Error(`Server Error : ${response.status}`);
            APICache.invalidate('dashboard');
            APICache.invalidate('history');
            return await response.json();
        } catch (error) {
            console.error("Prediction Error :", error);
            return { success: false, error: error.message };
        }
    },

    async getDashboardStats() {
        return APICache.fetch('dashboard:stats', async () => {
            const response = await fetch(`${API_URL}/dashboard/stats`);
            if (!response.ok) throw new Error(`Server Error : ${response.status}`);
            return response.json();
        }, 15000);
    },

    async getPredictionHistory(params = {}) {
        const query = new URLSearchParams();
        Object.entries(params).forEach(([key, value]) => {
            if (value !== undefined && value !== null && String(value).trim() !== '') {
                query.set(key, value);
            }
        });
        const cacheKey = `history:${query.toString()}`;
        return APICache.fetch(cacheKey, async () => {
            const response = await fetch(`${API_URL}/history?${query.toString()}`);
            if (!response.ok) throw new Error(`Server Error : ${response.status}`);
            return response.json();
        }, 10000);
    },

    async getPredictionHistoryMeta() {
        return APICache.fetch('history:meta', async () => {
            const response = await fetch(`${API_URL}/history/meta`);
            if (!response.ok) throw new Error(`Server Error : ${response.status}`);
            return response.json();
        }, 60000);
    },

    async deletePredictionHistoryEntry(id) {
        try {
            const response = await fetch(`${API_URL}/history/${id}`, { method: "DELETE" });
            if (!response.ok) throw new Error(`Server Error : ${response.status}`);
            APICache.invalidate('history');
            APICache.invalidate('dashboard');
            return await response.json();
        } catch (error) {
            console.error("History Delete Error :", error);
            return { success: false, error: error.message };
        }
    },
};
