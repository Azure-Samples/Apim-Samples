"""Generated from shared/ai-models.json. Do not edit directly.

Regenerate with: python setup/model_catalog.py --write
Runtime imports perform no JSON reads or code generation.

Autoreload: reload_unsafe
Restart the kernel after catalog edits.
"""

from dataclasses import dataclass
from enum import Enum, unique


@dataclass(frozen = True)
class ModelSpec:
    """A provider-neutral model identity with an optional opaque version."""

    provider: str
    model_name: str
    version: str | None = None


@unique
class ApprovedModel(Enum):
    """Only these exact model snapshots are approved for sample deployments."""

    GPT_5_1 = ModelSpec('openai', 'gpt-5.1', '2025-11-13')
    GPT_5_MINI = ModelSpec('openai', 'gpt-5-mini', '2025-08-07')
    GPT_5_NANO = ModelSpec('openai', 'gpt-5-nano', '2025-08-07')

    @property
    def model_name(self) -> str:
        return self.value.model_name

    @property
    def version(self) -> str | None:
        return self.value.version

    def __str__(self) -> str:
        return self.model_name
