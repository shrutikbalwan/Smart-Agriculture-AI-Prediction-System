/* ============================================
   Smart Agriculture Dashboard - Sidebar
   ============================================ */

const Sidebar = {
    element: null,
    isCollapsed: false,

    init() {
        this.element = document.getElementById('sidebar');
        const toggleBtn = document.getElementById('sidebarToggle');
        const mobileBtn = document.getElementById('mobileMenuBtn');
        const overlay = document.getElementById('overlay');

        // Load saved state
        const saved = localStorage.getItem('sidebarCollapsed');
        if (saved === 'true') {
            this.collapse();
        }

        // Desktop toggle
        toggleBtn?.addEventListener('click', () => this.toggle());

        // Mobile menu toggle
        mobileBtn?.addEventListener('click', () => this.toggleMobile());

        // Close mobile menu on overlay click
        overlay?.addEventListener('click', () => this.closeMobile());

        // Navigation click handling
        this.setupNavigation();

        // Handle escape key
        document.addEventListener('keydown', (e) => {
            if (e.key === 'Escape' && window.innerWidth <= 768) {
                this.closeMobile();
            }
        });

        // Debounced resize handler
        this._resizeHandler = Perf.debounce(() => {
            if (window.innerWidth > 768) {
                document.getElementById('overlay')?.classList.remove('active');
                this.element?.classList.remove('open');
            }
        }, 150);
        window.addEventListener('resize', this._resizeHandler, { passive: true });
    },

    toggle() {
        if (this.isCollapsed) {
            this.expand();
        } else {
            this.collapse();
        }
    },

    collapse() {
        this.isCollapsed = true;
        document.body.classList.add('sidebar-collapsed');
        localStorage.setItem('sidebarCollapsed', 'true');
    },

    expand() {
        this.isCollapsed = false;
        document.body.classList.remove('sidebar-collapsed');
        localStorage.setItem('sidebarCollapsed', 'false');
    },

    toggleMobile() {
        this.element?.classList.toggle('open');
        document.getElementById('overlay')?.classList.toggle('active');
        document.body.style.overflow = this.element?.classList.contains('open') ? 'hidden' : '';
    },

    closeMobile() {
        this.element?.classList.remove('open');
        document.getElementById('overlay')?.classList.remove('active');
        document.body.style.overflow = '';
    },

    setupNavigation() {
        const navLinks = document.querySelectorAll('.nav-link');
        const pages = document.querySelectorAll('.page');

        const activatePage = (pageId, updateHistory = true) => {
            if (!pageId) return;
            const link = document.querySelector(`[data-page="${pageId}"]`);
            if (!link) return;

            navLinks.forEach(l => l.classList.remove('active'));
            link.classList.add('active');
            pages.forEach(p => p.classList.remove('active'));
            document.getElementById(`page-${pageId}`)?.classList.add('active');

            if (updateHistory && window.location.hash !== `#${pageId}`) {
                history.pushState(null, '', `#${pageId}`);
            }

            Perf.scheduleIdle(() => {
                window.dispatchEvent(new Event('hashchange'));
            });
            if (window.innerWidth <= 768) this.closeMobile();
        };

        navLinks.forEach(link => {
            link.addEventListener('click', (e) => {
                e.preventDefault();
                activatePage(link.dataset.page || link.getAttribute('href')?.slice(1), true);
            });
        });

        // Handle back/forward browser navigation
        window.addEventListener('popstate', () => {
            const hash = window.location.hash.replace('#', '') || 'dashboard';
            activatePage(hash, false);
        });

        this.activatePage = activatePage;
    },

    // Highlight current nav based on hash on page load
    highlightCurrent() {
        const hash = window.location.hash.replace('#', '') || 'dashboard';
        if (typeof this.activatePage === 'function') this.activatePage(hash, false);
    },
};
