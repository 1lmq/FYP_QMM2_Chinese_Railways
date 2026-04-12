"""Exploratory analysis for China's railway network development.

This script covers:
- Temporal patterns of connection types
- Station count and rail length time series with expansion phases
- Spatial network snapshots for key years
- Centrality visualizations for key years
"""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Iterable

import matplotlib.colors as mcolors
import matplotlib.pyplot as plt
import networkx as nx
import numpy as np
import pandas as pd

from rail_growth_analysis import compute_growth_summary, normalize_name, prepare_tracks

# Configure matplotlib to display Chinese characters correctly
plt.style.use("seaborn-v0_8")
plt.rcParams["font.family"] = "sans-serif"
plt.rcParams["font.sans-serif"] = ["Microsoft YaHei", "SimHei"]
plt.rcParams["axes.unicode_minus"] = False

# Threshold (km) to classify short vs. long connections
SHORT_DISTANCE_THRESHOLD = 200.0

CORE_CITY_NAMES = {
    "北京市",
    "上海市",
    "天津市",
    "重庆市",
    "广州市",
    "深圳市",
    "武汉市",
    "成都市",
    "西安市",
    "郑州市",
    "南京市",
    "杭州市",
    "沈阳市",
    "青岛市",
    "大连市",
    "哈尔滨市",
    "长春市",
    "济南市",
    "厦门市",
    "宁波市",
    "南宁市",
    "福州市",
    "昆明市",
    "长沙市",
    "合肥市",
    "乌鲁木齐市",
    "兰州市",
    "石家庄市",
    "南昌市",
}

PORT_INDUSTRIAL_NAMES = {
    "天津市",
    "唐山市",
    "秦皇岛市",
    "烟台市",
    "青岛市",
    "连云港市",
    "宁波市",
    "舟山市",
    "温州市",
    "上海市",
    "苏州市",
    "南通市",
    "盐城市",
    "厦门市",
    "广州港",
    "湛江市",
    "北海市",
    "防城港市",
    "深圳市",
    "珠海市",
    "惠州市",
    "东莞市",
    "珠三角工业区",
    "大连市",
    "营口市",
    "鞍山市",
    "抚顺市",
    "本溪市",
    "锦州市",
    "盘锦市",
}

CATEGORY_COLORS = {
    "core_port_short": "#1f77b4",
    "core_core_long": "#d62728",
    "core_other": "#9467bd",
    "core_port_long": "#17becf",
    "core_core_short": "#ff9896",
    "non_core": "#8c564b",
}

EXPANSION_COLOR = {
    "fast": "#2ca02c",
    "steady": "#ff7f0e",
    "slow": "#7f7f7f",
}


@dataclass(frozen=True)
class KeyYears:
    baseline: int
    peak_growth: int
    high_speed_start: int | None
    recent: int

    def iter_years(self) -> Iterable[int]:
        years = [self.baseline, self.peak_growth, self.recent]
        if self.high_speed_start is not None:
            years.append(self.high_speed_start)
        return sorted(set(years))


def build_category_lookup() -> dict[str, str]:
    lookup: dict[str, str] = {}
    for name in CORE_CITY_NAMES:
        lookup[normalize_name(name)] = "core"
    for name in PORT_INDUSTRIAL_NAMES:
        lookup[normalize_name(name)] = "port_industrial"
    return lookup


def classify_connection(row: pd.Series, lookup: dict[str, str]) -> str:
    start_cat = lookup.get(normalize_name(row["start_station"]), "other")
    end_cat = lookup.get(normalize_name(row["end_station"]), "other")
    categories = {start_cat, end_cat}
    length = float(row["length"])

    if categories == {"core"}:
        if length >= SHORT_DISTANCE_THRESHOLD:
            return "core_core_long"
        return "core_core_short"

    if "core" in categories and "port_industrial" in categories:
        if length < SHORT_DISTANCE_THRESHOLD:
            return "core_port_short"
        return "core_port_long"

    if "core" in categories:
        return "core_other"

    return "non_core"


def summarize_connection_types(tracks_df: pd.DataFrame) -> pd.DataFrame:
    lookup = build_category_lookup()
    tracks = tracks_df.copy()
    tracks["connection_type"] = tracks.apply(lambda row: classify_connection(row, lookup), axis=1)

    agg = (
        tracks.groupby(["year", "connection_type"])
        .agg(
            new_connections=("edge_id", "count"),
            new_length_km=("length", "sum"),
        )
        .reset_index()
    )

    earliest = (
        tracks.groupby("connection_type")["year"].min().rename("first_year").reset_index()
    )

    return agg, earliest


def classify_expansion_phases(summary_df: pd.DataFrame) -> pd.DataFrame:
    summary = summary_df.copy()
    q25 = summary["length_growth_km"].quantile(0.25)
    q75 = summary["length_growth_km"].quantile(0.75)

    def label(growth: float) -> str:
        if growth >= q75:
            return "fast"
        if growth <= q25:
            return "slow"
        return "steady"

    summary["expansion_phase"] = summary["length_growth_km"].map(label)
    return summary


