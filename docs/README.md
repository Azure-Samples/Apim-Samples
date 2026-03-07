# GitHub Pages Site

This folder contains the source for the public landing page at
**<https://azure-samples.github.io/Apim-Samples/>**.

## How it works

| Piece | Role |
|---|---|
| `docs/index.html` | The page markup, structured data, and meta tags. CSS is externalised to `styles.css`; there is no executable JavaScript. |
| `docs/styles.css` | All visual rules for the landing page. Referenced by `index.html` via `<link rel="stylesheet">`. |
| `docs/robots.txt` | Permissive crawler policy plus a pointer to the sitemap. |
| `docs/sitemap.xml` | Single-URL sitemap. Deep links live on github.com and are out of scope for this origin. |
| `.github/workflows/github-pages.yml` | Assembles and publishes the site on every push to `main`. |
| `assets/` (repo root) | The workflow copies the logo, favicons, and architecture SVGs from here into the published artifact. `index.html` references them at `./assets/...`. |
| `assets/APIM-Samples-Slide-Deck.html` | The workflow runs `setup/export_presentation.py` to inline this deck's images and stages the result at `/slide-deck.html`. |

There is **no JavaScript framework, no bundler, and no npm install**. That is deliberate: the page changes rarely, and plain static HTML + CSS means the publish workflow cannot break due to a transitive package update. The only `<script>` in `index.html` is the JSON-LD structured-data block, which must remain inline because search-engine crawlers do not reliably follow external JSON-LD references.

## Previewing locally

From the Developer CLI (`./start.ps1` on Windows, `./start.sh` on macOS/Linux), choose:

```
w) Serve & view GitHub Pages website (auto-opens browser)
```

This runs `setup/serve_website.py`, which stages `_site/` exactly as the workflow does (including the self-contained slide deck), starts a local HTTP server on port 7800, and opens your browser. `_site/` is removed when you stop the server with Ctrl+C.

If you need to invoke it directly:

```bash
uv run python setup/serve_website.py          # default port 7800
uv run python setup/serve_website.py 7801     # custom port
```

The staging logic in `serve_website.py` is the single local source of truth. If the workflow's copy step changes, update `stage_site()` to match so local preview stays faithful.

## Keeping the page current

The page intentionally duplicates a small amount of content from the root `README.md` (infrastructure list, sample list, quick-start steps). **When those change in the README, change them here too.**

Agents and contributors should treat the following as the sync checklist:

- **New infrastructure added** → add an `.infra-card` in the *Infrastructures* section of `index.html`, add a `ListItem` to the JSON-LD `ItemList` in the `<head>`, add its SVG to the copy step in `github-pages.yml`, and update the count in the value-prop card if it still says "Five".
- **New sample added** → add a `.sample-card` in the *Samples* section of `index.html` **and** a `ListItem` to the JSON-LD `ItemList`.
- **Sample or infrastructure removed or renamed** → remove or rename the matching card and any asset mapping in the workflow.
- **Quick-start flow changes** → update the four `.step` items.

This checklist is also enforced by `.github/copilot-instructions.md` so that GitHub Copilot will prompt for these updates when reviewing related PRs.

## Design notes

- Colour tokens (`--brand-blue`, `--accent-cyan`, …) mirror `assets/APIM-Samples-Slide-Deck.html` so the repo has one visual identity.
- WCAG 2.0 AA contrast targets: body text on white is `#24292f` (≈ 13.6:1), dim text on the deep-blue footer is `rgba(255,255,255,0.88)` (≈ 10.4:1).
- No emoji variation selectors are used, in line with the repo-wide rule.
- `prefers-reduced-motion` disables every transition for users who ask for that.
- Card hover lifts, the pill CTA button, and the shine sweep animation are adapted from the [APIM Love](https://aka.ms/apimlove) landing page, recoloured to this repo's palette. The shine sweep is suppressed under `prefers-reduced-motion`.

## SEO notes

The `<head>` carries a JSON-LD `@graph` with three nodes. `WebSite` gives search engines a canonical display name. `SoftwareSourceCode` declares the license, language stack, and the GitHub repository URL so the code repo and this landing page are understood as the same entity. `ItemList` enumerates every infrastructure and sample by name and URL — this is what drives sitelinks beneath the main search result.

The `ItemList` is the one piece that **must** stay in lock-step with the visible cards. If they drift, the search-result sitelinks will advertise folders that no longer exist. Validate after editing by pasting the page URL into <https://search.google.com/test/rich-results>.

`<lastmod>` is deliberately absent from `sitemap.xml`. GitHub Pages sets an accurate `Last-Modified` HTTP header from the artifact timestamp, and a hand-edited date would be stale within days.
