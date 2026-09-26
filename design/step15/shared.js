(() => {
  const root = document.documentElement;
  const stored = localStorage.getItem("nac-theme");
  const prefersDark = window.matchMedia("(prefers-color-scheme: dark)").matches;
  root.dataset.theme =
    stored || root.dataset.defaultTheme || (prefersDark ? "dark" : "light");

  const syncToggleLabels = () => {
    const next = root.dataset.theme === "dark" ? "light" : "dark";
    document.querySelectorAll("[data-theme-toggle]").forEach((button) => {
      button.setAttribute("aria-label", `Switch to ${next} theme`);
      const label = button.querySelector(".theme-label") || button;
      label.textContent = next === "dark" ? "Dark" : "Light";
    });
  };

  // Tab groups sharing a data-tabs kind ("mode", "style") switch together.
  const select = (kind, value) => {
    document.querySelectorAll(`[data-tabs="${kind}"]`).forEach((group) => {
      group.querySelectorAll("[data-tab]").forEach((tab) => {
        const active = tab.dataset.tab === value;
        tab.setAttribute("aria-selected", String(active));
        tab.tabIndex = active ? 0 : -1;
      });
      group.querySelectorAll("[data-panel]").forEach((panel) => {
        panel.hidden = panel.dataset.panel !== value;
      });
    });
    localStorage.setItem(`nac-tab-${kind}`, value);
  };

  document.addEventListener("DOMContentLoaded", () => {
    syncToggleLabels();
    const kinds = new Set(
      [...document.querySelectorAll("[data-tabs]")].map((g) => g.dataset.tabs),
    );
    kinds.forEach((kind) => {
      const first = document.querySelector(`[data-tabs="${kind}"] [data-tab]`);
      select(kind, localStorage.getItem(`nac-tab-${kind}`) || first.dataset.tab);
    });

    document.addEventListener("click", (event) => {
      if (event.target.closest("[data-theme-toggle]")) {
        root.dataset.theme = root.dataset.theme === "dark" ? "light" : "dark";
        localStorage.setItem("nac-theme", root.dataset.theme);
        syncToggleLabels();
        return;
      }
      const tab = event.target.closest("[data-tab]");
      if (tab) select(tab.closest("[data-tabs]").dataset.tabs, tab.dataset.tab);

      const copy = event.target.closest("[data-copy]");
      if (copy) {
        navigator.clipboard?.writeText(copy.dataset.copy);
        const label = copy.querySelector(".copy-state") || copy;
        copy.dataset.state = "copied";
        label.textContent = "Copied";
        setTimeout(() => {
          delete copy.dataset.state;
          label.textContent = "Copy";
        }, 1400);
      }
    });

    document.addEventListener("keydown", (event) => {
      const tab = event.target.closest("[data-tab]");
      if (!tab || !["ArrowLeft", "ArrowRight"].includes(event.key)) return;
      const tabs = [...tab.parentElement.querySelectorAll("[data-tab]")];
      const step = event.key === "ArrowRight" ? 1 : -1;
      const next = tabs[(tabs.indexOf(tab) + step + tabs.length) % tabs.length];
      select(tab.closest("[data-tabs]").dataset.tabs, next.dataset.tab);
      next.focus();
    });
  });
})();
