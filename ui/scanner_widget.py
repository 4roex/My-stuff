"""Multi-pair market scanner widget."""
from typing import Dict, Any, List, Optional, Callable

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QTableWidget, QTableWidgetItem, QHeaderView
)
from PySide6.QtCore import Qt
from PySide6.QtGui import QFont


def fmt(inst: str) -> str:
    return inst.replace("_", "/") if inst else inst


class ScannerWidget(QWidget):
    def __init__(
        self,
        account: Dict[str, Any],
        scan_callback: Optional[Callable[[], None]] = None,
    ):
        super().__init__()
        self.account = account
        self.scan_callback = scan_callback
        self._build_ui()

    def _build_ui(self):
        layout = QVBoxLayout(self)
        layout.setSpacing(10)

        header = QHBoxLayout()
        self.scan_label = QLabel("Market Scanner")
        self.scan_label.setFont(QFont("Segoe UI", 14, QFont.Bold))
        header.addWidget(self.scan_label)
        header.addStretch()

        self.scan_btn = QPushButton("Scan Now")
        self.scan_btn.setStyleSheet("background-color: #3498db; color: white; padding: 6px 16px;")
        self.scan_btn.clicked.connect(self.request_scan)
        header.addWidget(self.scan_btn)

        layout.addLayout(header)

        self.scanner_table = QTableWidget()
        self.scanner_table.setColumnCount(8)
        self.scanner_table.setHorizontalHeaderLabels([
            "Instrument", "Price", "Change", "Trend", "Signal", "Strength", "RSI", "EMA Cross"
        ])
        self.scanner_table.horizontalHeader().setStretchLastSection(False)
        self.scanner_table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.scanner_table.setSelectionBehavior(QTableWidget.SelectRows)
        self.scanner_table.setEditTriggers(QTableWidget.NoEditTriggers)
        layout.addWidget(self.scanner_table)

        self.status_label = QLabel("Click Scan Now to load signals")
        layout.addWidget(self.status_label)

    def request_scan(self):
        active = self.account.get("instruments", ["EUR_USD", "GBP_USD", "USD_JPY"])
        count = len(active) if active else 0
        self.status_label.setText(f"Scanning {count} instruments...")
        if callable(self.scan_callback):
            self.scan_callback()

    def clear(self):
        self.scanner_table.setRowCount(0)
        self.status_label.setText("Click Scan Now to load signals")

    def update_data(self, scan_rows: List[Dict[str, Any]], status_text: str = ""):
        scan_rows = scan_rows or []
        self.scanner_table.setRowCount(len(scan_rows))

        for i, row in enumerate(scan_rows):
            inst = fmt(str(row.get("instrument", "")))
            close_price = row.get("price", "N/A")
            change = float(row.get("change", 0) or 0)
            trend = str(row.get("trend", "N/A"))
            signal = str(row.get("signal", "HOLD"))
            strength = int(row.get("strength", 0) or 0)
            rsi = row.get("rsi", "N/A")
            ema_cross = str(row.get("ema_cross", "N/A"))
            error = str(row.get("error", ""))

            self.scanner_table.setItem(i, 0, QTableWidgetItem(inst))

            if error:
                self.scanner_table.setItem(i, 1, QTableWidgetItem(f"Error: {error[:24]}"))
                self.scanner_table.setItem(i, 2, QTableWidgetItem("-"))
                self.scanner_table.setItem(i, 3, QTableWidgetItem("-"))
                self.scanner_table.setItem(i, 4, QTableWidgetItem("ERROR"))
                self.scanner_table.setItem(i, 5, QTableWidgetItem("0%"))
                self.scanner_table.setItem(i, 6, QTableWidgetItem("-"))
                self.scanner_table.setItem(i, 7, QTableWidgetItem("-"))
                continue

            self.scanner_table.setItem(i, 1, QTableWidgetItem(str(close_price)))

            chg_item = QTableWidgetItem(f"{change:+.2f}%")
            chg_item.setForeground(Qt.green if change >= 0 else Qt.red)
            self.scanner_table.setItem(i, 2, chg_item)

            self.scanner_table.setItem(i, 3, QTableWidgetItem(trend))

            sig_item = QTableWidgetItem(signal)
            if signal == "BUY":
                sig_item.setBackground(Qt.green)
                sig_item.setForeground(Qt.black)
            elif signal == "SELL":
                sig_item.setBackground(Qt.red)
                sig_item.setForeground(Qt.white)
            self.scanner_table.setItem(i, 4, sig_item)

            self.scanner_table.setItem(i, 5, QTableWidgetItem(f"{strength}%"))
            self.scanner_table.setItem(i, 6, QTableWidgetItem(str(rsi) if rsi != "N/A" else "N/A"))
            self.scanner_table.setItem(i, 7, QTableWidgetItem(ema_cross))

        self.status_label.setText(
            status_text or f"Last scan: {len(scan_rows)} instruments complete"
        )