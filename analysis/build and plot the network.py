import os
import pandas as pd
import folium
import itertools
import networkx as nx
import numpy as np
from pathlib import Path
from datetime import datetime


def load_and_process_data(stations_fp: Path, edges_fp: Path, year=None):
    """Load and process station and edge data for a specific year or latest available year"""
    
    # Load datasets
    print(f"Loading station data from: {stations_fp}")
    stations = pd.read_csv(stations_fp)
    
    print(f"Loading edge data from: {edges_fp}")
    edges = pd.read_csv(edges_fp)
    
    # Filter by year if specified, otherwise use the latest year
    if year is None:
        year = stations['year'].max()
        print(f"Using latest available year: {year}")
    else:
        print(f"Filtering data for year: {year}")
    
    stations_filtered = stations[stations['year'] == year].copy()
    edges_filtered = edges[edges['year'] == year].copy()
    
    print(f"Found {len(stations_filtered)} stations and {len(edges_filtered)} edges for year {year}")
    
    return stations_filtered, edges_filtered, year


def build_networkx_graph(stations: pd.DataFrame, edges: pd.DataFrame):
    """Build a NetworkX graph from stations and edges data"""
    
    G = nx.Graph()
    
    # Add nodes (stations) with attributes
    for _, station in stations.iterrows():
        G.add_node(
            station['station_id'],
            longitude=station['longitude'],
            latitude=station['latitude'],
            city_id=station.get('city_id'),
            city_name_chn=station.get('city_name_chn'),
            city_name_eng=station.get('city_name_eng'),
            province_code=station.get('province_code'),
            province_name=station.get('province_name')
        )
    
    # Add edges with attributes
    for _, edge in edges.iterrows():
        source = edge['source_station']
        target = edge['target_station']
        
        # Only add edge if both nodes exist
        if source in G.nodes and target in G.nodes:
            G.add_edge(
                source, 
                target,
                edge_id=edge['edge_id'],
                seg_id=edge['seg_id'],
                length_km=edge['length_km']
            )
    
    print(f"Created NetworkX graph with {G.number_of_nodes()} nodes and {G.number_of_edges()} edges")
    return G


def build_map_by_province(stations: pd.DataFrame, edges: pd.DataFrame, out_fp: Path):
    """Build an interactive folium map with stations grouped by province"""
    
    # Ensure coordinate columns are float
    stations = stations.copy()
    stations['latitude'] = pd.to_numeric(stations['latitude'], errors='coerce')
    stations['longitude'] = pd.to_numeric(stations['longitude'], errors='coerce')
    
    # Remove stations without valid coordinates
    valid_coords = stations.dropna(subset=['latitude', 'longitude'])
    print(f"Building map with {len(valid_coords)} stations with valid coordinates")
    
    # Calculate map center
    center_lat = valid_coords['latitude'].mean()
    center_lon = valid_coords['longitude'].mean()

    m = folium.Map(location=[center_lat, center_lon], zoom_start=5, tiles='CartoDB Positron')

    # Create station coordinate lookup
    station_coords = {}
    for _, row in valid_coords.iterrows():
        station_coords[row['station_id']] = [row['latitude'], row['longitude']]

    # Get unique provinces
    provinces_df = valid_coords[['province_code','province_name']].dropna(subset=['province_code']).drop_duplicates()
    provinces_df = provinces_df[provinces_df['province_code'] != ''].reset_index(drop=True)

    # Color palette for provinces
    palette = [
        '#1f77b4','#ff7f0e','#2ca02c','#d62728','#9467bd','#8c564b','#e377c2','#7f7f7f','#bcbd22','#17becf',
        '#393b79','#5254a3','#6b6ecf','#9c9ede','#637939','#8ca252','#b5cf6b','#cedb9c','#8c6d31','#bd9e39',
    ]
    color_cycle = itertools.cycle(palette)
    province_colors = {}
    province_groups = {}
    
    # Create feature groups for each province
    for _, row in provinces_df.iterrows():
        pcode = row['province_code']
        pname = row['province_name'] if pd.notna(row['province_name']) else f'Province {pcode}'
        color = next(color_cycle)
        province_colors[pcode] = color
        
        fg = folium.FeatureGroup(name=f"{pname}", show=True)
        province_groups[pcode] = fg
        fg.add_to(m)

    # Add feature group for stations without province
    unknown_fg = folium.FeatureGroup(name='Unknown Province', show=True)
    unknown_fg.add_to(m)

    # Add station markers
    for _, station in valid_coords.iterrows():
        sid = station['station_id']
        coord = station_coords.get(sid)
        if coord is None:
            continue
            
        pcode = station.get('province_code')
        if pd.isna(pcode) or pcode == '':
            fg = unknown_fg
            color = 'blue'
        else:
            fg = province_groups.get(pcode, unknown_fg)
            color = province_colors.get(pcode, 'blue')
        
        # Create popup with station info
        popup_text = f"Station: {sid}"
        if pd.notna(station.get('city_name_chn')):
            popup_text += f"<br>City: {station['city_name_chn']}"
        if pd.notna(station.get('province_name')):
            popup_text += f"<br>Province: {station['province_name']}"
            
        popup = folium.Popup(popup_text, max_width=300)
        folium.CircleMarker(
            location=coord, 
            radius=3, 
            color=color, 
            fill=True, 
            fill_opacity=0.8, 
            popup=popup
        ).add_to(fg)

    # Add railway edges
    edges_fg = folium.FeatureGroup(name='Railway Lines', show=True)
    edges_added = 0
    
    for _, edge in edges.iterrows():
        source = edge['source_station']
        target = edge['target_station']
        
        if source in station_coords and target in station_coords:
            source_coord = station_coords[source]
            target_coord = station_coords[target]
            
            # Get color from source station's province
            source_station = valid_coords[valid_coords['station_id'] == source]
            if not source_station.empty:
                source_prov = source_station.iloc[0].get('province_code')
                color = province_colors.get(source_prov, 'red')
            else:
                color = 'red'
            
            folium.PolyLine(
                locations=[source_coord, target_coord], 
                color=color, 
                weight=1.5, 
                opacity=0.6
            ).add_to(edges_fg)
            edges_added += 1
    
    edges_fg.add_to(m)
    print(f"Added {edges_added} railway edges to the map")

    # Add layer control
    folium.LayerControl(collapsed=False).add_to(m)

    # Add legend
    legend_html = '''
    <div style="position: fixed; bottom: 50px; left: 10px; width: 260px; height: 300px; 
                overflow: auto; z-index:9999; background-color: white; padding: 10px; 
                border:2px solid grey; border-radius: 5px;">
        <h4 style="margin:0 0 8px 0;">Provinces</h4>
    '''
    
    for _, row in provinces_df.iterrows():
        pcode = row['province_code']
        pname = row['province_name']
        color = province_colors.get(pcode, '#ccc')
        legend_html += f'''
        <div style="display:flex;align-items:center;margin:3px 0">
            <div style="width:16px;height:12px;background:{color};margin-right:8px;border:1px solid #444"></div>
            <div style="font-size:12px;color:#222">{pname}</div>
        </div>
        '''
    
    legend_html += '</div>'

    from branca.element import Template, MacroElement
    template = Template(legend_html)
    macro = MacroElement()
    macro._template = template
    m.get_root().add_child(macro)

    m.save(str(out_fp))
    print(f"Map saved to: {out_fp}")


