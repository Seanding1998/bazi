#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
排盘引擎单元测试 — test_paipan.py

运行：python test_paipan.py
（无 pytest 依赖：内置 runner 顺序执行全部 test_* 函数，全绿退出码 0）

测试锚点来源：
  - 1990-06-15 北京：庚午 壬午 辛亥（14时=乙未，23时=庚子）——sxtwl 实测
  - 2026 立春 2026-02-04 04:01:51（权威天文数据核对）
  - 1997 旧 eval 命例（丁丑 癸丑 丙寅 甲午，乾造逆行首运壬子）→ 对应 1998-01-19
  - 空亡/纳音/十神/长生为标准表逐项校验
"""

import json
import sys
import os
from datetime import datetime

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import paipan as pp


def build(birth, gender, **kw):
    dt, missing = pp.parse_birth(birth)
    return pp.build_paipan(dt, pp.norm_gender(gender), **kw)


# ── 已知命例回归 ──────────────────────────────────────────────

def test_known_chart_1990():
    """1990-06-15 14:30 北京 → 庚午 壬午 辛亥 乙未"""
    d = build("1990-06-15 14:30", "男")
    sz = d["sizhu"]
    assert sz["year"]["pillar"] == "庚午", sz["year"]["pillar"]
    assert sz["month"]["pillar"] == "壬午"
    assert sz["day"]["pillar"] == "辛亥"
    assert sz["hour"]["pillar"] == "乙未"
    assert d["day_master"]["stem"] == "辛" and d["day_master"]["yinyang"] == "阴"
    # 十神：庚年干对辛日主 = 劫财；壬月干 = 伤官；乙时干 = 偏财
    assert sz["year"]["gan"]["shishen"] == "劫财"
    assert sz["month"]["gan"]["shishen"] == "伤官"
    assert sz["hour"]["gan"]["shishen"] == "偏财"
    # 藏干：午 = 丁(本气七杀? 辛火克金→丁=七杀) 己(中气偏印)
    cg = {c["stem"]: c for c in sz["month"]["zhi"]["canggan"]}
    assert list(cg) == ["丁", "己"]
    assert cg["丁"]["shishen"] == "七杀" and cg["丁"]["level"] == "本气"
    assert cg["己"]["shishen"] == "偏印" and cg["己"]["level"] == "中气"
    # 空亡：辛亥 = 甲辰旬 → 寅卯空
    assert d["kongwang"]["xun"] == "甲辰旬"
    assert d["kongwang"]["branches"] == ["寅", "卯"]
    assert sz["year"]["kongwang_branch"] is False
    # 纳音
    assert sz["year"]["nayin"] == "路旁土"
    # 长生：辛日 → 亥=沐浴，午=病（辛：子长生…午=病），未=衰
    assert sz["day"]["zhi"]["stage"] == "沐浴"
    assert sz["year"]["zhi"]["stage"] == "病"
    # 调候月份：午月 = 第5月
    assert d["jiaojie"]["month_number_for_tiaohou"] == 5


def test_late_zishi():
    """晚子时约定：日柱按当日，时干按次日日干五鼠遁（随 sxtwl）"""
    d = build("1990-06-15 23:30", "男")
    assert d["sizhu"]["day"]["pillar"] == "辛亥"
    assert d["sizhu"]["hour"]["pillar"] == "庚子"
    # 对比：次日 00:30 的时柱同为 庚子，但日柱前进一位
    d2 = build("1990-06-16 00:30", "男")
    assert d2["sizhu"]["day"]["pillar"] == "壬子"
    assert d2["sizhu"]["hour"]["pillar"] == "庚子"


def test_lichun_boundary_2026():
    """2026-02-04 立春 04:01:51 前后 → 年柱/月柱同时切换"""
    before = build("2026-02-04 03:00", "男")
    after = build("2026-02-04 05:00", "男")
    assert before["sizhu"]["year"]["pillar"] == "乙巳"
    assert before["sizhu"]["month"]["pillar"] == "己丑"
    assert after["sizhu"]["year"]["pillar"] == "丙午"
    assert after["sizhu"]["month"]["pillar"] == "庚寅"
    assert before["jiaojie"]["month_number_for_tiaohou"] == 12
    assert after["jiaojie"]["month_number_for_tiaohou"] == 1


def test_eval_case_1998():
    """旧 eval 命例：丁丑 癸丑 丙寅 甲午，乾造阴年逆行，首步大运壬子"""
    d = build("1998-01-19 12:00", "男")
    sz = d["sizhu"]
    assert sz["year"]["pillar"] == "丁丑"
    assert sz["month"]["pillar"] == "癸丑"
    assert sz["day"]["pillar"] == "丙寅"
    assert sz["hour"]["pillar"] == "甲午"
    q = d["qi_yun"]
    assert q["direction"] == "逆行"
    assert q["anchor_jie"]["name"] == "小寒"
    # 小寒 1998-01-05 21:18 → 距离约 13.61 天 → 4年6个月13天上下，起运年份 2002
    assert q["breakdown"]["years"] == 4
    assert q["breakdown"]["months"] == 6
    assert q["qi_yun_year"] == 2002
    # 首步大运：癸丑逆行 → 壬子；第二步 辛亥
    assert d["dayun"][0]["pillar"] == "壬子"
    assert d["dayun"][1]["pillar"] == "辛亥"
    assert d["dayun"][0]["gan_shishen"] == "七杀"  # 壬对丙日主：水克火、同阳→七杀
    # 大运起止：首运 start_year = 起运年
    assert d["dayun"][0]["start_year"] == 2002
    assert d["dayun"][0]["end_year"] == 2012


# ── 基础表逐项校验 ────────────────────────────────────────────

def test_shishen_full():
    """丙火日主对十天干的十神全表"""
    expect = {"甲": "偏印", "乙": "正印", "丙": "比肩", "丁": "劫财", "戊": "食神",
              "己": "伤官", "庚": "偏财", "辛": "正财", "壬": "七杀", "癸": "正官"}
    for stem, ss in expect.items():
        assert pp.shishen("丙", stem) == ss, f"丙 vs {stem}"


def test_changsheng_fire_earth_tonggong():
    """火土同宫：丙戊同长生寅，丁己同长生酉；几组关键状态"""
    assert pp.changsheng("甲", "亥") == "长生"
    assert pp.changsheng("甲", "卯") == "帝旺"
    assert pp.changsheng("甲", "未") == "墓"
    assert pp.changsheng("乙", "午") == "长生"
    assert pp.changsheng("戊", "寅") == "长生"   # 火土同宫
    assert pp.changsheng("己", "酉") == "长生"
    assert pp.changsheng("庚", "巳") == "长生"
    assert pp.changsheng("辛", "子") == "长生"
    assert pp.changsheng("壬", "申") == "长生"
    assert pp.changsheng("癸", "卯") == "长生"
    assert pp.changsheng("癸", "未") == "墓"


def test_kongwang_six_xun():
    """六旬空亡速查（SKILL 原表）"""
    expect = {"甲子": ["戌", "亥"], "甲戌": ["申", "酉"], "甲申": ["午", "未"],
              "甲午": ["辰", "巳"], "甲辰": ["寅", "卯"], "甲寅": ["子", "丑"]}
    for day, kong in expect.items():
        xun, k = pp.kongwang(day)
        assert k == kong, f"{day} → {k}"
        assert xun == day + "旬"


def test_nayin():
    assert pp.nayin("甲子") == "海中金"
    assert pp.nayin("庚午") == "路旁土"
    assert pp.nayin("丙寅") == "炉中火"
    assert pp.nayin("壬戌") == "大海水"


def test_qiyun_breakdown_math():
    """折算：3天=1年，6小时=1月，0.2小时=1天"""
    assert pp.qiyun_breakdown(9.0) == (3, 0, 0)          # 9天 → 3年
    assert pp.qiyun_breakdown(1.5) == (0, 6, 0)          # 1.5天=36h → 6个月
    assert pp.qiyun_breakdown(0.2) == (0, 0, 24)         # 4.8h → 24天
    y, m, dd = pp.qiyun_breakdown(13.613)
    assert (y, m) == (4, 6) and 12 < dd < 15


# ── 真太阳时 ─────────────────────────────────────────────────

def test_true_solar_correction():
    """1990-11-03 均时差约 +16.4 分；上海经度再 +5.9 分"""
    dt = datetime(1990, 11, 3, 12, 0, 0)
    corrected, lon_corr, eot = pp.true_solar_correct(dt, 121.47, 8.0)
    assert 15.5 < eot < 17.0, eot
    assert abs(lon_corr - 5.88) < 0.01
    delta = (corrected - dt).total_seconds() / 60.0
    assert 21.0 < delta < 23.5, delta
    # 2月中旬均时差为负
    dt2 = datetime(1990, 2, 12, 12, 0, 0)
    _, _, eot2 = pp.true_solar_correct(dt2, 120.0, 8.0)
    assert -15.0 < eot2 < -13.5, eot2


def test_true_solar_cross_midnight():
    """真太阳时把时刻拉过午夜 → 日柱随校正后日期"""
    # 兰州 103.8E：经度修正 4*(103.8-120) = -64.8 分，12月均时差约 +10 分 → 净约 -55 分
    d = build("1990-12-01 00:20", "男", longitude=103.8)
    ts = d["meta"]["true_solar"]
    assert ts["applied"] is True
    assert ts["corrected_time"].startswith("1990-11-30"), ts["corrected_time"]
    # 日柱应为 11月30日 的日柱（而不是 12-01 的）
    import sxtwl
    ref = pp.gz_name(sxtwl.fromSolar(1990, 11, 30).getDayGZ())
    assert d["sizhu"]["day"]["pillar"] == ref


# ── 神煞 ─────────────────────────────────────────────────────

def test_shensha_1990():
    """辛日主、年支午/日支亥：天乙贵人午、华盖未(日支亥起)、将星午(年支起)、
    金舆亥(辛禄酉前二位)、天德贵人亥(午月天德在亥/乾位)"""
    d = build("1990-06-15 14:30", "男")
    names = set(d["shensha"].keys())
    for expected in ("天乙贵人", "华盖", "将星", "金舆", "天德贵人"):
        assert expected in names, names
    # 天乙贵人应落在年支/月支午（辛→午寅，盘中午亥未）
    hits = d["shensha"]["天乙贵人"]
    assert any(h["branch"] == "午" and h["position"] in ("年柱", "月柱") for h in hits)
    # 华盖必须带起组信息
    hg = d["shensha"]["华盖"]
    assert any(h.get("base", "").startswith("日支") for h in hg), hg
    # 金舆与天德都应落在日支亥
    for name in ("金舆", "天德贵人"):
        assert any(h["branch"] == "亥" and h["position"] == "日柱" for h in d["shensha"][name]), name
    # 月德：午月→丙，原局天干庚壬辛乙无丙 → 不得出现
    assert "月德贵人" not in names
    # 孤辰寡宿：年支午→巳午未方局(申/辰)、日支亥→亥子丑方局(寅/戌)，原局均未见
    assert "孤辰" not in names and "寡宿" not in names


def test_shensha_expanded():
    """新增五神煞的表格级校验（合成盘面，不依赖具体日期）"""
    # 丙日主、子年支、丑月支；盘面：年支丑、日支寅、月干庚
    ss = pp.compute_shensha(
        "丙", "子", "丑",
        chart_positions={"丑": ["年柱"], "寅": ["日柱"]},
        chart_stem_positions={"庚": ["月柱"]})
    # 天德：丑月→庚(干) → 落月柱；月德：丑月→巳酉丑金局→庚 → 同落月柱
    assert ss["天德贵人"] == [{"stem": "庚", "position": "月柱"}]
    assert ss["月德贵人"] == [{"stem": "庚", "position": "月柱"}]
    # 孤辰：年支子→亥子丑方局→寅 → 落日支，带年支起组标记
    assert ss["孤辰"] == [{"branch": "寅", "position": "日柱", "base": "年支子起"}]
    # 寡宿：日支寅→寅卯辰方局→丑 → 落年支，带日支起组标记
    assert ss["寡宿"] == [{"branch": "丑", "position": "年柱", "base": "日支寅起"}]
    # 金舆：丙→未，盘面无未
    assert "金舆" not in ss
    # 天德支型月份：午月天德在亥(乾位以支代) → 盘面有亥则落支
    ss2 = pp.compute_shensha("辛", "午", "午", chart_positions={"亥": ["日柱"]})
    assert ss2["天德贵人"] == [{"branch": "亥", "position": "日柱"}]
    assert ss2["金舆"] == [{"branch": "亥", "position": "日柱"}]  # 辛→亥


def test_shensha_guchen_integration():
    """1998-01-19 乾造：年支丑→亥子丑方局→孤辰寅，落日支寅"""
    d = build("1998-01-19 12:00", "男")
    assert "孤辰" in d["shensha"]
    assert any(h["branch"] == "寅" and h["position"] == "日柱" for h in d["shensha"]["孤辰"])


# ── 流年 ─────────────────────────────────────────────────────

def test_liunian():
    d = build("1990-06-15 14:30", "男", liunian_years=[1984, 2026])
    ln = {l["year"]: l for l in d["liunian"]}
    assert ln[1984]["pillar"] == "甲子"
    assert ln[2026]["pillar"] == "丙午"
    # 丙对辛日主：火克金、异阴阳 → 正官
    assert ln[2026]["gan_shishen"] == "正官"
    # 午与时支未六合
    assert any("未" in rel for rel in ln[2026]["relations"]["合"])
    # 午非空亡、非墓库
    assert ln[2026]["kongwang_fill"] is False and ln[2026]["tomb"] is False
    # 2024 辰年测试墓库标记
    d2 = build("1990-06-15 14:30", "男", liunian_years=[2024])
    ln2 = d2["liunian"][0]
    assert ln2["pillar"] == "甲辰" and ln2["tomb"] is True


# ── 与 sxtwl 的一致性回归（抓自算回归 bug）────────────────────

def test_sxtwl_consistency_random():
    """40 个随机时刻（非节气日）：四柱必须与 sxtwl 完全一致；节气日只比日柱"""
    import random
    import sxtwl
    random.seed(42)
    checked = 0
    for _ in range(40):
        y = random.randint(1995, 2035)
        m = random.randint(1, 12)
        day = random.randint(1, 28)
        h = 10
        dt = datetime(y, m, day, h, 30)
        obj = sxtwl.fromSolar(y, m, day)
        is_term_day = obj.hasJieQi()
        d = pp.build_paipan(dt, "男")
        sz = d["sizhu"]
        # 日柱与时柱必须永远一致
        assert sz["day"]["pillar"] == pp.gz_name(obj.getDayGZ()), (dt, sz["day"]["pillar"])
        assert sz["hour"]["pillar"] == pp.gz_name(obj.getHourGZ(h)), (dt, sz["hour"]["pillar"])
        # 年柱/月柱：sxtwl 是节气"日"粒度，本引擎精确到交节时刻 → 仅非节气日比对
        if not is_term_day:
            assert sz["year"]["pillar"] == pp.gz_name(obj.getYearGZ(False)), (dt, sz["year"]["pillar"])
            assert sz["month"]["pillar"] == pp.gz_name(obj.getMonthGZ()), (dt, sz["month"]["pillar"])
            checked += 1
    assert checked >= 30


def test_json_roundtrip():
    d = build("1990-06-15 14:30", "男", longitude=121.47, liunian_years=[2026])
    text = json.dumps(d, ensure_ascii=False, indent=2)
    back = json.loads(text)
    for key in ("meta", "conventions", "day_master", "sizhu", "kongwang", "jiaojie",
                "wuxing_count", "shensha", "qi_yun", "dayun", "current_dayun", "liunian"):
        assert key in back, key
    assert len(back["dayun"]) == 10
    assert back["meta"]["true_solar"]["applied"] is True
    assert back["sizhu"]["hour"]["pillar"] == "乙未"


# ── 错误处理 ─────────────────────────────────────────────────

def test_error_paths():
    """非法输入必须显式报错而不是猜"""
    try:
        pp.norm_gender("未知")
        assert False, "norm_gender 应当抛错"
    except ValueError:
        pass
    try:
        pp.parse_birth("1990年6月15日")
        assert False, "parse_birth 应当抛错"
    except ValueError:
        pass
    # 数字别名
    assert pp.norm_gender("0") == "男" and pp.norm_gender("1") == "女"
    assert pp.norm_gender("乾造") == "男" and pp.norm_gender("female") == "女"
    # 缺时辰 → hour_missing 标记
    dt, missing = pp.parse_birth("1990-06-15")
    assert missing is True and dt.hour == 0
    d = pp.build_paipan(dt, "男", hour_missing=missing)
    assert d["meta"]["hour_missing"] is True


# ═══════════════════════════════════════════════════════════════
#  内置 runner（无 pytest 依赖）
# ═══════════════════════════════════════════════════════════════

def main():
    pp.configure_stdio()
    tests = [(n, f) for n, f in sorted(globals().items()) if n.startswith("test_") and callable(f)]
    passed, failed = 0, 0
    for name, fn in tests:
        try:
            fn()
            print(f"  ✅ {name}")
            passed += 1
        except AssertionError as e:
            print(f"  ❌ {name}: {e}")
            failed += 1
        except Exception as e:
            print(f"  💥 {name}: {type(e).__name__}: {e}")
            failed += 1
    print(f"\n结果: {passed} 通过 / {failed} 失败（共 {len(tests)} 项）")
    sys.exit(1 if failed else 0)


if __name__ == "__main__":
    main()
