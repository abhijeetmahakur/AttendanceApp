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

    document.addEventListener("DOMContentLoaded", function () {
        initThemeToggle();
        initPasswordToggles();
    });
})();
