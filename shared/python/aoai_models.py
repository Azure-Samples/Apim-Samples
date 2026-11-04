"""Project approved model identities into Azure OpenAI deployment contracts.

Autoreload: reload_unsafe
Restart the kernel after catalog or enum edits.
"""

import re
from typing import TypedDict

# APIM Samples imports
from ai_models import ApprovedModel


class DeploymentConfig(TypedDict):
    """Fields required by the shared Azure OpenAI Bicep deployment modules."""

    name: str
    version: str
    capacity: int


def deployment_slug(model: ApprovedModel) -> str:
    """Normalize an approved model name for existing Azure resource and API identities."""
    if not isinstance(model, ApprovedModel):
        raise ValueError('An approved model enum member is required')
    slug = model.model_name.replace('.', '-')
    if not re.fullmatch(r'[a-z0-9-]+', slug):
        raise ValueError('Model names must produce safe lowercase deployment identifiers.')
    return slug


def to_deployment_config(model: ApprovedModel, capacity: int) -> DeploymentConfig:
    """Reject unapproved/unversioned identities and invalid Azure deployment capacities."""
    deployment_slug(model)
    if isinstance(capacity, bool) or not isinstance(capacity, int) or capacity <= 0:
        raise ValueError('Model deployment capacity must be an integer greater than zero')
    if model.value.provider != 'openai' or model.version is None:
        raise ValueError('Azure OpenAI requires an approved OpenAI model with an explicit version')
    return {'name': model.model_name, 'version': model.version, 'capacity': capacity}
