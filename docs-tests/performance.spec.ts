import { expect, test } from "@playwright/test";

const PAGES = {
  home: "/",
  guide: "/guides/relations/",
  reference: "/api/models/model_serializer/",
};

// Decoded bytes on a cold navigation, independent of hosting compression.
const BUDGETS = {
  total: 1536 * 1024,
  document: 160 * 1024,
  script: 384 * 1024,
  stylesheet: 384 * 1024,
  font: 128 * 1024,
  image: 128 * 1024,
  requests: 40,
  domNodes: 3000,
};

for (const [name, path] of Object.entries(PAGES)) {
  test(`${name} stays within the cold-load performance budget`, async ({ page, baseURL }, testInfo) => {
    const origin = new URL(baseURL!).origin;
    const externalDependencies: string[] = [];
    const failedResources: string[] = [];
    // Third-party badges and repository counters are outside the site's budget.
    // Fonts, CSS, and scripts must remain self-hosted.
    await page.route("**/*", async (route) => {
      const request = route.request();
      if (new URL(request.url()).origin === origin) {
        await route.continue();
      } else {
        if (["font", "stylesheet", "script"].includes(request.resourceType())) {
          externalDependencies.push(request.url());
        }
        await route.abort();
      }
    });

    const resources: Promise<{ url: string; kind: string; bytes: number }>[] = [];
    page.on("response", (response) => {
      const url = new URL(response.url());
      if (url.origin !== origin) return;
      if (!response.ok()) {
        // Version metadata is only supplied by the deployed, versioned site.
        if (url.pathname !== "/versions.json") {
          failedResources.push(`${response.status()} ${response.url()}`);
        }
        return;
      }
      resources.push((async () => ({
        url: response.url(),
        kind: response.request().resourceType(),
        bytes: (await response.body()).length,
      }))());
    });
    page.on("requestfailed", (request) => {
      if (new URL(request.url()).origin === origin) {
        failedResources.push(`${request.failure()?.errorText} ${request.url()}`);
      }
    });

    const response = await page.goto(path);
    expect(response?.ok()).toBe(true);
    await page.evaluate(() => document.fonts.ready);
    await page.waitForLoadState("networkidle");
    const loaded = await Promise.all(resources);
    const bytesFor = (kind: string) => loaded
      .filter((resource) => resource.kind === kind)
      .reduce((sum, resource) => sum + resource.bytes, 0);
    const metrics = {
      total: loaded.reduce((sum, resource) => sum + resource.bytes, 0),
      document: bytesFor("document"),
      script: bytesFor("script"),
      stylesheet: bytesFor("stylesheet"),
      font: bytesFor("font"),
      image: bytesFor("image"),
      requests: loaded.length,
      domNodes: await page.locator("*").count(),
    };
    await testInfo.attach("performance-budget.json", {
      body: JSON.stringify({ metrics, budgets: BUDGETS, resources: loaded }, null, 2),
      contentType: "application/json",
    });
    expect(externalDependencies, "Critical assets must remain self-hosted").toEqual([]);
    expect(failedResources, "Budget checks require successfully loaded assets").toEqual([]);
    for (const key of Object.keys(BUDGETS) as (keyof typeof BUDGETS)[]) {
      expect(metrics[key], `${name}: ${key}`).toBeLessThanOrEqual(BUDGETS[key]);
    }
  });
}
