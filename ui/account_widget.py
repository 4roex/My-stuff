"""Account tab widget with threaded refresh and tab appearance hooks."""
from __future__ import annotations

from typing import Dict, Any, List, Optional

from PySide6.QtCore import Qt, QObject, QThread, Signal, Slot
from PySide6.QtGui import QColor, QBrush, QFont
from PySide6.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QTabWidget,
    QLabel,
    QPushButton,
    QComboBox,
    QTableWidget,
    QTableWidgetItem,
    QGroupBox,
    QHeaderView,
    QSizePolicy,
    QDialog,
)

from core.oanda_client import OandaClient, OandaConfig
from core.data_engine import DataEngine
from core.trading_engine import TradingEngine
from core.secure_settings import SecureSettings
from ui.scanner_widget import ScannerWidget
from ui.risk_widget import RiskWidget
from ui.performance_widget import PerformanceWidget
from ui.risk_settings_dialog import RiskSettingsDialog
from ui.interactive_chart_widget import InteractiveChartWidget

TIMEFRAMES = ["M1", "M5", "M15", "M30", "H1", "H4", "D1", "W1"]

DARK_TAB_COLORS = {
    "Slate": "#1f2937",
    "Charcoal": "#23272f",
    "Midnight": "#1e293b",
    "Deep Blue": "#1e3a5f",
    "Forest": "#1f4d3a",
    "Plum": "#4b2e4f",
    "Burgundy": "#5a2632",
}


def fmt(inst: str) -> str:
    return inst.replace("_", "/") if inst else inst


def make_color_brush(hex_color: str) -> QBrush:
    return QBrush(QColor(hex_color))


class AccountRefreshWorker(QObject):
    finished = Signal(dict)
    error = Signal(str)

    def __init__(
        self,
        access_token: str,
        account_id: str,
        environment: str,
        data_dir: str,
        instrument: str,
        timeframe: str,
        db,
    ):
        super().__init__()
        self.access_token = access_token
        self.account_id = account_id
        self.environment = environment
        self.data_dir = data_dir
        self.instrument = instrument
        self.timeframe = timeframe
        self.db = db

    @Slot()
    def run(self):
        try:
            oanda_cfg = OandaConfig(
                access_token=self.access_token,
                account_id=self.account_id,
                environment=self.environment,
            )
            client = OandaClient(oanda_cfg)
            data_engine = DataEngine(client, data_dir=self.data_dir)

            summary = client.get_account_summary()
            trades = client.get_open_trades()
            stats = self.db.get_performance_stats(days=30)
            history = self.db.get_trade_history(limit=20)
            performance_trades = self.db.get_trade_history(limit=50)

            df = data_engine.get_data_with_indicators(
                self.instrument,
                granularity=self.timeframe,
                count=150,
            )
            snapshot = data_engine.get_latest_market_snapshot(
                self.instrument,
                granularity=self.timeframe,
            )

            payload = {
                "summary": summary,
                "trades": trades,
                "stats": stats,
                "history": history,
                "performance_trades": performance_trades,
                "df": df,
                "snapshot": snapshot,
                "instrument": self.instrument,
                "timeframe": self.timeframe,
            }
            self.finished.emit(payload)
        except Exception as e:
            self.error.emit(str(e))


