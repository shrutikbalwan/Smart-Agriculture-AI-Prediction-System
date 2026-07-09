/* ============================================
   Smart Agriculture Dashboard - Charts
   with memoization & lazy rendering
   ============================================ */

const Charts = {
    instances: {},
    historyRecords: [],
    historyLoadPromise: null,
    initialized: false,
    _lazyInit: false,

    init() {
        if (this.initialized) return;
        this.initialized = true;

        Perf.scheduleIdle(() => {
            this.initYieldChart();
            this.initSoilHealthChart();
            this.initRainImpactChart();
            this.initFarmEfficiencyChart();
            this.initHeatStressChart();
            this.initPredictionTrendChart();
        });

        document.getElementById('yieldPeriod')?.addEventListener('change', () => {
            this.refreshTrendCharts();
        });

        document.addEventListener('hashchange', () => {
            const hash = window.location.hash.replace('#', '');
            if (hash === 'dashboard' && !this._lazyInit) {
                this._lazyInit = true;
                this.refreshTrendCharts();
            }
        });

        Perf.scheduleIdle(() => this.refreshTrendCharts(), 1000);
    },

    _buildSeriesMemoized: null,

    async refreshTrendCharts() {
        const records = await this.loadHistoryRecords();
        this.historyRecords = records;

        const period = Math.max(1, parseInt(document.getElementById('yieldPeriod')?.value || '30', 10));
        const normalized = this._prepareRecordsMemoized(records);
        const visibleRecords = period ? normalized.slice(-period) : normalized;

        this.updateTrendChart(
            'yield',
            this._buildSeries(visibleRecords, (record) => this.asNumber(record.predicted_yield ?? record.yield), 'kg/ha'),
            'Yield Trend', 'Predicted Yield (kg/ha)', '#22c55e', ' kg/ha'
        );
        this.updateTrendChart(
            'soilHealth',
            this._buildSeries(visibleRecords, (record) => this.scoreSoilHealth(record.soil_health), 'score'),
            'Soil Health Trend', 'Soil Health Score', '#f59e0b', ' %'
        );
        this.updateTrendChart(
            'rainImpact',
            this._buildSeries(visibleRecords, (record) => this.scoreRainImpact(record.rain_impact), 'score'),
            'Rain Impact Trend', 'Rain Impact Score', '#06b6d4', ' %'
        );
        this.updateTrendChart(
            'farmEfficiency',
            this._buildSeries(visibleRecords, (record) => this.scoreFarmEfficiency(record.farm_efficiency), 'score'),
            'Farm Efficiency Trend', 'Farm Efficiency Score', '#8b5cf6', ' %'
        );
        this.updateTrendChart(
            'heatStress',
            this._buildSeries(visibleRecords, (record) => this.scoreHeatStress(record.heat_stress), 'score'),
            'Heat Stress Trend', 'Heat Stress Score', '#ef4444', ' %'
        );
        this.updateTrendChart(
            'predictionTrend',
            this._buildSeries(visibleRecords, (record) => this.asNumber(record.predicted_yield ?? record.yield), 'count'),
            'Prediction Trend', 'Total Predictions', '#3b82f6', ''
        );
    },

    _prepareRecordsMemoized: null,

    async loadHistoryRecords() {
        if (this.historyLoadPromise) return this.historyLoadPromise;

        this.historyLoadPromise = (async () => {
            const pageSize = 50;
            let page = 1;
            let totalPages = 1;
            const records = [];

            while (page <= totalPages) {
                const response = await API.getPredictionHistory({ page, per_page: pageSize });
                if (!response || !response.success) {
                    throw new Error(response?.error || 'Unable to load history for charts.');
                }
                if (Array.isArray(response.data)) records.push(...response.data);
                totalPages = Math.max(1, Number(response.pagination?.total_pages || 1));
                page += 1;
            }
            return records;
        })().catch((error) => {
            console.error('Chart history load failed:', error);
            return [];
        }).finally(() => {
            this.historyLoadPromise = null;
        });

        return this.historyLoadPromise;
    },

    prepareRecords: Perf.memoize(function(records) {
        return (records || [])
            .map((record) => this.normalizeRecord(record))
            .filter((record) => record.date instanceof Date && !Number.isNaN(record.date.getTime()))
            .sort((a, b) => a.date - b.date);
    }),

    normalizeRecord(record) {
        const normalized = record || {};
        const rawDate = normalized.Date ?? normalized.prediction_time ?? normalized.created_at ?? normalized.timestamp ?? normalized.prediction_date ?? null;
        const date = this.parseDate(rawDate);
        return {
            date,
            predicted_yield: normalized.predicted_yield ?? normalized['PredictedYield(Kg/Hectare)'] ?? normalized.yield ?? null,
            soil_health: normalized.soil_health ?? normalized.SoilHealth ?? null,
            rain_impact: normalized.rain_impact ?? normalized.RainImpact ?? null,
            farm_efficiency: normalized.farm_efficiency ?? normalized.FarmEfficiency ?? null,
            heat_stress: normalized.heat_stress ?? normalized.HeatStress ?? null,
        };
    },

    parseDate(value) {
        if (!value) return null;
        const date = new Date(String(value).replace(' ', 'T'));
        if (!Number.isNaN(date.getTime())) return date;
        const alt = new Date(value);
        return Number.isNaN(alt.getTime()) ? null : alt;
    },

    _buildSeries(records, valueGetter, type = 'value') {
        const buckets = new Map();
        records.forEach((record) => {
            const value = valueGetter(record);
            if (value === null || value === undefined || value === '') return;
            const key = this.formatDateKey(record.date);
            const bucket = buckets.get(key) || { date: record.date, sum: 0, count: 0 };
            bucket.sum += Number(value);
            bucket.count += 1;
            buckets.set(key, bucket);
        });
        const points = [...buckets.entries()]
            .sort((a, b) => a[1].date - b[1].date)
            .map(([key, bucket]) => ({
                label: this.formatDisplayDate(bucket.date),
                value: bucket.count ? bucket.sum / bucket.count : null,
                key,
            }))
            .filter((point) => Number.isFinite(point.value));
        return {
            labels: points.map((point) => point.label),
            values: points.map((point) => Number(point.value.toFixed(2))),
            type,
        };
    },

    formatDateKey(date) { return date.toISOString().slice(0, 10); },
    formatDisplayDate(date) { return date.toLocaleDateString('en-US', { month: 'short', day: 'numeric' }); },
    asNumber(value) { const n = Number(value); return Number.isFinite(n) ? n : null; },

    scoreSoilHealth(value) { const m = { Good: 100, Average: 66, Poor: 33 }; return m[value] ?? null; },
    scoreRainImpact(value) { const m = { Medium: 70, High: 30 }; return m[value] ?? null; },
    scoreFarmEfficiency(value) { const m = { Excellent: 100, Good: 80, Average: 60, Poor: 30 }; return m[value] ?? null; },
    scoreHeatStress(value) { const m = { Low: 15, Medium: 50, High: 85, Critical: 100 }; return m[value] ?? null; },

    _chartConfigs: {},

    createTrendChart(canvasId, label, color, unit) {
        const ctx = document.getElementById(canvasId);
        if (!ctx) return null;
        const isDarkTheme = isDark();
        const gridColor = isDarkTheme ? 'rgba(148, 163, 184, 0.15)' : 'rgba(0, 0, 0, 0.06)';
        const textColor = isDarkTheme ? '#94a3b8' : '#6b7280';

        const config = {
            type: 'line',
            data: { labels: [], datasets: [{
                label, data: [],
                borderColor: color,
                backgroundColor: (context) => {
                    const c = context.chart.ctx;
                    const g = c.createLinearGradient(0, 0, 0, 280);
                    g.addColorStop(0, this.hexToRgba(color, 0.25));
                    g.addColorStop(1, this.hexToRgba(color, 0));
                    return g;
                },
                fill: true, tension: 0.35, pointRadius: 3, pointHoverRadius: 6,
                pointBackgroundColor: color, pointBorderColor: isDarkTheme ? '#1e293b' : '#ffffff',
                pointBorderWidth: 2, borderWidth: 3,
            }]},
            options: {
                responsive: true, maintainAspectRatio: false,
                interaction: { intersect: false, mode: 'index' },
                plugins: {
                    legend: { display: false },
                    tooltip: {
                        backgroundColor: isDarkTheme ? '#1e293b' : '#ffffff',
                        titleColor: isDarkTheme ? '#f1f5f9' : '#1a2332',
                        bodyColor: isDarkTheme ? '#94a3b8' : '#6b7280',
                        borderColor: isDarkTheme ? '#334155' : '#e5e7eb',
                        borderWidth: 1, padding: 12, cornerRadius: 8,
                        callbacks: { label: (ctx) => ` ${ctx.parsed.y}${unit}` },
                    },
                },
                scales: {
                    x: { grid: { color: gridColor, drawBorder: false }, ticks: { color: textColor, font: { size: 11 }, maxTicksLimit: 8 } },
                    y: { grid: { color: gridColor, drawBorder: false }, ticks: { color: textColor, font: { size: 11 }, callback: (v) => `${v}${unit}` }, beginAtZero: true },
                },
            },
        };
        this._chartConfigs[canvasId] = { label, color, unit };
        return new Chart(ctx, config);
    },

    updateTrendChart(instanceKey, series, title, label, color, unit) {
        if (!this.instances[instanceKey]) {
            Perf.lazyRender(
                document.getElementById(this.getCanvasId(instanceKey)),
                () => {
                    this.instances[instanceKey] = this.createTrendChart(this.getCanvasId(instanceKey), label, color, unit);
                },
                { rootMargin: '50px' }
            );
        }

        const chart = this.instances[instanceKey];
        if (!chart) return;

        chart.data.labels = series.labels;
        chart.data.datasets[0].label = label;
        chart.data.datasets[0].data = series.values;
        chart.data.datasets[0].borderColor = color;
        chart.data.datasets[0].pointBackgroundColor = color;
        chart.data.datasets[0].backgroundColor = (context) => {
            const c = context.chart.ctx;
            const g = c.createLinearGradient(0, 0, 0, 280);
            g.addColorStop(0, this.hexToRgba(color, 0.25));
            g.addColorStop(1, this.hexToRgba(color, 0));
            return g;
        };
        chart.options.plugins.tooltip.callbacks.label = (ctx) => ` ${ctx.parsed.y}${unit}`;
        chart.update('none');
    },

    getCanvasId(instanceKey) {
        const map = { yield: 'yieldChart', soilHealth: 'soilChart', rainImpact: 'weatherChart', farmEfficiency: 'resourceChart', heatStress: 'heatChart', predictionTrend: 'predictionTrendChart' };
        return map[instanceKey];
    },

    hexToRgba(hex, alpha) {
        const n = parseInt(hex.replace('#', ''), 16);
        return `rgba(${(n>>16)&255}, ${(n>>8)&255}, ${n&255}, ${alpha})`;
    },

    initYieldChart() { this.instances.yield = this.createTrendChart('yieldChart', 'Predicted Yield', '#22c55e', ' kg/ha'); },
    initSoilHealthChart() { this.instances.soilHealth = this.createTrendChart('soilChart', 'Soil Health Score', '#f59e0b', ' %'); },
    initRainImpactChart() { this.instances.rainImpact = this.createTrendChart('weatherChart', 'Rain Impact Score', '#06b6d4', ' %'); },
    initFarmEfficiencyChart() { this.instances.farmEfficiency = this.createTrendChart('resourceChart', 'Farm Efficiency Score', '#8b5cf6', ' %'); },
    initHeatStressChart() { this.instances.heatStress = this.createTrendChart('heatChart', 'Heat Stress Score', '#ef4444', ' %'); },
    initPredictionTrendChart() { this.instances.predictionTrend = this.createTrendChart('predictionTrendChart', 'Prediction Count', '#3b82f6', ''); },
    updateYieldChart() { this.refreshTrendCharts(); },
    updateYieldChartWithPrediction() { this.refreshTrendCharts(); },
    updateSoilChartWithInputs() { this.refreshTrendCharts(); },

    refreshTheme() {
        Object.values(this.instances).forEach((chart) => {
            if (!chart || !chart.options) return;
            const isDarkTheme = document.documentElement.getAttribute('data-theme') === 'dark';
            const gridColor = isDarkTheme ? 'rgba(148, 163, 184, 0.15)' : 'rgba(0, 0, 0, 0.06)';
            const textColor = isDarkTheme ? '#94a3b8' : '#6b7280';

            if (chart.options.scales) {
                Object.values(chart.options.scales).forEach((scale) => {
                    if (!scale) return;
                    scale.grid = scale.grid || {};
                    scale.grid.color = gridColor;
                    scale.ticks = scale.ticks || {};
                    scale.ticks.color = textColor;
                });
            }
            chart.options.plugins = chart.options.plugins || {};
            chart.options.plugins.tooltip = chart.options.plugins.tooltip || {};
            chart.options.plugins.tooltip.backgroundColor = isDarkTheme ? '#1e293b' : '#ffffff';
            chart.options.plugins.tooltip.titleColor = isDarkTheme ? '#f1f5f9' : '#1a2332';
            chart.options.plugins.tooltip.bodyColor = isDarkTheme ? '#94a3b8' : '#6b7280';
            chart.options.plugins.tooltip.borderColor = isDarkTheme ? '#334155' : '#e5e7eb';
            chart.update('none');
        });
    },
};

function isDark() {
    return document.documentElement.getAttribute('data-theme') === 'dark';
}
