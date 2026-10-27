"""
构建一个国产化风格的区域电网案例（PyPower / MATPOWER 格式）。

说明
----
本模块用于将原项目底层的国外标准测试系统（IEEE 14/30-bus）替换为一个
**国产化风格的中部区域电网**，供 OPF / 状态估计 / 经济调度 / 可视化复用。

设计要点
--------
- 3 个电压等级：500 kV 主干网架、220 kV 地区网、110 kV 配电网；
- 33 条母线，6 台机组（火电 / 水电 / 风电 / 光伏 / 热电联产），
  覆盖「高比例新能源 + 多元电源」的国内典型结构；
- 母线 / 变电站采用中文地理命名（长江中游区域）；
- 110 kV 配网按「环网 + 电容补偿」设计，保证电压水平与 OPF 收敛；
- 线路与变压器用等值阻抗建模（变压器不设非标变比，TAP=0），
  参数按国内 500/220/110 kV 典型标幺值范围取值。

注意
----
真实的省级电网完整参数属于电网企业保密数据，公开渠道无法取得。
本案例为「国产化风格」的教学/演示算例，拓扑与参数范围符合国内习惯，
但不代表任何真实电网的实际运行数据。

Copyright (c) 2026
"""

import numpy as np

# PyPower 索引（内联常用列号，避免 idx_* 版本差异）
BUS_I, BUS_TYPE, PD, QD, GS, BS, BUS_AREA, VM, VA, BASE_KV, ZONE, VMAX, VMIN = range(13)
GEN_BUS, PG, QG, QMAX, QMIN, VG, MBASE, GEN_STATUS, PMAX, PMIN = range(10)
F_BUS, T_BUS, BR_R, BR_X, BR_B, RATE_A, RATE_B, RATE_C, TAP, SHIFT, BR_STATUS, ANGMIN, ANGMAX = range(13)

# 母线类型
REF, PV_, PQ_ = 3, 2, 1

BASE_MVA = 100.0


def _bus(i, type_, pd, qd, base_kv, vm=1.0, va=0.0, bs=0.0):
    """构造一条母线记录。pd/qd 单位 MW / MVAr，bs 为并联电容（MVAr @1.0pu）。"""
    return np.array([i, type_, pd, qd, 0.0, bs, 1, vm, va, base_kv, 1, 1.10, 0.90])


def _branch(fb, tb, r, x, b, rate):
    """构造一条支路记录（线路 / 变压器等值）。"""
    return np.array([fb, tb, r, x, b, rate, rate, rate, 0.0, 0.0, 1, -360, 360])


def _gen(bus, pg, pmin, pmax, qmax, qmin, vg, c2, c1, c0, qg=0.0, mbase=BASE_MVA):
    """构造一台机组及其二次成本曲线 c2*P^2 + c1*P + c0。"""
    g = np.zeros(21)
    g[GEN_BUS] = bus
    g[PG] = pg
    g[QG] = qg
    g[QMAX] = qmax
    g[QMIN] = qmin
    g[VG] = vg
    g[MBASE] = mbase
    g[GEN_STATUS] = 1
    g[PMAX] = pmax
    g[PMIN] = pmin
    gc = np.array([2, 0, 0, 3, c2, c1, c0])
    return g, gc


# ---------------------------------------------------------------------------
# 母线命名（1-based，用于界面与台账显示）
# ---------------------------------------------------------------------------
bus_names = {
    1: '武汉北 500kV变', 2: '三峡左岸 500kV变', 3: '长沙西 500kV变',
    4: '郑州东 500kV变', 5: '南昌北 500kV变', 6: '合肥南 500kV变',
    7: '武汉江南 220kV', 8: '宜昌东 220kV', 9: '长沙东 220kV',
    10: '郑州南 220kV', 11: '南昌西 220kV', 12: '合肥东 220kV',
    13: '荆州 220kV', 14: '岳阳 220kV', 15: '湘潭 220kV',
    16: '洛阳 220kV', 17: '新乡 220kV', 18: '九江 220kV',
    19: '武汉阳逻 110kV', 20: '荆州沙市 110kV', 21: '岳阳临湘 110kV',
    22: '湘潭雨湖 110kV', 23: '洛阳洛龙 110kV', 24: '新乡牧野 110kV',
    25: '九江浔阳 110kV', 26: '武汉光谷 110kV', 27: '宜昌坝区 110kV',
    28: '长沙望城 110kV', 29: '郑州高新 110kV', 30: '南昌红谷滩 110kV',
    31: '合肥滨湖 110kV', 32: '合肥肥西 110kV', 33: '合肥长丰 110kV',
}

