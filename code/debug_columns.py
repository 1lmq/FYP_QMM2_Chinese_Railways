"""
调试脚本：检查population_df的列
"""

import pandas as pd

# 读取人口数据文件
population_file = r"../data/ChinaCities_Swerts.csv"
df = pd.read_csv(population_file)

print("【CSV列名分析】")
print(f"列名列表：{df.columns.tolist()}")
print(f"列名数据类型：{[type(c).__name__ for c in df.columns]}")
print()

print("【逐个检查列名】")
for col in df.columns:
    is_digit = col.isdigit() if isinstance(col, str) else False
    print(f"列名: '{col}' (类型:{type(col).__name__}) -> isdigit(): {is_digit}")

print()
print("【年份列检测】")
available_years = [col for col in df.columns if col.isdigit()]
print(f"检测到的年份列：{available_years}")
