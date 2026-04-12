"""
人口加权鲁棒性分析框架（Population-Integrated Robustness Framework）
================================================================

用于评估铁路网络在故障条件下对人口可达性的影响。

核心概念：
- Rw(α) = 1 - [∑(wi * Pi)_孤立] / [∑(wi * Pi)_全部]
  其中：wi = 脆弱性权重，Pi = 节点i的服务人口，α = 故障强度

模块划分：
1. network_builder: 网络构建与数据加载
2. failure_simulator: 故障模拟（随机、中心性攻击）
3. robustness_calculator: 鲁棒性指标计算
4. visualization: 结果可视化
5. sensitivity_analyzer: 敏感性分析（可选）

作者：AI Assistant
日期：2026-03-23
"""

import pandas as pd
import numpy as np
import networkx as nx
from typing import Dict, List, Tuple, Optional, Callable
import matplotlib.pyplot as plt
from matplotlib import rcParams
from pathlib import Path
import warnings
warnings.filterwarnings('ignore')

# 配置中文字体
rcParams['font.sans-serif'] = ['SimHei', 'DejaVu Sans']
rcParams['axes.unicode_minus'] = False


# ============================================================================
# 模块 1: 网络构建与数据管理
# ============================================================================

class RailNetworkBuilder:
    """
    铁路网络构建器
    
    功能：
    - 从CSV文件加载站点和轨道数据
    - 构建NetworkX图对象
    - 为节点分配人口和权重
    """
    
    def __init__(self, stations_file: str, tracks_file: str, 
                 population_file: Optional[str] = None):
        """
        初始化网络构建器
        
        参数：
            stations_file (str): 站点数据CSV路径
            tracks_file (str): 轨道数据CSV路径
            population_file (str, optional): 真实人口数据CSV路径
        """
        self.stations_df = pd.read_csv(stations_file)
        self.tracks_df = pd.read_csv(tracks_file)
        self.population_file = population_file
        self.population_df = None
        if population_file:
            # 使用分号作为分隔符（ChinaCities_Swerts.csv使用分号分隔）
            self.population_df = pd.read_csv(population_file, sep=';')
        self.graph = None
        self.node_populations = {}
        self.node_weights = {}
        
    def build_network(self, year: Optional[float] = None, 
                     simplify: bool = True) -> nx.Graph:
        """
        构建网络图
        
        参数：
            year (float, optional): 指定年份；若None则使用所有轨道
            simplify (bool): 是否简化多重边为单边
            
        返回：
            networkx.Graph: 构建的网络图
            
        说明：
            - 节点为站点名称
            - 边为站点之间的直接连接
            - 若simplify=True，多重连接合并为一条边
        """
        # 筛选指定年份的轨道
        if year is not None:
            edges_data = self.tracks_df[self.tracks_df['year'] == year]
        else:
            edges_data = self.tracks_df
        
        # 创建无向图
        self.graph = nx.Graph()
        
        # 添加所有节点（使用站点名称作为节点ID）
        for _, row in self.stations_df.iterrows():
            self.graph.add_node(row['station_name'])
        
        # 添加边（站点之间的直接连接）
        for _, row in edges_data.iterrows():
            start = row['start_station']
            end = row['end_station']
            # 检查节点是否存在（处理数据不一致的情况）
            if (start in self.graph.nodes()) and (end in self.graph.nodes()):
                if self.graph.has_edge(start, end):
                    # 若边已存在，更新权重（取最小距离）
                    current_weight = self.graph[start][end].get('weight', row['length'])
                    self.graph[start][end]['weight'] = min(current_weight, row['length'])
                else:
                    # 添加新边，边权为距离
                    self.graph.add_edge(start, end, weight=row['length'])
        
        return self.graph
    
    def assign_population_data(self, population_dict: Dict[str, float]):
        """
        分配人口数据
        
        参数：
            population_dict (Dict): {节点名: 人口数}的字典
            
        说明：
            - 字典中未提及的节点默认人口为0
            - 建议先接收用户数据，若无则使用 generate_synthetic_population()
        """
        for node in self.graph.nodes():
            self.node_populations[node] = population_dict.get(node, 0)
    
    def load_real_population_data(self, year: int = 2010) -> Dict[str, float]:
        """
        从真实人口数据文件加载人口数据
        
        参数：
            year (int): 使用哪一年的人口数据，默认2010年
            
        返回：
            Dict: {站点名: 人口数}
            
        说明：
            - 从 ChinaCities_Swerts.csv 读取数据
            - 支持年份：1982, 1990, 2000, 2010
            - 若某城市无该年数据，使用最近可用年份
            - 未包含的小城市使用 0（或可微调）
        """
        if self.population_df is None:
            print("警告：人口数据文件未加载，使用模拟数据")
            return self.generate_synthetic_population()
        
        # 将年份列转换为字符串
        year_str = str(year)
        
        # 获取可用的年份列
        available_years = [col for col in self.population_df.columns 
                          if col.isdigit()]
        
        # 若指定年份不存在，找最接近的年份
        if year_str not in available_years:
            available_years = sorted([int(y) for y in available_years])
            # 找最接近的年份
            closest_year = min(available_years, 
                             key=lambda y: abs(y - year))
            print(f"提示：{year}年数据不可用，使用{closest_year}年数据")
            year_str = str(closest_year)
        
        # 构建人口字典
        population_dict = {}
        
        for _, row in self.population_df.iterrows():
            city_name = row['Name EN'].title() if 'Name EN' in row.index else None
            
            # 尝试多种城市名称匹配
            if city_name is None:
                continue
            
            # 将英文名转换为中文（基于常见映射）
            cn_name_map = {
                'SHANGHAI': '上海市',
                'BEIJING': '北京市',
                'GUANGZHOU': '广州市',
                'TIANJIN': '天津市',
                'SHENZHEN': '深圳市',
                'WUHAN': '武汉市',
                'CHONGQING': '重庆市',
                'CHENGDU': '成都市',
                'NANJING': '南京市',
                'SHENYANG': '沈阳市',
                'XIAN': '西安市',
                'ZHENGZHOU': '郑州市',
                'CHANGCHUN': '长春市',
                'QINGDAO': '青岛市',
                'HAERBIN': '哈尔滨市',
                'HANGZHOU': '杭州市',
                'DALIAN': '大连市',
                'JINAN': '济南市',
                'TAIYUAN': '太原市',
                'KUNMING': '昆明市',
                'XIAMEN': '厦门市',
                'CHANGSHA': '长沙市',
                'WENZHOU': '温州市',
                'ZIBO': '淄博市',
                'FUZHOU': '福州市',
                'WULUMUQI': '乌鲁木齐市',
                'SHIJIAZHUANG': '石家庄市',
                'NANNING': '南宁市',
            }
            
            city_en = row['Name EN'].upper()
            cn_name = cn_name_map.get(city_en)
            
            if cn_name and year_str in self.population_df.columns:
                pop_value = row[year_str]
                # 跳过缺失值
                if pd.notna(pop_value) and pop_value > 0:
                    population_dict[cn_name] = int(pop_value)
        
        # 分配给图的节点
        self.assign_population_data(population_dict)
        
        print(f"[OK] 已加载 {len(population_dict)} 个城市的 {year}年人口数据")
        print(f"  总服务人口：{sum(population_dict.values())/1e8:.2f}亿人")
        
        return population_dict
    
    def generate_synthetic_population(self, strategy: str = 'provincial_based') -> Dict[str, float]:
        """
        生成模拟人口数据（当实际数据不可用时）
        
        参数：
            strategy (str): 生成策略
                - 'provincial_based': 基于省份的人口分配（更合理）
                - 'uniform': 均匀分配
                - 'degree_based': 基于节点度数分配
                
        返回：
            Dict: {节点名: 人口数}
            
        说明：
            中国主要省份的人口估计（2020年左右）：
            北京、上海、浙江、江苏、山东等人口密集区；
            西北、西南地区人口相对较少。
        """
        # 省份-人口映射（简化版，表示该省份平均单个站点服务人口，单位万人）
        province_population_base = {
            '北京市': 800,
            '上海市': 700,
            '浙江省': 400,
            '江苏省': 450,
            '山东省': 380,
            '四川省': 300,
            '湖北省': 280,
            '湖南省': 260,
            '广东省': 320,
            '福建省': 240,
            '山西省': 180,
            '陕西省': 200,
            '甘肃省': 150,
            '宁夏回族自治区': 120,
            '青海省': 140,
            '新疆维吾尔自治区': 160,
            '西藏自治区': 80,
            '云南省': 120,
            '贵州省': 140,
            '重庆市': 280,
            '内蒙古自治区': 200,
            '黑龙江省': 220,
            '吉林省': 200,
            '辽宁省': 280,
            '天津市': 400,
        }
        
        population_dict = {}
        
        if strategy == 'provincial_based':
            # 基于省份：每个站点服务人口为省份基础人口
            # 再加上适度的随机变化（±20%）
            for node in self.graph.nodes():
                province = self._get_province_for_node(node)
                base_pop = province_population_base.get(province, 150)
                # 添加随机变化（正态分布，均值为基础值）
                variation = np.random.normal(1.0, 0.2)  # 均值1，标准差0.2
                variation = max(0.6, min(1.4, variation))  # 限制在0.6~1.4倍
                population_dict[node] = base_pop * variation * 10000  # 转换为人数
                
        elif strategy == 'degree_based':
            # 基于度中心性：重要节点服务更多人口
            if self.graph.number_of_nodes() == 0:
                return population_dict
            degrees = dict(self.graph.degree())
            max_degree = max(degrees.values()) if degrees else 1
            for node in self.graph.nodes():
                degree_norm = (degrees.get(node, 0) / max_degree) * 0.5 + 0.5
                population_dict[node] = degree_norm * 300 * 10000
                
        elif strategy == 'uniform':
            # 均匀分配
            pop_per_node = 200 * 10000  # 每站点200万人口
            for node in self.graph.nodes():
                population_dict[node] = pop_per_node
        
        self.assign_population_data(population_dict)
        return population_dict
    
    def _get_province_for_node(self, node_name: str) -> str:
        """
        根据节点名获取所在省份
        
        参数：
            node_name (str): 站点名称
            
        返回：
            str: 省份名称
        """
        try:
            province = self.stations_df[
                self.stations_df['station_name'] == node_name
            ]['province'].values[0]
            return province
        except:
            return '其他'
    
    def assign_node_weights(self, weight_dict: Optional[Dict[str, float]] = None,
                           strategy: str = 'uniform'):
        """
        分配节点脆弱性权重 wi
        
        参数：
            weight_dict (Dict, optional): 外部提供的权重字典；若None则生成
            strategy (str): 权重生成策略
                - 'uniform': 所有节点权重为1（无差异）
                - 'economic_importance': 基于经济重要性（模拟）
                - 'geographic_centrality': 基于地理位置中心性
                
        说明：
            权重反映节点重要性、经济价值、人口依赖等因素
            范围通常为 [0.5, 2.0]
        """
        if weight_dict is not None:
            self.node_weights = weight_dict
            return
        
        if strategy == 'uniform':
            # 无差异权重
            self.node_weights = {node: 1.0 for node in self.graph.nodes()}
            
        elif strategy == 'economic_importance':
            # 模拟经济重要性：省会和大城市权重更高
            major_cities = {
                '北京市': 2.0, '上海市': 2.0, '广州市': 1.8, '深圳市': 1.8,
                '成都市': 1.6, '杭州市': 1.7, '南京市': 1.5, '武汉市': 1.5,
                '西安市': 1.4, '重庆市': 1.6, '苏州市': 1.5, '长沙市': 1.3,
            }
            self.node_weights = {}
            for node in self.graph.nodes():
                self.node_weights[node] = major_cities.get(node, 1.0)
                
        elif strategy == 'geographic_centrality':
            # 基于节点的地理中心性（度中心性的代理）
            degrees = dict(self.graph.degree())
            if not degrees:
                self.node_weights = {node: 1.0 for node in self.graph.nodes()}
                return
            max_degree = max(degrees.values())
            min_degree = min(degrees.values())
            for node in self.graph.nodes():
                # 归一化度中心性到[0.5, 2.0]
                normalized_degree = (degrees.get(node, 0) - min_degree) / (max_degree - min_degree + 1)
                self.node_weights[node] = 0.5 + normalized_degree * 1.5
    
    def get_network_info(self) -> Dict:
        """
        获取网络基本信息
        
        返回：
            Dict: 网络统计信息
        """
        if self.graph is None:
            return {}
        
        return {
            'number_of_nodes': self.graph.number_of_nodes(),
            'number_of_edges': self.graph.number_of_edges(),
            'density': nx.density(self.graph),
            'is_connected': nx.is_connected(self.graph),
            'number_of_components': nx.number_connected_components(self.graph),
            'average_degree': np.mean([d for n, d in self.graph.degree()]) 
                            if self.graph.number_of_nodes() > 0 else 0,
        }


