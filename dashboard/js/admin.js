/* ============================================
   Smart Agriculture Dashboard - Admin Dashboard
   ============================================ */

const AdminDashboard = {
    initialized: false,
    charts: {},

    init() {
        if (this.initialized) return;
        this.initialized = true;

        this.cacheElements();
        this.bindEvents();
        this.setupRouteListener();

        if (this.isActivePage()) {
            this.loadStats();
        }
    },

    cacheElements() {
        this.elements = {
            page: document.getElementById('page-admin-dashboard'),
            totalPredictions: document.getElementById('adminTotalPredictionsValue'),
            mostCrop: document.getElementById('adminMostCropValue'),
            averageYield: document.getElementById('adminAverageYieldValue'),
            accuracy: document.getElementById('adminAccuracyValue'),
            databaseSize: document.getElementById('adminDatabaseSizeValue'),
            todayPredictions: document.getElementById('adminTodayPredictionsValue'),
            refreshBtn: document.getElementById('adminRefreshBtn'),
            loadingState: document.getElementById('adminLoadingState'),
            emptyState: document.getElementById('adminEmptyState'),
            dailyChart: document.getElementById('adminDailyPredictionsChart'),
            cropChart: document.getElementById('adminCropDistributionChart'),
        };
    },

    bindEvents() {
        this.elements.refreshBtn?.addEventListener('click', () => this.loadStats());
    },

    setupRouteListener() {
        window.addEventListener('hashchange', () => {
            if (this.isActivePage()) {
                this.loadStats();
            }
        });
    },

    isActivePage() {
        return document.getElementById('page-admin-dashboard')?.classList.contains('active') || window.location.hash === '#admin-dashboard';
    },

    async loadStats() {
        this.showLoading(true);

        try {
            const result = await API.getDashboardStats();
            if (!result || !result.success) {
                throw new Error(result?.error || 'Unable to load admin metrics.');
            }

            this.render(result.stats || {});
        } catch (error) {
            console.error('Admin dashboard load failed:', error);
            this.renderError(error.message || 'Unable to load admin metrics.');
        } finally {
            this.showLoading(false);
        }
    },

    render(stats) {
        this.setText(this.elements.totalPredictions, stats.total_predictions ?? '--');
        this.setText(this.elements.mostCrop, stats.most_recommended_crop || '--');
        this.setText(this.elements.averageYield, stats.average_yield != null ? `${stats.average_yield} kg/ha` : '--');
        this.setText(this.elements.accuracy, stats.prediction_accuracy != null ? `${stats.prediction_accuracy}%` : '--');
        this.setText(this.elements.databaseSize, stats.database_size_mb != null ? `${stats.database_size_mb} MB` : '--');
        this.setText(this.elements.todayPredictions, stats.today_predictions ?? '--');
        this.renderCharts(stats);
    },

    renderCharts(stats) {
        if (typeof Chart === 'undefined') return;

        const dailyLabels = Array.isArray(stats.daily_predictions) && stats.daily_predictions.length > 0
            ? stats.daily_predictions.map(item => item.date)
            : ['No data'];
        const dailyData = Array.isArray(stats.daily_predictions) && stats.daily_predictions.length > 0
            ? stats.daily_predictions.map(item => item.count)
            : [0];
        this.renderLineChart('adminDailyPredictionsChart', 'Daily Predictions', dailyLabels, dailyData, '#22c55e');

        const cropLabels = Array.isArray(stats.crop_distribution) && stats.crop_distribution.length > 0
            ? stats.crop_distribution.map(item => item.crop)
            : ['No data'];
        const cropData = Array.isArray(stats.crop_distribution) && stats.crop_distribution.length > 0
            ? stats.crop_distribution.map(item => item.count)
            : [0];
        this.renderBarChart('adminCropDistributionChart', 'Recommended Crops', cropLabels, cropData, '#3b82f6');
    },

    renderLineChart(canvasId, label, labels, data, color) {
        const canvas = document.getElementById(canvasId);
        if (!canvas) return;
        const existing = this.charts[canvasId];
        if (existing) existing.destroy();
        this.charts[canvasId] = new Chart(canvas, {
            type: 'line',
            data: { labels, datasets: [{ label, data, borderColor: color, backgroundColor: 'rgba(34, 197, 94, 0.16)', tension: 0.3, fill: true }] },
            options: { responsive: true, maintainAspectRatio: false, plugins: { legend: { display: false } }, scales: { y: { beginAtZero: true } } },
        });
    },

    renderBarChart(canvasId, label, labels, data, color) {
        const canvas = document.getElementById(canvasId);
        if (!canvas) return;
        const existing = this.charts[canvasId];
        if (existing) existing.destroy();
        this.charts[canvasId] = new Chart(canvas, {
            type: 'bar',
            data: { labels, datasets: [{ label, data, backgroundColor: color, borderRadius: 8 }] },
            options: { responsive: true, maintainAspectRatio: false, plugins: { legend: { display: false } }, scales: { y: { beginAtZero: true, precision: 0 } } },
        });
    },

    showLoading(show) {
        if (this.elements.loadingState) {
            this.elements.loadingState.hidden = !show;
        }
        if (this.elements.emptyState) {
            this.elements.emptyState.hidden = true;
        }
    },

    renderError(message) {
        this.elements.emptyState?.removeAttribute('hidden');
        const description = this.elements.emptyState?.querySelector('p');
        if (description) description.textContent = message;
    },

    setText(element, value) {
        if (element) element.textContent = value;
    },
};
