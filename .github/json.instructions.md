---
description: 'JSON conventions and guidelines'
applyTo: '**/*.json'
---

# Copilot Instructions (JSON)

## Conventions

- If $schema is defined, ensure that all changes are validated.
- Use two spaces for indentation. Do not use tabs.
- Sort properties alphabetically.

## $schema URLs

- Always reference JSON schemas from `raw.githubusercontent.com`, never from `github.com/.../blob/...`. The `blob/` URL serves an HTML preview page, not the schema JSON, so editors and validators cannot fetch or validate against it.
- Use the `refs/heads/<branch>` form (or a pinned tag/commit) so the URL is unambiguous and stable.
- Example — Azure Monitor Workbook:
  - ✅ `https://raw.githubusercontent.com/Microsoft/Application-Insights-Workbooks/refs/heads/master/schema/workbook.json`
  - ❌ `https://github.com/Microsoft/Application-Insights-Workbooks/blob/master/schema/workbook.json`
- When adding or updating a `$schema` value in any JSON file, convert any `github.com/<org>/<repo>/blob/<ref>/<path>` URL to `raw.githubusercontent.com/<org>/<repo>/refs/heads/<ref>/<path>` (or the appropriate `refs/tags/<tag>` form for pinned versions).