# ============================================================================
# 模块 2: 故障模拟器
# ============================================================================

class FailureSimulator:
    """
    网络故障模拟器
    
    功能：
    - 实现多种攻击策略（随机、中心性）
    - 逐步增加故障强度
    - 跟踪每一步后的网络状态
    """
    
    def __init__(self, graph: nx.Graph):
        """
        初始化故障模拟器
        
        参数：
            graph (nx.Graph): 待模拟的网络
        """
        self.original_graph = graph.copy()
        self.nodes_to_attack = []

    def _compute_static_attack_order(self, failure_mode: str,
                                     random_seed: Optional[int] = 42) -> List[str]:
        """
        在初始网络上一次性计算攻击顺序（static attack）。

        说明：
            - random: 固定随机种子后一次性打乱节点顺序
            - degree: 基于初始网络度中心性一次性排序
            - betweenness: 基于初始网络介数中心性一次性排序
        """
        nodes = list(self.original_graph.nodes())

        if failure_mode == 'random':
            rng = np.random.default_rng(random_seed)
            order = list(rng.permutation(nodes))
            return order

        if failure_mode == 'degree':
            degrees = dict(self.original_graph.degree())
            return sorted(nodes, key=lambda n: (-degrees.get(n, 0), str(n)))

        if failure_mode == 'betweenness':
            betweenness = nx.betweenness_centrality(self.original_graph)
            return sorted(nodes, key=lambda n: (-betweenness.get(n, 0.0), str(n)))

        raise ValueError(f"Unknown failure mode: {failure_mode}")
        
    def random_failure(self, num_failures: int = 1) -> List[str]:
        """
        随机失效策略
        
        参数：
            num_failures (int): 要移除的节点数
            
        返回：
            List[str]: 被移除的节点列表
            
        说明：
            - 等概率选择任意节点失效
            - 最不现实但最简单的模型
            - 用作基准对比
        """
        available_nodes = [n for n in self.original_graph.nodes() 
                          if n not in self.nodes_to_attack]
        if num_failures > len(available_nodes):
            num_failures = len(available_nodes)
        
        failed_nodes = np.random.choice(available_nodes, num_failures, replace=False)
        self.nodes_to_attack.extend(failed_nodes)
        return list(failed_nodes)
    
    def degree_based_attack(self, num_attacks: int = 1) -> List[str]:
        """
        基于度中心性的攻击策略
        
        参数：
            num_attacks (int): 要攻击的节点数
            
        返回：
            List[str]: 被攻击的节点列表
            
        说明：
            - 优先攻击度数最高的节点（枢纽）
            - 模拟针对重要节点的蓄意破坏
            - 通常比随机失效造成更大影响
        """
        available_nodes = [n for n in self.original_graph.nodes() 
                          if n not in self.nodes_to_attack]
        
        # 计算可用节点的度中心性
        degrees = dict(self.original_graph.degree())
        available_degrees = {n: degrees[n] for n in available_nodes}
        
        # 按度数降序排序，取前 num_attacks 个
        sorted_nodes = sorted(available_degrees.items(), 
                             key=lambda x: x[1], reverse=True)
        attacked_nodes = [node for node, _ in sorted_nodes[:num_attacks]]
        
        self.nodes_to_attack.extend(attacked_nodes)
        return attacked_nodes
    
    def betweenness_based_attack(self, num_attacks: int = 1) -> List[str]:
        """
        基于介数中心性的攻击策略
        
        参数：
            num_attacks (int): 要攻击的节点数
            
        返回：
            List[str]: 被攻击的节点列表
            
        说明：
            - 优先攻击介数中心性最高的节点
            - 这些节点充当"桥梁"角色，破坏造成网络分片
            - 比度中心性攻击更具破坏性（通常）
        """
        # 创建临时图用于计算介数（排除已攻击的节点）
        temp_graph = self.original_graph.copy()
        temp_graph.remove_nodes_from(self.nodes_to_attack)
        
        if temp_graph.number_of_nodes() == 0:
            return []
        
        # 计算介数中心性
        betweenness = nx.betweenness_centrality(temp_graph)
        available_nodes = [n for n in temp_graph.nodes()]
        
        # 按介数降序排序，取前 num_attacks 个
        sorted_nodes = sorted([(n, betweenness[n]) for n in available_nodes],
                             key=lambda x: x[1], reverse=True)
        attacked_nodes = [node for node, _ in sorted_nodes[:min(num_attacks, len(sorted_nodes))]]
        
        self.nodes_to_attack.extend(attacked_nodes)
        return attacked_nodes
    
    def simulate_cascade_failure(self, failure_mode: str = 'random',
                                alpha_steps: int = 20,
                                random_seed: Optional[int] = 42):
        """
        模拟级联故障
        
        参数：
            failure_mode (str): 故障模式 ('random', 'degree', 'betweenness')
            alpha_steps (int): 故障强度的步数（从0到1）
            
        返回：
            List[List[str]]: 每一步被移除的节点列表
            
        说明：
            - 逐步增加故障强度 α，从0到1
            - 在每一步中，通过相应策略选择节点失效
            - 返回整个过程中每一步被移除的节点
        """
        self.nodes_to_attack = []
        total_nodes = self.original_graph.number_of_nodes()
        failure_sequence = []

        # 关键修正：在初始网络上一次性确定攻击顺序，避免动态重算带来的自适应攻击偏差
        static_attack_order = self._compute_static_attack_order(
            failure_mode=failure_mode,
            random_seed=random_seed
        )
        
        for step in range(alpha_steps):
            # 目标累计删除节点数，确保逐步累积且最后一步达到全部节点
            target_failures = min(
                total_nodes,
                int(np.ceil((step + 1) * total_nodes / alpha_steps))
            )
            current_failures = len(self.nodes_to_attack)
            num_new_failures = target_failures - current_failures
            
            if num_new_failures <= 0:
                failure_sequence.append([])
                continue

            failed = static_attack_order[current_failures:target_failures]
            self.nodes_to_attack.extend(failed)
            
            failure_sequence.append(failed)
        
        return failure_sequence
    
    def get_damaged_network(self) -> nx.Graph:
        """
        获取当前故障后的网络
        
        返回：
            nx.Graph: 移除故障节点后的网络副本
        """
        damaged_graph = self.original_graph.copy()
        damaged_graph.remove_nodes_from(self.nodes_to_attack)
        return damaged_graph
    
    def reset(self):
        """
        重置模拟器，清除所有故障记录
        """
        self.nodes_to_attack = []


