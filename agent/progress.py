"""Progress streaming for Product Agent v9.0.

Provides real-time phase-by-phase progress output during builds.
Writes to stderr so stdout remains clean for programmatic use.

v12.1: Added friendly progress mode for Shipwright plugin integration.
"""

import os
import sys
import time
from dataclasses import dataclass, field
from typing import TextIO


# v12.1: Friendly phase name mapping for beginner-facing output
_FRIENDLY_PHASE_NAMES: dict[str, str] = {
    "enrich": "Researching your idea...",
    "analyze": "Understanding what to build...",
    "design": "Designing the app structure...",
    "review": "Reviewing the design...",
    "build": "Writing the code (this takes a few minutes)...",
    "audit": "Checking that everything matches your request...",
    "test": "Running tests...",
    "deploy": "Deploying to Vercel...",
    "verify": "Verifying the live app...",
}

_FRIENDLY_PHASE_DONE: dict[str, str] = {
    "enrich": "Research complete",
    "analyze": "Got it — picked the best tech for your app",
    "design": "App designed",
    "review": "Design looks good",
    "build": "Code written",
    "audit": "All features accounted for",
    "test": "Tests passed",
    "deploy": "Deployed!",
    "verify": "Live and working!",
}


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
    v12.1: Supports friendly mode for Shipwright beginner-facing output.
    """
    verbose: bool = False
    output: TextIO = field(default_factory=lambda: sys.stderr)
    _phase_count: int = 0
    _total_phases: int = 9
    _start_time: float = field(default_factory=time.time)
    _results: list[PhaseResult] = field(default_factory=list)
    # v12.1: Friendly mode for Shipwright — set via PROGRESS_MODE env var
    _friendly: bool = field(default_factory=lambda: os.environ.get("PROGRESS_MODE") == "friendly")

    def set_total_phases(self, total: int) -> None:
        """Set the total number of phases (varies by build mode)."""
        self._total_phases = total

    def phase_start(self, phase_name: str) -> None:
        """Report that a phase is starting."""
        self._phase_count += 1

        if self._friendly:
            # v12.1: Beginner-friendly output for Shipwright
            friendly = _FRIENDLY_PHASE_NAMES.get(phase_name.lower(), f"{phase_name}...")
            self.output.write(f"\r{friendly:<60}")
        else:
            label = f"[{self._phase_count}/{self._total_phases}]"
            msg = f"{label} {phase_name}..."
            # \r = carriage return: overwrites current line for in-place progress updates
            self.output.write(f"\r{msg:<55}")
        self.output.flush()

    def phase_complete(self, result: PhaseResult) -> None:
        """Report that a phase completed."""
        self._results.append(result)

        if self._friendly:
            # v12.1: Beginner-friendly completion messages
            phase_key = result.phase_name.lower()
            friendly_done = _FRIENDLY_PHASE_DONE.get(phase_key, "Done")
            detail = f" — {result.detail}" if result.detail else ""
            status_icon = "OK" if result.success else "!!"
            self.output.write(f"\r{friendly_done}{detail:<50} {status_icon}\n")
        else:
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

    def phase_skipped(self, phase_name: str, detail: str = "") -> None:
        """Report that a phase was skipped during resume.

        Increments the phase counter without running the phase,
        so subsequent phases show correct numbering.
        """
        self._phase_count += 1
        label = f"[{self._phase_count}/{self._total_phases}]"
        detail_str = f" ({detail})" if detail else ""
        line = f"{label} {phase_name}...skipped{detail_str}"
        self.output.write(f"\r{line:<55}\n")
        self.output.flush()

    def build_header(self, idea: str, version: str = "8.0") -> None:
        """Print build header."""
        display_idea = idea if len(idea) <= 60 else idea[:57] + "..."
        if self._friendly:
            self.output.write(f"\nShipwright — Building your app...\n\n")
        else:
            self.output.write(f"\nProduct Agent v{version} — Building: \"{display_idea}\"\n\n")
        self.output.flush()

    def build_resume_header(self, idea: str, resume_phase: str, version: str = "8.0") -> None:
        """Print build header for a resumed build.

        Shows which phase the build is resuming from instead of starting fresh.
        """
        display_idea = idea if len(idea) <= 60 else idea[:57] + "..."
        self.output.write(
            f"\nProduct Agent v{version} — Resuming: \"{display_idea}\"\n"
            f"  Resuming from: {resume_phase}\n\n"
        )
        self.output.flush()

    def build_complete(self, url: str | None, quality: str | None = None) -> None:
        """Print build summary."""
        total_duration = time.time() - self._start_time

        if self._friendly:
            self.output.write(f"\nYour app is ready! ({_format_duration(total_duration)})\n")
            if url:
                self.output.write(f"  Live at: {url}\n")
            for r in self._results:
                if "test" in r.phase_name.lower() and r.detail:
                    self.output.write(f"  Tests: {r.detail}\n")
            if quality:
                self.output.write(f"  Quality: {quality}\n")
        else:
            self.output.write(f"\nBUILD COMPLETE  {_format_duration(total_duration)}\n")
            if url:
                self.output.write(f"  URL: {url}\n")
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
        if self._friendly:
            self.output.write(f"\nBuild ran into an issue. ({_format_duration(total_duration)})\n")
            self.output.write(f"  What happened: {reason}\n\n")
        else:
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
