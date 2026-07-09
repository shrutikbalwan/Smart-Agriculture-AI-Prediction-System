const SettingsPage = {
  initialized: false,

  init() {
    if (this.initialized) return;
    this.initialized = true;

    this.bindEvents();
    this.loadSettings();
  },

  bindEvents() {
    document.getElementById('settingsSaveBtn')?.addEventListener('click', () => this.saveSettings());
    document.getElementById('settingsCancelBtn')?.addEventListener('click', () => this.loadSettings());
    document.getElementById('testApiConnection')?.addEventListener('click', () => this.testApiConnection());
    document.getElementById('toggleOwmKey')?.addEventListener('click', () => {
      const input = document.getElementById('settingOwmKey');
      if (input) input.type = input.type === 'password' ? 'text' : 'password';
    });
    document.getElementById('testOwmConnection')?.addEventListener('click', () => this.testOwmConnection());
    document.getElementById('exportSettingsBtn')?.addEventListener('click', () => this.exportSettings());
    document.getElementById('importSettingsBtn')?.addEventListener('click', () => document.getElementById('importSettingsFile')?.click());
    document.getElementById('importSettingsFile')?.addEventListener('change', (e) => this.importSettings(e));
    document.getElementById('clearHistoryBtn')?.addEventListener('click', () => this.clearLocalHistory());
    document.getElementById('resetSettingsBtn')?.addEventListener('click', () => this.resetAllSettings());
  },

  getRadioValue(name) {
    const checked = document.querySelector(`input[name="${name}"]:checked`);
    return checked ? checked.value : null;
  },

  setRadioValue(name, value) {
    const radio = document.querySelector(`input[name="${name}"][value="${value}"]`);
    if (radio) radio.checked = true;
  },

  getValue(id, fallback = '') {
    const el = document.getElementById(id);
    if (!el) return fallback;
    if (el.type === 'checkbox') return el.checked;
    return el.value;
  },

  setValue(id, value) {
    const el = document.getElementById(id);
    if (!el) return;
    if (el.type === 'checkbox') el.checked = !!value;
    else el.value = value;
  },

  loadSettings() {
    const saved = JSON.parse(localStorage.getItem('agrisense_settings') || '{}');

    this.setRadioValue('theme', saved.theme || 'light');
    this.setRadioValue('units', saved.units || 'metric');
    this.setRadioValue('timeFormat', saved.timeFormat || '24');
    this.setValue('settingLanguage', saved.language || 'en');
    this.setValue('settingDateFormat', saved.dateFormat || 'YYYY-MM-DD');
    this.setValue('settingNotifyEnabled', saved.notificationsEnabled ?? true);
    this.setValue('settingNotifyHeat', saved.notifyHeat ?? true);
    this.setValue('settingNotifyRain', saved.notifyRain ?? true);
    this.setValue('settingNotifyDisease', saved.notifyDisease ?? true);
    this.setValue('settingNotifySoil', saved.notifySoil ?? true);
    this.setValue('settingNotifyIrrigation', saved.notifyIrrigation ?? true);
    this.setValue('settingNotifyYield', saved.notifyYield ?? true);
    this.setValue('settingNotifyEmail', saved.notifyEmail ?? false);
    this.setValue('settingNotifyPush', saved.notifyPush ?? false);
    this.setValue('settingApiUrl', saved.apiUrl || 'http://127.0.0.1:5000');
    this.setValue('settingOwmKey', saved.owmKey || '');
    this.setValue('settingApiTimeout', saved.apiTimeout || 30);
    this.setValue('settingApiCache', saved.apiCache ?? true);
    this.setValue('settingDataSync', saved.dataSync ?? true);
    this.setValue('settingDataLocalStorage', saved.dataLocalStorage ?? true);
    this.setValue('settingDataAnalytics', saved.dataAnalytics ?? false);
    this.setValue('settingHistoryRetention', saved.historyRetention || 90);
    this.setValue('settingDevMode', saved.devMode ?? false);
    this.setValue('settingAnimations', saved.animations ?? true);
    this.setValue('settingReducedMotion', saved.reducedMotion ?? false);
    this.setValue('settingLogLevel', saved.logLevel || 'info');
    this.setValue('settingRefreshInterval', saved.refreshInterval || 0);

    window.OPENWEATHERMAP_API_KEY = saved.owmKey || window.OPENWEATHERMAP_API_KEY;
    if (window.WeatherWidget) window.WeatherWidget.syncApiKey();
  },

  saveSettings() {
    const settings = {
      theme: this.getRadioValue('theme') || 'light',
      language: this.getValue('settingLanguage', 'en'),
      units: this.getRadioValue('units') || 'metric',
      dateFormat: this.getValue('settingDateFormat', 'YYYY-MM-DD'),
      timeFormat: this.getRadioValue('timeFormat') || '24',
      notificationsEnabled: this.getValue('settingNotifyEnabled', true),
      notifyHeat: this.getValue('settingNotifyHeat', true),
      notifyRain: this.getValue('settingNotifyRain', true),
      notifyDisease: this.getValue('settingNotifyDisease', true),
      notifySoil: this.getValue('settingNotifySoil', true),
      notifyIrrigation: this.getValue('settingNotifyIrrigation', true),
      notifyYield: this.getValue('settingNotifyYield', true),
      notifyEmail: this.getValue('settingNotifyEmail', false),
      notifyPush: this.getValue('settingNotifyPush', false),
      apiUrl: this.getValue('settingApiUrl', 'http://127.0.0.1:5000'),
      owmKey: this.getValue('settingOwmKey', ''),
      apiTimeout: parseInt(this.getValue('settingApiTimeout', 30)),
      apiCache: this.getValue('settingApiCache', true),
      dataSync: this.getValue('settingDataSync', true),
      dataLocalStorage: this.getValue('settingDataLocalStorage', true),
      dataAnalytics: this.getValue('settingDataAnalytics', false),
      historyRetention: parseInt(this.getValue('settingHistoryRetention', 90)),
      devMode: this.getValue('settingDevMode', false),
      animations: this.getValue('settingAnimations', true),
      reducedMotion: this.getValue('settingReducedMotion', false),
      logLevel: this.getValue('settingLogLevel', 'info'),
      refreshInterval: parseInt(this.getValue('settingRefreshInterval', 0)),
    };

    localStorage.setItem('agrisense_settings', JSON.stringify(settings));

    if (settings.theme === 'dark') ThemeManager.setDark();
    else if (settings.theme === 'light') ThemeManager.setLight();
    else {
      const prefers = window.matchMedia('(prefers-color-scheme: dark)').matches;
      if (prefers) ThemeManager.setDark();
      else ThemeManager.setLight();
    }

    window.OPENWEATHERMAP_API_KEY = settings.owmKey;

    this.showToast('Settings saved successfully', 'success');
  },

  async testApiConnection() {
    const statusEl = document.getElementById('apiConnectionStatus');
    if (!statusEl) return;
    const url = this.getValue('settingApiUrl', 'http://127.0.0.1:5000');
    statusEl.hidden = false;
    statusEl.className = 'settings-status loading';
    statusEl.innerHTML = '<i class="fas fa-spinner fa-spin"></i> Testing connection...';

    try {
      const response = await fetch(`${url}/api/health`, { signal: AbortSignal.timeout(5000) });
      if (!response.ok) throw new Error('Connection failed');
      statusEl.className = 'settings-status success';
      statusEl.innerHTML = '<i class="fas fa-check-circle"></i> Connection successful';
    } catch {
      statusEl.className = 'settings-status error';
      statusEl.innerHTML = '<i class="fas fa-times-circle"></i> Cannot reach server';
    }

    setTimeout(() => { statusEl.hidden = true; }, 4000);
  },

  async testOwmConnection() {
    const statusEl = document.getElementById('owmConnectionStatus');
    if (!statusEl) return;
    const key = this.getValue('settingOwmKey', '');
    if (!key) {
      statusEl.hidden = false;
      statusEl.className = 'settings-status error';
      statusEl.innerHTML = '<i class="fas fa-times-circle"></i> Enter an API key first';
      setTimeout(() => { statusEl.hidden = true; }, 3000);
      return;
    }

    statusEl.hidden = false;
    statusEl.className = 'settings-status loading';
    statusEl.innerHTML = '<i class="fas fa-spinner fa-spin"></i> Testing API key...';

    try {
      const response = await fetch(`https://api.openweathermap.org/data/2.5/weather?q=London&appid=${key}&units=metric`, { signal: AbortSignal.timeout(5000) });
      if (!response.ok) throw new Error('Invalid key');
      statusEl.className = 'settings-status success';
      statusEl.innerHTML = '<i class="fas fa-check-circle"></i> API key is valid';
    } catch {
      statusEl.className = 'settings-status error';
      statusEl.innerHTML = '<i class="fas fa-times-circle"></i> Invalid API key';
    }

    setTimeout(() => { statusEl.hidden = true; }, 4000);
  },

  exportSettings() {
    const settings = localStorage.getItem('agrisense_settings') || '{}';
    const blob = new Blob([settings], { type: 'application/json' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = `agrisense-settings-${new Date().toISOString().slice(0, 10)}.json`;
    document.body.appendChild(a);
    a.click();
    document.body.removeChild(a);
    URL.revokeObjectURL(url);
    this.showToast('Settings exported', 'success');
  },

  importSettings(e) {
    const file = e.target.files?.[0];
    if (!file) return;
    const reader = new FileReader();
    reader.onload = (event) => {
      try {
        JSON.parse(event.target.result);
        localStorage.setItem('agrisense_settings', event.target.result);
        this.loadSettings();
        this.showToast('Settings imported successfully', 'success');
      } catch {
        this.showToast('Invalid settings file', 'error');
      }
    };
    reader.readAsText(file);
    e.target.value = '';
  },

  clearLocalHistory() {
    if (!confirm('Clear all local history data? This cannot be undone.')) return;
    localStorage.removeItem('predictionHistory');
    this.showToast('Local history cleared', 'info');
  },

  resetAllSettings() {
    if (!confirm('Reset all settings to defaults? This cannot be undone.')) return;
    localStorage.removeItem('agrisense_settings');
    this.loadSettings();
    this.showToast('Settings reset to defaults', 'info');
  },

  showToast(message, type = 'success') {
    const container = document.getElementById('settingsToastContainer');
    if (!container) return;

    const toast = document.createElement('div');
    toast.className = `settings-toast ${type}`;
    const icons = { success: 'fa-check-circle', error: 'fa-times-circle', warning: 'fa-exclamation-triangle', info: 'fa-info-circle' };
    toast.innerHTML = `
      <i class="fas ${icons[type] || icons.info}"></i>
      <div class="settings-toast-content">
        <span class="settings-toast-title">${message}</span>
      </div>
      <button class="settings-toast-close" onclick="this.parentElement.remove()"><i class="fas fa-times"></i></button>
    `;
    container.appendChild(toast);

    setTimeout(() => {
      toast.style.transition = 'all 0.35s cubic-bezier(0.5, 0, 0.5, 1)';
      toast.style.transform = 'translateX(120%)';
      toast.style.opacity = '0';
      setTimeout(() => toast.remove(), 350);
    }, 3500);
  },
};

if (document.readyState === 'loading') {
  document.addEventListener('DOMContentLoaded', () => SettingsPage.init());
} else {
  SettingsPage.init();
}
