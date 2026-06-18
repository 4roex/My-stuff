"""Fast interactive candlestick chart widget using PyQtGraph."""
from typing import Optional

import math
import numpy as np
import pandas as pd
import pyqtgraph as pg

from PySide6.QtCore import Qt, QPointF
from PySide6.QtGui import QColor
from PySide6.QtWidgets import QWidget, QVBoxLayout, QLabel


class CandlestickItem(pg.GraphicsObject):
    def __init__(self):
        super().__init__()
        self.data = []
        self.picture = None

    def set_data(self, data):
        self.data = data
        self._generate_picture()
        self.update()

    def _generate_picture(self):
        self.picture = pg.QtGui.QPicture()
        painter = pg.QtGui.QPainter(self.picture)

        bull_brush = pg.mkBrush(QColor("#2ecc71"))
        bear_brush = pg.mkBrush(QColor("#e74c3c"))
        bull_pen = pg.mkPen(QColor("#2ecc71"), width=1)
        bear_pen = pg.mkPen(QColor("#e74c3c"), width=1)

        if not self.data:
            painter.end()
            return

        w = 0.35
        for row in self.data:
            x, open_, high, low, close = row[:5]
            bull = close >= open_
            pen = bull_pen if bull else bear_pen
            brush = bull_brush if bull else bear_brush

            painter.setPen(pen)
            painter.drawLine(QPointF(x, low), QPointF(x, high))

            top = max(open_, close)
            bottom = min(open_, close)
            rect = pg.QtCore.QRectF(x - w, bottom, w * 2, max(top - bottom, 1e-8))
            painter.setBrush(brush)
            painter.drawRect(rect)

        painter.end()

    def paint(self, painter, *args):
        if self.picture:
            painter.drawPicture(0, 0, self.picture)

    def boundingRect(self):
        if self.picture:
            return self.picture.boundingRect()
        return pg.QtCore.QRectF()


