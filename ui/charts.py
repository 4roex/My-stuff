"""Plotly chart generation for forex candlesticks and indicators."""
import json
from pathlib import Path
from typing import List, Dict, Any, Optional
from datetime import datetime

import plotly.graph_objects as go
from plotly.subplots import make_subplots
import pandas as pd


class ChartGenerator:
    """Generates candlestick charts with indicator overlays."""
    
    def __init__(self, output_dir: str = "output/charts"):
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)
    
    def _prepare_df(self, df: pd.DataFrame) -> pd.DataFrame:
        """Convert index to strings so Plotly can serialize it."""
        df = df.copy()
        if isinstance(df.index, pd.DatetimeIndex):
            df.index = df.index.strftime("%Y-%m-%d %H:%M:%S")
        else:
            df.index = df.index.astype(str)
        return df
    
    def create_candlestick_chart(
        self,
        df: pd.DataFrame,
        instrument: str,
        indicators: Optional[List[str]] = None,
        width: int = 900,
        height: int = 500
    ) -> str:
        """Generate candlestick chart with overlays and save as PNG."""
        
        df = self._prepare_df(df)
        
        fig = make_subplots(
            rows=2, cols=1,
            shared_xaxes=True,
            vertical_spacing=0.03,
            row_heights=[0.75, 0.25],
            subplot_titles=(f"{instrument} Price", "Volume")
        )
        
        # Candlesticks
        fig.add_trace(
            go.Candlestick(
                x=df.index,
                open=df["open"],
                high=df["high"],
                low=df["low"],
                close=df["close"],
                name="Price"
            ),
            row=1, col=1
        )
        
        # EMA overlays
        if indicators:
            for ind in indicators:
                if ind in df.columns:
                    fig.add_trace(
                        go.Scatter(
                            x=df.index,
                            y=df[ind],
                            mode="lines",
                            name=ind.upper(),
                            line=dict(width=1)
                        ),
                        row=1, col=1
                    )
        
        # Bollinger Bands
        if "bb_upper" in df.columns and "bb_lower" in df.columns:
            fig.add_trace(
                go.Scatter(
                    x=df.index,
                    y=df["bb_upper"],
                    mode="lines",
                    name="BB Upper",
                    line=dict(width=1, color="rgba(255,0,0,0.3)")
                ),
                row=1, col=1
            )
            fig.add_trace(
                go.Scatter(
                    x=df.index,
                    y=df["bb_lower"],
                    mode="lines",
                    name="BB Lower",
                    line=dict(width=1, color="rgba(255,0,0,0.3)")
                ),
                row=1, col=1
            )
        
        # Volume
        if "volume" in df.columns:
            colors = ["green" if df["close"].iloc[i] >= df["open"].iloc[i] else "red" for i in range(len(df))]
            fig.add_trace(
                go.Bar(
                    x=df.index,
                    y=df["volume"],
                    marker_color=colors,
                    name="Volume"
                ),
                row=2, col=1
            )
        
        fig.update_layout(
            title=f"{instrument} - {datetime.now().strftime('%H:%M:%S')}",
            xaxis_rangeslider_visible=False,
            template="plotly_dark",
            width=width,
            height=height,
            showlegend=True,
            legend=dict(orientation="h", yanchor="bottom", y=1.02)
        )
        
        fig.update_yaxes(title_text="Price", row=1, col=1)
        fig.update_yaxes(title_text="Volume", row=2, col=1)
        fig.update_xaxes(title_text="Time", row=2, col=1)
        
        # Save
        filename = f"{instrument}_{datetime.now().strftime('%H%M%S')}.png"
        filepath = self.output_dir / filename
        fig.write_image(str(filepath), scale=1)
        
        return str(filepath)
    
    def create_indicator_chart(
        self,
        df: pd.DataFrame,
        instrument: str,
        width: int = 400,
        height: int = 300
    ) -> str:
        """Generate RSI/MACD indicator chart."""
        
        df = self._prepare_df(df)
        
        fig = make_subplots(
            rows=2, cols=1,
            shared_xaxes=True,
            vertical_spacing=0.1,
            row_heights=[0.5, 0.5],
            subplot_titles=("RSI", "MACD")
        )
        
        if "rsi_14" in df.columns:
            fig.add_trace(
                go.Scatter(x=df.index, y=df["rsi_14"], mode="lines", name="RSI", line=dict(color="purple")),
                row=1, col=1
            )
            fig.add_hline(y=70, line_dash="dash", line_color="red", row=1, col=1)
            fig.add_hline(y=30, line_dash="dash", line_color="green", row=1, col=1)
        
        if "macd" in df.columns and "macd_signal" in df.columns:
            fig.add_trace(
                go.Scatter(x=df.index, y=df["macd"], mode="lines", name="MACD", line=dict(color="blue")),
                row=2, col=1
            )
            fig.add_trace(
                go.Scatter(x=df.index, y=df["macd_signal"], mode="lines", name="Signal", line=dict(color="orange")),
                row=2, col=1
            )
            if "macd_hist" in df.columns:
                colors = ["green" if v >= 0 else "red" for v in df["macd_hist"]]
                fig.add_trace(
                    go.Bar(x=df.index, y=df["macd_hist"], marker_color=colors, name="Hist"),
                    row=2, col=1
                )
        
        fig.update_layout(
            title=f"{instrument} Indicators",
            template="plotly_dark",
            width=width,
            height=height,
            showlegend=True
        )
        
        filename = f"{instrument}_ind_{datetime.now().strftime('%H%M%S')}.png"
        filepath = self.output_dir / filename
        fig.write_image(str(filepath), scale=2)
        
        return str(filepath)
    
    def cleanup_old_charts(self, max_files: int = 50):
        """Remove old chart PNGs to save disk space."""
        files = sorted(self.output_dir.glob("*.png"), key=lambda p: p.stat().st_mtime, reverse=True)
        for old in files[max_files:]:
            old.unlink()