# ============================================================================
# 模块 3: 鲁棒性计算器
# ============================================================================

class RobustnessCalculator:
    """
    人口加权鲁棒性计算器
    
    核心指标：
    Rw(α) = 1 - [∑(wi * Pi)_孤立节点] / [∑(wi * Pi)_全部节点]
    
    说明：
    - R=1: 网络完全健康，所有人口都在连通分量中
    - R=0: 网络完全崩溃，网络被分离
    """
    
    def __init__(self, original_graph: nx.Graph,
                 node_populations: Dict[str, float],
                 node_weights: Dict[str, float]):
        """
        初始化鲁棒性计算器
        
        参数：
            original_graph (nx.Graph): 原始网络
            node_populations (Dict): 节点人口分配
            node_weights (Dict): 节点权重分配
        """
        self.original_graph = original_graph
        self.node_populations = node_populations
        self.node_weights = node_weights
        self.total_population = sum(node_populations.values())
        self.total_weight_population = sum(
            node_weights.get(n, 1.0) * node_populations.get(n, 0)
            for n in original_graph.nodes()
        )
        
    def identify_isolated_nodes(self, damaged_graph: nx.Graph) -> List[str]:
        """
        识别孤立节点
        
        参数：
            damaged_graph (nx.Graph): 故障后的网络
            
        返回：
            List[str]: 不在最大连通子图中的节点列表
            
        说明：
            - 获取最大连通分量（LCC）
            - 不在LCC中的节点视为"孤立"
            - 这些节点的人口无法通过铁路网络到达
        """
        if damaged_graph.number_of_nodes() == 0:
            return []
        
        # 获取所有连通分量
        components = list(nx.connected_components(damaged_graph))
        
        if not components:
            return list(damaged_graph.nodes())
        
        # 找出最大连通分量
        largest_component = max(components, key=len)
        
        # 孤立节点：在图中但不在LCC中
        isolated = [n for n in damaged_graph.nodes() 
                   if n not in largest_component]
        
        return isolated
    
    def calculate_robustness(self, damaged_graph: nx.Graph,
                           use_weights: bool = True) -> float:
        """
        计算人口加权鲁棒性指标
        
        参数：
            damaged_graph (nx.Graph): 故障后的网络
            use_weights (bool): 是否使用脆弱性权重
            
        返回：
            float: 鲁棒性值 Rw(α)，范围[0, 1]
            
        公式：
            Rw(α) = 1 - [∑(wi * Pi)_孤立] / [∑(wi * Pi)_全部]
            
        说明：
            当 use_weights=False 时，wi=1，公式简化为：
            R(α) = 1 - [∑Pi_孤立] / [∑Pi_全部]（人口未加权）
        """
        # 关键修正：鲁棒性定义为“当前最大连通分量（LCC）可达人口占原始总人口比例”
        # 这样在累积删除下理论上单调不增。
        if damaged_graph.number_of_nodes() == 0:
            return 0.0

        components = list(nx.connected_components(damaged_graph))
        largest_component = max(components, key=len) if components else set()

        if use_weights:
            accessible_population = sum(
                self.node_weights.get(n, 1.0) * self.node_populations.get(n, 0)
                for n in largest_component
            )
            denominator = self.total_weight_population
        else:
            accessible_population = sum(
                self.node_populations.get(n, 0)
                for n in largest_component
            )
            denominator = self.total_population

        # 避免除零
        if denominator == 0:
            return 0.0

        robustness = accessible_population / denominator
        return max(0.0, min(1.0, robustness))

    def _calculate_unreachable_population(self, damaged_graph: nx.Graph,
                                          use_weights: bool = True) -> float:
        """
        计算失去可达性的人口（包含已删除节点 + 非LCC节点）。
        """
        robustness = self.calculate_robustness(damaged_graph, use_weights=use_weights)
        if use_weights:
            denominator = self.total_weight_population
        else:
            denominator = self.total_population
        return (1.0 - robustness) * denominator

    def _enforce_non_increasing(self, values: List[float]) -> List[float]:
        """
        数值保护：将序列压成单调不增，消除浮点误差导致的微小回升。
        """
        if not values:
            return values
        arr = np.array(values, dtype=float)
        return list(np.minimum.accumulate(arr))
    
    def calculate_lcc_size(self, damaged_graph: nx.Graph,
                          metric: str = 'weighted_population') -> float:
        """
        计算最大连通分量的规模
        
        参数：
            damaged_graph (nx.Graph): 故障后的网络
            metric (str): 度量指标
                - 'nodes': 节点数
                - 'population': 人口总数
                - 'weighted_population': 加权人口总数
                
        返回：
            float: 各指标对应的LCC规模值
        """
        if damaged_graph.number_of_nodes() == 0:
            return 0
        
        components = list(nx.connected_components(damaged_graph))
        if not components:
            return 0
        
        largest_component = max(components, key=len)
        
        if metric == 'nodes':
            return len(largest_component)
        elif metric == 'population':
            return sum(self.node_populations.get(n, 0) 
                      for n in largest_component)
        elif metric == 'weighted_population':
            return sum(
                self.node_weights.get(n, 1.0) * self.node_populations.get(n, 0)
                for n in largest_component
            )
        else:
            raise ValueError(f"Unknown metric: {metric}")
    
    def analyze_failure_impact(self, failure_sequence: List[List[str]],
                              use_weights: bool = True) -> Dict:
        """
        分析在故障序列下的网络演化
        
        参数：
            failure_sequence (List[List[str]]): 每一步的故障节点列表
            use_weights (bool): 是否使用权重
            
        返回：
            Dict: 包含多个关键指标的分析结果
                - 'robustness_curve': 各步骤的鲁棒性值
                - 'alpha_values': 对应的故障强度
                - 'lcc_size': 各步骤的LCC规模
                - 'isolated_population': 各步骤的受影响人口
                
        说明：
            这是核心分析功能，返回的数据用于生成可视化
        """
        initial_robustness = self.calculate_robustness(self.original_graph, use_weights)
        robustness_values = [initial_robustness]
        alpha_values = [0.0]
        lcc_sizes = [self.calculate_lcc_size(self.original_graph, metric='nodes')]
        isolated_populations = [0]
        
        # 跟踪已移除的节点
        removed_nodes = set()
        
        for step_idx, failed_nodes in enumerate(failure_sequence):
            # 累积移除节点
            removed_nodes.update(failed_nodes)
            
            # 创建故障后的图
            damaged_graph = self.original_graph.copy()
            damaged_graph.remove_nodes_from(removed_nodes)
            
            # 计算当前步的故障强度
            total_nodes = self.original_graph.number_of_nodes()
            alpha = len(removed_nodes) / total_nodes if total_nodes > 0 else 0
            
            # 计算鲁棒性
            robustness = self.calculate_robustness(damaged_graph, use_weights)
            
            # 计算LCC
            lcc_size = self.calculate_lcc_size(damaged_graph, metric='nodes')
            
            # 受影响人口（包含已删除节点 + 非LCC节点）
            isolated_pop = self._calculate_unreachable_population(
                damaged_graph,
                use_weights=use_weights
            )
            
            robustness_values.append(robustness)
            alpha_values.append(alpha)
            lcc_sizes.append(lcc_size)
            isolated_populations.append(isolated_pop)

        # 数值保护，确保曲线单调不增
        robustness_values = self._enforce_non_increasing(robustness_values)
        
        return {
            'robustness_curve': robustness_values,
            'alpha_values': alpha_values,
            'lcc_size': lcc_sizes,
            'isolated_population': isolated_populations,
            'removed_nodes_count': len(removed_nodes),
        }


