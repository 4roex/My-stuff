"""Desktop notifications manager.

Default behavior is intentionally conservative on Windows:
desktop notifications are disabled unless explicitly enabled,
because PowerShell-based notifications can spawn visible popup
windows or console flashes.
"""
import platform
import subprocess
from typing import Optional


class NotificationManager:
    """Sends optional desktop notifications.

    On Windows, PowerShell notifications are disabled by default
    to avoid popup console windows. Keep enabled=False unless you
    explicitly want them.
    """

    def __init__(self, enabled: bool = False):
        self.enabled = enabled
        self._is_windows = platform.system() == "Windows"

    def set_enabled(self, enabled: bool):
        self.enabled = bool(enabled)

    def _send_windows(self, title: str, message: str, icon: str = "Info"):
        if not self._is_windows or not self.enabled:
            return

        safe_title = title.replace("'", "''")
        safe_message = message.replace("'", "''")

        ps_script = f"""
Add-Type -AssemblyName System.Windows.Forms
Add-Type -AssemblyName System.Drawing
$notify = New-Object System.Windows.Forms.NotifyIcon
$notify.Icon = [System.Drawing.SystemIcons]::{icon}
$notify.BalloonTipTitle = '{safe_title}'
$notify.BalloonTipText = '{safe_message}'
$notify.Visible = $True
$notify.ShowBalloonTip(3000)
Start-Sleep -Milliseconds 800
$notify.Dispose()
"""

        try:
            creationflags = 0
            if hasattr(subprocess, "CREATE_NO_WINDOW"):
                creationflags = subprocess.CREATE_NO_WINDOW

            subprocess.Popen(
                ["powershell", "-NoProfile", "-NonInteractive", "-ExecutionPolicy", "Bypass", "-Command", ps_script],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                stdin=subprocess.DEVNULL,
                creationflags=creationflags,
            )
        except Exception:
            pass

    def notify(self, title: str, message: str, icon: str = "Info"):
        if not self.enabled:
            return
        if self._is_windows:
            self._send_windows(title, message, icon)

    def trade_opened(self, instrument: str, direction: str, units: int, sl: Optional[float], tp: Optional[float]):
        msg = f"{instrument}: {direction} {units:,.0f} units"
        if sl:
            msg += f" | SL: {sl}"
        if tp:
            msg += f" | TP: {tp}"
        self.notify("Trade Opened", msg, "Info")

    def trade_closed(self, instrument: str, pl: float, reason: str = ""):
        icon = "Exclamation" if pl < 0 else "Info"
        msg = f"{instrument} | P&L: ${pl:+.2f}"
        if reason:
            msg += f" ({reason})"
        self.notify("Trade Closed", msg, icon)

    def signal(self, instrument: str, decision: str, confidence: int, reasoning: str):
        icon = "Warning" if decision in ("BUY", "SELL") else "Info"
        msg = f"{decision} ({confidence}%) — {reasoning[:60]}"
        self.notify(f"Signal: {instrument}", msg, icon)

    def limit_hit(self, limit_type: str, detail: str):
        self.notify(f"Limit Hit: {limit_type}", detail, "Error")

    def error(self, message: str):
        self.notify("Bot Error", message[:100], "Error")

    def breakeven(self, instrument: str):
        self.notify("Trade Management", f"SL moved to breakeven on {instrument}", "Info")

    def partial_close(self, instrument: str, pct: int, units: int):
        self.notify("Trade Management", f"Closed {pct}% ({units} units) on {instrument}", "Info")