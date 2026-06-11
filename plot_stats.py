#!/usr/bin/env python3
"""Build paginated grouped bar charts from trace processing statistics."""

from __future__ import annotations

import argparse
import csv
import math
import os
import re
from collections import OrderedDict
from pathlib import Path
from typing import Iterable

os.environ.setdefault("MPLCONFIGDIR", str(Path("/tmp") / "matplotlib-cache"))

import matplotlib.pyplot as plt
from matplotlib.lines import Line2D
from matplotlib.patches import Patch


MISSING_VALUES = {"", "-"}
SCENARIO_COLUMN = "scenario"
TRACE_COLUMN = "trace"
PROCESSING_COLUMN = "processing"
VERIFICATION_COLUMN = "verification"
DEFAULT_MISSING_FRACTION = 0.035
FONT_SCALE = 2
BASE_FONT_SIZE = 10.0 * FONT_SCALE
METRIC_LABEL_SIZE = 12.0 * FONT_SCALE
LEGEND_ANCHOR_Y = -0.16
PASSED_COLOR = "#2f7d4a"
VERIFICATION_FAILED_COLOR = "#f2c94c"
PROCESSING_FAILED_COLOR = "#d64545"
UNKNOWN_STATUS_COLOR = "#9a9a9a"
TARGET_LINE_COLORS = ("#6a4c93", "#2a9d8f", "#bc4749", "#5f6f52", "#8f2d56")

plt.rcParams.update(
    {
        "font.size": BASE_FONT_SIZE,
        "axes.labelsize": BASE_FONT_SIZE,
        "xtick.labelsize": BASE_FONT_SIZE,
        "ytick.labelsize": BASE_FONT_SIZE,
        "legend.fontsize": BASE_FONT_SIZE,
    }
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Visualize execution trace processing statistics as paginated grouped "
            "bar charts. Bars are grouped by scenario; traces are bars inside each "
            "group."
        )
    )
    parser.add_argument(
        "csv_path",
        nargs="?",
        default="stats.csv",
        help="Input CSV file. Default: stats.csv",
    )
    parser.add_argument(
        "-o",
        "--output-dir",
        default="pics/stats",
        help="Directory for generated images. Default: pics/stats",
    )
    parser.add_argument(
        "-m",
        "--metrics",
        nargs="+",
        help=(
            "Metric columns to plot. Default: all numeric measurement columns "
            "except scenario, trace, processing, and verification."
        ),
    )
    parser.add_argument(
        "--pictures",
        type=int,
        default=3,
        help=(
            "Number of images to generate. Scenarios are split into this many "
            "contiguous pages by rendered group size, preserving order. Default: 3"
        ),
    )
    parser.add_argument(
        "--fig-width",
        type=float,
        default=15.0,
        help="Output figure width in inches. Default: 15",
    )
    parser.add_argument(
        "--fig-height",
        type=float,
        default=7.0,
        help="Output figure height in inches. Default: 7",
    )
    parser.add_argument(
        "--dpi",
        type=int,
        default=180,
        help="Output image DPI. Default: 180",
    )
    parser.add_argument(
        "--format",
        choices=("png", "pdf", "svg"),
        default="png",
        help="Output image format. Default: png",
    )
    parser.add_argument(
        "--yscale",
        choices=("linear", "log"),
        default="linear",
        help="Y-axis scale. Default: linear",
    )
    parser.add_argument(
        "--missing-bar-fraction",
        type=float,
        default=DEFAULT_MISSING_FRACTION,
        help=(
            "Visual height of missing-value marker bars as a fraction of the "
            "plot area. Default: 0.035"
        ),
    )
    parser.add_argument(
        "--group-width",
        type=float,
        default=0.82,
        help="Fraction of each scenario slot occupied by trace bars. Default: 0.82",
    )
    parser.add_argument(
        "--sort-scenarios",
        choices=("input", "natural"),
        default="input",
        help="Scenario ordering. Default: input",
    )
    parser.add_argument(
        "--hline",
        type=float,
        action="append",
        default=[],
        metavar="VALUE",
        help=(
            "Draw a horizontal target line at VALUE on every selected metric "
            "chart. Can be used more than once."
        ),
    )
    return parser.parse_args()


def natural_key(value: str) -> list[object]:
    parts = re.split(r"(\d+)", value)
    return [int(part) if part.isdigit() else part.lower() for part in parts]


