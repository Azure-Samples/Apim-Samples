<!-- BEGIN MICROSOFT SECURITY.MD V0.0.9 BLOCK -->

# Security

Microsoft takes the security of our software products and services seriously, which includes all source code repositories managed through our GitHub organizations.

If you believe you have found a security vulnerability in any Microsoft-owned repository that meets [Microsoft's definition of a security vulnerability](https://aka.ms/security.md/definition), please report it to us as described below.

## Reporting Security Issues

**Please do not report security vulnerabilities through public GitHub issues.**

Instead, please report them to the Microsoft Security Response Center (MSRC) at [https://msrc.microsoft.com/create-report](https://aka.ms/security.md/msrc/create-report).

You should receive a response within 24 hours. If for some reason you do not, please follow up using the messaging functionality found at the bottom of the Activity tab on your vulnerability report on [https://msrc.microsoft.com/report/vulnerability](https://msrc.microsoft.com/report/vulnerability/) or via email as described in the instructions at the bottom of [https://msrc.microsoft.com/create-report](https://aka.ms/security.md/msrc/create-report). Additional information can be found at [microsoft.com/msrc](https://www.microsoft.com/msrc) or on MSRC's [FAQ page for reporting an issue](https://www.microsoft.com/msrc/faqs-report-an-issue).

Please include the requested information listed below (as much as you can provide) to help us better understand the nature and scope of the possible issue:

* Type of issue (e.g. buffer overflow, SQL injection, cross-site scripting, etc.)
* Full paths of source file(s) related to the manifestation of the issue
* The location of the affected source code (tag/branch/commit or direct URL)
* Any special configuration required to reproduce the issue
* Step-by-step instructions to reproduce the issue
* Proof-of-concept or exploit code (if possible)
* Impact of the issue, including how an attacker might exploit the issue

This information will help us triage your report more quickly.

If you are reporting for a bug bounty, more complete reports can contribute to a higher bounty award. Please visit our [Microsoft Bug Bounty Program](https://aka.ms/security.md/msrc/bounty) page for more details about our active programs.

## Preferred Languages

We prefer all communications to be in English.

## Policy

Microsoft follows the principle of [Coordinated Vulnerability Disclosure](https://aka.ms/security.md/cvd).

<!-- END MICROSOFT SECURITY.MD BLOCK -->

## Repository Security Stance

This repository is a **learning playground** for Azure API Management. Its security posture reflects a deliberate balance: enforce real-world best practices wherever they do not impede the learning workflow, and clearly document every intentional relaxation so users know what to tighten for production.

### What We Enforce

#### Supply chain and CI

* GitHub Actions use least-privilege `permissions:` blocks, SHA-pinned third-party actions, `persist-credentials: false` on `actions/checkout`, and no `pull_request_target`.
* Dependabot, Dependency Review, and OpenSSF Scorecard are configured.
* `pip-audit` runs in CI as a non-blocking supply-chain vulnerability check.
* `uv.lock` provides reproducible builds; `pyproject.toml` pins minimum versions for known-vulnerable packages.

#### Secrets hygiene

* No real secrets are committed. `.gitignore` and `.dockerignore` coverage is comprehensive.
* Managed identity and APIM named values are used for backend credentials; no hardcoded keys in policies.
* APIM subscription keys in Bicep outputs are annotated with `#disable-next-line outputs-should-not-contain-secrets` and an inline comment explaining intent. The Bicep linter rule is set to `warning` globally so that any *unintentional* secret output is caught.
* Python helpers redact sensitive headers (`api-key`, `Authorization`, `Ocp-Apim-Subscription-Key`, `x-api-key`) before logging. The `print_secret()` utility masks secret values in notebook output.
* The Azure CLI wrapper's secret-redaction regex covers access tokens, refresh tokens, client secrets, subscription keys, connection strings, storage account keys, and shared access signatures.

#### Authentication and authorization

* JWT validation via `validate-jwt` and `validate-azure-ad-token` is demonstrated in the `authX`, `authX-pro`, and `oauth-3rd-party` samples.
* APIM policy error handlers return generic messages to callers; detailed diagnostics are emitted to Application Insights via `<trace>`.

#### Development tooling

* Local preview servers (`serve_website.py`, `serve_presentation.py`) bind to `127.0.0.1`, not `0.0.0.0`.
* Jupyter notebook cell outputs are cleared before commit to prevent leaking resource names or subscription IDs.

### Intentional Compromises for Learning

The following defaults prioritise a frictionless learning experience. **Every one of them is parameterised** and can be flipped to the secure setting for production use.

| Default                                              | Why                                                                                                      | Production guidance                                                  |
| ---------------------------------------------------- | -------------------------------------------------------------------------------------------------------- | -------------------------------------------------------------------- |
| `apimPublicAccess = true`                            | Lets learners call APIM from their machine without VPN or private networking setup.                      | Disable public access; use Private Endpoints or VNet integration.    |
| `useStrictNsg = false`                               | Avoids NSG rules that block notebook or CLI connectivity during experiments.                             | Enable strict NSGs scoped to required ports and sources.             |
| WAF in `Detection` mode                              | Prevents the WAF from blocking exploratory requests while learners iterate.                              | Switch to `Prevention` mode once rules are tuned.                    |
| `enablePurgeProtection = false` on Key Vault         | Allows quick tear-down of lab environments without waiting for the purge-protection retention period.    | Enable purge protection.                                             |
| `revealBackendApiInfo = true` (X-Backend-URL header) | Helps learners observe routing decisions and backend selection in responses.                             | Remove or disable the header; do not expose internal URLs.           |
| Subscription-key-only auth on admin APIs             | Keeps sample setup simple. Each admin API includes a `SECURITY` comment pointing to `authX`/`authX-pro`. | Layer JWT validation (`validate-azure-ad-token` or `validate-jwt`).  |
| APIM subscription keys returned in Bicep outputs     | Notebooks need keys to generate test traffic. Outputs use `#disable-next-line` with an intent comment.   | Fetch keys via RBAC-controlled mechanisms; remove them from outputs. |

### What Is Not a Vulnerability

These items were reviewed and intentionally not flagged:

* **`allowInsecureTls=True` for Application Gateway infras** -- correctly scoped to AppGW infrastructure types (self-signed certificate by design); the flag is `False` for all other infrastructures.
* **`shell=True` in Azure CLI wrappers** -- commands are constructed from controlled internal strings, never from user-supplied input.
* **Application Insights instrumentation keys in Bicep outputs** -- Microsoft treats these as non-secret connection identifiers.
* **`ast.literal_eval` fallback in JSON parsing** -- this is the safe `ast` module function, not `eval`.

## Security Scanning Scope

This repository is scanned by [OpenSSF Scorecard](https://github.com/ossf/scorecard) via a scheduled GitHub Action. Some checks will report a low score by design; the rationale is recorded as maintainer annotations in [`.github/scorecard.yml`](.github/scorecard.yml) and summarised below.

### Fuzzing

This repository does not implement dedicated fuzz testing, and the Scorecard Fuzzing check is expected to report `0/10`. This is a deliberate scoping decision rather than an oversight.

Fuzz testing is most valuable where code parses untrusted, attacker-controlled input — file formats, network protocols, deserialisers — particularly in memory-unsafe languages. This repository is a learning playground composed of Bicep templates, Jupyter notebooks, APIM policy XML, and thin Python wrappers around the Azure CLI. None of these components parse untrusted input locally:

* Bicep, policy XML, and notebooks are declarative assets consumed by Azure-side tooling, not by code in this repository.
* The Python helpers read output from the operator's own `az` CLI session and their own policy files.
* The only parsing surface (`shared/python/json_utils.py`) delegates to the Python standard library `json` and `ast` modules, which are [already fuzzed upstream in CPython via OSS-Fuzz](https://github.com/google/oss-fuzz/tree/master/projects/cpython3).

Scorecard additionally has no Python-native fuzzer detection — only OSS-Fuzz enrolment, ClusterFuzzLite, or language-native fuzzers for Go, Haskell, JavaScript/TypeScript, and Erlang are recognised. Adding `hypothesis` or `atheris` property-based tests would therefore not change the score, and would only exercise standard-library code paths already covered upstream.
