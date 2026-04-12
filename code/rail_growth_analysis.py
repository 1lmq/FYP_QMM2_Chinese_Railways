"""Generate railway system growth charts.

This script aggregates station counts and rail lengths by year and saves two
charts to help identify network expansion phases.
"""
from __future__ import annotations

from pathlib import Path
import re
import unicodedata

import matplotlib.pyplot as plt
import pandas as pd


TYPE_MAPPING = {
    "rail_both": "rail_both",
    "rail_good": "rail_good",
    "rail pass": "rail_pass",
    "road": "road",
}
HIGH_SPEED_TYPES = {"rail_pass"}


def normalize_name(name: str) -> str:
    """Normalize station names for consistent matching."""
    if pd.isna(name):
        return ""
    text = str(name)
    text = unicodedata.normalize("NFKC", text)
    text = text.strip()
    text = re.sub(r"\s+", " ", text)
    text = re.sub(r"[\(\)\[\]\\/\-\.,。,··•\"]+", "", text)
    return text.lower()


def map_station_ids(stations_df: pd.DataFrame) -> dict[str, str]:
    mapping: dict[str, str] = {}
    for _, row in stations_df.iterrows():
        normalized = normalize_name(row["station_name"])
        if normalized and normalized not in mapping:
            mapping[normalized] = row["station_id"]
    return mapping


def prepare_tracks(tracks_df: pd.DataFrame) -> pd.DataFrame:
    tracks = tracks_df.copy()
    tracks["type_standard"] = tracks["type"].map(TYPE_MAPPING).fillna(tracks["type"])
    rail_tracks = tracks[tracks["type_standard"].str.contains("rail", case=False, na=False)].copy()
    rail_tracks = rail_tracks.dropna(subset=["year", "length"])
    rail_tracks["year"] = rail_tracks["year"].astype(int)
    rail_tracks["length"] = rail_tracks["length"].astype(float)
    return rail_tracks.sort_values("year")


def compute_growth_summary(stations_df: pd.DataFrame, tracks_df: pd.DataFrame) -> tuple[pd.DataFrame, set[str]]:
    name_to_id = map_station_ids(stations_df)
    rail_tracks = prepare_tracks(tracks_df)

    rail_tracks["start_id"] = rail_tracks["start_station"].map(lambda x: name_to_id.get(normalize_name(x)))
    rail_tracks["end_id"] = rail_tracks["end_station"].map(lambda x: name_to_id.get(normalize_name(x)))

    missing_stations: set[str] = set()
    for column in ("start_id", "end_id"):
        missing_mask = rail_tracks[column].isna()
        if missing_mask.any():
            source_col = "start_station" if column == "start_id" else "end_station"
            missing_stations.update(rail_tracks.loc[missing_mask, source_col].map(normalize_name))

    years = sorted(rail_tracks["year"].unique())
    cumulative_stations: set[str] = set()
    total_length = 0.0
    high_speed_length = 0.0

    records: list[dict[str, float]] = []

    for year in years:
        year_slice = rail_tracks[rail_tracks["year"] == year]

        for _, row in year_slice.iterrows():
            if isinstance(row["start_id"], str):
                cumulative_stations.add(row["start_id"])
            if isinstance(row["end_id"], str):
                cumulative_stations.add(row["end_id"])

        total_length += year_slice["length"].sum()
        high_speed_length += year_slice.loc[
            year_slice["type_standard"].isin(HIGH_SPEED_TYPES), "length"
        ].sum()

        records.append(
            {
                "year": year,
                "station_count": len(cumulative_stations),
                "total_length_km": total_length,
                "high_speed_length_km": high_speed_length,
            }
        )

    summary_df = pd.DataFrame(records)
    summary_df["station_growth"] = summary_df["station_count"].diff().fillna(summary_df["station_count"])
    summary_df["length_growth_km"] = summary_df["total_length_km"].diff().fillna(summary_df["total_length_km"])
    summary_df["high_speed_growth_km"] = summary_df["high_speed_length_km"].diff().fillna(
        summary_df["high_speed_length_km"]
    )

    return summary_df, missing_stations


def plot_growth(summary_df: pd.DataFrame, output_path: Path) -> None:
    plt.style.use("seaborn-v0_8-darkgrid")
    fig, axes = plt.subplots(2, 1, sharex=True, figsize=(11, 8))

    axes[0].plot(summary_df["year"], summary_df["station_count"], marker="o", color="#1f77b4")
    axes[0].set_ylabel("Number of stations")

    axes[1].plot(
        summary_df["year"],
        summary_df["total_length_km"],
        marker="o",
        color="#2ca02c",
        label="Total rail length",
    )
    axes[1].plot(
        summary_df["year"],
        summary_df["high_speed_length_km"],
        marker="o",
        color="#d62728",
        label="High-speed length",
    )
    axes[1].set_ylabel("Length (km)")
    axes[1].legend(loc="upper left")

    axes[1].set_xlabel("Year")
    fig.suptitle("China railway system growth")
    fig.tight_layout()
    fig.savefig(output_path, dpi=300)
    plt.close(fig)


def main() -> None:
    base_dir = Path(__file__).resolve().parent
    data_dir = base_dir.parent / "data"
    results_dir = base_dir.parent / "results" / "tables"
    results_dir.mkdir(parents=True, exist_ok=True)
    stations_path = data_dir / "stations.csv"
    tracks_path = data_dir / "tracks.csv"
    output_csv = results_dir / "rail_growth_summary.csv"
    output_png = base_dir.parent / "results" / "figures" / "rail_growth_trends.png"

    if not stations_path.exists() or not tracks_path.exists():
        raise FileNotFoundError("Required CSV files are missing in the network directory.")

    stations_df = pd.read_csv(stations_path)
    tracks_df = pd.read_csv(tracks_path)

    summary_df, missing_stations = compute_growth_summary(stations_df, tracks_df)

    summary_df.to_csv(output_csv, index=False)
    plot_growth(summary_df, output_png)

    print(f"Summary saved to {output_csv.name}")
    print(f"Chart saved to {output_png.name}")
    if missing_stations:
        print(f"Unmatched station names: {len(missing_stations)} (see console log for normalized forms)")


if __name__ == "__main__":
    main()
