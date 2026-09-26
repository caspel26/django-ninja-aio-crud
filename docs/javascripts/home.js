// Homepage interactions: operation demo, linked fields, sync/async tabs, install copy.
(() => {
  const moveThumb = (tablist) => {
    const selected = tablist.querySelector('[aria-selected="true"]');
    if (!selected) return;
    tablist.style.setProperty("--thumb-x", `${selected.offsetLeft}px`);
    tablist.style.setProperty("--thumb-w", `${selected.offsetWidth}px`);
  };

  const selectTab = (tablist, button) => {
    tablist.querySelectorAll('[role="tab"]').forEach((tab) => {
      const active = tab === button;
      tab.setAttribute("aria-selected", String(active));
      tab.tabIndex = active ? 0 : -1;
    });
    moveThumb(tablist);
  };

  const setupDemo = (demo) => {
    const tablist = demo.querySelector('[role="tablist"]');
    const choose = (op) => {
      demo.dataset.activeOp = op;
      const button = tablist.querySelector(`[data-op="${op}"]`);
      selectTab(tablist, button);
      demo.querySelectorAll("[data-op-panel]").forEach((panel) => {
        panel.hidden = panel.dataset.opPanel !== op;
      });
      demo.querySelectorAll("[data-kind-line]").forEach((line) => {
        line.classList.toggle("is-used", line.dataset.kindLine === button.dataset.kind);
      });
    };
    tablist.addEventListener("click", (event) => {
      const tab = event.target.closest("[data-op]");
      if (tab) choose(tab.dataset.op);
    });
    tablist.addEventListener("keydown", (event) => {
      if (!["ArrowLeft", "ArrowRight"].includes(event.key)) return;
      const tabs = [...tablist.querySelectorAll("[data-op]")];
      const index = tabs.indexOf(document.activeElement);
      const next = tabs[(index + (event.key === "ArrowRight" ? 1 : -1) + tabs.length) % tabs.length];
      choose(next.dataset.op);
      next.focus();
    });

    const link = (event) => {
      const field = event.target.closest("[data-field]")?.dataset.field;
      demo.querySelectorAll("[data-field]").forEach((node) => {
        node.classList.toggle("is-linked", node.dataset.field === field);
      });
    };
    demo.addEventListener("mouseover", link);
    demo.addEventListener("focusin", link);
    demo.addEventListener("mouseleave", () =>
      demo.querySelectorAll(".is-linked").forEach((node) => node.classList.remove("is-linked")),
    );
    choose(demo.dataset.activeOp || "list");
  };

  const setupModeTabs = (card) => {
    const tablist = card.querySelector('[role="tablist"]');
    const choose = (mode) => {
      selectTab(tablist, tablist.querySelector(`[data-tab="${mode}"]`));
      card.querySelectorAll("[data-panel]").forEach((panel) => {
        panel.hidden = panel.dataset.panel !== mode;
      });
      localStorage.setItem("nac-mode", mode);
    };
    tablist.addEventListener("click", (event) => {
      const tab = event.target.closest("[data-tab]");
      if (tab) choose(tab.dataset.tab);
    });
    choose(localStorage.getItem("nac-mode") || "sync");
  };

  const setupCopy = (button) => {
    const state = button.querySelector(".nac-install__state");
    button.addEventListener("click", () => {
      navigator.clipboard?.writeText(button.dataset.nacCopy);
      button.dataset.state = "copied";
      state.textContent = "Copied";
      setTimeout(() => {
        delete button.dataset.state;
        state.textContent = "Copy";
      }, 1400);
    });
  };

  const init = () => {
    const home = document.querySelector(".nac-home");
    if (!home) return;
    home.querySelectorAll(".nac-demo").forEach(setupDemo);
    home.querySelectorAll("[data-nac-tabs]").forEach(setupModeTabs);
    home.querySelectorAll("[data-nac-copy]").forEach(setupCopy);
    document.fonts?.ready.then(() => home.querySelectorAll(".nac-seg").forEach(moveThumb));
  };

  window.addEventListener("resize", () => document.querySelectorAll(".nac-seg").forEach(moveThumb));
  if (typeof document$ !== "undefined") {
    document$.subscribe(init);
  } else {
    document.addEventListener("DOMContentLoaded", init);
  }
})();
