"""Offline contract checks for all five infrastructure creation entry points."""

import importlib.util
import inspect
from dataclasses import replace
from pathlib import Path
from types import ModuleType
from unittest.mock import Mock

import pytest

# APIM Samples imports
import infrastructure_cli as cli
from apimtypes import APIM_SKU, INFRASTRUCTURE, Region

INFRASTRUCTURE_DIR = Path(__file__).resolve().parents[2] / 'infrastructure'
ARCHITECTURES = (
    ('simple-apim', INFRASTRUCTURE.SIMPLE_APIM, 'Basicv2', ('Basicv2', 'Standardv2', 'Premiumv2'), cli.AcaApis.NONE, False),
    ('apim-aca', INFRASTRUCTURE.APIM_ACA, 'Basicv2', ('Basicv2', 'Standardv2', 'Premiumv2'), cli.AcaApis.ALWAYS, False),
    ('appgw-apim', INFRASTRUCTURE.APPGW_APIM, 'Developer', ('Developer', 'Premium', 'Premiumv2'), cli.AcaApis.OPTIONAL, True),
    ('appgw-apim-pe', INFRASTRUCTURE.APPGW_APIM_PE, 'Standardv2', ('Standardv2', 'Premiumv2'), cli.AcaApis.OPTIONAL, True),
    ('afd-apim-pe', INFRASTRUCTURE.AFD_APIM_PE, 'Standardv2', ('Standardv2', 'Premiumv2'), cli.AcaApis.OPTIONAL, True),
)


@pytest.fixture(params=ARCHITECTURES, ids=lambda value: value[0])
def architecture(request: pytest.FixtureRequest) -> tuple[ModuleType, tuple]:
    """Import each real architecture script without invoking deployment."""
    folder = request.param[0]
    spec = importlib.util.spec_from_file_location(f'create_{folder.replace("-", "_")}', INFRASTRUCTURE_DIR / folder / 'create_infrastructure.py')
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)

    return module, request.param


@pytest.fixture
def deployment_boundary(monkeypatch: pytest.MonkeyPatch) -> tuple[Mock, Mock]:
    """Record deployment dispatch and prevent any real Azure command."""
    resource_exists = Mock(return_value=True)
    factory = Mock()
    factory.return_value.deploy_infrastructure.return_value.success = True
    monkeypatch.setattr(cli.az, 'does_resource_group_exist', resource_exists)

    return factory, resource_exists


def test_architecture_argument_contract(architecture: tuple[ModuleType, tuple]) -> None:
    """Preserve defaults, SKU choices, flags, and callable signatures."""
    module, (_, infrastructure, default_sku, choices, aca_apis, strict_nsg) = architecture
    spec = module.SPEC
    parser = cli.build_parser(spec)
    args = parser.parse_args([])

    assert spec.infrastructure == infrastructure
    assert spec.sku_choices == choices
    assert spec.default_sku == default_sku
    assert spec.aca_apis == aca_apis
    assert spec.supports_strict_nsg is strict_nsg
    assert (args.location, args.index, args.sku, args.rg_exists) == (Region.EAST_US_2, None, default_sku, None)
    assert hasattr(args, 'no_aca') is (aca_apis == cli.AcaApis.OPTIONAL)
    assert hasattr(args, 'use_strict_nsg') is strict_nsg
    expected_parameters = ['location', 'index', 'apim_sku']
    if strict_nsg:
        expected_parameters += ['no_aca', 'use_strict_nsg']
    expected_parameters += ['rg_exists']
    assert list(inspect.signature(module.create_infrastructure).parameters) == expected_parameters


