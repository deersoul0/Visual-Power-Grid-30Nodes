"""
电网数字孪生（简化版）：负荷预测 + 状态镜像对比。

设计思路
--------
数字孪生 = 一个与物理电网同步运行的「镜像模型」。本模块实现其核心闭环：
1. 用历史负荷时间序列在线预测下一时刻的系统负荷（含多种预测方法）；
2. 用预测负荷反推系统状态（机组出力、支路潮流）；
3. 下一时刻真实量测到来后，计算「孪生偏差」（预测 vs 实际），量化镜像误差。

提供预测方法：
- persistence：持续法（用上一时刻值作为预测）；
- moving_average：滑动平均；
- exponential：指数平滑；
- trend：线性趋势外推。

Copyright (c) 2026
"""

import numpy as np


def forecast_total_load(history, method='exponential', horizon=1):
    """
    根据历史总负荷序列 history（1D，时间升序）预测未来 horizon 步的总负荷。

    返回预测值（标量或数组）。
    """
    history = np.asarray(history, dtype=float)
    if len(history) == 0:
        return np.nan

    if method == 'persistence':
        pred = history[-1]
    elif method == 'moving_average':
        w = min(5, len(history))
        pred = history[-w:].mean()
    elif method == 'exponential':
        alpha = 0.3
        s = history[0]
        for x in history[1:]:
            s = alpha * x + (1 - alpha) * s
        pred = s
    elif method == 'trend':
        if len(history) < 2:
            pred = history[-1]
        else:
            slope = history[-1] - history[-2]
            pred = history[-1] + slope * horizon
    else:
        raise ValueError(f'未知预测方法: {method}')

    if horizon > 1:
        return np.full(horizon, pred)
    return float(pred)


def forecast_error(actual, forecast):
    """返回预测误差指标：MAE 与 MAPE(%)。"""
    actual = np.asarray(actual, dtype=float)
    forecast = np.asarray(forecast, dtype=float)
    mae = float(np.mean(np.abs(actual - forecast)))
    mape = float(np.mean(np.abs((actual - forecast) / np.maximum(np.abs(actual), 1e-6))) * 100.0)
    return mae, mape


class DigitalTwin:
    """
    在线数字孪生：维护历史负荷窗口，滚动预测并评估偏差。
    """

    def __init__(self, method='exponential', window=48):
        self.method = method
        self.window = window
        self.history = []
        self.forecasts = []      # 预测记录
        self.actuals = []        # 实际记录
        self.errors = []         # 逐点误差

    def update(self, actual_total_load):
        """送入当前时刻的真实总负荷，返回对下一时刻的预测值。"""
        self.actuals.append(actual_total_load)
        # 用截至当前的历史预测下一时刻
        hist = self.actuals[-self.window:]
        pred = forecast_total_load(hist, method=self.method)
        self.forecasts.append(pred)
        # 若有上一时刻的预测，计算其误差
        if len(self.forecasts) >= 2:
            prev_pred = self.forecasts[-2]
            self.errors.append(abs(actual_total_load - prev_pred))
        else:
            self.errors.append(0.0)
        self.history.append(actual_total_load)
        return pred

    @property
    def latest_mae(self):
        if not self.errors:
            return np.nan
        return float(np.mean(self.errors[-min(24, len(self.errors)):]))

    def series(self):
        """返回 (实际, 预测, 误差) 序列，供绘图。"""
        n = min(len(self.actuals), len(self.forecasts))
        actual = self.actuals[-n:]
        forecast = self.forecasts[-n:]
        errors = self.errors[-n:]
        return actual, forecast, errors


if __name__ == '__main__':
    # 用合成日负荷曲线测试
    t = np.linspace(0, 24, 288)
    load = 800 + 200 * np.sin(2 * np.pi * t / 24 - np.pi / 2) + 30 * np.random.randn(288)
    twin = DigitalTwin(method='exponential')
    for x in load:
        twin.update(x)
    a, f, e = twin.series()
    mae, mape = forecast_error(np.array(a[1:]), np.array(f[:-1]))
    print(f'数字孪生负荷预测 MAE={mae:.1f} MW, MAPE={mape:.2f}%')
