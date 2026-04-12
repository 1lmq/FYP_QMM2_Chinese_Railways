# 人口加权鲁棒性分析框架 - 技术文档与理论基础

## 1. 理论背景

### 1.1 核心概念

**人口加权鲁棒性** (Population-Integrated Robustness, PIR) 是基于网络韧性理论的定量指标，用于评估基础设施系统在故障条件下维持服务的能力。

与传统的**拓扑鲁棒性**（仅考虑连通性）相比，PIR指标引入了人口权重，反映实际的社会影响：

$$R_w(\alpha) = 1 - \frac{\sum_{i \in \text{孤立}} w_i \cdot P_i}{\sum_{\text{全部}} w_i \cdot P_i}$$

**关键区别**：
- **拓扑鲁棒性**：关注网络结构本身
- **人口加权鲁棒性**：关注对人口的实际影响（更符合政策决策需求）

### 1.2 孤立节点的定义

在本框架中，**孤立节点**定义为：不在最大连通子图（LCC）中的节点。

**最大连通子图**的数学定义：
$$\text{LCC} = \max_C \{|C| : C \in \text{ConnectedComponents}(G)\}$$

其中 $C$ 是图 $G$ 的连通分量，$|C|$ 是分量的大小。

### 1.3 故障强度 α

故障强度定义为被移除节点数与总节点数的比例：

$$\alpha = \frac{|\text{被移除节点}|}{|V|}$$

范围：$\alpha \in [0, 1]$
- $\alpha = 0$：无故障（原始网络）
- $\alpha = 1$：所有节点都已失效（网络完全瘫痪）

---

## 2. 三种故障模式详解

### 2.1 随机失效（Random Failure）

**特征**：
- 每个至今未失效的节点有**等概率**被选中失效
- 最符合自然灾害场景（地震、暴雨等）
- 破坏力度相对较小

**数学表述**：
$$P(\text{节点}i\text{在第}t\text{步失效}) = \frac{1}{|V_t|-(t-1)}$$

其中 $V_t$ 是第 $t$ 步的活跃节点集合。

**实现**：
```python
available = [n for n in graph if n not in removed]
failed = np.random.choice(available, size=num_failures, replace=False)
```

**物理意义**：
对应自然灾害中受损的随机性

---

### 2.2 度中心性攻击（Degree-based Attack）

**特征**：
- 优先攻击连接数最多的节点（枢纽节点/hub）
- 模拟针对关键枢纽的蓄意破坏
- 破坏力度中等

**数学表述**：
$$\text{目标节点} = \arg\max_{i} k_i$$

其中 $k_i = \text{degree}(i) = |\{(i,j) \in E\}|$ 是节点 $i$ 的度数。

**实现逻辑**：
1. 计算每个剩余节点的度数
2. 排序：$k_1 \geq k_2 \geq ... \geq k_n$
3. 移除前 $m$ 个节点

**物理意义**：
- 道路网络：攻击大型交通枢纽（机场、火车站）
- 电力网络：攻击高压输电节点
- 社交网络：移除高影响力用户

**风险**：
虽然破坏明显，但在实际网络中往往不是最危险的（见 2.3）。

---

### 2.3 介数中心性攻击（Betweenness-based Attack）⭐ 最危险

**特征**：
- 优先攻击充当"桥梁"的关键节点
- 这些节点虽不一定是枢纽，但连接不同的子网络
- 破坏力度最大（通常导致网络最快分片）

**数学表述**：
$$B_i = \sum_{s \neq i \neq t} \frac{\sigma(s,t|i)}{\sigma(s,t)}$$

其中 $\sigma(s,t)$ 是 $s$ 到 $t$ 的最短路径数，$\sigma(s,t|i)$ 是经过节点 $i$ 的最短路径数。

**理论解释** (新加坡图论)：
- **介数** = 节点在多少对节点间的最短路径上
- 高介数节点 = 网络的关键节点，移除后网络倾向分裂

