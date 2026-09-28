import AxeBuilder from "@axe-core/playwright";
import { expect, test, type Page } from "@playwright/test";

const PAGES = {
  home: "/",
  installation: "/getting_started/installation/",
  tutorial: "/tutorial/crud/",
  guide: "/guides/relations/",
  concept: "/concepts/lifecycle/",
  reference: "/api/models/model_serializer/",
  migration: "/migration/breaking-changes/",
  releases: "/release_notes/",
};

const SCHEMES = { dark: "slate", light: "default" } as const;

async function open(page: Page, path: string, scheme: string) {
  await page.goto(path);
  await page.evaluate((value) => document.body.setAttribute("data-md-color-scheme", value), scheme);
  await page.evaluate(() => document.fonts.ready);
  // Link and surface colors transition; measure the settled values.
  await page.evaluate(async () => {
    const animations = document.getAnimations().filter((animation) =>
      animation.effect instanceof KeyframeEffect && animation.effect.target === document.body,
    );
    await Promise.all(animations.map((animation) => animation.finished.catch(() => undefined)));
  });
}

for (const [name, path] of Object.entries(PAGES)) {
  for (const [theme, scheme] of Object.entries(SCHEMES)) {
    test(`${name} ${theme} matches the visual baseline`, async ({ page }) => {
      await open(page, path, scheme);
      // Remote badges and the GitHub star/fork counts change independently of the theme.
      await expect(page).toHaveScreenshot(`${name}-${theme}.png`, {
        mask: [page.locator(".badges img"), page.locator(".md-source__facts")],
      });
    });

    test(`${name} ${theme} has no WCAG 2 AA violations`, async ({ page }) => {
      await open(page, path, scheme);
      // Theme-owned markup: search overlay (Shadow DOM), drawer overlay, code-annotation
      // markers, and the header's aria-labelled <label> toggles.
      await page.evaluate(() =>
        [...document.body.children].filter((el) => el.shadowRoot).forEach((el) => el.remove()),
      );
      const results = await new AxeBuilder({ page })
        .withTags(["wcag2a", "wcag2aa"])
        .exclude(".md-overlay")
        .exclude(".md-annotation__index")
        .exclude('label[for="__drawer"]')
        .exclude('label[for="__search"]')
        .analyze();
      const summary = results.violations.map(
        (v) =>
          `${v.id} (${v.nodes.length}): ${v.help} -> ` +
          v.nodes
            .slice(0, 3)
            .map((n) => `${n.target.join(" ")} [${n.failureSummary?.split("\n")[1]?.trim() ?? ""}]`)
            .join("; "),
      );
      expect(summary).toEqual([]);
    });
  }
}

test("header exposes a labelled theme toggle and search", async ({ page }) => {
  await page.goto(PAGES.installation);
  await expect(page.locator(".nac-brand")).toHaveAccessibleName("django-ninja-aio-crud");
  const search = page.locator('.md-header .md-search__button, .md-header label[for="__search"]');
  await expect(search.filter({ visible: true }).first()).toBeVisible();
  await expect(page.locator('.md-header__option label[for^="__palette"]').first()).toHaveAttribute("title", /Switch to/);
});

test("horizontally scrollable code is reachable by keyboard", async ({ page }) => {
  await page.goto(PAGES.tutorial);
  const unreachable = await page.evaluate(() =>
    [...document.querySelectorAll(".md-typeset pre > code, .md-typeset__scrollwrap")].filter(
      (el) => el.scrollWidth > el.clientWidth && (el as HTMLElement).tabIndex < 0,
    ).length,
  );
  expect(unreachable).toBe(0);
});

test("showcase response follows endpoint selection by pointer and keyboard", async ({ page }) => {
  await page.goto(PAGES.home);
  const response = page.locator("#nac-route-response");
  const status = response.locator(".nac-routes__status");
  const body = response.locator("pre code");
  const route = (example: string) => page.locator(`.nac-routes li[data-example="${example}"] button`);

  await expect(status).toHaveText("200 OK");
  await expect(body).toContainText('"count": 1');

  await route("create").click();
  await expect(route("create")).toHaveAttribute("aria-pressed", "true");
  await expect(route("list")).toHaveAttribute("aria-pressed", "false");
  await expect(status).toHaveText("201 Created");
  await expect(body).toContainText('"New article"');

  await route("retrieve").click();
  await expect(status).toHaveText("200 OK");
  await expect(body).toContainText('"Hello"');
  await expect(body).not.toContainText('"items"');

  await route("update").focus();
  await page.keyboard.press("Enter");
  await expect(body).toContainText('"Updated article"');

  await route("delete").focus();
  await page.keyboard.press("Space");
  await expect(status).toHaveText("204 No Content");
  await expect(body).toHaveText("No response body");
  await expect(route("delete")).toHaveAttribute("aria-pressed", "true");
});

test("release notes include the full history across major and patch versions", async ({ page }) => {
  await page.goto(PAGES.releases);
  const toggle = page.locator("#release-toggle");
  const menu = page.locator("#release-menu");
  for (const tag of ["v3.0.0", "v2.36.0", "v2.35.0", "v2.34.3", "v2.34.2", "v0.1.1"]) {
    await toggle.click();
    await menu.getByRole("button", { name: new RegExp(`^${tag.replaceAll(".", "\\.")}`) }).click();
    const card = page.locator(`.release-card[data-version="${tag.replaceAll(".", "-")}"]`);
    await expect(card).toBeVisible();
    await expect(card.locator(".release-card-body")).not.toContainText("No release notes for this version.");
  }
});
