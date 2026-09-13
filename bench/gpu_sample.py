"""Optional nvidia-smi sampler for diagnostic runs.

Fills gpu_util_pct / gpu_mem_mb averages over a wall-clock window.
Never invents values — if nvidia-smi is missing, returns (None, None).
"""

from __future__ import annotations

import subprocess
import threading
import time
from dataclasses import dataclass, field


@dataclass
class GpuSample:
    util_pct: float | None = None
    mem_mb: float | None = None
    n: int = 0
    _utils: list[float] = field(default_factory=list, repr=False)
    _mems: list[float] = field(default_factory=list, repr=False)
    _stop: threading.Event = field(default_factory=threading.Event, repr=False)
    _thread: threading.Thread | None = field(default=None, repr=False)

    def start(self, interval_s: float = 0.5) -> None:
        self._stop.clear()
        self._utils.clear()
        self._mems.clear()

        def _loop() -> None:
            while not self._stop.is_set():
                u, m = _read_nvidia_smi()
                if u is not None:
                    self._utils.append(u)
                if m is not None:
                    self._mems.append(m)
                time.sleep(interval_s)

        self._thread = threading.Thread(target=_loop, daemon=True)
        self._thread.start()

    def stop(self) -> None:
        self._stop.set()
        if self._thread is not None:
            self._thread.join(timeout=5.0)
            self._thread = None
        self.n = len(self._utils)
        self.util_pct = (
            round(sum(self._utils) / len(self._utils), 2) if self._utils else None
        )
        self.mem_mb = (
            round(sum(self._mems) / len(self._mems), 1) if self._mems else None
        )


def _read_nvidia_smi() -> tuple[float | None, float | None]:
    try:
        out = subprocess.check_output(
            [
                "nvidia-smi",
                "--query-gpu=utilization.gpu,memory.used",
                "--format=csv,noheader,nounits",
            ],
            text=True,
            timeout=2,
        )
    except (FileNotFoundError, subprocess.SubprocessError, OSError):
        return None, None
    line = out.strip().splitlines()[0] if out.strip() else ""
    parts = [p.strip() for p in line.split(",")]
    if len(parts) < 2:
        return None, None
    try:
        return float(parts[0]), float(parts[1])
    except ValueError:
        return None, None
