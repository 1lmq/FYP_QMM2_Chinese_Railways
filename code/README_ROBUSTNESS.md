# 人口加权鲁棒性分析框架 - 使用手册

## 概述

本框架为铁路网络等基础设施系统提供了一套完整的**人口加权鲁棒性（Population-Integrated Robustness）**分析工具，用于评估网络在故障条件下对人口可达性的影响。

### 核心特性

✓ **模块化设计** - 清晰的代码结构，易于扩展  
✓ **多种故障模式** - 随机失效、中心性攻击、级联失效  
✓ **灵活的权重机制** - 支持有权/无权网络分析  
✓ **丰富的可视化** - 鲁棒性曲线、对比分析、网络结构  
✓ **高级分析功能** - 时间演化、敏感性分析、故障传播追踪  

---

## 1. 快速开始

### 1.1 基本使用（3步）

```python
from population_weighted_robustness import (
    RailNetworkBuilder, FailureSimulator, 
    RobustnessCalculator, RobustnessVisualizer
)

# 步骤1：加载数据并构建网络
builder = RailNetworkBuilder("stations.csv", "tracks.csv")
graph = builder.build_network(year=None)  # 使用所有数据

# 步骤2：分配人口数据
builder.generate_synthetic_population(strategy='provincial_based')
builder.assign_node_weights(strategy='economic_importance')

# 步骤3：执行故障模拟并计算鲁棒性
calculator = RobustnessCalculator(graph, builder.node_populations, builder.node_weights)
simulator = FailureSimulator(graph)
failure_seq = simulator.simulate_cascade_failure(failure_mode='degree', alpha_steps=20)
result = calculator.analyze_failure_impact(failure_seq, use_weights=True)

# 步骤4：可视化结果
RobustnessVisualizer.plot_robustness_curves({'度中心性攻击': result})
```

### 1.2 运行完整示例

```bash
cd code
python population_weighted_robustness.py
```

此命令将执行完整工作流，包括：
- 网络构建与数据加载
- 人口与权重分配
- 三种故障模式的模拟
- 生成4张对比图表
- 输出详细分析报告

---

## 2. 数据准备

### 2.1 输入数据格式

#### stations.csv（必需）
```csv
station_id,station_name,province,latitude,longitude
ST0001,上海市,上海市,31.23,121.48
ST0002,北京市,北京市,39.93,116.42
...
```

字段说明：
- `station_id`: 车站唯一标识
- `station_name`: 车站名称（用作节点ID）
- `province`: 所在省份
- `latitude`, `longitude`: 地理坐标

#### tracks.csv（必需）
```csv
edge_id,start_station,end_station,length,year,type
1,上海市,南京市,300.5,2020,rail_both
2,北京市,天津市,120.3,2020,rail_both
...
```

字段说明：
- `edge_id`: 轨道唯一标识
- `start_station`, `end_station`: 连接的两个车站
- `length`: 轨道长度（km）
- `year`: 该轨道开通/存在的年份
- `type`: 轨道类型（如rail_both, rail_good等）

### 2.2 可选的人口数据

如果有实际的人口数据，可以提供字典方式：

```python
actual_population = {
    '北京市': 2100 * 10000,      # 2100万人
    '上海市': 2400 * 10000,      # 2400万人
    '杭州市': 1000 * 10000,      # 1000万人
    ...
}

builder.assign_population_data(actual_population)
```

### 2.3 模拟数据生成

若无实际数据，框架提供三种模拟策略：

```python
# 策略1：省份基础（推荐）- 基于省份的人口分配
builder.generate_synthetic_population(strategy='provincial_based')

# 策略2：度数基础 - 重要节点服务更多人口
builder.generate_synthetic_population(strategy='degree_based')

# 策略3：均匀分配 - 所有节点服务相同人口
builder.generate_synthetic_population(strategy='uniform')
```

---

## 3. 核心模块详解

### 3.1 RailNetworkBuilder（网络构建器）

**作用**：管理数据加载、网络构建、人口与权重分配

**关键方法**：

| 方法 | 参数 | 说明 |
|-----|-----|------|
| `build_network()` | `year` (可选) | 构建网络，可指定年份或使用全部数据 |
| `generate_synthetic_population()` | `strategy` | 生成模拟人口（provincial_based/degree_based/uniform） |
| `assign_population_data()` | `population_dict` | 分配实际人口数据 |
| `assign_node_weights()` | `strategy` | 分配脆弱性权重（uniform/economic_importance/geographic_centrality） |
| `get_network_info()` | 无 | 返回网络统计信息 |

