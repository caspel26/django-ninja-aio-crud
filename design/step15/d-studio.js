(() => {
  const PAGES = [
    ["Installation", "Get started"],
    ["Quickstart", "Get started"],
    ["Choosing a serializer", "Get started"],
    ["Models and schemas", "Tutorial"],
    ["CRUD API", "Tutorial"],
    ["Relations", "Tutorial"],
    ["Authentication", "Tutorial"],
    ["Permissions", "Tutorial"],
    ["Filtering and pagination", "Tutorial"],
    ["Ready for production", "Tutorial"],
    ["Declare schemas", "Guides", "guide.html?d=d"],
    ["Validation", "Guides"],
    ["Using serializers in Python", "Guides"],
    ["Dumping objects", "Guides"],
    ["Nested writes", "Guides"],
    ["Bulk operations", "Guides"],
    ["Query optimization", "Guides"],
    ["ViewSets", "Guides"],
    ["Custom actions", "Guides"],
    ["Filtering and search", "Guides"],
    ["Field selection", "Guides"],
    ["Soft delete", "Guides"],
    ["JWT authentication", "Guides"],
    ["Cookie authentication", "Guides"],
    ["Hooks", "Guides"],
    ["Errors", "Guides"],
    ["AI agents (MCP)", "Guides"],
    ["Sync and async", "Concepts"],
    ["Request and operation lifecycle", "Concepts"],
    ["Transactions", "Concepts"],
    ["ModelSerializer", "Reference"],
    ["Serializer", "Reference"],
    ["SchemaConfig", "Reference"],
    ["APIViewSet", "Reference"],
    ["Settings", "Reference"],
    ["Deprecations and replacements", "Migration"],
    ["Breaking changes", "Migration"],
  ];

  const setupPalette = () => {
    const dialog = document.querySelector(".palette");
    if (!dialog) return;
    const input = dialog.querySelector("input");
    const list = dialog.querySelector("ul");
    let active = 0;

    const render = () => {
      const query = input.value.trim().toLowerCase();
      const matches = PAGES.filter(([title, section]) =>
        `${title} ${section}`.toLowerCase().includes(query),
      ).slice(0, 8);
      active = Math.min(active, Math.max(matches.length - 1, 0));
      list.replaceChildren(
        ...matches.map(([title, section, href], index) => {
          const item = document.createElement("li");
          item.setAttribute("role", "option");
          item.setAttribute("aria-selected", String(index === active));
          const link = document.createElement("a");
          link.href = href || "#";
          link.innerHTML = `<span>${title}</span><small>${section}</small>`;
          item.append(link);
          return item;
        }),
      );
      if (!matches.length) {
        const empty = document.createElement("li");
        empty.className = "palette-empty";
        empty.textContent = `No pages match "${input.value}"`;
        list.append(empty);
      }
    };

    const open = () => {
      input.value = "";
      active = 0;
      render();
      dialog.showModal();
      input.focus();
    };

    document.querySelectorAll("[data-palette-open]").forEach((button) =>
      button.addEventListener("click", open),
    );
    dialog.addEventListener("click", (event) => {
      if (event.target === dialog) dialog.close();
    });
    input.addEventListener("input", () => {
      active = 0;
      render();
    });
    input.addEventListener("keydown", (event) => {
      const options = list.querySelectorAll('[role="option"]');
      if (event.key === "ArrowDown" || event.key === "ArrowUp") {
        event.preventDefault();
        const step = event.key === "ArrowDown" ? 1 : -1;
        active = (active + step + options.length) % options.length;
        options.forEach((option, index) =>
          option.setAttribute("aria-selected", String(index === active)),
        );
        options[active]?.scrollIntoView({ block: "nearest" });
      } else if (event.key === "Enter") {
        options[active]?.querySelector("a")?.click();
      }
    });
    document.addEventListener("keydown", (event) => {
      const typing = /^(INPUT|TEXTAREA)$/.test(document.activeElement?.tagName);
      if ((event.key === "k" && (event.metaKey || event.ctrlKey)) || (event.key === "/" && !typing)) {
        event.preventDefault();
        dialog.open ? dialog.close() : open();
      }
    });
  };

  // Segmented controls: a thumb element slides under the selected tab.
  const updateThumbs = () => {
    document.querySelectorAll(".seg").forEach((tablist) => {
      const selected = tablist.querySelector('[aria-selected="true"]');
      if (!selected) return;
      tablist.style.setProperty("--thumb-x", `${selected.offsetLeft}px`);
      tablist.style.setProperty("--thumb-w", `${selected.offsetWidth}px`);
    });
  };

  // Demo: one operation at a time; hovering a field lights it up in every pane.
  const setupDemo = () => {
    const demo = document.querySelector(".demo");
    if (!demo) return;

    const selectOp = (op) => {
      demo.dataset.activeOp = op;
      demo.querySelectorAll("[data-op]").forEach((tab) => {
        const active = tab.dataset.op === op;
        tab.setAttribute("aria-selected", String(active));
        tab.tabIndex = active ? 0 : -1;
      });
      demo.querySelectorAll("[data-op-panel]").forEach((panel) => {
        panel.hidden = panel.dataset.opPanel !== op;
      });
      const kind = demo.querySelector(`[data-op="${op}"]`).dataset.kind;
      demo.querySelectorAll("[data-kind-line]").forEach((line) => {
        line.classList.toggle("is-used", line.dataset.kindLine === kind);
      });
      updateThumbs();
    };

    demo.addEventListener("click", (event) => {
      const tab = event.target.closest("[data-op]");
      if (tab) selectOp(tab.dataset.op);
    });
    demo.addEventListener("keydown", (event) => {
      const tab = event.target.closest("[data-op]");
      if (!tab || !["ArrowLeft", "ArrowRight"].includes(event.key)) return;
      const tabs = [...demo.querySelectorAll("[data-op]")];
      const step = event.key === "ArrowRight" ? 1 : -1;
      const next = tabs[(tabs.indexOf(tab) + step + tabs.length) % tabs.length];
      selectOp(next.dataset.op);
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

    selectOp(demo.dataset.activeOp || "list");
  };

  const setupScrollSpy = () => {
    const links = new Map(
      [...document.querySelectorAll(".doc-toc a[href^='#']")].map((a) => [a.hash.slice(1), a]),
    );
    if (!links.size) return;
    const observer = new IntersectionObserver(
      (entries) => {
        entries
          .filter((entry) => entry.isIntersecting)
          .forEach((entry) => {
            links.forEach((a) => a.removeAttribute("aria-current"));
            links.get(entry.target.id)?.setAttribute("aria-current", "location");
          });
      },
      { rootMargin: "-20% 0px -70% 0px" },
    );
    links.forEach((_, id) => {
      const heading = document.getElementById(id);
      if (heading) observer.observe(heading);
    });
  };

  const VERSIONS = {
    "3.0": null,
    dev: "<strong>Development docs.</strong> <span>They describe the <code>main</code> branch and may cover unreleased features.</span> <a href=\"#\">Read the 3.0 docs</a>",
    "2.36": "<strong>You are reading the 2.36 docs.</strong> <span>Version 3.0 is the latest release.</span> <a href=\"#\">Go to 3.0</a> <a href=\"#\">Migration guide</a>",
    "2.35": "<strong>You are reading the 2.35 docs.</strong> <span>Version 3.0 is the latest release.</span> <a href=\"#\">Go to 3.0</a> <a href=\"#\">Migration guide</a>",
    "2.34": "<strong>You are reading the 2.34 docs.</strong> <span>Version 3.0 is the latest release.</span> <a href=\"#\">Go to 3.0</a> <a href=\"#\">Migration guide</a>",
  };

  // Mirrors the mike version selector: switching version shows the banner for non-latest docs.
  const setupVersions = () => {
    const button = document.querySelector(".version-button");
    const list = document.querySelector(".version-list");
    const banner = document.querySelector(".version-banner");
    if (!button || !list) return;
    const items = [...list.querySelectorAll("[data-version]")];

    const apply = (version) => {
      items.forEach((item) => item.setAttribute("aria-checked", String(item.dataset.version === version)));
      button.querySelector(".version-current").textContent = version === "dev" ? "dev" : `v${version}`;
      if (banner) {
        banner.innerHTML = VERSIONS[version] || "";
        banner.hidden = !VERSIONS[version];
      }
      sessionStorage.setItem("nac-version", version);
    };
    const close = (focusButton) => {
      list.hidden = true;
      button.setAttribute("aria-expanded", "false");
      if (focusButton) button.focus();
    };
    const open = () => {
      list.hidden = false;
      button.setAttribute("aria-expanded", "true");
      (items.find((item) => item.getAttribute("aria-checked") === "true") || items[0]).focus();
    };

    button.addEventListener("click", () => (list.hidden ? open() : close(false)));
    items.forEach((item) =>
      item.addEventListener("click", () => {
        apply(item.dataset.version);
        close(true);
      }),
    );
    list.addEventListener("keydown", (event) => {
      const index = items.indexOf(document.activeElement);
      if (event.key === "Escape") close(true);
      if (event.key === "ArrowDown" || event.key === "ArrowUp") {
        event.preventDefault();
        const step = event.key === "ArrowDown" ? 1 : -1;
        items[(index + step + items.length) % items.length].focus();
      }
    });
    document.addEventListener("click", (event) => {
      if (!list.hidden && !event.target.closest(".version-menu")) close(false);
    });

    apply(sessionStorage.getItem("nac-version") || "3.0");
  };

  document.addEventListener("DOMContentLoaded", () => {
    setupPalette();
    setupDemo();
    setupScrollSpy();
    setupVersions();
    updateThumbs();
    document.addEventListener("click", () => requestAnimationFrame(updateThumbs));
    document.addEventListener("keydown", () => requestAnimationFrame(updateThumbs));
    window.addEventListener("resize", updateThumbs);
    document.fonts?.ready.then(updateThumbs);

    const header = document.querySelector(".site-header");
    const onScroll = () => header?.classList.toggle("is-scrolled", window.scrollY > 4);
    window.addEventListener("scroll", onScroll, { passive: true });
    onScroll();
  });
})();
