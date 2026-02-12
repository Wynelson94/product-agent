"""Progress streaming for Product Agent v8.0.

Provides real-time phase progress output during builds.
"""

import sys
import time
from dataclasses import dataclass, field
from typing import TextIO


@dataclass
class PhaseResult:
    """Result from a completed phase."""
    phase_name: str
    success: bool
    duration_s: float
    detail: str = ""
    num_turns: int = 0
    cost_usd: float | None = None


@dataclass
class ProgressReporter:
    """Reports build progress to the user in real time.

    Outputs formatted progress lines as phases complete.
    """
    verbose: bool = False
    output: TextIO = field(default_factory=lambda: sys.stderr)
    _phase_count: int = 0
    _total_phases: int = 9
    _start_time: float = field(default_factory=time.time)
    _results: list[PhaseResult] = field(default_factory=list)

    def set_total_phases(self, total: int) -> None:
        """Set the total number of phases (varies by build mode)."""
        self._total_phases = total

    def phase_start(self, phase_name: str) -> None:
        """Report that a phase is starting."""
        self._phase_count += 1
        label = f"[{self._phase_count}/{self._total_phases}]"
        msg = f"{label} {phase_name}..."
        self.output.write(f"\r{msg:<55}")
        self.output.flush()

    def phase_complete(self, result: PhaseResult) -> None:
        """Report that a phase completed."""
        self._results.append(result)
        label = f"[{self._phase_count}/{self._total_phases}]"
        status = "done" if result.success else "FAIL"
        duration = _format_duration(result.duration_s)
        detail = f" {result.detail}" if result.detail else ""
        line = f"{label} {result.phase_name}...{detail}"
        self.output.write(f"\r{line:<55} {status} {duration:>6}\n")
        self.output.flush()

    def phase_parallel_complete(self, results: list[PhaseResult]) -> None:
        """Report parallel phases completed."""
        for result in results:
            self._phase_count += 1
            label = f"[{self._phase_count}/{self._total_phases}]"
            status = "done" if result.success else "FAIL"
            duration = _format_duration(result.duration_s)
            detail = f" {result.detail}" if result.detail else ""
            line = f"{label} {result.phase_name}...{detail}"
            self.output.write(f"\r{line:<55} {status} {duration:>6}  (parallel)\n")
            self.output.flush()

    def build_header(self, idea: str, version: str = "8.0") -> None:
        """Print build header."""
        # Truncate long ideas
        display_idea = idea if len(idea) <= 60 else idea[:57] + "..."
        self.output.write(f"\nProduct Agent v{version} — Building: \"{display_idea}\"\n\n")
        self.output.flush()

    def build_complete(self, url: str | None, quality: str | None = None) -> None:
        """Print build summary."""
        total_duration = time.time() - self._start_time
        self.output.write(f"\nBUILD COMPLETE  {_format_duration(total_duration)}\n")
        if url:
            self.output.write(f"  URL: {url}\n")
        # Summarize test results
        for r in self._results:
            if "test" in r.phase_name.lower() and r.detail:
                self.output.write(f"  Tests: {r.detail}\n")
            if "audit" in r.phase_name.lower() and r.detail:
                self.output.write(f"  Spec: {r.detail}\n")
        if quality:
            self.output.write(f"  Quality: {quality}\n")
        self.output.write("\n")
        self.output.flush()

    def build_failed(self, reason: str) -> None:
        """Print build failure."""
        total_duration = time.time() - self._start_time
        self.output.write(f"\nBUILD FAILED  {_format_duration(total_duration)}\n")
        self.output.write(f"  Reason: {reason}\n\n")
        self.output.flush()

    def log(self, message: str) -> None:
        """Print a verbose log message (only if verbose mode)."""
        if self.verbose:
            self.output.write(f"  > {message}\n")
            self.output.flush()

    @property
    def results(self) -> list[PhaseResult]:
        """Return all phase results."""
        return list(self._results)

    @property
    def total_duration_s(self) -> float:
        """Return total build duration in seconds."""
        return time.time() - self._start_time


def _format_duration(seconds: float) -> str:
    """Format seconds into a human-readable duration."""
    if seconds < 60:
        return f"{seconds:.0f}s"
    minutes = int(seconds // 60)
    secs = int(seconds % 60)
    return f"{minutes}m{secs:02d}s"