# ============================================================================
# 模块 4: 可视化模块
# ============================================================================

class RobustnessVisualizer:
    """
    鲁棒性结果可视化
    
    功能：
    - 绘制多种攻击策略的鲁棒性曲线
    - 对比分析
    - 生成高质量图表
    """

    @staticmethod
    def _display_strategy_name(strategy: str) -> str:
        """Normalize strategy names to English for chart legends."""
        strategy_map = {
            '随机失效': 'Random Failure',
            '度中心性攻击': 'Degree-based Attack',
            '介数中心性攻击': 'Betweenness-based Attack',
            'random': 'Random Failure',
            'degree': 'Degree-based Attack',
            'betweenness': 'Betweenness-based Attack',
        }
        return strategy_map.get(strategy, strategy)
    
    @staticmethod
    def plot_robustness_curves(results_dict: Dict,
                              figsize: Tuple = (12, 8),
                              save_path: Optional[str] = None):
        """
        绘制鲁棒性曲线对比图
        
        参数：
            results_dict (Dict): {策略名: 分析结果}的字典
            figsize (Tuple): 图表尺寸
            save_path (str, optional): 保存路径
            
        说明：
            - 在同一图中绘制多条曲线，便于对比
            - 不同颜色代表不同策略
        """
        fig, ax = plt.subplots(figsize=figsize)
        
        # 定义颜色和线型
        colors = ['#2E86AB', '#A23B72', '#F18F01', '#C73E1D']
        linestyles = ['-', '--', '-.', ':']

        for idx, (strategy, analysis_result) in enumerate(results_dict.items()):
            alpha = analysis_result['alpha_values']
            robustness = analysis_result['robustness_curve']
            
            ax.plot(alpha, robustness,
                   label=RobustnessVisualizer._display_strategy_name(strategy),
                   linewidth=2.5,
                   color=colors[idx % len(colors)],
                   linestyle=linestyles[idx % len(linestyles)],
                   marker='o',
                   markersize=4,
                   markerfacecolor='white',
                   markeredgewidth=1.5)

        ax.set_xlabel('Failure Intensity α (Node Removal Ratio)', fontsize=12, fontweight='bold')
        ax.set_ylabel('Population-Weighted Robustness Rw(α)', fontsize=12, fontweight='bold')
        ax.set_title('Population-Weighted Robustness of Railway Network', fontsize=14, fontweight='bold')
        ax.grid(True, alpha=0.3, linestyle='--')
        ax.set_xlim(0, 1)
        ax.set_ylim(0, 1.05)
        ax.legend(fontsize=10, loc='best', frameon=True, shadow=True)
        
        plt.tight_layout()
        
        if save_path:
            plt.savefig(save_path, dpi=300, bbox_inches='tight')
            print(f"图表已保存到: {save_path}")
        
        return fig, ax
    
    @staticmethod
    def plot_detailed_comparison(results_dict: Dict,
                                save_path: Optional[str] = None):
        """
        绘制详细的对比分析图（四张独立图片）
        
        参数：
            results_dict (Dict): {策略名: 分析结果}的字典
            save_path (str, optional): 保存路径前缀或单个文件路径。
                例如传入".../detailed_comparison.png"时，会生成：
                - detailed_comparison_robustness.png
                - detailed_comparison_lcc_size.png
                - detailed_comparison_isolated_population.png
                - detailed_comparison_integrity.png
        """
        colors = ['#2E86AB', '#A23B72', '#F18F01', '#C73E1D']

        # 为四个指标分别创建图表
        fig_robust, ax_robust = plt.subplots(figsize=(10, 7))
        fig_lcc, ax_lcc = plt.subplots(figsize=(10, 7))
        fig_iso_pop, ax_iso_pop = plt.subplots(figsize=(10, 7))
        fig_integrity, ax_integrity = plt.subplots(figsize=(10, 7))

        for idx, (strategy, analysis_result) in enumerate(results_dict.items()):
            alpha = np.array(analysis_result['alpha_values'])
            robustness = np.array(analysis_result['robustness_curve'])
            lcc_size = np.array(analysis_result['lcc_size'])
            isolated_pop = np.array(analysis_result['isolated_population'])
            color = colors[idx % len(colors)]
            display_strategy = RobustnessVisualizer._display_strategy_name(strategy)

            ax_robust.plot(alpha, robustness, label=display_strategy,
                           color=color, linewidth=2, marker='o', markersize=4)
            ax_lcc.plot(alpha, lcc_size, label=display_strategy,
                        color=color, linewidth=2, marker='s', markersize=4)
            ax_iso_pop.plot(alpha, isolated_pop, label=display_strategy,
                            color=color, linewidth=2, marker='^', markersize=4)

            # 网络完整性（LCC占比）
            integrity = (lcc_size / max(lcc_size) if max(lcc_size) > 0 else lcc_size)
            ax_integrity.plot(alpha, integrity, label=display_strategy,
                              color=color, linewidth=2, marker='d', markersize=4)

        ax_robust.set_xlabel('Failure Intensity α', fontsize=10)
        ax_robust.set_ylabel('Robustness Rw(α)', fontsize=10)
        ax_robust.set_title('Population-Weighted Robustness Curve', fontsize=11, fontweight='bold')
        ax_robust.grid(True, alpha=0.3)
        ax_robust.legend(fontsize=9)
        fig_robust.tight_layout()

        ax_lcc.set_xlabel('Failure Intensity α', fontsize=10)
        ax_lcc.set_ylabel('LCC Node Count', fontsize=10)
        ax_lcc.set_title('Largest Connected Component Size', fontsize=11, fontweight='bold')
        ax_lcc.grid(True, alpha=0.3)
        ax_lcc.legend(fontsize=9)
        fig_lcc.tight_layout()

        ax_iso_pop.set_xlabel('Failure Intensity α', fontsize=10)
        ax_iso_pop.set_ylabel('Isolated Population', fontsize=10)
        ax_iso_pop.set_title('Isolated Population Count', fontsize=11, fontweight='bold')
        ax_iso_pop.grid(True, alpha=0.3)
        ax_iso_pop.legend(fontsize=9)
        fig_iso_pop.tight_layout()

        ax_integrity.set_xlabel('Failure Intensity α', fontsize=10)
        ax_integrity.set_ylabel('Network Integrity', fontsize=10)
        ax_integrity.set_title('Connectivity Retention Ratio', fontsize=11, fontweight='bold')
        ax_integrity.grid(True, alpha=0.3)
        ax_integrity.legend(fontsize=9)
        fig_integrity.tight_layout()

        figs = {
            'robustness': fig_robust,
            'lcc_size': fig_lcc,
            'isolated_population': fig_iso_pop,
            'integrity': fig_integrity,
        }
        axes = {
            'robustness': ax_robust,
            'lcc_size': ax_lcc,
            'isolated_population': ax_iso_pop,
            'integrity': ax_integrity,
        }

        if save_path:
            import os
            base_path, ext = os.path.splitext(save_path)
            ext = ext if ext else '.png'

            output_paths = {
                'robustness': f"{base_path}_robustness{ext}",
                'lcc_size': f"{base_path}_lcc_size{ext}",
                'isolated_population': f"{base_path}_isolated_population{ext}",
                'integrity': f"{base_path}_integrity{ext}",
            }

            for key, fig in figs.items():
                fig.savefig(output_paths[key], dpi=300, bbox_inches='tight')

            print("详细对比图已分别保存到:")
            for key in ['robustness', 'lcc_size', 'isolated_population', 'integrity']:
                print(f"  - {output_paths[key]}")

        return figs, axes
    
    @staticmethod
    def plot_network_structure(graph: nx.Graph, 
                              node_populations: Dict[str, float],
                              figsize: Tuple = (14, 10),
                              save_path: Optional[str] = None):
        """
        绘制网络拓扑结构
        
        参数：
            graph (nx.Graph): 网络图
            node_populations (Dict): 节点人口数据
            figsize (Tuple): 图表尺寸
            save_path (str, optional): 保存路径
            
        说明：
            节点大小反映服务人口大小
        """
        fig, ax = plt.subplots(figsize=figsize)
        
        # 使用弹簧布局
        pos = nx.spring_layout(graph, k=0.5, iterations=50, seed=42)
        
        # 节点大小与人口成正比
        node_sizes = [
            max(100, min(3000, node_populations.get(node, 100) / 10000))
            for node in graph.nodes()
        ]
        
        # 绘制边
        nx.draw_networkx_edges(graph, pos, ax=ax, width=1.5, alpha=0.6, edge_color='gray')
        
        # 绘制节点
        nodes = nx.draw_networkx_nodes(graph, pos, ax=ax,
                                       node_size=node_sizes,
                                       node_color='#2E86AB',
                                       alpha=0.8,
                                       edgecolors='darkblue',
                                       linewidths=1.5)
        
        # 绘制标签（仅显示高度中心的节点的标签，避免拥挤）
        labels = {node: node for node in graph.nodes() 
                 if node_populations.get(node, 0) > np.percentile(
                     list(node_populations.values()), 80)}
        nx.draw_networkx_labels(graph, pos, ax=ax, labels=labels, 
                               font_size=8, font_weight='bold')
        
        ax.set_title('Railway Network Topology (Node Size = Served Population)',
                fontsize=13, fontweight='bold', pad=20)
        ax.axis('off')
        
        plt.tight_layout()
        
        if save_path:
            plt.savefig(save_path, dpi=300, bbox_inches='tight')
            print(f"网络结构图已保存到: {save_path}")
        
        return fig, ax

    @staticmethod
    def plot_network_structure_folium(graph: nx.Graph,
                                      node_populations: Dict[str, float],
                                      node_coordinates: Dict[str, Tuple[float, float]],
                                      save_path: Optional[str] = None):
        """
        使用 Folium 在真实地理底图上绘制网络结构。

        参数：
            graph (nx.Graph): 网络图
            node_populations (Dict): 节点人口数据
            node_coordinates (Dict): {节点名: (纬度, 经度)}
            save_path (str, optional): HTML 保存路径
        """
        try:
            import folium
        except ImportError as e:
            raise ImportError("未安装 folium，请先运行: pip install folium") from e

        valid_coords = {
            node: coord for node, coord in node_coordinates.items()
            if node in graph.nodes() and coord is not None
        }
        if not valid_coords:
            raise ValueError("没有可用于 Folium 绘图的节点坐标数据")

        lats = [lat for lat, _ in valid_coords.values()]
        lons = [lon for _, lon in valid_coords.values()]
        center_lat = float(np.mean(lats))
        center_lon = float(np.mean(lons))

        m = folium.Map(location=[center_lat, center_lon], zoom_start=4, tiles='CartoDB positron')

        edge_layer = folium.FeatureGroup(name='Railway Links', show=True)
        node_layer = folium.FeatureGroup(name='Stations', show=True)

        for u, v in graph.edges():
            if u not in valid_coords or v not in valid_coords:
                continue
            (lat_u, lon_u) = valid_coords[u]
            (lat_v, lon_v) = valid_coords[v]
            folium.PolyLine(
                locations=[(lat_u, lon_u), (lat_v, lon_v)],
                color='#5A6C7D',
                weight=1.2,
                opacity=0.55,
            ).add_to(edge_layer)

        pop_values = [max(0, node_populations.get(node, 0)) for node in valid_coords]
        if pop_values and max(pop_values) > 0:
            pop_max = max(pop_values)
            label_threshold = np.percentile(pop_values, 90)
        else:
            pop_max = 1
            label_threshold = 0

        for node, (lat, lon) in valid_coords.items():
            pop = max(0, node_populations.get(node, 0))
            radius = 3 + 9 * (pop / pop_max)
            popup_html = (
                f"<b>{node}</b><br>"
                f"Served Population: {int(pop):,}<br>"
                f"Degree: {graph.degree(node)}"
            )
            tooltip_text = node if pop >= label_threshold else None

            folium.CircleMarker(
                location=[lat, lon],
                radius=radius,
                color='#1D3557',
                weight=1,
                fill=True,
                fill_color='#2E86AB',
                fill_opacity=0.8,
                popup=folium.Popup(popup_html, max_width=260),
                tooltip=tooltip_text,
            ).add_to(node_layer)

        edge_layer.add_to(m)
        node_layer.add_to(m)
        folium.LayerControl(collapsed=False).add_to(m)

        if save_path:
            m.save(save_path)
            print(f"Folium网络结构地图已保存到: {save_path}")

        return m


