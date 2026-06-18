"""Status tab for bot, broker sync, and filter state."""
from typing import Optional

from PySide6.QtCore import QTimer
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QGridLayout, QLabel, QPushButton,
    QGroupBox, QMessageBox
)


class StatusTab(QWidget):
    """Live status panel for trading engine and broker sync state."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.trading_engine = None
        self.account = None
        self._build_ui()

        self.timer = QTimer(self)
        self.timer.timeout.connect(self.refresh_status)
        self.timer.start(5000)

    def _build_ui(self):
        layout = QVBoxLayout(self)

        overview_box = QGroupBox("Bot Overview")
        overview_grid = QGridLayout(overview_box)

        overview_grid.addWidget(QLabel("Bot State"), 0, 0)
        self.bot_state_label = QLabel("Not connected")
        overview_grid.addWidget(self.bot_state_label, 0, 1)

        overview_grid.addWidget(QLabel("Account ID"), 1, 0)
        self.account_id_label = QLabel("-")
        overview_grid.addWidget(self.account_id_label, 1, 1)

        overview_grid.addWidget(QLabel("Open Trades"), 2, 0)
        self.open_trades_label = QLabel("-")
        overview_grid.addWidget(self.open_trades_label, 2, 1)

        overview_grid.addWidget(QLabel("Last Transaction ID"), 3, 0)
        self.last_tx_label = QLabel("-")
        overview_grid.addWidget(self.last_tx_label, 3, 1)

        layout.addWidget(overview_box)

        filters_box = QGroupBox("Active Filters")
        filters_grid = QGridLayout(filters_box)

        filters_grid.addWidget(QLabel("News Filter"), 0, 0)
        self.news_filter_label = QLabel("-")
        filters_grid.addWidget(self.news_filter_label, 0, 1)

        filters_grid.addWidget(QLabel("Correlation Filter"), 1, 0)
        self.correlation_filter_label = QLabel("-")
        filters_grid.addWidget(self.correlation_filter_label, 1, 1)

        filters_grid.addWidget(QLabel("Spread Filter"), 2, 0)
        self.spread_filter_label = QLabel("-")
        filters_grid.addWidget(self.spread_filter_label, 2, 1)

        filters_grid.addWidget(QLabel("Session Filter"), 3, 0)
        self.session_filter_label = QLabel("-")
        filters_grid.addWidget(self.session_filter_label, 3, 1)

        layout.addWidget(filters_box)

        health_box = QGroupBox("Health")
        health_grid = QGridLayout(health_box)

        health_grid.addWidget(QLabel("Last Error"), 0, 0)
        self.last_error_label = QLabel("None")
        self.last_error_label.setWordWrap(True)
        health_grid.addWidget(self.last_error_label, 0, 1)

        layout.addWidget(health_box)

        self.sync_button = QPushButton("Sync Broker History")
        self.sync_button.clicked.connect(self.sync_broker_history)
        layout.addWidget(self.sync_button)

        layout.addStretch()

    def set_context(self, trading_engine=None, account: Optional[dict] = None):
        self.trading_engine = trading_engine
        self.account = account
        self.refresh_status()

    def refresh_status(self):
        if self.account:
            self.account_id_label.setText(str(self.account.get("account_id", "-")))
        else:
            self.account_id_label.setText("-")

        if not self.trading_engine:
            self.bot_state_label.setText("Not connected")
            self.open_trades_label.setText("-")
            self.last_tx_label.setText("-")
            self.news_filter_label.setText("-")
            self.correlation_filter_label.setText("-")
            self.spread_filter_label.setText("-")
            self.session_filter_label.setText("-")
            self.last_error_label.setText("None")
            return

        risk = getattr(self.trading_engine, "risk", {}) or {}
        self.bot_state_label.setText(
            "Running" if getattr(self.trading_engine, "running", False) else "Stopped"
        )
        self.last_tx_label.setText(
            getattr(self.trading_engine, "_last_transaction_id", "") or "-"
        )

        self.news_filter_label.setText(
            "Enabled" if risk.get("news_filter_enabled", False) else "Disabled"
        )
        self.correlation_filter_label.setText(
            "Enabled" if risk.get("correlation_filter", True) else "Disabled"
        )
        self.spread_filter_label.setText(
            "Enabled" if risk.get("spread_filter", False) else "Disabled"
        )
        self.session_filter_label.setText(
            "Enabled" if risk.get("session_filter", False) else "Disabled"
        )

        try:
            open_trades = self.trading_engine.db.get_open_trades()
            self.open_trades_label.setText(str(len(open_trades)))
        except Exception:
            self.open_trades_label.setText("?")

        try:
            errors = self.trading_engine.db.get_recent_errors(limit=1)
            if errors:
                self.last_error_label.setText(errors[0].get("message", "None"))
            else:
                self.last_error_label.setText("None")
        except Exception:
            self.last_error_label.setText("Unavailable")

    def sync_broker_history(self):
        if not self.trading_engine:
            QMessageBox.warning(self, "Sync Broker History", "Trading engine is not initialized.")
            return

        ok, message = self.trading_engine.sync_broker_history_now()
        if ok:
            QMessageBox.information(self, "Sync Broker History", message)
        else:
            QMessageBox.warning(self, "Sync Broker History", message)

        self.refresh_status()