class AccountWidget(QWidget):
    appearance_requested = Signal(object)
    account_updated = Signal(dict)

    def __init__(self, account: Dict[str, Any], llm_config: Dict[str, Any]):
        super().__init__()
        self.account = account
        self.llm_config = llm_config
        self.secure_settings = SecureSettings()

        self.account.setdefault(
            "tab_name",
            self.account.get("name", self.account.get("account_id", "Account")),
        )
        self.account.setdefault("tab_color", "Slate")

        self._chart_cache_key = None
        self._chart_last_df_signature = None
        self._refresh_thread: Optional[QThread] = None
        self._refresh_worker: Optional[AccountRefreshWorker] = None
        self._refresh_in_progress = False
        self._pending_refresh = False

        self.client = self._create_client()
        self.data_engine = DataEngine(self.client, data_dir=f"data/{account['account_id']}")
        self.trading_engine = TradingEngine(account, llm_config)

        self._build_ui()
        self._apply_tab_theme_preview()
        self.refresh_data()

    def _resolve_access_token(self) -> str:
        direct = str(self.account.get("access_token", "") or "").strip()
        if direct:
            return direct

        secret_name = str(self.account.get("access_token_secret", "") or "").strip()
        if secret_name:
            token = self.secure_settings.get_secret(secret_name)
            if token:
                return token

        account_id = str(self.account.get("account_id", "") or "").strip()
        if account_id:
            token = self.secure_settings.get_account_token(account_id)
            if token:
                return token

        raise ValueError(
            f"No OANDA access token configured for account {self.account.get('account_id', 'unknown')}"
        )

    def _create_client(self) -> OandaClient:
        oanda_cfg = OandaConfig(
            access_token=self._resolve_access_token(),
            account_id=self.account["account_id"],
            environment=self.account.get("environment", "practice"),
        )
        return OandaClient(oanda_cfg)

    def _build_ui(self):
        main_layout = QVBoxLayout(self)
        main_layout.setSpacing(10)

        summary_box = QGroupBox("Account Summary")
        summary_layout = QHBoxLayout(summary_box)

        self.balance_label = QLabel("Balance: $0.00")
        self.pnl_label = QLabel("P&L: $0.00")
        self.trades_label = QLabel("Open Trades: 0")
        self.winrate_label = QLabel("Win Rate: 0%")

        for lbl in [self.balance_label, self.pnl_label, self.trades_label, self.winrate_label]:
            lbl.setFont(QFont("Segoe UI", 12, QFont.Bold))
            summary_layout.addWidget(lbl)

        main_layout.addWidget(summary_box)

        controls_layout = QHBoxLayout()

        self.instrument_combo = QComboBox()
        active = self.account.get("instruments", ["EUR_USD", "GBP_USD", "USD_JPY"])
        if not active:
            active = ["EUR_USD", "GBP_USD", "USD_JPY"]
        for inst in active:
            self.instrument_combo.addItem(fmt(inst), inst)
        self.instrument_combo.setMaxVisibleItems(20)
        self.instrument_combo.currentIndexChanged.connect(self.refresh_data)

        controls_layout.addWidget(QLabel("Instrument:"))
        controls_layout.addWidget(self.instrument_combo)

        self.timeframe_combo = QComboBox()
        self.timeframe_combo.addItems(TIMEFRAMES)
        self.timeframe_combo.setCurrentText("M5")
        self.timeframe_combo.currentIndexChanged.connect(self.refresh_data)

        controls_layout.addWidget(QLabel("Timeframe:"))
        controls_layout.addWidget(self.timeframe_combo)

        self.start_btn = QPushButton("Start Bot")
        self.start_btn.setStyleSheet("background-color: #2ecc71; color: white; padding: 6px 16px;")
        self.start_btn.clicked.connect(self._start_bot)
        controls_layout.addWidget(self.start_btn)

        self.stop_btn = QPushButton("Stop Bot")
        self.stop_btn.setStyleSheet("background-color: #e74c3c; color: white; padding: 6px 16px;")
        self.stop_btn.clicked.connect(self._stop_bot)
        controls_layout.addWidget(self.stop_btn)

        self.status_label = QLabel("Engine: Stopped")
        self.status_label.setStyleSheet("color: #f39c12;")
        controls_layout.addWidget(self.status_label)

        self.decision_label = QLabel("Last decision: None")
        controls_layout.addStretch()
        controls_layout.addWidget(self.decision_label)

        self.appearance_btn = QPushButton("Account Appearance")
        self.appearance_btn.setStyleSheet("padding: 6px 16px;")
        self.appearance_btn.clicked.connect(self._request_appearance_edit)
        controls_layout.addWidget(self.appearance_btn)

        self.risk_btn = QPushButton("Risk Settings")
        self.risk_btn.setStyleSheet("padding: 6px 16px;")
        self.risk_btn.clicked.connect(self._open_risk_settings)
        controls_layout.addWidget(self.risk_btn)

        main_layout.addLayout(controls_layout)

        self.theme_preview = QLabel("")
        self.theme_preview.setMinimumHeight(12)
        self.theme_preview.setMaximumHeight(12)
        self.theme_preview.setStyleSheet("border-radius: 6px;")
        main_layout.addWidget(self.theme_preview)

        self.view_tabs = QTabWidget()

        trading_tab = QWidget()
        trading_layout = QVBoxLayout(trading_tab)

        self.chart_widget = InteractiveChartWidget()
        self.chart_widget.setMinimumHeight(420)
        self.chart_widget.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        trading_layout.addWidget(self.chart_widget, stretch=1)

        bottom_layout = QHBoxLayout()

        trades_box = QGroupBox("Open Trades")
        trades_layout = QVBoxLayout(trades_box)

        self.trades_table = QTableWidget()
        self.trades_table.setColumnCount(6)
        self.trades_table.setHorizontalHeaderLabels(["ID", "Instrument", "Units", "Entry", "P&L", "Action"])
        self.trades_table.horizontalHeader().setStretchLastSection(True)
        self.trades_table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        trades_layout.addWidget(self.trades_table)

        bottom_layout.addWidget(trades_box, stretch=2)

        snapshot_box = QGroupBox("Market Snapshot")
        snapshot_layout = QVBoxLayout(snapshot_box)

        self.snapshot_label = QLabel("Loading...")
        self.snapshot_label.setFont(QFont("Consolas", 10))
        self.snapshot_label.setWordWrap(True)
        snapshot_layout.addWidget(self.snapshot_label)

        bottom_layout.addWidget(snapshot_box, stretch=1)

        log_box = QGroupBox("Recent Decisions")
        log_layout = QVBoxLayout(log_box)

        self.decision_log = QTableWidget()
        self.decision_log.setColumnCount(4)
        self.decision_log.setHorizontalHeaderLabels(["Time", "Decision", "Confidence", "Reason"])
        self.decision_log.horizontalHeader().setStretchLastSection(True)
        self.decision_log.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.decision_log.setMaximumHeight(180)
        log_layout.addWidget(self.decision_log)

        bottom_layout.addWidget(log_box, stretch=2)

        trading_layout.addLayout(bottom_layout)
        self.view_tabs.addTab(trading_tab, "Trading")

        self.scanner_widget = ScannerWidget(self.account, scan_callback=self.refresh_data)
        self.view_tabs.addTab(self.scanner_widget, "Scanner")

        self.risk_widget = RiskWidget(self.account)
        self.view_tabs.addTab(self.risk_widget, "Risk")

        self.performance_widget = PerformanceWidget()
        self.view_tabs.addTab(self.performance_widget, "Performance")

        main_layout.addWidget(self.view_tabs, stretch=1)

    def get_tab_name(self) -> str:
        return self.account.get("tab_name") or self.account.get("name") or self.account.get("account_id", "Account")

    def get_tab_color_name(self) -> str:
        color_name = self.account.get("tab_color", "Slate")
        return color_name if color_name in DARK_TAB_COLORS else "Slate"

    def get_tab_color_hex(self) -> str:
        return DARK_TAB_COLORS[self.get_tab_color_name()]

    def _apply_tab_theme_preview(self):
        self.theme_preview.setStyleSheet(
            f"background-color: {self.get_tab_color_hex()}; border-radius: 6px;"
        )

    def apply_account_identity(self, tab_name: str, color_name: str):
        self.account["tab_name"] = tab_name.strip() if tab_name.strip() else self.account.get("account_id", "Account")
        self.account["name"] = self.account["tab_name"]
        self.account["tab_color"] = color_name if color_name in DARK_TAB_COLORS else "Slate"
        self._apply_tab_theme_preview()
        self.account_updated.emit(self.account)

    def _request_appearance_edit(self):
        self.appearance_requested.emit(self)

    def refresh_data(self):
        if self._refresh_in_progress:
            self._pending_refresh = True
            return

        instrument = self.instrument_combo.currentData()
        timeframe = self.timeframe_combo.currentText()

        self._refresh_in_progress = True
        self._pending_refresh = False
        self.status_label.setText("Refreshing...")
        self.status_label.setStyleSheet("color: #3498db;")

        self._refresh_thread = QThread()
        self._refresh_worker = AccountRefreshWorker(
            access_token=self._resolve_access_token(),
            account_id=self.account["account_id"],
            environment=self.account.get("environment", "practice"),
            data_dir=f"data/{self.account['account_id']}",
            instrument=instrument,
            timeframe=timeframe,
            db=self.trading_engine.db,
        )
        self._refresh_worker.moveToThread(self._refresh_thread)

        self._refresh_thread.started.connect(self._refresh_worker.run)
        self._refresh_worker.finished.connect(self._on_refresh_success)
        self._refresh_worker.error.connect(self._on_refresh_error)
        self._refresh_worker.finished.connect(self._refresh_thread.quit)
        self._refresh_worker.error.connect(self._refresh_thread.quit)
        self._refresh_thread.finished.connect(self._cleanup_refresh_thread)

        self._refresh_thread.start()

    @Slot(dict)
    def _on_refresh_success(self, payload: Dict[str, Any]):
        try:
            summary = payload.get("summary", {})
            acc = summary.get("account", {})
            balance = float(acc.get("balance", 0) or 0)
            unrealized_pl = float(acc.get("unrealizedPL", 0) or 0)
            open_count = int(acc.get("openTradeCount", 0) or 0)

            self.balance_label.setText(f"Balance: ${balance:,.2f}")
            self.pnl_label.setText(f"P&L: ${unrealized_pl:+.2f}")
            self.pnl_label.setStyleSheet("color: #2ecc71;" if unrealized_pl >= 0 else "color: #e74c3c;")
            self.trades_label.setText(f"Open Trades: {open_count}")

            stats = payload.get("stats", {})
            win_rate = stats.get("win_rate", stats.get("winrate", 0))
            self.winrate_label.setText(f"Win Rate: {float(win_rate):.1f}%")

            running = self.trading_engine.running
            self.status_label.setText("Engine: Running" if running else "Engine: Stopped")
            self.status_label.setStyleSheet("color: #2ecc71;" if running else "color: #f39c12;")

            trades = payload.get("trades", [])
            self._update_trades_table(trades)

            df = payload.get("df")
            instrument = payload.get("instrument", self.instrument_combo.currentData())
            timeframe = payload.get("timeframe", self.timeframe_combo.currentText())
            self._update_chart(df, instrument, timeframe)

            snapshot = payload.get("snapshot")
            self._update_snapshot(snapshot)

            history = payload.get("history", [])
            self._update_decision_log_from_history(history)

            self.risk_widget.update_data(summary, trades)
            self.performance_widget.update_data(stats, payload.get("performance_trades", []))

        finally:
            self._refresh_in_progress = False
            if self._pending_refresh:
                self.refresh_data()

    @Slot(str)
    def _on_refresh_error(self, message: str):
        self._refresh_in_progress = False
        self.status_label.setText(f"Error: {message}")
        self.status_label.setStyleSheet("color: #e74c3c;")
        if self._pending_refresh:
            self.refresh_data()

    @Slot()
    def _cleanup_refresh_thread(self):
        if self._refresh_worker is not None:
            self._refresh_worker.deleteLater()
            self._refresh_worker = None
        if self._refresh_thread is not None:
            self._refresh_thread.deleteLater()
            self._refresh_thread = None

    def _update_chart(self, df, instrument: str, timeframe: str):
        if df is None or df.empty:
            self.chart_widget.clear()
            self._chart_cache_key = None
            self._chart_last_df_signature = None
            return

        cache_key = (instrument, timeframe)

        last_close = None
        last_time = None
        row_count = len(df)

        try:
            if "close" in df.columns:
                last_close = float(df["close"].iloc[-1])
        except Exception:
            last_close = None

        try:
            if hasattr(df.index, "__len__") and len(df.index) > 0:
                last_time = str(df.index[-1])
        except Exception:
            last_time = None

        df_signature = (row_count, last_close, last_time)

        if cache_key == self._chart_cache_key and df_signature == self._chart_last_df_signature:
            return

        self.chart_widget.set_data(df, fmt(instrument), timeframe)
        self._chart_cache_key = cache_key
        self._chart_last_df_signature = df_signature

    def _update_trades_table(self, trades: List[dict]):
        self.trades_table.setRowCount(len(trades))
        for i, t in enumerate(trades):
            pl = float(t.get("unrealizedPL", 0) or 0)
            self.trades_table.setItem(i, 0, QTableWidgetItem(str(t.get("id", ""))))
            self.trades_table.setItem(i, 1, QTableWidgetItem(fmt(str(t.get("instrument", "")))))
            self.trades_table.setItem(i, 2, QTableWidgetItem(str(t.get("currentUnits", ""))))
            self.trades_table.setItem(i, 3, QTableWidgetItem(str(t.get("price", ""))))

            pl_item = QTableWidgetItem(f"${pl:+.2f}")
            pl_item.setForeground(make_color_brush("#2ecc71" if pl >= 0 else "#e74c3c"))
            self.trades_table.setItem(i, 4, pl_item)

            close_btn = QPushButton("Close")
            close_btn.setStyleSheet("background-color: #e74c3c; color: white; padding: 2px 8px;")
            close_btn.clicked.connect(lambda checked=False, tid=t.get("id"): self._close_trade(tid))
            self.trades_table.setCellWidget(i, 5, close_btn)

    def _close_trade(self, trade_id: str):
        try:
            self.client.close_trade(trade_id)
            self.refresh_data()
        except Exception as e:
            self.status_label.setText(f"Close failed: {str(e)}")
            self.status_label.setStyleSheet("color: #e74c3c;")

    def _update_snapshot(self, snapshot: Dict[str, Any]):
        if not snapshot:
            self.snapshot_label.setText("No data")
            return

        price = snapshot.get("price", {})
        ind = snapshot.get("indicators", {})
        sig = snapshot.get("signals", {})

        text = (
            f"Instrument: {fmt(snapshot.get('instrument'))}\n"
            f"Timeframe: {snapshot.get('timeframe')}\n"
            f"Close: {price.get('close')}\n\n"
            f"EMA20: {ind.get('ema_20')}\n"
            f"EMA50: {ind.get('ema_50')}\n"
            f"RSI14: {ind.get('rsi_14')}\n"
            f"MACD: {ind.get('macd')}\n"
            f"ATR14: {ind.get('atr_14')}\n"
            f"ADX14: {ind.get('adx_14')}\n\n"
            f"Trend: {sig.get('trend')}\n"
            f"EMA Cross: {sig.get('ema_crossover')}\n"
            f"RSI Signal: {sig.get('rsi_signal')}\n"
            f"MACD Signal: {sig.get('macd_signal')}\n"
            f"Volatility: {sig.get('volatility')}"
        )
        self.snapshot_label.setText(text)

    def _update_decision_log_from_history(self, history: List[Dict[str, Any]]):
        self.decision_log.setRowCount(len(history))
        for i, row in enumerate(history):
            ts = str(row.get("timestamp", ""))[-8:]
            decision = str(row.get("llm_decision", row.get("decision", "")))
            confidence = str(row.get("llm_confidence", row.get("confidence", "")))
            reason = str(row.get("llm_reasoning", row.get("reasoning", "")))[:60]

            self.decision_log.setItem(i, 0, QTableWidgetItem(ts))

            dec_item = QTableWidgetItem(decision)
            if decision == "BUY":
                dec_item.setForeground(make_color_brush("#2ecc71"))
            elif decision == "SELL":
                dec_item.setForeground(make_color_brush("#e74c3c"))
            elif decision in {"CLOSE", "PARTIAL_CLOSE", "BREAKEVEN"}:
                dec_item.setForeground(make_color_brush("#f39c12"))

            self.decision_log.setItem(i, 1, dec_item)
            self.decision_log.setItem(i, 2, QTableWidgetItem(confidence))
            self.decision_log.setItem(i, 3, QTableWidgetItem(reason))

    def _start_bot(self):
        instrument = self.instrument_combo.currentData()
        self.trading_engine.instruments = [instrument]
        self.trading_engine.run_continuous()
        self.refresh_data()

    def _stop_bot(self):
        self.trading_engine.stop()
        self.refresh_data()

    def _open_risk_settings(self):
        dialog = RiskSettingsDialog(self.account, self)
        if dialog.exec() == QDialog.Accepted:
            was_running = self.trading_engine.running
            if was_running:
                self.trading_engine.stop()
            self.trading_engine = TradingEngine(self.account, self.llm_config)
            if was_running:
                selected = self.instrument_combo.currentData()
                self.trading_engine.instruments = [selected]
                self.trading_engine.run_continuous()
            self.refresh_data()

    def closeEvent(self, event):
        if self._refresh_thread is not None and self._refresh_thread.isRunning():
            self._refresh_thread.quit()
            self._refresh_thread.wait(2000)
        self.trading_engine.stop()
        super().closeEvent(event)