# ============================================================================
# 模块 5: 敏感性分析器（可选扩展）
# ============================================================================

class SensitivityAnalyzer:
    """
    敏感性分析工具
    
    功能：
    - 分析权重参数对鲁棒性的影响
    - 参数不确定性分析
    """
    
    @staticmethod
    def analyze_weight_sensitivity(calculator: RobustnessCalculator,
                                  failure_sequence: List[List[str]],
                                  weight_variations: List[float]) -> Dict:
        """
        权重灵敏度分析
        
        参数：
            calculator (RobustnessCalculator): 鲁棒性计算器
            failure_sequence (List[List[str]]): 故障序列
            weight_variations (List[float]): 权重变化因子（如 [0.5, 1.0, 1.5]）
            
        返回：
            Dict: 不同权重下的分析结果
        """
        results = {}
        
        for variation in weight_variations:
            # 调整权重
            adjusted_weights = {
                node: calculator.node_weights.get(node, 1.0) * variation
                for node in calculator.original_graph.nodes()
            }
            
            # 创建新计算器（使用调整后的权重）
            temp_calc = RobustnessCalculator(
                calculator.original_graph,
                calculator.node_populations,
                adjusted_weights
            )
            
            # 分析
            analysis = temp_calc.analyze_failure_impact(failure_sequence)
            results[f'Weight Factor={variation:.1f}'] = analysis
        
        return results