def parse_number(value: str | None) -> float | None:
    if value is None or value.strip() in MISSING_VALUES:
        return None
    return float(value)


def parse_success(value: str | None) -> bool | None:
    if value is None or value.strip() in MISSING_VALUES:
        return None
    try:
        return bool(int(float(value)))
    except ValueError:
        normalized = value.strip().lower()
        if normalized in {"true", "yes", "ok", "success"}:
            return True
        if normalized in {"false", "no", "fail", "failed", "error"}:
            return False
        return None


def sanitize_filename(value: str) -> str:
    return re.sub(r"[^A-Za-z0-9_.-]+", "_", value).strip("_") or "metric"


def metric_label(metric: str) -> str:
    labels = {
        "Pcomp": r"$P_{comp}$",
        "Rcomp": r"$R_{comp}$",
    }
    return labels.get(metric, metric)


def ensure_columns(columns: Iterable[str], required: Iterable[str]) -> None:
    available = set(columns)
    missing = [column for column in required if column not in available]
    if missing:
        raise SystemExit(f"Missing required CSV columns: {', '.join(missing)}")


def read_rows(csv_path: Path) -> tuple[list[str], list[dict[str, str]]]:
    with csv_path.open(newline="") as csv_file:
        reader = csv.DictReader(csv_file)
        if not reader.fieldnames:
            raise SystemExit(f"{csv_path} has no header row")
        rows = list(reader)
    if not rows:
        raise SystemExit(f"{csv_path} has no data rows")
    return list(reader.fieldnames), rows


def ordered_unique(values: Iterable[str]) -> list[str]:
    return list(OrderedDict((value, None) for value in values))


def discover_metrics(
    columns: list[str],
    rows: list[dict[str, str]],
    excluded_columns: set[str],
) -> list[str]:
    metrics = []
    for column in columns:
        if column in excluded_columns:
            continue
        has_value = False
        is_numeric_or_missing = True
        for row in rows:
            value = row.get(column, "")
            if value.strip() in MISSING_VALUES:
                continue
            has_value = True
            try:
                float(value)
            except ValueError:
                is_numeric_or_missing = False
                break
        if has_value and is_numeric_or_missing:
            metrics.append(column)
    return metrics


def grouped_rows(
    rows: list[dict[str, str]],
) -> dict[str, dict[str, dict[str, str]]]:
    groups: dict[str, dict[str, dict[str, str]]] = OrderedDict()
    for row in rows:
        scenario = row[SCENARIO_COLUMN]
        trace = row[TRACE_COLUMN]
        groups.setdefault(scenario, OrderedDict())[trace] = row
    return groups


def metric_extent(
    rows: list[dict[str, str]],
    metric: str,
    missing_fraction: float,
    target_lines: list[float],
    yscale: str,
) -> tuple[float, float, float, float]:
    values = [value for value in (parse_number(row.get(metric)) for row in rows) if value is not None]
    if not values:
        raise SystemExit(f"Metric {metric!r} has no numeric values")
    maximum = max(max(values), 0.0)
    scale_candidates = [maximum, *(line for line in target_lines if line > 0)]
    scale_base = max(scale_candidates)
    if scale_base == 0:
        scale_base = 1.0
    if yscale == "log":
        non_positive_values = [value for value in values if value <= 0]
        if non_positive_values:
            raise SystemExit(f"Metric {metric!r} contains non-positive values; log scale requires values > 0")
        non_positive_lines = [line for line in target_lines if line <= 0]
        if non_positive_lines:
            raise SystemExit(f"Metric {metric!r} has non-positive target lines; log scale requires values > 0")
        positive_scale_values = [*values, *target_lines]
        y_min = min(value for value in positive_scale_values if value > 0) / 1.25
        y_max = max(value for value in positive_scale_values if value > 0) * 1.25
        missing_bottom = y_min
        missing_top = y_min * ((y_max / y_min) ** missing_fraction)
    else:
        y_min = 0.0
        y_max = scale_base * 1.10
        missing_bottom = 0.0
        missing_top = y_min + (y_max - y_min) * missing_fraction
    return missing_bottom, missing_top, y_min, y_max


