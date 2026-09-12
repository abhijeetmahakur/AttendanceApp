(function () {
  "use strict";

  var FEATURES = [
    {
      tag: "#TimeWindows",
      titleLine1: "TIME-WINDOWED",
      titleLine2: "ATTENDANCE",
      desc: "Admins set the exact open/close window for each class - attendance can only be marked while it's live.",
      img: "https://images.unsplash.com/photo-1523240795612-9a054b0db644?w=800&q=80&auto=format&fit=crop",
      ctaText: "Admin Login",
      ctaUrl: "/login",
    },
    {
      tag: "#RegNoAccess",
      titleLine1: "REGISTRATION NUMBER",
      titleLine2: "LOGIN",
      desc: "Every student signs in with their own registration number and password - no shared logins, no confusion.",
      img: "https://images.unsplash.com/photo-1522202176988-66273c2fd55f?w=800&q=80&auto=format&fit=crop",
      ctaText: "Student Login",
      ctaUrl: "/login",
    },
    {
      tag: "#AutoAlerts",
      titleLine1: "INSTANT EMAIL",
      titleLine2: "SUMMARIES",
      desc: "The moment attendance is marked, students get an email with their live percentage - automatically, every time.",
      img: "https://images.unsplash.com/photo-1571260899304-425eee4c7efc?w=800&q=80&auto=format&fit=crop",
      ctaText: "See How",
      ctaUrl: "/login",
    },
    {
      tag: "#SmartTracking",
      titleLine1: "75% THRESHOLD",
      titleLine2: "GUIDANCE",
      desc: "Falling behind? The system tells students exactly how many classes in a row they need to attend to recover.",
      img: "https://images.unsplash.com/photo-1509062522246-3755977927d7?w=800&q=80&auto=format&fit=crop",
      ctaText: "Learn More",
      ctaUrl: "/login",
    },
    {
      tag: "#DualPanels",
      titleLine1: "ADMIN & STUDENT",
      titleLine2: "DASHBOARDS",
      desc: "Separate, focused panels - admins manage rosters and sessions, students track their own attendance.",
      img: "https://images.unsplash.com/photo-1524178232363-1fb2b075b655?w=800&q=80&auto=format&fit=crop",
      ctaText: "Get Started",
      ctaUrl: "/login",
    },
  ];

  var CHEVRON_LEFT =
    '<svg width="20" height="20" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="2.5"><path stroke-linecap="round" stroke-linejoin="round" d="M15 19l-7-7 7-7" /></svg>';
  var CHEVRON_RIGHT =
    '<svg width="20" height="20" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="2.5"><path stroke-linecap="round" stroke-linejoin="round" d="M9 5l7 7-7 7" /></svg>';
  var ARROW_RIGHT =
    '<svg width="13" height="13" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="2.5"><path stroke-linecap="round" stroke-linejoin="round" d="M14 5l7 7m0 0l-7 7m7-7H3" /></svg>';

  function initCoverflow(root) {
    var items = FEATURES;
    var total = items.length;
    var currentIndex = 0;
    var autoplayDelay = 5000;
    var autoplayTimer = null;
    var hovered = false;
    var touchStartX = 0;

    var bgImg = root.querySelector(".coverflow-bg img");
    var stage = root.querySelector(".coverflow-stage");
    var dotsWrap = root.querySelector(".coverflow-dots");
    var prevBtn = root.querySelector(".coverflow-arrow.prev");
    var nextBtn = root.querySelector(".coverflow-arrow.next");

    function offsetLayout(offset) {
      if (offset === 0) {
        return {
          transform: "translateX(0px) scale(1) rotateY(0deg)",
          opacity: 1,
          zIndex: 30,
          filter: "brightness(1)",
          isCenter: true,
        };
      }
      if (offset === 1) {
        return {
          transform: "translateX(285px) scale(0.84) rotateY(-24deg)",
          opacity: 0.65,
          zIndex: 20,
          filter: "brightness(0.75)",
          isCenter: false,
        };
      }
      if (offset === 2) {
        return {
          transform: "translateX(510px) scale(0.68) rotateY(-38deg)",
          opacity: 0.38,
          zIndex: 10,
          filter: "brightness(0.55) blur(1px)",
          isCenter: false,
        };
      }
      if (offset === total - 1) {
        return {
          transform: "translateX(-285px) scale(0.84) rotateY(24deg)",
          opacity: 0.65,
          zIndex: 20,
          filter: "brightness(0.75)",
          isCenter: false,
        };
      }
      if (offset === total - 2) {
        return {
          transform: "translateX(-510px) scale(0.68) rotateY(38deg)",
          opacity: 0.38,
          zIndex: 10,
          filter: "brightness(0.55) blur(1px)",
          isCenter: false,
        };
      }
      return {
        transform: "translateX(0px) scale(0.4) rotateY(0deg)",
        opacity: 0,
        zIndex: 0,
        filter: "brightness(0.4) blur(2px)",
        isCenter: false,
      };
    }

    function render() {
      bgImg.src = items[currentIndex].img;

      var cards = stage.querySelectorAll(".coverflow-card");
      cards.forEach(function (card) {
        var idx = parseInt(card.getAttribute("data-idx"), 10);
        var offset = (idx - currentIndex + total) % total;
        var layout = offsetLayout(offset);

        card.style.transform = layout.transform;
        card.style.opacity = layout.opacity;
        card.style.zIndex = layout.zIndex;
        card.style.filter = layout.filter;
        card.classList.toggle("is-center", layout.isCenter);
      });

      var dots = dotsWrap.querySelectorAll("button");
      dots.forEach(function (dot, idx) {
        dot.classList.toggle("active", idx === currentIndex);
      });
    }

    function goTo(idx) {
      currentIndex = ((idx % total) + total) % total;
      render();
    }

    function next() {
      goTo(currentIndex + 1);
    }

    function prev() {
      goTo(currentIndex - 1);
    }

    function startAutoplay() {
      stopAutoplay();
      if (hovered || total <= 1) return;
      autoplayTimer = setInterval(next, autoplayDelay);
    }

    function stopAutoplay() {
      if (autoplayTimer) {
        clearInterval(autoplayTimer);
        autoplayTimer = null;
      }
    }

    // Build cards
    items.forEach(function (item, idx) {
      var card = document.createElement("div");
      card.className = "coverflow-card";
      card.setAttribute("data-idx", String(idx));
      card.innerHTML =
        '<img class="card-photo" src="' + item.img + '" alt="' + item.titleLine1 + '">' +
        '<div class="card-vignette"></div>' +
        '<div class="card-content">' +
        '<div class="card-tag">' + (item.tag || "") + "</div>" +
        '<div class="card-body">' +
        "<h2>" + item.titleLine1 + "</h2>" +
        (item.titleLine2 ? '<span class="line2">' + item.titleLine2 + "</span>" : "") +
        '<div class="rule"></div>' +
        (item.desc ? "<p>" + item.desc + "</p>" : "") +
        '<a class="card-cta" href="' + (item.ctaUrl || "#") + '">' +
        "<span>" + (item.ctaText || "Learn More") + "</span>" + ARROW_RIGHT +
        "</a>" +
        "</div></div>";

      card.addEventListener("click", function () {
        var thisIdx = parseInt(card.getAttribute("data-idx"), 10);
        if (thisIdx !== currentIndex) goTo(thisIdx);
      });

      stage.appendChild(card);
    });

    // Build dots
    items.forEach(function (_, idx) {
      var dot = document.createElement("button");
      dot.type = "button";
      dot.setAttribute("aria-label", "Go to slide " + (idx + 1));
      dot.addEventListener("click", function () {
        goTo(idx);
      });
      dotsWrap.appendChild(dot);
    });

    prevBtn.innerHTML = CHEVRON_LEFT;
    nextBtn.innerHTML = CHEVRON_RIGHT;
    prevBtn.addEventListener("click", prev);
    nextBtn.addEventListener("click", next);

    root.addEventListener("mouseenter", function () {
      hovered = true;
      startAutoplay();
    });
    root.addEventListener("mouseleave", function () {
      hovered = false;
      startAutoplay();
    });

    root.addEventListener("touchstart", function (e) {
      touchStartX = e.touches[0].clientX;
    });
    root.addEventListener("touchend", function (e) {
      var diff = e.changedTouches[0].clientX - touchStartX;
      if (Math.abs(diff) > 45) {
        if (diff < 0) next();
        else prev();
      }
    });

    document.addEventListener("keydown", function (e) {
      if (e.key === "ArrowLeft") prev();
      if (e.key === "ArrowRight") next();
    });

    render();
    startAutoplay();
  }

  document.addEventListener("DOMContentLoaded", function () {
    var root = document.querySelector("[data-coverflow]");
    if (root) initCoverflow(root);
  });
})();
