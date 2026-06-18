"""LLM client supporting Ollama, OpenAI, Anthropic, DeepSeek."""
import json
import time
from typing import Dict, Any, List, Optional
from dataclasses import dataclass
from enum import Enum

import requests


class LLMProvider(Enum):
    OLLAMA = "ollama"
    OPENAI = "openai"
    ANTHROPIC = "anthropic"
    DEEPSEEK = "deepseek"


@dataclass
class LLMTradeDecision:
    decision: str
    confidence: int
    reasoning: str
    instrument: str
    risk_percent: float
    stop_loss_pips: Optional[int] = None
    take_profit_pips: Optional[int] = None
    position_size: Optional[float] = None


class LLMClient:
    """Client for LLM-based trade decisions."""

    def __init__(self, config: Dict[str, Any]):
        self.config = config
        self.url = config.get("url", "http://localhost:11434")
        self.model = config.get("default_model", "llama3.1:8b")
        self.fallback_model = config.get("fallback_model", "llama3.2:3b")
        self.complex_model = config.get("complex_model", self.model)
        self.timeout = config.get("timeout", 30)
        self.temperature = config.get("temperature", 0.1)
        self.max_retries = config.get("max_retries", 2)
        self.cache: Dict[str, Any] = {}

    def _build_prompt(
        self,
        instrument: str,
        snapshot: Dict[str, Any],
        account_summary: Dict[str, Any],
        open_trades: List[Dict[str, Any]],
        recent_history: List[Dict[str, Any]],
        risk_params: Dict[str, Any],
    ) -> str:
        price = snapshot.get("price", {})
        indicators = snapshot.get("indicators", {})
        signals = snapshot.get("signals", {})

        trades_text = "None"
        if open_trades:
            lines = []
            for t in open_trades:
                lines.append(
                    f"- {t.get('instrument')}: {t.get('currentUnits')} units @ {t.get('price')} (P&L: ${float(t.get('unrealizedPL', 0)):+.2f})"
                )
            trades_text = "\n".join(lines)

        history_text = "None"
        if recent_history:
            lines = []
            for h in recent_history[-5:]:
                pl = float(h.get("realizedPL", 0))
                lines.append(
                    f"- {h.get('instrument')} {h.get('direction')} ${pl:+.2f} ({h.get('close_reason')})"
                )
            history_text = "\n".join(lines)

        prompt = f"""You are an expert forex trading analyst. Analyze the following market data and make a trading decision.

## Account Status
- Balance: ${float(account_summary.get('balance', 0)):,.2f}
- Unrealized P&L: ${float(account_summary.get('unrealizedPL', 0)):+.2f}
- Open Trade Count: {account_summary.get('openTradeCount', 0)}
- Margin Available: ${float(account_summary.get('marginAvailable', 0)):,.2f}

## Risk Parameters
- Max Risk Per Trade: {risk_params.get('max_risk_percent', 1.0)}%
- Daily Loss Limit: {risk_params.get('daily_drawdown_limit', 5.0)}%
- Total Drawdown Limit: {risk_params.get('total_drawdown_limit', 10.0)}%
- Cooldown Minutes: {risk_params.get('cooldown_minutes', 15)}

## Current Open Positions
{trades_text}

## Recent Trade History (Last 5)
{history_text}

## Market Data: {instrument}
- Timeframe: {snapshot.get('timeframe', 'N/A')}
- Close: {price.get('close', 'N/A')}
- Change: {price.get('change_percent', 0):+.2f}%

## Technical Indicators
- EMA 20: {indicators.get('ema_20', 'N/A')}
- EMA 50: {indicators.get('ema_50', 'N/A')}
- RSI 14: {indicators.get('rsi_14', 'N/A')}
- MACD: {indicators.get('macd', 'N/A')}
- ATR 14: {indicators.get('atr_14', 'N/A')}
- ADX 14: {indicators.get('adx_14', 'N/A')}

## Technical Signals
- Trend: {signals.get('trend', 'N/A')}
- EMA Crossover: {signals.get('ema_crossover', 'N/A')}
- RSI Signal: {signals.get('rsi_signal', 'N/A')}
- MACD Signal: {signals.get('macd_signal', 'N/A')}
- Volatility: {signals.get('volatility', 'N/A')}

## Instructions
Based on the above data, decide whether to:
1. BUY (open long position)
2. SELL (open short position)
3. HOLD (no action)
4. CLOSE (close existing position on this instrument)

Consider:
- Technical indicator alignment
- Risk management (don't over-leverage)
- Account margin availability
- Recent performance (avoid revenge trading)
- Market volatility (wider stops in high ATR)

Respond ONLY with a JSON object in this exact format:
{{
    "decision": "BUY" | "SELL" | "HOLD" | "CLOSE",
    "confidence": 0-100,
    "reasoning": "Brief explanation in 1-2 sentences",
    "instrument": "{instrument}",
    "risk_percent": 0.5-2.0,
    "stop_loss_pips": integer or null,
    "take_profit_pips": integer or null
}}
"""
        return prompt

    def _call_ollama(self, prompt: str, model: str) -> Dict[str, Any]:
        """Call Ollama API (OpenAI-compatible endpoint)."""
        payload = {
            "model": model,
            "messages": [
                {"role": "system", "content": "You are a forex trading assistant. Respond only with valid JSON."},
                {"role": "user", "content": prompt},
            ],
            "stream": False,
            "options": {
                "temperature": self.temperature,
            },
            "format": "json",
        }
        resp = requests.post(
            f"{self.url}/api/chat",
            json=payload,
            timeout=self.timeout,
        )
        resp.raise_for_status()
        data = resp.json()
        content = data.get("message", {}).get("content", "{}")
        return json.loads(content)

    def _call_openai(self, prompt: str) -> Dict[str, Any]:
        api_key = self.config.get("api_key", "")
        model = self.config.get("default_model", "gpt-4o-mini")
        headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        }
        payload = {
            "model": model,
            "messages": [
                {"role": "system", "content": "You are a forex trading assistant. Respond only with valid JSON."},
                {"role": "user", "content": prompt},
            ],
            "temperature": self.temperature,
            "max_tokens": 500,
            "response_format": {"type": "json_object"},
        }
        resp = requests.post(
            "https://api.openai.com/v1/chat/completions",
            headers=headers,
            json=payload,
            timeout=self.timeout,
        )
        resp.raise_for_status()
        data = resp.json()
        content = data["choices"][0]["message"]["content"]
        return json.loads(content)

    def _call_anthropic(self, prompt: str) -> Dict[str, Any]:
        api_key = self.config.get("api_key", "")
        model = self.config.get("default_model", "claude-3-haiku-20240307")
        headers = {
            "x-api-key": api_key,
            "Content-Type": "application/json",
            "anthropic-version": "2023-06-01",
        }
        payload = {
            "model": model,
            "max_tokens": 500,
            "temperature": self.temperature,
            "system": "You are a forex trading assistant. Respond only with valid JSON.",
            "messages": [{"role": "user", "content": prompt}],
        }
        resp = requests.post(
            "https://api.anthropic.com/v1/messages",
            headers=headers,
            json=payload,
            timeout=self.timeout,
        )
        resp.raise_for_status()
        data = resp.json()
        content = data["content"][0]["text"]
        if "```json" in content:
            content = content.split("```json").split("```").strip()[1]
        elif "```" in content:
            content = content.split("```").split("```")[0].strip()
        return json.loads(content)

    def _call_deepseek(self, prompt: str) -> Dict[str, Any]:
        api_key = self.config.get("api_key", "")
        model = self.config.get("default_model", "deepseek-chat")
        headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        }
        payload = {
            "model": model,
            "messages": [
                {"role": "system", "content": "You are a forex trading assistant. Respond only with valid JSON."},
                {"role": "user", "content": prompt},
            ],
            "temperature": self.temperature,
            "max_tokens": 500,
            "response_format": {"type": "json_object"},
        }
        resp = requests.post(
            "https://api.deepseek.com/v1/chat/completions",
            headers=headers,
            json=payload,
            timeout=self.timeout,
        )
        resp.raise_for_status()
        data = resp.json()
        content = data["choices"][0]["message"]["content"]
        return json.loads(content)

    def _call_llm(self, prompt: str) -> Dict[str, Any]:
        provider = self.config.get("provider", "ollama").lower()
        if provider == "ollama" or self.url.startswith("http://localhost"):
            return self._call_ollama(prompt, self.model)
        elif provider == "openai":
            return self._call_openai(prompt)
        elif provider == "anthropic":
            return self._call_anthropic(prompt)
        elif provider == "deepseek":
            return self._call_deepseek(prompt)
        else:
            # Default to Ollama
            return self._call_ollama(prompt, self.model)

    def get_trade_decision(
        self,
        instrument: str,
        snapshot: Dict[str, Any],
        account_summary: Dict[str, Any],
        open_trades: List[Dict[str, Any]],
        recent_history: List[Dict[str, Any]],
        risk_params: Optional[Dict[str, Any]] = None,
    ) -> LLMTradeDecision:
        """Get a trade decision from the LLM."""
        if risk_params is None:
            risk_params = {
                "max_risk_percent": 1.0,
                "daily_drawdown_limit": 5.0,
                "total_drawdown_limit": 10.0,
                "cooldown_minutes": 15,
            }

        cache_key = f"{instrument}:{snapshot.get('price', {}).get('close')}"
        if cache_key in self.cache:
            return self.cache[cache_key]

        prompt = self._build_prompt(
            instrument, snapshot, account_summary, open_trades, recent_history, risk_params
        )

        last_error = None
        models_to_try = [self.model, self.fallback_model]
        for model in models_to_try:
            for attempt in range(self.max_retries + 1):
                try:
                    raw = self._call_llm(prompt) if model == self.model else self._call_ollama(prompt, model)
                    decision = LLMTradeDecision(
                        decision=raw.get("decision", "HOLD").upper(),
                        confidence=max(0, min(100, int(raw.get("confidence", 50)))),
                        reasoning=raw.get("reasoning", "No reasoning provided"),
                        instrument=raw.get("instrument", instrument),
                        risk_percent=float(raw.get("risk_percent", 1.0)),
                        stop_loss_pips=raw.get("stop_loss_pips"),
                        take_profit_pips=raw.get("take_profit_pips"),
                    )
                    self.cache[cache_key] = decision
                    return decision
                except Exception as e:
                    last_error = e
                    if attempt < self.max_retries:
                        time.sleep(1)
                    continue

        # Fallback to technical signals
        signals = snapshot.get("signals", {})
        trend = signals.get("trend", "NEUTRAL")
        ema_cross = signals.get("ema_crossover", "NEUTRAL")

        fallback_decision = "HOLD"
        if trend == "BULLISH" and ema_cross == "BULLISH":
            fallback_decision = "BUY"
        elif trend == "BEARISH" and ema_cross == "BEARISH":
            fallback_decision = "SELL"

        return LLMTradeDecision(
            decision=fallback_decision,
            confidence=50,
            reasoning=f"LLM failed ({str(last_error)}). Fallback to technical signals.",
            instrument=instrument,
            risk_percent=risk_params.get("max_risk_percent", 1.0),
        )

    def clear_cache(self):
        self.cache.clear()