def status_color(
    row: dict[str, str],
) -> str:
    processing = parse_success(row.get(PROCESSING_COLUMN))
    verification = parse_success(row.get(VERIFICATION_COLUMN))
    if processing is False:
        return PROCESSING_FAILED_COLOR
    if verification is False:
        return VERIFICATION_FAILED_COLOR
    if processing is True and verification is True:
        return PASSED_COLOR
    return UNKNOWN_STATUS_COLOR


def build_page_layout(
    page_scenarios: list[str],
    groups: dict[str, dict[str, dict[str, str]]],
    slot_width: float,
    group_gap: float,
) -> tuple[dict[str, tuple[float, list[str]]], float]:
    layout = {}
    cursor = 0.0
    for index, scenario in enumerate(page_scenarios):
        scenario_traces = sorted(groups[scenario], key=natural_key)
        scenario_width = slot_width * len(scenario_traces)
        center = cursor + scenario_width / 2
        layout[scenario] = (center, scenario_traces)
        cursor += scenario_width
        if index != len(page_scenarios) - 1:
            cursor += group_gap
    return layout, cursor


def balanced_pages(
    scenario_names: list[str],
    groups: dict[str, dict[str, dict[str, str]]],
    picture_count: int,
    slot_width: float,
    group_gap: float,
) -> list[list[str]]:
    scenario_count = len(scenario_names)
    if picture_count > scenario_count:
        raise SystemExit("--pictures cannot exceed the number of scenarios")

    prefix_trace_counts = [0]
    for scenario in scenario_names:
        prefix_trace_counts.append(prefix_trace_counts[-1] + len(groups[scenario]))

    def page_width(start: int, end: int) -> float:
        trace_count = prefix_trace_counts[end] - prefix_trace_counts[start]
        gap_count = max(0, end - start - 1)
        return trace_count * slot_width + gap_count * group_gap

    costs = [[math.inf] * (scenario_count + 1) for _ in range(picture_count + 1)]
    parents = [[-1] * (scenario_count + 1) for _ in range(picture_count + 1)]
    costs[0][0] = 0.0

    for page_index in range(1, picture_count + 1):
        for end in range(page_index, scenario_count + 1):
            for start in range(page_index - 1, end):
                previous = costs[page_index - 1][start]
                if previous == math.inf:
                    continue
                candidate = max(previous, page_width(start, end))
                if candidate < costs[page_index][end]:
                    costs[page_index][end] = candidate
                    parents[page_index][end] = start

    pages = []
    end = scenario_count
    for page_index in range(picture_count, 0, -1):
        start = parents[page_index][end]
        if start < 0:
            raise SystemExit("Could not split scenarios into balanced pages")
        pages.append(scenario_names[start:end])
        end = start
    pages.reverse()
    return pages


