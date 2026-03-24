"""Tests for azure_cost module."""

import pytest

# APIM Samples imports
from apimtypes import APIM_SKU
from azure_cost import PRICING_AS_OF, PRICING_URL, ApimSkuPricing, get_apim_sku_pricing

# ------------------------------
#    CONSTANTS
# ------------------------------


class TestApimSkuPricingDataclass:
    """Tests for the ApimSkuPricing frozen dataclass."""

    def test_frozen_dataclass(self):
        """Verify ApimSkuPricing instances are immutable."""
        pricing = ApimSkuPricing(
            sku=APIM_SKU.BASICV2,
            base_monthly_cost=150.01,
            per_k_rate=0.003,
            included_requests_k=10_000,
        )
        with pytest.raises(AttributeError):
            pricing.base_monthly_cost = 999.99

    def test_equality(self):
        """Two ApimSkuPricing instances with the same values are equal."""
        a = ApimSkuPricing(sku=APIM_SKU.DEVELOPER, base_monthly_cost=48.04, per_k_rate=0.0, included_requests_k=0)
        b = ApimSkuPricing(sku=APIM_SKU.DEVELOPER, base_monthly_cost=48.04, per_k_rate=0.0, included_requests_k=0)
        assert a == b


# ------------------------------
#    MODULE-LEVEL CONSTANTS
# ------------------------------


class TestModuleConstants:
    """Tests for module-level constants."""

    def test_pricing_url(self):
        """PRICING_URL points to the official Azure APIM pricing page."""
        assert 'azure.microsoft.com' in PRICING_URL
        assert 'api-management' in PRICING_URL

    def test_pricing_as_of(self):
        """PRICING_AS_OF is a non-empty date string."""
        assert PRICING_AS_OF
        assert isinstance(PRICING_AS_OF, str)


# ------------------------------
#    get_apim_sku_pricing
# ------------------------------


class TestGetApimSkuPricing:
    """Tests for the get_apim_sku_pricing function."""

    # --- v2 tiers ---

    def test_basicv2_pricing(self):
        """BasicV2 returns expected base cost, overage rate, and included requests."""
        p = get_apim_sku_pricing(APIM_SKU.BASICV2)
        assert p.sku == APIM_SKU.BASICV2
        assert p.base_monthly_cost == pytest.approx(150.01)
        assert p.per_k_rate == pytest.approx(0.003)
        assert p.included_requests_k == 10_000

    def test_standardv2_pricing(self):
        """StandardV2 returns expected base cost, overage rate, and included requests."""
        p = get_apim_sku_pricing(APIM_SKU.STANDARDV2)
        assert p.sku == APIM_SKU.STANDARDV2
        assert p.base_monthly_cost == pytest.approx(700.00)
        assert p.per_k_rate == pytest.approx(0.0025)
        assert p.included_requests_k == 50_000

    def test_premiumv2_unlimited(self):
        """PremiumV2 has unlimited requests (per_k_rate and included_requests_k are 0)."""
        p = get_apim_sku_pricing(APIM_SKU.PREMIUMV2)
        assert p.sku == APIM_SKU.PREMIUMV2
        assert p.base_monthly_cost == pytest.approx(2_801.00)
        assert p.per_k_rate == 0.0
        assert p.included_requests_k == 0

    # --- Classic (v1) tiers ---

    def test_developer_pricing(self):
        """Developer tier returns base cost with no overage pricing."""
        p = get_apim_sku_pricing(APIM_SKU.DEVELOPER)
        assert p.sku == APIM_SKU.DEVELOPER
        assert p.base_monthly_cost == pytest.approx(48.04)
        assert p.per_k_rate == 0.0
        assert p.included_requests_k == 0

    def test_basic_pricing(self):
        """Basic (classic) tier returns base cost with no overage pricing."""
        p = get_apim_sku_pricing(APIM_SKU.BASIC)
        assert p.sku == APIM_SKU.BASIC
        assert p.base_monthly_cost == pytest.approx(147.17)
        assert p.per_k_rate == 0.0

    def test_standard_pricing(self):
        """Standard (classic) tier returns base cost with no overage pricing."""
        p = get_apim_sku_pricing(APIM_SKU.STANDARD)
        assert p.sku == APIM_SKU.STANDARD
        assert p.base_monthly_cost == pytest.approx(686.72)
        assert p.per_k_rate == 0.0

    def test_premium_pricing(self):
        """Premium (classic) tier returns base cost with no overage pricing."""
        p = get_apim_sku_pricing(APIM_SKU.PREMIUM)
        assert p.sku == APIM_SKU.PREMIUM
        assert p.base_monthly_cost == pytest.approx(2_795.17)
        assert p.per_k_rate == 0.0

    # --- All SKUs covered ---

    @pytest.mark.parametrize('sku', list(APIM_SKU))
    def test_all_skus_have_pricing(self, sku):
        """Every defined APIM_SKU must have a pricing entry."""
        p = get_apim_sku_pricing(sku)
        assert p.sku == sku
        assert p.base_monthly_cost > 0

    # --- Error case ---

    def test_invalid_sku_raises_value_error(self):
        """An unrecognised SKU string raises ValueError."""
        with pytest.raises(ValueError, match='No pricing data'):
            get_apim_sku_pricing('NonExistentSku')

    # --- Return type ---

    def test_returns_apim_sku_pricing(self):
        """Return value is an ApimSkuPricing instance."""
        p = get_apim_sku_pricing(APIM_SKU.BASICV2)
        assert isinstance(p, ApimSkuPricing)
