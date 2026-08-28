const reduceMotion = window.matchMedia("(prefers-reduced-motion: reduce)").matches;
const sections = [...document.querySelectorAll("main > section, main > .ticker, body > .footer-kicker")];
const itemSelector = ".card, .loop-step, .boundary-row, .build-col, .exp, .authority-graph, .panel";

for (const section of sections) {
  section.classList.add("motion-section");
  [...section.querySelectorAll(itemSelector)].forEach((item, index) => {
    item.classList.add("motion-item");
    item.style.setProperty("--motion-order", String(index));
  });
}

document.documentElement.classList.add("motion-ready");

const revealHashTarget = () => {
  if (!location.hash) return;
  const target = document.querySelector(location.hash);
  target?.closest(".motion-section")?.classList.add("is-visible");
};

if (reduceMotion || !("IntersectionObserver" in window)) {
  sections.forEach((section) => section.classList.add("is-visible"));
} else {
  const observer = new IntersectionObserver((entries) => {
    for (const entry of entries) {
      entry.target.classList.toggle("is-visible", entry.isIntersecting);
    }
  }, { threshold: 0.14, rootMargin: "0px 0px -10% 0px" });
  sections.forEach((section) => observer.observe(section));
  revealHashTarget();
  window.addEventListener("hashchange", revealHashTarget);
}