# 机组命名与类型
gen_names = {
    1: '武汉北 火电', 2: '三峡 水电', 4: '郑州东 火电',
    8: '宜昌东 风电', 15: '湘潭 光伏', 19: '阳逻 热电联产',
}
gen_types = {
    1: '火电', 2: '水电', 4: '火电', 8: '风电', 15: '光伏', 19: '热电',
}


def china_case(target_load_mw=1100.0):
    """
    返回一个国产化区域电网案例 dict（PyPower 格式）。

    target_load_mw: 有功负荷总量目标（MW），用于把各母线的相对负荷权重归一化。
    """
    # --- 母线 --------------------------------------------------------------
    # (编号, 类型, 有功负荷权重 MW, 无功负荷权重 MVAr)
    bus_spec = [
        # 500 kV 主干网架
        (1, REF, 0.0, 0.0),   # 武汉北（平衡节点）
        (2, PV_, 0.0, 0.0),   # 三峡左岸（水电）
        (3, PQ_, 120.0, 40.0),
        (4, PV_, 0.0, 0.0),   # 郑州东（火电）
        (5, PQ_, 110.0, 36.0),
        (6, PQ_, 100.0, 33.0),
        # 220 kV 地区网
        (7, PQ_, 80.0, 26.0),
        (8, PV_, 0.0, 0.0),   # 宜昌东（风电）
        (9, PQ_, 85.0, 28.0),
        (10, PQ_, 80.0, 26.0),
        (11, PQ_, 70.0, 23.0),
        (12, PQ_, 65.0, 21.0),
        (13, PQ_, 55.0, 18.0),
        (14, PQ_, 50.0, 16.0),
        (15, PV_, 0.0, 0.0),  # 湘潭（光伏）
        (16, PQ_, 60.0, 20.0),
        (17, PQ_, 45.0, 15.0),
        (18, PQ_, 55.0, 18.0),
        # 110 kV 配电网
        (19, PV_, 0.0, 0.0),  # 阳逻（热电联产）
        (20, PQ_, 25.0, 8.0),
        (21, PQ_, 30.0, 10.0),
        (22, PQ_, 35.0, 12.0),
        (23, PQ_, 30.0, 10.0),
        (24, PQ_, 35.0, 12.0),
        (25, PQ_, 30.0, 10.0),
        (26, PQ_, 25.0, 8.0),
        (27, PQ_, 30.0, 10.0),
        (28, PQ_, 35.0, 12.0),
        (29, PQ_, 25.0, 8.0),
        (30, PQ_, 25.0, 8.0),
        (31, PQ_, 30.0, 10.0),
        (32, PQ_, 30.0, 10.0),
        (33, PQ_, 35.0, 12.0),
    ]

    # 电压等级
    kv_of = {}
    for i in range(1, 7):
        kv_of[i] = 500.0
    for i in range(7, 19):
        kv_of[i] = 220.0
    for i in range(19, 34):
        kv_of[i] = 110.0

    # 归一化有功负荷到目标总量，无功按功率因数 ~0.95 折算
    pd_raw = np.array([s[2] for s in bus_spec], dtype=float)
    scale = target_load_mw / pd_raw.sum()
    pd_vec = pd_raw * scale
    qd_vec = pd_vec * 0.329

    buses = []
    for s, pd_v, qd_v in zip(bus_spec, pd_vec, qd_vec):
        # 110 kV 母线加并联电容补偿（3 MVAr），保障末端电压
        bs = 0.04 if (s[1] == PQ_ and kv_of[s[0]] == 110.0) else 0.0
        buses.append(_bus(s[0], s[1], pd_v, qd_v, kv_of[s[0]], bs=bs))

    # --- 支路 --------------------------------------------------------------
    branches = []
    def L500(a, b):
        branches.append(_branch(a, b, 0.006, 0.10, 0.00, 12.0))
    def T500(a, b):  # 500/220 kV 变压器
        branches.append(_branch(a, b, 0.004, 0.12, 0.00, 8.0))
    def L220(a, b):
        branches.append(_branch(a, b, 0.020, 0.18, 0.00, 6.0))
    def T220(a, b):  # 220/110 kV 变压器
        branches.append(_branch(a, b, 0.006, 0.14, 0.00, 3.0))
    def L110(a, b):
        branches.append(_branch(a, b, 0.050, 0.20, 0.00, 2.0))

    # 500 kV 主干环网 + 跨区联络
    L500(1, 2); L500(2, 3); L500(3, 4); L500(4, 5); L500(5, 6); L500(6, 1)
    L500(2, 5); L500(3, 6)

    # 500 / 220 kV 主变
    T500(1, 7); T500(2, 8); T500(3, 9); T500(4, 10); T500(5, 11); T500(6, 12)

    # 220 kV 核心环网
    L220(7, 8); L220(8, 9); L220(9, 10); L220(10, 11); L220(11, 12); L220(12, 7)

    # 220 kV 城市变电站（每个接两条 220 kV 线路，保持环网）
    L220(7, 13); L220(13, 8)
    L220(7, 14); L220(14, 9)
    L220(9, 15); L220(15, 14)
    L220(10, 16); L220(16, 11)
    L220(10, 17); L220(17, 16)
    L220(11, 18); L220(18, 12)

    # 220 / 110 kV 主变（12 台）
    T220(13, 20); T220(14, 21); T220(15, 22); T220(16, 23); T220(17, 24); T220(18, 25)
    T220(7, 26); T220(8, 27); T220(9, 28); T220(10, 29); T220(11, 30); T220(12, 31)
    T220(11, 32)  # 环 E 第二路电源，避免单台主变馈入导致的末端电压跌落

    # 110 kV 环网（每个母线至少两条进线，避免末端电压跌落）
    L110(19, 20); L110(20, 21); L110(21, 19)           # 环 A
    L110(22, 23); L110(23, 24); L110(24, 22)           # 环 B
    L110(25, 26); L110(26, 27); L110(27, 25)           # 环 C
    L110(28, 29); L110(29, 30); L110(30, 31); L110(31, 28)  # 环 D
    L110(31, 32); L110(32, 33); L110(33, 31)           # 环 E
    L110(19, 22); L110(24, 25); L110(27, 28)           # 环间联络

    branch = np.array(branches)

    # --- 机组 --------------------------------------------------------------
    gens, gencost = [], []
    for g, gc in [
        _gen(1, 350, 100, 500, 300, -100, 1.02, 0.02, 30, 120),
        _gen(2, 500, 100, 600, 400, -150, 1.02, 0.01, 12, 60),
        _gen(4, 250, 80, 350, 200, -100, 1.01, 0.03, 35, 90),
        _gen(8, 120, 0, 200, 100, -100, 1.02, 0.001, 8, 25),
        _gen(15, 60, 0, 150, 80, -80, 1.02, 0.001, 5, 15),
        _gen(19, 60, 20, 100, 50, -30, 1.01, 0.05, 45, 50),
    ]:
        gens.append(g)
        gencost.append(gc)

    case = {
        'version': '2',
        'baseMVA': BASE_MVA,
        'bus': np.array(buses),
        'gen': np.array(gens),
        'branch': np.array(branch),
        'areas': np.array([[1, 1]]),
        'gencost': np.array(gencost),
    }
    return case


if __name__ == '__main__':
    from pypower.api import ppoption, runopf
    case = china_case()
    print('母线数:', len(case['bus']), ' 支路数:', len(case['branch']), ' 机组数:', len(case['gen']))
    print('有功负荷总量(MW):', round(case['bus'][:, PD].sum(), 1))
    print('装机容量(MW):', round(case['gen'][:, PMAX].sum(), 1))

    opt = ppoption()
    opt['VERBOSE'] = 0
    opt['OUT_ALL'] = 0
    result = runopf(case, opt)
    print('OPF 收敛:', result['success'])
    if result['success']:
        print('目标函数(成本):', round(result['f'], 2))
        print('机组出力(MW):', np.round(result['gen'][:, PG], 1).tolist())
        flows = np.abs(result['branch'][:, 13])  # PF
        rates = case['branch'][:, RATE_A]
        loading = flows / (rates * BASE_MVA) * 100
        print('支路负载率(%): min=%.1f max=%.1f' % (loading.min(), loading.max()))
        print('电压范围: %.3f ~ %.3f' % (result['bus'][:, VM].min(), result['bus'][:, VM].max()))
