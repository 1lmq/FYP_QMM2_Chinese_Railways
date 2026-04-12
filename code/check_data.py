import pandas as pd

s = pd.read_csv('../data/stations.csv')
t = pd.read_csv('../data/tracks.csv')

print("【数据规模统计】")
print(f"站点数: {len(s)}")
print(f"轨道记录数: {len(t)}")
print(f"年份范围: {t['year'].min():.0f} - {t['year'].max():.0f}")
print(f"\n网络特性:")
print(f"涉及省份: {s['province'].nunique()}")
print(f"平均每站点的轨道数: {len(t)/len(s):.2f}")