@pytest.mark.parametrize('rg_exists', [None, False, True])
@pytest.mark.parametrize('success', [False, True])
def test_cli_dispatch(
    architecture: tuple[ModuleType, tuple],
    deployment_boundary: tuple[Mock, Mock],
    rg_exists: bool | None,
    success: bool,
) -> None:
    """Keep tri-state existence hints, constructor defaults, and exit codes."""
    module, (_, infrastructure, default_sku, _, aca_apis, strict_nsg) = architecture
    factory, resource_exists = deployment_boundary
    factory.return_value.deploy_infrastructure.return_value.success = success
    spec = replace(module.SPEC, factory=factory)
    argv = ['--location', 'westus2', '--index', '3']
    if rg_exists is not None:
        argv.append('--rg-exists' if rg_exists else '--no-rg-exists')

    with pytest.raises(SystemExit) as exit_info:
        cli.main(spec, argv)

    assert exit_info.value.code == (0 if success else 1)
    assert factory.call_args.args == ('westus2', 3, APIM_SKU(default_sku))
    kwargs = factory.call_args.kwargs
    assert kwargs['rg_exists'] is rg_exists
    if aca_apis == cli.AcaApis.NONE:
        assert 'infra_apis' not in kwargs
    else:
        assert [api.name for api in kwargs['infra_apis']] == ['hello-world-aca-1', 'hello-world-aca-2', 'hello-world-aca-pool']
    if strict_nsg:
        assert kwargs['use_strict_nsg'] is False
    else:
        assert 'use_strict_nsg' not in kwargs
    if rg_exists is None:
        resource_exists.assert_called_once_with(cli.az.get_infra_rg_name(infrastructure, 3))
    else:
        resource_exists.assert_not_called()
    factory.return_value.deploy_infrastructure.assert_called_once_with(True if rg_exists is None else rg_exists)


@pytest.mark.parametrize('success', [False, True])
def test_callable_entry_point_preserved(architecture: tuple[ModuleType, tuple], deployment_boundary: tuple[Mock, Mock], monkeypatch: pytest.MonkeyPatch, success: bool) -> None:
    """Existing Python callers still receive SystemExit after deployment."""
    module, (_, _, default_sku, _, _, strict_nsg) = architecture
    factory, _ = deployment_boundary
    factory.return_value.deploy_infrastructure.return_value.success = success
    monkeypatch.setattr(module, 'SPEC', replace(module.SPEC, factory=factory))
    kwargs = {'rg_exists': False}
    if strict_nsg:
        kwargs.update(no_aca=True, use_strict_nsg=True)

    with pytest.raises(SystemExit) as exit_info:
        module.create_infrastructure('eastus2', 2, APIM_SKU(default_sku), **kwargs)

    assert exit_info.value.code == (0 if success else 1)
    assert factory.call_args.args == ('eastus2', 2, APIM_SKU(default_sku))
    assert factory.call_args.kwargs['rg_exists'] is False
    if strict_nsg:
        assert factory.call_args.kwargs['infra_apis'] == []
        assert factory.call_args.kwargs['use_strict_nsg'] is True


def test_cli_explicit_sku_and_supported_flags(architecture: tuple[ModuleType, tuple], deployment_boundary: tuple[Mock, Mock]) -> None:
    """Wire parsed SKU and network flags through the shared dispatch."""
    module, (_, _, _, choices, _, strict_nsg) = architecture
    factory, _ = deployment_boundary
    argv = ['--sku', choices[-1], '--no-rg-exists']
    if strict_nsg:
        argv += ['--no-aca', '--use-strict-nsg']

    with pytest.raises(SystemExit) as exit_info:
        cli.main(replace(module.SPEC, factory=factory), argv)

    assert exit_info.value.code == 0
    assert factory.call_args.args == (Region.EAST_US_2, None, APIM_SKU(choices[-1]))
    if strict_nsg:
        assert factory.call_args.kwargs['infra_apis'] == []
        assert factory.call_args.kwargs['use_strict_nsg'] is True


def test_missing_resource_group_discovered_with_default_index(architecture: tuple[ModuleType, tuple], deployment_boundary: tuple[Mock, Mock]) -> None:
    """Unknown hints remain None even when discovery requests a fresh deployment."""
    module, (_, infrastructure, default_sku, _, _, _) = architecture
    factory, resource_exists = deployment_boundary
    resource_exists.return_value = False

    with pytest.raises(SystemExit) as exit_info:
        cli.main(replace(module.SPEC, factory=factory), [])

    assert exit_info.value.code == 0
    assert factory.call_args.args == (Region.EAST_US_2, None, APIM_SKU(default_sku))
    assert factory.call_args.kwargs['rg_exists'] is None
    resource_exists.assert_called_once_with(cli.az.get_infra_rg_name(infrastructure, None))
    factory.return_value.deploy_infrastructure.assert_called_once_with(False)


