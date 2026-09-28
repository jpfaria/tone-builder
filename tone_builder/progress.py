"""Progress lines on stderr: where the build is, out of how many, and roughly how long is left.

On a pedal every render is a real re-amp the user hears; without a count, a chord played in
forty voicings sounds like a loop that never ends.
"""

from __future__ import annotations

import sys
import time


class Progress:
    def __init__(self, stage: str, total: int, out=None, clock=time.monotonic):
        self.stage, self.total, self.done = stage, total, 0
        self.out, self.clock, self.t0 = out or sys.stderr, clock, clock()

    def step(self, what: str) -> None:
        self.done += 1
        elapsed = self.clock() - self.t0
        left = elapsed / self.done * (self.total - self.done)
        print(f"[{self.stage}] {self.done}/{self.total} {what} — faltam ~{_mmss(left)}", file=self.out, flush=True)


def _mmss(s: float) -> str:
    s = int(round(s))
    return f"{s // 60}:{s % 60:02d}"
