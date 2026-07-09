/* ============================================
   Smart Agriculture Dashboard - Main App
   ============================================ */

const App = {
    initialized: false,
    predictionHistory: [],

    init() {
        if (this.initialized) return;
        this.initialized = true;

        ThemeManager.init();
        Sidebar.init();
        WeatherWidget.init();

        Perf.scheduleIdle(() => {
            Charts.init();
            if (typeof PredictionHistoryModule !== 'undefined') PredictionHistoryModule.init();
            if (typeof NotificationService !== 'undefined') NotificationService.init();
            if (typeof SettingsPage !== 'undefined') SettingsPage.init();
        }, 500);

        this.setupEventListeners();

        Perf.scheduleIdle(() => {
            this.loadDashboardData();
            Sidebar.highlightCurrent();
        }, 200);

        console.log('AgriSense Dashboard initialized successfully');
    },

    setupEventListeners() {
        document.getElementById('refreshBtn')?.addEventListener('click', () => this.refreshDashboard());
        document.getElementById('exportBtn')?.addEventListener('click', () => this.exportData());
        document.getElementById('notificationsBtn')?.addEventListener('click', () => this.toggleNotifications());
        document.getElementById('notificationsClose')?.addEventListener('click', () => this.toggleNotifications(false));

        document.addEventListener('keydown', (e) => {
            if ((e.ctrlKey || e.metaKey) && e.key === 'r') {
                e.preventDefault();
                this.refreshDashboard();
            }
        });

        const observer = new MutationObserver(() => Charts.refreshTheme());
        observer.observe(document.documentElement, {
            attributes: true,
            attributeFilter: ['data-theme'],
        });

        document.getElementById('predictBtn')?.addEventListener('click', () => this.handlePrediction());
        document.getElementById('resetFormBtn')?.addEventListener('click', () => this.resetForm());

        document.getElementById('profileAvatar')?.addEventListener('click', (e) => {
            e.stopPropagation();
            const menu = document.getElementById('profileMenu');
            menu?.classList.toggle('open');
        });
        document.addEventListener('click', () => {
            document.getElementById('profileMenu')?.classList.remove('open');
        });
        document.querySelectorAll('[data-action="settings"]').forEach(el => {
            el.addEventListener('click', (e) => {
                e.preventDefault();
                const page = document.getElementById('page-settings');
                if (page) {
                    document.querySelectorAll('.page').forEach(p => p.classList.remove('active'));
                    page.classList.add('active');
                    document.querySelectorAll('.nav-link').forEach(l => l.classList.remove('active'));
                    document.querySelector('[data-page="settings"]')?.classList.add('active');
                    history.pushState(null, '', '#settings');
                }
            });
        });
    },

    async loadDashboardData() {
        try {
            const response = await API.getDashboardStats();
            if (response && response.success && response.stats) {
                this.updateStats(response.stats);
            } else {
                this.clearStats();
            }
        } catch (error) {
            console.error('Failed to load dashboard stats:', error);
            this.clearStats();
        }
    },

    updateStats(stats) {
        Perf.batchDOM(() => {
            this.animateValue('yieldValue', stats.average_yield, 800, 't/ha');
            this.animateValue('irrigationValue', stats.average_irrigation, 800, '%');
            this.animateValue('soilHealthValue', stats.average_soil_health, 800, '%');
            this.animateValue('efficiencyValue', stats.average_farm_efficiency, 800, '%');
            this.animateValue('heatStressValue', stats.average_heat_stress, 800, '%');
            this.animateValue('rainImpactValue', stats.average_rain_impact, 800, '%');
        }, 'statsUpdate');
    },

    clearStats() {
        ['yieldValue', 'irrigationValue', 'soilHealthValue', 'efficiencyValue', 'heatStressValue', 'rainImpactValue'].forEach((id) => {
            const el = document.getElementById(id);
            if (el) el.textContent = '--';
        });
    },

    animateValue(elementId, targetValue, duration = 800, suffix = '') {
        const element = document.getElementById(elementId);
        if (!element) return;

        const numericTarget = Number(targetValue);
        if (!Number.isFinite(numericTarget)) {
            element.textContent = '--';
            return;
        }

        if (element._animFrameId) {
            cancelAnimationFrame(element._animFrameId);
        }

        const startValue = 0;
        const startTime = performance.now();
        const isDecimal = numericTarget % 1 !== 0;
        const finalText = isDecimal
            ? `${numericTarget.toFixed(1)}${suffix}`
            : `${Math.round(numericTarget)}${suffix}`;

        const animate = (currentTime) => {
            const elapsed = currentTime - startTime;
            const progress = Math.min(elapsed / duration, 1);
            const eased = 1 - Math.pow(1 - progress, 3);
            const currentValue = startValue + (numericTarget - startValue) * eased;

            element.textContent = isDecimal
                ? `${currentValue.toFixed(1)}${suffix}`
                : `${Math.round(currentValue)}${suffix}`;

            if (progress < 1) {
                element._animFrameId = requestAnimationFrame(animate);
            } else {
                element._animFrameId = null;
                element.textContent = finalText;
            }
        };

        element._animFrameId = requestAnimationFrame(animate);
    },

    async refreshDashboard() {
        const btn = document.getElementById('refreshBtn');
        const icon = btn?.querySelector('i');

        if (icon) {
            icon.style.animation = 'none';
            icon.offsetHeight;
            icon.style.animation = 'spin 0.6s linear';
        }

        await Promise.all([
            this.loadDashboardData(),
            WeatherWidget.refresh(WeatherWidget.defaultLocation),
        ]);

        if (icon) {
            setTimeout(() => {
                icon.style.animation = '';
            }, 600);
        }
    },

    getPredictionValue(prediction, keys, fallback = '--') {
        if (!prediction) return fallback;
        for (const key of keys) {
            const value = prediction[key];
            if (value !== undefined && value !== null && value !== '') {
                return value;
            }
        }
        return fallback;
    },

    setTextContent(elementId, value) {
        const element = document.getElementById(elementId);
        if (element) element.textContent = value;
    },

    validateForm(data) {
        const errors = [];
        this.clearFieldErrors();

        const checks = [
            { field: 'region', test: !data.region, msg: 'Region is required' },
            { field: 'crop_type', test: !data.crop_type, msg: 'Crop is required' },
            { field: 'soil_moisture', test: isNaN(data['soil_moisture_%']) || data['soil_moisture_%'] < 0 || data['soil_moisture_%'] > 100, msg: 'Must be 0-100' },
            { field: 'soil_pH', test: isNaN(data.soil_pH) || data.soil_pH < 0 || data.soil_pH > 14, msg: 'Must be 0-14' },
            { field: 'temperature_C', test: isNaN(data.temperature_C), msg: 'Temperature is required' },
            { field: 'rainfall_mm', test: isNaN(data.rainfall_mm) || data.rainfall_mm < 0, msg: 'Must be >= 0' },
            { field: 'humidity', test: isNaN(data['humidity_%']) || data['humidity_%'] < 0 || data['humidity_%'] > 100, msg: 'Must be 0-100' },
            { field: 'sunlight_hours', test: isNaN(data.sunlight_hours) || data.sunlight_hours < 0, msg: 'Must be >= 0' },
            { field: 'irrigation_type', test: !data.irrigation_type, msg: 'Irrigation type is required' },
            { field: 'fertilizer_type', test: !data.fertilizer_type, msg: 'Fertilizer type is required' },
            { field: 'pesticide_usage_ml', test: isNaN(data.pesticide_usage_ml) || data.pesticide_usage_ml < 0, msg: 'Must be >= 0' },
            { field: 'total_days', test: isNaN(data.total_days) || data.total_days < 1, msg: 'Must be >= 1' },
            { field: 'latitude', test: isNaN(data.latitude) || data.latitude < -90 || data.latitude > 90, msg: 'Must be -90 to 90' },
            { field: 'longitude', test: isNaN(data.longitude) || data.longitude < -180 || data.longitude > 180, msg: 'Must be -180 to 180' },
            { field: 'NDVI_index', test: isNaN(data.NDVI_index) || data.NDVI_index < 0 || data.NDVI_index > 1, msg: 'Must be 0-1' },
        ];

        for (const check of checks) {
            if (check.test) {
                errors.push(check.msg);
                this.showFieldError(check.field, check.msg);
            }
        }

        return errors;
    },

    clearFieldErrors() {
        document.querySelectorAll('.field-error').forEach(el => {
            el.classList.remove('visible');
            el.textContent = '';
        });
        document.querySelectorAll('.input-error').forEach(el => {
            el.classList.remove('input-error');
        });
    },

    showFieldError(fieldId, message) {
        const errorEl = document.getElementById(`err-${fieldId}`);
        if (errorEl) {
            errorEl.textContent = message;
            errorEl.classList.add('visible');
        }
        const inputIdMap = { humidity: 'humidity_%', soil_moisture: 'soil_moisture_%', soil_pH: 'soil_pH', temperature_C: 'temperature_C', rainfall_mm: 'rainfall_mm', sunlight_hours: 'sunlight_hours', pesticide_usage_ml: 'pesticide_usage_ml', total_days: 'total_days', NDVI_index: 'NDVI_index' };
        const input = document.getElementById(inputIdMap[fieldId] || fieldId);
        if (input) input.classList.add('input-error');
    },

    updateResultsBadge(state, message) {
        const badge = document.getElementById('resultsBadge');
        if (!badge) return;
        badge.className = 'results-badge';
        if (state) badge.classList.add(state);
        badge.textContent = message || 'Ready';
    },

    resetForm() {
        document.querySelectorAll('.prediction-grid input, .prediction-grid select').forEach(el => {
            if (el.tagName === 'SELECT') el.selectedIndex = 0;
            else el.value = '';
        });
        document.querySelectorAll('#cropResult, #yieldResult, #diseaseResult, #irrigationResult, #fertilizerResult, #heatResult, #soilResult, #rainResult, #farmResult, #timeResult').forEach(el => {
            el.textContent = '--';
        });
        this.clearFieldErrors();
        this.updateResultsBadge('', 'Ready');
    },

    collectFormData() {
        return {
            region: document.getElementById('region').value,
            crop_type: document.getElementById('crop_type').value,
            'soil_moisture_%': parseFloat(document.getElementById('soil_moisture_%').value),
            soil_pH: parseFloat(document.getElementById('soil_pH').value),
            temperature_C: parseFloat(document.getElementById('temperature_C').value),
            rainfall_mm: parseFloat(document.getElementById('rainfall_mm').value),
            'humidity_%': parseFloat(document.getElementById('humidity_%').value),
            sunlight_hours: parseFloat(document.getElementById('sunlight_hours').value),
            irrigation_type: document.getElementById('irrigation_type').value,
            fertilizer_type: document.getElementById('fertilizer_type').value,
            pesticide_usage_ml: parseFloat(document.getElementById('pesticide_usage_ml').value),
            total_days: parseInt(document.getElementById('total_days').value),
            latitude: parseFloat(document.getElementById('latitude').value),
            longitude: parseFloat(document.getElementById('longitude').value),
            NDVI_index: parseFloat(document.getElementById('NDVI_index').value),
        };
    },

    updatePredictionResults(prediction) {
        const safePrediction = prediction || {};

        const maps = [
            { id: 'cropResult', keys: ['CropRecommendation', 'crop_recommendation'] },
            { id: 'yieldResult', keys: ['PredictedYield(Kg/Hectare)', 'predicted_yield'], suffix: ' kg/ha' },
            { id: 'diseaseResult', keys: ['Disease', 'disease_prediction'] },
            { id: 'irrigationResult', keys: ['Irrigation', 'irrigation'] },
            { id: 'fertilizerResult', keys: ['Fertilizer', 'fertilizer_recommendation', 'Recommended_Fertilizer'] },
            { id: 'heatResult', keys: ['HeatStress', 'heat_stress'] },
            { id: 'soilResult', keys: ['SoilHealth', 'soil_health'] },
            { id: 'rainResult', keys: ['RainImpact', 'rain_impact'] },
            { id: 'farmResult', keys: ['FarmEfficiency', 'farm_efficiency'] },
            { id: 'timeResult', keys: ['IrrigationTime', 'irrigation_time'] },
        ];

        Perf.batchDOM(() => {
            for (const { id, keys, suffix } of maps) {
                const value = this.getPredictionValue(safePrediction, keys);
                this.setTextContent(id, value === '--' ? '--' : suffix ? `${value}${suffix}` : value);
            }
        }, 'predictionResults');
    },

    async _postPredictionTasks(result, formData) {
        if (typeof NotificationService !== 'undefined') {
            NotificationService.checkPredictionAlerts(result.prediction, formData.region);
        }
        try {
            if (typeof Charts.refreshTrendCharts === 'function') {
                await Charts.refreshTrendCharts();
            }
        } catch (e) { console.warn('Chart refresh skipped:', e); }
        await this.loadDashboardData();
    },

    async handlePrediction() {
        const predictBtn = document.getElementById('predictBtn');
        if (!predictBtn) return;

        const formData = this.collectFormData();
        const errors = this.validateForm(formData);
        if (errors.length > 0) {
            this.updateResultsBadge('error', 'Fix errors');
            predictBtn.disabled = false;
            return;
        }

        const originalText = predictBtn.innerHTML;
        predictBtn.disabled = true;
        predictBtn.innerHTML = '<i class="fas fa-spinner fa-spin"></i> Predicting...';
        this.updateResultsBadge('loading', 'Predicting...');

        try {
            this.predictionHistory.push({ ...formData, timestamp: new Date() });
            if (this.predictionHistory.length > 20) this.predictionHistory.shift();

            const result = await API.predictFarm(formData);
            if (result && result.success) {
                this.updatePredictionResults(result.prediction);
                this.updateResultsBadge('success', 'Complete');
                Perf.scheduleIdle(() => this._postPredictionTasks(result, formData));
            } else {
                throw new Error(result?.error || 'Prediction failed on the server.');
            }
        } catch (error) {
            console.error('Prediction failed:', error);
            this.showToast('Prediction Failed. Please Try Again.', 'error');
        } finally {
            predictBtn.disabled = false;
            predictBtn.innerHTML = originalText;
        }
    },

    showToast(message, type = 'success', duration = 3500) {
        const existing = document.querySelector('#settingsToastContainer .settings-toast');
        if (existing) existing.remove();

        const container = document.getElementById('settingsToastContainer') || document.body;
        const toast = document.createElement('div');
        toast.className = `settings-toast ${type}`;
        const icons = { success: 'fa-check-circle', error: 'fa-times-circle', warning: 'fa-exclamation-triangle', info: 'fa-info-circle' };
        toast.innerHTML = `
            <i class="fas ${icons[type] || icons.info}"></i>
            <span class="settings-toast-content">
                <span class="settings-toast-title">${message}</span>
            </span>
        `;
        toast.style.cssText = `
            position: fixed; bottom: 24px; right: 24px; z-index: 10000;
            display: flex; align-items: center; gap: 10px;
            padding: 14px 20px; border-radius: 12px;
            background: var(--bg-card); border: 1px solid var(--border-color);
            box-shadow: 0 20px 60px rgba(0,0,0,0.15);
            font-size: 0.875rem; font-weight: 500;
            animation: slideInRight 0.35s cubic-bezier(0.16, 1, 0.3, 1);
            max-width: 400px; pointer-events: auto;
        `;
        if (type === 'success') toast.style.borderLeft = '4px solid var(--accent-green)';
        else if (type === 'error') toast.style.borderLeft = '4px solid var(--accent-red)';
        else if (type === 'warning') toast.style.borderLeft = '4px solid var(--accent-orange)';
        else toast.style.borderLeft = '4px solid var(--accent-blue)';

        container.appendChild(toast);
        setTimeout(() => {
            toast.style.transition = 'all 0.35s cubic-bezier(0.5, 0, 0.5, 1)';
            toast.style.transform = 'translateX(120%)';
            toast.style.opacity = '0';
            setTimeout(() => toast.remove(), 350);
        }, duration);
    },

    toggleNotifications(force) {
        const panel = document.getElementById('notificationPanel');
        const overlay = document.getElementById('overlay');

        if (force !== undefined) {
            panel?.classList.toggle('open', force);
            overlay?.classList.toggle('active', force);
        } else {
            panel?.classList.toggle('open');
            overlay?.classList.toggle('active');
        }

        document.body.style.overflow = panel?.classList.contains('open') ? 'hidden' : '';
    },

    exportData() {
        const data = {
            timestamp: new Date().toISOString(),
            cropYield: document.getElementById('yieldValue')?.textContent || '--',
            irrigationLevel: document.getElementById('irrigationValue')?.textContent || '--',
            soilHealth: document.getElementById('soilHealthValue')?.textContent || '--',
            farmEfficiency: document.getElementById('efficiencyValue')?.textContent || '--',
            heatStressRisk: document.getElementById('heatStressValue')?.textContent || '--',
            rainImpact: document.getElementById('rainImpactValue')?.textContent || '--',
        };

        const blob = new Blob([JSON.stringify(data, null, 2)], { type: 'application/json' });
        const url = URL.createObjectURL(blob);
        const a = document.createElement('a');
        a.href = url;
        a.download = `agrisense-report-${new Date().toISOString().slice(0, 10)}.json`;
        document.body.appendChild(a);
        a.click();
        document.body.removeChild(a);
        URL.revokeObjectURL(url);
    },
};

if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', () => App.init());
} else {
    App.init();
}
