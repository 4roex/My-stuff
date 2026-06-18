"""Risk settings dialog for configuring trade execution parameters."""
from typing import Dict, Any

from PySide6.QtWidgets import (
    QDialog, QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QCheckBox, QDoubleSpinBox, QSpinBox, QGroupBox, QGridLayout,
    QDialogButtonBox, QLineEdit, QComboBox, QScrollArea
)
from PySide6.QtCore import Qt
from core.secure_settings import SecureSettings


class RiskSettingsDialog(QDialog):
    """Dialog to configure risk management and order execution settings."""

    def __init__(self, account: Dict[str, Any], parent=None):
        super().__init__(parent)
        self.account = account
        self.secure_settings = SecureSettings()
        self.setWindowTitle(f"Risk Settings — {account.get('name', 'Account')}")
        self.resize(1100, 760)
        self.setMinimumSize(900, 650)
        self._build_ui()
        self._load_values()

    def _build_ui(self):
        outer_layout = QVBoxLayout(self)
        outer_layout.setContentsMargins(10, 10, 10, 10)
        outer_layout.setSpacing(10)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        scroll.setVerticalScrollBarPolicy(Qt.ScrollBarAsNeeded)

        content = QWidget()
        self.content_layout = QGridLayout(content)
        self.content_layout.setSpacing(12)
        self.content_layout.setContentsMargins(8, 8, 8, 8)

        self._build_position_sizing()
        self._build_sltp()
        self._build_trailing()
        self._build_trade_management()
        self._build_limits_filters()
        self._build_news_filter()
        self._build_session_filter()
        self._build_notifications()

        self.content_layout.addWidget(self.position_box, 0, 0)
        self.content_layout.addWidget(self.sltp_box, 0, 1)

        self.content_layout.addWidget(self.trailing_box, 1, 0)
        self.content_layout.addWidget(self.mgmt_box, 1, 1)

        self.content_layout.addWidget(self.limits_box, 2, 0)
        self.content_layout.addWidget(self.news_box, 2, 1)

        self.content_layout.addWidget(self.session_box, 3, 0)
        self.content_layout.addWidget(self.notify_box, 3, 1)

        self.content_layout.setColumnStretch(0, 1)
        self.content_layout.setColumnStretch(1, 1)
        self.content_layout.setRowStretch(4, 1)

        scroll.setWidget(content)
        outer_layout.addWidget(scroll)

        bottom_row = QHBoxLayout()
        self.reset_btn = QPushButton("Reset to Defaults")
        self.reset_btn.clicked.connect(self._reset_defaults)
        bottom_row.addWidget(self.reset_btn)
        bottom_row.addStretch()

        self.buttons = QDialogButtonBox(QDialogButtonBox.Save | QDialogButtonBox.Cancel)
        self.buttons.accepted.connect(self._save_and_close)
        self.buttons.rejected.connect(self.reject)
        bottom_row.addWidget(self.buttons)

        outer_layout.addLayout(bottom_row)

    def _build_position_sizing(self):
        self.position_box = QGroupBox("Position Sizing")
        grid = QGridLayout(self.position_box)

        grid.addWidget(QLabel("Risk per Trade (%)"), 0, 0)
        self.risk_percent_spin = QDoubleSpinBox()
        self.risk_percent_spin.setRange(0.1, 10.0)
        self.risk_percent_spin.setDecimals(2)
        self.risk_percent_spin.setSingleStep(0.1)
        grid.addWidget(self.risk_percent_spin, 0, 1)

        grid.addWidget(QLabel("Max Open Trades"), 1, 0)
        self.max_trades_spin = QSpinBox()
        self.max_trades_spin.setRange(1, 20)
        grid.addWidget(self.max_trades_spin, 1, 1)

        grid.addWidget(QLabel("Min Position Size (units)"), 2, 0)
        self.min_units_spin = QSpinBox()
        self.min_units_spin.setRange(100, 100000)
        self.min_units_spin.setSingleStep(1000)
        grid.addWidget(self.min_units_spin, 2, 1)

        grid.addWidget(QLabel("Leverage Cap (x)"), 3, 0)
        self.leverage_spin = QSpinBox()
        self.leverage_spin.setRange(1, 100)
        self.leverage_spin.setValue(50)
        grid.addWidget(self.leverage_spin, 3, 1)

    def _build_sltp(self):
        self.sltp_box = QGroupBox("Stop Loss / Take Profit")
        grid = QGridLayout(self.sltp_box)

        self.auto_sl_tp_check = QCheckBox("Auto-place SL/TP on every order")
        grid.addWidget(self.auto_sl_tp_check, 0, 0, 1, 2)

        self.use_atr_check = QCheckBox("Use ATR for SL distance")
        grid.addWidget(self.use_atr_check, 1, 0, 1, 2)

        grid.addWidget(QLabel("ATR Multiplier (SL)"), 2, 0)
        self.atr_sl_spin = QDoubleSpinBox()
        self.atr_sl_spin.setRange(0.5, 5.0)
        self.atr_sl_spin.setDecimals(1)
        self.atr_sl_spin.setSingleStep(0.5)
        self.atr_sl_spin.setValue(1.5)
        grid.addWidget(self.atr_sl_spin, 2, 1)

        grid.addWidget(QLabel("TP Multiplier (vs SL)"), 3, 0)
        self.tp_mult_spin = QDoubleSpinBox()
        self.tp_mult_spin.setRange(0.5, 5.0)
        self.tp_mult_spin.setDecimals(1)
        self.tp_mult_spin.setSingleStep(0.5)
        self.tp_mult_spin.setValue(2.0)
        grid.addWidget(self.tp_mult_spin, 3, 1)

        grid.addWidget(QLabel("Fixed SL (pips, fallback)"), 4, 0)
        self.fixed_sl_spin = QSpinBox()
        self.fixed_sl_spin.setRange(5, 500)
        self.fixed_sl_spin.setValue(30)
        grid.addWidget(self.fixed_sl_spin, 4, 1)

    def _build_trailing(self):
        self.trailing_box = QGroupBox("Trailing Stop")
        grid = QGridLayout(self.trailing_box)

        self.trailing_check = QCheckBox("Enable trailing stop")
        grid.addWidget(self.trailing_check, 0, 0, 1, 2)

        grid.addWidget(QLabel("Trailing ATR Multiplier"), 1, 0)
        self.trail_atr_spin = QDoubleSpinBox()
        self.trail_atr_spin.setRange(0.5, 5.0)
        self.trail_atr_spin.setDecimals(1)
        self.trail_atr_spin.setSingleStep(0.5)
        self.trail_atr_spin.setValue(1.0)
        grid.addWidget(self.trail_atr_spin, 1, 1)

        grid.addWidget(QLabel("Fixed Trail (pips)"), 2, 0)
        self.trail_fixed_spin = QSpinBox()
        self.trail_fixed_spin.setRange(5, 500)
        self.trail_fixed_spin.setValue(20)
        grid.addWidget(self.trail_fixed_spin, 2, 1)

    def _build_trade_management(self):
        self.mgmt_box = QGroupBox("Trade Management")
        grid = QGridLayout(self.mgmt_box)

        self.partial_close_check = QCheckBox("Enable partial close (scale out)")
        grid.addWidget(self.partial_close_check, 0, 0, 1, 2)

        grid.addWidget(QLabel("Close % at TP1"), 1, 0)
        self.partial_pct_spin = QSpinBox()
        self.partial_pct_spin.setRange(10, 90)
        self.partial_pct_spin.setSuffix("%")
        self.partial_pct_spin.setValue(50)
        grid.addWidget(self.partial_pct_spin, 1, 1)

        self.breakeven_check = QCheckBox("Auto move SL to breakeven at TP1")
        grid.addWidget(self.breakeven_check, 2, 0, 1, 2)

    def _build_limits_filters(self):
        self.limits_box = QGroupBox("Limits & Filters")
        grid = QGridLayout(self.limits_box)

        self.daily_dd_check = QCheckBox("Enable daily drawdown limit")
        grid.addWidget(self.daily_dd_check, 0, 0, 1, 2)

        grid.addWidget(QLabel("Daily Drawdown (%)"), 1, 0)
        self.daily_dd_spin = QDoubleSpinBox()
        self.daily_dd_spin.setRange(0.5, 20.0)
        self.daily_dd_spin.setDecimals(1)
        self.daily_dd_spin.setSingleStep(0.5)
        self.daily_dd_spin.setValue(5.0)
        grid.addWidget(self.daily_dd_spin, 1, 1)

        self.total_dd_check = QCheckBox("Enable total drawdown limit")
        grid.addWidget(self.total_dd_check, 2, 0, 1, 2)

        grid.addWidget(QLabel("Total Drawdown (%)"), 3, 0)
        self.total_dd_spin = QDoubleSpinBox()
        self.total_dd_spin.setRange(1.0, 50.0)
        self.total_dd_spin.setDecimals(1)
        self.total_dd_spin.setSingleStep(0.5)
        self.total_dd_spin.setValue(10.0)
        grid.addWidget(self.total_dd_spin, 3, 1)

        grid.addWidget(QLabel("Cooldown (minutes)"), 4, 0)
        self.cooldown_spin = QSpinBox()
        self.cooldown_spin.setRange(0, 240)
        self.cooldown_spin.setValue(15)
        grid.addWidget(self.cooldown_spin, 4, 1)

        self.spread_filter_check = QCheckBox("Enable spread filter")
        grid.addWidget(self.spread_filter_check, 5, 0, 1, 2)

        grid.addWidget(QLabel("Max Spread (pips)"), 6, 0)
        self.max_spread_spin = QSpinBox()
        self.max_spread_spin.setRange(1, 50)
        self.max_spread_spin.setValue(5)
        grid.addWidget(self.max_spread_spin, 6, 1)

        self.correlation_check = QCheckBox("Enable correlation filter")
        grid.addWidget(self.correlation_check, 7, 0, 1, 2)

    def _build_news_filter(self):
        self.news_box = QGroupBox("News Filter")
        grid = QGridLayout(self.news_box)

        self.news_enabled_check = QCheckBox("Enable news filter")
        grid.addWidget(self.news_enabled_check, 0, 0, 1, 2)

        grid.addWidget(QLabel("Provider"), 1, 0)
        self.news_provider_combo = QComboBox()
        self.news_provider_combo.addItems(["jblanked"])
        grid.addWidget(self.news_provider_combo, 1, 1)

        grid.addWidget(QLabel("API Key"), 2, 0)
        self.news_api_key_edit = QLineEdit()
        self.news_api_key_edit.setEchoMode(QLineEdit.Password)
        self.news_api_key_edit.setPlaceholderText("Enter news API key")
        grid.addWidget(self.news_api_key_edit, 2, 1)

        self.show_api_key_check = QCheckBox("Show API key")
        self.show_api_key_check.toggled.connect(self._toggle_api_key_visibility)
        grid.addWidget(self.show_api_key_check, 3, 0, 1, 2)

        grid.addWidget(QLabel("Block before news (minutes)"), 4, 0)
        self.news_before_spin = QSpinBox()
        self.news_before_spin.setRange(0, 240)
        self.news_before_spin.setValue(30)
        grid.addWidget(self.news_before_spin, 4, 1)

        grid.addWidget(QLabel("Block after news (minutes)"), 5, 0)
        self.news_after_spin = QSpinBox()
        self.news_after_spin.setRange(0, 240)
        self.news_after_spin.setValue(30)
        grid.addWidget(self.news_after_spin, 5, 1)

        self.news_high_impact_check = QCheckBox("High impact only")
        grid.addWidget(self.news_high_impact_check, 6, 0, 1, 2)

        self.delete_news_key_btn = QPushButton("Delete Stored API Key")
        self.delete_news_key_btn.clicked.connect(self._delete_news_api_key)
        grid.addWidget(self.delete_news_key_btn, 7, 0, 1, 2)

    def _build_session_filter(self):
        self.session_box = QGroupBox("Session Filter")
        layout = QVBoxLayout(self.session_box)

        self.session_check = QCheckBox("Trade only during selected sessions")
        layout.addWidget(self.session_check)

        self.london_check = QCheckBox("London (08:00–17:00 UTC)")
        self.ny_check = QCheckBox("New York (13:00–22:00 UTC)")
        self.tokyo_check = QCheckBox("Tokyo (00:00–09:00 UTC)")
        self.sydney_check = QCheckBox("Sydney (22:00–07:00 UTC)")
        layout.addWidget(self.london_check)
        layout.addWidget(self.ny_check)
        layout.addWidget(self.tokyo_check)
        layout.addWidget(self.sydney_check)
        layout.addStretch()

    def _build_notifications(self):
        self.notify_box = QGroupBox("Notifications")
        layout = QVBoxLayout(self.notify_box)
        self.notifications_check = QCheckBox("Enable desktop notifications")
        layout.addWidget(self.notifications_check)
        layout.addStretch()

    def _toggle_api_key_visibility(self, checked: bool):
        self.news_api_key_edit.setEchoMode(QLineEdit.Normal if checked else QLineEdit.Password)

    def _delete_news_api_key(self):
        self.secure_settings.delete_news_api_key()
        self.news_api_key_edit.clear()

    def _load_values(self):
        risk = self.account.get("risk", {})
        news = self.secure_settings.load_news_settings()

        self.risk_percent_spin.setValue(risk.get("max_risk_percent", self.account.get("max_risk_percent", 1.0)))
        self.max_trades_spin.setValue(risk.get("max_open_trades", 3))
        self.min_units_spin.setValue(risk.get("min_units", 1000))
        self.leverage_spin.setValue(risk.get("max_leverage", 50))

        self.auto_sl_tp_check.setChecked(risk.get("auto_sl_tp", True))
        self.use_atr_check.setChecked(risk.get("use_atr_sl", True))
        self.atr_sl_spin.setValue(risk.get("atr_sl_multiplier", 1.5))
        self.tp_mult_spin.setValue(risk.get("tp_multiplier", 2.0))
        self.fixed_sl_spin.setValue(risk.get("fixed_sl_pips", 30))

        self.trailing_check.setChecked(risk.get("trailing_stop", False))
        self.trail_atr_spin.setValue(risk.get("trailing_atr_multiplier", 1.0))
        self.trail_fixed_spin.setValue(risk.get("trailing_fixed_pips", 20))

        self.partial_close_check.setChecked(risk.get("partial_close", False))
        self.partial_pct_spin.setValue(risk.get("partial_close_pct", 50))
        self.breakeven_check.setChecked(risk.get("auto_breakeven", False))

        self.daily_dd_check.setChecked(risk.get("daily_drawdown_enabled", True))
        self.daily_dd_spin.setValue(risk.get("daily_drawdown_limit", self.account.get("daily_drawdown_limit", 5.0)))
        self.total_dd_check.setChecked(risk.get("total_drawdown_enabled", True))
        self.total_dd_spin.setValue(risk.get("total_drawdown_limit", self.account.get("total_drawdown_limit", 10.0)))
        self.cooldown_spin.setValue(risk.get("cooldown_minutes", self.account.get("cooldown_minutes", 15)))

        self.spread_filter_check.setChecked(risk.get("spread_filter", False))
        self.max_spread_spin.setValue(risk.get("max_spread_pips", 5))
        self.correlation_check.setChecked(risk.get("correlation_filter", True))

        self.news_enabled_check.setChecked(news.get("enabled", False))
        self.news_provider_combo.setCurrentText(news.get("provider", "jblanked"))
        self.news_api_key_edit.setText(news.get("api_key", ""))
        self.news_before_spin.setValue(news.get("block_minutes_before", 30))
        self.news_after_spin.setValue(news.get("block_minutes_after", 30))
        self.news_high_impact_check.setChecked(news.get("high_impact_only", True))

        self.session_check.setChecked(risk.get("session_filter", False))
        sessions = risk.get("allowed_sessions", ["london", "ny"])
        self.london_check.setChecked("london" in sessions)
        self.ny_check.setChecked("ny" in sessions)
        self.tokyo_check.setChecked("tokyo" in sessions)
        self.sydney_check.setChecked("sydney" in sessions)

        self.notifications_check.setChecked(risk.get("notifications_enabled", True))

    def _save_and_close(self):
        risk = {
            "max_risk_percent": self.risk_percent_spin.value(),
            "max_open_trades": self.max_trades_spin.value(),
            "min_units": self.min_units_spin.value(),
            "max_leverage": self.leverage_spin.value(),
            "auto_sl_tp": self.auto_sl_tp_check.isChecked(),
            "use_atr_sl": self.use_atr_check.isChecked(),
            "atr_sl_multiplier": self.atr_sl_spin.value(),
            "tp_multiplier": self.tp_mult_spin.value(),
            "fixed_sl_pips": self.fixed_sl_spin.value(),
            "trailing_stop": self.trailing_check.isChecked(),
            "trailing_atr_multiplier": self.trail_atr_spin.value(),
            "trailing_fixed_pips": self.trail_fixed_spin.value(),
            "partial_close": self.partial_close_check.isChecked(),
            "partial_close_pct": self.partial_pct_spin.value(),
            "auto_breakeven": self.breakeven_check.isChecked(),
            "daily_drawdown_enabled": self.daily_dd_check.isChecked(),
            "daily_drawdown_limit": self.daily_dd_spin.value(),
            "total_drawdown_enabled": self.total_dd_check.isChecked(),
            "total_drawdown_limit": self.total_dd_spin.value(),
            "cooldown_minutes": self.cooldown_spin.value(),
            "spread_filter": self.spread_filter_check.isChecked(),
            "max_spread_pips": self.max_spread_spin.value(),
            "correlation_filter": self.correlation_check.isChecked(),
            "news_filter_enabled": self.news_enabled_check.isChecked(),
            "session_filter": self.session_check.isChecked(),
            "allowed_sessions": self._get_sessions(),
            "notifications_enabled": self.notifications_check.isChecked(),
        }

        self.secure_settings.save_news_settings({
            "enabled": self.news_enabled_check.isChecked(),
            "provider": self.news_provider_combo.currentText(),
            "api_key": self.news_api_key_edit.text().strip(),
            "block_minutes_before": self.news_before_spin.value(),
            "block_minutes_after": self.news_after_spin.value(),
            "high_impact_only": self.news_high_impact_check.isChecked(),
        })

        self.account["risk"] = risk
        self.account["max_risk_percent"] = risk["max_risk_percent"]
        self.account["daily_drawdown_limit"] = risk["daily_drawdown_limit"]
        self.account["total_drawdown_limit"] = risk["total_drawdown_limit"]
        self.account["cooldown_minutes"] = risk["cooldown_minutes"]
        self.accept()

    def _get_sessions(self) -> list:
        sessions = []
        if self.london_check.isChecked():
            sessions.append("london")
        if self.ny_check.isChecked():
            sessions.append("ny")
        if self.tokyo_check.isChecked():
            sessions.append("tokyo")
        if self.sydney_check.isChecked():
            sessions.append("sydney")
        return sessions

    def _reset_defaults(self):
        self.risk_percent_spin.setValue(1.0)
        self.max_trades_spin.setValue(3)
        self.min_units_spin.setValue(1000)
        self.leverage_spin.setValue(50)
        self.auto_sl_tp_check.setChecked(True)
        self.use_atr_check.setChecked(True)
        self.atr_sl_spin.setValue(1.5)
        self.tp_mult_spin.setValue(2.0)
        self.fixed_sl_spin.setValue(30)
        self.trailing_check.setChecked(False)
        self.trail_atr_spin.setValue(1.0)
        self.trail_fixed_spin.setValue(20)
        self.partial_close_check.setChecked(False)
        self.partial_pct_spin.setValue(50)
        self.breakeven_check.setChecked(False)
        self.daily_dd_check.setChecked(True)
        self.daily_dd_spin.setValue(5.0)
        self.total_dd_check.setChecked(True)
        self.total_dd_spin.setValue(10.0)
        self.cooldown_spin.setValue(15)
        self.spread_filter_check.setChecked(False)
        self.max_spread_spin.setValue(5)
        self.correlation_check.setChecked(True)
        self.news_enabled_check.setChecked(False)
        self.news_provider_combo.setCurrentText("jblanked")
        self.news_before_spin.setValue(30)
        self.news_after_spin.setValue(30)
        self.news_high_impact_check.setChecked(True)
        self.session_check.setChecked(False)
        self.london_check.setChecked(True)
        self.ny_check.setChecked(True)
        self.tokyo_check.setChecked(False)
        self.sydney_check.setChecked(False)
        self.notifications_check.setChecked(True)