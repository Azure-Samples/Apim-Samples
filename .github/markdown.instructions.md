---
applyTo: "**/*.md"
---

# Markdown Guidelines

This document provides standards for Markdown files in the APIM Samples repository, including README files, documentation, instructions, and skill guides.

## Critical Rules

### Markdownlint Must Pass Before Finalizing

After creating or editing any Markdown file, check the editor diagnostics for every changed `.md` file and resolve all markdownlint warnings before finalizing the work. If the repository adds a Markdown lint command in the future, run it as well.

Do not assume a visually correct preview is lint-clean. Markdownlint also enforces source-level consistency for whitespace, table delimiters, nested list indentation, code-fence languages, inline HTML, and unused link definitions.

Use a narrowly scoped `<!-- markdownlint-disable-next-line RULE -->` comment only when Markdown syntax cannot express the required behavior, such as an intentional `<details>` disclosure. Do not disable a rule for an entire file when a local exception is enough.

### 🚨 No Emoji Variation Selectors in Markdown Links

**This is the most important rule.** Emoji variation selectors cause rendering and Markdown anchor link failures.

❌ **WRONG** — DO NOT DO THIS:
```markdown
## ✅ Prerequisites

[Go to Prerequisites](#%EF%B8%8F-prerequisites)  <!-- Encoded emoji in link -->
```

✅ **CORRECT** — DO THIS:
```markdown
## ✅ Prerequisites

[Go to Prerequisites](#prerequisites)  <!-- Text only, no emoji encoding -->
```

**Why:** When you create an anchor link with an emoji in the heading, Markdown renders the emoji but the anchor reference gets URL-encoded (like `%EF%B8%8F`). The link then breaks because the actual anchor is just the text portion without the encoding.

**The pattern:**
- **Keep emojis in headings** for visual clarity — they're fine there
- **Never include emojis in anchor link references** — always reference just the text
- **When linking to a heading**, use only the text: `[Link text](#heading-text-only)`

---

## Formatting Standards

### Line Endings
- Use **LF line endings only**, never CRLF
- This applies to all files, including Windows development environments

### Quotes and Apostrophes
- Use only straight quotes and apostrophes: `'` (U+0027) and `"` (U+0022)
- Never use typographic/curly quotes: `'` `'` `"` `"`
- Improves consistency across editors and platforms

### Blank Lines

- Use exactly one blank line between paragraphs and sections. Do not add multiple consecutive blank lines.
- Surround headings, tables, lists, and fenced code blocks with a blank line.
- Add a blank line between introductory text such as `**Windows:**` and the fenced code block that follows it.
- Keep a blank line between the final table row and any following HTML closing tag or paragraph.

### Markdown Tables

Use one table style consistently within each table. Always include one space on both sides of each pipe delimiter, including separator rows. Never write compact separators such as `|---|---|`.

**Prefer aligned tables** for short values. Pad cell values with spaces so that every `|` delimiter in a column lines up vertically.

❌ **WRONG** — misaligned columns:
```markdown
| Name | Value |
|---|---|
| Short | 123 |
| Very Long Name | 45 |
```

✅ **CORRECT** — aligned columns:
```markdown
| Name              | Value |
| --- | --- |
| Short             | 123   |
| Very Long Name    | 45    |
```

Use the separator row (`---`, `:---:`, `---:`, etc.) to establish column widths, then align all subsequent rows to match.

**Use compact tables** for prose-heavy content when alignment would create very long lines. Keep spaces around every pipe delimiter and use the same compact style for the header, separator, and each row.

```markdown
| Name | Description |
| --- | --- |
| Simple API Management | Public API Management instance for learning and experimentation. |
| Private Link | Private ingress for security-focused scenarios. |
```

### Lists

- Surround lists with a blank line.
- Indent nested unordered list items consistently. Prefer two spaces for each nested level to satisfy `MD007`.
- Use `1.` for every item in ordered Markdown source. Markdown renderers calculate the visible numbering, and this satisfies the repository's `MD029` style.
- If an established formatter forces a different nested indentation style, use the smallest possible scoped markdownlint annotation and keep the list internally consistent.

### Inline HTML

- Prefer native Markdown syntax over inline HTML whenever Markdown can express the same result.
- Use Markdown image syntax instead of `<img>` tags.
- Use inline HTML only when it adds behavior Markdown does not provide, such as `<details>` disclosures.
- Add `<!-- markdownlint-disable-next-line MD033 -->` immediately before an intentional inline HTML opening tag. Keep the exception local.

### File Links

When referencing files or line numbers in documentation:

**Format:** `[display text](path/to/file.md)` or `[display text](path/to/file.md#L10)` for specific lines

**Rules:**
- Display text must match or describe the target
- Use workspace-relative paths (no `file://` or `vscode://` schemes)
- Encode spaces in the URL: `My File.md` → `My%20File.md`
- Line numbers are 1-indexed: `#L10` (not `#L9`)
- For line ranges: `#L10-L12`
- Do NOT wrap file paths in backticks — they're already links

✅ **CORRECT:**
```markdown
See [configuration guide](docs/configuration.md) for details.

The [initialization code](src/init.ts#L15-L20) runs on startup.

Update [my config file](path/to/My%20Config.md) as needed.
```

