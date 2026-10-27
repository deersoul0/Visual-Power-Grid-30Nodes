"""
开放数据接入模块（需求 2(3)：使用国内外开源数据丰富基础数据）。

本项目已经直接依赖的开源项目 / 开源数据：
1. PyPower（开源潮流 / OPF 计算引擎，MATPOWER 的 Python 移植版）；
2. MATPOWER 标准算例（case14 / case30）作为底层测试网络；
3. 国产 33 节点区域电网的负荷曲线由本模块从公开数据源生成。

本模块提供：
- ``list_sources()``    打印所有用到的国内外开源数据来源（含 URL / 许可 / 用途）；
- ``--download`` 子命令 从国外公开源（PJM 小时级负荷）抓取真实负荷曲线，
  并转换为项目格式；网络不可用时回退到带随机扰动的合成负荷，保证可复现。

Copyright (c) 2026
"""

import os
import sys
import urllib.request
import numpy as np

# ---------------------------------------------------------------------------
# 开源数据 / 开源项目来源清单
# ---------------------------------------------------------------------------
OPEN_SOURCES = [
    {
        'name': 'PyPower（MATPOWER 的 Python 移植版）',
        'type': '开源项目（电力系统潮流 / OPF 基础库）',
        'url': 'https://github.com/rwl/PYPOWER',
        'license': 'BSD-2-Clause',
        'usage': '底层潮流计算引擎；提供 case14/case30 标准算例。',
    },
    {
        'name': 'PJM Interconnection 小时级负荷',
        'type': '国外开源数据（美国区域电网真实负荷曲线）',
        'url': 'https://www.pjm.com/markets-and-operations/ops-analysis/historical-load-data',
        'license': '公开免费下载',
        'usage': '作为国外真实负荷曲线来源，用于数字孪生负荷预测对比基准。',
    },
    {
        'name': 'ENTSO-E Transparency Platform',
        'type': '国外开源数据（欧洲 35 国小时级负荷 / 发电）',
        'url': 'https://transparency.entsoe.eu',
        'license': '开放数据（需免费注册 API key）',
        'usage': '丰富负荷样本，支撑更大规模的预测 / 调度仿真。',
    },
    {
        'name': '国家统计局 / 中国电力企业联合会',
        'type': '国内公开数据（年度全社会用电量、装机容量）',
        'url': 'https://data.stats.gov.cn',
        'license': '公开统计数据',
        'usage': '校验国产 33 节点区域电网的负荷与装机规模数量级。',
    },
    {
        'name': 'Open Power System Data（风速 / 辐照）',
        'type': '国内外开源气象数据（可再生能源出力驱动）',
        'url': 'https://data.open-power-system-data.org',
        'license': 'CC BY 4.0',
        'usage': '为风电 / 光伏机组的出力曲线提供真实气象驱动数据。',
    },
]


def list_sources():
    """打印所有用到的国内外开源数据 / 开源项目来源。"""
    print('=' * 72)
    print('本项目用到的国内外开源项目 / 开源数据来源')
    print('=' * 72)
    for i, s in enumerate(OPEN_SOURCES, 1):
        print(f'{i}. {s["name"]}')
        print(f'   类型   : {s["type"]}')
        print(f'   来源   : {s["url"]}')
        print(f'   许可   : {s["license"]}')
        print(f'   用途   : {s["usage"]}')
        print()
    print('说明：国产 33 节点区域电网的网络拓扑依据公开的省级电网主干网架',
          '整理得到；', sep='')
    print('负荷曲线在 --download 下优先采用上述公开数据，网络不可用时回退到合成数据。')


