"""Secure settings storage for API keys, broker tokens, and app preferences."""
from typing import Dict, Any

import keyring
from PySide6.QtCore import QSettings


class SecureSettings:
    """Stores non-secret settings in QSettings and secrets in OS keyring."""

    ORG_NAME = "4XPro"
    APP_NAME = "ForexLLMBot"
    SERVICE_NAME = "4XPro.ForexLLMBot"

    def __init__(self):
        self.settings = QSettings(self.ORG_NAME, self.APP_NAME)

    # ---------- secret storage ----------
    def set_secret(self, name: str, value: str):
        if value is None:
            value = ""
        keyring.set_password(self.SERVICE_NAME, name, value)

    def get_secret(self, name: str) -> str:
        value = keyring.get_password(self.SERVICE_NAME, name)
        return value or ""

    def delete_secret(self, name: str):
        try:
            keyring.delete_password(self.SERVICE_NAME, name)
        except Exception:
            pass

    # ---------- normal settings ----------
    def set_value(self, key: str, value: Any):
        self.settings.setValue(key, value)

    def get_value(self, key: str, default=None, value_type=None):
        if value_type is not None:
            return self.settings.value(key, default, type=value_type)
        return self.settings.value(key, default)

    def remove_value(self, key: str):
        self.settings.remove(key)

    # ---------- news settings ----------
    def save_news_settings(self, data: Dict[str, Any]):
        for k, v in data.items():
            if k == "api_key":
                self.set_secret("news_api_key", v or "")
            else:
                self.set_value(f"news/{k}", v)

    def load_news_settings(self) -> Dict[str, Any]:
        return {
            "enabled": self.get_value("news/enabled", False, bool),
            "provider": self.get_value("news/provider", "jblanked", str),
            "block_minutes_before": self.get_value("news/block_minutes_before", 30, int),
            "block_minutes_after": self.get_value("news/block_minutes_after", 30, int),
            "high_impact_only": self.get_value("news/high_impact_only", True, bool),
            "api_key": self.get_secret("news_api_key"),
        }

    def delete_news_api_key(self):
        self.delete_secret("news_api_key")

    # ---------- broker token helpers ----------
    def account_token_key(self, account_id: str) -> str:
        return f"oanda_token::{account_id}"

    def set_account_token(self, account_id: str, token: str):
        self.set_secret(self.account_token_key(account_id), token or "")

    def get_account_token(self, account_id: str) -> str:
        return self.get_secret(self.account_token_key(account_id))

    def delete_account_token(self, account_id: str):
        self.delete_secret(self.account_token_key(account_id))