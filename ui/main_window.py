"""Main application window."""
import json
from typing import Optional

from PySide6.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QTabWidget, QLabel, QPushButton
)
from PySide6.QtCore import QTimer
from PySide6.QtGui import QFont

from ui.account_widget import AccountWidget
from ui.settings_dialog import SettingsDialog
from ui.status_tab import StatusTab


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("FX LLM Trading Bot")
        self.setMinimumSize(1400, 900)

        with open("config/accounts.json", "r") as f:
            self.config = json.load(f)

        accounts = self.config.get("accounts", [])
        if isinstance(accounts, dict):
            accounts = [accounts]
        llm_config = self.config.get("llm", {})

        self.account_tabs: list[AccountWidget] = []

        central = QWidget()
        self.setCentralWidget(central)
        layout = QVBoxLayout(central)

        top_bar = QHBoxLayout()
        top_bar.addWidget(QLabel("FX LLM Trading Bot", font=QFont("Segoe UI", 16, QFont.Bold)))
        top_bar.addStretch()

        self.settings_btn = QPushButton("Settings")
        self.settings_btn.setStyleSheet("padding: 6px 16px;")
        self.settings_btn.clicked.connect(self._open_settings)
        top_bar.addWidget(self.settings_btn)

        self.refresh_btn = QPushButton("Refresh")
        self.refresh_btn.clicked.connect(self._refresh_all)
        top_bar.addWidget(self.refresh_btn)

        layout.addLayout(top_bar)

        self.tabs = QTabWidget()

        self.status_tab = StatusTab()
        self.tabs.addTab(self.status_tab, "Status")

        for account in accounts:
            if not account.get("active", True):
                continue
            name = account.get("name", account["account_id"])
            tab = AccountWidget(account, llm_config)
            self.account_tabs.append(tab)
            self.tabs.addTab(tab, name)

        self.tabs.currentChanged.connect(self._on_tab_changed)
        layout.addWidget(self.tabs)

        self.timer = QTimer(self)
        self.timer.timeout.connect(self._refresh_all)
        self.timer.start(5000)

        self._on_tab_changed(self.tabs.currentIndex())

    def _get_current_account_widget(self) -> Optional[AccountWidget]:
        widget = self.tabs.currentWidget()
        if isinstance(widget, AccountWidget):
            return widget

        for i in range(self.tabs.count()):
            w = self.tabs.widget(i)
            if isinstance(w, AccountWidget):
                return w
        return None

    def _on_tab_changed(self, index: int):
        current = self._get_current_account_widget()
        if current is None:
            self.status_tab.set_context(None, None)
            return

        engine = getattr(current, "trading_engine", None)
        account = getattr(current, "account", None)
        self.status_tab.set_context(engine, account)

    def _refresh_all(self):
        for i in range(self.tabs.count()):
            widget = self.tabs.widget(i)
            if isinstance(widget, AccountWidget):
                widget.refresh_data()

        self._on_tab_changed(self.tabs.currentIndex())

    def _open_settings(self):
        dialog = SettingsDialog(self.config, self)
        dialog.exec()
        self._on_tab_changed(self.tabs.currentIndex())