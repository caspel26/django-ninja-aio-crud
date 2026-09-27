/* Theme behavior: version selector, header menus, scroll state, page motion, TOC marker. */
(() => {
  const reduceMotion = window.matchMedia("(prefers-reduced-motion: reduce)");

  function siteRoot() {
    if (window.__md_scope instanceof URL) return window.__md_scope;
    const logo = document.querySelector(".nac-brand");
    return new URL(logo ? logo.getAttribute("href") : "./", location.href);
  }

  async function fetchVersions(remote) {
    const scope = siteRoot();
    const sources = [
      { url: new URL("../versions.json", scope), base: new URL("../", scope) },
    ];
    if (remote) sources.push({ url: new URL("versions.json", remote), base: new URL(remote) });
    for (const source of sources) {
      try {
        const response = await fetch(source.url, { credentials: "omit" });
        if (!response.ok) continue;
        const versions = await response.json();
        if (Array.isArray(versions) && versions.length) return { versions, base: source.base };
      } catch (error) {
        /* Try the next source. */
      }
    }
    return null;
  }

  function versionItem(label, { href, badges = [], current = false } = {}) {
    const li = document.createElement("li");
    const node = document.createElement(href && !current ? "a" : "span");
    node.className = "nac-version__item" + (current ? " is-current" : "");
    if (href && !current) node.href = href;
    if (current) node.setAttribute("aria-current", "true");
    const name = document.createElement("span");
    name.textContent = label;
    node.append(name);
    for (const badge of badges) {
      const tag = document.createElement("span");
      tag.className = `nac-version__badge nac-version__badge--${badge}`;
      tag.textContent = badge;
      node.append(tag);
    }
    li.append(node);
    return li;
  }

  async function initVersion(root) {
    const widget = root.querySelector("[data-nac-version]");
    if (!widget || widget.dataset.ready) return;
    widget.dataset.ready = "1";
    const button = widget.querySelector(".nac-version__button");
    const menu = widget.querySelector(".nac-version__menu");
    const list = widget.querySelector(".nac-version__list");
    const label = widget.querySelector(".nac-version__label");

    const toggle = (open) => {
      const next = open ?? menu.hidden;
      menu.hidden = !next;
      button.setAttribute("aria-expanded", String(next));
      widget.classList.toggle("is-open", next);
    };
    button.addEventListener("click", (event) => {
      event.stopPropagation();
      toggle();
    });
    document.addEventListener("click", (event) => {
      if (!widget.contains(event.target)) toggle(false);
    });
    widget.addEventListener("keydown", (event) => {
      if (event.key === "Escape") {
        toggle(false);
        button.focus();
      }
    });

    const data = await fetchVersions(widget.dataset.remote);
    const scopeSegment = siteRoot().pathname.split("/").filter(Boolean).pop() || "";
    const configured = widget.dataset.current;
    const match = data?.versions.find(
      (v) => v.version === scopeSegment || (v.aliases || []).includes(scopeSegment),
    );
    const currentName = match ? match.title || match.version : configured;
    label.textContent = `v${currentName}`;

    if (!match) list.append(versionItem(configured, { badges: ["preview"], current: true }));
    for (const version of data?.versions || []) {
      const aliases = version.aliases || [];
      list.append(
        versionItem(version.title || version.version, {
          href: new URL(`${version.version}/`, data.base).href,
          badges: aliases.includes("latest") ? ["latest"] : [],
          current: match === version,
        }),
      );
    }
    if (!data) {
      const note = document.createElement("li");
      note.className = "nac-version__note";
      note.textContent = "Other versions are listed on the published site.";
      list.append(note);
    }
  }

  function initMenus(root) {
    for (const item of root.querySelectorAll(".nac-nav__item")) {
      if (item.dataset.ready) continue;
      item.dataset.ready = "1";
      let timer;
      const open = () => {
        clearTimeout(timer);
        for (const other of root.querySelectorAll(".nac-nav__item.is-open")) {
          if (other !== item) other.classList.remove("is-open");
        }
        item.classList.add("is-open");
      };
      const close = () => {
        timer = setTimeout(() => item.classList.remove("is-open"), 120);
      };
      item.addEventListener("pointerenter", open);
      item.addEventListener("pointerleave", close);
      item.addEventListener("focusin", open);
      item.addEventListener("focusout", (event) => {
        if (!item.contains(event.relatedTarget)) item.classList.remove("is-open");
      });
      item.addEventListener("keydown", (event) => {
        if (event.key === "Escape") {
          item.classList.remove("is-open");
          item.querySelector(".nac-nav__link").focus();
        }
      });
      for (const link of item.querySelectorAll("a")) {
        link.addEventListener("click", () => item.classList.remove("is-open"));
      }
    }
  }

  function initScrollState() {
    const header = document.querySelector(".nac-header");
    if (!header) return;
    const update = () => header.classList.toggle("is-scrolled", window.scrollY > 8);
    update();
    if (!window.__nacScrollBound) {
      window.__nacScrollBound = true;
      window.addEventListener("scroll", () => {
        const current = document.querySelector(".nac-header");
        if (current) current.classList.toggle("is-scrolled", window.scrollY > 8);
      }, { passive: true });
    }
  }

  function initSearchHint(root) {
    const button = root.querySelector(".md-search__button");
    if (!button || button.dataset.ready) return;
    button.dataset.ready = "1";
    const mac = /Mac|iPhone|iPad/.test(navigator.platform);
    const hint = document.createElement("kbd");
    hint.className = "nac-search__kbd";
    hint.textContent = mac ? "⌘K" : "Ctrl K";
    button.append(hint);
    if (!window.__nacSearchKey) {
      window.__nacSearchKey = true;
      document.addEventListener("keydown", (event) => {
        if ((event.metaKey || event.ctrlKey) && event.key.toLowerCase() === "k") {
          event.preventDefault();
          document.querySelector(".md-search__button")?.click();
        }
      });
    }
  }

  function initTocMarker() {
    const toc = document.querySelector(".md-sidebar--secondary .md-nav--secondary > .md-nav__list");
    if (!toc) return;
    let marker = toc.querySelector(".nac-toc-marker");
    if (!marker) {
      marker = document.createElement("span");
      marker.className = "nac-toc-marker";
      marker.setAttribute("aria-hidden", "true");
      toc.prepend(marker);
    }
    const place = () => {
      const active = toc.querySelector(".md-nav__link--active");
      if (!active) {
        marker.style.opacity = "0";
        return;
      }
      const listBox = toc.getBoundingClientRect();
      const box = active.getBoundingClientRect();
      marker.style.opacity = "1";
      marker.style.transform = `translateY(${box.top - listBox.top}px)`;
      marker.style.height = `${box.height}px`;
    };
    place();
    new MutationObserver(place).observe(toc, { subtree: true, attributes: true, attributeFilter: ["class"] });
  }

  function animateEntry() {
    if (reduceMotion.matches) return;
    const content = document.querySelector(".md-content__inner");
    if (!content) return;
    content.classList.remove("nac-enter");
    void content.offsetWidth;
    content.classList.add("nac-enter");
  }

  // The search dialog lives in a shadow root with minified class names, so match by structure.
  const EMPTY_SEARCH_CSS = `
    div:has(> div > div > div > input:placeholder-shown) { height: auto !important; align-self: flex-start !important; margin-top: 15vh !important; }
    div:has(> div > div > div > input:placeholder-shown) > :not(:first-child),
    div:has(> div > div > input:placeholder-shown) > :not(:first-child) { display: none !important; }
    div:has(> div > div > input:placeholder-shown) { height: auto !important; }
    div:has(> div > input:placeholder-shown) { border-bottom-color: transparent !important; }
  `;

  function styleSearchDialog() {
    for (const host of document.body.children) {
      const root = host.shadowRoot;
      if (!root || root.querySelector("style[data-nac]") || !root.querySelector("input")) continue;
      const style = document.createElement("style");
      style.dataset.nac = "";
      style.textContent = EMPTY_SEARCH_CSS;
      root.append(style);
    }
  }

  function initSearchDialog() {
    styleSearchDialog();
    if (window.__nacSearchObserver) return;
    window.__nacSearchObserver = new MutationObserver(styleSearchDialog);
    window.__nacSearchObserver.observe(document.body, { childList: true });
  }

  function init() {
    initVersion(document);
    initMenus(document);
    initScrollState();
    initSearchHint(document);
    initSearchDialog();
    initTocMarker();
    animateEntry();
  }

  if (window.document$ && typeof window.document$.subscribe === "function") {
    window.document$.subscribe(init);
  } else if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", init);
  } else {
    init();
  }
})();
