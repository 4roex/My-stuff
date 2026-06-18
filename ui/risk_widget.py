"""Risk dashboard widget."""
from typing import Dict, Any, List

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QTableWidget,
    QTableWidgetItem, QGroupBox, QHeaderView
)
from PySide6.QtCore import Qt
from PySide6.QtGui import QFont


def fmt(inst: str) -> str:
    return inst.replace("_", "/") if inst else inst


class RiskWidget(QWidget):
    def __init__(self, account: Dict[str, Any]):
        super().__init__()
        self.account = account
        self._build_ui()

    def _build_ui(self):
        layout = QVBoxLayout(self)
        layout.setSpacing(10)

        margin_box = QGroupBox("Margin Summary")
        margin_layout = QHBoxLayout(margin_box)
        self.balance_label = QLabel("Balance: $0.00")
        self.margin_used_label = QLabel("Margin Used: $0.00")
        self.margin_avail_label = QLabel("Margin Available: $0.00")
        self.margin_closeout_label = QLabel("Closeout %: 0.0%")
        for lbl in [
            self.balance_label,
            self.margin_used_label,
            self.margin_avail_label,
            self.margin_closeout_label,
        ]:
            lbl.setFont(QFont("Segoe UI", 11, QFont.Bold))
            margin_layout.addWidget(lbl)
        layout.addWidget(margin_box)

        pos_box = QGroupBox("Position Risk")
        pos_layout = QVBoxLayout(pos_box)
        self.pos_table = QTableWidget()
        self.pos_table.setColumnCount(5)
        self.pos_table.setHorizontalHeaderLabels(
            ["Instrument", "Direction", "Units", "P&L", "% of Balance"]
        )
        self.pos_table.horizontalHeader().setStretchLastSection(True)
        self.pos_table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        pos_layout.addWidget(self.pos_table)
        layout.addWidget(pos_box)

        warn_box = QGroupBox("Risk Warnings")
        warn_layout = QVBoxLayout(warn_box)
        self.warnings_label = QLabel("No warnings")
        self.warnings_label.setWordWrap(True)
        self.warnings_label.setFont(QFont("Segoe UI", 10))
        warn_layout.addWidget(self.warnings_label)
        layout.addWidget(warn_box)

    def clear(self):
        self.balance_label.setText("Balance: $0.00")
        self.margin_used_label.setText("Margin Used: $0.00")
        self.margin_avail_label.setText("Margin Available: $0.00")
        self.margin_closeout_label.setText("Closeout %: 0.0%")
        self.margin_closeout_label.setStyleSheet("")
        self.pos_table.setRowCount(0)
        self.warnings_label.setText("No warnings")
        self.warnings_label.setStyleSheet("")

    def update_data(self, summary: Dict[str, Any], trades: List[Dict[str, Any]]):
        try:
            acc = summary.get("account", {}) if summary else {}
            balance = float(acc.get("balance", 0))
            margin_used = float(acc.get("marginUsed", 0))
            margin_avail = float(acc.get("marginAvailable", 0))
            margin_closeout = float(acc.get("marginCloseoutPercent", 0)) * 100

            self.balance_label.setText(f"Balance: ${balance:,.2f}")
            self.margin_used_label.setText(f"Margin Used: ${margin_used:,.2f}")
            self.margin_avail_label.setText(f"Margin Available: ${margin_avail:,.2f}")
            self.margin_closeout_label.setText(f"Closeout %: {margin_closeout:.1f}%")

            if margin_closeout > 50:
                self.margin_closeout_label.setStyleSheet("color: #e74c3c;")
            elif margin_closeout > 25:
                self.margin_closeout_label.setStyleSheet("color: #f39c12;")
            else:
                self.margin_closeout_label.setStyleSheet("color: #2ecc71;")

            self.pos_table.setRowCount(len(trades))
            warnings: List[str] = []

            for i, t in enumerate(trades):
                inst = str(t.get("instrument", ""))
                units = float(t.get("currentUnits", 0) or 0)
                pl = float(t.get("unrealizedPL", 0) or 0)
                direction = "LONG" if units > 0 else "SHORT"
                price = float(t.get("price", 1) or 1)
                pct = (abs(units) * price / balance * 100) if balance > 0 else 0

                self.pos_table.setItem(i, 0, QTableWidgetItem(fmt(inst)))
                self.pos_table.setItem(i, 1, QTableWidgetItem(direction))
                self.pos_table.setItem(i, 2, QTableWidgetItem(f"{abs(units):,.0f}"))

                pl_item = QTableWidgetItem(f"${pl:+.2f}")
                pl_item.setForeground(Qt.green if pl >= 0 else Qt.red)
                self.pos_table.setItem(i, 3, pl_item)

                self.pos_table.setItem(i, 4, QTableWidgetItem(f"{pct:.2f}%"))

            if not trades:
                warnings.append("No open positions.")
            else:
                if margin_closeout > 50:
                    warnings.append("CRITICAL: Margin closeout risk above 50%!")
                elif margin_closeout > 25:
                    warnings.append("WARNING: Margin closeout risk above 25%.")
                if len(trades) > 5:
                    warnings.append(f"High trade count: {len(trades)} open trades.")

                inst_counts: Dict[str, int] = {}
                for t in trades:
                    inst = str(t.get("instrument", ""))
                    inst_counts[inst] = inst_counts.get(inst, 0) + 1

                for inst, count in inst_counts.items():
                    if count > 1:
                        warnings.append(f"Multiple positions on {fmt(inst)} ({count} trades).")

            self.warnings_label.setText("\n".join(warnings) if warnings else "No warnings")
            if any("CRITICAL" in w or "WARNING" in w for w in warnings):
                self.warnings_label.setStyleSheet("color: #e74c3c;")
            else:
                self.warnings_label.setStyleSheet("color: #2ecc71;")

        except Exception as e:
            self.warnings_label.setText(f"Error loading risk data: {str(e)}")
            self.warnings_label.setStyleSheet("color: #e74c3c;")