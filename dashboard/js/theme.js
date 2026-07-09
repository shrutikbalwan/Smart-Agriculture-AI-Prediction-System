/* ============================================
   Smart Agriculture Dashboard - Theme Toggle
   ============================================ */

const ThemeManager = {
    currentTheme: 'light',

    init() {
        const themeToggle = document.getElementById('themeToggle');

        // Load saved theme
        const saved = localStorage.getItem('theme');
        if (saved === 'dark') {
            this.setDark();
        }

        themeToggle?.addEventListener('click', () => {
            this.toggle();
        });

        // Respect system preference if no saved theme
        if (!saved) {
            const prefersDark = window.matchMedia('(prefers-color-scheme: dark)').matches;
            if (prefersDark) {
                this.setDark();
            }

            // Listen for system changes
            window.matchMedia('(prefers-color-scheme: dark)').addEventListener('change', (e) => {
                if (!localStorage.getItem('theme')) {
                    if (e.matches) {
                        this.setDark();
                    } else {
                        this.setLight();
                    }
                }
            });
        }

        // Update theme icon on page visibility change
        document.addEventListener('visibilitychange', () => {
            if (document.visibilityState === 'visible') {
                this.updateIcon();
            }
        });
    },

    toggle() {
        if (this.currentTheme === 'light') {
            this.setDark();
        } else {
            this.setLight();
        }
    },

    setDark() {
        this.currentTheme = 'dark';
        document.documentElement.setAttribute('data-theme', 'dark');
        localStorage.setItem('theme', 'dark');
        this.updateIcon();
    },

    setLight() {
        this.currentTheme = 'light';
        document.documentElement.setAttribute('data-theme', 'light');
        localStorage.setItem('theme', 'light');
        this.updateIcon();
    },

    updateIcon() {
        const icon = document.querySelector('.theme-toggle i');
        if (icon) {
            if (this.currentTheme === 'dark') {
                icon.className = 'fas fa-sun';
            } else {
                icon.className = 'fas fa-moon';
            }
        }
    },
};
