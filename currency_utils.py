import re
from typing import Any

EXCHANGE_RATES = {
    "USD": 1.0,
    "INR": 85.0,
    "EUR": 0.92,
    "GBP": 0.78
}

CURRENCY_SYMBOLS = {
    "USD": "$",
    "INR": "₹",
    "EUR": "€",
    "GBP": "£"
}

def detect_budget(text: str) -> tuple[float | None, str]:
    """
    Detects budget amount and currency code from text.
    Handles 'INR 25 lakhs', '25L INR', '₹2,500,000', '$50,000', '50k USD', etc.
    Returns (budget_amount_in_detected_currency, currency_code).
    """
    if not text:
        return (None, "USD")

    text_upper = text.upper()

    # Determine currency
    currency = "USD"
    if "INR" in text_upper or "RS" in text_upper or "RUPEES" in text_upper or "LAKH" in text_upper or "CRORE" in text_upper or "₹" in text:
        currency = "INR"
    elif "EUR" in text_upper or "EURO" in text_upper or "€" in text:
        currency = "EUR"
    elif "GBP" in text_upper or "POUND" in text_upper or "£" in text:
        currency = "GBP"
    elif "USD" in text_upper or "$" in text:
        currency = "USD"

    # Match Lakhs: e.g., "25 lakhs", "25 lakh", "25L"
    m_lakh = re.search(r"(\d+(?:\.\d+)?)\s*(?:lakhs?|lakh|l)\b", text, re.IGNORECASE)
    if m_lakh:
        amount = float(m_lakh.group(1)) * 100_000.0
        return (amount, currency)

    # Match Crores: e.g., "2 crores", "1.5 crore", "2Cr"
    m_crore = re.search(r"(\d+(?:\.\d+)?)\s*(?:crores?|crore|cr)\b", text, re.IGNORECASE)
    if m_crore:
        amount = float(m_crore.group(1)) * 10_000_000.0
        return (amount, currency)

    # Match Thousand 'k': e.g., "50k"
    m_k = re.search(r"(\d+(?:\.\d+)?)\s*k\b", text, re.IGNORECASE)
    if m_k:
        amount = float(m_k.group(1)) * 1_000.0
        return (amount, currency)

    # Match explicit numeric with currency symbol or code: e.g. "INR 2,500,000", "$50,000", "2500000"
    m_num = re.search(r"(?:INR|USD|EUR|GBP|₹|\$|€|£)?\s*([\d,]{4,12})(?:\.\d+)?", text, re.IGNORECASE)
    if m_num:
        raw_num = m_num.group(1).replace(",", "")
        try:
            amount = float(raw_num)
            return (amount, currency)
        except ValueError:
            pass

    return (None, currency)


def convert_from_usd(amount_usd: float, target_currency: str) -> float:
    rate = EXCHANGE_RATES.get(target_currency.upper(), 1.0)
    return amount_usd * rate


def format_currency(amount: float, currency: str) -> str:
    symbol = CURRENCY_SYMBOLS.get(currency.upper(), "$")
    if currency.upper() == "INR":
        if amount >= 10_000_000:
            return f"₹{amount / 10_000_000:.2f} Crores (INR {amount:,.0f})"
        elif amount >= 100_000:
            return f"₹{amount / 100_000:.2f} Lakhs (INR {amount:,.0f})"
        else:
            return f"₹{amount:,.0f} INR"
    return f"{symbol}{amount:,.0f} {currency}"


def check_budget_risk(min_cost_in_currency: float, budget_amount: float | None, currency: str) -> tuple[bool, str]:
    """
    Checks if min_cost_in_currency exceeds budget_amount.
    Returns (has_risk, warning_message).
    """
    if not budget_amount or budget_amount <= 0:
        return (False, "")

    if min_cost_in_currency > budget_amount:
        overrun = min_cost_in_currency - budget_amount
        pct = (overrun / budget_amount) * 100.0
        cost_str = format_currency(min_cost_in_currency, currency)
        budget_str = format_currency(budget_amount, currency)
        overrun_str = format_currency(overrun, currency)
        msg = (
            f"**Budget Risk Warning:** Estimated minimum project cost of {cost_str} "
            f"exceeds the stated budget constraint of {budget_str} by {overrun_str} ({pct:.1f}% overrun). "
            f"Recommended mitigation: Scope reduction or phased roll-out."
        )
        return (True, msg)

    return (False, "")


def synchronize_estimation_currency(estimation_md: str, target_currency: str) -> str:
    """
    Ensures that all currency symbols and codes in estimation_md match target_currency.
    Replaces mismatched currency headers/symbols (e.g. '$', '€', '£', '₹', 'USD', 'EUR', 'GBP')
    with target_currency and its corresponding symbol.
    """
    if not estimation_md:
        return estimation_md

    curr = target_currency.upper()
    target_symbol = CURRENCY_SYMBOLS.get(curr, "$")

    synced_md = re.sub(
        r"Estimated Cost \((?:USD|INR|EUR|GBP|\$|₹|€|£)\)",
        f"Estimated Cost ({curr})",
        estimation_md,
        flags=re.IGNORECASE
    )

    if curr != "USD" and "1 USD =" not in synced_md:
        rate_val = EXCHANGE_RATES.get(curr, 1.0)
        synced_md += f"\n\n*Note: Exchange rate assumption: 1 USD = {rate_val:.2f} {curr}.*\n"

    return synced_md
