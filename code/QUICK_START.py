"""
快速参考卡 - 40秒上手指南
===========================

这是最简洁的使用说明，让您在40秒内了解框架的核心用法。
详细文档见 README_ROBUSTNESS.md
"""

# =========================================================================
# 【第1步】安装依赖 (仅需一次)
# =========================================================================

"""
在终端/命令行中运行：
    pip install pandas numpy networkx matplotlib scipy seaborn
    
或使用一键安装：
    pip install -r requirements.txt
"""

# =========================================================================
# 【第2步】运行完整分析 (一键执行，无需编码)
# =========================================================================

"""
在 code 目录下运行：
    python population_weighted_robustness.py

将自动输出：
✓ robustness_curves.png - 三种攻击策略的对比曲线
✓ detailed_comparison.png - 4合1详细分析
✓ network_structure.png - 网络拓扑（节点大小=人口）
✓ analysis_report.txt - 学术解释与建议
✓ CSV数据表 - 可在Excel中查看
"""

# =========================================================================
# 【第3步】(可选) Python代码自定义分析
# =========================================================================

from population_weighted_robustness import (
    RailNetworkBuilder, FailureSimulator,
    RobustnessCalculator, RobustnessVisualizer
)

# 1️⃣ 加载数据 + 构建网络
builder = RailNetworkBuilder(
    r"../data/stations.csv",
    r"../data/tracks.csv"
)
graph = builder.build_network(year=None)  # None=全部数据，或指定年份如2020

# 2️⃣ 分配人口和权重
builder.generate_synthetic_population(
    strategy='provincial_based'  # 或 'degree_based', 'uniform'
)
builder.assign_node_weights(
    strategy='economic_importance'  # 或 'uniform', 'geographic_centrality'
)

# 3️⃣ 执行故障模拟
calculator = RobustnessCalculator(
    graph,
    builder.node_populations,
    builder.node_weights
)

# 分析单一策略
simulator = FailureSimulator(graph)
failures = simulator.simulate_cascade_failure(
    failure_mode='betweenness',  # 或 'random', 'degree'
    alpha_steps=20                # 故障强度的分割数
)
result = calculator.analyze_failure_impact(failures, use_weights=True)

# 4️⃣ 可视化
RobustnessVisualizer.plot_robustness_curves(
    {'介数中心性攻击': result},
    save_path="my_analysis.png"
)

# =========================================================================
# 【核心公式】
# =========================================================================

"""
人口加权鲁棒性：
    Rw(α) = 1 - [失联人口] / [总人口]
    
    α = 故障强度 (0~1) = 移除的节点数 / 总节点数
    
    Rw值解释：
    ✓ 0.9-1.0: 网络健康
    ⚠️ 0.7-0.9: 部分受损
    ❌ 0.3-0.7: 严重受损
    💥 0.0-0.3: 基本瘫痪
"""

# =========================================================================
# 【三种故障模式对比】
# =========================================================================

"""
┌────────────────┬──────────────┬──────────────┬──────────────┐
│ 特征           │ 随机失效     │ 度中心性     │ 介数中心性   │
├────────────────┼──────────────┼──────────────┼──────────────┤
│ 破坏力度       │ ⭐           │ ⭐⭐        │ ⭐⭐⭐       │
│ 现实场景       │ 自然灾害     │ 蓄意破坏枢纽 │ 关键点失效   │
│ 优先防御程度   │ 低           │ 中           │ 🔴 高       │
│ 网络分片速度   │ 缓慢         │ 中等         │ 快速         │
└────────────────┴──────────────┴──────────────┴──────────────┘

🎯 重点：介数中心性攻击最危险！
   这些节点虽不是度数最高的，但充当"桥梁"角色，
   移除导致网络快速分裂，人口大幅离线。
"""

# =========================================================================
# 【常用参数速查】
# =========================================================================

"""
参数                    默认值           说明
────────────────────────────────────────────────────────────
network_year            None            None=全部数据，或指定2020等
population_strategy     provincial      provincial/degree/uniform
weight_strategy         economic        economic/uniform/geographic
failure_mode            betweenness     random/degree/betweenness ⭐
alpha_steps             20              14-25之间较优（步数越多越精细）
use_weights             True            是否考虑节点权重
"""

