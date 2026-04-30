---
applyTo: "**/*.md"
---

# Markdown Guidelines

This document provides standards for Markdown files in the APIM Samples repository, including README files, documentation, instructions, and skill guides.

## Critical Rules

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

### Markdown Tables
**Markdown tables must be column-aligned.** Pad cell values with spaces so that every `|` delimiter in a column lines up vertically.

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
- Use `*italic*` for variables or placeholders
- Use `code` (backticks) for symbols, filenames, and technical terms
- Use blockquotes `>` for notes, tips, and callouts

### Cross-References

- Use reference-style links at the bottom for multiple references to the same target
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
- Example: `![Deployment workflow showing resource dependencies](images/deployment.png)`

### Code Blocks

- Use language tags for syntax highlighting: ` ```python `, ` ```bicep `, ` ```json `
- Include enough context in code examples that they're self-explanatory

---

## Common Issues and Fixes

| Issue | Cause | Fix |
| --- | --- | --- |
| Anchor links break | Emoji in heading + encoded in link | Remove emoji from link reference: `[text](#heading-only)` |
| Tables misaligned | Inconsistent column widths | Pad cells with spaces to align `\|` delimiters |
| File links broken | Wrong path or encoded characters | Use relative paths, encode spaces: `My%20File.md` |
| Symbols not highlighted | Missing backticks | Wrap in backticks: `symbolName` |
| Line ending issues | Mixed CRLF/LF | Ensure all `.md` files use LF only |
| Rendering issues | Curly quotes | Use straight quotes: `'` and `"` only |
