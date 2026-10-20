"""This module provides a reusable way to create Simple APIM infrastructure that can be called from notebooks or other scripts."""

# APIM Samples imports
import infrastructure_cli as cli
from apimtypes import APIM_SKU, INFRASTRUCTURE
from infrastructures import SimpleApimInfrastructure

SPEC = cli.InfrastructureCliSpec(
    infrastructure=INFRASTRUCTURE.SIMPLE_APIM,
    factory=SimpleApimInfrastructure,
    description='Create Simple APIM infrastructure',
    sku_choices=('Basicv2', 'Standardv2', 'Premiumv2'),
    default_sku='Basicv2',
    aca_apis=cli.AcaApis.NONE,
    supports_strict_nsg=False,
)


def create_infrastructure(location: str, index: int, apim_sku: APIM_SKU, rg_exists: bool | None = None) -> None:
    """Create the simple APIM infrastructure."""
    success = cli.create_infrastructure(SPEC, location, index, apim_sku, rg_exists=rg_exists)
    raise SystemExit(0 if success else 1)


def main() -> None:
    """Run the architecture's existing command-line interface."""
    cli.main(SPEC)


if __name__ == '__main__':  # pragma: no cover
    main()