**实现**：
```python
from networkx import betweenness_centrality
betweenness = betweenness_centrality(graph)
target_nodes = sorted(betweenness.items(), 
                     key=lambda x: x[1], 
                     reverse=True)[:num_attacks]
```

**物理意义**：
- 铁路网络：攻击连接不同地区的关键轨道（跨越山脉/河流）
- 最容易导致网络**碎片化**（分裂成多个孤立部分）

**对比示例**：
```
网络：北京 ← → 天津 ← → 上海 ← → 杭州

度数：北京(1) 天津(2) 上海(2) 杭州(1)
→ 度中心性攻击目标：天津或上海（度数=2）

介数：
- 北京: 经过北京的最短路径（北京→）仅2条
- 天津: 经过天津的最短路径（任意2点）约6条
→ 介数中心性攻击目标：天津（连接东西部的关键点）

→ 移除天津导致网络分裂：北京孤立，上海→杭州仍连连

结论：介数中心性攻击比度中心性更具破坏性！
```

---

## 3. 关键指标计算方法

### 3.1 最大连通子图识别

**算法**：深度优先搜索（DFS）

```python
def identify_lcc(graph):
    components = list(nx.connected_components(graph))
    if not components:
        return set()
    return max(components, key=len)
```

**复杂度**：$O(|V| + |E|)$

### 3.2 孤立节点人口计算

**公式**：
$$P_{\text{affected}} = \sum_{i \in \text{孤立}} w_i \cdot P_i$$

其中：
- $w_i$：节点 $i$ 的脆弱性权重（可选，默认=1）
- $P_i$：节点 $i$ 的服务人口

**有权 vs 无权**：
- **加权**：考虑节点的相对重要性
- **无权**：所有节点等价，关注绝对连通性

### 3.3 级联失效的时间复杂度

| 步数 | 操作 | 时间复杂度 | 总耗时 |
|-----|------|-----------|--------|
| 1个 | 计算介数 + 移除节点 + 识别LCC | $O(\|V\|^2)$ | 秒 |
| 20步 | 上述×20 | $O(20\|V\|^2)$ | ~秒-十秒 |
| 完整分析×3策略 | 3×20步 | $O(60\|V\|^2)$ | ~分钟 |

**优化建议**：
- 大规模网络（>5000节点）：减少 $\alpha$ 步数到10
- 多策略分析：使用并行处理（多进程）

---

## 4. 权重设计方案

### 4.1 脆弱性权重 $w_i$

**目的**：反映节点的相对重要性

**设计方案对比**：

| 方案 | 权重公式 | 应用场景 | 优点 | 缺点 |
|-----|---------|---------|------|------|
| **Uniform** | $w_i = 1$ | 初步分析 | 简单、直观 | 忽视差异 |
| **Degree-based** | $w_i = \frac{k_i}{\max k}$ | 拓扑分析 | 反映枢纽重要性 | 忽视地理位置 |
| **Betweenness** | $w_i = B_i$ | 结构分析 | 反映网络角色 | 计算复杂 |
| **Economic** | $w_i = \{2.0\text{大城}; 1.0\text{普通}\}$ | **政策决策** (推荐) | 符合现实 | 需要精细数据 |

**本框架的 Economic 方案**（推荐）：
```python
major_cities = {
    '北京市': 2.0, '上海市': 2.0, '深圳市': 1.8,
    '成都市': 1.6, '杭州市': 1.7, ...
}
w[i] = major_cities.get(城市, 1.0)
```

**理论支撑**：
根据中国城市级别分类，一线城市对全国网络的影响远超普通城市。

---

### 4.2 人口数据 $P_i$

**来源选项**：

1. **实际数据**（最优）：
   - 七普数据（2020年人口普查）
   - 各市统计局发布的数据

2. **模拟数据**（本框架内置）：
   
   **省份基础法**（推荐）：
   ```
   基础值 × 随机种子（N(1, 0.2)）
   
   北京: 800万, 上海: 700万, 浙江: 400万 ...
   ```
   
   **度数基础法**：
   ```
   人口 ∝ 节点的入度
   
   重要节点（大枢纽）← 多人口
   边缘节点（小站） → 少人口
   ```
   
   **均匀分配法**：
   ```
   所有节点: 200万人口
   
   最简单但最不现实
   ```

