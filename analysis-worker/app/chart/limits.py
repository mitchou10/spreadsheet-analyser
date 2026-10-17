import os
from dataclasses import dataclass, field


def _int(name: str, default: int) -> int:
    return int(os.environ.get(name, default))


@dataclass(frozen=True)
class ChartLimits:
    """Bounds on one chart: what it may plot, and how big the image is (fixed, whatever the data)."""

    # Rows of the query that are drawn (the query runs again, with room for more points than the agent sees).
    max_points: int = field(default_factory=lambda: _int("CHART_MAX_POINTS", 5000))
    # Bars and slices stay readable only up to here: the author is asked to aggregate or keep the largest.
    max_categories: int = field(default_factory=lambda: _int("CHART_MAX_CATEGORIES", 40))
    max_series: int = 12
    # A pie keeps its largest slices and groups the rest.
    max_slices: int = 11
    # 900 x 540 px. A small figure at a high resolution: text is relatively larger, so it stays readable when the
    # image is shown at the width of a message.
    width_inches: float = 7.2
    height_inches: float = 4.32
    dpi: int = 125
