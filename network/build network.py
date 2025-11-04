import networkx as nx
import pandas as pd
import folium
import os
import itertools
import numpy as np
from pathlib import Path
from folium import plugins
import unicodedata
import re

def normalize_name(name):
    """规范化站点名称以改善匹配"""
    if pd.isna(name):
        return ""
    s = str(name)
    s = unicodedata.normalize('NFKC', s)  # Unicode规范化
    s = s.strip()  # 去除首尾空格
    s = re.sub(r'\s+', ' ', s)  # 统一内部空格
    s = re.sub(r'[\(\)\[\]\\/\\\-\.,。,··•"]+', '', s)  # 去除常见标点
    return s.lower()

def main():
    """Main function containing all execution logic"""
    try:
        print("🚄 Railway Network Visualization Script")
        print("=" * 50)
        
        # Get script directory
        script_dir = Path(__file__).parent.absolute()
        os.chdir(script_dir)
        print(f"📂 Working Directory: {os.getcwd()}")
        
        # Check required files
        required_files = ['stations.csv', 'tracks.csv']
        for file in required_files:
            if not os.path.exists(file):
                raise FileNotFoundError(f"Missing required file: {file}")
        
        # Load data
        print("\n📊 Loading data...")
        stations_df = pd.read_csv('stations.csv')
        tracks_df = pd.read_csv('tracks.csv')
        print(f"✓ Loaded {len(stations_df)} stations")
        print(f"✓ Loaded {len(tracks_df)} track records")
        
        # Create station mapping using normalized names
        name_to_id = {}
        for _, row in stations_df.iterrows():
            normalized = normalize_name(row['station_name'])
            name_to_id[normalized] = row['station_id']
        
        # Create network graph - Using MultiDiGraph to preserve parallel edges
        print("\n🔗 Building network graph...")
        G = nx.MultiDiGraph()
        
        # Add nodes
        for _, row in stations_df.iterrows():
            G.add_node(row['station_id'], 
                      name=row['station_name'], 
                      province=row['province'],
                      latitude=row['latitude'], 
                      longitude=row['longitude'])
        
        # Create track type mapping to standardize names
        type_mapping = {
            'rail_both': 'rail_both',
            'rail_good': 'rail_good', 
            'rail pass': 'rail_pass',  # Map 'rail pass' to 'rail_pass'
            'road': 'road'
        }
        
        # Apply type mapping
        tracks_df['type_standardized'] = tracks_df['type'].map(type_mapping).fillna(tracks_df['type'])
        
        # Add edges
        edges_added = 0
        missing_stations = []
        
        for _, row in tracks_df.iterrows():
            start_name = row['start_station'] 
            end_name = row['end_station']
            # 使用规范化名称进行匹配
            start_normalized = normalize_name(start_name)
            end_normalized = normalize_name(end_name)
            start_id = name_to_id.get(start_normalized)
            end_id = name_to_id.get(end_normalized)
            
            if start_id and end_id:
                # 严格遵守"不推断年份"规则 - 仅使用CSV原始年份
                year_val = row['year'] if pd.notna(row['year']) else None
                year_int = int(year_val) if year_val is not None else None
                
                G.add_edge(start_id, end_id, 
                          length=row['length'], 
                          year=year_int, 
                          year_raw=row['year'],  # 保存原始值
                          type=row['type_standardized'],
                          edge_id=row.get('edge_id'))
                edges_added += 1
            else:
                if not start_id:
                    missing_stations.append(start_name)
                if not end_id:
                    missing_stations.append(end_name)
        
        print(f"✓ Successfully added {edges_added} edges")
        if missing_stations:
            unique_missing = list(set(missing_stations))
            print(f"⚠️ {len(unique_missing)} stations not found")
        
        # Province color configuration
        province_list = list(set(nx.get_node_attributes(G, 'province').values()))
        colors = ['#FF6B6B', '#4ECDC4', '#45B7D1', '#96CEB4', '#FFEAA7', '#DDA0DD', 
                  '#98D8C8', '#F7DC6F', '#BB8FCE', '#85C1E9', '#F8C471', '#82E0AA',
                  '#AED6F1', '#F5B7B1', '#D2B4DE', '#A3E4D7', '#F9E79F', '#FADBD8']
        color_map = {province: colors[i % len(colors)] for i, province in enumerate(province_list)}
        
        # Track type configuration
        type_colors = {
            'rail_both': '#FF0000',
            'rail_good': '#008000',
            'rail_pass': '#0000FF',
            'road': '#0066CC',
        }
        
        type_names = {
            'rail_both': 'rail_both',
            'rail_good': 'rail_good',
            'rail_pass': 'rail_pass',
            'road': 'road'
        }
        
        print(f"✓ Assigned colors to {len(province_list)} provinces")
        
        # Prepare map data
        print("\n🗺️ Preparing map data...")
        
        # Create station data
        stations_for_map = []
        for node in G.nodes():
            node_data = G.nodes[node]
            if not pd.isna(node_data.get('latitude')) and not pd.isna(node_data.get('longitude')):
                stations_for_map.append({
                    'station_id': node,
                    'station_name': node_data['name'],
                    'province': node_data['province'],
                    'latitude': node_data['latitude'],
                    'longitude': node_data['longitude'],
                    'color': color_map[node_data['province']]
                })
        
        stations_map_df = pd.DataFrame(stations_for_map)
        
        # Create edge data - MultiDiGraph requires keys parameter for iteration
        edges_for_map = []
        rail_edges_total = 0
        
        for u, v, key, edge_data in G.edges(keys=True, data=True):
            # 只处理轨道类型的边
            if not (edge_data.get('type', '').lower().find('rail') != -1):
                continue
                
            rail_edges_total += 1
            source_node = G.nodes[u]
            target_node = G.nodes[v]
            
            if (not pd.isna(source_node.get('latitude')) and not pd.isna(source_node.get('longitude')) and
                not pd.isna(target_node.get('latitude')) and not pd.isna(target_node.get('longitude'))):
                
                edges_for_map.append({
                    'start_lat': source_node['latitude'],
                    'start_lon': source_node['longitude'],
                    'end_lat': target_node['latitude'], 
                    'end_lon': target_node['longitude'],
                    'start_name': source_node['name'],
                    'end_name': target_node['name'],
                    'length': edge_data['length'],
                    'year': edge_data.get('year'),
                    'year_raw': edge_data.get('year_raw'),
                    'edge_id': edge_data.get('edge_id'),
                    'type': edge_data['type']
                })
        
        print(f"✓ Prepared {len(stations_for_map)} stations and {len(edges_for_map)} connections")
        print(f"✓ Total rail edges in network: {rail_edges_total}")
        print(f"✓ Rail edges with coordinates: {len(edges_for_map)}")
        
        # Create map
        print("\n🎨 Creating Folium map...")
        center_lat = stations_map_df['latitude'].mean()
        center_lon = stations_map_df['longitude'].mean()
        
        m = folium.Map(location=[center_lat, center_lon], zoom_start=5, tiles='CartoDB Positron')
        
        # Group by track type
        track_types = {}
        for edge in edges_for_map:
            track_type = edge['type']
            if track_type not in track_types:
                track_types[track_type] = []
            track_types[track_type].append(edge)
        
        # Add track type layers
        track_feature_groups = {}
        for track_type, type_name in type_names.items():
            edges_count = len(track_types.get(track_type, []))
            if edges_count > 0:
                fg = folium.FeatureGroup(name=f"{type_name} ({edges_count} tracks)", show=True)
                track_feature_groups[track_type] = fg
                fg.add_to(m)
        
        # Add track connection lines
        for track_type, edges in track_types.items():
            if len(edges) > 0 and track_type in track_feature_groups:
                color = type_colors.get(track_type, '#808080')
                fg = track_feature_groups[track_type]
                
                for edge in edges:
                    coordinates = [
                        [edge['start_lat'], edge['start_lon']],
                        [edge['end_lat'], edge['end_lon']]
                    ]
                    
                    # 年份显示 - 严格按原始CSV，不推断
                    year_val = edge.get('year')
                    year_display = int(year_val) if (year_val is not None and not pd.isna(year_val)) else '年份缺失'
                    
                    edge_id_text = f"Edge ID: {edge.get('edge_id', 'N/A')}<br>" if edge.get('edge_id') else ""
                    popup_text = f"""
                    <b>轨道连接</b><br>
                    {edge_id_text}起点: {edge['start_name']}<br>
                    终点: {edge['end_name']}<br>
                    <b>长度:</b> {edge['length']:.2f} km<br>
                    <b>建设年份:</b> {year_display}<br>
                    <b>轨道类型:</b> {type_names.get(edge['type'], edge['type'])}
                    """
                    
                    year_text = str(int(year_val)) if (year_val is not None and not pd.isna(year_val)) else '年份缺失'
                    tooltip_content = f"""
                    <div style='font-size: 12px; font-weight: bold;'>
                        <div>🚂 {edge['start_name']} ↔ {edge['end_name']}</div>
                        <div>📏 Length: {edge['length']:.1f}km</div>
                        <div>📅 Built: {year_text}</div>
                        <div>🛤️ Type: {type_names.get(edge['type'], edge['type'])}</div>
                    </div>
                    """
                    
                    folium.PolyLine(
                        locations=coordinates,
                        color=color,
                        weight=2.5,
                        opacity=0.8,
                        popup=folium.Popup(popup_text, max_width=300),
                        tooltip=folium.Tooltip(tooltip_content, permanent=False, sticky=True)
                    ).add_to(fg)
        
        # Add province layers
        province_counts = [(province, len(stations_map_df[stations_map_df['province'] == province])) 
                          for province in province_list]
        province_counts.sort(key=lambda x: x[1], reverse=True)
        
        province_feature_groups = {}
        for province, count in province_counts:
            if count > 0:
                fg = folium.FeatureGroup(name=f"🚉 {province} ({count} stations)", show=True)
                province_feature_groups[province] = fg
                fg.add_to(m)
        
        # Add station markers
        for province, count in province_counts:
            if count > 0 and province in province_feature_groups:
                province_stations = stations_map_df[stations_map_df['province'] == province]
                fg = province_feature_groups[province]
                color = color_map[province]
                
                for _, station in province_stations.iterrows():
                    station_connections = sum(1 for edge in edges_for_map 
                                            if edge['start_name'] == station['station_name'] or 
                                               edge['end_name'] == station['station_name'])
                    
                    popup_text = f"""
                    <b>{station['station_name']}</b><br>
                    <b>Province:</b> {station['province']}<br>
                    <b>Coordinates:</b> ({station['latitude']:.2f}°N, {station['longitude']:.2f}°E)<br>
                    <b>Track Connections:</b> {station_connections} tracks<br>
                    <b>Station ID:</b> {station['station_id']}
                    """
                    
                    folium.CircleMarker(
                        location=[station['latitude'], station['longitude']],
                        radius=4,
                        popup=folium.Popup(popup_text, max_width=300),
                        color='white',
                        weight=1,
                        fillColor=color,
                        fillOpacity=0.7,
                        tooltip=station['station_name']
                    ).add_to(fg)
        
        # Add map controls
        folium.LayerControl(collapsed=False).add_to(m)
        plugins.Fullscreen().add_to(m)
        plugins.MeasureControl().add_to(m)
        
        # Add statistics information
        stats_html = f"""
        <div style="position: fixed; 
             top: 20px; left: 50%; transform: translateX(-50%); 
             width: 320px; height: 140px; 
             background-color: rgba(255, 255, 255, 0.95); 
             border: 3px solid #2c3e50; 
             z-index: 9999; 
             font-size: 14px; 
             padding: 15px; 
             border-radius: 10px;
             box-shadow: 0 4px 8px rgba(0,0,0,0.3);
             text-align: center;">
        <h3 style="margin: 0 0 12px 0; color: #2c3e50; font-weight: bold;">🚄 Railway Network Statistics</h3>
        <div style="display: grid; grid-template-columns: 1fr 1fr; gap: 8px; text-align: left;">
            <div><strong>🚉 Total Stations:</strong> {len(stations_for_map)}</div>
            <div><strong>🛤️ Track Connections:</strong> {len(edges_for_map)}</div>
            <div><strong>🗺️ Provinces Covered:</strong> {len(province_list)}</div>
            <div><strong>📊 Track Types:</strong> {len(track_types)}</div>
        </div>
        </div>
        """
        
        m.get_root().html.add_child(folium.Element(stats_html))
        
        # Save map
        output_file = 'railway_network_folium.html'
        m.save(output_file)
        print(f"✓ Map saved to: {output_file}")
        
        # Connectivity analysis
        print(f"\n📈 Network Analysis Results:")
        print(f"- Nodes: {len(G.nodes())}")
        print(f"- Edges: {len(G.edges())}")
        
        if G.number_of_edges() > 0:
            G_undirected = G.to_undirected()
            components = nx.number_connected_components(G_undirected)
            print(f"- Connected Components: {components}")
            
            if components == 1:
                print("✓ Network is fully connected")
            else:
                largest_component = max(nx.connected_components(G_undirected), key=len)
                print(f"- Largest Connected Component: {len(largest_component)} stations")
        
        # Province statistics
        province_stats = stations_df['province'].value_counts()
        print(f"\n📊 Covers {len(province_stats)} provinces:")
        for province, count in province_stats.head(10).items():
            print(f"  {province}: {count} stations")
        
        return True
        
    except FileNotFoundError as e:
        print(f"\n❌ File Error: {e}")
        print("💡 Please check if the following files exist:")
        print("   - stations.csv")
        print("   - tracks.csv")
        return False
        
    except pd.errors.EmptyDataError:
        print(f"\n❌ Data file is empty or format error")
        print("💡 Please check if CSV files contain valid data")
        return False
        
    except ImportError as e:
        print(f"\n❌ Missing dependency: {e}")
        print("💡 Please run the following command to install:")
        print("   pip install networkx pandas folium numpy")
        return False
        
    except Exception as e:
        print(f"\n❌ Unexpected error: {e}")
        print(f"   Error type: {type(e).__name__}")
        return False

if __name__ == "__main__":
    print("🚄 China Railway Network Visualization Tool")
    print("=" * 60)
    
    success = main()
    
    if success:
        print("\n✅ Script execution completed!")
        print("📁 Output file: railway_network_folium.html")
        print(f"📍 File location: {os.getcwd()}")
    else:
        print("\n❌ Script execution failed")
        print("💡 Please check error messages and retry")
    
    print(f"\n🕒 Completion time: {pd.Timestamp.now().strftime('%Y-%m-%d %H:%M:%S')}")
    input("Press Enter to exit...")