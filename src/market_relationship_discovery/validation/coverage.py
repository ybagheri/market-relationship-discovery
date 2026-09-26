"""Cross-symbol coverage reporting for multi-symbol price panels.

A price panel collected from one broker request can look complete while being
useless. ``collect --limit 1500`` returns the last 1500 bars *per symbol*, and a
symbol with thin liquidity or a stale history reaches much further back in
calendar time than a liquid one. On a real Alpari demo account a single request
produced panels where one symbol ended sixteen days before another.

Pivoting such a panel yields a wide frame full of gaps, and any later
``dropna`` silently yields nothing. The failure surfaces far from its cause, as
an unrelated error deep inside a statistics routine.

This module reports what each symbol actually covers, which symbols share any
usable window, and where the largest shared window is. It is a diagnostic: it
never repairs data, never fills gaps, and never widens a window to manufacture
overlap.
"""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass, field

import pandas as pd

from market_relationship_discovery.domain.errors import DataQualityError


@dataclass(frozen=True, slots=True)
class SymbolCoverage:
    """How much of the union window one symbol actually covers."""

    symbol: str
    observations: int
    first: pd.Timestamp | None
    last: pd.Timestamp | None
    coverage_fraction: float
    largest_gap: int

    @property
    def span(self) -> pd.Timedelta | None:
        if self.first is None or self.last is None:
            return None
        return self.last - self.first

    def to_dict(self) -> dict[str, object]:
        return {
            "symbol": self.symbol,
            "observations": self.observations,
            "first": self.first.isoformat() if self.first is not None else None,
            "last": self.last.isoformat() if self.last is not None else None,
            "coverage_fraction": self.coverage_fraction,
            "largest_gap": self.largest_gap,
        }


@dataclass(frozen=True, slots=True)
class SharedWindow:
    """The longest contiguous span where enough symbols all have data."""

    start: pd.Timestamp
    end: pd.Timestamp
    rows: int
    symbols: tuple[str, ...]

    def to_dict(self) -> dict[str, object]:
        return {
            "start": self.start.isoformat(),
            "end": self.end.isoformat(),
            "rows": self.rows,
            "symbols": list(self.symbols),
        }


@dataclass(frozen=True, slots=True)
class PanelCoverageReport:
    """Coverage of every symbol in a panel, and what can be used together."""

    union_rows: int
    union_start: pd.Timestamp | None
    union_end: pd.Timestamp | None
    symbols: tuple[str, ...]
    coverage: tuple[SymbolCoverage, ...]
    fully_overlapping_rows: int
    no_overlap_symbols: tuple[str, ...]
    best_shared_window: SharedWindow | None
    minimum_symbols_for_window: int = 2
    issues: tuple[str, ...] = field(default_factory=tuple)

    @property
    def is_usable(self) -> bool:
        return self.best_shared_window is not None

    def coverage_for(self, symbol: str) -> SymbolCoverage | None:
        for item in self.coverage:
            if item.symbol == symbol:
                return item
        return None

    def to_dict(self) -> dict[str, object]:
        return {
            "union_rows": self.union_rows,
            "union_start": self.union_start.isoformat() if self.union_start is not None else None,
            "union_end": self.union_end.isoformat() if self.union_end is not None else None,
            "symbols": list(self.symbols),
            "coverage": [item.to_dict() for item in self.coverage],
            "fully_overlapping_rows": self.fully_overlapping_rows,
            "no_overlap_symbols": list(self.no_overlap_symbols),
            "best_shared_window": (
                self.best_shared_window.to_dict() if self.best_shared_window is not None else None
            ),
            "minimum_symbols_for_window": self.minimum_symbols_for_window,
            "is_usable": self.is_usable,
            "issues": list(self.issues),
        }