def select_key_years(summary_df: pd.DataFrame) -> KeyYears:
    baseline_year = int(summary_df["year"].min())
    peak_growth_year = int(summary_df.loc[summary_df["length_growth_km"].idxmax(), "year"])
    high_speed_years = summary_df.loc[summary_df["high_speed_length_km"] > 0, "year"]
    high_speed_start = int(high_speed_years.iloc[0]) if not high_speed_years.empty else None
    recent_year = int(summary_df["year"].max())

    return KeyYears(baseline_year, peak_growth_year, high_speed_start, recent_year)


def plot_station_timeseries(summary_df: pd.DataFrame, output_path: Path) -> None:
    fig, ax = plt.subplots(figsize=(10, 5))
    ax.plot(summary_df["year"], summary_df["station_count"], marker="o", color="#1f77b4")
    ax.set_xlabel("Year")
    ax.set_ylabel("Number of Railway Stations")
    ax.set_title("Railway Station Count Time Series")
    ax.grid(True, alpha=0.3)
    fig.tight_layout()
    fig.savefig(output_path, dpi=300)
    plt.close(fig)


def plot_length_timeseries(summary_df: pd.DataFrame, output_path: Path) -> None:
    fig, ax = plt.subplots(figsize=(10, 5))

    ax.plot(
        summary_df["year"],
        summary_df["total_length_km"],
        marker="o",
        color="#2ca02c",
        label="Total Railway Length",
    )
    ax.plot(
        summary_df["year"],
        summary_df["high_speed_length_km"],
        marker="o",
        color="#d62728",
        label="High-Speed Railway Length",
    )

    for phase, color in EXPANSION_COLOR.items():
        phase_df = summary_df[summary_df["expansion_phase"] == phase]
        if phase_df.empty:
            continue
        # Highlight contiguous segments per phase
        segments = np.split(
            phase_df,
            np.where(np.diff(phase_df["year"].values) > 1)[0] + 1,
        )
        for segment in segments:
            ax.axvspan(
                segment["year"].iloc[0] - 0.5,
                segment["year"].iloc[-1] + 0.5,
                color=color,
                alpha=0.08,
            )

    ax.set_xlabel("Year")
    ax.set_ylabel("Railway Length (km)")
    ax.set_title("Railway Length and Expansion Phases")
    ax.legend(loc="upper left")
    ax.grid(True, alpha=0.3)
    fig.tight_layout()
    fig.savefig(output_path, dpi=300)
    plt.close(fig)


def plot_connection_type_timeline(connection_agg: pd.DataFrame, output_path: Path) -> None:
    pivot = connection_agg.pivot_table(
        index="year",
        columns="connection_type",
        values="new_connections",
        fill_value=0,
    ).sort_index()

    fig, ax = plt.subplots(figsize=(10, 5))

    for connection_type, color in CATEGORY_COLORS.items():
        if connection_type not in pivot.columns:
            continue
        ax.plot(
            pivot.index,
            pivot[connection_type].cumsum(),
            label=connection_type,
            color=color,
        )

    ax.set_xlabel("Year")
    ax.set_ylabel("Cumulative New Connections")
    ax.set_title("Cumulative Appearance of Different Connection Types")
    ax.legend(loc="upper left", frameon=False)
    ax.grid(True, alpha=0.3)
    fig.tight_layout()
    fig.savefig(output_path, dpi=300)
    plt.close(fig)


def build_graph(edges_df: pd.DataFrame) -> nx.Graph:
    graph = nx.Graph()
    for _, row in edges_df.iterrows():
        start = normalize_name(row["start_station"])
        end = normalize_name(row["end_station"])
        length = float(row["length"])
        graph.add_edge(start, end, weight=length)
    return graph


def prepare_positions(stations_df: pd.DataFrame) -> dict[str, tuple[float, float]]:
    positions: dict[str, tuple[float, float]] = {}
    for _, row in stations_df.iterrows():
        positions[normalize_name(row["station_name"])] = (row["longitude"], row["latitude"])
    return positions


def plot_network_snapshot(
    tracks_df: pd.DataFrame,
    stations_df: pd.DataFrame,
    year: int,
    output_path: Path,
    highlight_nodes: set[str] | None = None,
) -> None:
    subset = tracks_df[tracks_df["year"] <= year]
    positions = prepare_positions(stations_df)
    fig, ax = plt.subplots(figsize=(8, 8))

    for _, row in subset.iterrows():
        start = normalize_name(row["start_station"])
        end = normalize_name(row["end_station"])
        if start not in positions or end not in positions:
            continue
        x_values = [positions[start][0], positions[end][0]]
        y_values = [positions[start][1], positions[end][1]]
        ax.plot(x_values, y_values, color="#bbbbbb", linewidth=0.7, alpha=0.6)

    xs = []
    ys = []
    colors = []
    sizes = []
    for node, (lon, lat) in positions.items():
        xs.append(lon)
        ys.append(lat)
        if highlight_nodes and node in highlight_nodes:
            colors.append("#d62728")
            sizes.append(40)
        else:
            colors.append("#1f77b4")
            sizes.append(12)

    ax.scatter(xs, ys, c=colors, s=sizes, alpha=0.9)
    ax.set_title(f"Railway Network Spatial Distribution (<= {year})")
    ax.set_xlabel("Longitude")
    ax.set_ylabel("Latitude")
    ax.set_aspect("equal", adjustable="datalim")
    ax.grid(True, alpha=0.2)
    fig.tight_layout()
    fig.savefig(output_path, dpi=300)
    plt.close(fig)


