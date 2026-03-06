<!-- BEGIN MICROSOFT SECURITY.MD V0.0.9 BLOCK -->

## Security

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

## Security Scanning Scope

This repository is scanned by [OpenSSF Scorecard](https://github.com/ossf/scorecard) via a scheduled GitHub Action. Some checks will report a low score by design; the rationale is recorded as maintainer annotations in [`.github/scorecard.yml`](.github/scorecard.yml) and summarised below.

### Fuzzing

This repository does not implement dedicated fuzz testing, and the Scorecard Fuzzing check is expected to report `0/10`. This is a deliberate scoping decision rather than an oversight.

Fuzz testing is most valuable where code parses untrusted, attacker-controlled input — file formats, network protocols, deserialisers — particularly in memory-unsafe languages. This repository is a learning playground composed of Bicep templates, Jupyter notebooks, APIM policy XML, and thin Python wrappers around the Azure CLI. None of these components parse untrusted input locally:

- Bicep, policy XML, and notebooks are declarative assets consumed by Azure-side tooling, not by code in this repository.
- The Python helpers read output from the operator's own `az` CLI session and their own policy files.
- The only parsing surface (`shared/python/json_utils.py`) delegates to the Python standard library `json` and `ast` modules, which are [already fuzzed upstream in CPython via OSS-Fuzz](https://github.com/google/oss-fuzz/tree/master/projects/cpython3).

Scorecard additionally has no Python-native fuzzer detection — only OSS-Fuzz enrolment, ClusterFuzzLite, or language-native fuzzers for Go, Haskell, JavaScript/TypeScript, and Erlang are recognised. Adding `hypothesis` or `atheris` property-based tests would therefore not change the score, and would only exercise standard-library code paths already covered upstream.
