"""Technical indicator calculations for forex trading strategies."""
import pandas as pd
import numpy as np
from typing import List, Dict, Any


def calculate_ema(df: pd.DataFrame, period: int = 20, column: str = "close") -> pd.Series:
    """Calculate Exponential Moving Average."""
    return df[column].ewm(span=period, adjust=False).mean()


def calculate_sma(df: pd.DataFrame, period: int = 50, column: str = "close") -> pd.Series:
    """Calculate Simple Moving Average."""
    return df[column].rolling(window=period).mean()


def calculate_rsi(df: pd.DataFrame, period: int = 14, column: str = "close") -> pd.Series:
    """Calculate Relative Strength Index."""
    delta = df[column].diff()
    gain = (delta.where(delta > 0, 0)).rolling(window=period).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(window=period).mean()
    rs = gain / loss
    return 100 - (100 / (1 + rs))


def calculate_macd(
    df: pd.DataFrame,
    fast: int = 12,
    slow: int = 26,
    signal: int = 9,
    column: str = "close"
) -> Dict[str, pd.Series]:
    """Calculate MACD, Signal line, and Histogram."""
    ema_fast = df[column].ewm(span=fast, adjust=False).mean()
    ema_slow = df[column].ewm(span=slow, adjust=False).mean()
    macd_line = ema_fast - ema_slow
    signal_line = macd_line.ewm(span=signal, adjust=False).mean()
    histogram = macd_line - signal_line
    return {
        "macd": macd_line,
        "signal": signal_line,
        "histogram": histogram
    }


def calculate_atr(df: pd.DataFrame, period: int = 14) -> pd.Series:
    """Calculate Average True Range."""
    high_low = df["high"] - df["low"]
    high_close = np.abs(df["high"] - df["close"].shift())
    low_close = np.abs(df["low"] - df["close"].shift())
    tr = pd.concat([high_low, high_close, low_close], axis=1).max(axis=1)
    return tr.rolling(window=period).mean()


def calculate_bollinger_bands(
    df: pd.DataFrame,
    period: int = 20,
    std_dev: float = 2.0,
    column: str = "close"
) -> Dict[str, pd.Series]:
    """Calculate Bollinger Bands."""
    sma = df[column].rolling(window=period).mean()
    std = df[column].rolling(window=period).std()
    return {
        "middle": sma,
        "upper": sma + (std * std_dev),
        "lower": sma - (std * std_dev)
    }


def calculate_stochastic(
    df: pd.DataFrame,
    k_period: int = 14,
    d_period: int = 3
) -> Dict[str, pd.Series]:
    """Calculate Stochastic Oscillator."""
    lowest_low = df["low"].rolling(window=k_period).min()
    highest_high = df["high"].rolling(window=k_period).max()
    k = 100 * ((df["close"] - lowest_low) / (highest_high - lowest_low))
    d = k.rolling(window=d_period).mean()
    return {"k": k, "d": d}


def calculate_adx(df: pd.DataFrame, period: int = 14) -> pd.Series:
    """Calculate Average Directional Index."""
    plus_dm = df["high"].diff()
    minus_dm = df["low"].diff().abs()
    
    plus_dm = plus_dm.where((plus_dm > minus_dm) & (plus_dm > 0), 0)
    minus_dm = minus_dm.where((minus_dm > plus_dm) & (minus_dm > 0), 0)
    
    tr = pd.concat([
        df["high"] - df["low"],
        (df["high"] - df["close"].shift()).abs(),
        (df["low"] - df["close"].shift()).abs()
    ], axis=1).max(axis=1)
    
    atr = tr.rolling(window=period).mean()
    plus_di = 100 * (plus_dm.rolling(window=period).mean() / atr)
    minus_di = 100 * (minus_dm.rolling(window=period).mean() / atr)
    dx = (abs(plus_di - minus_di) / (plus_di + minus_di)) * 100
    return dx.rolling(window=period).mean()


def calculate_all_indicators(df: pd.DataFrame) -> pd.DataFrame:
    """Calculate all indicators and add to DataFrame."""
    result = df.copy()
    
    result["ema_9"] = calculate_ema(df, 9)
    result["ema_20"] = calculate_ema(df, 20)
    result["ema_50"] = calculate_ema(df, 50)
    result["ema_200"] = calculate_ema(df, 200)
    
    result["sma_50"] = calculate_sma(df, 50)
    result["sma_200"] = calculate_sma(df, 200)
    
    result["rsi_14"] = calculate_rsi(df, 14)
    
    macd = calculate_macd(df)
    result["macd"] = macd["macd"]
    result["macd_signal"] = macd["signal"]
    result["macd_hist"] = macd["histogram"]
    
    result["atr_14"] = calculate_atr(df, 14)
    
    bb = calculate_bollinger_bands(df)
    result["bb_upper"] = bb["upper"]
    result["bb_middle"] = bb["middle"]
    result["bb_lower"] = bb["lower"]
    
    stoch = calculate_stochastic(df)
    result["stoch_k"] = stoch["k"]
    result["stoch_d"] = stoch["d"]
    
    result["adx_14"] = calculate_adx(df, 14)
    
    return result


def get_latest_signals(df: pd.DataFrame) -> Dict[str, Any]:
    """Extract latest indicator values and basic signals."""
    latest = df.iloc[-1]
    
    signals = {
        "ema_crossover": "BULLISH" if latest["ema_20"] > latest["ema_50"] else "BEARISH",
        "rsi_signal": "OVERSOLD" if latest["rsi_14"] < 30 else "OVERBOUGHT" if latest["rsi_14"] > 70 else "NEUTRAL",
        "macd_signal": "BULLISH" if latest["macd"] > latest["macd_signal"] else "BEARISH",
        "bb_position": "ABOVE" if latest["close"] > latest["bb_upper"] else "BELOW" if latest["close"] < latest["bb_lower"] else "INSIDE",
        "trend": "UP" if latest["ema_50"] > latest["ema_200"] else "DOWN",
        "volatility": "HIGH" if latest["atr_14"] > df["atr_14"].rolling(20).mean().iloc[-1] else "NORMAL"
    }
    
    return signals