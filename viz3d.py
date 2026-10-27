"""
电网 3D 可视化。

用 Matplotlib 的 mplot3d 把国产区域电网画成三维图：
- X / Y：力导向布局的地理坐标；
- Z：电压等级（500 / 220 / 110 kV），形成「主干—地区—配网」三级立体结构；
- 支路按负载率着色，母线按电压幅值着色。

Copyright (c) 2026
"""

import numpy as np
import matplotlib
matplotlib.use('TkAgg')
import matplotlib.pyplot as plt
from matplotlib import cm, colors
from mpl_toolkits.mplot3d import Axes3D  # noqa: F401


def _bus_kv(case):
    return case['bus'][:, 9].astype(float)


def plot_3d(case, coordinate, result=None, title='国产区域电网 3D 视图'):
    """弹出一个 3D 电网图窗口。"""
    n_bus = len(case['bus'])
    n_brh = len(case['branch'])

    # 母线坐标：x, y 取布局坐标，z 取电压等级（映射到合适高度）
    kv = _bus_kv(case)
    z_bus = np.log10(kv) * 2.0  # 500->5.4, 220->4.7, 110->4.1 量级分层

    xy = np.zeros((n_bus, 2))
    for i in range(n_bus):
        xy[i] = coordinate[f'{i+1}']

    fig = plt.figure(figsize=(9, 7), facecolor='#f5f7fa')
    ax = fig.add_subplot(111, projection='3d')
    ax.set_facecolor('#f5f7fa')

    # 支路（按负载率着色）
    if result is not None:
        pf = np.abs(result['branch'][:, 13])
        rate = case['branch'][:, 5]
        ratio = np.clip(pf / np.maximum(rate, 1e-6), 0, 1.5)
        cmap = plt.get_cmap('viridis')
        for i in range(n_brh):
            f, t = int(case['branch'][i, 0]) - 1, int(case['branch'][i, 1]) - 1
            c = cmap(min(ratio[i], 1.0))
            ax.plot([xy[f, 0], xy[t, 0]], [xy[f, 1], xy[t, 1]],
                    [z_bus[f], z_bus[t]], color=c, linewidth=2.0, alpha=0.9)
    else:
        for i in range(n_brh):
            f, t = int(case['branch'][i, 0]) - 1, int(case['branch'][i, 1]) - 1
            ax.plot([xy[f, 0], xy[t, 0]], [xy[f, 1], xy[t, 1]],
                    [z_bus[f], z_bus[t]], color='#9ba8b3', linewidth=1.6, alpha=0.7)

    # 母线（按电压幅值着色，发电节点用星号标记）
    if result is not None:
        vm = result['bus'][:, 7]
    else:
        vm = np.ones(n_bus)
    vnorm = (vm - vm.min()) / (vm.max() - vm.min() + 1e-6)
    gen_buses = set(case['gen'][:, 0].astype(int))

    for i in range(n_bus):
        is_gen = (i + 1) in gen_buses
        marker = '^' if is_gen else 'o'
        size = 55 if is_gen else 35
        color = plt.get_cmap('coolwarm')(vnorm[i])
        ax.scatter(xy[i, 0], xy[i, 1], z_bus[i], c=[color], s=size,
                   marker=marker, edgecolors='#333', linewidths=0.5, depthshade=True)
        ax.text(xy[i, 0], xy[i, 1], z_bus[i] + 0.08, str(i + 1),
                fontsize=7, ha='center', color='#333')

    # 电压等级标注
    for kv_, z_ in [(500, np.log10(500) * 2), (220, np.log10(220) * 2), (110, np.log10(110) * 2)]:
        ax.text(ax.get_xlim()[0], ax.get_ylim()[1], z_, f'{kv_} kV', fontsize=9, color='#666')

    ax.set_xlabel('X')
    ax.set_ylabel('Y')
    ax.set_zlabel('电压等级 (log10·kV)')
    ax.set_title(title, fontsize=13)
    ax.set_xticks([])
    ax.set_yticks([])

    fig.tight_layout()
    plt.show(block=False)
    return fig, ax


if __name__ == '__main__':
    from china_grid import china_case
    from src.china_grid.coordinate import coordinate
    from dispatch import run_opf_robust

    case = china_case()
    result = run_opf_robust(case)
    print('OPF success', result['success'])
    plot_3d(case, coordinate, result)
    plt.pause(2)
    print('3D 图已弹出')
