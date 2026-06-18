"""Matplotlib chart generation - no Kaleido required, sharper rendering."""
import matplotlib
matplotlib.use("Agg")

import matplotlib.pyplot as plt
from pathlib import Path
from typing import List, Optional, Dict, Any
from datetime import datetime
import pandas as pd


class ChartGenerator:
    def __init__(self, output_dir: str = "output/charts"):
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)
        plt.style.use("dark_background")
        plt.rcParams["figure.dpi"] = 150
        plt.rcParams["savefig.dpi"] = 150

    def create_candlestick_chart(
        self,
        df: pd.DataFrame,
        instrument: str,
        indicators: Optional[List[str]] = None,
        width: int = 1200,
        height: int = 500
    ) -> str:
        fig_w = width / 150
        fig_h = height / 150

        fig, (ax1, ax2) = plt.subplots(
            2, 1,
            figsize=(fig_w, fig_h),
            gridspec_kw={"height_ratios": [3, 1]},
            sharex=True
        )
        fig.patch.set_facecolor("#1a1a2e")
        ax1.set_facecolor("#1a1a2e")
        ax2.set_facecolor("#1a1a2e")

        x = range(len(df))

        for i, (_, row) in enumerate(df.iterrows()):
            color = "#2ecc71" if row["close"] >= row["open"] else "#e74c3c"
            ax1.plot([i, i], [row["low"], row["high"]], color=color, linewidth=1, solid_capstyle="round")
            ax1.bar(i, row["close"] - row["open"], bottom=row["open"], color=color, width=0.65, zorder=3)

        if indicators:
            for ind in indicators:
                if ind in df.columns:
                    ax1.plot(x, df[ind].values, label=ind.upper(), linewidth=1.2, alpha=0.85)

        if "bb_upper" in df.columns and "bb_lower" in df.columns:
            ax1.plot(x, df["bb_upper"].values, color="#ff5050", alpha=0.4, linewidth=1, label="BB Upper")
            ax1.plot(x, df["bb_lower"].values, color="#ff5050", alpha=0.4, linewidth=1, label="BB Lower")

        ax1.set_title(f"{instrument} {datetime.now().strftime('%H:%M:%S')}", fontsize=11, color="white", pad=10)

        handles, labels = ax1.get_legend_handles_labels()
        if handles:
            ax1.legend(loc="upper left", fontsize=7, facecolor="#1a1a2e", edgecolor="#444")

        ax1.set_ylabel("Price", fontsize=9, color="#aaa")
        ax1.tick_params(colors="#aaa", labelsize=7)
        ax1.grid(True, alpha=0.15, color="#555")
        ax1.spines["top"].set_visible(False)
        ax1.spines["right"].set_visible(False)

        if "volume" in df.columns:
            colors = [
                "#2ecc71" if df["close"].iloc[i] >= df["open"].iloc[i] else "#e74c3c"
                for i in range(len(df))
            ]
            ax2.bar(x, df["volume"], color=colors, width=0.65)
            ax2.set_ylabel("Volume", fontsize=9, color="#aaa")
            ax2.tick_params(colors="#aaa", labelsize=7)
            ax2.grid(True, alpha=0.15, color="#555")
            ax2.spines["top"].set_visible(False)
            ax2.spines["right"].set_visible(False)

        plt.tight_layout()

        safe_name = instrument.replace("/", "_")
        filename = f"{safe_name}_{datetime.now().strftime('%H%M%S')}.png"
        filepath = self.output_dir / filename

        plt.savefig(filepath, bbox_inches="tight", facecolor="#1a1a2e", edgecolor="none")
        plt.close(fig)
        return str(filepath)

    def create_equity_curve_chart(
        self,
        trades: List[Dict[str, Any]],
        width: int = 600,
        height: int = 300
    ) -> str:
        if not trades:
            return ""

        fig_w = width / 150
        fig_h = height / 150

        fig, ax = plt.subplots(figsize=(fig_w, fig_h))
        fig.patch.set_facecolor("#1a1a2e")
        ax.set_facecolor("#1a1a2e")

        equity = []
        cumulative = 0.0

        def trade_sort_key(trade: Dict[str, Any]) -> str:
            return str(trade.get("timestamp", trade.get("close_time", "")))

        for t in sorted(trades, key=trade_sort_key):
            pl = float(t.get("realized_pl", t.get("realizedPL", 0)) or 0)
            cumulative += pl
            equity.append(cumulative)

        x = list(range(len(equity)))

        ax.plot(x, equity, color="#2ecc71", linewidth=1.5, alpha=0.9)
        ax.fill_between(x, equity, alpha=0.15, color="#2ecc71")
        ax.axhline(y=0, color="#555", linewidth=0.5, linestyle="--")

        ax.set_title("Equity Curve", fontsize=10, color="white", pad=8)
        ax.set_ylabel("Cumulative P&L ($)", fontsize=8, color="#aaa")
        ax.tick_params(colors="#aaa", labelsize=7)
        ax.grid(True, alpha=0.15, color="#555")
        ax.spines["top"].set_visible(False)
        ax.spines["right"].set_visible(False)

        plt.tight_layout()

        filename = f"equity_{datetime.now().strftime('%H%M%S')}.png"
        filepath = self.output_dir / filename

        plt.savefig(filepath, bbox_inches="tight", facecolor="#1a1a2e", edgecolor="none")
        plt.close(fig)
        return str(filepath)

    def create_win_loss_chart(
        self,
        wins: int,
        losses: int,
        width: int = 300,
        height: int = 300
    ) -> str:
        if wins + losses == 0:
            return ""

        fig_w = width / 150
        fig_h = height / 150

        fig, ax = plt.subplots(figsize=(fig_w, fig_h))
        fig.patch.set_facecolor("#1a1a2e")
        ax.set_facecolor("#1a1a2e")

        sizes = [wins, losses]
        colors = ["#2ecc71", "#e74c3c"]
        labels = [f"Wins\n{wins}", f"Losses\n{losses}"]
        explode = (0.02, 0.02)

        ax.pie(
            sizes,
            explode=explode,
            labels=labels,
            colors=colors,
            autopct="%1.1f%%",
            startangle=90,
            textprops={"color": "white", "fontsize": 8}
        )
        ax.set_title("Win / Loss", fontsize=10, color="white", pad=8)

        plt.tight_layout()

        filename = f"winloss_{datetime.now().strftime('%H%M%S')}.png"
        filepath = self.output_dir / filename

        plt.savefig(filepath, bbox_inches="tight", facecolor="#1a1a2e", edgecolor="none")
        plt.close(fig)
        return str(filepath)

    def create_daily_pnl_chart(
        self,
        daily_breakdown: List[Dict[str, Any]],
        width: int = 1200,
        height: int = 300
    ) -> str:
        if not daily_breakdown:
            return ""

        fig_w = width / 150
        fig_h = height / 150

        fig, ax = plt.subplots(figsize=(fig_w, fig_h))
        fig.patch.set_facecolor("#1a1a2e")
        ax.set_facecolor("#1a1a2e")

        ordered = sorted(daily_breakdown, key=lambda x: str(x.get("day", "")))
        days = [str(row.get("day", ""))[5:] for row in ordered]
        pnl_values = [float(row.get("pnl", 0) or 0) for row in ordered]
        colors = ["#2ecc71" if v >= 0 else "#e74c3c" for v in pnl_values]

        x = list(range(len(days)))
        ax.bar(x, pnl_values, color=colors, width=0.65)
        ax.axhline(y=0, color="#888", linewidth=0.8, linestyle="--")

        ax.set_title("Daily P&L", fontsize=10, color="white", pad=8)
        ax.set_ylabel("P&L ($)", fontsize=8, color="#aaa")
        ax.set_xticks(x)
        ax.set_xticklabels(days, rotation=45, ha="right", fontsize=7, color="#aaa")
        ax.tick_params(axis="y", colors="#aaa", labelsize=7)
        ax.grid(True, axis="y", alpha=0.15, color="#555")
        ax.spines["top"].set_visible(False)
        ax.spines["right"].set_visible(False)

        plt.tight_layout()

        filename = f"daily_pnl_{datetime.now().strftime('%H%M%S')}.png"
        filepath = self.output_dir / filename

        plt.savefig(filepath, bbox_inches="tight", facecolor="#1a1a2e", edgecolor="none")
        plt.close(fig)
        return str(filepath)

    def cleanup_old_charts(self, max_files: int = 50):
        files = sorted(
            self.output_dir.glob("*.png"),
            key=lambda p: p.stat().st_mtime,
            reverse=True
        )
        for old in files[max_files:]:
            old.unlink()