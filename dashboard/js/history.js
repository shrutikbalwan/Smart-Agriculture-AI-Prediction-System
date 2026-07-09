/* ============================================
   Smart Agriculture Dashboard - Prediction History
   ============================================ */

const PredictionHistoryModule = {
    initialized: false,
    loading: false,
    metaLoaded: false,
    sortColumn: 'prediction_time',
    sortOrder: 'DESC',
    records: [],
    pagination: {
        page: 1,
        per_page: 10,
        total: 0,
        total_pages: 1,
    },
    elements: {},

    init() {
        if (this.initialized) return;
        this.initialized = true;

        this.cacheElements();
        this.bindEvents();
        this.setupRouteListener();
        this.loadMeta();

        if (this.isActivePage()) {
            this.loadHistory(1);
        }
    },

    cacheElements() {
        this.elements = {
            page: document.getElementById('page-prediction-history'),
            searchInput: document.getElementById('historySearchInput'),
            searchBtn: document.getElementById('historySearchBtn'),
            clearSearchBtn: document.getElementById('historyClearSearchBtn'),
            applyFiltersBtn: document.getElementById('historyApplyFiltersBtn'),
            resetBtn: document.getElementById('historyResetBtn'),
            refreshBtn: document.getElementById('historyRefreshBtn'),
            regionFilter: document.getElementById('historyRegionFilter'),
            cropFilter: document.getElementById('historyCropFilter'),
            diseaseFilter: document.getElementById('historyDiseaseFilter'),
            startDate: document.getElementById('historyStartDate'),
            endDate: document.getElementById('historyEndDate'),
            tableBody: document.getElementById('historyTableBody'),
            emptyState: document.getElementById('historyEmptyState'),
            loadingState: document.getElementById('historyLoadingState'),
            paginationInfo: document.getElementById('historyPaginationInfo'),
            tableMeta: document.getElementById('historyTableMeta'),
            prevPageBtn: document.getElementById('historyPrevPageBtn'),
            nextPageBtn: document.getElementById('historyNextPageBtn'),
            totalValue: document.getElementById('historyTotalValue'),
            visibleValue: document.getElementById('historyVisibleValue'),
            latestValue: document.getElementById('historyLatestValue'),
            activeFiltersValue: document.getElementById('historyActiveFiltersValue'),
        };
    },

    bindEvents() {
        this._debouncedSearch = Perf.debounce(() => {
            if (this.isActivePage()) this.loadHistory(1);
        }, 300);

        this.elements.searchInput?.addEventListener('input', () => {
            this._debouncedSearch();
        });

        this.elements.searchBtn?.addEventListener('click', () => this.loadHistory(1));
        this.elements.clearSearchBtn?.addEventListener('click', () => {
            if (this.elements.searchInput) {
                this.elements.searchInput.value = '';
            }
            this.loadHistory(1);
        });

        this.elements.applyFiltersBtn?.addEventListener('click', () => this.loadHistory(1));
        this.elements.resetBtn?.addEventListener('click', () => this.resetFilters());
        this.elements.refreshBtn?.addEventListener('click', () => this.loadHistory(this.pagination.page));
        this.elements.prevPageBtn?.addEventListener('click', () => {
            if (this.pagination.page > 1) {
                this.loadHistory(this.pagination.page - 1);
            }
        });
        this.elements.nextPageBtn?.addEventListener('click', () => {
            if (this.pagination.page < this.pagination.total_pages) {
                this.loadHistory(this.pagination.page + 1);
            }
        });

        [this.elements.regionFilter, this.elements.cropFilter, this.elements.diseaseFilter, this.elements.startDate, this.elements.endDate]
            .forEach((element) => {
                element?.addEventListener('change', () => this.loadHistory(1));
            });

        document.querySelectorAll('.history-table thead th.sortable').forEach((th) => {
            th.addEventListener('click', () => {
                const col = th.getAttribute('data-sort');
                if (this.sortColumn === col) {
                    this.sortOrder = this.sortOrder === 'ASC' ? 'DESC' : 'ASC';
                } else {
                    this.sortColumn = col;
                    this.sortOrder = 'DESC';
                }
                document.querySelectorAll('.history-table thead th.sortable i').forEach((icon) => {
                    icon.className = 'fas fa-sort';
                });
                const icon = th.querySelector('i');
                if (icon) {
                    icon.className = this.sortOrder === 'ASC' ? 'fas fa-sort-up' : 'fas fa-sort-down';
                }
                this.loadHistory(1);
            });
        });

        this.elements.tableBody?.addEventListener('click', (event) => {
            const deleteBtn = event.target.closest('[data-action="delete-history"]');
            if (deleteBtn) {
                const recordId = deleteBtn.getAttribute('data-id');
                if (recordId) {
                    this.deleteRecord(recordId);
                }
                return;
            }
            const viewBtn = event.target.closest('[data-action="view-history"]');
            if (viewBtn) {
                const recordId = viewBtn.getAttribute('data-id');
                if (recordId) {
                    this.viewRecord(recordId);
                }
            }
        });
    },

    setupRouteListener() {
        window.addEventListener('hashchange', () => {
            if (this.isActivePage()) {
                this.loadHistory(1);
            }
        });
    },

    isActivePage() {
        return document.getElementById('page-prediction-history')?.classList.contains('active') || window.location.hash === '#prediction-history';
    },

    getFilters() {
        return {
            search: this.elements.searchInput?.value?.trim() || '',
            region: this.elements.regionFilter?.value || '',
            crop: this.elements.cropFilter?.value || '',
            disease: this.elements.diseaseFilter?.value || '',
            start_date: this.elements.startDate?.value || '',
            end_date: this.elements.endDate?.value || '',
        };
    },

    async loadMeta() {
        if (this.metaLoaded) return;

        const result = await API.getPredictionHistoryMeta();
        if (!result || !result.success) return;

        this.metaLoaded = true;
        this.populateSelect(this.elements.regionFilter, result.regions || [], 'All Regions');
        this.populateSelect(this.elements.cropFilter, result.crops || [], 'All Crops');
        this.populateSelect(this.elements.diseaseFilter, result.diseases || [], 'All Diseases');

        if (result.date_range?.max && this.elements.endDate && !this.elements.endDate.value) {
            this.elements.endDate.max = String(result.date_range.max).slice(0, 10);
        }
        if (result.date_range?.min && this.elements.startDate && !this.elements.startDate.value) {
            this.elements.startDate.min = String(result.date_range.min).slice(0, 10);
        }
    },

    populateSelect(selectElement, values, placeholder) {
        if (!selectElement) return;

        const currentValue = selectElement.value;
        const options = new Set(Array.from(selectElement.options).map((option) => option.value));
        const sortedValues = [...values].filter(Boolean).sort((a, b) => String(a).localeCompare(String(b)));

        selectElement.innerHTML = `<option value="">${placeholder}</option>`;
        sortedValues.forEach((value) => {
            const option = document.createElement('option');
            option.value = value;
            option.textContent = value;
            selectElement.appendChild(option);
            options.add(value);
        });

        if (options.has(currentValue)) {
            selectElement.value = currentValue;
        }
    },

    async loadHistory(page = 1) {
        if (this.loading) return;
        this.loading = true;
        this.showLoading(true);

        try {
            await this.loadMeta();

            const filters = this.getFilters();
            const result = await API.getPredictionHistory({
                page,
                per_page: this.pagination.per_page,
                sort: this.sortColumn,
                order: this.sortOrder,
                ...filters,
            });

            if (!result || !result.success) {
                throw new Error(result?.error || 'Unable to load prediction history.');
            }

            this.records = Array.isArray(result.data) ? result.data.map((record) => this.normalizeRecord(record)) : [];
            this.pagination = {
                ...this.pagination,
                ...(result.pagination || {}),
            };

            this.pagination.page = result.pagination?.page || page;
            this.pagination.per_page = result.pagination?.per_page || this.pagination.per_page;
            this.pagination.total = result.pagination?.total || 0;
            this.pagination.total_pages = result.pagination?.total_pages || 1;

            this.render();
        } catch (error) {
            console.error('Failed to load history:', error);
            this.renderError(error.message || 'Failed to load prediction history.');
        } finally {
            this.loading = false;
            this.showLoading(false);
        }
    },

    normalizeRecord(record) {
        const normalized = record || {};
        const id = normalized.id ?? normalized.prediction_id ?? normalized.history_id ?? normalized.record_id ?? '';
        const dateValue = normalized.Date ?? normalized.prediction_time ?? normalized.created_at ?? normalized.timestamp ?? normalized.prediction_date ?? null;
        const yieldValue = normalized.predicted_yield ?? normalized.yield ?? normalized.PredictedYield ?? normalized['PredictedYield(Kg/Hectare)'] ?? null;

        return {
            id,
            date: dateValue,
            region: normalized.region ?? '--',
            crop: normalized.crop_type ?? '--',
            recommendedCrop: normalized.crop_recommendation ?? normalized.CropRecommendation ?? '--',
            yield: yieldValue,
            disease: normalized.disease_prediction ?? normalized.Disease ?? '--',
            soilHealth: normalized.soil_health ?? normalized.SoilHealth ?? '--',
            farmEfficiency: normalized.farm_efficiency ?? normalized.FarmEfficiency ?? '--',
        };
    },

    render() {
        Perf.batchDOM(() => {
            this.renderSummary();
            this.renderTable();
            this.renderPagination();
        }, 'historyRender');
    },

    renderSummary() {
        const total = this.pagination.total || 0;
        const visible = this.records.length;
        const latest = this.records.length ? this.formatDate(this.records[0].date) : '--';
        const activeFilters = this.getActiveFilterCount();

        if (this.elements.totalValue) this.elements.totalValue.textContent = this.formatNumber(total);
        if (this.elements.visibleValue) this.elements.visibleValue.textContent = this.formatNumber(visible);
        if (this.elements.latestValue) this.elements.latestValue.textContent = latest;
        if (this.elements.activeFiltersValue) this.elements.activeFiltersValue.textContent = activeFilters > 0 ? this.formatNumber(activeFilters) : '0';
        if (this.elements.tableMeta) {
            this.elements.tableMeta.textContent = total
                ? `${this.formatNumber(total)} records across ${this.formatNumber(this.pagination.total_pages || 1)} pages`
                : 'No records in history yet';
        }
    },

    getActiveFilterCount() {
        const filters = this.getFilters();
        return Object.values(filters).filter((value) => value !== '').length;
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

        this.records.forEach((record) => {
            const row = document.createElement('tr');
            row.appendChild(this.createCell(this.formatDate(record.date)));
            row.appendChild(this.createCell(this.formatText(record.region)));
            row.appendChild(this.createCell(this.formatText(record.crop)));
            row.appendChild(this.createCell(this.formatText(record.recommendedCrop)));
            row.appendChild(this.createCell(this.formatYield(record.yield)));
            row.appendChild(this.createCell(this.formatText(record.disease)));
            row.appendChild(this.createCell(this.formatText(record.soilHealth)));
            row.appendChild(this.createCell(this.formatText(record.farmEfficiency)));
            row.appendChild(this.createActionCell(record.id));
            tbody.appendChild(row);
        });
    },

    createCell(value) {
        const cell = document.createElement('td');
        cell.textContent = value;
        return cell;
    },

    createActionCell(recordId) {
        const cell = document.createElement('td');
        const wrapper = document.createElement('div');
        wrapper.className = 'history-actions';

        const viewBtn = document.createElement('button');
        viewBtn.type = 'button';
        viewBtn.className = 'history-view-btn';
        viewBtn.setAttribute('data-action', 'view-history');
        viewBtn.setAttribute('data-id', recordId || '');
        viewBtn.disabled = !recordId;
        viewBtn.innerHTML = '<i class="fas fa-eye"></i>';

        const delBtn = document.createElement('button');
        delBtn.type = 'button';
        delBtn.className = 'history-delete-btn';
        delBtn.setAttribute('data-action', 'delete-history');
        delBtn.setAttribute('data-id', recordId || '');
        delBtn.disabled = !recordId;
        delBtn.innerHTML = '<i class="fas fa-trash"></i>';

        wrapper.appendChild(viewBtn);
        wrapper.appendChild(delBtn);
        cell.appendChild(wrapper);
        return cell;
    },

    viewRecord(recordId) {
        const record = this.records.find((r) => String(r.id) === String(recordId));
        if (!record) return;
        this.showDetailModal(record);
    },

    showDetailModal(record) {
        const existing = document.getElementById('historyDetailModal');
        if (existing) existing.remove();

        const overlay = document.createElement('div');
        overlay.className = 'overlay';
        overlay.id = 'historyDetailOverlay';
        overlay.style.display = 'block';
        overlay.addEventListener('click', () => this.closeDetailModal());

        const fields = [
            { label: 'Date', value: this.formatDate(record.date) },
            { label: 'Region', value: this.formatText(record.region) },
            { label: 'Crop Type', value: this.formatText(record.crop) },
            { label: 'Recommended Crop', value: this.formatText(record.recommendedCrop) },
            { label: 'Predicted Yield', value: this.formatYield(record.yield) },
            { label: 'Disease Prediction', value: this.formatText(record.disease) },
            { label: 'Soil Health', value: this.formatText(record.soilHealth) },
            { label: 'Farm Efficiency', value: this.formatText(record.farmEfficiency) },
        ];

        const modal = document.createElement('div');
        modal.className = 'history-detail-modal';
        modal.id = 'historyDetailModal';
        modal.innerHTML = `
            <div class="history-detail-header">
                <h3><i class="fas fa-file-alt"></i> Prediction Details</h3>
                <button class="btn-close" id="historyDetailClose"><i class="fas fa-times"></i></button>
            </div>
            <div class="history-detail-body">
                ${fields.map((f) => `
                    <div class="history-detail-row">
                        <span class="history-detail-label">${f.label}</span>
                        <span class="history-detail-value">${f.value}</span>
                    </div>
                `).join('')}
            </div>
            <div class="history-detail-footer">
                <button class="btn btn-outline" id="historyDetailCloseBtn">Close</button>
            </div>
        `;

        document.body.appendChild(overlay);
        document.body.appendChild(modal);

        document.getElementById('historyDetailClose')?.addEventListener('click', () => this.closeDetailModal());
        document.getElementById('historyDetailCloseBtn')?.addEventListener('click', () => this.closeDetailModal());
        document.addEventListener('keydown', this._closeOnEscape = (e) => {
            if (e.key === 'Escape') this.closeDetailModal();
        });
    },

    closeDetailModal() {
        document.getElementById('historyDetailModal')?.remove();
        const overlay = document.getElementById('historyDetailOverlay');
        if (overlay) overlay.style.display = 'none';
        overlay?.remove();
        if (this._closeOnEscape) {
            document.removeEventListener('keydown', this._closeOnEscape);
            this._closeOnEscape = null;
        }
    },

    renderPagination() {
        const totalPages = Math.max(1, this.pagination.total_pages || 1);
        const page = Math.min(Math.max(1, this.pagination.page || 1), totalPages);

        if (this.elements.paginationInfo) {
            this.elements.paginationInfo.textContent = `Page ${page} of ${totalPages}`;
        }
        if (this.elements.prevPageBtn) {
            this.elements.prevPageBtn.disabled = page <= 1;
        }
        if (this.elements.nextPageBtn) {
            this.elements.nextPageBtn.disabled = page >= totalPages;
        }
    },

    renderError(message) {
        this.records = [];
        this.toggleEmptyState(true, message);
        if (this.elements.tableMeta) {
            this.elements.tableMeta.textContent = message;
        }
    },

    toggleEmptyState(show, message) {
        if (this.elements.emptyState) {
            this.elements.emptyState.hidden = !show;
            if (show && message) {
                const description = this.elements.emptyState.querySelector('p');
                if (description) description.textContent = message;
            }
        }
    },

    showLoading(show) {
        if (this.elements.loadingState) {
            this.elements.loadingState.hidden = !show;
        }
        if (this.elements.tableBody) {
            this.elements.tableBody.closest('.history-table-body')?.classList.toggle('is-loading', show);
        }
    },

    async deleteRecord(recordId) {
        const confirmDelete = window.confirm('Delete this prediction record? This cannot be undone.');
        if (!confirmDelete) return;

        const result = await API.deletePredictionHistoryEntry(recordId);
        if (!result || !result.success) {
            App.showToast(result?.error || 'Unable to delete this record.', 'warning');
            return;
        }

        await this.loadHistory(this.pagination.page);
    },

    resetFilters() {
        if (this.elements.searchInput) this.elements.searchInput.value = '';
        if (this.elements.regionFilter) this.elements.regionFilter.value = '';
        if (this.elements.cropFilter) this.elements.cropFilter.value = '';
        if (this.elements.diseaseFilter) this.elements.diseaseFilter.value = '';
        if (this.elements.startDate) this.elements.startDate.value = '';
        if (this.elements.endDate) this.elements.endDate.value = '';
        this.loadHistory(1);
    },

    formatText(value) {
        return value === undefined || value === null || value === '' ? '--' : String(value);
    },

    formatYield(value) {
        if (value === undefined || value === null || value === '') return '--';
        const numeric = Number(value);
        if (Number.isFinite(numeric)) {
            return `${numeric.toFixed(2)} kg/ha`;
        }
        return String(value);
    },

    formatDate(value) {
        if (!value) return '--';

        const date = new Date(String(value).replace(' ', 'T'));
        if (Number.isNaN(date.getTime())) {
            return String(value);
        }

        return date.toLocaleDateString('en-US', {
            year: 'numeric',
            month: 'short',
            day: 'numeric',
        });
    },

    formatNumber(value) {
        const numeric = Number(value);
        if (!Number.isFinite(numeric)) return '--';
        return numeric.toLocaleString('en-US');
    },
};
