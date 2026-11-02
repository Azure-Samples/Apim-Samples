"""Azure projection of approved model identities."""

import pytest

from ai_models import ApprovedModel, ModelSpec
from aoai_models import deployment_slug, to_deployment_config


def test_azure_projection():
    model = ApprovedModel.GPT_5_1
    assert deployment_slug(model) == model.model_name.replace('.', '-')
    assert to_deployment_config(model, 10) == {'name': model.model_name, 'version': model.version, 'capacity': 10}


@pytest.mark.parametrize('capacity', [0, -1, True, 1.5, '10'])
def test_invalid_capacity(capacity):
    with pytest.raises(ValueError, match = 'greater than zero'):
        to_deployment_config(ApprovedModel.GPT_5_MINI, capacity)


@pytest.mark.parametrize('model', [ModelSpec('other', 'sample'), 'unknown', None])
def test_not_approved(model):
    with pytest.raises(ValueError, match = 'approved'):
        to_deployment_config(model, 1)


@pytest.mark.parametrize('spec,error', [
    (ModelSpec('other', 'sample-model', 'release-a'), 'explicit version'),
    (ModelSpec('openai', 'sample-model'), 'explicit version'),
    (ModelSpec('openai', 'Unsafe_Name', 'release-a'), 'identifiers'),
])
def test_azure_specific_projection_rejects_neutral_specs(monkeypatch, spec, error):
    monkeypatch.setattr(ApprovedModel.GPT_5_MINI, '_value_', spec)
    with pytest.raises(ValueError, match = error):
        to_deployment_config(ApprovedModel.GPT_5_MINI, 1)