class PanelCoverageAnalyzer:
    """Measure what a panel's symbols share, without altering the panel."""

    def analyze(
        self,
        panel: pd.DataFrame,
        minimum_symbols: int = 2,
    ) -> PanelCoverageReport:
        if panel.empty or not len(panel.columns):
            raise DataQualityError("price panel must contain at least one symbol")
        if minimum_symbols < 2:
            raise ValueError("minimum_symbols must be at least two to form a relationship")
        present = panel.notna()
        union_rows = len(panel)
        union_start = panel.index.min() if isinstance(panel.index, pd.DatetimeIndex) else None
        union_end = panel.index.max() if isinstance(panel.index, pd.DatetimeIndex) else None
        coverage: list[SymbolCoverage] = []
        no_overlap: list[str] = []
        for symbol in panel.columns:
            series = present[symbol]
            observations = int(series.sum())
            first = panel.index[series][0] if observations else None
            last = panel.index[series][-1] if observations else None
            coverage.append(
                SymbolCoverage(
                    symbol=str(symbol),
                    observations=observations,
                    first=first,
                    last=last,
                    coverage_fraction=observations / union_rows if union_rows else 0.0,
                    largest_gap=self._largest_gap(series),
                )
            )
        fully_overlapping = int(present.all(axis=1).sum())
        window = self._best_shared_window(present, minimum_symbols)
        if window is None:
            no_overlap = [item.symbol for item in coverage]
        issues: list[str] = []
        if fully_overlapping == 0:
            issues.append(
                "no timestamp is shared by every symbol, so an intersection would be empty"
            )
        if no_overlap:
            issues.append(
                "no window is shared by the requested minimum number of symbols: "
                + ", ".join(sorted(no_overlap))
            )
        stale = [
            item.symbol
            for item in coverage
            if union_end is not None and item.last is not None and item.last < union_end
        ]
        if stale:
            issues.append("symbols ending before the union window end: " + ", ".join(sorted(stale)))
        return PanelCoverageReport(
            union_rows=union_rows,
            union_start=union_start,
            union_end=union_end,
            symbols=tuple(str(column) for column in panel.columns),
            coverage=tuple(coverage),
            fully_overlapping_rows=fully_overlapping,
            no_overlap_symbols=tuple(sorted(no_overlap)),
            best_shared_window=window,
            minimum_symbols_for_window=minimum_symbols,
            issues=tuple(issues),
        )

    def require_usable(
        self,
        panel: pd.DataFrame,
        minimum_symbols: int = 2,
        minimum_observations: int = 30,
    ) -> PanelCoverageReport:
        """Analyse coverage and fail with an actionable message when unusable.

        The previous failure surfaced as ``prices must be finite positive
        values`` from a statistics routine, which told the reader nothing about
        the misaligned panel that caused it.
        """
        report = self.analyze(panel, minimum_symbols)
        if report.best_shared_window is None:
            detail = "; ".join(report.issues) or "the panel has no shared timestamps"
            raise DataQualityError(
                "price panel has no usable shared window: "
                f"{detail}. Symbols collected in one request can cover very "
                "different calendar ranges; collect a common window explicitly "
                "or restrict the panel to symbols that overlap."
            )
        if report.best_shared_window.rows < minimum_observations:
            raise DataQualityError(
                "price panel shared window is too short: "
                f"{report.best_shared_window.rows} rows for symbols "
                f"{list(report.best_shared_window.symbols)}, "
                f"minimum is {minimum_observations}"
            )
        return report

    @staticmethod
    def _largest_gap(series: pd.Series) -> int:
        values = series.to_numpy(dtype=bool)
        largest = 0
        current = 0
        for value in values:
            if value:
                largest = max(largest, current)
                current = 0
            else:
                current += 1
        return max(largest, current)

    @staticmethod
    def _best_shared_window(
        present: pd.DataFrame,
        minimum_symbols: int,
    ) -> SharedWindow | None:
        """Find the widest set of symbols sharing one contiguous window.

        A first pass locates the longest run where at least ``minimum_symbols``
        are present. The symbols spanning that run entirely are preferred,
        because they are directly comparable. Real panels rarely have any, since
        a daily session break leaves no symbol present on every bar, so a greedy
        pass then grows a comparable set by repeatedly adding whichever symbol
        maximises the shared window. Choosing symbols by column order instead
        would pair instruments that never trade at the same time.
        """
        if not isinstance(present.index, pd.DatetimeIndex):
            raise DataQualityError("price panel requires a datetime index for coverage analysis")
        first = PanelCoverageAnalyzer._longest_run(present.sum(axis=1).to_numpy(), minimum_symbols)
        if first is None:
            return None
        low, high = first
        window_slice = present.iloc[low : high + 1]
        complete = [
            str(column)
            for column in window_slice.columns
            if int(window_slice[column].sum()) == len(window_slice)
        ]
        if len(complete) >= minimum_symbols:
            candidates = complete
        else:
            candidates = PanelCoverageAnalyzer._greedy_subset(window_slice, minimum_symbols)
        if len(candidates) < minimum_symbols:
            return None
        subset = present[candidates]
        # ``all(axis=1)`` is already a per-row boolean, so the run threshold is
        # one present symbol, not the size of the candidate set.
        refined = PanelCoverageAnalyzer._longest_run(subset.all(axis=1).to_numpy(), 1)
        if refined is None:
            return None
        start_index, end_index = refined
        return SharedWindow(
            start=subset.index[start_index],
            end=subset.index[end_index],
            rows=end_index - start_index + 1,
            symbols=tuple(sorted(candidates)),
        )

    @staticmethod
    def _greedy_subset(window_slice: pd.DataFrame, minimum_symbols: int) -> list[str]:
        """Grow a comparable symbol set by maximising the shared window."""
        columns = [str(column) for column in window_slice.columns]
        if not columns:
            return []
        selected = [max(columns, key=lambda name: int(window_slice[name].sum()))]
        while len(selected) < minimum_symbols:
            best_name: str | None = None
            best_score = 0
            for name in columns:
                if name in selected:
                    continue
                score = int(window_slice[[*selected, name]].all(axis=1).sum())
                if score > best_score:
                    best_score = score
                    best_name = name
            if best_name is None:
                break
            selected.append(best_name)
        return selected

    @staticmethod
    def _longest_run(flags: Iterable[int], threshold: int) -> tuple[int, int] | None:
        """Return the bounds of the longest contiguous run meeting a threshold.

        ``flags`` holds per-row symbol counts, so the comparison is numeric. A
        boolean series is also accepted and compared against a threshold of one.
        """
        values = [int(value) for value in flags]
        total = len(values)
        best: tuple[int, int, int] | None = None
        start: int | None = None
        for index, value in enumerate(values):
            if value >= threshold:
                if start is None:
                    start = index
            elif start is not None:
                length = index - start
                if best is None or length > best[0]:
                    best = (length, start, index - 1)
                start = None
        if start is not None:
            length = total - start
            if best is None or length > best[0]:
                best = (length, start, total - 1)
        if best is None:
            return None
        _, low, high = best
        return low, high
