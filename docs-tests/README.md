# Documentation checks

Run from the repository root:

```sh
python -m pip install -r docs-tests/requirements.txt
zensical build --strict
cd docs-tests
npm ci
npx playwright install chromium
npm test
```

Use Zensical for the v3 site: the visual baselines were generated with its
classic theme. `docs/requirements.txt` supports the legacy MkDocs tooling.

The suite checks desktop and mobile visuals, WCAG 2 AA accessibility, keyboard
controls, and cold-load budgets for the homepage, relations guide, and serializer
reference. It runs against the local `site/` directory and does not deploy.

Each performance check saves measured resources and budgets in the HTML report.
Limits are 1.5 MiB total decoded resources, 160 KiB HTML, 384 KiB each for scripts
and styles, 128 KiB each for fonts and images, 40 successful local requests, and
3,000 DOM nodes. Third-party badges and repository counters are excluded; fonts,
styles, and scripts must be self-hosted. Each test uses a fresh browser context.
These size and complexity limits catch growth without depending on CI machine
speed or production compression; they do not measure production Core Web Vitals.

Baselines are stored separately under `baselines/linux` and `baselines/darwin`.
CI uses Ubuntu 24.04 with the Chromium version pinned by `package-lock.json`.
Generate macOS baselines locally. For Linux, dispatch `Validate Docs` with
`update_snapshots=true`, download the `docs-linux-baselines` artifact, review
the images, and commit them under `baselines/linux`. This workflow only uploads
artifacts; it does not commit changes or deploy the site.

Review screenshot differences before deliberately updating baselines with
`npm run update`. The validation workflow uploads browser reports for inspection
and has read-only repository permissions.
