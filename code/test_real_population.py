"""
快速验证：真实人口数据加载测试
"""

from population_weighted_robustness import RailNetworkBuilder

# 文件路径
stations_file = r"../data/stations.csv"
tracks_file = r"../data/tracks.csv"
population_file = r"../data/ChinaCities_Swerts.csv"

print("【真实人口数据加载测试】\n")

# 构建网络
print("[1] 构建网络...")
builder = RailNetworkBuilder(stations_file, tracks_file, population_file)
graph = builder.build_network(year=None, simplify=True)

info = builder.get_network_info()
print(f"✓ 网络已构建：{info['number_of_nodes']} 个节点，{info['number_of_edges']} 条边")

# 加载真实人口数据
print("\n[2] 加载真实人口数据...")
population_dict = builder.load_real_population_data(year=2010)

print(f"\n【数据统计】")
print(f"✓ 已加载 {len(population_dict)} 个城市的人口数据")
print(f"✓ 总服务人口：{sum(population_dict.values())/1e8:.2f}亿人")

# 显示前10个城市
print(f"\n【前10个城市的人口数据】")
for i, (city, pop) in enumerate(sorted(population_dict.items(), 
                                       key=lambda x: x[1], 
                                       reverse=True)[:10]):
    print(f"{i+1:2d}. {city:12s} {pop:12,.0f} 人 ({pop/1e7:.1f}百万)")

# 检查数据覆盖率
print(f"\n【数据覆盖分析】")
total_nodes = info['number_of_nodes']
nodes_with_population = sum(1 for n in graph.nodes() 
                           if builder.node_populations.get(n, 0) > 0)
coverage_rate = (nodes_with_population / total_nodes) * 100
print(f"✓ 网络节点总数：{total_nodes}")
print(f"✓ 有人口数据的节点：{nodes_with_population}")
print(f"✓ 数据覆盖率：{coverage_rate:.1f}%")

# 检查5个最大的节点
print(f"\n【网络中5个最大的节点（按人口）】")
top_nodes = sorted([(n, builder.node_populations.get(n, 0)) 
                    for n in graph.nodes()],
                   key=lambda x: x[1],
                   reverse=True)[:5]
for i, (node, pop) in enumerate(top_nodes):
    print(f"{i+1}. {node:15s} {pop:12,.0f} 人" if pop > 0 else f"{i+1}. {node:15s} (无数据)")

print("\n✅ 真实人口数据加载成功！可以运行主程序了。")
print("   命令：python population_weighted_robustness.py")
