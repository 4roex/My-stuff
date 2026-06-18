"""Economic news filter using an online calendar API."""
from typing import Dict, List, Tuple
from datetime import datetime, timedelta, timezone
import requests

from core.secure_settings import SecureSettings


class NewsFilter:
    """Checks for upcoming high-impact news affecting a currency pair."""

    def __init__(self):
        self.secure_settings = SecureSettings()

    def _extract_currencies(self, instrument: str) -> List[str]:
        parts = instrument.split("_")
        if len(parts) == 2:
            return [parts[0], parts[1]]
        return []

    def _parse_event_time(self, value: str) -> datetime | None:
        if not value:
            return None

        candidates = [
            "%Y-%m-%dT%H:%M:%S.%fZ",
            "%Y-%m-%dT%H:%M:%SZ",
            "%Y-%m-%d %H:%M:%S",
            "%Y-%m-%d %H:%M",
        ]
        for fmt in candidates:
            try:
                dt = datetime.strptime(value, fmt)
                if value.endswith("Z"):
                    return dt.replace(tzinfo=timezone.utc)
                return dt.replace(tzinfo=timezone.utc)
            except Exception:
                continue
        return None

    def _fetch_jblanked_events(self, currencies: List[str], high_impact_only: bool) -> List[Dict]:
        cfg = self.secure_settings.load_news_settings()
        api_key = cfg.get("api_key", "").strip()
        if not api_key:
            return []

        headers = {"Authorization": f"Bearer {api_key}"}
        events: List[Dict] = []

        for currency in currencies:
            params = {"currency": currency}
            if high_impact_only:
                params["impact"] = "High"

            try:
                resp = requests.get(
                    "https://www.jblanked.com/news/api/calendar/today/",
                    headers=headers,
                    params=params,
                    timeout=10,
                )
                if resp.status_code == 200:
                    data = resp.json()
                    if isinstance(data, list):
                        events.extend(data)
                    elif isinstance(data, dict):
                        for key in ("results", "data", "events"):
                            if isinstance(data.get(key), list):
                                events.extend(data[key])
                                break
            except Exception:
                continue

        return events

    def has_blocking_news(self, instrument: str) -> Tuple[bool, str]:
        cfg = self.secure_settings.load_news_settings()
        if not cfg.get("enabled", False):
            return False, ""

        provider = cfg.get("provider", "jblanked")
        high_impact_only = cfg.get("high_impact_only", True)
        before_min = int(cfg.get("block_minutes_before", 30))
        after_min = int(cfg.get("block_minutes_after", 30))

        currencies = self._extract_currencies(instrument)
        if not currencies:
            return False, ""

        if provider != "jblanked":
            return False, ""

        events = self._fetch_jblanked_events(currencies, high_impact_only)
        now = datetime.now(timezone.utc)

        for event in events:
            currency = str(event.get("currency", ""))
            impact = str(event.get("impact", event.get("Impact", "")))
            title = str(event.get("title", event.get("event", event.get("name", "News Event"))))
            dt_raw = (
                event.get("date")
                or event.get("datetime")
                or event.get("time")
                or event.get("Date")
            )
            event_time = self._parse_event_time(str(dt_raw))
            if not event_time:
                continue

            start_window = event_time - timedelta(minutes=before_min)
            end_window = event_time + timedelta(minutes=after_min)

            if start_window <= now <= end_window:
                return True, f"{currency} {impact} event: {title}"

        return False, ""