# 窑炉保温复算台深度登记

工艺班组将全窑热区的采样证据对齐，复算连续保温并签核放行或送复核。

## 功能模块

| 模块 | 使用者动作 | 入口 | 核心文件 | 测试 |
|---|---|---|---|---|
| M1 炉单采集 | 采信炉单与读数，检查冲突 | `GET /api/intake/{source}` | `app/modules/m1_intake/readings.py` | `tests/test_intake.py` |
| M2 热电偶校正 | 查看生效校准与漂移行 | `GET /api/calibration/{source}` | `app/modules/m2_calibration/service.py` | `tests/test_calibration.py` |
| M3 热区对齐 | 核对沿用窗口及采样边界 | `GET /api/alignment/{source}` | `app/modules/m3_alignment/intervals.py` | `tests/test_alignment.py` |
| M4 保温计时 | 看共同达标及连续时长 | `GET /api/soak/{source}` | `app/modules/m4_soak/service.py` | `tests/test_soak.py` |
| M5 断档复判 | 找到缺证原因及恢复点 | `GET /api/gaps/{source}` | `app/modules/m5_gaps/grouping.py` | `tests/test_gaps.py` |
| M6 炉批勾稽 | 核对计划时长与读数行账 | `GET /api/reconcile/{source}` | `app/modules/m6_reconcile/service.py` | `tests/test_reconcile.py` |
| M7 签核归档 | 按证据签核、重跑、导出 | `POST /api/runs` | `app/modules/m7_archive/signoff.py` `app/modules/m7_archive/service.py` | `tests/test_archive.py` `tests/test_bundle.py` |

## 陷阱登记

| TRAP | 现象 | 朴素实现 | 处理 | 位置 | 测试 |
|---|---|---|---|---|---|
| TRAP-06 | 华氏读数带千分位 | 直接解析失败 | 先验证千分位再折算 | `app/modules/m1_intake/readings.py` | `tests/test_intake.py::test_temperature_conversion_and_lexical_bound` |
| TRAP-07 | 南墙 N/A | 沿用上一点 | 记录断点并隔离 | `app/modules/m3_alignment/intervals.py` | `tests/test_alignment.py::test_sentinel_cuts_band` |
| TRAP-11 | UTC 回传与东八区同一时刻 | 重复保留 | 先归一再去重 | `app/modules/m1_intake/readings.py` | `tests/test_intake.py::test_offset_duplicate` |
| TRAP-13 | 北墙乱序 | 丢掉迟到点 | 保留原行与顺序告警 | `app/modules/m1_intake/readings.py` | `tests/test_intake.py::test_dirty_out_of_order_kept` |
| TRAP-14 | 窑心同秒读数冲突 | 后写覆盖 | 两行都隔离 | `app/modules/m1_intake/readings.py` | `tests/test_intake.py::test_conflicting_duplicate_quarantines_both` |
| TRAP-15 | 摄氏和华氏混用 | 单位错配 | 归一到毫摄氏度 | `app/modules/m1_intake/readings.py` | `tests/test_intake.py::test_temperature_conversion_and_lexical_bound` |
| TRAP-19 | 同一时段缺证和失温同时出现 | 只看失温 | 缺证优先，留失温证据 | `app/modules/m4_soak/service.py` | `tests/test_soak.py::test_unknown_thermal_state_counts_before_cold` |
| TRAP-23 | 配方边界相邻 | 两段合算连续 | 左闭右开且版本处切段 | `app/modules/m4_soak/service.py` | `tests/test_soak.py::test_version_break_beats_sum` |
| TRAP-25 | 试签配方与在用版并发 | 任取一版 | 记录双来源并切入缺证 | `app/modules/m4_soak/service.py` | `tests/test_soak.py::test_recipe_overlap_cannot_choose_last` |

## 对账

样例计划 2520 秒。干净样例全部达标，最长连续 1320 秒。脏样例为达标 1560 秒、失温 120 秒、缺证 840 秒，最长连续 360 秒。