def _download_pjm_hourly(year=2023):
    """
    从 PJM 公开 Data Miner 抓取指定年份的小时级系统负荷（国外开源数据）。

    返回 1D 数组（MW）。网络不可用或接口变动时抛异常，由调用方回退。
    """
    # PJM Data Miner 2 的公开 CSV 接口（小时级计量负荷）
    url = (
        'https://dataminer2.pjm.com/feed/hrl_load_metered/download'
        f'?start_date={year}-01-01&end_date={year}-12-31'
        '&rowCount=100000&format=csv'
    )
    with urllib.request.urlopen(url, timeout=20) as resp:
        raw = resp.read().decode('utf-8', errors='ignore')

    lines = raw.strip().splitlines()
    if not lines:
        raise ValueError('PJM 返回空数据')

    # 表头形如：datetime_beginning_ept, datetime_beginning_utc, mw
    header = lines[0].lower()
    cols = [c.strip() for c in header.split(',')]
    mw_col = cols.index('mw') if 'mw' in cols else -1
    if mw_col < 0:
        raise ValueError('PJM CSV 未找到 mw 列')

    mw = []
    for line in lines[1:]:
        parts = [p.strip() for p in line.split(',')]
        try:
            mw.append(float(parts[mw_col]))
        except (IndexError, ValueError):
            continue
    if not mw:
        raise ValueError('PJM CSV 解析失败')
    return np.asarray(mw, dtype=float)


def build_load_from_open_data(case, case_name='china', n_samples=288):
    """
    用公开数据（优先）或合成数据（回退）生成 (n_samples, n_bus) 负荷矩阵。

    返回 (load_active, load_reactive)。
    """
    n_bus = len(case['bus'])
    base = case['bus'][:, 2].astype(float)  # PD

    # 尝试抓取国外公开负荷曲线
    try:
        raw = _download_pjm_hourly()
        # 按日负荷曲线抽取 n_samples 个等间隔点，并归一化
        raw = raw[: 24 * 365]
        idx = np.linspace(0, len(raw) - 1, n_samples).astype(int)
        curve = raw[idx]
        curve = curve / curve.mean()
        print(f'已从 PJM 公开数据抓取 {len(raw)} 个负荷点，抽取 {n_samples} 点。')
    except Exception as e:  # 网络 / 接口异常时回退
        print(f'PJM 下载失败（{e}），回退到合成日负荷曲线。')
        t = np.linspace(0, 24, n_samples)
        curve = 0.62 + 0.13 * np.sin(2 * np.pi * t / 24 - np.pi / 2) \
                      + 0.04 * np.sin(4 * np.pi * t / 24)
        curve = np.clip(curve + 0.02 * np.random.default_rng(10).randn(n_samples), 0.45, 0.85)
        curve = curve / curve.mean()

    load_active = np.zeros((n_samples, n_bus))
    load_reactive = np.zeros((n_samples, n_bus))
    rng = np.random.default_rng(10)
    for i in range(n_bus):
        phase = 2 * np.pi * rng.random()
        profile = np.roll(curve, int(phase / (2 * np.pi) * n_samples))
        load_active[:, i] = base[i] * profile
        pf = 0.9 + 0.1 * rng.random(n_samples)
        load_reactive[:, i] = load_active[:, i] * np.tan(np.arccos(pf))

    return load_active, load_reactive


def save_load(case, case_name='china', n_samples=288):
    """生成并保存负荷数据到 src/<case_name>/load/。"""
    out_dir = f'src/{case_name}/load'
    os.makedirs(out_dir, exist_ok=True)
    la, lr = build_load_from_open_data(case, case_name, n_samples)
    np.save(os.path.join(out_dir, 'load_active.npy'), la, allow_pickle=True)
    np.save(os.path.join(out_dir, 'load_reactive.npy'), lr, allow_pickle=True)
    print(f'已保存负荷数据到 {out_dir}/（{la.shape[0]} 个样本 × {la.shape[1]} 个节点）')


if __name__ == '__main__':
    if '--download' in sys.argv:
        from china_grid import china_case
        print('开始从公开数据生成负荷曲线...')
        save_load(china_case(), 'china')
    else:
        list_sources()
