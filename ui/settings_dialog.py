"""Settings dialog for configuring bot parameters."""
import json
from typing import Dict, Any

from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QFormLayout,
    QLabel, QLineEdit, QDoubleSpinBox, QSpinBox, QComboBox,
    QPushButton, QListWidget, QListWidgetItem, QMessageBox
)
from PySide6.QtCore import Qt


class SettingsDialog(QDialog):
    """Dialog to edit account and LLM settings."""

    def __init__(self, config: Dict[str, Any], parent=None):
        super().__init__(parent)
        self.config = config
        self.setWindowTitle("Bot Settings")
        self.setMinimumSize(500, 700)
        self._build_ui()
        self._load_values()

    def _build_ui(self):
        layout = QVBoxLayout(self)

        account_box = QFormLayout()

        self.risk_spin = QDoubleSpinBox()
        self.risk_spin.setRange(0.1, 10.0)
        self.risk_spin.setSingleStep(0.1)
        self.risk_spin.setDecimals(1)
        self.risk_spin.setSuffix(" %")
        account_box.addRow("Max Risk per Trade:", self.risk_spin)

        self.daily_dd_spin = QDoubleSpinBox()
        self.daily_dd_spin.setRange(1.0, 50.0)
        self.daily_dd_spin.setSingleStep(0.5)
        self.daily_dd_spin.setDecimals(1)
        self.daily_dd_spin.setSuffix(" %")
        account_box.addRow("Daily Drawdown Limit:", self.daily_dd_spin)

        self.total_dd_spin = QDoubleSpinBox()
        self.total_dd_spin.setRange(1.0, 50.0)
        self.total_dd_spin.setSingleStep(0.5)
        self.total_dd_spin.setDecimals(1)
        self.total_dd_spin.setSuffix(" %")
        account_box.addRow("Total Drawdown Limit:", self.total_dd_spin)

        self.cooldown_spin = QSpinBox()
        self.cooldown_spin.setRange(0, 60)
        self.cooldown_spin.setSuffix(" min")
        account_box.addRow("Cooldown After SL:", self.cooldown_spin)

        layout.addLayout(account_box)

        layout.addWidget(QLabel("Active Instruments:"))
        self.instrument_list = QListWidget()
        self.instruments = [
            "EUR_USD", "GBP_USD", "USD_JPY", "USD_CHF", "AUD_USD", "NZD_USD",
            "EUR_GBP", "EUR_JPY", "GBP_JPY", "NZD_JPY", "AUD_JPY", "CAD_JPY",
            "USD_CAD", "EUR_CHF", "GBP_CHF", "AUD_NZD", "EUR_AUD", "GBP_AUD",
            "USD_SGD", "USD_HKD", "USD_CNH", "USD_MXN", "USD_ZAR", "USD_TRY",
            "USD_SEK", "USD_NOK", "USD_DKK", "USD_PLN", "USD_CZK", "USD_HUF",
            "EUR_NOK", "EUR_SEK", "EUR_DKK", "EUR_PLN", "EUR_HUF", "EUR_CZK",
            "GBP_NZD", "GBP_CAD", "AUD_CAD", "AUD_CHF", "NZD_CAD", "NZD_CHF",
            "CAD_CHF", "CHF_JPY", "SGD_JPY", "ZAR_JPY", "MXN_JPY", "NOK_JPY",
            "SEK_JPY", "HKD_JPY", "TRY_JPY", "PLN_JPY", "HUF_JPY", "XAU_USD",
            "XAG_USD", "WTI_USD", "BRENT_USD", "NATGAS_USD", "SOYBN_USD",
            "CORN_USD", "WHEAT_USD", "SPX500_USD", "NAS100_USD", "US30_USD",
            "GER30_USD", "UK100_USD", "JPN225_USD", "AUS200_USD", "EUSTX50_USD",
            "FR40_USD", "HK33_USD", "US2000_USD", "US10Y_USD", "US5Y_USD",
            "US2Y_USD", "DE10Y_USD", "UK10Y_USD", "JP10Y_USD", "EU50_USD"
        ]

        for inst in self.instruments:
            item = QListWidgetItem(inst)
            item.setFlags(item.flags() | Qt.ItemIsUserCheckable)
            item.setCheckState(Qt.Unchecked)
            self.instrument_list.addItem(item)

        self.instrument_list.setMaximumHeight(300)
        layout.addWidget(self.instrument_list)

        llm_box = QFormLayout()

        self.llm_url = QLineEdit()
        llm_box.addRow("Ollama URL:", self.llm_url)

        self.default_model = QComboBox()
        self.default_model.addItems([
            "llama3.1:8b", "llama3.2:3b", "qwen2.5:14b", "mistral:7b",
            "codellama:7b", "deepseek-coder:6.7b", "phi4:14b",
            "gemma2:9b", "gemma2:27b", "mixtral:8x7b", "llama3.3:70b"
        ])
        llm_box.addRow("Default Model:", self.default_model)

        self.fallback_model = QComboBox()
        self.fallback_model.addItems([
            "llama3.2:3b", "llama3.1:8b", "qwen2.5:14b", "mistral:7b",
            "codellama:7b", "deepseek-coder:6.7b", "phi4:14b",
            "gemma2:9b", "gemma2:27b", "mixtral:8x7b"
        ])
        llm_box.addRow("Fallback Model:", self.fallback_model)

        self.temp_spin = QDoubleSpinBox()
        self.temp_spin.setRange(0.0, 1.0)
        self.temp_spin.setSingleStep(0.05)
        self.temp_spin.setDecimals(2)
        llm_box.addRow("Temperature:", self.temp_spin)

        self.timeout_spin = QSpinBox()
        self.timeout_spin.setRange(5, 120)
        self.timeout_spin.setSuffix(" sec")
        llm_box.addRow("Timeout:", self.timeout_spin)

        layout.addLayout(llm_box)

        btn_layout = QHBoxLayout()

        self.save_btn = QPushButton("Save Settings")
        self.save_btn.setStyleSheet("background-color: #2ecc71; color: white; padding: 8px 20px;")
        self.save_btn.clicked.connect(self._save)
        btn_layout.addWidget(self.save_btn)

        self.cancel_btn = QPushButton("Cancel")
        self.cancel_btn.clicked.connect(self.reject)
        btn_layout.addWidget(self.cancel_btn)

        layout.addLayout(btn_layout)

    def _load_values(self):
        accounts = self.config.get("accounts", [])
        if isinstance(accounts, dict):
            accounts = [accounts]
        account = accounts[0] if accounts else {}

        risk = account.get("risk", {})

        self.risk_spin.setValue(risk.get("max_risk_percent", account.get("max_risk_percent", 1.0)))
        self.daily_dd_spin.setValue(risk.get("daily_drawdown_limit", account.get("daily_drawdown_limit", 5.0)))
        self.total_dd_spin.setValue(risk.get("total_drawdown_limit", account.get("total_drawdown_limit", 10.0)))
        self.cooldown_spin.setValue(risk.get("cooldown_minutes", account.get("cooldown_minutes", 15)))

        active_instruments = account.get("instruments", ["EUR_USD", "GBP_USD", "USD_JPY"])
        for i in range(self.instrument_list.count()):
            item = self.instrument_list.item(i)
            item.setCheckState(Qt.Checked if item.text() in active_instruments else Qt.Unchecked)

        llm = self.config.get("llm", {})
        self.llm_url.setText(llm.get("url", "http://localhost:11434"))
        self.default_model.setCurrentText(llm.get("default_model", "llama3.1:8b"))
        self.fallback_model.setCurrentText(llm.get("fallback_model", "llama3.2:3b"))
        self.temp_spin.setValue(llm.get("temperature", 0.1))
        self.timeout_spin.setValue(llm.get("timeout", 30))

    def _save(self):
        accounts = self.config.get("accounts", [])
        if isinstance(accounts, dict):
            accounts = [accounts]
            self.config["accounts"] = accounts

        if accounts:
            account = accounts[0]
            risk = account.setdefault("risk", {})

            risk["max_risk_percent"] = self.risk_spin.value()
            risk["daily_drawdown_limit"] = self.daily_dd_spin.value()
            risk["total_drawdown_limit"] = self.total_dd_spin.value()
            risk["cooldown_minutes"] = self.cooldown_spin.value()

            account["max_risk_percent"] = risk["max_risk_percent"]
            account["daily_drawdown_limit"] = risk["daily_drawdown_limit"]
            account["total_drawdown_limit"] = risk["total_drawdown_limit"]
            account["cooldown_minutes"] = risk["cooldown_minutes"]

            active_instruments = []
            for i in range(self.instrument_list.count()):
                item = self.instrument_list.item(i)
                if item.checkState() == Qt.Checked:
                    active_instruments.append(item.text())
            account["instruments"] = active_instruments

        llm = self.config.setdefault("llm", {})
        llm["url"] = self.llm_url.text().strip()
        llm["default_model"] = self.default_model.currentText()
        llm["fallback_model"] = self.fallback_model.currentText()
        llm["temperature"] = self.temp_spin.value()
        llm["timeout"] = self.timeout_spin.value()

        try:
            with open("config/accounts.json", "w") as f:
                json.dump(self.config, f, indent=2)
            QMessageBox.information(self, "Saved", "Settings saved successfully.")
            self.accept()
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Failed to save: {str(e)}")