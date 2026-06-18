"""Trading engine with LLM-driven decisions, risk management, filters, and broker sync."""
import threading
import time
from datetime import datetime, timezone
from typing import Dict, Any, List, Optional

from core.oanda_client import OandaClient, OandaConfig
from core.data_engine import DataEngine
from core.llm_client import LLMClient, LLMTradeDecision
from core.order_manager import OrderManager
from core.notifications import NotificationManager
from core.database import TradeDatabase
from core.correlation import CorrelationFilter
from core.news_filter import NewsFilter
from core.secure_settings import SecureSettings


class TradingEngine:
    """Executes trades based on LLM + technical analysis with full risk management."""

    def __init__(self, account: Dict[str, Any], llm_config: Dict[str, Any]):
        self.account = account
        self.llm = LLMClient(llm_config)
        self.running = False
        self._stop_event = threading.Event()
        self._thread: Optional[threading.Thread] = None
        self.instruments: List[str] = list(account.get("instruments", ["EUR_USD"]))
        self.secure_settings = SecureSettings()
        self.risk = self._build_risk_settings(account)
        self.db = TradeDatabase(account["account_id"])
        self.notifier = NotificationManager(enabled=self._get_risk_bool("notifications_enabled", True))
        self.correlation_filter = CorrelationFilter()
        self.news_filter = NewsFilter()
        self._daily_pnl = 0.0
        self._last_trade_time = 0.0
        self._start_of_day_balance = 0.0
        self._managed_trades: set[str] = set()
        self._last_transaction_id = self.db.get_setting("last_transaction_id", "")

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

    def _build_risk_settings(self, account: Dict[str, Any]) -> Dict[str, Any]:
        base = dict(account.get("risk", {}) or {})

        flat_defaults = {
            "max_risk_percent": account.get("max_risk_percent", 1.0),
            "daily_drawdown_limit": account.get("daily_drawdown_limit", 5.0),
            "total_drawdown_limit": account.get("total_drawdown_limit", 10.0),
            "cooldown_minutes": account.get("cooldown_minutes", 15),
            "daily_drawdown_enabled": account.get("daily_drawdown_enabled", True),
            "total_drawdown_enabled": account.get("total_drawdown_enabled", True),
            "correlation_filter": account.get("correlation_filter", True),
            "news_filter_enabled": account.get("news_filter_enabled", False),
            "spread_filter": account.get("spread_filter", False),
            "max_spread_pips": account.get("max_spread_pips", 5),
            "session_filter": account.get("session_filter", False),
            "allowed_sessions": account.get("allowed_sessions", ["london", "ny"]),
            "max_open_trades": account.get("max_open_trades", 3),
            "min_units": account.get("min_units", 1000),
            "max_leverage": account.get("max_leverage", 50),
            "auto_sl_tp": account.get("auto_sl_tp", True),
            "use_atr_sl": account.get("use_atr_sl", True),
            "trailing_stop": account.get("trailing_stop", False),
            "trailing_fixed_pips": account.get("trailing_fixed_pips", 20),
            "auto_breakeven": account.get("auto_breakeven", False),
            "partial_close": account.get("partial_close", False),
            "partial_close_pct": account.get("partial_close_pct", 50),
            "notifications_enabled": account.get("notifications_enabled", True),
        }

        for key, value in flat_defaults.items():
            base.setdefault(key, value)

        return base

    def _get_risk_bool(self, key: str, default: bool = False) -> bool:
        value = self.risk.get(key, default)
        if isinstance(value, str):
            return value.strip().lower() in {"1", "true", "yes", "on"}
        return bool(value)

    def _get_risk_float(self, key: str, default: float = 0.0) -> float:
        try:
            return float(self.risk.get(key, default))
        except (TypeError, ValueError):
            return float(default)

    def _get_risk_int(self, key: str, default: int = 0) -> int:
        try:
            return int(float(self.risk.get(key, default)))
        except (TypeError, ValueError):
            return int(default)

    def sync_broker_history_now(self) -> tuple[bool, str]:
        """Run broker-history sync on demand from the UI."""
        try:
            client = self._create_client()
            before = self._last_transaction_id
            self._sync_broker_history(client)
            after = self._last_transaction_id

            if after and after != before:
                return True, f"Broker history synced. Last transaction ID: {after}"
            if after:
                return True, "Broker history checked. No new broker updates found."
            return True, "Broker history check completed."
        except Exception as e:
            self.db.log_error(f"Manual broker sync failed: {str(e)}")
            return False, f"Manual sync failed: {str(e)}"

    def run_continuous(self, interval: int = 60):
        if self.running:
            return
        self.running = True
        self._stop_event.clear()
        self._thread = threading.Thread(target=self._trading_loop, args=(interval,), daemon=True)
        self._thread.start()

    def stop(self):
        self.running = False
        self._stop_event.set()
        if self._thread and self._thread.is_alive() and self._thread is not threading.current_thread():
            self._thread.join(timeout=5)

    def _trading_loop(self, interval: int):
        client = self._create_client()
        data_engine = DataEngine(client)
        order_manager = OrderManager(client)

        try:
            summary = client.get_account_summary().get("account", {})
            self._start_of_day_balance = float(summary.get("balance", 0) or 0)
            if not self._last_transaction_id:
                self._last_transaction_id = str(summary.get("lastTransactionID", "") or "")
            if self._last_transaction_id:
                self.db.set_setting("last_transaction_id", self._last_transaction_id)
        except Exception:
            pass

        while not self._stop_event.is_set():
            try:
                self._evaluate_and_trade(client, data_engine, order_manager)
                self._manage_open_trades(client, data_engine, order_manager)
                self._sync_broker_history(client)
            except Exception as e:
                self.db.log_error(str(e))
                self.notifier.error(str(e))
            self._stop_event.wait(interval)

    def _evaluate_and_trade(self, client: OandaClient, data_engine: DataEngine, order_manager: OrderManager):
        summary = client.get_account_summary().get("account", {})
        balance = float(summary.get("balance", 0) or 0)
        unrealized_pl = float(summary.get("unrealizedPL", 0) or 0)
        total_pl = self._daily_pnl + unrealized_pl
        open_trades = client.get_open_trades()
        history = self.db.get_trade_history(limit=10)

        if self._start_of_day_balance <= 0:
            self._start_of_day_balance = balance

        if self._get_risk_bool("daily_drawdown_enabled", True):
            limit = self._get_risk_float("daily_drawdown_limit", 5.0)
            if self._start_of_day_balance > 0 and total_pl <= -(self._start_of_day_balance * limit / 100):
                self.db.log_error("Daily loss limit hit. Trading paused.")
                self.notifier.limit_hit("Daily Drawdown", f"Loss exceeded {limit}%")
                return

        if self._get_risk_bool("total_drawdown_enabled", True):
            limit = self._get_risk_float("total_drawdown_limit", 10.0)
            if self._start_of_day_balance > 0 and balance < self._start_of_day_balance * (1 - limit / 100):
                self.db.log_error("Total drawdown limit hit. Trading paused.")
                self.notifier.limit_hit("Total Drawdown", f"Loss exceeded {limit}%")
                return

        cooldown = self._get_risk_int("cooldown_minutes", 15) * 60
        if time.time() - self._last_trade_time < cooldown:
            return

        if self._get_risk_bool("session_filter", False):
            if not self._is_allowed_session():
                return

        for inst in list(self.instruments):
            if self._get_risk_bool("news_filter_enabled", False):
                blocked, reason = self.news_filter.has_blocking_news(inst)
                if blocked:
                    self.db.log_error(f"News filter blocked {inst}: {reason}")
                    continue

            snapshot = data_engine.get_latest_market_snapshot(inst, granularity="M5")
            if not snapshot:
                continue

            if self._get_risk_bool("spread_filter", False):
                if not self._spread_ok(snapshot, inst):
                    continue

            decision = self.llm.get_trade_decision(
                instrument=inst,
                snapshot=snapshot,
                account_summary=summary,
                open_trades=[t for t in open_trades if t.get("instrument") == inst],
                recent_history=history,
                risk_params=self.risk,
            )

            self.db.log_decision(decision.__dict__)
            self.notifier.signal(inst, decision.decision, decision.confidence, decision.reasoning)

            if decision.decision in ("BUY", "SELL"):
                if self._get_risk_bool("correlation_filter", True):
                    blocked, reason = self.correlation_filter.is_blocked(inst, decision.decision, open_trades)
                    if blocked:
                        self.db.log_error(f"Correlation filter blocked {inst}: {reason}")
                        continue
                self._execute_trade(client, order_manager, inst, decision, balance, snapshot)
            elif decision.decision == "CLOSE":
                self._close_positions(client, inst)

    def _execute_trade(
        self,
        client: OandaClient,
        order_manager: OrderManager,
        instrument: str,
        decision: LLMTradeDecision,
        balance: float,
        snapshot: Dict[str, Any],
    ):
        max_trades = self._get_risk_int("max_open_trades", 3)
        if len(client.get_open_trades()) >= max_trades:
            self.db.log_error(f"Max open trades reached. Skipping {instrument}.")
            return

        price_data = snapshot.get("price", {})
        entry_price = float(price_data.get("close", 0) or 0)
        if entry_price == 0:
            self.db.log_error(f"Invalid price for {instrument}")
            return

        atr = float(snapshot.get("indicators", {}).get("atr_14", 0.0001) or 0.0001)
        pip = 0.01 if "JPY" in instrument else 0.0001
        sl_pips = decision.stop_loss_pips or max(20, int((atr / pip) * 1.5))

        risk_percent = float(decision.risk_percent or self._get_risk_float("max_risk_percent", 1.0))
        risk_percent = min(risk_percent, self._get_risk_float("max_risk_percent", 1.0))

        units = order_manager.calculate_position_size(balance, risk_percent, sl_pips, instrument)
        min_units = self._get_risk_int("min_units", 1000)
        units = max(min_units, units)

        max_leverage = self._get_risk_int("max_leverage", 50)
        max_units = int(balance * max_leverage / entry_price) if entry_price > 0 else units
        units = min(units, max_units)

        if units < min_units:
            self.db.log_error(f"Calculated units below minimum for {instrument}")
            return

        auto_sl_tp = self._get_risk_bool("auto_sl_tp", True)
        use_atr_sl = self._get_risk_bool("use_atr_sl", True)
        trail_fixed = self._get_risk_int("trailing_fixed_pips", 20)
        trailing = self._get_risk_bool("trailing_stop", False)

        if auto_sl_tp:
            result = order_manager.execute_market_order(
                instrument=instrument,
                direction=decision.decision,
                units=units,
                entry_price=entry_price,
                stop_loss_pips=sl_pips if not use_atr_sl else None,
                take_profit_pips=decision.take_profit_pips,
                trailing_stop_pips=trail_fixed if trailing else None,
                use_atr=use_atr_sl,
                atr_value=atr,
            )
        else:
            result = {
                "success": True,
                "result": client.create_market_order(
                    instrument=instrument,
                    units=units if decision.decision == "BUY" else -units,
                ),
                "stop_loss": None,
                "take_profit": None,
            }

        if result["success"]:
            self._last_trade_time = time.time()
            fill = result["result"].get("orderFillTransaction", {})
            trade_data = {
                "trade_id": fill.get("id", ""),
                "instrument": instrument,
                "direction": decision.decision,
                "units": units if decision.decision == "BUY" else -units,
                "entry_price": entry_price,
                "stop_loss": result.get("stop_loss"),
                "take_profit": result.get("take_profit"),
                "llm_decision": decision.decision,
                "llm_confidence": decision.confidence,
                "llm_reasoning": decision.reasoning,
            }
            self.db.log_trade(trade_data)
            self.notifier.trade_opened(
                instrument,
                decision.decision,
                units,
                result.get("stop_loss"),
                result.get("take_profit"),
            )
        else:
            self.db.log_error(f"Order failed for {instrument}: {result}")
            self.notifier.error(f"Order failed for {instrument}")

    def _close_positions(self, client: OandaClient, instrument: str):
        trades = [t for t in client.get_open_trades() if t.get("instrument") == instrument]
        for t in trades:
            try:
                pl = float(t.get("unrealizedPL", 0) or 0)
                trade_id = t.get("id")
                client.close_trade(trade_id)
                self.db.close_trade(trade_id, float(t.get("price", 0) or 0), pl)
                self.notifier.trade_closed(instrument, pl, "manual close")
            except Exception as e:
                self.db.log_error(f"Close failed for {t.get('id')}: {str(e)}")

    def _manage_open_trades(self, client: OandaClient, data_engine: DataEngine, order_manager: OrderManager):
        if not self._get_risk_bool("auto_breakeven", False) and not self._get_risk_bool("partial_close", False):
            return

        open_trades = client.get_open_trades()
        for t in open_trades:
            try:
                trade_id = t.get("id")
                inst = t.get("instrument", "")
                units = float(t.get("currentUnits", 0) or 0)
                entry = float(t.get("price", 0) or 0)

                if units == 0 or entry == 0:
                    continue

                direction = 1 if units > 0 else -1
                pip = 0.01 if "JPY" in inst else 0.0001

                snapshot = data_engine.get_latest_market_snapshot(inst, granularity="M5")
                if not snapshot:
                    continue

                current_price = float(snapshot.get("price", {}).get("close", 0) or 0)
                if current_price == 0:
                    continue

                if direction == 1:
                    distance_pips = (current_price - entry) / pip
                else:
                    distance_pips = (entry - current_price) / pip

                if distance_pips <= 0:
                    continue

                sl_price = None
                tp_price = None
                if t.get("stopLossOrder"):
                    sl_price = float(t["stopLossOrder"].get("price", 0) or 0)
                if t.get("takeProfitOrder"):
                    tp_price = float(t["takeProfitOrder"].get("price", 0) or 0)

                tp_distance_pips = 0.0
                if tp_price:
                    tp_distance_pips = abs(tp_price - entry) / pip

                if self._get_risk_bool("auto_breakeven", False):
                    halfway = tp_distance_pips * 0.5 if tp_distance_pips > 0 else 20
                    should_move = distance_pips >= halfway

                    if should_move:
                        if direction == 1 and (sl_price is None or sl_price < entry):
                            if order_manager.move_to_breakeven(trade_id, entry, sl_price or 0):
                                self.notifier.breakeven(inst)
                                self.db.log_decision({
                                    "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
                                    "instrument": inst,
                                    "decision": "BREAKEVEN",
                                    "confidence": 100,
                                    "reasoning": f"Price moved {distance_pips:.1f} pips, moved SL to entry",
                                })
                        elif direction == -1 and (sl_price is None or sl_price > entry):
                            if order_manager.move_to_breakeven(trade_id, entry, sl_price or 0):
                                self.notifier.breakeven(inst)
                                self.db.log_decision({
                                    "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
                                    "instrument": inst,
                                    "decision": "BREAKEVEN",
                                    "confidence": 100,
                                    "reasoning": f"Price moved {distance_pips:.1f} pips, moved SL to entry",
                                })

                if self._get_risk_bool("partial_close", False):
                    if trade_id in self._managed_trades:
                        continue

                    halfway = tp_distance_pips * 0.5 if tp_distance_pips > 0 else 20
                    if distance_pips >= halfway:
                        pct = self._get_risk_int("partial_close_pct", 50)
                        close_units = int(abs(units) * pct / 100)
                        if close_units >= 1000:
                            if order_manager.partial_close(trade_id, close_units):
                                self._managed_trades.add(trade_id)
                                self.notifier.partial_close(inst, pct, close_units)
                                self.db.log_decision({
                                    "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
                                    "instrument": inst,
                                    "decision": "PARTIAL_CLOSE",
                                    "confidence": 100,
                                    "reasoning": f"Closed {pct}% ({close_units} units) at {distance_pips:.1f} pips",
                                })

            except Exception as e:
                self.db.log_error(f"Trade management failed: {str(e)}")

    def _sync_broker_history(self, client: OandaClient):
        """Sync broker-side closed or reduced trades into the local database."""
        try:
            if not self._last_transaction_id:
                summary = client.get_account_summary().get("account", {})
                self._last_transaction_id = str(summary.get("lastTransactionID", "") or "")
                if self._last_transaction_id:
                    self.db.set_setting("last_transaction_id", self._last_transaction_id)
                return

            result = client.get_account_changes(self._last_transaction_id)
            changes = result.get("changes", {})
            state = result.get("state", {})
            last_tx = result.get("lastTransactionID") or state.get("lastTransactionID")

            for trade in changes.get("tradesClosed", []):
                self._apply_closed_trade_sync(trade)

            for trade in changes.get("tradesReduced", []):
                self._log_reduced_trade(trade)

            if last_tx:
                self._last_transaction_id = str(last_tx)
                self.db.set_setting("last_transaction_id", self._last_transaction_id)

        except Exception as e:
            self.db.log_error(f"Broker history sync failed: {str(e)}")

    def _apply_closed_trade_sync(self, trade: Dict[str, Any]):
        trade_id = str(trade.get("id", "") or "")
        if not trade_id:
            return

        realized_pl = float(trade.get("realizedPL", 0) or 0)
        avg_close_price = float(trade.get("averageClosePrice", 0) or 0)

        updated = self.db.update_trade_close_from_broker(
            trade_id=trade_id,
            exit_price=avg_close_price,
            realized_pl=realized_pl,
        )

        if updated:
            instrument = trade.get("instrument", "")
            self.notifier.trade_closed(instrument, realized_pl, "broker sync")

    def _log_reduced_trade(self, trade: Dict[str, Any]):
        trade_id = str(trade.get("id", "") or "")
        instrument = trade.get("instrument", "")
        current_units = trade.get("currentUnits", "")
        realized_pl = float(trade.get("realizedPL", 0) or 0)

        self.db.log_decision({
            "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
            "instrument": instrument,
            "decision": "BROKER_REDUCE",
            "confidence": 100,
            "reasoning": f"Broker reduced trade {trade_id}; currentUnits={current_units}, realizedPL={realized_pl}",
        })

    def _spread_ok(self, snapshot: Dict[str, Any], instrument: str) -> bool:
        price = snapshot.get("price", {})
        bid = float(price.get("bid", 0) or 0)
        ask = float(price.get("ask", 0) or 0)

        if bid <= 0 or ask <= 0:
            return True

        spread = abs(ask - bid)
        pip = 0.01 if "JPY" in instrument else 0.0001
        spread_pips = spread / pip
        max_spread = self._get_risk_int("max_spread_pips", 5)
        return spread_pips <= max_spread

    def _is_allowed_session(self) -> bool:
        now = datetime.now(timezone.utc)
        hour = now.hour
        allowed = self.risk.get("allowed_sessions", ["london", "ny"])
        if isinstance(allowed, str):
            allowed = [allowed]

        sessions = {
            "london": 8 <= hour < 17,
            "ny": 13 <= hour < 22,
            "new_york": 13 <= hour < 22,
            "tokyo": 0 <= hour < 9,
            "sydney": hour >= 22 or hour < 7,
        }
        return any(sessions.get(str(session).lower(), False) for session in allowed)