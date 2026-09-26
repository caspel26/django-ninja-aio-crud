import { defineConfig, devices } from "@playwright/test";

// Serves the already-built site/ directory; run `zensical build` first.
export default defineConfig({
  testDir: ".",
  snapshotPathTemplate: "{testDir}/baselines/{arg}-{projectName}{ext}",
  fullyParallel: true,
  reporter: [["list"]],
  expect: {
    toHaveScreenshot: { maxDiffPixelRatio: 0.01, animations: "disabled" },
  },
  use: {
    baseURL: "http://127.0.0.1:8799",
    reducedMotion: "reduce",
  },
  webServer: {
    command: "python3 -m http.server 8799 --directory ../site",
    url: "http://127.0.0.1:8799/",
    reuseExistingServer: true,
  },
  projects: [
    { name: "desktop", use: { ...devices["Desktop Chrome"], viewport: { width: 1440, height: 900 } } },
    { name: "mobile", use: { ...devices["Pixel 7"] } },
  ],
});