**示例**：
```python
builder = RailNetworkBuilder("stations.csv", "tracks.csv")

# 构建2020年的网络
graph_2020 = builder.build_network(year=2020)

# 或构建完整网络
graph_all = builder.build_network(year=None)

# 分配人口（省份基础）
builder.generate_synthetic_population(strategy='provincial_based')

# 分配权重（经济重要性）
builder.assign_node_weights(strategy='economic_importance')

# 查看网络信息
info = builder.get_network_info()
print(f"节点数：{info['number_of_nodes']}")
print(f"边数：{info['number_of_edges']}")
print(f"网络密度：{info['density']}")
```

---

### 3.2 FailureSimulator（故障模拟器）

**作用**：实现多种故障攻击策略，生成故障序列

**故障模式**：

1. **随机失效 (Random Failure)**
   - 每个节点等概率被选择
   - 最符合自然灾害
   - 造成破坏最温和

2. **度中心性攻击 (Degree-based)**
   - 优先移除连接数最多的节点
   - 模拟针对枢纽节点的破坏
   - 破坏力度中等

3. **介数中心性攻击 (Betweenness-based)** ⭐ 推荐
   - 优先移除作为"桥梁"的关键节点
   - 造成网络分片
   - 破坏力度最大

**关键方法**：

```python
simulator = FailureSimulator(graph)

# 模拟级联故障
failure_sequence = simulator.simulate_cascade_failure(
    failure_mode='betweenness',  # 或 'random', 'degree'
    alpha_steps=20               # 故障强度的步数
)
# 返回：List[List[str]]，每一步被移除的节点列表

# 单步故障（高级用法）
simulator.degree_based_attack(num_attacks=3)  # 一次移除3个度数最高的节点
simulator.betweenness_based_attack(num_attacks=2)

# 获取故障后的网络
damaged_graph = simulator.get_damaged_network()

# 重置
simulator.reset()
```

---

### 3.3 RobustnessCalculator（鲁棒性计算器）

**作用**：计算人口加权鲁棒性指标

**核心公式**：

$$R_w(\alpha) = 1 - \frac{\sum_{i \in \text{孤立}} w_i \cdot P_i}{\sum_{\text{全部}} w_i \cdot P_i}$$

其中：
- $\alpha$：故障强度（移除节点的比例）
- $w_i$：节点i的脆弱性权重（可选）
- $P_i$：节点i的服务人口
- 孤立节点：不在最大连通子图中的节点

**关键方法**：

```python
calculator = RobustnessCalculator(graph, node_populations, node_weights)

# 分析整个故障序列
analysis_result = calculator.analyze_failure_impact(
    failure_sequence,
    use_weights=True  # 是否使用权重
)
# 返回：
# {
#     'robustness_curve': [1.0, 0.98, 0.95, ..., 0.2],
#     'alpha_values': [0.0, 0.05, 0.1, ..., 1.0],
#     'lcc_size': [100, 99, 98, ...],
#     'isolated_population': [0, 50000, 100000, ...]
# }

# 单个损坏网络的鲁棒性
damaged_graph = graph.copy()
damaged_graph.remove_nodes_from(['北京市', '上海市'])
robustness_value = calculator.calculate_robustness(damaged_graph, use_weights=True)
# 返回：float，0~1之间的值

# 识别孤立节点
isolated = calculator.identify_isolated_nodes(damaged_graph)
# 返回：List[str]，不在最大连通子图中的节点

# 计算LCC大小
lcc_size = calculator.calculate_lcc_size(damaged_graph, metric='weighted_population')
# metric 可选：'nodes', 'population', 'weighted_population'
```

**结果解释**：
- Rw(α) = 1：完全健康，所有人口都可达
- Rw(α) = 0.5：一半的加权人口无法通过网络到达
- Rw(α) = 0：网络完全崩溃

---

### 3.4 RobustnessVisualizer（可视化器）

**作用**：生成高质量的对比分析图表

**可用图表**：

