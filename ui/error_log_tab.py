"""Error log tab for viewing recent bot errors."""
from typing import Optional

from PySide6.QtCore import QTimer, Qt
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QTableWidget, QTableWidgetItem, QHeaderView
)


class ErrorLogTab(QWidget):
    """Shows recent errors from the trading database."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.trading_engine = None
        self.account = None
        self._build_ui()

        self.timer = QTimer(self)
        self.timer.timeout.connect(self.refresh_errors)
        self.timer.start(5000)

    def _build_ui(self):
        layout = QVBoxLayout(self)

        top_row = QHBoxLayout()
        self.title_label = QLabel("Recent Errors")
        self.count_label = QLabel("0 entries")
        top_row.addWidget(self.title_label)
        top_row.addStretch()
        top_row.addWidget(self.count_label)

        self.refresh_btn = QPushButton("Refresh")
        self.refresh_btn.clicked.connect(self.refresh_errors)
        top_row.addWidget(self.refresh_btn)

        layout.addLayout(top_row)

        self.error_table = QTableWidget()
        self.error_table.setColumnCount(3)
        self.error_table.setHorizontalHeaderLabels(["ID", "Timestamp", "Message"])
        self.error_table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeToContents)
        self.error_table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeToContents)
        self.error_table.horizontalHeader().setSectionResizeMode(2, QHeaderView.Stretch)
        self.error_table.setEditTriggers(QTableWidget.NoEditTriggers)
        self.error_table.setSelectionBehavior(QTableWidget.SelectRows)
        self.error_table.setWordWrap(True)
        layout.addWidget(self.error_table)

        self.empty_label = QLabel("No errors logged.")
        self.empty_label.setAlignment(Qt.AlignCenter)
        layout.addWidget(self.empty_label)

    def set_context(self, trading_engine=None, account: Optional[dict] = None):
        self.trading_engine = trading_engine
        self.account = account
        self.refresh_errors()

    def refresh_errors(self):
        if not self.trading_engine:
            self.error_table.setRowCount(0)
            self.count_label.setText("0 entries")
            self.empty_label.setText("Trading engine not connected.")
            self.empty_label.show()
            return

        try:
            errors = self.trading_engine.db.get_recent_errors(limit=100)
        except Exception as e:
            self.error_table.setRowCount(0)
            self.count_label.setText("0 entries")
            self.empty_label.setText(f"Failed to load errors: {str(e)}")
            self.empty_label.show()
            return

        self.error_table.setRowCount(len(errors))
        self.count_label.setText(f"{len(errors)} entries")

        if not errors:
            self.empty_label.setText("No errors logged.")
            self.empty_label.show()
            return

        self.empty_label.hide()

        for row_idx, err in enumerate(errors):
            id_item = QTableWidgetItem(str(err.get("id", "")))
            ts_item = QTableWidgetItem(str(err.get("timestamp", "")))
            msg_item = QTableWidgetItem(str(err.get("message", "")))

            id_item.setFlags(id_item.flags() & ~Qt.ItemIsEditable)
            ts_item.setFlags(ts_item.flags() & ~Qt.ItemIsEditable)
            msg_item.setFlags(msg_item.flags() & ~Qt.ItemIsEditable)

            self.error_table.setItem(row_idx, 0, id_item)
            self.error_table.setItem(row_idx, 1, ts_item)
            self.error_table.setItem(row_idx, 2, msg_item)

        self.error_table.resizeRowsToContents()