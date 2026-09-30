---
description: |
  Reviews the supported Azure OpenAI model catalog every week. When a model
  reaches its earliest relevant retirement or new-deployment cutoff within
  30 days, this workflow migrates the samples to a compatible replacement and
  opens a draft pull request with lifecycle evidence and a migration path.

on:
  schedule: weekly on monday
  workflow_dispatch:

permissions:
  contents: read
  copilot-requests: write

engine: copilot

network:
  allowed:
    - defaults
    - learn.microsoft.com
    - azure.microsoft.com

tools:
  bash: ['cat', 'date', 'find', 'grep', 'head', 'python', 'tail']
  web-fetch:

safe-outputs:
  mentions: false
  allowed-github-references: []
  create-pull-request:
    title-prefix: '[model-lifecycle] '
    labels: [automation, azure-openai]
    draft: true
    max: 1
    if-no-changes: ignore
    fallback-as-issue: true
    excluded-files:
      - '.github/workflows/**'
      - 'pyproject.toml'
      - 'uv.lock'
---

# Maintain the supported Azure OpenAI model catalog

Review `AzureOpenAIModel` in `shared/python/apimtypes.py` and every place its
members are deployed or documented. Act only on models whose earliest relevant
new-deployment cutoff or retirement date is 30 calendar days or less from the
current UTC date.

## Evidence requirements

1. Treat Microsoft Learn and Azure-published lifecycle or retirement notices as
   authoritative. Start with the
   [model retirement schedule](https://learn.microsoft.com/azure/foundry/openai/concepts/model-retirement-schedule),
   [model lifecycle policy](https://learn.microsoft.com/azure/foundry/openai/concepts/model-retirements),
   and [retired-model list](https://learn.microsoft.com/azure/foundry/openai/concepts/retired-models).
   Use Azure CLI model metadata only when it is available without inventing
   credentials or subscription context.
1. Check every Azure region and deployment SKU used by the model in this
   repository. A cutoff in any supported sample path is sufficient to trigger
   a migration.
1. Record the exact model name, snapshot version, lifecycle state, affected
   regions and SKUs, cutoff date, days remaining, UTC check time, and source
   URLs.
1. Do not infer a date from a lifecycle label alone. If an authoritative cutoff
   date cannot be established, make no code changes and do not open a pull
   request.

## Migration requirements

1. Choose a replacement that is Generally Available and provisionable in the
   same regions and deployment SKUs.
1. Preserve the retiring model's role described by
   `AzureOpenAIModel.intended_use`. Verify API compatibility, streaming and
   token telemetry behavior, quota/deployment-type support, and any sample
   feature that depends on that model.
1. Remove the retiring model from `AzureOpenAIModel`, add the replacement model
   and snapshot there if needed, and migrate all executable, infrastructure,
   workbook, KQL, test, and documentation references. Do not leave the
   retiring model in the supported enum.
1. Keep historical lifecycle or pricing references only when they are clearly
   labeled as historical and are not used for provisioning.
1. Preserve notebook structure, clear every notebook output, and keep `index`
   set to `1`.
1. Follow all repository instructions. Run targeted Python tests, Ruff, Bicep
   builds, JSON parsing, and Markdown linting for the changed surfaces.

## Pull request contract

Create one draft pull request only when a qualifying migration is complete.
Use these headings in its body:

- `## Lifecycle evidence`
- `## Migration path`
- `## Compatibility assessment`
- `## Changes`
- `## Validation`
- `## Residual risks`

Explain why the replacement is appropriate rather than merely newer. Include
the last safe migration date and identify any region, quota, or deployment-SKU
checks that maintainers must perform before merging.

If no supported model is within the 30-day window, make no changes and emit no
pull request.