def plot_centrality_map(
    tracks_df: pd.DataFrame,
    stations_df: pd.DataFrame,
    year: int,
    output_path: Path,
) -> None:
    subset = tracks_df[tracks_df["year"] <= year]
    graph = build_graph(subset)
    positions = prepare_positions(stations_df)

    betweenness = nx.betweenness_centrality(graph, weight="weight", normalized=True)
    degree = nx.degree_centrality(graph)

    betweenness_values = np.array([betweenness.get(node, 0.0) for node in graph.nodes])
    degree_values = np.array([degree.get(node, 0.0) for node in graph.nodes])

    norm = mcolors.Normalize(vmin=betweenness_values.min(), vmax=betweenness_values.max() or 1)
    cmap = plt.cm.plasma

    fig, ax = plt.subplots(figsize=(8, 8))

    for _, row in subset.iterrows():
        start = normalize_name(row["start_station"])
        end = normalize_name(row["end_station"])
        if start not in positions or end not in positions:
            continue
        x_values = [positions[start][0], positions[end][0]]
        y_values = [positions[start][1], positions[end][1]]
        ax.plot(x_values, y_values, color="#dddddd", linewidth=0.6, alpha=0.5)

    for node in graph.nodes:
        if node not in positions:
            continue
        lon, lat = positions[node]
        color = cmap(norm(betweenness.get(node, 0.0)))
        size = 40 + 300 * degree.get(node, 0.0)
        ax.scatter(lon, lat, s=size, color=color, edgecolor="#333333", linewidth=0.2, alpha=0.9)

    ax.set_title(f"Node Centrality (<= {year})")
    ax.set_xlabel("Longitude")
    ax.set_ylabel("Latitude")
    ax.set_aspect("equal", adjustable="datalim")
    ax.grid(True, alpha=0.2)

    sm = plt.cm.ScalarMappable(cmap=cmap, norm=norm)
    sm.set_array([])
    cbar = fig.colorbar(sm, ax=ax, fraction=0.03, pad=0.04)
    cbar.set_label("Betweenness Centrality")

    fig.tight_layout()
    fig.savefig(output_path, dpi=300)
    plt.close(fig)


def run_analysis() -> None:
    base_dir = Path(__file__).resolve().parent
    data_dir = base_dir.parent / "data"
    stations_path = data_dir / "stations.csv"
    tracks_path = data_dir / "tracks.csv"

    stations_df = pd.read_csv(stations_path)
    tracks_df = pd.read_csv(tracks_path)

    rail_tracks = prepare_tracks(tracks_df)

    summary_df, _ = compute_growth_summary(stations_df, tracks_df)
    summary_df = classify_expansion_phases(summary_df)

    connection_agg, connection_first = summarize_connection_types(rail_tracks)

    key_years = select_key_years(summary_df)

    results_dir = base_dir.parent / "results"
    figures_dir = results_dir / "figures"
    tables_dir = results_dir / "tables"
    maps_dir = figures_dir / "maps"
    centrality_dir = figures_dir / "centrality"
    figures_dir.mkdir(parents=True, exist_ok=True)
    tables_dir.mkdir(parents=True, exist_ok=True)
    maps_dir.mkdir(parents=True, exist_ok=True)
    centrality_dir.mkdir(parents=True, exist_ok=True)

    plot_station_timeseries(summary_df, figures_dir / "station_timeseries.png")
    plot_length_timeseries(summary_df, figures_dir / "length_timeseries.png")
    plot_connection_type_timeline(connection_agg, figures_dir / "connection_type_timeline.png")

    connection_agg.to_csv(tables_dir / "connection_type_by_year.csv", index=False)
    connection_first.to_csv(tables_dir / "connection_type_first_year.csv", index=False)
    summary_df.to_csv(tables_dir / "growth_summary_with_phase.csv", index=False)

    key_nodes = {normalize_name(name) for name in CORE_CITY_NAMES}
    for year in key_years.iter_years():
        plot_network_snapshot(rail_tracks, stations_df, year, maps_dir / f"network_snapshot_{year}.png", key_nodes)
        plot_centrality_map(rail_tracks, stations_df, year, centrality_dir / f"centrality_{year}.png")

    print("Analysis outputs saved to:", results_dir)
    print("Key years:", list(key_years.iter_years()))


if __name__ == "__main__":
    run_analysis()
