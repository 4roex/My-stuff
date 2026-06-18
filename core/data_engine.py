"""Data engine for fetching, caching, and processing forex data."""
import os
import json
import sqlite3
import time
from datetime import datetime, timedelta
from typing import List, Dict, Any, Optional
from pathlib import Path

import pandas as pd
import numpy as np

from core.oanda_client import OandaClient, OandaConfig
from core.indicators import calculate_all_indicators, get_latest_signals


class DataEngine:
    """Handles historical data caching, real-time streaming, and indicator calculation."""
    
    def __init__(self, client: OandaClient, data_dir: str = "data"):
        self.client = client
        self.data_dir = Path(data_dir)
        self.data_dir.mkdir(exist_ok=True)
        
        self.cache_db = self.data_dir / "forex_cache.db"
        self._init_db()
        
        self.price_buffer: Dict[str, List[Dict]] = {}
        self.max_buffer_size = 1000
    
    def _init_db(self):
        """Initialize SQLite cache database."""
        with sqlite3.connect(self.cache_db) as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS candles (
                    instrument TEXT,
                    granularity TEXT,
                    time TEXT,
                    open REAL,
                    high REAL,
                    low REAL,
                    close REAL,
                    volume INTEGER,
                    PRIMARY KEY (instrument, granularity, time)
                )
            """)
            conn.execute("""
                CREATE TABLE IF NOT EXISTS price_cache_meta (
                    instrument TEXT,
                    granularity TEXT,
                    last_fetch TEXT,
                    count INTEGER,
                    PRIMARY KEY (instrument, granularity)
                )
            """)
            conn.commit()
    
    def fetch_historical_data(
        self,
        instrument: str,
        granularity: str = "M1",
        count: int = 500,
        from_time: Optional[str] = None,
        to_time: Optional[str] = None,
        use_cache: bool = True
    ) -> pd.DataFrame:
        """Fetch historical candles with SQLite caching."""
        
        if use_cache:
            cached = self._load_from_cache(instrument, granularity, count)
            if len(cached) >= count:
                return cached.tail(count)
        
        print(f"Fetching {count} candles for {instrument} ({granularity}) from Oanda...")
        candles = self.client.get_candles(
            instrument=instrument,
            granularity=granularity,
            count=count,
            from_time=from_time,
            to_time=to_time
        )
        
        if not candles:
            return pd.DataFrame()
        
        df = self._candles_to_dataframe(candles)
        
        if use_cache:
            self._save_to_cache(instrument, granularity, df)
        
        return df
    
    def _candles_to_dataframe(self, candles: List[Dict]) -> pd.DataFrame:
        """Convert Oanda candle format to pandas DataFrame."""
        records = []
        for c in candles:
            if not c["complete"]:
                continue
            records.append({
                "time": c["time"],
                "open": float(c["mid"]["o"]),
                "high": float(c["mid"]["h"]),
                "low": float(c["mid"]["l"]),
                "close": float(c["mid"]["c"]),
                "volume": int(c["volume"])
            })
        
        df = pd.DataFrame(records)
        df["time"] = pd.to_datetime(df["time"])
        df.set_index("time", inplace=True)
        return df
    
    def _load_from_cache(
        self,
        instrument: str,
        granularity: str,
        count: int
    ) -> pd.DataFrame:
        """Load candles from SQLite cache."""
        with sqlite3.connect(self.cache_db) as conn:
            query = """
                SELECT time, open, high, low, close, volume
                FROM candles
                WHERE instrument = ? AND granularity = ?
                ORDER BY time DESC
                LIMIT ?
            """
            df = pd.read_sql_query(query, conn, params=(instrument, granularity, count))
        
        if df.empty:
            return df
        
        df["time"] = pd.to_datetime(df["time"])
        df.set_index("time", inplace=True)
        return df.sort_index()
    
    def _save_to_cache(self, instrument: str, granularity: str, df: pd.DataFrame):
        """Save candles to SQLite cache."""
        with sqlite3.connect(self.cache_db) as conn:
            for idx, row in df.iterrows():
                conn.execute("""
                    INSERT OR REPLACE INTO candles
                    (instrument, granularity, time, open, high, low, close, volume)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    instrument, granularity,
                    idx.isoformat(),
                    row["open"], row["high"], row["low"], row["close"], row["volume"]
                ))
            
            conn.execute("""
                INSERT OR REPLACE INTO price_cache_meta
                (instrument, granularity, last_fetch, count)
                VALUES (?, ?, ?, ?)
            """, (
                instrument, granularity,
                datetime.utcnow().isoformat(),
                len(df)
            ))
            conn.commit()
    
    def get_data_with_indicators(
        self,
        instrument: str,
        granularity: str = "M5",
        count: int = 200
    ) -> pd.DataFrame:
        """Get historical data with all technical indicators calculated."""
        df = self.fetch_historical_data(instrument, granularity, count)
        if df.empty:
            return df
        return calculate_all_indicators(df)
    
    def get_latest_market_snapshot(self, instrument: str, granularity: str = "M5") -> Dict[str, Any]:
        """Get latest price + indicators for LLM decision."""
        df = self.get_data_with_indicators(instrument, granularity, count=200)
        if df.empty:
            return {}
        
        latest = df.iloc[-1]
        signals = get_latest_signals(df)
        
        snapshot = {
            "instrument": instrument,
            "timeframe": granularity,
            "timestamp": latest.name.isoformat(),
            "price": {
                "open": round(latest["open"], 5),
                "high": round(latest["high"], 5),
                "low": round(latest["low"], 5),
                "close": round(latest["close"], 5)
            },
            "indicators": {
                "ema_20": round(latest["ema_20"], 5),
                "ema_50": round(latest["ema_50"], 5),
                "ema_200": round(latest["ema_200"], 5),
                "rsi_14": round(latest["rsi_14"], 2),
                "macd": round(latest["macd"], 5),
                "macd_signal": round(latest["macd_signal"], 5),
                "atr_14": round(latest["atr_14"], 5),
                "bb_upper": round(latest["bb_upper"], 5),
                "bb_lower": round(latest["bb_lower"], 5),
                "stoch_k": round(latest["stoch_k"], 2),
                "adx_14": round(latest["adx_14"], 2)
            },
            "signals": signals
        }
        
        return snapshot
    
    def get_multi_pair_snapshot(
        self,
        instruments: List[str],
        granularity: str = "M5"
    ) -> Dict[str, Dict[str, Any]]:
        """Get snapshots for multiple currency pairs."""
        return {
            inst: self.get_latest_market_snapshot(inst, granularity)
            for inst in instruments
        }
    
    def clear_cache(self, instrument: Optional[str] = None):
        """Clear cached data."""
        with sqlite3.connect(self.cache_db) as conn:
            if instrument:
                conn.execute("DELETE FROM candles WHERE instrument = ?", (instrument,))
                conn.execute("DELETE FROM price_cache_meta WHERE instrument = ?", (instrument,))
            else:
                conn.execute("DELETE FROM candles")
                conn.execute("DELETE FROM price_cache_meta")
            conn.commit()
        print(f"Cache cleared{' for ' + instrument if instrument else ''}")