def draw_metric(
    metric: str,
    groups: dict[str, dict[str, dict[str, str]]],
    scenario_names: list[str],
    trace_names: list[str],
    target_lines: list[float],
    args: argparse.Namespace,
    output_dir: Path,
) -> list[Path]:
    missing_bottom, missing_top, y_min, y_max = metric_extent(
        [row for scenario_rows in groups.values() for row in scenario_rows.values()],
        metric,
        args.missing_bar_fraction,
        target_lines,
        args.yscale,
    )
    group_width = max(0.05, min(args.group_width, 0.98))
    slot_width = group_width / len(trace_names)
    bar_width = slot_width * 0.86
    group_gap = 1.0 - group_width
    pages = balanced_pages(scenario_names, groups, args.pictures, slot_width, group_gap)
    page_layouts = []
    x_span = 0.0
    for page_scenarios in pages:
        layout, page_width = build_page_layout(page_scenarios, groups, slot_width, group_gap)
        page_layouts.append((page_scenarios, layout, page_width))
        x_span = max(x_span, page_width)
    x_margin = group_gap / 2
    output_paths = []

    for page, (page_scenarios, layout, _page_width) in enumerate(page_layouts):
        fig, ax = plt.subplots(figsize=(args.fig_width, args.fig_height), dpi=args.dpi)
        display_metric = metric_label(metric)

        for scenario in page_scenarios:
            center, scenario_traces = layout[scenario]
            trace_rows = groups[scenario]
            scenario_width = slot_width * len(scenario_traces)
            first_offset = -scenario_width / 2 + slot_width / 2
            for trace_index, trace in enumerate(scenario_traces):
                row = trace_rows[trace]

                value = parse_number(row.get(metric))
                x = center + first_offset + trace_index * slot_width
                bar_color = status_color(row)

                if value is None:
                    ax.bar(
                        x,
                        missing_top - missing_bottom,
                        width=bar_width,
                        bottom=missing_bottom,
                        color=bar_color,
                        edgecolor="#303030",
                        linewidth=0.35,
                        hatch="xxx",
                        zorder=3,
                    )
                else:
                    ax.bar(
                        x,
                        value,
                        width=bar_width,
                        color=bar_color,
                        edgecolor="#303030",
                        linewidth=0.35,
                        zorder=3,
                    )

        ax.set_ylabel(display_metric, fontsize=METRIC_LABEL_SIZE)
        ax.set_xlabel("Нагрузка")
        ax.set_yscale(args.yscale)
        ax.set_ylim(y_min, y_max)
        ax.set_xlim(-x_margin, x_span + x_margin)
        ax.set_xticks([layout[scenario][0] for scenario in page_scenarios])
        ax.set_xticklabels(page_scenarios, rotation=35, ha="right")
        ax.grid(axis="y", which="both", color="#d9d9d9", linewidth=0.7, zorder=0)

        legend_items = [
            Patch(facecolor=PASSED_COLOR, edgecolor="#303030", label="Обработка и верификация успешны"),
            Patch(facecolor=VERIFICATION_FAILED_COLOR, edgecolor="#303030", label="Ошибка верификации"),
            Patch(facecolor=PROCESSING_FAILED_COLOR, edgecolor="#303030", label="Ошибка обработки"),
            Patch(
                facecolor="white",
                edgecolor="#303030",
                hatch="xxx",
                label="Значение отсутствует",
            ),
        ]
        for line_index, line_value in enumerate(target_lines):
            color = TARGET_LINE_COLORS[line_index % len(TARGET_LINE_COLORS)]
            mantissa, exponent = f"{line_value:.2e}".split("e")
            mantissa = mantissa.rstrip("0").rstrip(".")
            ax.axhline(
                line_value,
                color=color,
                linestyle="--",
                linewidth=1.2,
                zorder=4,
            )
            legend_items.append(
                Line2D(
                    [0],
                    [0],
                    color=color,
                    linestyle="--",
                    linewidth=1.2,
                    label=f"{display_metric} = {mantissa}e{int(exponent):d}",
                )
            )
        ax.legend(
            handles=legend_items,
            loc="upper center",
            bbox_to_anchor=(0.5, LEGEND_ANCHOR_Y),
            ncol=min(6, len(legend_items)),
            frameon=False,
        )
        fig.tight_layout()

        filename = f"{sanitize_filename(metric)}_{page + 1:02d}.{args.format}"
        output_path = output_dir / filename
        fig.savefig(output_path)
        plt.close(fig)
        output_paths.append(output_path)

    return output_paths


def main() -> None:
    args = parse_args()
    if args.pictures <= 0:
        raise SystemExit("--pictures must be positive")
    if args.fig_width <= 0 or args.fig_height <= 0:
        raise SystemExit("--fig-width and --fig-height must be positive")
    if args.missing_bar_fraction <= 0:
        raise SystemExit("--missing-bar-fraction must be positive")

    csv_path = Path(args.csv_path)
    columns, rows = read_rows(csv_path)
    ensure_columns(columns, [SCENARIO_COLUMN, TRACE_COLUMN, PROCESSING_COLUMN, VERIFICATION_COLUMN])

    excluded_columns = {
        SCENARIO_COLUMN,
        TRACE_COLUMN,
        PROCESSING_COLUMN,
        VERIFICATION_COLUMN,
    }
    metrics = args.metrics or discover_metrics(columns, rows, excluded_columns)
    ensure_columns(columns, metrics)
    if not metrics:
        raise SystemExit("No metric columns selected")

    groups = grouped_rows(rows)
    scenario_names = list(groups.keys())
    if args.sort_scenarios == "natural":
        scenario_names.sort(key=natural_key)
    trace_names = ordered_unique(row[TRACE_COLUMN] for row in rows)
    trace_names.sort(key=natural_key)

    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    generated = []
    for metric in metrics:
        generated.extend(
            draw_metric(
                metric,
                groups,
                scenario_names,
                trace_names,
                args.hline,
                args,
                output_dir,
            )
        )

    print(f"Generated {len(generated)} image(s) in {output_dir}")
    for path in generated:
        print(path)


if __name__ == "__main__":
    main()