```python
# 图表1：多策略对比曲线
results = {
    '随机失效': result1,
    '度中心性攻击': result2,
    '介数中心性攻击': result3,
}

RobustnessVisualizer.plot_robustness_curves(
    results,
    figsize=(12, 8),
    save_path="robustness_curves.png"
)

# 图表2：4合1详细分析（推荐）
RobustnessVisualizer.plot_detailed_comparison(
    results,
    save_path="detailed_comparison.png"
)

# 图表3：网络拓扑结构（节点大小表示人口）
RobustnessVisualizer.plot_network_structure(
    graph,
    node_populations,
    save_path="network_structure.png"
)
```

---

## 4. 高级功能

### 4.1 可达性阈值分析

考虑距离阈值（如乘车时间超过8小时不现实）：

```python
from advanced_robustness_analysis import AccessibilityThresholdAnalyzer

analyzer = AccessibilityThresholdAnalyzer(graph, distance_attr='weight')

# 计算距离阈值内的可达节点
accessible = analyzer.calculate_accessibility('北京市', distance_threshold=800)

# 获取全网可达性映射
accessibility_map = analyzer.get_accessibility_map(distance_threshold=800)

# 计算有效网络规模
effective_size = analyzer.calculate_effective_network_size(distance_threshold=800)
```

### 4.2 时间演化分析

对比不同时期的网络韧性：

```python
from advanced_robustness_analysis import TemporalRobustnessAnalyzer

years_to_analyze = [1990, 2000, 2010, 2020]

temporal_results = TemporalRobustnessAnalyzer.analyze_multiple_years(
    stations_file="stations.csv",
    tracks_file="tracks.csv",
    years=years_to_analyze,
    builder_class=RailNetworkBuilder,
    calculator_class=RobustnessCalculator,
    simulator_class=FailureSimulator
)

# 绘制时间演化
TemporalRobustnessAnalyzer.plot_temporal_evolution(
    temporal_results,
    save_path="temporal_evolution.png"
)
```

### 4.3 参数灵敏度分析

分析权重参数的影响：

```python
from advanced_robustness_analysis import ParameterSensitivityAnalyzer

sensitivity_results = ParameterSensitivityAnalyzer.sensitivity_on_population_weights(
    calculator_class=RobustnessCalculator,
    graph=graph,
    node_populations=node_populations,
    base_weights=node_weights,
    weight_multipliers=[0.5, 0.8, 1.0, 1.2, 1.5],  # 权重倍数
    failure_sequence=failure_sequence
)

ParameterSensitivityAnalyzer.plot_sensitivity_results(
    sensitivity_results,
    save_path="sensitivity_analysis.png"
)
```

### 4.4 故障传播模式分析

追踪故障如何级联发展：

```python
from advanced_robustness_analysis import FailurePropagationAnalyzer

propagation = FailurePropagationAnalyzer.analyze_propagation_pattern(
    graph=graph,
    failure_sequence=failure_sequence,
    node_populations=node_populations
)

FailurePropagationAnalyzer.plot_propagation_pattern(
    propagation,
    save_path="propagation_pattern.png"
)
```

---

## 5. 常见参数配置

### 5.1 权重分配策略选择

| 策略 | 适用场景 | 特点 |
|-----|---------|------|
| `uniform` | 初步分析 | 所有节点权重=1，简单直观 |
| `economic_importance` | 标准分析（推荐） | 分配高权重给大城市和经济中心 |
| `geographic_centrality` | 拓扑分析 | 权重反映节点的地理中心性 |

### 5.2 人口数据策略选择

| 策略 | 特点 | 推荐度 |
|-----|------|--------|
| `provincial_based` | ⭐⭐⭐ | 省份基础+随机变化，最真实 |
| `degree_based` | ⭐⭐ | 重要节点人口多，有一定偏差 |
| `uniform` | ⭐ | 每个站点均匀分布，过于简化 |

### 5.3 故障模式参数

```python
# 故障步数（alpha_steps）的影响
# - 步数越多，曲线越光滑（但耗时长）
# - 推荐：15-20步（平衡精度和速度）

failure_seq = simulator.simulate_cascade_failure(
    failure_mode='degree',
    alpha_steps=20  # 推荐值
)
```

---

## 6. 实际案例：中国高铁网络分析

