# Contributing to Azure API Management Samples

Thank you for your interest in contributing!

## How to Contribute

- Fork the repository and create your branch from `main`.
- Make your changes, following the existing code style and structure.
- Add or update documentation and tests as needed.
- Ensure your code passes linting and runs as expected.
- Open a pull request with a clear description of your changes.

## Guidelines

- Use standard Python and Bicep best practices.
- Keep reusable assets in the `shared` folder.
- Follow the [Python helper strategy](shared/python/README.md) when deciding what stays in a notebook, belongs in a sample-local module, or should be promoted to `shared/python/`.
- For infrastructure or sample changes, update the relevant `create.ipynb` and `main.bicep` files.
- Keep documentation clear and concise.

## Sample Catalog

[samples/catalog.json](samples/catalog.json) is the source of truth for sample folders, canonical display names, root README summaries, and supported infrastructures. Entries are alphabetical by display name; infrastructure IDs follow the existing matrix column order. Every active sample is listed, except `_TEMPLATE`.

When adding, renaming, or changing compatibility for a sample:

1. Update the catalog first.
1. Synchronize the root README table, website cards and JSON-LD, slide deck names/counts, test matrix, and compatibility SVG. Use the catalog display name exactly.
1. Keep the sample README badge and notebook's explicit `supported_infras` declaration consistent with the catalog. The notebook retains visible configuration for learners.
1. Run the read-only check from the repository root:

   ```bash
   python setup/sample_catalog.py
   ```

The existing Python test workflow enforces these checks through `tests/python/test_sample_catalog.py`. Diagnostics identify the file and mismatched metadata. The checker never changes manual test results, executes notebooks, or calls Azure.

Website and slide-deck descriptions remain tailored, hand-authored prose. The catalog's plain-text summary matches the root README description, where emphasis and reference links may still be used. There is no website build step or generated HTML requirement.

## Project Scope

This repository is maintained as a **learning and experimentation playground** for Azure API Management policies. It is sample code, not a product. That framing is deliberate and keeps the following out of scope:

- **Packaging** - There is no installable package, and none is planned. Please clone or fork the repo and run notebooks directly.
- **Signed releases** - There are no release artifacts to sign. The repo is consumed at source.
- **Fuzzing** - The code surface is Jupyter notebooks, Bicep templates, and thin helper utilities calling Azure APIs. There are no parsers or untrusted-input handlers that would benefit from fuzz testing.

If you believe one of these should become in scope, please open an issue to discuss before submitting a PR.

## Decision-Making Process

All contributions are appreciated and evaluated. In the event of a difference of opinion, final decisions lie with the project owner.

## Code of Conduct

Please be respectful and considerate in all interactions.

---

For questions or suggestions, please open an issue or reach out to the author.
