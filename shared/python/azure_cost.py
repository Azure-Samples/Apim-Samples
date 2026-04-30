"""Azure API Management and Azure OpenAI pricing helpers.

Provides hard-coded retail pricing for APIM SKUs and Azure OpenAI models so
that cost-allocation notebooks can derive base monthly cost, overage rate,
included request allowances, and token rates from the deployed SKU and model
without manual look-up.

APIM pricing source (as of March 2026):
    https://azure.microsoft.com/pricing/details/api-management/

Azure OpenAI pricing source (as of April 2026):
    https://azure.microsoft.com/pricing/details/cognitive-services/openai-service/

Classic-tier (v1) SKUs do not publish a per-request overage rate;
``get_apim_sku_pricing`` returns ``0.0`` for both ``per_k_rate`` and
``included_requests_k`` on those tiers.
"""

from __future__ import annotations

from dataclasses import dataclass

# APIM Samples imports
from apimtypes import APIM_SKU

# Pricing pages used as the authoritative source for all numbers below.
APIM_PRICING_URL = 'https://azure.microsoft.com/pricing/details/api-management/'
APIM_PRICING_AS_OF = 'March 2026'
AOAI_PRICING_URL = 'https://azure.microsoft.com/pricing/details/cognitive-services/openai-service/'
AOAI_PRICING_AS_OF = 'April 2026'


@dataclass(frozen=True)
class ApimSkuPricing:
    """Retail pricing for a single APIM SKU (single unit)."""

    sku: APIM_SKU
    base_monthly_cost: float
    per_k_rate: float
    included_requests_k: float


# v2 tiers
_BASICV2 = ApimSkuPricing(
    sku=APIM_SKU.BASICV2,
    base_monthly_cost=150.01,
    per_k_rate=0.003,  # $3 per 1M = $0.003 per 1K
    included_requests_k=10_000,  # 10M requests = 10 000 K
)

_STANDARDV2 = ApimSkuPricing(
    sku=APIM_SKU.STANDARDV2,
    base_monthly_cost=700.00,
    per_k_rate=0.0025,  # $2.50 per 1M = $0.0025 per 1K
    included_requests_k=50_000,  # 50M requests = 50 000 K
)

_PREMIUMV2 = ApimSkuPricing(
    sku=APIM_SKU.PREMIUMV2,
    base_monthly_cost=2_801.00,
    per_k_rate=0.0,  # unlimited included
    included_requests_k=0,  # unlimited (0 = no overage concept)
)

# Classic (v1) tiers — per-request overage is not published for these SKUs.
_DEVELOPER = ApimSkuPricing(
    sku=APIM_SKU.DEVELOPER,
    base_monthly_cost=48.04,
    per_k_rate=0.0,
    included_requests_k=0,
)

_BASIC = ApimSkuPricing(
    sku=APIM_SKU.BASIC,
    base_monthly_cost=147.17,
    per_k_rate=0.0,
    included_requests_k=0,
)

_STANDARD = ApimSkuPricing(
    sku=APIM_SKU.STANDARD,
    base_monthly_cost=686.72,
    per_k_rate=0.0,
    included_requests_k=0,
)

_PREMIUM = ApimSkuPricing(
    sku=APIM_SKU.PREMIUM,
    base_monthly_cost=2_795.17,
    per_k_rate=0.0,
    included_requests_k=0,
)

_PRICING: dict[APIM_SKU, ApimSkuPricing] = {
    APIM_SKU.BASICV2: _BASICV2,
    APIM_SKU.STANDARDV2: _STANDARDV2,
    APIM_SKU.PREMIUMV2: _PREMIUMV2,
    APIM_SKU.DEVELOPER: _DEVELOPER,
    APIM_SKU.BASIC: _BASIC,
    APIM_SKU.STANDARD: _STANDARD,
    APIM_SKU.PREMIUM: _PREMIUM,
}


def get_apim_sku_pricing(sku: APIM_SKU) -> ApimSkuPricing:
    """Return retail pricing for the given APIM SKU.

    Args:
        sku: An ``APIM_SKU`` enum member.

    Returns:
        An ``ApimSkuPricing`` dataclass with ``base_monthly_cost``,
        ``per_k_rate``, and ``included_requests_k``.

    Raises:
        ValueError: If the SKU is not recognised.
    """
    pricing = _PRICING.get(sku)
    if pricing is None:
        raise ValueError(f'No pricing data for SKU {sku!r}. Check {APIM_PRICING_URL} for current pricing.')

    return pricing


# ---------------------------------------------------------------------------
#  Azure OpenAI model pricing
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class ModelPricing:
    """Retail per-token pricing for an Azure OpenAI model deployment."""

    model: str
    sku: str
    prompt_rate_per_k: float
    completion_rate_per_k: float


# Key format: (lower-cased model name, lower-cased sku name)
_MODEL_PRICING: dict[tuple[str, str], ModelPricing] = {
    ('gpt-5-mini', 'globalstandard'): ModelPricing(
        model='gpt-5-mini',
        sku='GlobalStandard',
        prompt_rate_per_k=0.00025,  # $0.25 / 1M input tokens
        completion_rate_per_k=0.002,  # $2.00 / 1M output tokens
    ),
    ('gpt-4o-mini', 'globalstandard'): ModelPricing(
        model='gpt-4o-mini',
        sku='GlobalStandard',
        prompt_rate_per_k=0.00015,  # $0.15 / 1M input tokens
        completion_rate_per_k=0.0006,  # $0.60 / 1M output tokens
    ),
}


def get_model_pricing(model: str, sku: str = 'GlobalStandard') -> ModelPricing:
    """Return retail per-token pricing for an Azure OpenAI model deployment.

    Args:
        model: Model name (e.g. ``'gpt-5-mini'``). Case-insensitive.
        sku:   Deployment SKU name (e.g. ``'GlobalStandard'``).
               Case-insensitive. Defaults to ``'GlobalStandard'``.

    Returns:
        A ``ModelPricing`` dataclass with ``prompt_rate_per_k`` and
        ``completion_rate_per_k``.

    Raises:
        ValueError: If the model/SKU combination is not recognised.
    """
    key = (model.lower(), sku.lower())
    pricing = _MODEL_PRICING.get(key)
    if pricing is None:
        raise ValueError(f'No pricing data for model {model!r} with SKU {sku!r}. Check {AOAI_PRICING_URL} for current pricing.')

    return pricing