# ============================================================================
# 模块 6: 区域级鲁棒性分析器
# ============================================================================

class RegionalRobustnessAnalyzer:
    """
    区域级鲁棒性分析工具
    
    功能：
    - 按地理区域（东、中、西）划分网络
    - 分别分析各区域的鲁棒性
    - 对比分析和识别脆弱性差异
    """
    
    # 区域划分（按省份）
    REGION_MAP = {
        'East': [
            '北京市', '天津市', '河北省', '山东省', '江苏省', '上海市',
            '浙江省', '福建省', '广东省', '海南省', '辽宁省', '青岛市',
            '山西省'  # 可选：通常晋南属东部
        ],
        'Central': [
            '河南省', '湖北省', '湖南省', '江西省', '安徽省', '山西省',
            '陕西省', '重庆市'
        ],
        'West': [
            '四川省', '云南省', '贵州省', '甘肃省', '青海省', '宁夏回族自治区',
            '新疆维吾尔自治区', '西藏自治区', '内蒙古自治区'
        ]
    }
    
    def __init__(self, builder: 'RailNetworkBuilder', graph: nx.Graph,
                 calculator: RobustnessCalculator):
        """
        初始化区域分析器
        
        参数：
            builder (RailNetworkBuilder): 网络构建器
            graph (nx.Graph): 完整网络图
            calculator (RobustnessCalculator): 鲁棒性计算器
        """
        self.builder = builder
        self.graph = graph
        self.calculator = calculator
        self.regional_graphs = {}
        self.regional_results = {}
        
    def _extract_subgraph_by_region(self, region: str) -> Tuple[nx.Graph, Dict]:
        """
        按区域提取子网络
        
        参数：
            region (str): 区域名 ('East', 'Central', 'West')
            
        返回：
            Tuple: (子图, 该区域的节点人口字典)
        """
        if region not in self.REGION_MAP:
            raise ValueError(f"未知区域：{region}")
        
        provinces = self.REGION_MAP[region]
        
        # 识别属于该区域的所有节点
        regional_nodes = []
        for node in self.graph.nodes():
            # 查找节点对应的省份
            station_rows = self.builder.stations_df[
                self.builder.stations_df['station_name'] == node
            ]
            if not station_rows.empty:
                province = station_rows.iloc[0]['province']
                if province in provinces:
                    regional_nodes.append(node)
        
        # 提取子图（仅保留区域内的节点和它们之间的边）
        subgraph = self.graph.subgraph(regional_nodes).copy()
        
        # 区域内的人口数据
        regional_population = {
            node: self.calculator.node_populations.get(node, 0)
            for node in regional_nodes
        }
        
        return subgraph, regional_population
    
    def analyze_region(self, region: str, alpha_steps: int = 20) -> Dict:
        """
        分析单个区域的鲁棒性
        
        参数：
            region (str): 区域名
            alpha_steps (int): 故障强度步数
            
        返回：
            Dict: 该区域的分析结果（包含3种攻击策略）
        """
        # 提取区域子图
        subgraph, regional_pop = self._extract_subgraph_by_region(region)
        
        if subgraph.number_of_nodes() == 0:
            print(f"  警告：{region}区域无节点数据")
            return {}
        
        # 创建区域级鲁棒性计算器
        regional_weights = {
            node: self.calculator.node_weights.get(node, 1.0)
            for node in subgraph.nodes()
        }
        regional_calc = RobustnessCalculator(
            subgraph,
            regional_pop,
            regional_weights
        )
        
        # 对三种策略分别分析
        region_results = {}
        strategies = [
            ('Random Failure', 'random'),
            ('Degree-based Attack', 'degree'),
            ('Betweenness-based Attack', 'betweenness'),
        ]
        
        for strategy_name, strategy_mode in strategies:
            # 模拟故障
            simulator = FailureSimulator(subgraph)
            failure_seq = simulator.simulate_cascade_failure(
                failure_mode=strategy_mode,
                alpha_steps=alpha_steps
            )
            
            # 计算鲁棒性
            analysis = regional_calc.analyze_failure_impact(
                failure_seq,
                use_weights=True
            )
            region_results[strategy_name] = analysis
        
        # 记录区域信息
        self.regional_graphs[region] = subgraph
        self.regional_results[region] = {
            'results': region_results,
            'info': {
                'nodes': subgraph.number_of_nodes(),
                'edges': subgraph.number_of_edges(),
                'population': sum(regional_pop.values()),
                'density': nx.density(subgraph),
            }
        }
        
        return region_results
    
    def analyze_all_regions(self, alpha_steps: int = 20) -> Dict:
        """
        分析所有区域
        
        返回：
            Dict: {区域: 分析结果}
        """
        all_results = {}
        
        for region in ['East', 'Central', 'West']:
            print(f"  分析区域：{region}...")
            results = self.analyze_region(region, alpha_steps=alpha_steps)
            all_results[region] = results
        
        return all_results
    
    def extract_critical_threshold(self, strategy_name: str = 'Degree-based Attack') -> Dict:
        """
        提取各区域的临界阈值（鲁棒性降到0.5的故障强度）
        
        参数：
            strategy_name (str): 策略名
            
        返回：
            Dict: {区域: 临界阈值α_c}
        """
        thresholds = {}
        
        for region, data in self.regional_results.items():
            results = data['results']
            if strategy_name in results:
                analysis = results[strategy_name]
                alpha = analysis['alpha_values']
                robustness = analysis['robustness_curve']
                
                # 找到鲁棒性最先降到0.5的点
                for a, r in zip(alpha, robustness):
                    if r <= 0.5:
                        thresholds[region] = a
                        break
                else:
                    thresholds[region] = 1.0  # 未触及0.5
        
        return thresholds
    
    def extract_decay_rate(self, strategy_name: str = 'Degree-based Attack') -> Dict:
        """
        提取各区域的衰减速率（鲁棒性曲线平均下降速）
        
        参数：
            strategy_name (str): 策略名
            
        返回：
            Dict: {区域: 平均下降速率}
        """
        decay_rates = {}
        
        for region, data in self.regional_results.items():
            results = data['results']
            if strategy_name in results:
                analysis = results[strategy_name]
                robustness = np.array(analysis['robustness_curve'])
                
                # 计算平均下降速率：(R(0) - R(1)) / 步数
                if len(robustness) > 1:
                    decay = (robustness[0] - robustness[-1]) / (len(robustness) - 1)
                    decay_rates[region] = decay
        
        return decay_rates
    
    def plot_regional_comparison(self, strategy_name: str = 'Degree-based Attack',
                                save_dir: Optional[str] = None):
        """
        绘制区域鲁棒性对比图
        
        参数：
            strategy_name (str): 策略名
            save_dir (str, optional): 保存目录
        """
        fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(16, 6))
        
        colors = {'East': '#2E86AB', 'Central': '#A23B72', 'West': '#F18F01'}
        region_names = {'East': 'East Region', 'Central': 'Central Region', 'West': 'West Region'}
        
        # 左图：鲁棒性曲线对比
        for region in ['East', 'Central', 'West']:
            if region not in self.regional_results:
                continue
            
            results = self.regional_results[region]['results']
            if strategy_name in results:
                analysis = results[strategy_name]
                alpha = analysis['alpha_values']
                robustness = analysis['robustness_curve']
                
                ax1.plot(alpha, robustness, label=region_names[region],
                        color=colors[region], linewidth=2.5, marker='o', markersize=5)
        
        ax1.set_xlabel('Failure Intensity α', fontsize=12, fontweight='bold')
        ax1.set_ylabel('Robustness Rw(α)', fontsize=12, fontweight='bold')
        ax1.set_title(f'Regional Robustness Comparison ({strategy_name})',
                     fontsize=13, fontweight='bold')
        ax1.grid(True, alpha=0.3)
        ax1.legend(fontsize=10)
        ax1.set_xlim(0, 1)
        ax1.set_ylim(0, 1.05)
        
        # 右图：关键指标对比（条形图）
        thresholds = self.extract_critical_threshold(strategy_name)
        regions = list(thresholds.keys())
        threshold_values = [thresholds[r] for r in regions]
        
        region_labels = [region_names.get(r, r) for r in regions]
        bars = ax2.bar(region_labels, threshold_values,
                      color=[colors[r] for r in regions], alpha=0.7, edgecolor='black', linewidth=1.5)
        
        # 在每个柱子上显示数值
        for bar, val in zip(bars, threshold_values):
            height = bar.get_height()
            ax2.text(bar.get_x() + bar.get_width()/2., height,
                    f'{val:.3f}', ha='center', va='bottom', fontweight='bold')
        
        ax2.set_ylabel('Critical Threshold α_c', fontsize=12, fontweight='bold')
        ax2.set_title('Regional Critical Breakdown Points',
                     fontsize=13, fontweight='bold')
        ax2.set_ylim(0, 1.1)
        ax2.grid(True, alpha=0.3, axis='y')
        
        plt.tight_layout()
        
        if save_dir:
            save_path = f"{save_dir}/regional_comparison_{strategy_name}.png"
            plt.savefig(save_path, dpi=300, bbox_inches='tight')
            print(f"区域对比图已保存到：{save_path}")
        
        return fig, (ax1, ax2)
    
    def plot_regional_population_loss(self, strategy_name: str = 'Degree-based Attack',
                                      save_dir: Optional[str] = None):
        """
        绘制区域人口损失对比
        
        参数：
            strategy_name (str): 策略名
            save_dir (str, optional): 保存目录
        """
        fig, ax = plt.subplots(figsize=(12, 7))
        
        colors = {'East': '#2E86AB', 'Central': '#A23B72', 'West': '#F18F01'}
        region_names = {'East': 'East Region', 'Central': 'Central Region', 'West': 'West Region'}
        
        for region in ['East', 'Central', 'West']:
            if region not in self.regional_results:
                continue
            
            results = self.regional_results[region]['results']
            if strategy_name in results:
                analysis = results[strategy_name]
                alpha = analysis['alpha_values']
                isolated_pop = np.array(analysis['isolated_population'])
                
                # 归一化为百万人
                isolated_pop_millions = isolated_pop / 1e6
                
                ax.plot(alpha, isolated_pop_millions, label=region_names[region],
                       color=colors[region], linewidth=2.5, marker='s', markersize=5)
        
        ax.set_xlabel('Failure Intensity α', fontsize=12, fontweight='bold')
        ax.set_ylabel('Isolated Population (Million)', fontsize=12, fontweight='bold')
        ax.set_title(f'Regional Population Loss Under {strategy_name}',
                    fontsize=13, fontweight='bold')
        ax.grid(True, alpha=0.3)
        ax.legend(fontsize=10)
        ax.set_xlim(0, 1)
        
        plt.tight_layout()
        
        if save_dir:
            save_path = f"{save_dir}/regional_population_loss_{strategy_name}.png"
            plt.savefig(save_path, dpi=300, bbox_inches='tight')
            print(f"人口损失图已保存到：{save_path}")
        
        return fig, ax
    
    def print_regional_summary(self):
        """
        打印区域分析总结
        """
        print("\n[Regional Summary]")
        print("=" * 70)
        
        for region in ['East', 'Central', 'West']:
            if region not in self.regional_results:
                continue
            
            region_names = {'East': 'East Region', 'Central': 'Central Region', 'West': 'West Region'}
            info = self.regional_results[region]['info']
            
            print(f"\n{region_names[region]}：")
            print(f"  Nodes: {info['nodes']}")
            print(f"  Edges: {info['edges']}")
            print(f"  Total population: {info['population']/1e8:.2f} hundred million people")
            print(f"  Network density: {info['density']:.4f}")
            
            # 各策略的临界阈值
            for strategy in ['Random Failure', 'Degree-based Attack', 'Betweenness-based Attack']:
                thresholds = self.extract_critical_threshold(strategy)
                if region in thresholds:
                    print(f"  {strategy} critical point: α={thresholds[region]:.3f}")


