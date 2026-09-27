// Scrollable code blocks and tables must be reachable by keyboard (WCAG 2.1.1).
(() => {
  const SELECTOR = ".md-typeset pre > code, .md-typeset__scrollwrap";

  const update = () => {
    document.querySelectorAll(SELECTOR).forEach((el) => {
      const scrollable = el.scrollWidth > el.clientWidth;
      if (scrollable && !el.hasAttribute("tabindex")) {
        el.tabIndex = 0;
        el.dataset.nacFocusable = "";
      } else if (!scrollable && "nacFocusable" in el.dataset) {
        el.removeAttribute("tabindex");
        delete el.dataset.nacFocusable;
      }
    });
  };

  // document$ fires on every instant-navigation page load; fall back to a plain load.
  if (typeof document$ !== "undefined") {
    document$.subscribe(update);
  } else {
    document.addEventListener("DOMContentLoaded", update);
  }
  window.addEventListener("resize", update, { passive: true });
})();
