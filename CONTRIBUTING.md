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
- For infrastructure or sample changes, update the relevant `create.ipynb` and `main.bicep` files.
- Keep documentation clear and concise.

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