❌ **WRONG:**
```markdown
See `docs/configuration.md` for details.

The `src/init.ts` runs on startup.

See the `README.md#L10` file.
```

### Symbols and Code References

- Wrap symbol names in backticks: `functionName()`, `ClassName`, `variableName`
- Use for methods, classes, properties, types, and identifiers
- Do NOT wrap file paths or headings in backticks

---

## Repository File Conventions

### README Files

**Location & Naming:**
- Root `README.md` - Main repository overview
- `infrastructure/[name]/README.md` - Infrastructure architecture guide
- `samples/[name]/README.md` - Sample documentation
- `shared/` folders - Optional READMEs for component overview

**Structure** (see `copilot-instructions.md` for detailed layouts):
- Consistent heading hierarchy and emoji usage across similar documents
- Badges for runtime, supported services, prerequisites
- Clear sections: Objectives, Scenario, Lab Components, Configuration, Results, Clean Up, Links
- Consistent ordering makes all READMEs feel familiar

### Instruction Files

**Location & Naming:**
- Language-specific: `.github/[language].instructions.md` (e.g., `python.instructions.md`, `markdown.instructions.md`)
- Topic-specific: `.github/markdown.instructions.md` (e.g., for Markdown formatting)
- General: `.github/copilot-instructions.md`

**Metadata Block:**
```markdown
---
applyTo: "**/*.md"
---
```

- `applyTo` uses glob patterns to scope where the instruction applies
- `**` matches any folder depth
- Examples: `**/*.py`, `**/*.bicep`, `.github/workflows/*.yml`

### Skill Files

Location: `.github/skills/[skill-name]/SKILL.md`

Structured guides for domain-specific tasks (Bicep, Python policies, sample creation, etc.).

---

## When to Use Markdown Files

| File Type | When | Example |
| --- | --- | --- |
| README | Document a folder/project | `infrastructure/simple-apim/README.md` |
| CONTRIBUTING | Contribution process | Root `CONTRIBUTING.md` |
| Instructions | Copilot guidance | `.github/bicep.instructions.md` |
| Skill Guide | Domain expertise | `.github/skills/sample-creator/SKILL.md` |
| Index/Navigation | Landing pages, TOCs | `samples/README.md` listing all samples |

---

## Documentation Best Practices

### Headings

- Use consistent emoji patterns across related documents (e.g., all README files use the same emoji set)
- Heading levels should reflect document structure (H1 for title, H2 for major sections)
- Never skip levels (e.g., H1 → H3, skipping H2)

### Lists

- Use bullet lists for unordered items
- Use numbered lists for ordered steps or priorities
- Indent sub-items consistently
- Keep list items concise (one line when possible)

### Emphasis

- Use `**bold**` for emphasis and strong concepts
- Use `_italic_` for variables or placeholders to satisfy the repository's `MD049` style
- Use `code` (backticks) for symbols, filenames, and technical terms
- Use blockquotes `>` for notes, tips, and callouts

### Cross-References

- Use reference-style links at the bottom for multiple references to the same target
- Remove reference-style link definitions when their final usage is removed. Unused definitions fail `MD053`.
- Example:
  ```markdown
  See the [setup guide][setup] and [troubleshooting][troubleshooting] pages.

  [setup]: docs/setup.md
  [troubleshooting]: docs/troubleshooting.md
  ```

- Link within README sections using anchor links: `[Jump to section](#section-name)`

---

## Accessibility

### Contrast and Color

- Do NOT rely on color alone to convey meaning (applies to embedded diagrams and exported slides)
- Pair color cues with labels, text, icons, or structure
- Ensure text meets WCAG 2.0 AA contrast: `4.5:1` for normal text, `3:1` for large text

### Images and Alt Text

- Provide meaningful `alt` text for all images and diagrams
- Alt text should describe the image purpose, not just say "screenshot" or "diagram"
- Use native Markdown image syntax instead of inline HTML: `![alt text](path/to/image.png "Optional title")`
- Example: `![Deployment workflow showing resource dependencies](images/deployment.png)`

### Code Blocks

- Use language tags for syntax highlighting: ` ```python `, ` ```bicep `, ` ```json `
- Use `text` for plain terminal output, menu choices, and other non-code examples
- Surround every fenced code block with blank lines
- Include enough context in code examples that they're self-explanatory

---

## Common Issues and Fixes

| Issue | Cause | Fix |
| --- | --- | --- |
| Anchor links break | Emoji in heading + encoded in link | Remove emoji from link reference: `[text](#heading-only)` |
| Tables misaligned | Mixed table styles or missing spaces around pipes | Use one consistent aligned or compact style and write separator rows as `\| --- \| --- \|` |
| Sections run together | Missing or repeated blank lines | Use exactly one blank line around headings, tables, lists, and fences |
| Code fence warning | Missing fence language | Add the appropriate language, or use `text` for plain output |
| List indentation warning | Inconsistent nesting or ordered prefixes | Use two spaces per unordered nesting level and `1.` for ordered items |
| Inline HTML warning | HTML used where Markdown is sufficient | Prefer native Markdown; add a local `MD033` exception only for required HTML behavior |
| Unused reference warning | Link definition remains after its final usage was removed | Delete the unused reference definition |
| File links broken | Wrong path or encoded characters | Use relative paths, encode spaces: `My%20File.md` |
| Symbols not highlighted | Missing backticks | Wrap in backticks: `symbolName` |
| Line ending issues | Mixed CRLF/LF | Ensure all `.md` files use LF only |
| Rendering issues | Curly quotes | Use straight quotes: `'` and `"` only |
