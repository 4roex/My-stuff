"""OANDA v20 REST client."""
from dataclasses import dataclass
from typing import Dict, Any, Optional
import requests


@dataclass
class OandaConfig:
    access_token: str
    account_id: str
    environment: str = "practice"


class OandaClient:
    """Thin client for OANDA REST v20 API."""

    def __init__(self, config: OandaConfig):
        self.config = config
        if config.environment.lower() in ("live", "fxtrade"):
            self.base_url = "https://api-fxtrade.oanda.com/v3"
        else:
            self.base_url = "https://api-fxpractice.oanda.com/v3"

        self.session = requests.Session()
        self.session.headers.update({
            "Authorization": f"Bearer {self.config.access_token}",
            "Content-Type": "application/json",
            "Accept-Datetime-Format": "RFC3339",
        })

    def _make_request(
        self,
        method: str,
        endpoint: str,
        params: Optional[Dict[str, Any]] = None,
        data: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        url = f"{self.base_url}{endpoint}"
        response = self.session.request(
            method=method,
            url=url,
            params=params,
            json=data,
            timeout=30,
        )
        response.raise_for_status()
        if response.text.strip():
            return response.json()
        return {}

    def get_account_summary(self) -> Dict[str, Any]:
        endpoint = f"/accounts/{self.config.account_id}/summary"
        return self._make_request("GET", endpoint)

    def get_account_details(self) -> Dict[str, Any]:
        endpoint = f"/accounts/{self.config.account_id}"
        return self._make_request("GET", endpoint)

    def get_account_changes(self, since_transaction_id: str) -> Dict[str, Any]:
        endpoint = f"/accounts/{self.config.account_id}/changes"
        params = {"sinceTransactionID": str(since_transaction_id)}
        return self._make_request("GET", endpoint, params=params)

    def get_open_trades(self) -> list:
        endpoint = f"/accounts/{self.config.account_id}/openTrades"
        result = self._make_request("GET", endpoint)
        return result.get("trades", [])

    def get_trade(self, trade_id: str) -> Dict[str, Any]:
        endpoint = f"/accounts/{self.config.account_id}/trades/{trade_id}"
        return self._make_request("GET", endpoint)

    def close_trade(self, trade_id: str, units: str = "ALL") -> Dict[str, Any]:
        endpoint = f"/accounts/{self.config.account_id}/trades/{trade_id}/close"
        data = {"units": str(units)}
        return self._make_request("PUT", endpoint, data=data)

    def partial_close_trade(self, trade_id: str, units: int) -> Dict[str, Any]:
        return self.close_trade(trade_id, units=str(abs(int(units))))

    def create_market_order(
        self,
        instrument: str,
        units: int,
        stop_loss: Optional[float] = None,
        take_profit: Optional[float] = None,
        trailing_stop_distance: Optional[float] = None,
    ) -> Dict[str, Any]:
        endpoint = f"/accounts/{self.config.account_id}/orders"
        order: Dict[str, Any] = {
            "type": "MARKET",
            "instrument": instrument,
            "units": str(units),
            "timeInForce": "FOK",
            "positionFill": "DEFAULT",
        }

        if stop_loss is not None:
            order["stopLossOnFill"] = {
                "price": str(stop_loss),
                "timeInForce": "GTC",
            }

        if take_profit is not None:
            order["takeProfitOnFill"] = {
                "price": str(take_profit),
                "timeInForce": "GTC",
            }

        if trailing_stop_distance is not None:
            order["trailingStopLossOnFill"] = {
                "distance": str(trailing_stop_distance),
                "timeInForce": "GTC",
            }

        return self._make_request("POST", endpoint, data={"order": order})

    def create_limit_order(
        self,
        instrument: str,
        units: int,
        price: float,
        stop_loss: Optional[float] = None,
        take_profit: Optional[float] = None,
    ) -> Dict[str, Any]:
        endpoint = f"/accounts/{self.config.account_id}/orders"
        order: Dict[str, Any] = {
            "type": "LIMIT",
            "instrument": instrument,
            "units": str(units),
            "price": str(price),
            "timeInForce": "GTC",
            "positionFill": "DEFAULT",
        }

        if stop_loss is not None:
            order["stopLossOnFill"] = {
                "price": str(stop_loss),
                "timeInForce": "GTC",
            }

        if take_profit is not None:
            order["takeProfitOnFill"] = {
                "price": str(take_profit),
                "timeInForce": "GTC",
            }

        return self._make_request("POST", endpoint, data={"order": order})

    def create_stop_order(
        self,
        instrument: str,
        units: int,
        price: float,
        stop_loss: Optional[float] = None,
        take_profit: Optional[float] = None,
    ) -> Dict[str, Any]:
        endpoint = f"/accounts/{self.config.account_id}/orders"
        order: Dict[str, Any] = {
            "type": "STOP",
            "instrument": instrument,
            "units": str(units),
            "price": str(price),
            "timeInForce": "GTC",
            "positionFill": "DEFAULT",
        }

        if stop_loss is not None:
            order["stopLossOnFill"] = {
                "price": str(stop_loss),
                "timeInForce": "GTC",
            }

        if take_profit is not None:
            order["takeProfitOnFill"] = {
                "price": str(take_profit),
                "timeInForce": "GTC",
            }

        return self._make_request("POST", endpoint, data={"order": order})

    def set_trade_stop_loss(self, trade_id: str, price: float) -> Dict[str, Any]:
        endpoint = f"/accounts/{self.config.account_id}/trades/{trade_id}/orders"
        data = {
            "stopLoss": {
                "price": str(price),
                "timeInForce": "GTC",
            }
        }
        return self._make_request("PUT", endpoint, data=data)

    def modify_trade_stop_loss(self, trade_id: str, price: float) -> Dict[str, Any]:
        return self.set_trade_stop_loss(trade_id, price)

    def set_trade_take_profit(self, trade_id: str, price: float) -> Dict[str, Any]:
        endpoint = f"/accounts/{self.config.account_id}/trades/{trade_id}/orders"
        data = {
            "takeProfit": {
                "price": str(price),
                "timeInForce": "GTC",
            }
        }
        return self._make_request("PUT", endpoint, data=data)

    def set_trade_trailing_stop(self, trade_id: str, distance: float) -> Dict[str, Any]:
        endpoint = f"/accounts/{self.config.account_id}/trades/{trade_id}/orders"
        data = {
            "trailingStopLoss": {
                "distance": str(distance),
                "timeInForce": "GTC",
            }
        }
        return self._make_request("PUT", endpoint, data=data)

    def get_transactions_since_id(self, last_transaction_id: str) -> Dict[str, Any]:
        endpoint = f"/accounts/{self.config.account_id}/transactions/sinceid"
        params = {"id": str(last_transaction_id)}
        return self._make_request("GET", endpoint, params=params)

    def get_transactions_range(self, from_id: str, to_id: str) -> Dict[str, Any]:
        endpoint = f"/accounts/{self.config.account_id}/transactions/idrange"
        params = {"from": str(from_id), "to": str(to_id)}
        return self._make_request("GET", endpoint, params=params)

    def get_transactions(
        self,
        from_time: Optional[str] = None,
        to_time: Optional[str] = None,
        page_size: int = 100,
    ) -> Dict[str, Any]:
        endpoint = f"/accounts/{self.config.account_id}/transactions"
        params: Dict[str, Any] = {"pageSize": page_size}
        if from_time:
            params["from"] = from_time
        if to_time:
            params["to"] = to_time
        return self._make_request("GET", endpoint, params=params)

    def get_candles(
        self,
        instrument: str,
        granularity: str = "M5",
        count: int = 500,
        from_time: Optional[str] = None,
        to_time: Optional[str] = None,
        price: str = "M",
    ) -> list:
        endpoint = f"/instruments/{instrument}/candles"
        params: Dict[str, Any] = {
            "granularity": granularity,
            "price": price,
        }

        if from_time:
            params["from"] = from_time
        if to_time:
            params["to"] = to_time
        if not from_time and not to_time:
            params["count"] = count

        result = self._make_request("GET", endpoint, params=params)
        return result.get("candles", [])