# ============================================================================
# 主函数：完整工作流示例
# ============================================================================

def main():
    """
    主函数：演示完整的人口加权鲁棒性分析工作流
    """
    print("=" * 70)
    print("铁路网络人口加权鲁棒性分析框架")
    print("=" * 70)
    
    # ---- 步骤1：数据加载与网络构建 ----
    print("\n[步骤1] 加载数据并构建网络...")
    
    # 文件路径
    stations_file = r"c:\Users\16639\Desktop\FYP_QMM2_Chinese_Railways\data\stations.csv"
    tracks_file = r"c:\Users\16639\Desktop\FYP_QMM2_Chinese_Railways\data\tracks.csv"
    population_file = r"c:\Users\16639\Desktop\FYP_QMM2_Chinese_Railways\data\ChinaCities_Swerts.csv"
    
    # 构建网络（使用所有轨道，不限定年份）
    builder = RailNetworkBuilder(stations_file, tracks_file, population_file)
    graph = builder.build_network(year=None, simplify=True)
    
    # 打印网络信息
    info = builder.get_network_info()
    print(f"  网络节点数：{info['number_of_nodes']}")
    print(f"  网络边数：{info['number_of_edges']}")
    print(f"  网络密度：{info['density']:.4f}")
    print(f"  是否连通：{info['is_connected']}")
    print(f"  连通分量数：{info['number_of_components']}")
    
    # ---- 步骤2：分配人口和权重 ----
    print("\n[步骤2] 加载真实人口数据并分配权重...")
    
    # 使用真实人口数据（2010年）
    builder.load_real_population_data(year=2010)
    
    # 分配脆弱性权重
    builder.assign_node_weights(strategy='economic_importance')
    print(f"  分配脆弱性权重：{len(builder.node_weights)} 个节点")
    
    # ---- 步骤3：故障模拟与鲁棒性计算 ----
    print("\n[步骤3] 执行故障模拟与鲁棒性计算...")
    
    # 创建鲁棒性计算器
    calculator = RobustnessCalculator(
        graph,
        builder.node_populations,
        builder.node_weights
    )
    
    # 分析结果存储
    results_dict = {}
    
    # 测试三种故障策略
    strategies = [
        ('Random Failure', 'random'),
        ('Degree-based Attack', 'degree'),
        ('Betweenness-based Attack', 'betweenness'),
    ]
    
    for strategy_name, strategy_mode in strategies:
        print(f"\n  分析策略：{strategy_name}...")
        
        # 重置模拟器
        simulator = FailureSimulator(graph)
        
        # 生成故障序列
        failure_sequence = simulator.simulate_cascade_failure(
            failure_mode=strategy_mode,
            alpha_steps=20
        )
        
        # 计算鲁棒性
        analysis_result = calculator.analyze_failure_impact(
            failure_sequence,
            use_weights=True
        )
        
        results_dict[strategy_name] = analysis_result
        
        # 输出关键指标
        final_robustness = analysis_result['robustness_curve'][-1]
        print(f"    最终鲁棒性值：{final_robustness:.4f}")
        print(f"    被移除节点数：{analysis_result['removed_nodes_count']}")
    
    # ---- 步骤4：可视化结果 ----
    print("\n[步骤4] 生成可视化结果...")
    
    output_dir = Path(r"c:\Users\16639\Desktop\FYP_QMM2_Chinese_Railways\results\robustness_analysis")
    output_dir.mkdir(parents=True, exist_ok=True)
    
    # 绘制鲁棒性曲线对比
    fig1_path = output_dir / "robustness_curves.png"
    RobustnessVisualizer.plot_robustness_curves(
        results_dict,
        save_path=str(fig1_path)
    )
    
    # 绘制详细对比分析
    fig2_path = output_dir / "detailed_comparison.png"
    RobustnessVisualizer.plot_detailed_comparison(
        results_dict,
        save_path=str(fig2_path)
    )
    
    # 绘制网络结构
    fig3_path = output_dir / "network_structure.png"
    RobustnessVisualizer.plot_network_structure(
        graph,
        builder.node_populations,
        save_path=str(fig3_path)
    )

    # 在真实地理底图上绘制网络结构（Folium）
    station_coords = {
        row['station_name']: (float(row['latitude']), float(row['longitude']))
        for _, row in builder.stations_df.iterrows()
        if pd.notna(row.get('latitude')) and pd.notna(row.get('longitude'))
    }
    folium_map_path = output_dir / "network_structure_folium.html"
    RobustnessVisualizer.plot_network_structure_folium(
        graph,
        builder.node_populations,
        station_coords,
        save_path=str(folium_map_path)
    )
    
    print(f"\n  已生成 7 个可视化结果（含 detailed_comparison 的4张独立图 + 1个Folium地图）")
    print(f"  保存目录：{output_dir}")
    
    # ---- 步骤5：区域级鲁棒性分析（新功能）----
    print("\n[步骤5] 执行区域级鲁棒性分析...")
    
    regional_analyzer = RegionalRobustnessAnalyzer(builder, graph, calculator)
    regional_analyzer.analyze_all_regions(alpha_steps=20)
    
    # 绘制区域对比图
    for strategy in ['Random Failure', 'Degree-based Attack', 'Betweenness-based Attack']:
        regional_analyzer.plot_regional_comparison(strategy_name=strategy, save_dir=str(output_dir))
        regional_analyzer.plot_regional_population_loss(strategy_name=strategy, save_dir=str(output_dir))
    
    regional_analyzer.print_regional_summary()
    
    # ---- 步骤6：生成总结报告 ----
    print("\n[步骤6] 生成分析报告...")
    
    report = generate_analysis_report(
        results_dict,
        info,
        builder.node_populations
    )
    
    report_path = output_dir / "analysis_report.txt"
    with open(report_path, 'w', encoding='utf-8') as f:
        f.write(report)
    
    print(f"\n  报告已保存到：{report_path}")
    
    print("\n" + "=" * 70)
    print("分析完成！")
    print("=" * 70)
    
    return builder, calculator, results_dict, report


