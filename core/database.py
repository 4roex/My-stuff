"""SQLite database for trade history, decisions, and performance analytics."""
import sqlite3
import json
from typing import Dict, Any, List, Optional
from pathlib import Path


class TradeDatabase:
    """Persistent SQLite storage for all trading activity."""

    def __init__(self, account_id: str):
        self.db_path = Path(f"data/{account_id}/trades.db")
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._init_tables()

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(str(self.db_path))
        conn.row_factory = sqlite3.Row
        return conn

    def _init_tables(self):
        with self._connect() as conn:
            conn.executescript("""
            CREATE TABLE IF NOT EXISTS trades (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp TEXT DEFAULT CURRENT_TIMESTAMP,
                trade_id TEXT,
                instrument TEXT,
                direction TEXT,
                units INTEGER,
                entry_price REAL,
                stop_loss REAL,
                take_profit REAL,
                exit_price REAL,
                realized_pl REAL,
                status TEXT DEFAULT 'OPEN',
                llm_decision TEXT,
                llm_confidence INTEGER,
                llm_reasoning TEXT
            );

            CREATE TABLE IF NOT EXISTS decisions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp TEXT DEFAULT CURRENT_TIMESTAMP,
                instrument TEXT,
                decision TEXT,
                confidence INTEGER,
                reasoning TEXT,
                metadata TEXT
            );

            CREATE TABLE IF NOT EXISTS errors (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp TEXT DEFAULT CURRENT_TIMESTAMP,
                message TEXT
            );

            CREATE TABLE IF NOT EXISTS snapshots (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp TEXT DEFAULT CURRENT_TIMESTAMP,
                instrument TEXT,
                timeframe TEXT,
                price_data TEXT,
                indicators TEXT,
                signals TEXT
            );

            CREATE TABLE IF NOT EXISTS app_settings (
                key TEXT PRIMARY KEY,
                value TEXT
            );

            CREATE INDEX IF NOT EXISTS idx_trades_instrument ON trades(instrument);
            CREATE INDEX IF NOT EXISTS idx_trades_status ON trades(status);
            CREATE INDEX IF NOT EXISTS idx_trades_trade_id ON trades(trade_id);
            CREATE INDEX IF NOT EXISTS idx_decisions_time ON decisions(timestamp);
            CREATE INDEX IF NOT EXISTS idx_errors_time ON errors(timestamp);
            """)
            conn.commit()

    def log_trade(self, trade: Dict[str, Any]):
        with self._connect() as conn:
            conn.execute("""
            INSERT INTO trades (
                trade_id, instrument, direction, units, entry_price,
                stop_loss, take_profit, llm_decision, llm_confidence, llm_reasoning
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                trade.get("trade_id"),
                trade.get("instrument"),
                trade.get("direction"),
                trade.get("units"),
                trade.get("entry_price"),
                trade.get("stop_loss"),
                trade.get("take_profit"),
                trade.get("llm_decision"),
                trade.get("llm_confidence"),
                trade.get("llm_reasoning")
            ))
            conn.commit()

    def close_trade(self, trade_id: str, exit_price: float, realized_pl: float):
        with self._connect() as conn:
            conn.execute("""
            UPDATE trades
            SET status = 'CLOSED', exit_price = ?, realized_pl = ?
            WHERE trade_id = ? AND status = 'OPEN'
            """, (exit_price, realized_pl, trade_id))
            conn.commit()

    def update_trade_close_from_broker(
        self,
        trade_id: str,
        exit_price: float,
        realized_pl: float,
    ) -> bool:
        with self._connect() as conn:
            cursor = conn.execute("""
            UPDATE trades
            SET status = 'CLOSED',
                exit_price = ?,
                realized_pl = ?
            WHERE trade_id = ?
            """, (exit_price, realized_pl, trade_id))
            conn.commit()
            return cursor.rowcount > 0

    def trade_exists(self, trade_id: str) -> bool:
        with self._connect() as conn:
            row = conn.execute(
                "SELECT 1 FROM trades WHERE trade_id = ? LIMIT 1",
                (trade_id,)
            ).fetchone()
            return row is not None

    def get_setting(self, key: str, default_value: str = "") -> str:
        with self._connect() as conn:
            row = conn.execute(
                "SELECT value FROM app_settings WHERE key = ?",
                (key,)
            ).fetchone()
            return row["value"] if row else default_value

    def set_setting(self, key: str, value: str):
        with self._connect() as conn:
            conn.execute("""
            INSERT INTO app_settings (key, value)
            VALUES (?, ?)
            ON CONFLICT(key) DO UPDATE SET value = excluded.value
            """, (key, str(value)))
            conn.commit()

    def log_decision(self, decision: Dict[str, Any]):
        with self._connect() as conn:
            conn.execute("""
            INSERT INTO decisions (instrument, decision, confidence, reasoning, metadata)
            VALUES (?, ?, ?, ?, ?)
            """, (
                decision.get("instrument"),
                decision.get("decision"),
                decision.get("confidence"),
                decision.get("reasoning"),
                json.dumps({
                    k: v for k, v in decision.items()
                    if k not in ("instrument", "decision", "confidence", "reasoning")
                })
            ))
            conn.commit()

    def log_error(self, message: str):
        with self._connect() as conn:
            conn.execute("INSERT INTO errors (message) VALUES (?)", (message,))
            conn.commit()

    def log_snapshot(self, instrument: str, timeframe: str, snapshot: Dict[str, Any]):
        with self._connect() as conn:
            conn.execute("""
            INSERT INTO snapshots (instrument, timeframe, price_data, indicators, signals)
            VALUES (?, ?, ?, ?, ?)
            """, (
                instrument,
                timeframe,
                json.dumps(snapshot.get("price", {})),
                json.dumps(snapshot.get("indicators", {})),
                json.dumps(snapshot.get("signals", {}))
            ))
            conn.commit()

    def get_open_trades(self, instrument: Optional[str] = None) -> List[Dict[str, Any]]:
        with self._connect() as conn:
            if instrument:
                rows = conn.execute(
                    "SELECT * FROM trades WHERE status = 'OPEN' AND instrument = ? ORDER BY timestamp DESC",
                    (instrument,)
                ).fetchall()
            else:
                rows = conn.execute(
                    "SELECT * FROM trades WHERE status = 'OPEN' ORDER BY timestamp DESC"
                ).fetchall()
            return [dict(r) for r in rows]

    def get_trade_history(
        self,
        limit: int = 100,
        instrument: Optional[str] = None,
        status: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        query = "SELECT * FROM trades WHERE 1=1"
        params = []

        if instrument:
            query += " AND instrument = ?"
            params.append(instrument)
        if status:
            query += " AND status = ?"
            params.append(status)

        query += " ORDER BY timestamp DESC LIMIT ?"
        params.append(limit)

        with self._connect() as conn:
            rows = conn.execute(query, params).fetchall()
            return [dict(r) for r in rows]

    def get_performance_stats(self, days: int = 30) -> Dict[str, Any]:
        with self._connect() as conn:
            rows = conn.execute("""
            SELECT realized_pl FROM trades
            WHERE status = 'CLOSED' AND timestamp >= datetime('now', '-{} days')
            """.format(days)).fetchall()

            pnl = [r["realized_pl"] for r in rows if r["realized_pl"] is not None]
            if not pnl:
                return {
                    "total_trades": 0,
                    "win_rate": 0,
                    "profit_factor": 0,
                    "avg_win": 0,
                    "avg_loss": 0,
                    "max_drawdown": 0,
                    "daily_pnl": 0,
                    "total_pnl": 0,
                }

            wins = [x for x in pnl if x > 0]
            losses = [x for x in pnl if x < 0]
            total = len(pnl)
            win_rate = (len(wins) / total * 100) if total > 0 else 0
            avg_win = sum(wins) / len(wins) if wins else 0
            avg_loss = sum(losses) / len(losses) if losses else 0
            profit_factor = abs(sum(wins) / sum(losses)) if losses else float('inf')
            total_pnl = sum(pnl)

            daily = conn.execute("""
            SELECT date(timestamp) as day, SUM(realized_pl) as pnl
            FROM trades
            WHERE status = 'CLOSED'
              AND timestamp >= datetime('now', '-{} days')
            GROUP BY day
            ORDER BY day DESC
            """.format(days)).fetchall()

            return {
                "total_trades": total,
                "win_rate": win_rate,
                "profit_factor": profit_factor if profit_factor != float('inf') else 0,
                "avg_win": avg_win,
                "avg_loss": avg_loss,
                "total_pnl": total_pnl,
                "daily_pnl": daily[0]["pnl"] if daily else 0,
                "max_drawdown": 0,
                "sharpe_ratio": 0,
                "daily_breakdown": [dict(r) for r in daily],
            }

    def get_recent_errors(self, limit: int = 20) -> List[Dict[str, Any]]:
        with self._connect() as conn:
            rows = conn.execute(
                "SELECT * FROM errors ORDER BY timestamp DESC LIMIT ?",
                (limit,)
            ).fetchall()
            return [dict(r) for r in rows]

    def get_decision_stats(self, days: int = 7) -> Dict[str, int]:
        with self._connect() as conn:
            rows = conn.execute("""
            SELECT decision, COUNT(*) as count
            FROM decisions
            WHERE timestamp >= datetime('now', '-{} days')
            GROUP BY decision
            """.format(days)).fetchall()
            return {r["decision"]: r["count"] for r in rows}

    def cleanup_old_data(self, days: int = 90):
        """Delete snapshots and errors older than X days."""
        with self._connect() as conn:
            conn.execute("DELETE FROM snapshots WHERE timestamp < datetime('now', '-{} days')".format(days))
            conn.execute("DELETE FROM errors WHERE timestamp < datetime('now', '-{} days')".format(days))
            conn.execute("DELETE FROM decisions WHERE timestamp < datetime('now', '-{} days')".format(days))
            conn.commit()