class InteractiveChartWidget(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.df: Optional[pd.DataFrame] = None
        self.instrument = ""
        self.timeframe = ""

        self._build_ui()
        self._setup_plot()

    def _build_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(6)

        self.info_label = QLabel("Move cursor over chart for OHLC details")
        self.info_label.setStyleSheet(
            "background-color: #111827; color: #e5e7eb; padding: 6px 10px; border-radius: 6px;"
        )
        layout.addWidget(self.info_label)

        self.plot_widget = pg.GraphicsLayoutWidget()
        self.plot_widget.setBackground("#1a1a2e")
        layout.addWidget(self.plot_widget, stretch=1)

    def _setup_plot(self):
        pg.setConfigOptions(antialias=False)

        self.price_plot = self.plot_widget.addPlot(row=0, col=0)
        self.price_plot.showGrid(x=True, y=True, alpha=0.15)
        self.price_plot.setMenuEnabled(False)
        self.price_plot.hideButtons()
        self.price_plot.getAxis("left").setTextPen("#aaaaaa")
        self.price_plot.getAxis("bottom").setTextPen("#aaaaaa")
        self.price_plot.getViewBox().setMouseEnabled(x=True, y=True)
        self.price_plot.getViewBox().setDefaultPadding(0.02)

        self.plot_widget.nextRow()

        self.volume_plot = self.plot_widget.addPlot(row=1, col=0)
        self.volume_plot.showGrid(x=True, y=True, alpha=0.10)
        self.volume_plot.setMaximumHeight(140)
        self.volume_plot.setXLink(self.price_plot)
        self.volume_plot.setMenuEnabled(False)
        self.volume_plot.hideButtons()
        self.volume_plot.getAxis("left").setTextPen("#aaaaaa")
        self.volume_plot.getAxis("bottom").setTextPen("#aaaaaa")
        self.volume_plot.getViewBox().setMouseEnabled(x=True, y=False)
        self.volume_plot.getViewBox().setDefaultPadding(0.02)

        self.candle_item = CandlestickItem()
        self.price_plot.addItem(self.candle_item)

        self.ema20_curve = self.price_plot.plot([], [], pen=pg.mkPen("#f1c40f", width=1.2), name="EMA20")
        self.ema50_curve = self.price_plot.plot([], [], pen=pg.mkPen("#3498db", width=1.2), name="EMA50")

        self.volume_bars = pg.BarGraphItem(x=[], height=[], width=0.7, brushes=[])
        self.volume_plot.addItem(self.volume_bars)

        self.vline = pg.InfiniteLine(angle=90, movable=False, pen=pg.mkPen("#9ca3af", width=1))
        self.hline = pg.InfiniteLine(angle=0, movable=False, pen=pg.mkPen("#9ca3af", width=1))
        self.price_plot.addItem(self.vline, ignoreBounds=True)
        self.price_plot.addItem(self.hline, ignoreBounds=True)

        self.proxy = pg.SignalProxy(
            self.price_plot.scene().sigMouseMoved,
            rateLimit=60,
            slot=self._on_mouse_moved
        )

    def set_data(self, df: pd.DataFrame, instrument: str = "", timeframe: str = ""):
        if df is None or df.empty:
            self.clear()
            return

        self.df = df.reset_index(drop=False).copy()
        self.instrument = instrument
        self.timeframe = timeframe

        x = np.arange(len(self.df), dtype=float)

        candles = []
        for i, row in self.df.iterrows():
            candles.append((
                float(i),
                float(row["open"]),
                float(row["high"]),
                float(row["low"]),
                float(row["close"]),
            ))
        self.candle_item.set_data(candles)

        if "ema_20" in self.df.columns:
            self.ema20_curve.setData(x, self.df["ema_20"].astype(float).values)
        else:
            self.ema20_curve.setData([], [])

        if "ema_50" in self.df.columns:
            self.ema50_curve.setData(x, self.df["ema_50"].astype(float).values)
        else:
            self.ema50_curve.setData([], [])

        if "volume" in self.df.columns:
            brushes = []
            for _, row in self.df.iterrows():
                brushes.append("#2ecc71" if float(row["close"]) >= float(row["open"]) else "#e74c3c")

            self.volume_plot.clear()
            self.volume_plot.addItem(self.volume_bars)
            self.volume_bars = pg.BarGraphItem(
                x=x,
                height=self.df["volume"].fillna(0).astype(float).values,
                width=0.7,
                brushes=brushes
            )
            self.volume_plot.addItem(self.volume_bars)

        lows = self.df["low"].astype(float).values
        highs = self.df["high"].astype(float).values
        self.price_plot.setXRange(max(0, len(self.df) - 100), len(self.df) + 1, padding=0)
        self.price_plot.setYRange(float(np.min(lows)), float(np.max(highs)), padding=0.02)

        title = instrument
        if timeframe:
            title = f"{title} - {timeframe}"
        self.price_plot.setTitle(title, color="#ffffff", size="11pt")

        self.info_label.setText("Move cursor over chart for OHLC details")

    def clear(self):
        self.df = None
        self.candle_item.set_data([])
        self.ema20_curve.setData([], [])
        self.ema50_curve.setData([], [])
        self.volume_plot.clear()
        self.info_label.setText("No chart data")

    def _on_mouse_moved(self, evt):
        if self.df is None or self.df.empty:
            return

        pos = evt[0]
        if not self.price_plot.sceneBoundingRect().contains(pos):
            return

        mouse_point = self.price_plot.getViewBox().mapSceneToView(pos)
        x_val = mouse_point.x()
        y_val = mouse_point.y()

        idx = int(round(x_val))
        idx = max(0, min(idx, len(self.df) - 1))

        self.vline.setPos(idx)
        self.hline.setPos(y_val)

        row = self.df.iloc[idx]

        ts = ""
        if "time" in self.df.columns:
            ts = str(row.get("time", ""))
        elif "timestamp" in self.df.columns:
            ts = str(row.get("timestamp", ""))
        elif self.df.index.name:
            ts = str(row.get(self.df.index.name, ""))
        elif len(self.df.columns) > 0:
            first_col = self.df.columns[0]
            if "date" in str(first_col).lower() or "time" in str(first_col).lower():
                ts = str(row.get(first_col, ""))

        open_ = float(row["open"])
        high = float(row["high"])
        low = float(row["low"])
        close = float(row["close"])
        volume = float(row["volume"]) if "volume" in self.df.columns and not pd.isna(row["volume"]) else 0.0

        ema20 = row["ema_20"] if "ema_20" in self.df.columns else None
        ema50 = row["ema_50"] if "ema_50" in self.df.columns else None

        parts = [
            f"{self.instrument} {self.timeframe}".strip(),
            f"Index: {idx}",
            f"O: {open_:.5f}",
            f"H: {high:.5f}",
            f"L: {low:.5f}",
            f"C: {close:.5f}",
            f"V: {volume:,.0f}",
        ]

        if ts:
            parts.insert(1, f"T: {ts}")

        if ema20 is not None and not pd.isna(ema20):
            parts.append(f"EMA20: {float(ema20):.5f}")
        if ema50 is not None and not pd.isna(ema50):
            parts.append(f"EMA50: {float(ema50):.5f}")

        self.info_label.setText(" | ".join(parts))