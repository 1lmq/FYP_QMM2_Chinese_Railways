"""
人口加权鲁棒性分析 - 配置文件示例
===================================

本文件提供了常用的配置参数，用户可根据实际需求修改。
"""

# ============================================================================
# 数据路径配置
# ============================================================================

DATA_CONFIG = {
    # 输入文件路径
    'stations_file': r"c:\Users\16639\Desktop\FYP_QMM2_Chinese_Railways\data\stations.csv",
    'tracks_file': r"c:\Users\16639\Desktop\FYP_QMM2_Chinese_Railways\data\tracks.csv",
    'population_file': r"c:\Users\16639\Desktop\FYP_QMM2_Chinese_Railways\data\ChinaCities_Swerts.csv",
    
    # 输出目录
    'output_directory': r"c:\Users\16639\Desktop\FYP_QMM2_Chinese_Railways\results\robustness_analysis",
}

# ============================================================================
# 网络构建参数
# ============================================================================

NETWORK_CONFIG = {
    # 年份筛选：None表示使用所有数据
    'target_year': None,
    
    # 是否简化多重边
    'simplify_edges': True,
    
    # 边权重属性名
    'edge_weight_attribute': 'weight',
}

# ============================================================================
# 人口数据配置
# ============================================================================

POPULATION_CONFIG = {
    # 人口数据来源
    # 可选：'synthetic','actual','file'
    'source': 'synthetic',
    
    # 生成策略（当source='synthetic'时）
    # 选项：'provincial_based', 'degree_based', 'uniform'
    'generation_strategy': 'provincial_based',
    
    # 单位：人（若要以万人为单位，设置为10000）
    'unit': 1,
    
    # 实际人口数据（若source='actual'）
    # 格式：{'站点名': 人口数}
    'actual_population': {
        # 示例：
        # '北京市': 2171 * 10000,
        # '上海市': 2428 * 10000,
    },
}

# ============================================================================
# 权重配置
# ============================================================================

WEIGHT_CONFIG = {
    # 脆弱性权重生成策略
    # 选项：'uniform', 'economic_importance', 'geographic_centrality'
    'strategy': 'economic_importance',
    
    # 权重范围
    'min_weight': 0.5,
    'max_weight': 2.0,
    
    # 重要城市的自定义权重（若需要）
    'custom_weights': {
        # 示例：
        # '北京市': 2.0,
        # '上海市': 2.0,
        # '广州市': 1.8,
    },
}

# ============================================================================
# 故障模拟参数
# ============================================================================

FAILURE_CONFIG = {
    # 故障模型列表（可同时运行多个）
    'failure_modes': ['random', 'degree', 'betweenness'],
    
    # 故障强度的步数（α从0到1）
    # 更多步数 = 更精细的分析，但耗时更长
    'alpha_steps': 20,
    
    # 最大节点移除数（可选上限）
    'max_nodes_to_remove': None,  # None表示无限制
    
    # 故障参数（高级）
    'random_seed': 42,  # 随机种子，用于再现性
}

# ============================================================================
# 可视化配置
# ============================================================================

VISUALIZATION_CONFIG = {
    # 输出格式
    'format': 'png',  # 或 'pdf', 'jpg'
    
    # 分辨率（DPI）
    'dpi': 300,
    
    # 图表尺寸（英寸）
    'figsize': {
        'robustness_curves': (12, 8),
        'detailed_comparison': (14, 10),
        'network_structure': (14, 10),
    },
    
    # 颜色方案
    'color_scheme': 'default',  # 或 'colorblind', 'grayscale'
    
    # 是否显示图表
    'show_plots': False,
    
    # 是否保存图表
    'save_plots': True,
}

# ============================================================================
# 分析范围配置
# ============================================================================

ANALYSIS_CONFIG = {
    # 是否进行基础分析（3种故障模式）
    'run_basic_analysis': True,
    
    # 是否进行时间演化分析
    'run_temporal_analysis': False,
    'temporal_years': [1990, 2000, 2010, 2020],  # 分析的年份
    
    # 是否进行敏感性分析
    'run_sensitivity_analysis': False,
    'sensitivity_weight_multipliers': [0.5, 0.8, 1.0, 1.2, 1.5],
    
    # 是否进行可达性阈值分析
    'run_accessibility_analysis': False,
    'distance_thresholds': [500, 800, 1200],  # km
    
    # 是否进行故障传播分析
    'run_propagation_analysis': False,
}

# ============================================================================
# 高级参数
# ============================================================================

ADVANCED_CONFIG = {
    # 是否使用加权网络（考虑边的权重）
    'use_weighted_network': False,
    
    # 可达性定义
    # 'lcc': 最大连通分量
    # 'distance_threshold': 距离阈值
    'reachability_definition': 'lcc',
    
    # 是否将孤立的连通分量视为受影响
    'count_small_components_as_affected': True,
    
    # 数值精度
    'precision': 4,  # 四舍五入到小数点后4位
    
    # 多线程处理（加速）
    'use_parallel_processing': False,
    'num_workers': 4,
}

# ============================================================================
# 输出报告配置
# ============================================================================

REPORT_CONFIG = {
    # 是否生成文本报告
    'generate_text_report': True,
    
    # 报告包含的内容
    'report_sections': [
        'network_overview',
        'failure_analysis',
        'academic_interpretation',
        'recommendations',
    ],
    
    # 是否生成CSV表格数据
    'export_csv': True,
    
    # 是否生成JSON格式的详细数据
    'export_json': False,
}

# ============================================================================
# 预设配置方案
# ============================================================================

# 方案1：快速分析（用于初步测试）
QUICK_ANALYSIS = {
    'alpha_steps': 10,
    'failure_modes': ['random', 'degree'],
    'run_sensitivity_analysis': False,
    'run_temporal_analysis': False,
}

# 方案2：标准分析（推荐用于学术研究）
STANDARD_ANALYSIS = {
    'alpha_steps': 20,
    'failure_modes': ['random', 'degree', 'betweenness'],
    'run_sensitivity_analysis': True,
    'run_propagation_analysis': True,
}

# 方案3：完整分析（全功能，耗时较长）
COMPREHENSIVE_ANALYSIS = {
    'alpha_steps': 25,
    'failure_modes': ['random', 'degree', 'betweenness'],
    'run_sensitivity_analysis': True,
    'run_propagation_analysis': True,
    'run_temporal_analysis': True,
    'run_accessibility_analysis': True,
    'use_parallel_processing': True,
}

# ============================================================================
# 使用示例
# ============================================================================

"""
# 方式1：使用默认配置
from config import DATA_CONFIG, NETWORK_CONFIG, POPULATION_CONFIG

builder = RailNetworkBuilder(
    DATA_CONFIG['stations_file'],
    DATA_CONFIG['tracks_file']
)
graph = builder.build_network(**NETWORK_CONFIG)

# 方式2：使用预设方案
from config import STANDARD_ANALYSIS
config = STANDARD_ANALYSIS
# ... 应用于分析

# 方式3：自定义组合
custom_config = {
    **STANDARD_ANALYSIS,
    'alpha_steps': 30,  # 覆盖标准值
}
"""

if __name__ == "__main__":
    # 打印当前配置
    print("当前配置信息：")
    print(f"数据路径：{DATA_CONFIG['stations_file']}")
    print(f"网络构建：{NETWORK_CONFIG}")
    print(f"故障配置：{FAILURE_CONFIG}")
    print(f"分析范围：{ANALYSIS_CONFIG}")
