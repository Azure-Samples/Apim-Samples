"""Tests for azure_cost module."""

import pytest

# APIM Samples imports
from apimtypes import APIM_SKU
from azure_cost import (
    AOAI_PRICING_AS_OF,
    AOAI_PRICING_URL,
    APIM_PRICING_AS_OF,
    APIM_PRICING_URL,
    ApimSkuPricing,
    ModelPricing,
    get_apim_sku_pricing,
    get_model_pricing,
)

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

    def test_apim_pricing_url(self):
        """APIM_PRICING_URL points to the official Azure APIM pricing page."""
        assert 'azure.microsoft.com' in APIM_PRICING_URL
        assert 'api-management' in APIM_PRICING_URL

    def test_apim_pricing_as_of(self):
        """APIM_PRICING_AS_OF is a non-empty date string."""
        assert APIM_PRICING_AS_OF
        assert isinstance(APIM_PRICING_AS_OF, str)

    def test_aoai_pricing_url(self):
        """AOAI_PRICING_URL points to the official Azure OpenAI pricing page."""
        assert 'azure.microsoft.com' in AOAI_PRICING_URL
        assert 'openai-service' in AOAI_PRICING_URL

    def test_aoai_pricing_as_of(self):
        """AOAI_PRICING_AS_OF is a non-empty date string."""
        assert AOAI_PRICING_AS_OF
        assert isinstance(AOAI_PRICING_AS_OF, str)


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


# ------------------------------
#    ModelPricing dataclass
# ------------------------------


class TestModelPricingDataclass:
    """Tests for the ModelPricing frozen dataclass."""

    def test_frozen_dataclass(self):
        """Verify ModelPricing instances are immutable."""
        pricing = ModelPricing(model='gpt-5-mini', sku='GlobalStandard', prompt_rate_per_k=0.00025, completion_rate_per_k=0.002)
        with pytest.raises(AttributeError):
            pricing.prompt_rate_per_k = 999.0

    def test_equality(self):
        """Two ModelPricing instances with the same values are equal."""
        a = ModelPricing(model='gpt-5-mini', sku='GlobalStandard', prompt_rate_per_k=0.00025, completion_rate_per_k=0.002)
        b = ModelPricing(model='gpt-5-mini', sku='GlobalStandard', prompt_rate_per_k=0.00025, completion_rate_per_k=0.002)
        assert a == b


# ------------------------------
#    get_model_pricing
# ------------------------------


class TestGetModelPricing:
    """Tests for the get_model_pricing function."""

    def test_gpt5_mini_global_standard(self):
        """gpt-5-mini GlobalStandard returns expected token rates."""
        p = get_model_pricing('gpt-5-mini')
        assert p.model == 'gpt-5-mini'
        assert p.sku == 'GlobalStandard'
        assert p.prompt_rate_per_k == pytest.approx(0.00025)
        assert p.completion_rate_per_k == pytest.approx(0.002)

    def test_case_insensitive_model(self):
        """Model name lookup is case-insensitive."""
        p = get_model_pricing('GPT-5-Mini')
        assert p.model == 'gpt-5-mini'

    def test_case_insensitive_sku(self):
        """SKU name lookup is case-insensitive."""
        p = get_model_pricing('gpt-5-mini', 'globalstandard')
        assert p.sku == 'GlobalStandard'

    def test_default_sku_is_global_standard(self):
        """Default SKU parameter is GlobalStandard."""
        p = get_model_pricing('gpt-5-mini')
        assert p.sku == 'GlobalStandard'

    def test_invalid_model_raises_value_error(self):
        """An unrecognised model raises ValueError."""
        with pytest.raises(ValueError, match='No pricing data'):
            get_model_pricing('nonexistent-model')

    def test_invalid_sku_raises_value_error(self):
        """An unrecognised SKU for a valid model raises ValueError."""
        with pytest.raises(ValueError, match='No pricing data'):
            get_model_pricing('gpt-5-mini', 'NonExistentSku')

    def test_returns_model_pricing(self):
        """Return value is a ModelPricing instance."""
        p = get_model_pricing('gpt-5-mini')
        assert isinstance(p, ModelPricing)
