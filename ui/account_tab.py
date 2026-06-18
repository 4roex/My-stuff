"""Enhanced account tab UI with Plotly charts."""
from typing import Dict, Any, Optional, List
from datetime import datetime
import threading

import flet as ft
from flet import (
    Column, Row, Container, Text, Card, DataTable, DataColumn, DataCell, DataRow,
    alignment, IconButton, ElevatedButton, Dropdown, dropdown, Image
)

from core.oanda_client import OandaClient
from core.data_engine import DataEngine
from core.trading_engine import TradingEngine
from ui.charts import ChartGenerator


class AccountTab:
    """Content for a single account tab with charts and trading controls."""

    def __init__(self, name: str, client: OandaClient, engine: DataEngine, trading_engine: Optional[TradingEngine] = None):
        self.name = name
        self.client = client
        self.engine = engine
        self.trading_engine = trading_engine
        self.chart_gen = ChartGenerator()

        self.summary_text: Optional[Text] = None
        self.pnl_text: Optional[Text] = None
        self.open_trades_text: Optional[Text] = None
        self.win_rate_text: Optional[Text] = None
        self.trade_table: Optional[DataTable] = None
        self.chart_image: Optional[Image] = None
        self.indicator_text: Optional[Text] = None
        self.last_decision_text: Optional[Text] = None
        self.status_text: Optional[Text] = None
        self.instrument_dropdown: Optional[Dropdown] = None
        self.start_button: Optional[ElevatedButton] = None
        self.stop_button: Optional[ElevatedButton] = None

    def build(self) -> ft.Control:
        summary_row = self._build_summary_cards()
        control_row = self._build_control_row()
        chart_area = self._build_chart_area()
        bottom_row = self._build_bottom_section()

        self.refresh_data()

        return Column([
            summary_row,
            control_row,
            chart_area,
            bottom_row
        ], expand=True, spacing=10, scroll=ft.ScrollMode.AUTO)

    def _build_summary_cards(self) -> Row:
        self.summary_text = Text("Loading...", size=16, weight="bold")
        self.pnl_text = Text("$0.00", size=14, color=ft.Colors.GREEN)
        self.open_trades_text = Text("0", size=16, weight="bold")
        self.win_rate_text = Text("0%", size=16, weight="bold")

        return Row([
            self._card("Balance", self.summary_text, ft.Icons.ACCOUNT_BALANCE),
            self._card("Unrealized P&L", self.pnl_text, ft.Icons.TRENDING_UP),
            self._card("Open Trades", self.open_trades_text, ft.Icons.SWAP_HORIZ),
            self._card("Win Rate", self.win_rate_text, ft.Icons.EMOJI_EVENTS),
        ], spacing=10)

    def _card(self, title: str, content: Text, icon_name: str) -> Card:
        return Card(
            content=Container(
                content=Column([
                    Row([
                        ft.Icon(icon=icon_name, color=ft.Colors.BLUE),
                        Text(title, size=12, color=ft.Colors.GREY)
                    ]),
                    content
                ], spacing=5),
                padding=15,
                width=220
            ),
            elevation=2
        )

    def _build_control_row(self) -> Card:
        self.last_decision_text = Text("Last decision: None", size=14)
        self.status_text = Text("Engine: Stopped", size=14, color=ft.Colors.ORANGE)
        self.instrument_dropdown = Dropdown(
            width=160,
            value="EUR_USD",
            options=[
                dropdown.Option("EUR_USD"),
                dropdown.Option("GBP_USD"),
                dropdown.Option("USD_JPY")
            ]
        )
        self.start_button = ElevatedButton("Start Bot", icon=ft.Icons.PLAY_ARROW, on_click=self._start_bot)
        self.stop_button = ElevatedButton("Stop Bot", icon=ft.Icons.STOP, on_click=self._stop_bot)

        return Card(
            content=Container(
                content=Row([
                    self.instrument_dropdown,
                    self.start_button,
                    self.stop_button,
                    self.last_decision_text,
                    self.status_text
                ], alignment=ft.MainAxisAlignment.SPACE_BETWEEN),
                padding=12
            )
        )

    def _build_chart_area(self) -> Container:
        self.chart_image = Image(
            src="output/charts/placeholder.png",
            width=900,
            height=400,
            fit=ft.ImageFit.CONTAIN,
            border_radius=10
        )
        return Container(
            content=self.chart_image,
            bgcolor=ft.Colors.SURFACE_CONTAINER_HIGHEST,
            padding=12,
            border_radius=10,
            height=420,
            expand=True,
            alignment=alignment.center
        )

    def _build_bottom_section(self) -> Row:
        self.trade_table = DataTable(
            columns=[
                DataColumn(Text("ID")),
                DataColumn(Text("Instrument")),
                DataColumn(Text("Units")),
                DataColumn(Text("Entry")),
                DataColumn(Text("P&L")),
                DataColumn(Text("Action")),
            ],
            rows=[]
        )

        self.indicator_text = Text("Loading indicators...", size=12, selectable=True)

        left = Card(
            content=Container(
                content=Column([
                    Text("Open Trades", size=16, weight="bold"),
                    self.trade_table
                ], scroll=ft.ScrollMode.AUTO),
                padding=10,
                expand=True
            ),
            expand=True
        )

        right = Card(
            content=Container(
                content=Column([
                    Text("Market Snapshot", size=16, weight="bold"),
                    self.indicator_text
                ], scroll=ft.ScrollMode.AUTO),
                padding=10,
                width=380
            )
        )

        return Row([left, right], expand=True, spacing=10)

    def refresh_data(self):
        try:
            summary = self.client.get_account_summary()
            acc = summary.get("account", {})
            balance = float(acc.get("balance", 0))
            unrealized_pl = float(acc.get("unrealizedPL", 0))
            open_count = int(acc.get("openTradeCount", 0))

            if self.summary_text:
                self.summary_text.value = f"${balance:,.2f}"
            if self.pnl_text:
                self.pnl_text.value = f"${unrealized_pl:+.2f}"
                self.pnl_text.color = ft.Colors.GREEN if unrealized_pl >= 0 else ft.Colors.RED
            if self.open_trades_text:
                self.open_trades_text.value = str(open_count)

            if self.trading_engine:
                stats = self.trading_engine.logger.get_performance_stats(days=30)
                if self.win_rate_text:
                    self.win_rate_text.value = f"{stats.get('win_rate', 0):.1f}%"
                if self.status_text:
                    running = self.trading_engine.running
                    self.status_text.value = "Engine: Running" if running else "Engine: Stopped"
                    self.status_text.color = ft.Colors.GREEN if running else ft.Colors.ORANGE

            trades = self.client.get_open_trades()
            self._update_trade_table(trades)

            instrument = self.instrument_dropdown.value if self.instrument_dropdown else "EUR_USD"
            
            # Update chart
            df = self.engine.get_data_with_indicators(instrument, granularity="M5", count=100)
            if not df.empty and self.chart_image:
                chart_path = self.chart_gen.create_candlestick_chart(
                    df, instrument, indicators=["ema_20", "ema_50"]
                )
                self.chart_image.src = chart_path
                self.chart_gen.cleanup_old_charts()
            
            snapshot = self.engine.get_latest_market_snapshot(instrument, granularity="M5")
            self._update_indicators(snapshot)
        except Exception as e:
            if self.status_text:
                self.status_text.value = f"Refresh error: {str(e)}"
                self.status_text.color = ft.Colors.RED

    def _update_trade_table(self, trades: List[dict]):
        if not self.trade_table:
            return
        rows = []
        for t in trades:
            pl = float(t.get("unrealizedPL", 0))
            rows.append(DataRow(cells=[
                DataCell(Text(str(t.get("id", "")))),
                DataCell(Text(str(t.get("instrument", "")))),
                DataCell(Text(str(t.get("currentUnits", "")))),
                DataCell(Text(str(t.get("price", "")))),
                DataCell(Text(f"${pl:+.2f}", color=ft.Colors.GREEN if pl >= 0 else ft.Colors.RED)),
                DataCell(IconButton(icon=ft.Icons.CLOSE, tooltip="Close trade"))
            ]))
        self.trade_table.rows = rows

    def _update_indicators(self, snapshot: Dict[str, Any]):
        if not self.indicator_text:
            return
        if not snapshot:
            self.indicator_text.value = "No snapshot available"
            return
        price = snapshot.get("price", {})
        ind = snapshot.get("indicators", {})
        sig = snapshot.get("signals", {})
        self.indicator_text.value = "\n".join([
            f"Instrument: {snapshot.get('instrument')}",
            f"Timeframe: {snapshot.get('timeframe')}",
            f"Close: {price.get('close')}",
            "",
            f"EMA20: {ind.get('ema_20')}",
            f"EMA50: {ind.get('ema_50')}",
            f"EMA200: {ind.get('ema_200')}",
            f"RSI14: {ind.get('rsi_14')}",
            f"MACD: {ind.get('macd')}",
            f"ATR14: {ind.get('atr_14')}",
            f"ADX14: {ind.get('adx_14')}",
            "",
            f"Trend: {sig.get('trend')}",
            f"EMA Cross: {sig.get('ema_crossover')}",
            f"RSI Signal: {sig.get('rsi_signal')}",
            f"MACD Signal: {sig.get('macd_signal')}",
            f"Volatility: {sig.get('volatility')}",
        ])

    def run_single_decision(self):
        if not self.trading_engine:
            return
        instrument = self.instrument_dropdown.value if self.instrument_dropdown else "EUR_USD"
        result = self.trading_engine.run_single_cycle(instrument)
        if self.last_decision_text:
            self.last_decision_text.value = f"Last decision: {result.get('decision')} | {result.get('reason', '')}"
        self.refresh_data()

    def _start_bot(self, e):
        if not self.trading_engine:
            return
        selected = self.instrument_dropdown.value if self.instrument_dropdown else "EUR_USD"
        self.trading_engine.instruments = [selected]
        self.trading_engine.run_continuous()
        self.refresh_data()
        if e and e.page:
            e.page.update()

    def _stop_bot(self, e):
        if not self.trading_engine:
            return
        self.trading_engine.stop()
        self.refresh_data()
        if e and e.page:
            e.page.update()