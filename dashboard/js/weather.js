/* ============================================
   Smart Agriculture Dashboard - Weather
   ============================================ */

const WeatherWidget = {
    apiKey: '',
    defaultLocation: { lat: 28.6139, lon: 77.2090 },
    refreshIntervalMs: 15 * 60 * 1000,
    refreshTimer: null,
    currentLocation: null,
    elements: {},

    getStoredApiKey() {
        try {
            const saved = JSON.parse(localStorage.getItem('agrisense_settings') || '{}');
            return saved.owmKey || window.OPENWEATHERMAP_API_KEY || '';
        } catch (err) {
            return window.OPENWEATHERMAP_API_KEY || '';
        }
    },

    syncApiKey() {
        this.apiKey = this.getStoredApiKey();
    },

    init() {
        this.syncApiKey();
        this.elements = {
            container: document.getElementById('weatherWidget'),
            temp: document.getElementById('weatherTemp'),
            humidity: document.getElementById('weatherHumidity'),
            wind: document.getElementById('weatherWind'),
            rain: document.getElementById('weatherRain'),
            forecast: document.getElementById('weatherForecast'),
            status: document.getElementById('weatherStatus'),
        };

        this.loadLocationAndStart();
    },

    async loadLocationAndStart() {
        this.stopAutoRefresh();
        await this.resolveLocation();
        await this.refresh();
        this.startAutoRefresh();
    },

    resolveLocation() {
        return new Promise((resolve) => {
            if (!navigator.geolocation) {
                this.currentLocation = this.defaultLocation;
                resolve(this.currentLocation);
                return;
            }

            navigator.geolocation.getCurrentPosition(
                (position) => {
                    this.currentLocation = {
                        lat: position.coords.latitude,
                        lon: position.coords.longitude,
                    };
                    resolve(this.currentLocation);
                },
                () => {
                    this.currentLocation = this.defaultLocation;
                    resolve(this.currentLocation);
                },
                { enableHighAccuracy: false, timeout: 8000, maximumAge: 10 * 60 * 1000 }
            );
        });
    },

    async refresh() {
        this.syncApiKey();
        const location = this.currentLocation || this.defaultLocation;

        if (!this.apiKey) {
            this.setUnavailableState('OpenWeatherMap API key not configured');
            return;
        }

        try {
            if (this._refreshPromise) return this._refreshPromise;

            this._refreshPromise = (async () => {
                const [currentWeather, forecastWeather] = await Promise.all([
                    this.fetchCurrentWeather(location),
                    this.fetchForecast(location),
                ]);
                this.updateDisplay(currentWeather, forecastWeather);
            })();

            await this._refreshPromise;
            this._refreshPromise = null;
        } catch (error) {
            console.error('Error fetching weather:', error);
            this.setUnavailableState('Weather unavailable');
            this._refreshPromise = null;
        }
    },

    async fetchCurrentWeather({ lat, lon }) {
        const url = `https://api.openweathermap.org/data/2.5/weather?lat=${lat}&lon=${lon}&appid=${this.apiKey}&units=metric`;
        const response = await fetch(url);
        if (!response.ok) throw new Error('Current weather request failed');
        return response.json();
    },

    async fetchForecast({ lat, lon }) {
        const url = `https://api.openweathermap.org/data/2.5/forecast?lat=${lat}&lon=${lon}&appid=${this.apiKey}&units=metric`;
        const response = await fetch(url);
        if (!response.ok) throw new Error('Forecast request failed');
        return response.json();
    },

    updateDisplay(currentWeather, forecastWeather) {
        if (!currentWeather || !forecastWeather) {
            this.setUnavailableState('Weather unavailable');
            return;
        }

        const temp = Math.round(currentWeather.main?.temp);
        const humidity = currentWeather.main?.humidity;
        const windSpeed = currentWeather.wind?.speed;
        const rainAmount = this.getRainAmount(currentWeather, forecastWeather);
        const forecast = this.summarizeForecast(currentWeather, forecastWeather);

        if (this.elements.temp) this.elements.temp.textContent = Number.isFinite(temp) ? `${temp}\u00B0C` : '--';
        if (this.elements.humidity) this.elements.humidity.textContent = Number.isFinite(humidity) ? `${humidity}%` : '--';
        if (this.elements.wind) this.elements.wind.textContent = Number.isFinite(windSpeed) ? `${Math.round(windSpeed * 3.6)} km/h` : '--';
        if (this.elements.rain) this.elements.rain.textContent = `${rainAmount.toFixed(1)} mm`;
        if (this.elements.forecast) this.elements.forecast.textContent = forecast;
        if (this.elements.status) this.elements.status.textContent = currentWeather.weather?.[0]?.main || 'Live weather';
    },

    setUnavailableState(message) {
        if (this.elements.temp) this.elements.temp.textContent = '--';
        if (this.elements.humidity) this.elements.humidity.textContent = '--';
        if (this.elements.wind) this.elements.wind.textContent = '--';
        if (this.elements.rain) this.elements.rain.textContent = '--';
        if (this.elements.forecast) this.elements.forecast.textContent = message || 'Weather unavailable';
        if (this.elements.status) this.elements.status.textContent = 'N/A';
    },

    getRainAmount(currentWeather, forecastWeather) {
        const currentRain = Number(currentWeather.rain?.['1h'] || currentWeather.rain?.['3h'] || 0);
        if (Number.isFinite(currentRain) && currentRain > 0) {
            return currentRain;
        }

        return (forecastWeather.list || []).reduce((sum, item) => {
            const rain = Number(item.rain?.['3h'] || 0);
            return sum + (Number.isFinite(rain) ? rain : 0);
        }, 0);
    },

    summarizeForecast(currentWeather, forecastWeather) {
        const currentMain = currentWeather.weather?.[0]?.main || '';
        const currentDescription = currentWeather.weather?.[0]?.description || '';
        const nextItems = (forecastWeather.list || []).slice(0, 4);
        const hasRainSoon = nextItems.some((item) => Number(item.rain?.['3h'] || 0) > 0 || /rain|drizzle|storm/i.test(item.weather?.[0]?.main || ''));
        const peakTemp = nextItems.reduce((max, item) => Math.max(max, Number(item.main?.temp ?? -Infinity)), Number.NEGATIVE_INFINITY);
        const peakTempText = Number.isFinite(peakTemp) ? `, up to ${Math.round(peakTemp)}\u00B0C` : '';

        if (hasRainSoon) {
            return `Rain expected soon${peakTempText}`;
        }

        if (currentMain) {
            return `${this.capitalize(currentMain)}${currentDescription ? `, ${currentDescription}` : ''}${peakTempText}`;
        }

        return 'Clear conditions ahead';
    },

    capitalize(value) {
        if (!value) return '';
        return String(value).charAt(0).toUpperCase() + String(value).slice(1).toLowerCase();
    },

    startAutoRefresh() {
        this.stopAutoRefresh();
        this.refreshTimer = window.setInterval(() => {
            this.refresh();
        }, this.refreshIntervalMs);
    },

    stopAutoRefresh() {
        if (this.refreshTimer) {
            window.clearInterval(this.refreshTimer);
            this.refreshTimer = null;
        }
    },
};
