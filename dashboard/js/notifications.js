const NotificationService = {
  initialized: false,
  permission: "default",
  notificationList: [],
  badgeCount: 0,

  init() {
    if (this.initialized) return;
    this.initialized = true;

    if ("Notification" in window) {
      this.permission = Notification.permission;
    }

    document.getElementById("notificationsBtn")?.addEventListener("click", () => {
      this.requestPermission();
      this.togglePanel();
    });

    document.getElementById("notificationsClose")?.addEventListener("click", () => {
      this.closePanel();
    });

    document.addEventListener("click", (e) => {
      if (!e.target.closest(".notification-panel") && !e.target.closest("#notificationsBtn")) {
        this.closePanel();
      }
    });
  },

  async requestPermission() {
    if (!("Notification" in window)) return;
    if (Notification.permission === "granted") return;
    this.permission = await Notification.requestPermission();
  },

  send(title, options = {}) {
    if (!("Notification" in window) || Notification.permission !== "granted") return;
    try {
      new Notification(title, {
        icon: "/favicon.ico",
        badge: "/favicon.ico",
        ...options,
      });
    } catch (e) {
    }
  },

  addNotification(type, title, message, iconClass, iconColor) {
    const icons = {
      warning: "exclamation-triangle",
      info: "info-circle",
      success: "check-circle",
      danger: "times-circle",
    };
    const icon = iconClass || icons[type] || "bell";
    const now = new Date();
    const timeStr = now.toLocaleTimeString("en-US", { hour: "2-digit", minute: "2-digit" });

    this.notificationList.unshift({
      id: Date.now(),
      type: type || "info",
      title,
      message,
      icon,
      iconColor: iconColor || "var(--accent-blue)",
      time: timeStr,
      unread: true,
    });

    if (this.notificationList.length > 50) this.notificationList.length = 50;
    this.badgeCount = this.notificationList.filter((n) => n.unread).length;
    this.updateBadge();
    this.renderPanel();
  },

  updateBadge() {
    const badge = document.querySelector(".notification-badge");
    if (badge) {
      badge.textContent = this.badgeCount > 99 ? "99+" : this.badgeCount;
      badge.style.display = this.badgeCount > 0 ? "flex" : "none";
    }
  },

  renderPanel() {
    const list = document.querySelector(".notification-list");
    if (!list) return;

    if (this.notificationList.length === 0) {
      list.innerHTML = `
        <div class="notification-empty" style="text-align:center;padding:40px 20px;color:var(--text-muted);">
          <i class="fas fa-bell-slash" style="font-size:2rem;margin-bottom:12px;display:block;"></i>
          <p>No notifications yet</p>
        </div>
      `;
      return;
    }

    list.innerHTML = this.notificationList.slice(0, 20).map((n) => `
      <div class="notification-item ${n.unread ? "unread" : ""}" data-id="${n.id}">
        <div class="notification-icon ${n.type}" style="color:${n.iconColor};">
          <i class="fas fa-${n.icon}"></i>
        </div>
        <div class="notification-content">
          <p>${n.message}</p>
          <span>${n.time}</span>
        </div>
      </div>
    `).join("");
  },

  togglePanel() {
    const panel = document.getElementById("notificationPanel");
    const overlay = document.getElementById("overlay");
    if (!panel) return;

    const isOpen = panel.classList.contains("open");
    panel.classList.toggle("open", !isOpen);
    if (overlay) overlay.classList.toggle("active", !isOpen);
    document.body.style.overflow = !isOpen ? "hidden" : "";

    if (!isOpen) {
      this.notificationList.forEach((n) => { n.unread = false; });
      this.badgeCount = 0;
      this.updateBadge();
    }
  },

  closePanel() {
    const panel = document.getElementById("notificationPanel");
    const overlay = document.getElementById("overlay");
    if (panel) panel.classList.remove("open");
    if (overlay) overlay.classList.remove("active");
    document.body.style.overflow = "";
  },

  heatAlert(level, region) {
    this.addNotification("warning", "Heat Stress Alert",
      `${level} heat stress detected in ${region}. Take cooling measures.`,
      "temperature-high", "var(--accent-red)");
    this.send("Heat Stress Alert", {
      body: `${level} heat stress detected in ${region}. Take cooling measures.`,
      tag: "heat-alert",
    });
  },

  rainAlert(impact, region) {
    this.addNotification("warning", "Rain Impact Alert",
      `${impact} rain impact expected in ${region}. Check drainage.`,
      "cloud-rain", "var(--accent-cyan)");
    this.send("Rain Impact Alert", {
      body: `${impact} rain impact expected in ${region}. Check drainage.`,
      tag: "rain-alert",
    });
  },

  diseaseAlert(disease, crop) {
    this.addNotification("danger", "Disease Alert",
      `${disease} detected in ${crop}. Apply treatment immediately.`,
      "virus", "var(--accent-red)");
    this.send("Disease Alert", {
      body: `${disease} detected in ${crop}. Apply treatment immediately.`,
      tag: "disease-alert",
    });
  },

  soilAlert(health, region) {
    this.addNotification("warning", "Soil Health Alert",
      `Soil health is ${health} in ${region}. Consider soil treatment.`,
      "mountain", "var(--accent-orange)");
    this.send("Soil Health Alert", {
      body: `Soil health is ${health} in ${region}. Consider soil treatment.`,
      tag: "soil-alert",
    });
  },

  irrigationAlert(status, region) {
    this.addNotification("info", "Irrigation Alert",
      `${status} recommended for ${region}.`,
      "tint", "var(--accent-blue)");
    this.send("Irrigation Alert", {
      body: `${status} recommended for ${region}.`,
      tag: "irrigation-alert",
    });
  },

  checkPredictionAlerts(prediction, region) {
    const heat = prediction.HeatStress || "";
    if (heat.toLowerCase() === "high") this.heatAlert(heat, region);

    const rain = prediction.RainImpact || "";
    if (rain.toLowerCase() === "high") this.rainAlert(rain, region);

    const disease = prediction.Disease || "";
    if (disease && !["healthy", "none"].includes(disease.toLowerCase())) {
      this.diseaseAlert(disease, prediction.CropRecommendation || "crop");
    }

    const soil = prediction.SoilHealth || "";
    if (soil.toLowerCase() === "poor") this.soilAlert(soil, region);

    const irrigation = prediction.Irrigation || "";
    if (irrigation.toLowerCase().includes("start")) {
      this.irrigationAlert(irrigation, region);
    }
  },
};

if (document.readyState === "loading") {
  document.addEventListener("DOMContentLoaded", () => NotificationService.init());
} else {
  NotificationService.init();
}
