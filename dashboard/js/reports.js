/* ============================================
   Smart Agriculture Dashboard - Reports Page
   ============================================ */

const ReportsPage = {
    initialized: false,
    records: [],
    charts: {},

    init() {
        if (this.initialized) return;
        this.initialized = true;

        this.cacheElements();
        this.bindEvents();
        this.setupRouteListener();

        if (this.isActivePage()) {
            this.loadReports();
        }
    },

    cacheElements() {
        this.elements = {
            page: document.getElementById('page-reports'),
            totalValue: document.getElementById('reportsTotalValue'),
            avgYieldValue: document.getElementById('reportsAvgYieldValue'),
            soilValue: document.getElementById('reportsSoilValue'),
            efficiencyValue: document.getElementById('reportsEfficiencyValue'),
            generatedAtValue: document.getElementById('reportsGeneratedAtValue'),
            tableBody: document.getElementById('reportsTableBody'),
            emptyState: document.getElementById('reportsEmptyState'),
            loadingState: document.getElementById('reportsLoadingState'),
            exportCsvBtn: document.getElementById('reportExportCsvBtn'),
            exportExcelBtn: document.getElementById('reportExportExcelBtn'),
            exportPdfBtn: document.getElementById('reportExportPdfBtn'),
            refreshBtn: document.getElementById('reportRefreshBtn'),
            yieldChart: document.getElementById('reportsYieldChart'),
            diseaseChart: document.getElementById('reportsDiseaseChart'),
        };
    },

    bindEvents() {
        this.elements.exportCsvBtn?.addEventListener('click', () => this.exportCsv());
        this.elements.exportExcelBtn?.addEventListener('click', () => this.exportExcel());
        this.elements.exportPdfBtn?.addEventListener('click', () => this.exportPdf());
        this.elements.refreshBtn?.addEventListener('click', () => this.loadReports());
    },

    setupRouteListener() {
        window.addEventListener('hashchange', () => {
            if (this.isActivePage()) {
                this.loadReports();
            }
        });
    },

    isActivePage() {
        return document.getElementById('page-reports')?.classList.contains('active') || window.location.hash === '#reports';
    },

    async loadReports() {
        this.showLoading(true);

        try {
            const result = await API.getPredictionHistory({ page: 1, per_page: 200 });
            if (!result || !result.success) {
                throw new Error(result?.error || 'Unable to load report data.');
            }

            this.records = Array.isArray(result.data) ? result.data.map((record) => this.normalizeRecord(record)) : [];
            this.render();
        } catch (error) {
            console.error('Reports load failed:', error);
            this.renderError(error.message || 'Unable to load report data.');
        } finally {
            this.showLoading(false);
        }
    },

    normalizeRecord(record) {
        const normalized = record || {};
        const dateValue = normalized.Date ?? normalized.prediction_time ?? normalized.created_at ?? normalized.timestamp ?? null;
        const yieldValue = normalized.predicted_yield ?? normalized.yield ?? normalized.PredictedYield ?? normalized['PredictedYield(Kg/Hectare)'] ?? null;

        return {
            date: dateValue,
            region: normalized.region ?? '--',
            crop: normalized.crop_type ?? '--',
            recommendedCrop: normalized.crop_recommendation ?? normalized.CropRecommendation ?? '--',
            yield: yieldValue,
            disease: normalized.disease_prediction ?? normalized.Disease ?? '--',
            soilHealth: normalized.soil_health ?? normalized.SoilHealth ?? '--',
            farmEfficiency: normalized.farm_efficiency ?? normalized.FarmEfficiency ?? '--',
            confidence: normalized.confidence ?? '--',
        };
    },

    render() {
        Perf.batchDOM(() => {
            this.renderSummary();
            this.renderCharts();
            this.renderTable();
        }, 'reportsRender');
    },

    renderSummary() {
        const total = this.records.length;
        const yields = this.records.map((record) => Number(record.yield)).filter((value) => Number.isFinite(value));
        const avgYield = yields.length ? (yields.reduce((sum, value) => sum + value, 0) / yields.length).toFixed(2) : '0.00';
        const soilValues = this.records.map((record) => this.scoreQuality(record.soilHealth)).filter((value) => Number.isFinite(value));
        const efficiencyValues = this.records.map((record) => this.scoreQuality(record.farmEfficiency)).filter((value) => Number.isFinite(value));

        this.setText(this.elements.totalValue, total.toLocaleString('en-US'));
        this.setText(this.elements.avgYieldValue, `${avgYield} kg/ha`);
        this.setText(this.elements.soilValue, soilValues.length ? `${Math.round(soilValues.reduce((sum, value) => sum + value, 0) / soilValues.length)}%` : '--');
        this.setText(this.elements.efficiencyValue, efficiencyValues.length ? `${Math.round(efficiencyValues.reduce((sum, value) => sum + value, 0) / efficiencyValues.length)}%` : '--');
        this.setText(this.elements.generatedAtValue, new Date().toLocaleString('en-US'));
    },

    renderCharts() {
        if (typeof Chart === 'undefined') return;

        const yieldLabels = this.records.slice(0, 10).reverse().map((record) => this.formatDate(record.date));
        const yieldData = this.records.slice(0, 10).reverse().map((record) => Number(record.yield) || 0);

        this.renderLineChart('reportsYieldChart', 'Yield Trend', yieldLabels, yieldData, '#22c55e');

        const diseaseCounts = this.records.reduce((counts, record) => {
            const key = record.disease || 'Unknown';
            counts[key] = (counts[key] || 0) + 1;
            return counts;
        }, {});

        const diseaseLabels = Object.keys(diseaseCounts);
        const diseaseValues = Object.values(diseaseCounts);
        this.renderBarChart('reportsDiseaseChart', 'Disease Distribution', diseaseLabels, diseaseValues, '#3b82f6');
    },

    renderLineChart(canvasId, label, labels, data, color) {
        const canvas = document.getElementById(canvasId);
        if (!canvas) return;

        const existing = this.charts[canvasId];
        if (existing) {
            existing.destroy();
        }

        this.charts[canvasId] = new Chart(canvas, {
            type: 'line',
            data: {
                labels,
                datasets: [{
                    label,
                    data,
                    borderColor: color,
                    backgroundColor: 'rgba(34, 197, 94, 0.14)',
                    tension: 0.3,
                    fill: true,
                    pointRadius: 4,
                }],
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                plugins: { legend: { display: false } },
                scales: {
                    y: { beginAtZero: true },
                },
            },
        });
    },

    renderBarChart(canvasId, label, labels, data, color) {
        const canvas = document.getElementById(canvasId);
        if (!canvas) return;

        const existing = this.charts[canvasId];
        if (existing) {
            existing.destroy();
        }

        this.charts[canvasId] = new Chart(canvas, {
            type: 'bar',
            data: {
                labels,
                datasets: [{
                    label,
                    data,
                    backgroundColor: color,
                    borderRadius: 8,
                }],
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                plugins: { legend: { display: false } },
                scales: {
                    y: { beginAtZero: true, precision: 0 },
                },
            },
        });
    },

    renderTable() {
        const tbody = this.elements.tableBody;
        if (!tbody) return;

        tbody.innerHTML = '';
        if (!this.records.length) {
            this.toggleEmptyState(true);
            return;
        }

        this.toggleEmptyState(false);
        this.records.slice(0, 8).forEach((record) => {
            const row = document.createElement('tr');
            row.innerHTML = `
                <td>${this.escapeHtml(this.formatDate(record.date))}</td>
                <td>${this.escapeHtml(this.formatText(record.region))}</td>
                <td>${this.escapeHtml(this.formatText(record.crop))}</td>
                <td>${this.escapeHtml(this.formatText(record.recommendedCrop))}</td>
                <td>${this.escapeHtml(this.formatYield(record.yield))}</td>
                <td>${this.escapeHtml(this.formatText(record.disease))}</td>
            `;
            tbody.appendChild(row);
        });
    },

    toggleEmptyState(show) {
        this.elements.emptyState?.toggleAttribute('hidden', !show);
        this.elements.loadingState?.toggleAttribute('hidden', true);
    },

    showLoading(show) {
        if (this.elements.loadingState) {
            this.elements.loadingState.hidden = !show;
        }
        if (this.elements.tableBody) {
            this.elements.tableBody.closest('.history-table-body')?.classList.toggle('is-loading', show);
        }
    },

    renderError(message) {
        this.records = [];
        this.elements.emptyState?.removeAttribute('hidden');
        const description = this.elements.emptyState?.querySelector('p');
        if (description) description.textContent = message;
    },

    exportCsv() {
        const headers = ['Date', 'Region', 'Crop', 'Recommended Crop', 'Yield', 'Disease', 'Soil Health', 'Farm Efficiency', 'Confidence'];
        const rows = this.records.map((record) => [
            record.date || '',
            record.region || '',
            record.crop || '',
            record.recommendedCrop || '',
            record.yield || '',
            record.disease || '',
            record.soilHealth || '',
            record.farmEfficiency || '',
            record.confidence || '',
        ]);
        const csv = [headers, ...rows].map((row) => row.map((value) => this.escapeCsv(value)).join(',')).join('\n');
        this.downloadBlob(new Blob([csv], { type: 'text/csv;charset=utf-8;' }), 'agrisense-report.csv');
    },

    exportExcel() {
        const headers = ['Date', 'Region', 'Crop', 'Recommended Crop', 'Yield', 'Disease', 'Soil Health', 'Farm Efficiency', 'Confidence'];
        const rows = this.records.map((record) => [
            record.date || '',
            record.region || '',
            record.crop || '',
            record.recommendedCrop || '',
            record.yield || '',
            record.disease || '',
            record.soilHealth || '',
            record.farmEfficiency || '',
            record.confidence || '',
        ]);
        const xml = `<?xml version="1.0" encoding="UTF-8"?>\n<Workbook xmlns="urn:schemas-microsoft-com:office:spreadsheet" xmlns:ss="urn:schemas-microsoft-com:office:spreadsheet">\n  <Worksheet ss:Name="Reports">\n    <Table>${headers.map((header) => `<Cell><Data ss:Type="String">${this.escapeXml(header)}</Data></Cell>`).join('')}\n${rows.map((row) => `<Row>${row.map((value) => `<Cell><Data ss:Type="String">${this.escapeXml(value)}</Data></Cell>`).join('')}</Row>`).join('\n')}\n    </Table>\n  </Worksheet>\n</Workbook>`;
        this.downloadBlob(new Blob([xml], { type: 'application/vnd.ms-excel;charset=utf-8;' }), 'agrisense-report.xls');
    },

    exportPdf() {
        window.print();
    },

    downloadBlob(blob, fileName) {
        const url = URL.createObjectURL(blob);
        const link = document.createElement('a');
        link.href = url;
        link.download = fileName;
        document.body.appendChild(link);
        link.click();
        document.body.removeChild(link);
        URL.revokeObjectURL(url);
    },

    setText(element, value) {
        if (element) element.textContent = value;
    },

    escapeCsv(value) {
        const stringValue = String(value ?? '');
        return /[",\n]/.test(stringValue) ? `"${stringValue.replace(/"/g, '""')}"` : stringValue;
    },

    escapeXml(value) {
        return String(value ?? '').replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;').replace(/"/g, '&quot;');
    },

    escapeHtml(value) {
        return String(value ?? '').replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;');
    },

    formatText(value) {
        return value === undefined || value === null || value === '' ? '--' : String(value);
    },

    formatDate(value) {
        if (!value) return '--';
        const date = new Date(String(value).replace(' ', 'T'));
        if (Number.isNaN(date.getTime())) return String(value);
        return date.toLocaleDateString('en-US', { year: 'numeric', month: 'short', day: 'numeric' });
    },

    formatYield(value) {
        if (value === undefined || value === null || value === '') return '--';
        const numeric = Number(value);
        return Number.isFinite(numeric) ? `${numeric.toFixed(2)} kg/ha` : String(value);
    },

    scoreQuality(value) {
        if (value === undefined || value === null || value === '') return null;
        const text = String(value).toLowerCase();
        if (text.includes('excellent')) return 100;
        if (text.includes('good')) return 80;
        if (text.includes('average')) return 60;
        if (text.includes('poor')) return 35;
        const numeric = Number(value);
        return Number.isFinite(numeric) ? numeric : null;
    },
};
