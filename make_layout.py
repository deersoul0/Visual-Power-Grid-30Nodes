"""
为国产区域电网生成可视化布局坐标（Fruchterman-Reingold 力导向算法）。

原项目在 README 中提及「自研 numpy 布局算法」，但布局脚本未随仓库提交
（坐标直接硬编码在 src/case*/coordinate.py 中）。本模块将该算法补全为可复现的
源码，并据此生成 src/china_grid/coordinate.py。

运行：
    python make_layout.py

输出：
    src/china_grid/coordinate.py   # coordinate 字典 + std_width/std_height

Copyright (c) 2026
"""

import numpy as np


def fruchterman_reingold(edges, n, width=500.0, height=500.0, iterations=1000, seed=42):
    """
    Fruchterman-Reingold 力导向布局（优化版）。
    """
    # 1. 内部使用更大的虚拟画布进行力导向计算，让节点充分拉开
    w_inner = 1500.0
    h_inner = 1500.0

    rng = np.random.default_rng(seed)
    pos = rng.uniform(0, w_inner, (n, 2))

    # 理想边长 k（适当放大，让整体框架更松散）
    k = np.sqrt(w_inner * h_inner / n) * 1.2

    for it in range(iterations):
        # 冷却系数
        t = 1.0 - it / iterations
        t = max(t, 0.01)
        disp = np.zeros_like(pos)

        # (1) 节点间的斥力（全连接）
        for i in range(n):
            delta = pos[i] - pos
            d2 = np.sum(delta ** 2, axis=1)
            d2 = np.maximum(d2, 1e-4) # 防止距离为 0 导致除零错误
            d = np.sqrt(d2)

            # 采用经典 FR 公式：f = k^2 / d
            f = (k * k) / d
            # 限制最大斥力，防止初始节点重叠时产生数值爆炸
            f = np.minimum(f, k * 50.0)

            disp[i] += np.sum((delta / d[:, None]) * f[:, None], axis=0)

        # (2) 边（支路）的引力
        for u, v in edges:
            delta = pos[v - 1] - pos[u - 1]
            d = np.linalg.norm(delta) + 1e-4
            # 经典 FR 公式：f = d^2 / k
            f = (d * d) / k

            disp[u - 1] += (delta / d) * f
            disp[v - 1] -= (delta / d) * f

        # (3) 更新位置
        dlen = np.linalg.norm(disp, axis=1)
        dlen = np.maximum(dlen, 1e-4)

        # 步长限制，前期散得快，后期微调
        step = np.minimum(dlen, t * (w_inner / 10.0))
        pos = pos + disp / dlen[:, None] * step[:, None]

        # 软边界处理（防止飞得太远）
        pos = np.clip(pos, -w_inner * 0.5, w_inner * 1.5)

    # ==========================================
    # 最后：统一缩放到目标画布尺寸(500x500)，居中输出
    # ==========================================
    margin = 40.0
    min_ = pos.min(axis=0)
    max_ = pos.max(axis=0)
    span = max_ - min_
    span = np.where(span < 1e-6, 1.0, span)

    # 计算缩放比例，保持宽高比
    scale_x = (width - 2 * margin) / span[0]
    scale_y = (height - 2 * margin) / span[1]
    scale = min(scale_x, scale_y)

    # 先平移到原点，再按比例缩放
    pos = (pos - min_) * scale

    # 居中处理
    pos[:, 0] += (width - pos[:, 0].max()) / 2.0
    pos[:, 1] += (height - pos[:, 1].max()) / 2.0

    return pos


def build_coordinate_file(case):
    """根据案例生成 coordinate.py 内容。"""
    n = len(case['bus'])
    edges = [(int(case['branch'][i, 0]), int(case['branch'][i, 1]))
             for i in range(len(case['branch']))]

    # 调用优化后的布局算法
    pos = fruchterman_reingold(edges, n)

    lines = ['"""', '国产区域电网（33 节点）可视化布局坐标。', '',
             '由 make_layout.py 的 Fruchterman-Reingold 力导向算法自动生成。',
             'Copyright (c) 2026', '"""', '', 'coordinate = {']
    for i in range(n):
        x, y = pos[i]
        lines.append(f"    '{i+1}':({x:.1f},{y:.1f}),")
    lines.append('}')
    lines.append('')
    lines.append('std_width = 500')
    lines.append('std_height = 500')
    return '\n'.join(lines) + '\n'


if __name__ == '__main__':
    from china_grid import china_case
    case = china_case()
    content = build_coordinate_file(case)
    # 注意这里的路径，确保与你的项目结构匹配
    with open('src/china_grid/coordinate.py', 'w', encoding='utf-8') as f:
        f.write(content)
    print('已生成 src/china_grid/coordinate.py，母线数', len(case['bus']))