"""Correlation filter for FX instruments."""
from typing import Dict, List, Tuple


class CorrelationFilter:
    """Simple rule-based FX correlation filter."""

    def __init__(self):
        # Positive correlation groups
        self.positive_groups = [
            {"EUR_USD", "GBP_USD", "AUD_USD", "NZD_USD"},
            {"USD_CHF", "EUR_USD"},
            {"USD_CAD", "AUD_USD", "NZD_USD"},
            {"EUR_JPY", "GBP_JPY", "AUD_JPY", "NZD_JPY"},
        ]

        # Negative or inverse relationship groups
        self.inverse_pairs = {
            ("EUR_USD", "USD_CHF"),
            ("GBP_USD", "USD_JPY"),
            ("AUD_USD", "USD_CAD"),
        }

    def is_blocked(
        self,
        new_instrument: str,
        new_direction: str,
        open_trades: List[Dict]
    ) -> Tuple[bool, str]:
        """
        Return (blocked, reason).
        Blocks:
        - Same direction in strongly positively correlated pairs.
        - Opposite direction in inverse pairs.
        """
        for trade in open_trades:
            inst = trade.get("instrument", "")
            units = float(trade.get("currentUnits", 0))
            if units == 0:
                continue
            existing_direction = "BUY" if units > 0 else "SELL"

            if self._same_positive_group(new_instrument, inst):
                if existing_direction == new_direction:
                    return True, f"{new_instrument} is positively correlated with open {inst} ({existing_direction})"

            if self._is_inverse_pair(new_instrument, inst):
                if existing_direction != new_direction:
                    return True, f"{new_instrument} is inversely correlated with open {inst} ({existing_direction})"

        return False, ""

    def _same_positive_group(self, a: str, b: str) -> bool:
        for group in self.positive_groups:
            if a in group and b in group and a != b:
                return True
        return False

    def _is_inverse_pair(self, a: str, b: str) -> bool:
        return (a, b) in self.inverse_pairs or (b, a) in self.inverse_pairs