def main():
    # Use current directory for data files
    current_dir = Path(__file__).resolve().parent
    station_dataset_fp = current_dir / 'station_dataset.csv'
    edge_dataset_fp = current_dir / 'edge_dataset.csv'
    stations_with_prov_fp = current_dir / 'stations_with_province.csv'

    # Check if required files exist
    if not station_dataset_fp.exists():
        print(f'Station dataset not found: {station_dataset_fp}')
        return
    
    if not edge_dataset_fp.exists():
        print(f'Edge dataset not found: {edge_dataset_fp}')
        return

    # Load and process data
    stations, edges, year = load_and_process_data(station_dataset_fp, edge_dataset_fp)
    
    # If stations_with_province.csv exists, merge the province information
    if stations_with_prov_fp.exists():
        print(f"Loading province information from: {stations_with_prov_fp}")
        prov_data = pd.read_csv(stations_with_prov_fp)
        
        # Create a station_id to province mapping (province assignments are year-independent)
        prov_mapping = prov_data[['station_id', 'province_code', 'province_name']].drop_duplicates()
        
        # Merge province info into stations data
        stations = stations.merge(prov_mapping, on='station_id', how='left')
        
        # Fill missing province info
        stations['province_code'] = stations['province_code'].fillna('')
        stations['province_name'] = stations['province_name'].fillna('')
        
        stations_with_prov_count = len(stations[stations['province_code'] != ''])
        unique_provinces = len(stations[stations['province_code'] != '']['province_name'].unique())
        
        print(f"Merged province information for {stations_with_prov_count} stations")
        print(f"Found stations in {unique_provinces} provinces")
    else:
        print("No province information file found. Creating map without province grouping.")
        stations['province_code'] = ''
        stations['province_name'] = ''

    # Build NetworkX graph
    G = build_networkx_graph(stations, edges)
    
    # Save NetworkX graph
    graph_fp = current_dir / f'rail_network_{year}.gpickle'
    import pickle
    with open(graph_fp, 'wb') as f:
        pickle.dump(G, f)
    print(f"Saved NetworkX graph to: {graph_fp}")
    
    # Generate network statistics
    stats = {
        'year': year,
        'nodes': G.number_of_nodes(),
        'edges': G.number_of_edges(),
        'connected_components': nx.number_connected_components(G),
        'density': nx.density(G),
        'stations_with_province': len(stations[stations['province_code'] != '']),
        'unique_provinces': len(stations[stations['province_code'] != '']['province_code'].unique())
    }
    
    # Save statistics
    stats_fp = current_dir / f'network_stats_{year}.txt'
    with open(stats_fp, 'w', encoding='utf-8') as f:
        f.write(f"Railway Network Statistics for {year}\n")
        f.write("=" * 40 + "\n")
        for key, value in stats.items():
            f.write(f"{key}: {value}\n")
    
    print(f"Network statistics saved to: {stats_fp}")

    # Build interactive map
    out_map = current_dir / f'rail_network_map_{year}.html'
    build_map_by_province(stations, edges, out_map)
    print(f'Interactive map saved to: {out_map}')
    
    # Save processed data for future use
    stations_processed_fp = current_dir / f'stations_processed_{year}.csv'
    edges_processed_fp = current_dir / f'edges_processed_{year}.csv'
    
    stations.to_csv(stations_processed_fp, index=False)
    edges.to_csv(edges_processed_fp, index=False)
    
    print(f"Processed station data saved to: {stations_processed_fp}")
    print(f"Processed edge data saved to: {edges_processed_fp}")
    
    print("\nSummary:")
    print(f"- Year: {year}")
    print(f"- Stations: {len(stations)}")
    print(f"- Railway segments: {len(edges)}")
    print(f"- NetworkX graph: {G.number_of_nodes()} nodes, {G.number_of_edges()} edges")
    print(f"- Stations with province info: {stats['stations_with_province']}")
    print(f"- Unique provinces: {stats['unique_provinces']}")


if __name__ == '__main__':
    main()
