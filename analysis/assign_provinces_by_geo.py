import math
import pandas as pd
import numpy as np
from pathlib import Path


def haversine(lon1, lat1, lon2, lat2):
    # all args can be arrays
    lon1, lat1, lon2, lat2 = map(np.asarray, (lon1, lat1, lon2, lat2))
    lon1 = np.deg2rad(lon1)
    lat1 = np.deg2rad(lat1)
    lon2 = np.deg2rad(lon2)
    lat2 = np.deg2rad(lat2)
    dlon = lon2 - lon1
    dlat = lat2 - lat1
    a = np.sin(dlat/2.0)**2 + np.cos(lat1) * np.cos(lat2) * np.sin(dlon/2.0)**2
    c = 2 * np.arcsin(np.sqrt(a))
    R = 6371.0
    return R * c


# Province name mapping based on ChinaCities_Swerts.csv Province column
PROVINCE_NAME_MAP = {
    'BEIJING': '北京市',
    'TIANJIN': '天津市', 
    'HEBEI': '河北省',
    'SHANXI': '山西省',
    'INNER MONGOLIA': '内蒙古自治区',
    'NEIMENGGU': '内蒙古自治区',  # Alternative name for Inner Mongolia
    'LIAONING': '辽宁省',
    'JILIN': '吉林省',
    'HEILONGJIANG': '黑龙江省',
    'SHANGHAI': '上海市',
    'JIANGSU': '江苏省',
    'ZHEJIANG': '浙江省',
    'ANHUI': '安徽省',
    'FUJIAN': '福建省',
    'JIANGXI': '江西省',
    'SHANDONG': '山东省',
    'HENAN': '河南省',
    'HUBEI': '湖北省',
    'HUNAN': '湖南省',
    'GUANGDONG': '广东省',
    'GUANGXI': '广西壮族自治区',
    'HAINAN': '海南省',
    'CHONGQING': '重庆市',
    'SICHUAN': '四川省',
    'GUIZHOU': '贵州省',
    'YUNNAN': '云南省',
    'TIBET': '西藏自治区',
    'XIZANG': '西藏自治区',  # Alternative name for Tibet
    'SHAANXI': '陕西省',
    'GANSU': '甘肃省',
    'QINGHAI': '青海省',
    'NINGXIA': '宁夏回族自治区',
    'XINJIANG': '新疆维吾尔自治区'
}


def main():
    # Use current directory for data files
    current_dir = Path(__file__).resolve().parent
    repo_root = current_dir.parent
    
    stations_fp = current_dir / 'station_dataset.csv'
    cityinfo_fp = repo_root / 'ChinaCities_Swerts.csv'

    # Read station dataset
    print(f"Reading station data from: {stations_fp}")
    stations = pd.read_csv(stations_fp)
    
    # Read city info (ChinaCities_Swerts.csv format with semicolon separator)
    print(f"Reading city info from: {cityinfo_fp}")
    cities = pd.read_csv(cityinfo_fp, sep=';')
    
    # Filter cities with valid coordinates
    cities = cities.dropna(subset=['Lat', 'Long']).copy()
    print(f"Found {len(stations)} station records and {len(cities)} city records with valid coordinates")
    
    # Get unique stations (remove year dimension)
    unique_stations = stations.drop_duplicates(subset=['station_id']).copy()
    print(f"Found {len(unique_stations)} unique stations")
    
    # Prepare result columns
    unique_stations['province_code'] = ''
    unique_stations['province_name'] = ''
    unique_stations['prov_assign_method'] = ''
    unique_stations['nearest_city'] = ''
    unique_stations['distance_to_city_km'] = np.nan

    # Create city coordinates arrays for distance calculation
    city_names = cities['Name EN'].values
    city_lons = cities['Long'].astype(float).values
    city_lats = cities['Lat'].astype(float).values
    city_provinces = cities['Province'].values

    filled = 0
    no_coords = 0
    
    print("Assigning provinces by nearest city...")
    for idx, row in unique_stations.iterrows():
        try:
            station_lon = float(row['longitude'])
            station_lat = float(row['latitude'])
        except (ValueError, TypeError):
            unique_stations.at[idx, 'prov_assign_method'] = 'no_coords'
            no_coords += 1
            continue

        # Calculate distances to all cities
        dists = haversine(station_lon, station_lat, city_lons, city_lats)
        nearest_idx = np.argmin(dists)
        
        nearest_city = city_names[nearest_idx]
        nearest_dist = dists[nearest_idx]
        nearest_province_en = city_provinces[nearest_idx]
        nearest_province_cn = PROVINCE_NAME_MAP.get(nearest_province_en, nearest_province_en)
        
        unique_stations.at[idx, 'province_code'] = nearest_province_en
        unique_stations.at[idx, 'province_name'] = nearest_province_cn
        unique_stations.at[idx, 'prov_assign_method'] = 'assigned_by_nearest_city'
        unique_stations.at[idx, 'nearest_city'] = nearest_city
        unique_stations.at[idx, 'distance_to_city_km'] = nearest_dist
        filled += 1

    print(f'Assigned province for {filled} stations by nearest city')
    print(f'Skipped {no_coords} stations without valid coordinates')

    # Save updated stations file
    out_fp = current_dir / 'stations_with_province.csv'
    unique_stations.to_csv(out_fp, index=False)

    # Save a detailed report
    report_lines = []
    report_lines.append(f'Station Province Assignment Report')
    report_lines.append(f'Generated: {pd.Timestamp.now()}')
    report_lines.append(f'')
    report_lines.append(f'Total unique stations: {len(unique_stations)}')
    report_lines.append(f'Stations with province assigned: {filled}')
    report_lines.append(f'Stations without coordinates: {no_coords}')
    report_lines.append(f'')
    
    # Province distribution
    prov_dist = unique_stations['province_name'].value_counts()
    report_lines.append('Province distribution:')
    for prov, count in prov_dist.items():
        report_lines.append(f'  {prov}: {count} stations')
    
    report_lines.append(f'')
    # Distance statistics
    valid_dists = unique_stations['distance_to_city_km'].dropna()
    if len(valid_dists) > 0:
        report_lines.append('Distance to nearest city statistics:')
        report_lines.append(f'  Mean: {valid_dists.mean():.2f} km')
        report_lines.append(f'  Median: {valid_dists.median():.2f} km')
        report_lines.append(f'  Min: {valid_dists.min():.2f} km')
        report_lines.append(f'  Max: {valid_dists.max():.2f} km')

    report_fp = current_dir / 'assign_province_report.txt'
    report_fp.write_text('\n'.join(report_lines), encoding='utf-8')

    print(f'Wrote updated stations to {out_fp}')
    print(f'Wrote report to {report_fp}')


if __name__ == '__main__':
    main()