def test_main_entry_point_preserved(architecture: tuple[ModuleType, tuple], monkeypatch: pytest.MonkeyPatch) -> None:
    """Architecture-specific main functions forward their exact spec."""
    module, _ = architecture
    main = Mock()
    monkeypatch.setattr(cli, 'main', main)

    module.main()

    main.assert_called_once_with(module.SPEC)


@pytest.mark.parametrize('option', ['--no-aca', '--use-strict-nsg'])
def test_unsupported_flags_are_rejected(architecture: tuple[ModuleType, tuple], option: str) -> None:
    """Do not expose networking or optional-ACA flags on simpler architectures."""
    module, (_, _, _, _, aca_apis, strict_nsg) = architecture
    supported = aca_apis == cli.AcaApis.OPTIONAL if option == '--no-aca' else strict_nsg
    if supported:
        args = cli.build_parser(module.SPEC).parse_args([option])
        assert getattr(args, option.removeprefix('--').replace('-', '_')) is True
    else:
        with pytest.raises(SystemExit) as exit_info:
            cli.build_parser(module.SPEC).parse_args([option])
        assert exit_info.value.code == 2


@pytest.mark.parametrize('argv', [['--sku', 'invalid'], ['--index', 'not-an-integer']])
def test_invalid_arguments_never_deploy(architecture: tuple[ModuleType, tuple], deployment_boundary: tuple[Mock, Mock], argv: list[str]) -> None:
    """Argparse rejects invalid inputs before discovery or resource creation."""
    module, _ = architecture
    factory, resource_exists = deployment_boundary

    with pytest.raises(SystemExit) as exit_info:
        cli.main(replace(module.SPEC, factory=factory), argv)

    assert exit_info.value.code == 2
    factory.assert_not_called()
    resource_exists.assert_not_called()


def test_aca_api_definitions_match_existing_contract(monkeypatch: pytest.MonkeyPatch) -> None:
    """Pin complete serialized APIs, not just backend identifiers or counts."""
    monkeypatch.setattr(cli, 'read_policy_xml', lambda path: '<backend id="{backend_id}" />')
    operation_policy = '<default />'
    monkeypatch.setattr('apimtypes._read_policy_xml', lambda path: operation_policy)
    expected = []
    for suffix, label in [('1', '1'), ('2', '2'), ('pool', 'Pool')]:
        expected.append(
            {
                'name': f'hello-world-aca-{suffix}',
                'displayName': f'Hello World (ACA {label})',
                'path': f'/aca-{suffix}',
                'description': f'This is the ACA API for Backend {label}',
                'operations': [
                    {
                        'name': 'GET',
                        'displayName': 'GET',
                        'urlTemplate': '/',
                        'description': f'This is a GET for Hello World on ACA Backend {label}',
                        'method': 'GET',
                        'policyXml': operation_policy,
                        'templateParameters': [],
                    }
                ],
                'serviceUrl': None,
                'subscriptionRequired': True,
                'policyXml': f'<backend id="aca-backend-{suffix}" />',
                'tags': [],
                'productNames': [],
                'enableLlmLogging': False,
            }
        )

    assert [api.to_dict() for api in cli.build_aca_hello_world_apis()] == expected


def test_discovery_failure_is_not_reported_as_success(architecture: tuple[ModuleType, tuple], deployment_boundary: tuple[Mock, Mock]) -> None:
    """Propagate discovery errors before constructing an infrastructure."""
    module, _ = architecture
    factory, resource_exists = deployment_boundary
    resource_exists.side_effect = RuntimeError('discovery unavailable')

    with pytest.raises(RuntimeError, match='discovery unavailable'):
        cli.main(replace(module.SPEC, factory=factory), [])

    factory.assert_not_called()
