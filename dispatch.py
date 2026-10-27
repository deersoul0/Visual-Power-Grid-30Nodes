"""
经济调度（Economic Dispatch）与优化算法仿真模块。

背景
----
PyPower 5.x 自带的 AC OPF 求解器（PIPS）对某些网络结构数值不稳定
（可运行 /runpf 却报 "Numerically failed"）。本模块用「经济调度 + 交流潮流」
两段式方法替代，结果稳定，并且把「调度优化算法」做成显式的仿真功能。

提供三种经济调度算法，可对比：
1. 等微增率法（λ 迭代）：凸二次成本的经典精确解法；
2. 粒子群优化（PSO）；
3. 遗传算法（GA）。

接口
----
- economic_dispatch(case, method='lambda') -> ndarray  机组有功出力 PG (MW)
- run_opf_robust(case, method='lambda') -> dict        PyPower 兼容的 OPF 结果

Copyright (c) 2026
"""

import numpy as np
from scipy.optimize import minimize

# PyPower 索引（内联，避免 idx_* 版本差异）
GEN_BUS, PG, QG, QMAX, QMIN, VG, MBASE, GEN_STATUS, PMAX, PMIN = range(10)
MODEL, STARTUP, SHUTDOWN, NCOST, COST = 0, 1, 2, 3, 4


def _cost_coeffs(case):
    """返回每台机组的 (c2, c1, c0) 成本系数（P 以 MW 计）。

    兼容二次（NCOST=3）与线性（NCOST=2）成本模型。
    """
    ncost = case['gencost'][:, NCOST].astype(int)
    c2 = np.where(ncost >= 3, case['gencost'][:, COST].astype(float), 0.0)
    c1 = np.where(ncost >= 3, case['gencost'][:, COST + 1].astype(float),
                  case['gencost'][:, COST].astype(float))
    c0 = np.where(ncost >= 3, case['gencost'][:, COST + 2].astype(float),
                  case['gencost'][:, COST + 1].astype(float))
    return c2, c1, c0


def _total_cost(P, c2, c1, c0):
    """给定机组出力向量 P (MW)，返回总成本。"""
    return float(np.sum(c2 * P ** 2 + c1 * P + c0))


def _bounds_and_demand(case, loss_mw=0.0):
    """返回 (pmin, pmax, demand)。demand = 负荷 + 损耗。"""
    pmin = case['gen'][:, PMIN].astype(float)
    pmax = case['gen'][:, PMAX].astype(float)
    demand = float(case['bus'][:, 2].sum()) + loss_mw
    return pmin, pmax, demand


def economic_dispatch(case, method='lambda', loss_mw=0.0):
    """
    经济调度：在满足功率平衡与出力上下限下，最小化发电成本。

    返回机组有功出力向量 PG (MW)。
    """
    c2, c1, c0 = _cost_coeffs(case)
    pmin, pmax, demand = _bounds_and_demand(case, loss_mw)

    if method == 'lambda':
        return _dispatch_lambda(c2, c1, c0, pmin, pmax, demand)
    elif method == 'pso':
        return _dispatch_pso(c2, c1, c0, pmin, pmax, demand)
    elif method == 'ga':
        return _dispatch_ga(c2, c1, c0, pmin, pmax, demand)
    else:
        raise ValueError(f'未知调度算法: {method}')


def _dispatch_lambda(c2, c1, c0, pmin, pmax, demand):
    """
    等微增率法（λ 迭代）。对凸二次成本：
        d(cost)/dP = 2*c2*P + c1 = λ  ->  P = (λ - c1) / (2*c2)
    迭代调整 λ 直到 ΣP = demand，并做出力限幅。
    """
    n = len(c2)
    # 初始 λ 取所有机组边际成本的均值
    lam = float(np.mean(c1 + 2 * c2 * (pmin + pmax) / 2))

    for _ in range(200):
        P = np.clip((lam - c1) / (2 * c2), pmin, pmax)
        diff = demand - P.sum()
        if abs(diff) < 1e-3:
            break
        # 步长按增量成本的平均斜率自适应
        denom = np.sum(np.where((P > pmin) & (P < pmax), 1.0 / (2 * c2), 0.0))
        lam += diff / denom if denom > 0 else diff * 0.1
    return _enforce_balance(P, demand, pmin, pmax)


def _dispatch_pso(c2, c1, c0, pmin, pmax, demand, n_particles=60, n_iter=400):
    """粒子群优化经济调度。"""
    rng = np.random.default_rng(0)
    n = len(c2)

    # 初始化粒子（满足上下限，随后按比例修正到 demand）
    X = rng.uniform(pmin, pmax, (n_particles, n))
    for i in range(n_particles):
        X[i] = _project_balance(X[i], demand, pmin, pmax)

    V = np.zeros_like(X)
    pbest = X.copy()
    pbest_cost = np.array([_total_cost(x, c2, c1, c0) for x in X])
    gbest = pbest[np.argmin(pbest_cost)].copy()
    gbest_cost = pbest_cost.min()

    w, c_p, c_g = 0.6, 1.2, 1.2
    for _ in range(n_iter):
        r1, r2 = rng.random((n_particles, n)), rng.random((n_particles, n))
        V = w * V + c_p * r1 * (pbest - X) + c_g * r2 * (gbest - X)
        X = X + V
        X = np.clip(X, pmin, pmax)
        for i in range(n_particles):
            X[i] = _project_balance(X[i], demand, pmin, pmax)
        cost = np.array([_total_cost(x, c2, c1, c0) for x in X])
        improve = cost < pbest_cost
        pbest[improve] = X[improve]
        pbest_cost[improve] = cost[improve]
        if pbest_cost.min() < gbest_cost:
            gbest = pbest[np.argmin(pbest_cost)].copy()
            gbest_cost = pbest_cost.min()
    return _enforce_balance(gbest, demand, pmin, pmax)


