"""Amounts in words, Indian style (lakh, crore), for payment vouchers."""

from decimal import ROUND_HALF_UP, Decimal

_ONES = (
    "", "one", "two", "three", "four", "five", "six", "seven", "eight", "nine", "ten", "eleven", "twelve",
    "thirteen", "fourteen", "fifteen", "sixteen", "seventeen", "eighteen", "nineteen",
)  # fmt: skip
_TENS = ("", "", "twenty", "thirty", "forty", "fifty", "sixty", "seventy", "eighty", "ninety")


def _below_hundred(n: int) -> str:
    if n < 20:
        return _ONES[n]
    return _TENS[n // 10] + ("-" + _ONES[n % 10] if n % 10 else "")


def _below_thousand(n: int) -> str:
    hundreds, rest = divmod(n, 100)
    parts = []
    if hundreds:
        parts.append(f"{_ONES[hundreds]} hundred")
    if rest:
        parts.append(_below_hundred(rest))
    return " ".join(parts)


def number_in_words(n: int) -> str:
    if n == 0:
        return "zero"
    parts = []
    for size, name in ((10_000_000, "crore"), (100_000, "lakh"), (1_000, "thousand")):
        count, n = divmod(n, size)
        if count:
            parts.append(f"{number_in_words(count) if count >= 100 else _below_hundred(count)} {name}")
    if n:
        parts.append(_below_thousand(n))
    return " ".join(parts)


def rupees_in_words(amount: Decimal) -> str:
    """Decimal('17682.50') -> 'Rupees seventeen thousand six hundred eighty-two and fifty paise only'"""
    value = amount.quantize(Decimal("0.01"), ROUND_HALF_UP)
    rupees = int(value)
    paise = int((value - rupees) * 100)
    text = f"Rupees {number_in_words(rupees)}"
    if paise:
        text += f" and {_below_hundred(paise)} paise"
    return text + " only"
