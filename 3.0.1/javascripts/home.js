(() => {
  const timers = [];
  const reduced = () => window.matchMedia("(prefers-reduced-motion: reduce)").matches;

  const setupReveal = (home) => {
    const targets = home.querySelectorAll("[data-reveal]");
    if (!("IntersectionObserver" in window)) {
      targets.forEach((el) => el.classList.add("is-visible"));
      return;
    }
    const observer = new IntersectionObserver(
      (entries) => {
        entries.forEach((entry) => {
          if (!entry.isIntersecting) return;
          entry.target.classList.add("is-visible");
          observer.unobserve(entry.target);
        });
      },
      { rootMargin: "0px 0px -8% 0px", threshold: 0.12 },
    );
    targets.forEach((el) => observer.observe(el));
  };

  const setupFileTabs = (showcase) => {
    const tabs = [...showcase.querySelectorAll("[data-file]")];
    const select = (tab, focus) => {
      tabs.forEach((other) => {
        const on = other === tab;
        other.setAttribute("aria-selected", String(on));
        other.tabIndex = on ? 0 : -1;
        showcase.querySelector(`[data-file-panel="${other.dataset.file}"]`).hidden = !on;
      });
      if (focus) tab.focus();
    };
    tabs.forEach((tab, index) => {
      tab.addEventListener("click", () => select(tab));
      tab.addEventListener("keydown", (event) => {
        const step = { ArrowRight: 1, ArrowLeft: -1 }[event.key];
        if (!step) return;
        event.preventDefault();
        select(tabs[(index + step + tabs.length) % tabs.length], true);
      });
    });
    return select;
  };

  const setupRoutes = (showcase, selectFile) => {
    const routes = [...showcase.querySelectorAll("[data-route]")];
    const modelsTab = showcase.querySelector('[data-file="models"]');
    const response = showcase.querySelector(".nac-routes__response");
    const status = response.querySelector(".nac-routes__status");
    const code = response.querySelector("pre code");
    const examples = {
      list: {
        status: "200 OK",
        body: '{\n  "items": [{ "id": 1, "title": "Hello", "body": "..." }],\n  "count": 1\n}',
      },
      create: {
        status: "201 Created",
        body: '{\n  "id": 2,\n  "title": "New article",\n  "body": "..."\n}',
      },
      retrieve: {
        status: "200 OK",
        body: '{\n  "id": 1,\n  "title": "Hello",\n  "body": "..."\n}',
      },
      update: {
        status: "200 OK",
        body: '{\n  "id": 1,\n  "title": "Updated article",\n  "body": "..."\n}',
      },
      delete: { status: "204 No Content", body: "No response body" },
    };
    let auto = !reduced();
    let index = 0;

    const link = (route) => {
      showcase.querySelectorAll(".is-linked").forEach((el) => el.classList.remove("is-linked"));
      if (!route) return;
      route.classList.add("is-linked");
      showcase.querySelector(`.hl[data-op="${route.dataset.route}"]`)?.classList.add("is-linked");
    };

    const renderResponse = (route) => {
      const example = examples[route.dataset.example];
      status.textContent = example.status;
      code.replaceChildren();
      if (route.dataset.example === "delete") {
        code.textContent = example.body;
      } else {
        const tokens = /"(?:\\.|[^"\\])*"|\b\d+\b/g;
        let end = 0;
        for (const match of example.body.matchAll(tokens)) {
          code.append(document.createTextNode(example.body.slice(end, match.index)));
          const token = document.createElement("span");
          token.className = match[0].startsWith('"') ? "s" : "m";
          token.textContent = match[0];
          code.append(token);
          end = match.index + match[0].length;
        }
        code.append(document.createTextNode(example.body.slice(end)));
      }
    };

    const show = (route) => {
      link(route);
      renderResponse(route);
      routes.forEach((other) => {
        other.querySelector("button").setAttribute("aria-pressed", String(other === route));
      });
    };

    routes.forEach((route) => {
      const select = () => {
        auto = false;
        if (modelsTab.getAttribute("aria-selected") !== "true") selectFile(modelsTab);
        show(route);
      };
      route.addEventListener("mouseenter", select);
      route.querySelector("button").addEventListener("click", select);
    });

    timers.push(
      setInterval(() => {
        if (!auto || !showcase.classList.contains("is-visible")) return;
        if (modelsTab.getAttribute("aria-selected") !== "true") return;
        show(routes[index % routes.length]);
        index += 1;
      }, 2200),
    );
  };

  const setupModeToggle = (toggle) => {
    if (reduced()) return;
    const [asyncOpt, syncOpt] = toggle.querySelectorAll(".nac-toggle__opt");
    timers.push(
      setInterval(() => {
        const sync = toggle.classList.toggle("is-sync");
        asyncOpt.classList.toggle("is-on", !sync);
        syncOpt.classList.toggle("is-on", sync);
      }, 2600),
    );
  };

  const setupSpotlight = (card) => {
    card.addEventListener("pointermove", (event) => {
      const rect = card.getBoundingClientRect();
      card.style.setProperty("--x", `${event.clientX - rect.left}px`);
      card.style.setProperty("--y", `${event.clientY - rect.top}px`);
    });
  };

  const setupCopy = (button) => {
    const state = button.querySelector(".nac-install__state");
    button.addEventListener("click", async () => {
      try {
        await navigator.clipboard.writeText(button.dataset.nacCopy);
      } catch {
        return;
      }
      button.classList.add("is-copied");
      state.textContent = "Copied";
      setTimeout(() => {
        button.classList.remove("is-copied");
        state.textContent = "Copy";
      }, 1400);
    });
  };

  const init = () => {
    timers.splice(0).forEach(clearInterval);
    const home = document.querySelector(".nac-home");
    if (!home) return;
    setupReveal(home);
    const showcase = home.querySelector(".nac-showcase");
    if (showcase) setupRoutes(showcase, setupFileTabs(showcase));
    home.querySelectorAll("[data-nac-mode]").forEach(setupModeToggle);
    home.querySelectorAll("[data-spotlight], .grid.cards > ul > li").forEach(setupSpotlight);
    home.querySelectorAll("[data-nac-copy]").forEach(setupCopy);
  };

  if (typeof document$ !== "undefined") {
    document$.subscribe(init);
  } else {
    document.addEventListener("DOMContentLoaded", init);
  }
})();