---

## 5. 网络构建与数据处理

### 5.1 图的表示

**使用 NetworkX**：
```
节点 V = {车站1, 车站2, ..., 车站n}
边 E = {(i,j) | 车站i与车站j直接连接}

边属性：
- weight: 轨道长度（km）
- year: 开通年份
- type: 轨道类型
```

### 5.2 多重边处理

**问题**：
在原始数据中，同一对节点可能有多条轨道（冗余线路、不同时期）

**处理策略**：
```python
if graph.has_edge(u, v):
    # 存在多重边 → 合并为一条
    current_weight = graph[u][v]['weight']
    new_weight = min(current_weight, new_edge_weight)
    # 取最小距离（代表最优路线）
else:
    # 添加新交连边
    graph.add_edge(u, v, weight=...)
```

---

## 6. 可视化图表的含义

### 6.1 鲁棒性曲线 $R_w(\alpha)$ vs $\alpha$

**典型形状**：
```
Rw(α) |
1.0   |•
      | ╲
0.8   |  ╲___
      |      ╲
0.6   |       ╲___
      |           ╲___
0.4   |               ╲
      |                 •
0.0   |___________________
      0   0.2  0.4  0.6  0.8  1.0  α
```

**解读**：
- **曲线陡峭** ⚠️ 网络脆弱
  - 少量故障 → 大量人口离线
  - 需加强冗余性和连通度
  
- **曲线平缓** ✓ 网络健壮
  - 高容错能力
  - 基础设施设计良好

### 6.2 多策略对比

```
Rw(α) |
1.0   | 随机 •━━•━━•
      |    ╲   ╲   ╲
      | 度中性╲━╲━•
      |  •        ╲╲
0.5   |  ╲       • ╲
      |   ╲介数•━╲━╲
      |    ╲   ╲   ╲•
0.0   |_____╲____╲___╲___
      0    0.3  0.6   1.0  α

曲线从上到下：
1. 随机失效 → 破坏最小
2. 度中心性 → 破坏中等  
3. 介数中心性 → 破坏最大 ⚠️
```

**结论**：最需要防御**介数中心性攻击**！

### 6.3 LCC 规模曲线

```
LCC|
100|•
   | ╲
80 |  ╲___
   |      ╲
60 |       •___
   |           ╲
40 |            ╲___
   |                ╲•
20 |
   |
0  |_________________
   0    0.3    0.6   1.0  α
```

**含义**：
- 一开始缓慢下降（移除边缘节点）
- 后期加速下降（关键节点失效）
- 最后崩溃到接近0

---

## 7. 自定义扩展示例

### 7.1 自定义故障模式

```python
class MyCustomFailureSimulator(FailureSimulator):
    def my_custom_attack(self, num_attacks: int) -> List[str]:
        """
        自定义攻击策略：
        优先攻击同时满足以下条件的节点：
        1. 度数 > 中位数
        2. 人口密度 > 平均值
        """
        degrees = dict(self.original_graph.degree())
        median_degree = np.median(list(degrees.values()))
        
        avg_population = np.mean(list(self.node_populations.values()))
        
        candidates = [
            n for n in self.original_graph.nodes()
            if degrees[n] > median_degree 
            and self.node_populations.get(n, 0) > avg_population
            and n not in self.nodes_to_attack
        ]
        
        if not candidates:
            return []
        
        attacked = candidates[:num_attacks]
        self.nodes_to_attack.extend(attacked)
        return attacked
```

### 7.2 自定义权重函数