def _dispatch_ga(c2, c1, c0, pmin, pmax, demand, pop_size=80, n_gen=500, n_elite=8):
    """遗传算法经济调度（含精英保留策略）。"""
    rng = np.random.default_rng(1)
    n = len(c2)

    pop = rng.uniform(pmin, pmax, (pop_size, n))
    for i in range(pop_size):
        pop[i] = _project_balance(pop[i], demand, pmin, pmax)

    for _ in range(n_gen):
        cost = np.array([_total_cost(x, c2, c1, c0) for x in pop])
        # 精英保留：最优个体直接进入下一代
        elite_idx = np.argsort(cost)[:n_elite]
        elite = pop[elite_idx].copy()
        # 锦标赛选择
        idx = rng.integers(0, pop_size, (pop_size, 2))
        winners = np.array([pop[i[0]] if cost[i[0]] < cost[i[1]] else pop[i[1]] for i in idx])
        # 交叉
        mask = rng.random((pop_size, n)) < 0.5
        children = np.where(mask, winners, winners[rng.permutation(pop_size)])
        # 变异
        mut = rng.random((pop_size, n)) < 0.1
        children[mut] = rng.uniform(pmin, pmax, (pop_size, n))[mut]
        children = np.clip(children, pmin, pmax)
        for i in range(pop_size):
            children[i] = _project_balance(children[i], demand, pmin, pmax)
        children[:n_elite] = elite
        pop = children
    cost = np.array([_total_cost(x, c2, c1, c0) for x in pop])
    return _enforce_balance(pop[np.argmin(cost)], demand, pmin, pmax)


def _project_balance(P, demand, pmin, pmax):
    """把出力向量按比例投影到满足 ΣP = demand 的可行域内。"""
    P = np.clip(P, pmin, pmax)
    for _ in range(50):
        gap = demand - P.sum()
        if abs(gap) < 1e-6:
            break
        if gap > 0:
            room = pmax - P
        else:
            room = P - pmin
        if room.sum() < 1e-9:
            break
        P = np.clip(P + gap * room / room.sum(), pmin, pmax)
    return P


def _enforce_balance(P, demand, pmin, pmax):
    """最终按等微增率微调，精确满足功率平衡。"""
    return _project_balance(P, demand, pmin, pmax)


def run_opf_robust(case, method='lambda'):
    """
    PyPower 兼容的「经济调度 + 交流潮流」两段式 OPF。

    返回结果字典，字段与 pypower.runopf 兼容：
        success / f / bus / branch / gen
    """
    from pypower.api import ppoption, runpf

    case = {k: (v.copy() if hasattr(v, 'copy') else v) for k, v in case.items()}
    c2, c1, c0 = _cost_coeffs(case)
    pmin, pmax, _ = _bounds_and_demand(case)

    # 迭代补偿网损：调度 -> 潮流 -> 更新网损 -> 重新调度
    loss_mw = 0.0
    pg = None
    for _ in range(3):
        pg = economic_dispatch(case, method=method, loss_mw=loss_mw)
        case['gen'][:, PG] = pg
        result, success = runpf(case, ppoption(VERBOSE=0, OUT_ALL=0))
        if not success:
            break
        loss_mw = float(result['gen'][:, PG].sum() - result['bus'][:, 2].sum())

    if not success:
        return {'success': False, 'f': np.nan, 'bus': None, 'branch': None, 'gen': None}

    result['success'] = True
    result['f'] = _total_cost(pg, c2, c1, c0)
    return result


if __name__ == '__main__':
    from china_grid import china_case
    case = china_case()

    print('=== 经济调度对比（不计网损） ===')
    c2, c1, c0 = _cost_coeffs(case)
    pmin, pmax, demand = _bounds_and_demand(case)
    for method in ('lambda', 'pso', 'ga'):
        pg = economic_dispatch(case, method=method)
        print(f'{method:>6}: PG={np.round(pg, 1).tolist()}  成本={_total_cost(pg, c2, c1, c0):.2f}')

    print('\n=== 两段式 OPF ===')
    r = run_opf_robust(case)
    print('success', r['success'], ' 成本', round(r['f'], 2))
    if r['success']:
        print('机组出力(MW):', np.round(r['gen'][:, PG], 1).tolist())
        print('电压范围: %.3f ~ %.3f' % (r['bus'][:, 7].min(), r['bus'][:, 7].max()))
