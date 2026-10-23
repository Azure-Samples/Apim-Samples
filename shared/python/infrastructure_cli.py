"""Shared parsing and deployment dispatch for infrastructure creation scripts."""

import argparse
from collections.abc import Callable
from dataclasses import dataclass
from enum import StrEnum
from pathlib import Path
from typing import NotRequired, TypedDict

# APIM Samples imports
import azure_resources as az
from apimtypes import API, APIM_SKU, BACKEND_XML_POLICY_PATH, INFRASTRUCTURE, GET_APIOperation, Region
from infrastructures import Infrastructure
from policy_files import read_policy_xml


class AcaApis(StrEnum):
    """Whether the creation script publishes the Container Apps demo APIs."""

    NONE = 'none'
    ALWAYS = 'always'
    OPTIONAL = 'optional'


@dataclass(frozen=True)
class InfrastructureCliSpec:
    """The architecture-specific defaults and capabilities of a creation CLI."""

    infrastructure: INFRASTRUCTURE
    factory: Callable[..., Infrastructure]
    description: str
    sku_choices: tuple[str, ...]
    default_sku: str
    aca_apis: AcaApis = AcaApis.NONE
    supports_strict_nsg: bool = False


class _InfrastructureArguments(TypedDict):
    rg_exists: bool | None
    infra_apis: NotRequired[list[API]]
    use_strict_nsg: NotRequired[bool]


def build_aca_hello_world_apis() -> list[API]:
    """Build the existing demo URLs with explicit routing to MockAPI's exact Hello World path."""
    backend_policy = read_policy_xml(str(Path(BACKEND_XML_POLICY_PATH).with_name('mockapi-backend.xml')))

    return [
        API(
            f'hello-world-aca-{suffix}',
            f'Hello World (ACA {display_suffix})',
            f'/aca-{suffix}',
            f'This is the ACA API for Backend {display_suffix}',
            backend_policy.format(backend_id=f'aca-backend-{suffix}'),
            [GET_APIOperation(f'This is a GET for Hello World on ACA Backend {display_suffix}')],
        )
        for suffix, display_suffix in (('1', '1'), ('2', '2'), ('pool', 'Pool'))
    ]


def build_parser(spec: InfrastructureCliSpec) -> argparse.ArgumentParser:
    """Create the existing argument surface for one infrastructure."""
    parser = argparse.ArgumentParser(description=spec.description)
    parser.add_argument('--location', default=Region.EAST_US_2, help=f'Azure region (default: {Region.EAST_US_2})')
    parser.add_argument('--index', type=int, help='Infrastructure index')
    parser.add_argument('--sku', choices=spec.sku_choices, default=spec.default_sku, help=f'APIM SKU (default: {spec.default_sku})')
    if spec.aca_apis == AcaApis.OPTIONAL:
        parser.add_argument('--no-aca', action='store_true', help='Disable Azure Container Apps')
    if spec.supports_strict_nsg:
        parser.add_argument('--use-strict-nsg', action='store_true', help='Deploy strict NSGs for supported subnets')
    parser.add_argument('--rg-exists', action=argparse.BooleanOptionalAction, default=None, help='Pre-checked resource group existence state')

    return parser


def create_infrastructure(
    spec: InfrastructureCliSpec,
    location: str,
    index: int | None,
    apim_sku: APIM_SKU,
    *,
    no_aca: bool = False,
    use_strict_nsg: bool = False,
    rg_exists: bool | None = None,
) -> bool:
    """Dispatch a deployment without changing its resource-group or API contract."""
    infrastructure_exists = rg_exists
    if infrastructure_exists is None:
        infrastructure_exists = az.does_resource_group_exist(az.get_infra_rg_name(spec.infrastructure, index))

    infrastructure_args: _InfrastructureArguments = {'rg_exists': rg_exists}
    if spec.aca_apis == AcaApis.ALWAYS or (spec.aca_apis == AcaApis.OPTIONAL and not no_aca):
        infrastructure_args['infra_apis'] = build_aca_hello_world_apis()
    elif spec.aca_apis == AcaApis.OPTIONAL:
        infrastructure_args['infra_apis'] = []
    if spec.supports_strict_nsg:
        infrastructure_args['use_strict_nsg'] = use_strict_nsg

    infrastructure = spec.factory(location, index, apim_sku, **infrastructure_args)

    return infrastructure.deploy_infrastructure(infrastructure_exists).success


def main(spec: InfrastructureCliSpec, argv: list[str] | None = None) -> None:
    """Parse arguments and exit with the existing deployment success/failure code."""
    args = build_parser(spec).parse_args(argv)
    success = create_infrastructure(
        spec,
        args.location,
        args.index,
        APIM_SKU(args.sku),
        no_aca=getattr(args, 'no_aca', False),
        use_strict_nsg=getattr(args, 'use_strict_nsg', False),
        rg_exists=args.rg_exists,
    )
    raise SystemExit(0 if success else 1)
