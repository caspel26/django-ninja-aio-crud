import AxeBuilder from "@axe-core/playwright";
import { expect, test, type Page } from "@playwright/test";

const PAGES = {
  home: "/",
  installation: "/getting_started/installation/",
  tutorial: "/tutorial/crud/",
  reference: "/api/models/model_serializer/",
  releases: "/release_notes/",
  patterns: "/v3-components/",
};

const SCHEMES = { dark: "slate", light: "default" } as const;

async function open(page: Page, path: string, scheme: string) {
  await page.goto(path);
  await page.evaluate((value) => document.body.setAttribute("data-md-color-scheme", value), scheme);
  await page.evaluate(() => document.fonts.ready);
  // Link and surface colors transition; measure the settled values.
  await page.waitForTimeout(400);
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