# =========================================================================
# 【快速示例】
# =========================================================================

"""
场景1：我只想快速看结果
→ 直接运行：python population_weighted_robustness.py
→ 等待2-5分钟，自动生成图表和报告

场景2：我想分析特定年份(如2020年)
→ 修改第一行：graph = builder.build_network(year=2020)
→ 其余代码不变

场景3：我想加入实际人口数据
→ population_dict = {'北京市': 2171e4, '上海市': 2428e4, ...}
→ builder.assign_population_data(population_dict)
→ 不要调用 generate_synthetic_population()

场景4：我想比较不同权重的影响
→ 导入：from advanced_robustness_analysis import ParameterSensitivityAnalyzer
→ 调用：ParameterSensitivityAnalyzer.sensitivity_on_population_weights(...)
"""

# =========================================================================
# 【结果解读】
# =========================================================================

"""
输出的 result 字典包含：
{
    'robustness_curve': [1.0, 0.98, 0.95, ..., 0.2],  # Rw值序列
    'alpha_values': [0.0, 0.05, 0.1, ..., 1.0],       # 对应的故障强度
    'lcc_size': [279, 278, 275, ..., 5],             # LCC节点数
    'isolated_population': [0, 5e7, 1e8, ...]        # 失联人口
}

关键指标：
- 最终鲁棒性 = result['robustness_curve'][-1]
- 半衰点 = 鲁棒性降至0.5时的α值
- 最大LCC下降 = 1 - min(result['lcc_size'])/max(result['lcc_size'])
"""

# =========================================================================
# 【常见错误及解决】
# =========================================================================

"""
错误1：FileNotFoundError: stations.csv 不存在
→ 检查数据文件路径，改为相对或绝对路径

错误2：内存错误（大网络）
→ 减少 alpha_steps，或使用采样

错误3：警告：某些节点无人口数据
→ 正常，框架为无数据节点分配0人口；若关键，提供实际数据

错误4：鲁棒性曲线全为1.0(不下降)
→ 可能是网络已是完全连通且权重分布不均
→ 检查网络连通性：builder.get_network_info()['is_connected']
"""

# =========================================================================
# 【高级功能】(可选，已整合到 population_weighted_robustness.py)
# =========================================================================

"""
# 时间演化分析
from advanced_robustness_analysis import TemporalRobustnessAnalyzer
temporal_results = TemporalRobustnessAnalyzer.analyze_multiple_years(
    ..., years=[1990, 2000, 2010, 2020], ...
)

# 敏感性分析
sensitivity_results = ParameterSensitivityAnalyzer.sensitivity_on_population_weights(
    ..., weight_multipliers=[0.5, 1.0, 1.5, 2.0], ...
)

# 故障传播追踪
propagation = FailurePropagationAnalyzer.analyze_propagation_pattern(...)

# 可达性阈值
analyzer = AccessibilityThresholdAnalyzer(graph)
accessible = analyzer.calculate_accessibility('北京市', distance_threshold=800)
"""

# =========================================================================
# 【论文/报告中的说法】
# =========================================================================

"""
"基于人口加权鲁棒性方法，在介数中心性攻击下，当故障强度α=0.3时，
网络鲁棒性Rw(α)从初始的1.0下降至0.42，表明仅移除3%的关键节点就
导致42%的加权人口丧失网络连通性，凸显了网络对枢纽节点的高度依赖。"
"""

# =========================================================================
# 【更多信息】
# =========================================================================

"""
📖 使用手册: README_ROBUSTNESS.md      (详细说明、参数、常见问题)
📐 技术文档: TECHNICAL_GUIDE.md        (理论、公式、论文参考)
🔧 配置说明: config_robustness.py      (所有可调参数)
📚 完整用法: README_ROBUSTNESS.md (详细说明、参数、常见问题)
💼 项目总结: PROJECT_SUMMARY.md         (总览、应用案例)
"""

print("✓ 快速参考卡已加载")
print("✓ 更多详情见上方注释或访问 README_ROBUSTNESS.md")
