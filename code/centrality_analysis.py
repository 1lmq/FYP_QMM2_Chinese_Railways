import os
import re
import unicodedata
from pathlib import Path
from typing import Dict, List

import networkx as nx
import pandas as pd


def normalize_name(name: str) -> str:
    """Normalize station names for consistent matching."""
    if pd.isna(name):
        return ""
    text = str(name)
    text = unicodedata.normalize("NFKC", text)
    text = text.strip()
    text = re.sub(r"\s+", " ", text)
    text = re.sub(r"[\(\)\[\]\\/\\\-\.,。,··•\"]+", "", text)
    return text.lower()


def load_data(stations_path: Path, tracks_path: Path) -> tuple[pd.DataFrame, pd.DataFrame]:
    stations_df = pd.read_csv(stations_path)
    tracks_df = pd.read_csv(tracks_path)
    return stations_df, tracks_df


def map_station_ids(stations_df: pd.DataFrame) -> Dict[str, str]:
    mapping: Dict[str, str] = {}
    for _, row in stations_df.iterrows():
        normalized = normalize_name(row["station_name"])
        if normalized:
            mapping[normalized] = row["station_id"]
    return mapping


def prepare_tracks(tracks_df: pd.DataFrame, name_to_id: Dict[str, str]) -> pd.DataFrame:
    tracks_df = tracks_df.copy()
    tracks_df["start_id"] = tracks_df["start_station"].map(lambda x: name_to_id.get(normalize_name(x)))
    tracks_df["end_id"] = tracks_df["end_station"].map(lambda x: name_to_id.get(normalize_name(x)))
    tracks_df = tracks_df.dropna(subset=["start_id", "end_id", "year"])
    tracks_df["year"] = tracks_df["year"].astype(int)
    tracks_df = tracks_df.sort_values("year")
    return tracks_df


def initialize_graph(stations_df: pd.DataFrame) -> nx.Graph:
    graph = nx.Graph()
    for _, row in stations_df.iterrows():
        graph.add_node(
            row["station_id"],
            station_name=row["station_name"],
            province=row.get("province"),
            latitude=row.get("latitude"),
            longitude=row.get("longitude"),
        )
    return graph


def add_edge_with_min_length(graph: nx.Graph, start_id: str, end_id: str, length: float, edge_year: int) -> None:
    if graph.has_edge(start_id, end_id):
        existing_length = graph[start_id][end_id].get("length", length)
        graph[start_id][end_id]["length"] = min(existing_length, length)
        years: List[int] = graph[start_id][end_id].setdefault("years", [])
        if edge_year not in years:
            years.append(edge_year)
    else:
        graph.add_edge(start_id, end_id, length=length, years=[edge_year])


def compute_centrality_over_time(stations_df: pd.DataFrame, tracks_df: pd.DataFrame) -> pd.DataFrame:
    name_to_id = map_station_ids(stations_df)
    prepared_tracks = prepare_tracks(tracks_df, name_to_id)

    if prepared_tracks.empty:
        raise ValueError("No usable track records with valid station mappings and years.")

    graph = initialize_graph(stations_df)
    unique_years = sorted(prepared_tracks["year"].unique())
    track_records = prepared_tracks.to_dict("records")
    record_index = 0

    results: List[dict] = []

    for year in unique_years:
        while record_index < len(track_records) and track_records[record_index]["year"] <= year:
            record = track_records[record_index]
            add_edge_with_min_length(
                graph,
                record["start_id"],
                record["end_id"],
                float(record.get("length", 1.0) or 1.0),
                record["year"],
            )
            record_index += 1

        active_nodes = [node for node in graph.nodes if graph.degree(node) > 0]

        if not active_nodes:
            continue

        active_subgraph = graph.subgraph(active_nodes).copy()

        degree_centrality = nx.degree_centrality(active_subgraph)
        betweenness_centrality = nx.betweenness_centrality(active_subgraph, weight="length", normalized=True)
        closeness_centrality = nx.closeness_centrality(active_subgraph, distance="length", wf_improved=True)

        for node in active_nodes:
            node_data = graph.nodes[node]
            results.append(
                {
                    "year": year,
                    "station_id": node,
                    "station_name": node_data.get("station_name"),
                    "province": node_data.get("province"),
                    "degree_centrality": degree_centrality.get(node, 0.0),
                    "betweenness_centrality": betweenness_centrality.get(node, 0.0),
                    "closeness_centrality": closeness_centrality.get(node, 0.0),
                }
            )

    centrality_df = pd.DataFrame(results)
    centrality_df = centrality_df.sort_values(["year", "station_id"]).reset_index(drop=True)
    return centrality_df


def main() -> Path:
    script_dir = Path(__file__).parent.resolve()
    stations_path = script_dir / "stations.csv"
    tracks_path = script_dir / "tracks.csv"
    output_path = script_dir / "centrality_by_year.csv"

    if not stations_path.exists() or not tracks_path.exists():
        missing = [str(path.name) for path in [stations_path, tracks_path] if not path.exists()]
        raise FileNotFoundError(f"Missing required CSV files: {', '.join(missing)}")

    stations_df, tracks_df = load_data(stations_path, tracks_path)
    centrality_df = compute_centrality_over_time(stations_df, tracks_df)
    centrality_df.to_csv(output_path, index=False)
    return output_path


if __name__ == "__main__":
    try:
        output_file = main()
        print(f"Centrality export completed: {output_file}")
    except Exception as exc:
        print(f"Failed to compute centralities: {exc}")
