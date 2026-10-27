# 33 节点国产区域电网状态估计与安全防御可视化平台

> 基于开源项目 [Visual-Power-Grid](https://github.com/xuwkk/Visual-Power-Grid) 的二次开发

![界面演示](visualization.png)

## 项目简介

本项目在开源项目 Visual-Power-Grid 的基础上进行二次开发，构建了一个面向国内区域电网的
**交流状态估计（AC-SE）、网络安全防御与调度优化仿真可视化平台**。平台底层基于
[PyPower](https://github.com/rwl/PYPOWER) 求解最优潮流（OPF）与状态估计，并通过
Tkinter + Matplotlib 实现实时可视化。

相对原项目的核心改进，覆盖课程二次开发全部要求：

1. **丰富网络结构，扩展国产电网**：将原 IEEE 14 节点系统扩展为 **33 节点国产区域电网**
   （华东某区域，含 500 / 220 / 110 kV 三级网架，6 台机组含火 / 水 / 风 / 光 / 热电联产）；
2. **扩展功能**：新增 **经济调度优化算法仿真**（等微增率法 / PSO / GA 对比）、
   **3D 电网可视化**（`mplot3d`，按电压等级分层）、**数字孪生**（负荷滚动预测与状态镜像）；
3. **使用国内外开源数据**：接入 PyPower / MATPOWER、PJM、ENTSO-E、国家统计局、
   Open Power System Data 等国内外开源数据来源（见 `fetch_open_data.py`）；
4. **以国产数据 / 网络替换国外数据 / 网络**：用国产 33 节点区域电网替换原 IEEE 案例，
   全部界面汉化，母线 / 机组均采用中文站名命名。

## 核心亮点

1. **全界面中文化（解决 matplotlib / tkinter 中文乱码）**
   所有 UI 文本、状态标签、图例均本地化为中文，并统一采用「微软雅黑」字体，
   彻底解决 Windows 下 matplotlib / tkinter 显示中文时的方块乱码问题。

2. **33 节点国产区域电网（自研 numpy 力导向布局）**
   在无 networkx 依赖的前提下，基于 numpy 自行实现了 Fruchterman–Reingold
   力导向布局算法，生成 33 节点的分散美观布局，并结合画布自动缩放与居中。
   网架按 500 / 220 / 110 kV 三级电压分层，母线采用中文站名命名。

3. **经济调度优化算法仿真**
   实现两段式「经济调度 + 交流潮流」OPF，内置等微增率法（λ 迭代）、
   粒子群优化（PSO）与遗传算法（GA）三种调度算法，可一键对比机组出力分配与发电成本。

4. **3D 电网可视化**
   用 `mplot3d` 将网架绘制为三维立体图：X/Y 为布局坐标，Z 为电压等级，
   支路按负载率着色、母线按电压幅值着色、发电节点用星形标记。

5. **数字孪生（负荷预测 + 状态镜像）**
   每个 OPF 周期在线滚动预测系统负荷（持续法 / 滑动平均 / 指数平滑 / 趋势外推），
   实时显示预测 vs 实际曲线与近期 MAE。

6. **网络攻击模式可视化（无攻击 / 随机攻击 / FDI 攻击）**
   保留并完善原三种攻击模式，在 33 节点下均可正常触发与检测，并可开启
   **MTD**（移动目标防御）主动改变线路电抗以破坏 FDI 攻击者的电网知识。

## 主要功能

- 循环运行最优潮流（OPF），实时显示支路有功潮流（相对线路限值的百分比）；
- 稳态交流状态估计（AC-SE），输出卡方坏数据检测（BDD）残差；
- 三种攻击模式（无攻击 / 随机攻击 / FDI 攻击）及被攻击与正常量测的对比展示；
- 在 FDI 攻击下触发 MTD，主动改变线路电抗以破坏攻击者的电网知识；
- 经济调度算法对比（等微增率法 / PSO / GA），展示机组出力与发电成本；
- 3D 电网视图，展示三级电压网架与潮流 / 电压分布；
- 数字孪生负荷预测，实时对比预测与实际负荷曲线。

## 目录结构

```
.
├── visualization.py          # 主程序入口（Tkinter 界面）
├── class_se.py               # 交流状态估计（SE）与 BDD 检测
├── fdi_att.py                # FDI 攻击与 MTD 防御
├── power_sys.py              # 电力系统稳态仿真环境（OPF）
├── gen_data.py               # 案例生成与负荷数据生成
├── config_mea_idx.py         # 量测配置（RTU / FULL）
├── config_se.py              # 状态估计与 OPF 配置
├── china_grid.py             # 33 节点国产区域电网案例构建（二次开发新增）
├── dispatch.py               # 经济调度 + 两段式稳健 OPF（二次开发新增）
├── viz3d.py                  # 3D 电网可视化（二次开发新增）
├── digital_twin.py           # 数字孪生负荷预测（二次开发新增）
├── make_layout.py            # Fruchterman-Reingold 力导向布局（二次开发新增）
├── fetch_open_data.py        # 国内外开源数据接入（二次开发新增）
├── requirements.txt          # 依赖清单
└── src/
    ├── china/                # 国产 33 节点电网负荷数据
    │   └── load/
    ├── china_grid/           # 国产 33 节点电网布局坐标
    │   └── coordinate.py
    ├── case14/               # 原 IEEE 14 节点案例（坐标 + 负荷）
    └── case30/               # 30 节点国内模拟电网（坐标 + 负荷）
```

## 环境依赖

| 依赖包 | 用途 |
| --- | --- |
| `numpy` | 矩阵 / 向量运算、力导向布局、经济调度 |
| `scipy` | 状态估计、卡方 BDD 阈值、经济调度优化 |
| `pandas` | 读取 CSV 负荷数据 |
| `matplotlib` | Tkinter 内嵌曲线与 3D 可视化（含 mplot3d） |
| `pillow` | 加载界面 logo 图片 |
| `pypower` | 潮流 / OPF / 状态估计底层引擎 |
| `tkinter` | GUI（Python 自带，Linux 需另装 `python3-tk`） |

推荐 Python 3.10+（本项目开发环境为 Python 3.14，已在 3.10 与 3.14 下测试通过）。

## 如何运行

### 1. 克隆仓库

```bash
git clone https://github.com/deersoul0/Visual-Power-Grid.git
cd Visual-Power-Grid
```

### 2. 创建虚拟环境并安装依赖

```bash
# 创建并激活虚拟环境
python -m venv .venv
# Windows
.venv\Scripts\activate
# macOS / Linux
# source .venv/bin/activate

# 安装依赖
pip install -r requirements.txt
```

> 提示：Linux 用户若缺少 Tkinter，可先执行 `sudo apt install python3-tk`。

### 3. 启动可视化平台

```bash
python visualization.py
```

首次启动会自动生成 `src/china/load/` 下的 33 节点负荷数据，无需手动下载。

### 4. （可选）查看 / 接入国内外开源数据

```bash
# 打印所有用到的国内外开源项目 / 数据来源
python fetch_open_data.py

# 尝试从公开源（PJM 小时级负荷）抓取真实负荷曲线并转换为项目格式
python fetch_open_data.py --download
```

## 致谢

本项目为开源项目 [Visual-Power-Grid](https://github.com/xuwkk/Visual-Power-Grid)
的二次开发，衷心感谢原作者 **Wangkun Xu（[@xuwkk](https://github.com/xuwkk)）** 的开源工作。

底层电力系统计算（OPF / SE / BDD）封装自作者的另一开源仓库
[steady-state-power-system](https://github.com/xuwkk/steady-state-power-system)；
潮流与最优潮流求解基于 [PyPower](https://github.com/rwl/PYPOWER)
（[MATPOWER](http://www.pserc.cornell.edu/matpower/) 的 Python 移植）。

## 版权与引用

原始代码版权归原作者所有：Copyright (c) 2026 Wangkun Xu. All rights reserved.

如需学术引用，请引用原论文：

```bibtex
@article{xu2022robust,
  title={Robust moving target defence against false data injection attacks in power grids},
  author={Xu, Wangkun and Jaimoukha, Imad M and Teng, Fei},
  journal={IEEE Transactions on Information Forensics and Security},
  volume={18},
  pages={29--40},
  year={2022},
  publisher={IEEE}
}
```
