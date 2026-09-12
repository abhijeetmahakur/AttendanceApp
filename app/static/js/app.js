(function () {
    "use strict";

    var EYE_OPEN =
        '<svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" ' +
        'stroke-linecap="round" stroke-linejoin="round"><path d="M1 12s4-7 11-7 11 7 11 7-4 7-11 7-11-7-11-7z"/>' +
        '<circle cx="12" cy="12" r="3"/></svg>';

    var EYE_OFF =
        '<svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" ' +
        'stroke-linecap="round" stroke-linejoin="round"><path d="M17.94 17.94A10.94 10.94 0 0 1 12 19c-7 0-11-7-11-7 ' +
        'a21.86 21.86 0 0 1 5.06-6.06M9.9 4.24A10.94 10.94 0 0 1 12 4c7 0 11 7 11 7a21.86 21.86 0 0 1-3.22 4.32M1 1l22 22"/>' +
        '<path d="M14.12 14.12a3 3 0 1 1-4.24-4.24"/></svg>';

    function initThemeToggle() {
        var btn = document.getElementById("theme-toggle");
        if (!btn) return;

        function current() {
            return document.documentElement.getAttribute("data-theme") === "light" ? "light" : "dark";
        }

        function sync() {
            var theme = current();
            var icon = theme === "dark" ? "☀️" : "🌙"; // ☀️ : 🌙
            var label = theme === "dark" ? "Switch to light mode" : "Switch to dark mode";
            btn.textContent = icon;
            btn.setAttribute("aria-label", label);
            btn.setAttribute("title", label);
        }

        sync();

        btn.addEventListener("click", function () {
            var next = current() === "dark" ? "light" : "dark";
            document.documentElement.setAttribute("data-theme", next);
            try {
                localStorage.setItem("theme", next);
            } catch (e) {
                // localStorage unavailable (private mode, etc.) - theme still applies for this page load
            }
            sync();
        });
    }

    function initPasswordToggles() {
        var toggles = document.querySelectorAll(".toggle-password");
        toggles.forEach(function (toggle) {
            var targetId = toggle.getAttribute("data-target");
            var input = targetId ? document.getElementById(targetId) : null;
            if (!input) return;

            toggle.innerHTML = EYE_OPEN;
            toggle.setAttribute("aria-label", "Show password");

            toggle.addEventListener("click", function () {
                var willShow = input.type === "password";
                input.type = willShow ? "text" : "password";
                toggle.innerHTML = willShow ? EYE_OFF : EYE_OPEN;
                toggle.setAttribute("aria-label", willShow ? "Hide password" : "Show password");
            });
        });
    }

    function initLeaveDayCalculator() {
        var startInput = document.getElementById("start_date");
        var endInput = document.getElementById("end_date");
        var daysInput = document.getElementById("num_days");
        if (!startInput || !endInput || !daysInput) return;

        function update() {
            if (startInput.value) {
                endInput.min = startInput.value;
            }

            if (!startInput.value || !endInput.value) {
                daysInput.value = "";
                endInput.setCustomValidity("");
                return;
            }

            var start = new Date(startInput.value + "T00:00:00");
            var end = new Date(endInput.value + "T00:00:00");

            if (end < start) {
                daysInput.value = "";
                endInput.setCustomValidity("End date cannot be before the start date.");
                return;
            }

            endInput.setCustomValidity("");
            var diffDays = Math.round((end - start) / 86400000) + 1;
            daysInput.value = diffDays + (diffDays === 1 ? " day" : " days");
        }

        startInput.addEventListener("change", update);
        endInput.addEventListener("input", update);
        update();
    }

    function initNavDropdowns() {
        var dropdowns = document.querySelectorAll(".nav-dropdown");
        dropdowns.forEach(function (dropdown) {
            var toggle = dropdown.querySelector(".nav-dropdown-toggle");
            var menu = dropdown.querySelector(".nav-dropdown-menu");
            if (!toggle || !menu) return;

            toggle.addEventListener("click", function (e) {
                e.stopPropagation();
                var isOpen = !menu.hidden;
                document.querySelectorAll(".nav-dropdown-menu").forEach(function (m) { m.hidden = true; });
                menu.hidden = isOpen;
            });
        });

        document.addEventListener("click", function () {
            document.querySelectorAll(".nav-dropdown-menu").forEach(function (m) { m.hidden = true; });
        });

        document.addEventListener("keydown", function (e) {
            if (e.key === "Escape") {
                document.querySelectorAll(".nav-dropdown-menu").forEach(function (m) { m.hidden = true; });
            }
        });
    }

    function initPasswordConfirmation() {
        var password = document.getElementById("password");
        var confirm = document.getElementById("confirm_password");
        if (!password || !confirm) return;

        function check() {
            confirm.setCustomValidity(confirm.value && confirm.value !== password.value ? "Passwords do not match." : "");
        }

        password.addEventListener("input", check);
        confirm.addEventListener("input", check);
    }

    document.addEventListener("DOMContentLoaded", function () {
        initThemeToggle();
        initPasswordToggles();
        initLeaveDayCalculator();
        initNavDropdowns();
        initPasswordConfirmation();
    });
})();

// Lightweight toast notifications, usable from any page's inline scripts
// (e.g. the QR scan result) without a full page reload / server-rendered flash.
window.showToast = function (message, type, duration) {
    var container = document.getElementById("toast-container");
    if (!container) return;

    var toast = document.createElement("div");
    toast.className = "toast" + (type ? " toast-" + type : "");
    toast.textContent = message;
    container.appendChild(toast);

    window.setTimeout(function () {
        toast.remove();
    }, duration || 4500);
};
