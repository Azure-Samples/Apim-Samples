"""Reusable script to create Application Gateway + APIM (Internal) infrastructure.

Autoreload: reload_conditional
Function edits reload when imported. Recreate deployment specifications after state changes; CLI subprocesses always load fresh source.
"""

# APIM Samples imports
import infrastructure_cli as cli
from apimtypes import APIM_SKU, INFRASTRUCTURE
from infrastructures import AppGwApimInfrastructure

SPEC = cli.InfrastructureCliSpec(
    infrastructure=INFRASTRUCTURE.APPGW_APIM,
    factory=AppGwApimInfrastructure,
    description='Create APPGW-APIM infrastructure (VNet Internal)',
    sku_choices=('Developer', 'Premium', 'Premiumv2'),
    default_sku='Developer',
    aca_apis=cli.AcaApis.OPTIONAL,
    supports_strict_nsg=True,
)


def create_infrastructure(
    location: str,
    index: int,
    apim_sku: APIM_SKU,
    no_aca: bool = False,
    use_strict_nsg: bool = False,
    rg_exists: bool | None = None,
) -> None:
    """Create the Application Gateway + APIM infrastructure."""
    success = cli.create_infrastructure(SPEC, location, index, apim_sku, no_aca=no_aca, use_strict_nsg=use_strict_nsg, rg_exists=rg_exists)
    raise SystemExit(0 if success else 1)


def main() -> None:
    """Run the architecture's existing command-line interface."""
    cli.main(SPEC)


if __name__ == '__main__':  # pragma: no cover
    main()
