"""Dashboard wired to trading engines for each account tab."""
import json
import threading
import time
from typing import Dict, Any, Optional

import flet as ft
from flet import Page, Column, Row, Container, Text

from core.oanda_client import OandaClient, OandaConfig
from core.data_engine import DataEngine
from core.trading_engine import TradingEngine
from ui.account_tab import AccountTab


class DashboardApp:
    def __init__(self, page: Page):
        self.page = page
        self.page.title = "FX LLM Trading Bot"
        self.page.theme_mode = ft.ThemeMode.DARK
        self.page.padding = 0
        self.page.spacing = 0
        self.page.bgcolor = ft.Colors.SURFACE

        self.account_tabs: Dict[str, AccountTab] = {}
        self.tab_bar: Optional[ft.TabBar] = None
        self.tab_view: Optional[ft.TabBarView] = None
        self.tabs_control: Optional[ft.Tabs] = None

        self.config = self._load_config()
        self._build_ui()
        self._start_refresh_loop()

    def _load_config(self) -> Dict[str, Any]:
        with open("config/accounts.json", "r") as f:
            return json.load(f)

    def _build_ui(self):
        accounts = self.config.get("accounts", [])
        if isinstance(accounts, dict):
            accounts = [accounts]
        llm_config = self.config.get("llm", {})

        nav = Container(
            content=Row([
                Text("FX LLM Bot", size=20, weight="bold", color=ft.Colors.WHITE),
                ft.IconButton(icon=ft.Icons.REFRESH, tooltip="Refresh", on_click=self._manual_refresh),
            ], alignment=ft.MainAxisAlignment.SPACE_BETWEEN),
            padding=15,
            bgcolor=ft.Colors.SURFACE_CONTAINER_HIGHEST,
            border_radius=ft.BorderRadius.only(bottom_left=10, bottom_right=10)
        )

        # Build tab bar and tab view
        tab_bar_tabs = []
        tab_view_controls = []

        for account in accounts:
            if not account.get("active", True):
                continue
            name = account.get("name", account["account_id"])
            oanda_cfg = OandaConfig(
                access_token=account["access_token"],
                account_id=account["account_id"],
                environment=account.get("environment", "practice")
            )
            client = OandaClient(oanda_cfg)
            data_engine = DataEngine(client, data_dir=f"data/{account['account_id']}")
            trading_engine = TradingEngine(account, llm_config)
            tab_view_instance = AccountTab(name, client, data_engine, trading_engine)
            self.account_tabs[name] = tab_view_instance

            tab_bar_tabs.append(ft.Tab(label=ft.Text(name)))
            tab_view_controls.append(tab_view_instance.build())

        if not tab_bar_tabs:
            tab_bar_tabs.append(ft.Tab(label=ft.Text("Welcome")))
            tab_view_controls.append(Container(content=Text("No active accounts configured"), padding=20))

        self.tab_bar = ft.TabBar(tabs=tab_bar_tabs)
        self.tab_view = ft.TabBarView(controls=tab_view_controls, expand=True)

        self.tabs_control = ft.Tabs(
            length=len(tab_bar_tabs),
            selected_index=0,
            expand=True,
            content=ft.Column(
                expand=True,
                controls=[
                    self.tab_bar,
                    self.tab_view
                ]
            )
        )

        self.page.add(Column([nav, self.tabs_control], expand=True, spacing=0))

    def _manual_refresh(self, e):
        for tab in self.account_tabs.values():
            tab.refresh_data()
        self.page.update()

    def _start_refresh_loop(self):
        def loop():
            while True:
                time.sleep(5)
                try:
                    for tab in self.account_tabs.values():
                        tab.refresh_data()
                    self.page.update()
                except Exception:
                    pass
        threading.Thread(target=loop, daemon=True).start()


def main(page: Page):
    DashboardApp(page)


if __name__ == "__main__":
    ft.run(main)