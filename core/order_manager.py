"""Order manager for advanced trade execution with SL/TP."""
from typing import Dict, Any, Optional

from core.oanda_client import OandaClient


class OrderManager:
    """Handles order creation with risk-managed stop loss and take profit."""

    def __init__(self, client: OandaClient):
        self.client = client

    def execute_market_order(
        self,
        instrument: str,
        direction: str,
        units: int,
        entry_price: float,
        stop_loss_pips: Optional[int] = None,
        take_profit_pips: Optional[int] = None,
        trailing_stop_pips: Optional[int] = None,
        use_atr: bool = False,
        atr_value: float = 0.0,
    ) -> Dict[str, Any]:
        """Execute market order with calculated SL/TP."""
        pip = 0.01 if "JPY" in instrument else 0.0001

        if use_atr and atr_value > 0:
            sl_pips = max(15, int((atr_value / pip) * 1.5))
            tp_pips = int(sl_pips * 2)
        else:
            sl_pips = stop_loss_pips or 30
            tp_pips = take_profit_pips or sl_pips * 2

        sl_distance = sl_pips * pip
        tp_distance = tp_pips * pip

        if direction == "BUY":
            stop_loss = entry_price - sl_distance
            take_profit = entry_price + tp_distance
            signed_units = abs(int(units))
        else:
            stop_loss = entry_price + sl_distance
            take_profit = entry_price - tp_distance
            signed_units = -abs(int(units))

        decimals = 3 if "JPY" in instrument else 5
        stop_loss = round(stop_loss, decimals)
        take_profit = round(take_profit, decimals)

        trailing_distance = None
        if trailing_stop_pips:
            trailing_distance = round(trailing_stop_pips * pip, decimals)

        result = self.client.create_market_order(
            instrument=instrument,
            units=signed_units,
            stop_loss=stop_loss,
            take_profit=take_profit,
            trailing_stop_distance=trailing_distance,
        )

        return {
            "success": "orderFillTransaction" in result or "orderCreateTransaction" in result,
            "result": result,
            "stop_loss": stop_loss,
            "take_profit": take_profit,
            "trailing_distance": trailing_distance,
        }

    def execute_limit_order(
        self,
        instrument: str,
        direction: str,
        units: int,
        limit_price: float,
        stop_loss_pips: int = 30,
        take_profit_pips: Optional[int] = None,
    ) -> Dict[str, Any]:
        """Place a limit order with SL/TP."""
        pip = 0.01 if "JPY" in instrument else 0.0001
        sl_distance = stop_loss_pips * pip
        tp_pips = take_profit_pips or stop_loss_pips * 2
        tp_distance = tp_pips * pip

        if direction == "BUY":
            stop_loss = limit_price - sl_distance
            take_profit = limit_price + tp_distance
            signed_units = abs(int(units))
        else:
            stop_loss = limit_price + sl_distance
            take_profit = limit_price - tp_distance
            signed_units = -abs(int(units))

        decimals = 3 if "JPY" in instrument else 5
        stop_loss = round(stop_loss, decimals)
        take_profit = round(take_profit, decimals)
        limit_price = round(limit_price, decimals)

        result = self.client.create_limit_order(
            instrument=instrument,
            units=signed_units,
            price=limit_price,
            stop_loss=stop_loss,
            take_profit=take_profit,
        )

        return {
            "success": "orderCreateTransaction" in result,
            "result": result,
            "stop_loss": stop_loss,
            "take_profit": take_profit,
        }

    def execute_stop_entry(
        self,
        instrument: str,
        direction: str,
        units: int,
        stop_price: float,
        stop_loss_pips: int = 30,
        take_profit_pips: Optional[int] = None,
    ) -> Dict[str, Any]:
        """Place a stop entry order with SL/TP."""
        pip = 0.01 if "JPY" in instrument else 0.0001
        sl_distance = stop_loss_pips * pip
        tp_pips = take_profit_pips or stop_loss_pips * 2
        tp_distance = tp_pips * pip

        if direction == "BUY":
            stop_loss = stop_price - sl_distance
            take_profit = stop_price + tp_distance
            signed_units = abs(int(units))
        else:
            stop_loss = stop_price + sl_distance
            take_profit = stop_price - tp_distance
            signed_units = -abs(int(units))

        decimals = 3 if "JPY" in instrument else 5
        stop_loss = round(stop_loss, decimals)
        take_profit = round(take_profit, decimals)
        stop_price = round(stop_price, decimals)

        result = self.client.create_stop_order(
            instrument=instrument,
            units=signed_units,
            price=stop_price,
            stop_loss=stop_loss,
            take_profit=take_profit,
        )

        return {
            "success": "orderCreateTransaction" in result,
            "result": result,
            "stop_loss": stop_loss,
            "take_profit": take_profit,
        }

    def move_to_breakeven(self, trade_id: str, entry_price: float, current_sl: float) -> bool:
        """Move stop loss to breakeven if profitable."""
        try:
            self.client.modify_trade_stop_loss(trade_id, entry_price)
            return True
        except Exception:
            return False

    def partial_close(self, trade_id: str, units: int) -> bool:
        """Close half or partial position."""
        try:
            self.client.partial_close_trade(trade_id, units)
            return True
        except Exception:
            return False

    def calculate_position_size(
        self,
        balance: float,
        risk_percent: float,
        stop_loss_pips: int,
        instrument: str,
    ) -> int:
        """Calculate units based on risk %."""
        risk_amount = balance * (risk_percent / 100.0)
        risk_pips = max(1, int(stop_loss_pips or 30))
        pip_value_per_1000_units = 0.10
        units = int((risk_amount / (risk_pips * pip_value_per_1000_units)) * 1000)
        return max(1000, units)