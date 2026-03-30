// FTU Labs — Main JS

if ("serviceWorker" in navigator) {
  navigator.serviceWorker.register("/sw.js");
}

document.addEventListener("DOMContentLoaded", () => {
  // --- Theme toggle ---
  const saved = localStorage.getItem("ftu-theme");
  if (saved) {
    document.documentElement.setAttribute("data-theme", saved);
  }

  document.querySelectorAll(".theme-toggle").forEach((btn) => {
    btn.addEventListener("click", () => {
      const current = document.documentElement.getAttribute("data-theme");
      const next = current === "light" ? "dark" : "light";
      if (next === "dark") {
        document.documentElement.removeAttribute("data-theme");
      } else {
        document.documentElement.setAttribute("data-theme", next);
      }
      localStorage.setItem("ftu-theme", next);
    });
  });

  // --- Mobile navigation toggle ---
  const toggle = document.querySelector(".nav-toggle");
  const mobile = document.querySelector(".nav-mobile");

  if (toggle && mobile) {
    toggle.addEventListener("click", () => {
      toggle.classList.toggle("open");
      mobile.classList.toggle("open");
    });

    mobile.querySelectorAll("a").forEach((link) => {
      link.addEventListener("click", () => {
        toggle.classList.remove("open");
        mobile.classList.remove("open");
      });
    });
  }

  // --- Scroll reveal (IntersectionObserver) ---
  const reveals = document.querySelectorAll(".reveal");

  if (reveals.length) {
    const observer = new IntersectionObserver(
      (entries) => {
        entries.forEach((entry, i) => {
          if (entry.isIntersecting) {
            // Stagger reveals that enter together
            setTimeout(() => {
              entry.target.classList.add("visible");
            }, i * 60);
            observer.unobserve(entry.target);
          }
        });
      },
      { threshold: 0.08, rootMargin: "0px 0px -30px 0px" },
    );

    reveals.forEach((el) => observer.observe(el));
  }

  // --- Active nav link highlight ---
  const path = window.location.pathname;
  const filename = path.substring(path.lastIndexOf("/") + 1) || "index.html";

  document.querySelectorAll(".nav-links a, .nav-mobile a").forEach((link) => {
    const href = link.getAttribute("href");
    if (!href) return;

    const linkFile = href.replace("./", "").replace("../", "");

    if (
      filename === linkFile ||
      (filename === "" && linkFile === "index.html")
    ) {
      link.classList.add("active");
    }
  });
});