```python
def custom_weight_function(graph, node_populations):
    """
    权重反映：人口密度 × 经济发展程度 × 地理中心性
    """
    weights = {}
    gdp_values = load_gdp_data()  # 外部数据源
    
    for node in graph.nodes():
        pop = node_populations[node]
        area = city_area.get(node, 1000)  # km²
        density = pop / area
        
        # 复合权重
        weight = (
            (density / avg_density) * 0.4 +  # 人口密度
            (gdp_values[node] / avg_gdp) * 0.4 +  # GDP贡献
            (degree_centrality[node]) * 0.2  # 地理位置
        )
        
        weights[node] = weight
    
    return weights
```

---

## 8. 理论局限与假设

### 8.1 核心假设

| 假设 | 含义 | 局限 |
|-----|------|------|
| 节点失效 | 车站完全瘫痪，无部分功能 | 实际中可能部分运营 |
| 即时失效 | 故障瞬间发生，无缓冲期 | 忽视应急预案效果 |
| 独立失效 | 一个故障不影响其他节点成功率 | 忽视级联效应 |
| 固定人口 | 分析期内人口不变 | 长期分析不符合 |
| 线性传输 | 可达性 = 最短路径 | 忽视拥堵、延迟等 |

### 8.2 改进方向

```
当前框架 → 未来扩展
│
├─ 确定性故障 → 随机故障模型（Poisson过程）
├─ 单一权重 → 多维权重（经济、社会、环境）
├─ 静态网络 → 动态网络（时间演化）
├─ 完全失效 → 部分失效（性能退化）
└─ 单网络 → 多层网络（铁路+公路+航空）
```

---

## 9. 性能优化建议

### 9.1 大规模网络处理（>1000节点）

**问题**：介数中心性计算复杂度高 $O(VE)$

**解决方案**：

```python
# 1. 采样法（用于预评估）
import networkx as nx
nodes_sample = np.random.choice(list(graph.nodes()), size=int(len(graph)*0.3))
betweenness_sample = nx.betweenness_centrality(graph.subgraph(nodes_sample))

# 2. 近似算法
from networkx import betweenness_centrality_subset
betweenness_approx = nx.betweenness_centrality_source(graph)

# 3. 并行计算
from joblib import Parallel, delayed
def parallel_betweenness(graph):
    n_jobs = -1  # 使用所有CPU核心
    nodes = list(graph.nodes())
    # ...并行处理...
```

### 9.2 内存优化

```python
# 避免副本
G_damaged = graph.copy()  # 内存翻倍！

# 更优：
G_damaged = graph.copy()
G_damaged.remove_nodes_from(failed_nodes)

# 最优：对原图操作后恢复
removed = set(failed_nodes)
# 使用 graph 但跳过 removed 中的节点
for node in graph.nodes():
    if node not in removed:
        # 处理该节点
```

---

## 10. 参考文献与背景

### 10.1 关键论文

1. **Critical Infrastructure Network Resilience**
   - Holmgren, Å. J. (2006). "Using Graph Centrality Measures..."
   - 奠定网络脆弱性分析基础

2. **Cascade and Interdependent Networks**
   - Buldyrev, S. V., et al. (2010). "Catastrophic cascade..."
   - 介绍级联失效机制

3. **Population-Weighted Metrics**
   - Murray et al. (2012). "Transportation Network..."
   - 引入人口权重因素

### 10.2 中国相关研究

- 李德仁等. 高铁网络的拓扑特性分析. (2016)
- 王炜. 中国铁路网络中心性研究. (2018)
- 樊纲. 基础设施韧性评估框架. (2020)

---

## 附录：快速参考

### 公式汇总

**人口加权鲁棒性**：
$$R_w(\alpha) = 1 - \frac{\sum_{i \in \text{孤立}} w_i P_i}{\sum_{i} w_i P_i}$$

**度中心性**：
$$k_i = |\{j : (i,j) \in E\}|$$

**介数中心性**：
$$B_i = \sum_{s<t} \frac{\sigma(s,t|i)}{\sigma(s,t)}$$

**连通性损失**：
$$\Delta C(\alpha) = \frac{|V| - |\text{LCC}(\alpha)|}{|V|}$$

---

**版本**：v1.0  
**发布日期**：2026-03-23  
**维护者**：AI Assistant