def generate_analysis_report(results_dict: Dict, network_info: Dict,
                            node_populations: Dict) -> str:
    """
    生成文字分析报告
    
    参数：
        results_dict (Dict): 所有策略的分析结果
        network_info (Dict): 网络基本信息
        node_populations (Dict): 节点人口数据
        
    返回：
        str: 报告文本
    """
    report = []
    report.append("=" * 70)
    report.append("铁路网络人口加权鲁棒性分析报告")
    report.append("=" * 70)
    report.append(f"生成时间：2026-03-23\n")
    
    # 网络概况
    report.append("\n【网络概况】")
    report.append(f"  节点数（车站）：{network_info['number_of_nodes']}")
    report.append(f"  边数（轨道）：{network_info['number_of_edges']}")
    report.append(f"  网络密度：{network_info['density']:.4f}")
    report.append(f"  平均度数：{network_info['average_degree']:.2f}")
    report.append(f"  总服务人口：{sum(node_populations.values())/1e8:.2f} 亿人")
    report.append(f"  网络连通性：{'连通' if network_info['is_connected'] else '非连通'}")
    
    # 各策略结果
    report.append("\n【故障模式对比分析】\n")
    
    for strategy_name, analysis_result in results_dict.items():
        report.append(f"\n策略：{strategy_name}")
        report.append("-" * 50)
        
        robustness = analysis_result['robustness_curve']
        alpha = analysis_result['alpha_values']
        
        # 计算关键指标
        initial_robustness = robustness[0]
        final_robustness = robustness[-1]
        robustness_loss = initial_robustness - final_robustness
        
        # 计算半衰深度（鲁棒性降至0.5的故障强度）
        half_life_alpha = None
        for i, (a, r) in enumerate(zip(alpha, robustness)):
            if r <= 0.5:
                half_life_alpha = a
                break
        
        report.append(f"  初始鲁棒性：{initial_robustness:.4f}")
        report.append(f"  最终鲁棒性：{final_robustness:.4f}")
        report.append(f"  鲁棒性丧失：{robustness_loss:.4f}")
        
        if half_life_alpha:
            report.append(f"  鲁棒性半衰点：α={half_life_alpha:.4f}")
        else:
            report.append(f"  鲁棒性半衰点：未达到0.5")
    
    # 学术解释
    report.append("\n【学术解释与发现】\n")
    report.append("""
1. 鲁棒性曲线含义：
   - 水平型曲线：网络能够容容忍大部分节点失效，具有强健性
   - 陡峭型曲线：网络脆弱，少量关键节点失效导致快速崩溃
   - 位移型曲线：不同策略造成的破坏程度差异

2. 三种故障模式的区别：
   随机失效 (Random):
   - 每个节点等概率失效
   - 最符合自然灾害场景
   - 通常造成最温和的破坏

   度中心性攻击 (Degree-based):
   - 优先攻击度数最高的枢纽节点
   - 模拟针对高流量枢纽的蓄意破坏
   - 通常造成中等破坏

   介数中心性攻击 (Betweenness-based):
   - 优先攻击充当"桥梁"角色的关键节点
   - 这些节点破坏造成网络分片
   - 通常最具破坏性

3. 人口加权 vs 未加权：
   - 加权：考虑不同节点服务的人口规模
   - 反映真实的人口可达性影响
   - 经济和社会影响评估的关键

4. 临界阈值：
   - 鲁棒性大幅下降的点表示网络的临界脆弱区域
   - 这些点对应的节点应被列为保护优先级最高的对象
""")
    
    report.append("\n【建议与启示】\n")
    report.append("""
1. 基础设施投资优先级：
   - 加强介数中心性高的节点（特别是跨区域连接点）
   - 增加网络冗余度和连接多样性

2. 应急预案：
   - 针对不同故障模式制定应急响应机制
   - 重点保护人口密集区的连通性

3. 网络扩展建议：
   - 增加新的轨道连接来提高网络连通度
   - 优先连接目前处于"孤立"风险的区域

4. 定期评估：
   - 随着网络演化定期重新评估鲁棒性
   - 跟踪人口变化对鲁棒性的影响
""")
    
    report.append("\n" + "=" * 70)
    
    return "\n".join(report)


if __name__ == "__main__":
    # 运行主分析流程
    builder, calculator, results_dict, report = main()
    
    # 打印报告到控制台
    print("\n" + report)
