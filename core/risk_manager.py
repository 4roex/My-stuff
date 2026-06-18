"""Risk management: drawdown protection, position sizing, cooldown, volatility filters."""
import time
from datetime import datetime, timedelta
from typing import Dict, Any, Optional, List
from dataclasses import dataclass


@dataclass
class RiskConfig:
    """Risk management configuration."""
    max_risk_percent: float = 1.0
    daily_drawdown_limit: float = 5.0
    total_drawdown_limit: float = 10.0
    cooldown_minutes: int = 15
    max_spread_pips: float = 5.0
    max_correlated_pairs: int = 3
    volatility_spike_reduction: float = 0.5


class RiskManager:
    """Manages trading risk and account protection."""
    
    def __init__(self, config: RiskConfig):
        self.config = config
        self.daily_start_balance: Optional[float] = None
        self.total_start_balance: Optional[float] = None
        self.last_stop_loss_time: Optional[datetime] = None
        self.trade_history: List[Dict[str, Any]] = []
        self.circuit_breaker_active: bool = False
        self.circuit_breaker_reason: str = ""
    
    def initialize_balance(self, balance: float):
        """Set starting balances for drawdown tracking."""
        if self.daily_start_balance is None:
            self.daily_start_balance = balance
        if self.total_start_balance is None:
            self.total_start_balance = balance
    
    def reset_daily_balance(self, balance: float):
        """Reset daily tracking (call at midnight or new trading day)."""
        self.daily_start_balance = balance
    
    def check_drawdown(self, current_balance: float) -> Dict[str, Any]:
        """Check if drawdown limits are breached."""
        if self.daily_start_balance is None or self.total_start_balance is None:
            return {"allowed": True, "reason": "Not initialized"}
        
        daily_dd = ((self.daily_start_balance - current_balance) / self.daily_start_balance) * 100
        total_dd = ((self.total_start_balance - current_balance) / self.total_start_balance) * 100
        
        if daily_dd >= self.config.daily_drawdown_limit:
            self.circuit_breaker_active = True
            self.circuit_breaker_reason = f"Daily drawdown {daily_dd:.2f}% >= {self.config.daily_drawdown_limit}%"
            return {"allowed": False, "reason": self.circuit_breaker_reason}
        
        if total_dd >= self.config.total_drawdown_limit:
            self.circuit_breaker_active = True
            self.circuit_breaker_reason = f"Total drawdown {total_dd:.2f}% >= {self.config.total_drawdown_limit}%"
            return {"allowed": False, "reason": self.circuit_breaker_reason}
        
        self.circuit_breaker_active = False
        return {"allowed": True, "daily_dd": daily_dd, "total_dd": total_dd}
    
    def check_cooldown(self) -> Dict[str, Any]:
        """Check if cooldown period is active after stop-loss."""
        if self.last_stop_loss_time is None:
            return {"allowed": True}
        
        elapsed = datetime.utcnow() - self.last_stop_loss_time
        minutes_elapsed = elapsed.total_seconds() / 60
        
        if minutes_elapsed < self.config.cooldown_minutes:
            remaining = self.config.cooldown_minutes - minutes_elapsed
            return {"allowed": False, "reason": f"Cooldown: {remaining:.1f} min remaining"}
        
        return {"allowed": True}
    
    def check_spread(self, spread_pips: float) -> Dict[str, Any]:
        """Check if spread is acceptable."""
        if spread_pips > self.config.max_spread_pips:
            return {"allowed": False, "reason": f"Spread {spread_pips:.1f}pips > max {self.config.max_spread_pips}pips"}
        return {"allowed": True}
    
    def check_correlation(self, open_trades: List[Dict], new_instrument: str) -> Dict[str, Any]:
        """Check correlation limits."""
        correlated = 0
        for trade in open_trades:
            existing = trade.get("instrument", "")
            if (existing[:3] == new_instrument[:3]) or (existing[4:] == new_instrument[4:]):
                correlated += 1
        
        if correlated >= self.config.max_correlated_pairs:
            return {"allowed": False, "reason": f"Max correlated pairs ({self.config.max_correlated_pairs}) reached"}
        return {"allowed": True, "correlated_count": correlated}
    
    def calculate_position_size(
        self,
        balance: float,
        risk_percent: float,
        entry_price: float,
        stop_loss: float,
        instrument: str
    ) -> Dict[str, Any]:
        """Calculate position size in units based on risk."""
        risk_amount = balance * (risk_percent / 100)
        price_risk = abs(entry_price - stop_loss)
        
        if price_risk == 0:
            return {"allowed": False, "reason": "Invalid stop loss (same as entry)"}
        
        units = int(risk_amount / price_risk)
        
        return {
            "allowed": True,
            "units": units,
            "risk_amount": risk_amount,
            "price_risk": price_risk
        }
    
    def apply_volatility_filter(
        self,
        base_size: int,
        atr_current: float,
        atr_average: float
    ) -> int:
        """Reduce position size if volatility is spiking."""
        if atr_average == 0:
            return base_size
        
        atr_ratio = atr_current / atr_average
        
        if atr_ratio > 2.0:
            return int(base_size * self.config.volatility_spike_reduction)
        elif atr_ratio > 1.5:
            return int(base_size * 0.75)
        
        return base_size
    
    def register_stop_loss(self):
        """Register a stop-loss hit to trigger cooldown."""
        self.last_stop_loss_time = datetime.utcnow()
    
    def can_trade(
        self,
        balance: float,
        spread_pips: float,
        open_trades: List[Dict],
        new_instrument: str
    ) -> Dict[str, Any]:
        """Master check - runs all risk filters."""
        self.initialize_balance(balance)
        
        dd_check = self.check_drawdown(balance)
        if not dd_check["allowed"]:
            return dd_check
        
        cd_check = self.check_cooldown()
        if not cd_check["allowed"]:
            return cd_check
        
        spread_check = self.check_spread(spread_pips)
        if not spread_check["allowed"]:
            return spread_check
        
        corr_check = self.check_correlation(open_trades, new_instrument)
        if not corr_check["allowed"]:
            return corr_check
        
        return {"allowed": True, "daily_dd": dd_check.get("daily_dd", 0), "total_dd": dd_check.get("total_dd", 0)}