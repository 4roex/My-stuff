"""Performance widget showing account analytics and recent trades."""
from typing import Dict, Any, List, Optional

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QGroupBox,
    QTableWidget, QTableWidgetItem, QHeaderView, QSizePolicy
)
from PySide6.QtCore import Qt
from PySide6.QtGui import QFont, QColor, QPixmap


class PerformanceWidget(QWidget):
    def __init__(self, trading_engine=None, chart_gen=None):
        super().__init__()
        self.trading_engine = trading_engine
        self.chart_gen = chart_gen
        self._build_ui()

    def _build_ui(self):
        layout = QVBoxLayout(self)
        layout.setSpacing(10)

        stats_box = QGroupBox("Performance Summary")
        stats_layout = QHBoxLayout(stats_box)

        self.total_trades_label = QLabel("Total Trades: 0")
        self.win_rate_label = QLabel("Win Rate: 0%")
        self.total_pnl_label = QLabel("Total P&L: $0.00")
        self.avg_win_label = QLabel("Avg Win: $0.00")
        self.avg_loss_label = QLabel("Avg Loss: $0.00")
        self.profit_factor_label = QLabel("Profit Factor: 0.00")

        for lbl in [
            self.total_trades_label,
            self.win_rate_label,
            self.total_pnl_label,
            self.avg_win_label,
            self.avg_loss_label,
            self.profit_factor_label,
        ]:
            lbl.setFont(QFont("Segoe UI", 11, QFont.Bold))
            stats_layout.addWidget(lbl)

        layout.addWidget(stats_box)

        trades_box = QGroupBox("Recent Trades")
        trades_layout = QVBoxLayout(trades_box)

        self.trades_table = QTableWidget()
        self.trades_table.setColumnCount(9)
        self.trades_table.setHorizontalHeaderLabels([
            "Time", "Trade ID", "Instrument", "Dir", "Entry", "SL", "TP", "Status", "P&L"
        ])
        self.trades_table.horizontalHeader().setStretchLastSection(True)
        self.trades_table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        trades_layout.addWidget(self.trades_table)

        layout.addWidget(trades_box)

        chart_box = QGroupBox("Daily P&L")
        chart_layout = QVBoxLayout(chart_box)

        self.daily_chart_label = QLabel("No chart data yet")
        self.daily_chart_label.setAlignment(Qt.AlignCenter)
        self.daily_chart_label.setMinimumHeight(250)
        self.daily_chart_label.setStyleSheet("background-color: #1a1a2e; border-radius: 8px;")
        self.daily_chart_label.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        chart_layout.addWidget(self.daily_chart_label)

        layout.addWidget(chart_box)

    def set_trading_engine(self, trading_engine):
        self.trading_engine = trading_engine
        self.refresh()

    def refresh(self):
        if not self.trading_engine:
            self._clear_ui()
            self.daily_chart_label.setText("No trading engine connected")
            return

        try:
            stats = self.trading_engine.db.get_performance_stats(days=30)

            self.total_trades_label.setText(f"Total Trades: {stats.get('total_trades', 0)}")
            self.win_rate_label.setText(f"Win Rate: {stats.get('win_rate', 0):.1f}%")
            self.total_pnl_label.setText(f"Total P&L: ${stats.get('total_pnl', 0):+.2f}")
            self.avg_win_label.setText(f"Avg Win: ${stats.get('avg_win', 0):+.2f}")
            self.avg_loss_label.setText(f"Avg Loss: ${stats.get('avg_loss', 0):+.2f}")
            self.profit_factor_label.setText(f"Profit Factor: {stats.get('profit_factor', 0):.2f}")

            total_pnl = float(stats.get("total_pnl", 0) or 0)
            self.total_pnl_label.setStyleSheet(
                "color: #2ecc71;" if total_pnl >= 0 else "color: #e74c3c;"
            )

            trades = self.trading_engine.db.get_trade_history(limit=50)
            self._update_trades_table(trades)

            self._update_daily_chart(stats)

        except Exception as e:
            self.daily_chart_label.setText(f"Performance error: {str(e)}")

    def _update_trades_table(self, trades: List[Dict[str, Any]]):
        self.trades_table.setRowCount(len(trades))

        for i, t in enumerate(trades):
            pnl = float(t.get("realized_pl", 0) or 0)

            self.trades_table.setItem(i, 0, QTableWidgetItem(str(t.get("timestamp", ""))))
            self.trades_table.setItem(i, 1, QTableWidgetItem(str(t.get("trade_id", ""))))
            self.trades_table.setItem(i, 2, QTableWidgetItem(str(t.get("instrument", ""))))
            self.trades_table.setItem(i, 3, QTableWidgetItem(str(t.get("direction", ""))))
            self.trades_table.setItem(i, 4, QTableWidgetItem(str(t.get("entry_price", ""))))
            self.trades_table.setItem(i, 5, QTableWidgetItem(str(t.get("stop_loss", ""))))
            self.trades_table.setItem(i, 6, QTableWidgetItem(str(t.get("take_profit", ""))))
            self.trades_table.setItem(i, 7, QTableWidgetItem(str(t.get("status", ""))))

            pnl_item = QTableWidgetItem(f"${pnl:+.2f}")
            pnl_item.setForeground(QColor("#2ecc71") if pnl >= 0 else QColor("#e74c3c"))
            self.trades_table.setItem(i, 8, pnl_item)

    def _update_daily_chart(self, stats: Dict[str, Any]):
        daily_breakdown = stats.get("daily_breakdown", [])

        if not daily_breakdown:
            self.daily_chart_label.setText("No daily P&L data yet")
            self.daily_chart_label.setPixmap(QPixmap())
            return

        if not self.chart_gen or not hasattr(self.chart_gen, "create_daily_pnl_chart"):
            latest = daily_breakdown[0].get("pnl", 0)
            self.daily_chart_label.setText(f"Latest Daily P&L: ${float(latest):+.2f}")
            self.daily_chart_label.setPixmap(QPixmap())
            return

        try:
            chart_path = self.chart_gen.create_daily_pnl_chart(daily_breakdown, width=1200, height=300)
            pixmap = QPixmap(chart_path)
            if pixmap and not pixmap.isNull():
                scaled = pixmap.scaled(
                    self.daily_chart_label.size(),
                    Qt.KeepAspectRatio,
                    Qt.SmoothTransformation
                )
                self.daily_chart_label.setPixmap(scaled)
                self.daily_chart_label.setText("")
            else:
                self.daily_chart_label.setText("Failed to render daily P&L chart")
        except Exception:
            latest = daily_breakdown[0].get("pnl", 0)
            self.daily_chart_label.setText(f"Latest Daily P&L: ${float(latest):+.2f}")

    def _clear_ui(self):
        self.total_trades_label.setText("Total Trades: 0")
        self.win_rate_label.setText("Win Rate: 0%")
        self.total_pnl_label.setText("Total P&L: $0.00")
        self.avg_win_label.setText("Avg Win: $0.00")
        self.avg_loss_label.setText("Avg Loss: $0.00")
        self.profit_factor_label.setText("Profit Factor: 0.00")
        self.trades_table.setRowCount(0)

    def resizeEvent(self, event):
        super().resizeEvent(event)
        pixmap = self.daily_chart_label.pixmap()
        if pixmap and not pixmap.isNull():
            scaled = pixmap.scaled(
                self.daily_chart_label.size(),
                Qt.KeepAspectRatio,
                Qt.SmoothTransformation
            )
            self.daily_chart_label.setPixmap(scaled)