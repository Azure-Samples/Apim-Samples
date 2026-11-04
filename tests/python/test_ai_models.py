"""Provider-neutral catalog and compatibility contracts."""

import ast
from dataclasses import FrozenInstanceError
from enum import Enum
from pathlib import Path

import pytest

from ai_models import ApprovedModel, ModelSpec
from apimtypes import AzureOpenAIModel


def test_catalog_is_pure_and_provider_neutral():
    source = (Path(__file__).resolve().parents[2] / 'shared' / 'python' / 'ai_models.py').read_text(encoding = 'utf-8')
    imports = {node.module for node in ast.walk(ast.parse(source)) if isinstance(node, ast.ImportFrom)}
    imports.update(alias.name for node in ast.walk(ast.parse(source)) if isinstance(node, ast.Import) for alias in node.names)
    assert imports == {'dataclasses', 'enum'}
    assert AzureOpenAIModel is ApprovedModel
    assert set(ModelSpec.__dataclass_fields__) == {'provider', 'model_name', 'version'}
    assert len({model.value for model in ApprovedModel}) == len(ApprovedModel)
    with pytest.raises(FrozenInstanceError):
        ApprovedModel.GPT_5_MINI.value.model_name = 'mutation'


def test_other_providers_and_multiple_opaque_versions():
    class OtherProvider(Enum):
        FIRST = ModelSpec('other', 'sample-model', 'release-a')
        SECOND = ModelSpec('other', 'sample-model', 'release-b')
        UNVERSIONED = ModelSpec('other', 'unversioned')

    assert len(OtherProvider) == 3
    assert OtherProvider.FIRST.value != OtherProvider.SECOND.value
    assert OtherProvider.UNVERSIONED.value.version is None
    assert OtherProvider.FIRST.value.version == 'release-a'