```python
# 完整示例：分析2024年中国高铁网络

from population_weighted_robustness import *

# 1. 构建2024年网络
builder = RailNetworkBuilder("stations.csv", "tracks.csv")
graph = builder.build_network(year=2024)

# 2. 分配数据
builder.generate_synthetic_population(strategy='provincial_based')
builder.assign_node_weights(strategy='economic_importance')

info = builder.get_network_info()
print(f"2024年网络：{info['number_of_nodes']}个站点，{info['number_of_edges']}条轨道")

# 3. 多策略分析
calculator = RobustnessCalculator(graph, builder.node_populations, builder.node_weights)
results = {}

for mode in ['random', 'degree', 'betweenness']:
    print(f"\n分析{mode}...")
    sim = FailureSimulator(graph)
    failures = sim.simulate_cascade_failure(failure_mode=mode, alpha_steps=20)
    results[mode.upper()] = calculator.analyze_failure_impact(failures)

# 4. 解读结果
print("\n【关键发现】")
for mode, result in results.items():
    final_robustness = result['robustness_curve'][-1]
    print(f"{mode}: 最终鲁棒性={final_robustness:.3f}")
    
    # 找到鲁棒性降至0.7的阈值
    for alpha, rw in zip(result['alpha_values'], result['robustness_curve']):
        if rw <= 0.7:
            print(f"{mode}: 临界阈值α={alpha:.3f} (移除{alpha*100:.1f}%的节点)")
            break

# 5. 可视化对比
RobustnessVisualizer.plot_detailed_comparison(results)
```

---

## 7. 输出结果解释

### 7.1 鲁棒性曲线解读

```
Rw(α)
1.0 |
    |     ___随机失效___
0.8 |    /
    |   /  ___度中心性___
0.6 |  /  /
    | /  /  ___介数中心性___
0.4|/  /  /
  |    /  /
0.2|___/__/___
  |
0.0|________________ α (故障强度)
    0   0.2  0.4  0.6  0.8  1.0
```

**解读规律**：
- **曲线陡峭** → 网络脆弱，少量关键节点失效导致快速崩溃
- **曲线平缓** → 网络健壮，容错能力强
- **曲线分布** → 不同策略的相对威胁  
  - 介数线最陡 → 介数攻击最危险
  - 随机线最平缓 → 网络有随机冗余度

### 7.2 关键指标

- **Rw(α=0)**：初始鲁棒性（应为1.0）
- **Rw(α=0.5)**：移除50%节点后的鲁棒性（关键指标）
- **Rw(α=1)**：最坏情况（网络完全瘫痪）
- **有效故障阈值**：Rw首次降至0.7的α值

---

## 8. 常见问题

**Q: 为什么鲁棒性值在0-1之间波动而不是单调递减?**
A: 通常不会波动，但如果出现，可能是因为网络不连通或权重分配不均。建议检查数据质量。

**Q: 如何处理孤立的节点或连通分量？**
A: 框架自动将它们视为"完全孤立"（无法到达）。这是最保守的评估。

**Q: 能否自定义故障模式？**
A: 可以。继承 `FailureSimulator` 并重写对应方法即可。

**Q: 计算需要多久？**
A: 对于500个节点、20步、3种策略：约5-10秒。可减少alpha_steps加速。

**Q: 如何比较不同年份的网络?**
A: 使用 `TemporalRobustnessAnalyzer` 模块（见4.2节）。

---

## 9. 学术背景

### 论文参考

人口加权鲁棒性方法基于网络韧性理论：
- Holmgren, A. J. (2006). "Using Graph Centrality Measures to Predict Swedish Railway Vulnerability to ...
- Buldyrev, S. V., et al. (2010). "Catastrophic cascade of failures in interdependent networks."
- 国内研究：许多交通网络韧性评估论文采用类似指标

### 核心概念

- **网络韧性** (Network Resilience)：网络在破坏后恢复的能力
- **脆弱性** (Vulnerability)：对故障的敏感程度
- **级联失效** (Cascading Failure)：一个节点失效引发连锁反应
- **最大连通子图** (Largest Connected Component, LCC)：网络中最大的连通部分

---

## 10. 联系与支持

- 如有问题，请检查数据格式（见2.1节）
- 代码已完整注释，建议对照注释理解各模块逻辑
- 建议先运行 `main()` 函数查看完整示例输出

---

**版本**：1.0  
**最后更新**：2026-03-23  
**许可证**：MIT
