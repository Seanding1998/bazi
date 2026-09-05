# Publisher Note（安全与隐私声明）

## v2.0.0 起的行为边界

1. **无网络请求**。v2.0.0 已移除 v1.x 的 yoebao.com API 排盘（该方式会把用户出生时间发送给第三方服务）。排盘完全由本地 `scripts/paipan.py`（sxtwl）完成，不发起任何网络连接。
2. **文件读写范围**。脚本只读写两类路径：
   - 用户案例目录（桌面 `YY.MM.DD-*` 目录）下的 `paipan_result.json`、步骤 md、`bazi-data.json`、`report.html`；
   - skill 自身目录下的 references 与 scripts。
3. **无遥测、无依赖安装**。除 `pip install sxtwl`（用户主动执行）外，skill 不安装任何东西、不执行任何下载。

## v1.x → v2.0.0 的 API 移除说明

`scripts/fetch_bazi.py`（v1.3 及更早）存在三项缺陷，已删除：
- `urlopen` 无 timeout、无重试、无离线兜底，可能挂起会话；
- 出生时间以 Unix 时间戳形式发送至第三方 API，存在隐私外发；
- 解析脆弱（魔法前缀字符串 + 位置参数）。

新引擎以 sxtwl 本地计算替代，并新增真太阳时校正能力（经度 + 均时差），精度高于原 API（原 API 不考虑真太阳时）。

## 依赖透明度

- `sxtwl`（PyPI）：天文历法计算库，本地运行，开源（MIT）。
- 报告生成与测试脚本仅用 Python 标准库。
