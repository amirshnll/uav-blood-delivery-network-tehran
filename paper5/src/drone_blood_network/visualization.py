from __future__ import annotations

import os
from pathlib import Path
import tempfile

import geopandas as gpd

_cache_root = Path(tempfile.gettempdir()) / "paper5-matplotlib"
_cache_root.mkdir(parents=True, exist_ok=True)
os.environ.setdefault("MPLCONFIGDIR", str(_cache_root))
os.environ.setdefault("XDG_CACHE_HOME", str(_cache_root))

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import pandas as pd


def plot_scenario_summary(summary: pd.DataFrame, output_path: Path) -> None:
    fig, axes = plt.subplots(1, 2, figsize=(13, 5))
    colors = ["#4C78A8" if code == "CALM" else "#F58518" for code in summary["scenario"]]
    axes[0].bar(summary["scenario"], summary["station_count"], color=colors)
    axes[0].set_ylabel("Selected stations")
    axes[0].tick_params(axis="x", rotation=45)
    axes[0].grid(axis="y", alpha=0.25)
    axes[1].bar(summary["scenario"], 100 * summary["mean_total_energy_fraction"], color=colors)
    axes[1].set_ylabel("Mean mission battery use (%)")
    axes[1].tick_params(axis="x", rotation=45)
    axes[1].grid(axis="y", alpha=0.25)
    fig.tight_layout()
    fig.savefig(output_path, dpi=220, bbox_inches="tight")
    plt.close(fig)


def plot_calm_network(
    boundary: gpd.GeoDataFrame,
    zones: gpd.GeoDataFrame,
    demands: gpd.GeoDataFrame,
    selected: gpd.GeoDataFrame,
    routes: gpd.GeoDataFrame,
    output_path: Path,
) -> None:
    fig, ax = plt.subplots(figsize=(10, 9))
    boundary.boundary.plot(ax=ax, color="#4D4D4D", linewidth=0.7)
    clipped_zones = gpd.clip(zones, boundary)
    clipped_zones.plot(ax=ax, color="#D62728", alpha=0.20, linewidth=0)
    if not routes.empty:
        routes.iloc[:: max(1, len(routes) // 250)].plot(
            ax=ax, color="#4C78A8", linewidth=0.35, alpha=0.35
        )
    demands.plot(ax=ax, color="#9ECAE1", markersize=2, alpha=0.45)
    selected.plot(
        ax=ax,
        color="#111111",
        edgecolor="white",
        markersize=55,
        marker="^",
        linewidth=0.6,
        label="Selected station",
    )
    ax.set_axis_off()
    ax.set_title("Obstacle-safe network under calm conditions")
    ax.legend(loc="lower left")
    minx, miny, maxx, maxy = boundary.total_bounds
    margin_x = 0.02 * (maxx - minx)
    margin_y = 0.02 * (maxy - miny)
    ax.set_xlim(minx - margin_x, maxx + margin_x)
    ax.set_ylim(miny - margin_y, maxy + margin_y)
    fig.tight_layout()
    fig.savefig(output_path, dpi=240, bbox_inches="tight")
    plt.close(fig)


def plot_detour_distribution(assignments: pd.DataFrame, output_path: Path) -> None:
    values = assignments["detour_ratio"].dropna()
    upper = max(2.0, float(values.quantile(0.995)))
    displayed = values[values <= upper]
    fig, ax = plt.subplots(figsize=(7.5, 4.8))
    ax.hist(displayed, bins=35, color="#4C78A8", edgecolor="white", linewidth=0.4)
    ax.axvline(1.0, color="#222222", linestyle="--", linewidth=1)
    ax.set_xlabel("Safe-path distance / straight-line distance")
    ax.set_ylabel("Demand points")
    ax.set_xlim(0.9, upper)
    omitted = len(values) - len(displayed)
    if omitted:
        ax.text(
            0.98,
            0.95,
            f"{omitted} extreme near-origin ratios omitted",
            ha="right",
            va="top",
            transform=ax.transAxes,
            fontsize=9,
        )
    ax.grid(axis="y", alpha=0.2)
    fig.tight_layout()
    fig.savefig(output_path, dpi=220, bbox_inches="tight")
    plt.close(fig)
