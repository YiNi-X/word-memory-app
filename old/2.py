import matplotlib.pyplot as plt
import numpy as np

# 设置中文字体
plt.rcParams['font.sans-serif'] = ['SimHei', 'DejaVu Sans']
plt.rcParams['axes.unicode_minus'] = False

# 数据准备
# 左图：宏观水面垃圾
inner_labels = ['可回收垃圾\n46%', '有害垃圾\n29%', '有机垃圾\n25%']
inner_sizes = [46, 29, 25]
outer_labels = ['塑料类\n17%', '纸质类\n18%', '玻璃类\n6%', '金属类\n5%',
                '化工排放\n16%', '废弃电子\n7%', '过期药品\n6%',
                '食物残渣\n25%']
outer_sizes = [17, 18, 6, 5, 16, 7, 6, 25]

# 右图：微观水质监测
water_labels = ['微塑料\n50%', '重金属\n25%', '理化指标\n15%', '其他\n10%']
water_sizes = [50, 25, 15, 10]

# 配色
cmap_inner = ['#004c6d', '#0077b6', '#48cae4']
colors_recyclable = ['#023e8a', '#0077b6', '#0096c7', '#48cae4']
colors_hazardous = ['#00b4d8', '#48cae4', '#90e0ef']
colors_organic = ['#caf0f8']
outer_colors = colors_recyclable + colors_hazardous + colors_organic
water_colors_blue = ['#003049', '#00609C', '#59C3E1', '#A8D1E7']

# 绘图
fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(16, 8))

# --- 左图：调整内外比例并居中文字 ---
radius_outer = 1.0
width_outer = 0.45
radius_inner = radius_outer - width_outer # 0.55

# 计算文字中心位置
labeldistance_outer = radius_inner + width_outer / 2
labeldistance_inner = radius_inner / 2

# 外圈绘制
wedges1, texts1 = ax1.pie(outer_sizes, labels=outer_labels, radius=radius_outer, colors=outer_colors,
                          wedgeprops=dict(width=width_outer, edgecolor='w'), startangle=90,
                          labeldistance=labeldistance_outer,
                          textprops={'fontsize': 9, 'color': 'white', 'fontweight': 'bold'})

# 内圈绘制
wedges2, texts2 = ax1.pie(inner_sizes, labels=inner_labels, radius=radius_inner, colors=cmap_inner,
                          wedgeprops=dict(width=radius_inner, edgecolor='w'), startangle=90,
                          labeldistance=labeldistance_inner,
                          textprops={'fontsize': 11, 'color': 'white', 'fontweight': 'bold'})

# 设置标题在底部
ax1.set_title("水面宏观垃圾成分分析", fontsize=16, y=-0.05)

# --- 右图：实心饼图文字居中 ---
radius_water = 1.0
labeldistance_water = radius_water / 2

wedges3, texts3 = ax2.pie(water_sizes, labels=water_labels, radius=radius_water, colors=water_colors_blue,
                          wedgeprops=dict(width=radius_water, edgecolor='w'), startangle=140,
                          labeldistance=labeldistance_water,
                          textprops={'fontsize': 12, 'color': 'white', 'fontweight': 'bold'})

# 设置标题在底部
ax2.set_title("水体微观污染监测要素占比", fontsize=16, y=-0.05)

plt.tight_layout()
plt.savefig('water_pollution_analysis_bottom_titles.png', dpi=300)