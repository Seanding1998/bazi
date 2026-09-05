#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
八字排盘引擎 — bazi-analysis v2.0 单一事实源

功能：
  - 真太阳时校正（经度平太阳时修正 + 均时差 Spencer 公式）
  - 四柱排盘：年柱以立春交节时刻分界、月柱以节（立春/惊蛰/…/小寒）交节时刻分界，精确到秒
  - 十神（天干 + 地支藏干）、藏干（本气/中气/余气）、空亡（日柱旬空）、纳音
  - 十二长生（与 references/地支互动关系与十二长生.md 的火土同宫表逐字一致）
  - 核心神煞 16 种（天乙贵人/禄神/羊刃/文昌/金舆/桃花/驿马/华盖/将星/天医/红鸾/天喜/天德贵人/月德贵人/孤辰/寡宿）
  - 起运折算（3天=1年，1天=4个月，1时辰=10天）、十步大运、当前大运
  - 流年干支（立春分界）及流年/大运与原局的六冲六合标记
  - 输出 JSON（唯一事实源），供 SKILL.md 十步流程与 generate_report.py 消费

用法：
  python paipan.py --birth "1990-06-15 14:30" --gender 男 \
      [--longitude 121.47] [--tz 8] [--liunian 2024,2025,2026] [-o paipan_result.json]

  --birth     出生时间 "YYYY-MM-DD HH:MM[:SS]"（北京时间；缺省 00:00 时 meta.hour_missing=true）
  --gender    男/女/乾造/坤造/male/female/0/1
  --longitude 出生地的东经度数（可选；提供时启用真太阳时校正）
  --tz        时区（默认 8 = 东八区）
  --liunian   需要排流年的公历年份，逗号分隔（可选）
  -o          JSON 输出路径（可选；不给则 JSON 打到 stdout）

约定（写入输出 JSON 的 conventions 字段，SKILL.md 铁律 3 禁止手推这些结果）：
  - 年柱与流年以立春交节时刻分界；月柱以节交节时刻分界，月干按"最近一次立春"锚定的年干五虎遁
  - 晚子时（23:00-24:00）：日柱按当日，时柱天干按次日日干五鼠遁（随 sxtwl 行为）
  - 十二长生采用火土同宫（丙戊同宫、丁己同宫）
  - 起运年龄按周岁折算，起运年份 = 出生年 + 折算年数
  - 羊刃只取阳干（阴干不置刃，主流排盘口径）

依赖：sxtwl（必须，`pip install sxtwl`）。为保节气精度不提供纯 Python 回退。
"""

import sys
import json
import argparse
import math
from datetime import datetime, timedelta

try:
    import sxtwl
except ImportError:
    sys.stderr.write(
        "排盘失败：缺少依赖 sxtwl。请先执行 `pip install sxtwl` 后重试。\n"
        "为保住节气/起运精度，本脚本不提供无 sxtwl 的降级模式；"
        "若无法安装，请向用户直接索要排盘结果（四柱、起运、大运），禁止手推。\n"
    )
    sys.exit(2)

# ═══════════════════════════════════════════════════════════════
#  基础常量表
# ═══════════════════════════════════════════════════════════════

TIANGAN = ["甲", "乙", "丙", "丁", "戊", "己", "庚", "辛", "壬", "癸"]
DIZHI = ["子", "丑", "寅", "卯", "辰", "巳", "午", "未", "申", "酉", "戌", "亥"]

GAN_WUXING = {"甲": "木", "乙": "木", "丙": "火", "丁": "火", "戊": "土",
              "己": "土", "庚": "金", "辛": "金", "壬": "水", "癸": "水"}
ZHI_WUXING = {"子": "水", "丑": "土", "寅": "木", "卯": "木", "辰": "土", "巳": "火",
              "午": "火", "未": "土", "申": "金", "酉": "金", "戌": "土", "亥": "水"}
GAN_YINYANG = {g: ("阳" if i % 2 == 0 else "阴") for i, g in enumerate(TIANGAN)}
ZHI_YINYANG = {z: ("阳" if i % 2 == 0 else "阴") for i, z in enumerate(DIZHI)}

# 地支藏干：[本气, 中气, 余气...]（子卯酉单支单干）
CANGGAN = {
    "子": ["癸"], "丑": ["己", "癸", "辛"], "寅": ["甲", "丙", "戊"], "卯": ["乙"],
    "辰": ["戊", "乙", "癸"], "巳": ["丙", "庚", "戊"], "午": ["丁", "己"],
    "未": ["己", "丁", "乙"], "申": ["庚", "壬", "戊"], "酉": ["辛"],
    "戌": ["戊", "辛", "丁"], "亥": ["壬", "甲"],
}

SHENG = {"木": "火", "火": "土", "土": "金", "金": "水", "水": "木"}
KE = {"木": "土", "土": "水", "水": "火", "火": "金", "金": "木"}

# 五虎遁：年干 → 寅月天干（月干按最近一次立春锚定的年干推）
WUHU = {"甲": "丙", "己": "丙", "乙": "戊", "庚": "戊", "丙": "庚",
        "辛": "庚", "丁": "壬", "壬": "壬", "戊": "甲", "癸": "甲"}

# 纳音（六十甲子，两柱一组共 30 组）
NAYIN = ["海中金", "炉中火", "大林木", "路旁土", "剑锋金", "山头火", "涧下水",
         "城头土", "白蜡金", "杨柳木", "泉中水", "屋上土", "霹雳火", "松柏木",
         "长流水", "沙中金", "山下火", "平地木", "壁上土", "金箔金", "覆灯火",
         "天河水", "大驿土", "钗钏金", "桑柘木", "大溪水", "沙中土", "天上火",
         "石榴木", "大海水"]

# 十二长生（火土同宫：丙戊同宫、丁己同宫）
# 列序：长生 沐浴 冠带 临官 帝旺 衰 病 死 墓 绝 胎 养
CHANGSHENG_TABLE = {
    "甲": ["亥", "子", "丑", "寅", "卯", "辰", "巳", "午", "未", "申", "酉", "戌"],
    "乙": ["午", "巳", "辰", "卯", "寅", "丑", "子", "亥", "戌", "酉", "申", "未"],
    "丙": ["寅", "卯", "辰", "巳", "午", "未", "申", "酉", "戌", "亥", "子", "丑"],
    "戊": ["寅", "卯", "辰", "巳", "午", "未", "申", "酉", "戌", "亥", "子", "丑"],
    "丁": ["酉", "申", "未", "午", "巳", "辰", "卯", "寅", "丑", "子", "亥", "戌"],
    "己": ["酉", "申", "未", "午", "巳", "辰", "卯", "寅", "丑", "子", "亥", "戌"],
    "庚": ["巳", "午", "未", "申", "酉", "戌", "亥", "子", "丑", "寅", "卯", "辰"],
    "辛": ["子", "亥", "戌", "酉", "申", "未", "午", "巳", "辰", "卯", "寅", "丑"],
    "壬": ["申", "酉", "戌", "亥", "子", "丑", "寅", "卯", "辰", "巳", "午", "未"],
    "癸": ["卯", "寅", "丑", "子", "亥", "戌", "酉", "申", "未", "午", "巳", "辰"],
}
STAGE_NAMES = ["长生", "沐浴", "冠带", "临官", "帝旺", "衰", "病", "死", "墓", "绝", "胎", "养"]

# 节气：sxtwl jqIndex → 名称（0=冬至起）。单数序位为"节"，双数为"气"。
JIEQI_NAMES = ["冬至", "小寒", "大寒", "立春", "雨水", "惊蛰", "春分", "清明", "谷雨",
               "立夏", "小满", "芒种", "夏至", "小暑", "大暑", "立秋", "处暑", "白露",
               "秋分", "寒露", "霜降", "立冬", "小雪", "大雪"]
JIE_INDICES = {1, 3, 5, 7, 9, 11, 13, 15, 17, 19, 21, 23}
JIE_TO_BRANCH = {3: "寅", 5: "卯", 7: "辰", 9: "巳", 11: "午", 13: "未",
                 15: "申", 17: "酉", 19: "戌", 21: "亥", 23: "子", 1: "丑"}

# 地支关系（与 references/地支互动关系与十二长生.md 一致，只做客观标记）
LIUCHONG = [("子", "午"), ("丑", "未"), ("寅", "申"), ("卯", "酉"), ("辰", "戌"), ("巳", "亥")]
LIUHE = [("子", "丑"), ("寅", "亥"), ("卯", "戌"), ("辰", "酉"), ("巳", "申"), ("午", "未")]

# 神煞表
SHENSHA_TIANYI = {"甲": ["丑", "未"], "戊": ["丑", "未"], "庚": ["丑", "未"],
                  "乙": ["子", "申"], "己": ["子", "申"],
                  "丙": ["亥", "酉"], "丁": ["亥", "酉"],
                  "壬": ["巳", "卯"], "癸": ["巳", "卯"], "辛": ["午", "寅"]}
SHENSHA_LUSHEN = {"甲": "寅", "乙": "卯", "丙": "巳", "丁": "午", "戊": "巳",
                  "己": "午", "庚": "申", "辛": "酉", "壬": "亥", "癸": "子"}
SHENSHA_YANGREN = {"甲": "卯", "丙": "午", "戊": "午", "庚": "酉", "壬": "子"}
SHENSHA_WENCHANG = {"甲": "巳", "乙": "午", "丙": "申", "丁": "酉", "戊": "申",
                    "己": "酉", "庚": "亥", "辛": "子", "壬": "寅", "癸": "卯"}
# 三合局系列神煞：基组 → 支
SHENSHA_SANHE = {
    "桃花": {"申子辰": "酉", "寅午戌": "卯", "巳酉丑": "午", "亥卯未": "子"},
    "驿马": {"申子辰": "寅", "寅午戌": "申", "巳酉丑": "亥", "亥卯未": "巳"},
    "华盖": {"申子辰": "辰", "寅午戌": "戌", "巳酉丑": "丑", "亥卯未": "未"},
    "将星": {"申子辰": "子", "寅午戌": "午", "巳酉丑": "酉", "亥卯未": "卯"},
}
SANHE_GROUP_OF = {}
for _grp, _zhis in {"申子辰": ["申", "子", "辰"], "寅午戌": ["寅", "午", "戌"],
                    "巳酉丑": ["巳", "酉", "丑"], "亥卯未": ["亥", "卯", "未"]}.items():
    for _z in _zhis:
        SANHE_GROUP_OF[_z] = _grp
# 红鸾（年支起卯逆行）、天喜（红鸾对冲）
HONGTUAN = {"子": "卯", "丑": "寅", "寅": "丑", "卯": "子", "辰": "亥", "巳": "戌",
            "午": "酉", "未": "申", "申": "未", "酉": "午", "戌": "巳", "亥": "辰"}
# 金舆：禄前二位（日干 → 支）
SHENSHA_JINYU = {"甲": "辰", "乙": "巳", "丙": "未", "丁": "申", "戊": "未",
                 "己": "申", "庚": "戌", "辛": "亥", "壬": "丑", "癸": "寅"}
# 天德贵人：月支 → 干/支（口诀"正丁二坤三壬四辛，五乾六甲七癸八艮，九丙十乙，子巽丑庚"；坤申/乾亥/艮寅/巽巳以支代）
TIANDE = {"寅": ("stem", "丁"), "卯": ("branch", "申"), "辰": ("stem", "壬"),
          "巳": ("stem", "辛"), "午": ("branch", "亥"), "未": ("stem", "甲"),
          "申": ("stem", "癸"), "酉": ("branch", "寅"), "戌": ("stem", "丙"),
          "亥": ("stem", "乙"), "子": ("branch", "巳"), "丑": ("stem", "庚")}
# 月德贵人：月支三合局 → 天干（寅午戌月丙、申子辰月壬、亥卯未月甲、巳酉丑月庚）
YUEDE = {"寅": "丙", "午": "丙", "戌": "丙", "申": "壬", "子": "壬", "辰": "壬",
         "亥": "甲", "卯": "甲", "未": "甲", "巳": "庚", "酉": "庚", "丑": "庚"}
# 孤辰寡宿：年支/日支所在方局（三会季节组，非三合组）
FANGJU_OF = {}
for _grp, _members in {"亥子丑": ["亥", "子", "丑"], "寅卯辰": ["寅", "卯", "辰"],
                       "巳午未": ["巳", "午", "未"], "申酉戌": ["申", "酉", "戌"]}.items():
    for _z in _members:
        FANGJU_OF[_z] = _grp
GUCHEN = {"亥子丑": "寅", "寅卯辰": "巳", "巳午未": "申", "申酉戌": "亥"}
GUASU = {"亥子丑": "戌", "寅卯辰": "丑", "巳午未": "辰", "申酉戌": "未"}

CONVENTIONS = {
    "year_boundary": "年柱与流年以立春交节时刻分界（精确到秒，非春节/非正月初零点粗分）",
    "month_boundary": "月柱以节交节时刻分界；月干按『最近一次立春』锚定的年干五虎遁",
    "late_zishi": "晚子时(23:00-24:00)：日柱按当日，时柱天干按次日日干五鼠遁（夜子时派，随 sxtwl）",
    "changsheng": "十二长生采用火土同宫（丙戊同宫、丁己同宫），与 references/地支互动关系与十二长生.md 一致",
    "qiyun_age": "起运按周岁折算（3天=1年，1天=4个月，1时辰=10天），起运年份=出生年+折算年数",
    "yangren": "羊刃只取阳干（甲卯/丙戊午/庚酉/壬子），阴干不置刃",
    "nianliu_boundary": "流年干支按公历年号直接取 (年份-1984) mod 60，该干支自立春当日起生效",
}


# ═══════════════════════════════════════════════════════════════
#  工具函数
# ═══════════════════════════════════════════════════════════════

def configure_stdio():
    """Windows 控制台 UTF-8 兜底。"""
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(encoding="utf-8")
        except Exception:
            pass


def gz_name(gz_obj):
    return TIANGAN[gz_obj.tg] + DIZHI[gz_obj.dz]


def gz_index(name):
    """干支名 → 六十甲子序号 (0=甲子)"""
    tg, zh = name[0], name[1]
    for i in range(60):
        if TIANGAN[i % 10] == tg and DIZHI[i % 12] == zh:
            return i
    raise ValueError(f"非法干支: {name}")


def gz_from_index(i):
    return TIANGAN[i % 10] + DIZHI[i % 12]


def jd_from_datetime(dt):
    """北京墙钟时刻 → sxtwl JD 约定（已用 2024/2025/2026 立春三点标定，误差 <0.2s）。

    sxtwl 的 getJieQiJD/JD2DD 互相一致：JD2DD(jd) 返回的 Y/M/D/h/m/s 即北京时间。
    本函数与该约定对齐：jd = toordinal + 1721424.5 + 当日小数。
    """
    frac = (dt.hour * 3600 + dt.minute * 60 + dt.second + dt.microsecond / 1e6) / 86400.0
    return dt.toordinal() + 1721424.5 + frac


def jd_to_datetime(jd):
    t = sxtwl.JD2DD(jd)
    sec = int(t.s)
    micro = int(round((t.s - sec) * 1e6))
    return datetime(int(t.Y), int(t.M), int(t.D), int(t.h), int(t.m), sec, micro)


def equation_of_time_minutes(dt):
    """Spencer 均时差公式，单位分钟（真太阳时 - 平太阳时）。11月初 ≈ +16.4，2月中 ≈ -14.2。"""
    n = dt.timetuple().tm_yday
    gamma = 2 * math.pi * (n - 1) / 365.0
    eot = 229.18 * (0.000075 + 0.001868 * math.cos(gamma) - 0.032077 * math.sin(gamma)
                    - 0.014615 * math.cos(2 * gamma) - 0.040849 * math.sin(2 * gamma))
    return eot


def true_solar_correct(dt, longitude, tz=8.0):
    """北京时间 → 真太阳时。返回 (corrected_dt, 经度修正分钟, 均时差分钟)。"""
    lon_corr = 4.0 * (longitude - 15.0 * tz)
    eot = equation_of_time_minutes(dt)
    corrected = dt + timedelta(minutes=lon_corr + eot)
    return corrected, lon_corr, eot


def add_years(dt, n):
    """加 n 年，2月29日落地为2月28日。"""
    try:
        return dt.replace(year=dt.year + n)
    except ValueError:  # 2/29
        return dt.replace(year=dt.year + n, day=28)


def collect_terms(birth_year):
    """收集 birth_year-1 .. birth_year+1 的全部节气（去重排序）。

    getJieQiByYear(Y) 返回自立春(Y)至立春(Y+1)共25项，三年并集保证
    任意出生时刻前后各有多个节可用。
    """
    terms, seen = [], set()
    for y in (birth_year - 1, birth_year, birth_year + 1):
        for info in sxtwl.getJieQiByYear(y):
            key = round(info.jd, 6)
            if key in seen:
                continue
            seen.add(key)
            terms.append({
                "index": int(info.jqIndex),
                "name": JIEQI_NAMES[int(info.jqIndex)],
                "is_jie": int(info.jqIndex) in JIE_INDICES,
                "jd": float(info.jd),
                "time": jd_to_datetime(float(info.jd)),
            })
    terms.sort(key=lambda t: t["jd"])
    return terms


def latest_before(terms, jd, predicate=None):
    """返回 jd 之前（含等于）的最近一项；predicate 过滤（如 is_jie / name=='立春'）。"""
    result = None
    for t in terms:
        if t["jd"] <= jd and (predicate is None or predicate(t)):
            result = t
        elif t["jd"] > jd:
            break
    return result


def next_after(terms, jd, predicate=None):
    for t in terms:
        if t["jd"] > jd and (predicate is None or predicate(t)):
            return t
    return None


def shishen(day_stem, other_stem):
    """十神：以日干为"我"。"""
    dw, ow = GAN_WUXING[day_stem], GAN_WUXING[other_stem]
    same_yy = GAN_YINYANG[day_stem] == GAN_YINYANG[other_stem]
    if ow == dw:
        return "比肩" if same_yy else "劫财"
    if SHENG[dw] == ow:
        return "食神" if same_yy else "伤官"
    if KE[dw] == ow:
        return "偏财" if same_yy else "正财"
    if KE[ow] == dw:
        return "七杀" if same_yy else "正官"
    if SHENG[ow] == dw:
        return "偏印" if same_yy else "正印"
    raise ValueError(f"无法判定十神: {day_stem} vs {other_stem}")


def changsheng(day_stem, branch):
    """日干在某地支的十二长生状态（火土同宫表）。"""
    stages = CHANGSHENG_TABLE[day_stem]
    return STAGE_NAMES[stages.index(branch)]


def kongwang(day_gz):
    """日柱旬空。返回 (旬名, [空亡地支])。"""
    g = gz_index(day_gz)
    xun_start = g - (g % 10)
    xun = gz_from_index(xun_start) + "旬"
    kong = [DIZHI[(xun_start + 10) % 12], DIZHI[(xun_start + 11) % 12]]
    return xun, kong


def nayin(gz_name_):
    g = gz_index(gz_name_)
    return NAYIN[g // 2]


def relation_flags(target_branch, chart_branches):
    """target 与原局各支的六冲/六合客观标记。"""
    chong, he = [], []
    for pos, b in chart_branches:
        pair = tuple(sorted((target_branch, b)))
        if pair in [tuple(sorted(p)) for p in LIUCHONG]:
            chong.append(f"{b}({pos})")
        if pair in [tuple(sorted(p)) for p in LIUHE]:
            he.append(f"{b}({pos})")
    return {"冲": chong, "合": he}


def compute_shensha(day_stem, year_branch, month_branch, chart_positions, chart_stem_positions=None):
    """chart_positions: {支: [柱名...]}，chart_stem_positions: {干: [柱名...]}。
    返回 {神煞名: [{branch|stem, position, base?}]}，只列原局见到的。"""
    found = {}

    def add(name, branch, base=None):
        if branch in chart_positions:
            for pos in chart_positions[branch]:
                entry = {"branch": branch, "position": pos}
                if base:
                    entry["base"] = base
                found.setdefault(name, []).append(entry)

    def add_stem(name, stem, base=None):
        if not chart_stem_positions:
            return
        if stem in chart_stem_positions:
            for pos in chart_stem_positions[stem]:
                entry = {"stem": stem, "position": pos}
                if base:
                    entry["base"] = base
                found.setdefault(name, []).append(entry)

    for b in SHENSHA_TIANYI.get(day_stem, []):
        add("天乙贵人", b)
    add("禄神", SHENSHA_LUSHEN[day_stem])
    if day_stem in SHENSHA_YANGREN:
        add("羊刃", SHENSHA_YANGREN[day_stem])
    add("文昌", SHENSHA_WENCHANG[day_stem])
    add("金舆", SHENSHA_JINYU[day_stem])
    # 三合系列：以年支、日支各自起组
    for name, table in SHENSHA_SANHE.items():
        for base_label, base in (("年支", year_branch), ("日支", _pos_of(chart_positions, "日柱"))):
            if base is None:
                continue
            grp = SANHE_GROUP_OF.get(base)
            if grp:
                add(name, table[grp], base=f"{base_label}{base}起")
    add("红鸾", HONGTUAN[year_branch])
    add("天喜", HONGTUAN[HONGTUAN[year_branch]])
    add("天医", DIZHI[(DIZHI.index(month_branch) - 1) % 12])
    # 天德/月德贵人：按月支定，天德干支混合、月德取天干
    td_kind, td_val = TIANDE[month_branch]
    if td_kind == "branch":
        add("天德贵人", td_val)
    else:
        add_stem("天德贵人", td_val)
    add_stem("月德贵人", YUEDE[month_branch])
    # 孤辰寡宿：年支、日支所在方局各起一组
    for base_label, base in (("年支", year_branch), ("日支", _pos_of(chart_positions, "日柱"))):
        if base is None:
            continue
        fang = FANGJU_OF.get(base)
        if fang:
            add("孤辰", GUCHEN[fang], base=f"{base_label}{base}起")
            add("寡宿", GUASU[fang], base=f"{base_label}{base}起")
    return found


def _pos_of(chart_positions, pillar):
    for b, positions in chart_positions.items():
        if pillar in positions:
            return b
    return None


# ═══════════════════════════════════════════════════════════════
#  排盘主逻辑
# ═══════════════════════════════════════════════════════════════

def parse_birth(s):
    s = s.strip().replace("/", "-").replace(".", "-").replace("T", " ")
    fmts = ["%Y-%m-%d %H:%M:%S", "%Y-%m-%d %H:%M", "%Y-%m-%d %H", "%Y-%m-%d"]
    for f in fmts:
        try:
            dt = datetime.strptime(s, f)
            missing = f in ("%Y-%m-%d", "%Y-%m-%d %H")
            return dt, missing
        except ValueError:
            continue
    raise ValueError(f"无法解析出生时间 '{s}'，请用 YYYY-MM-DD HH:MM 格式（北京时间）")


def norm_gender(s):
    s = str(s).strip().lower()
    if s in ("男", "male", "m", "0", "乾造", "乾"):
        return "男"
    if s in ("女", "female", "f", "1", "坤造", "坤"):
        return "女"
    raise ValueError(f"无法解析性别 '{s}'，请用 男/女")


def pillar_dict(pillar, day_stem, chart_positions=None):
    """构造单柱结构。"""
    gan, zhi = pillar[0], pillar[1]
    d = {
        "pillar": pillar,
        "gan": {"stem": gan, "wuxing": GAN_WUXING[gan], "yinyang": GAN_YINYANG[gan],
                "shishen": shishen(day_stem, gan)},
        "zhi": {"branch": zhi, "wuxing": ZHI_WUXING[zhi], "yinyang": ZHI_YINYANG[zhi],
                "stage": changsheng(day_stem, zhi),
                "canggan": [{"stem": c, "wuxing": GAN_WUXING[c], "yinyang": GAN_YINYANG[c],
                             "shishen": shishen(day_stem, c),
                             "stage": changsheng(c, zhi),  # 藏干自身在此地支的长生态
                             "level": lv}
                            for lv, c in zip(("本气", "中气", "余气"), CANGGAN[zhi])]},
        "nayin": nayin(pillar),
    }
    if chart_positions is not None:
        d["shensha"] = [name for name, hits in (chart_positions.get("shensha") or {}).items()
                        if any(h["position"].startswith(pillar) for h in hits)]
    return d


def qiyun_breakdown(distance_days):
    """起运折算：3天=1年，6小时=1个月，0.2小时=1天。返回 (years, months, days)。"""
    hours = distance_days * 24.0
    years = int(hours // 72)
    rem = hours - years * 72
    months = int(rem // 6)
    rem2 = rem - months * 6
    days = rem2 * 5.0
    return years, months, round(days, 1)


def compute_dayun(month_gz, direction, qi_yun_dt, birth_dt, day_stem, chart_branches):
    base = gz_index(month_gz)
    step = 1 if direction == "顺行" else -1
    result = []
    for i in range(10):
        pillar = gz_from_index((base + step * (i + 1)) % 60)
        start_dt = add_years(qi_yun_dt, i * 10)
        end_dt = add_years(qi_yun_dt, (i + 1) * 10)
        gan, zhi = pillar[0], pillar[1]
        result.append({
            "index": i + 1,
            "pillar": pillar,
            "gan_shishen": shishen(day_stem, gan),
            "branch": zhi,
            "stage": changsheng(day_stem, zhi),
            "start_year": start_dt.year,
            "end_year": end_dt.year,
            "start_age": start_dt.year - birth_dt.year,
            "end_age": end_dt.year - birth_dt.year,
            "start_datetime": start_dt.strftime("%Y-%m-%d %H:%M:%S"),
            "end_datetime": end_dt.strftime("%Y-%m-%d %H:%M:%S"),
            "relations": relation_flags(zhi, chart_branches),
        })
    return result


def compute_liunian(years, day_stem, kong_branches, chart_branches, terms):
    out = []
    for y in years:
        pillar = gz_from_index((y - 1984) % 60)
        gan, zhi = pillar[0], pillar[1]
        grp = SANHE_GROUP_OF.get(zhi)
        shensha_hits = []
        for name, table in SHENSHA_SANHE.items():
            for base, base_pos in (("年支", chart_branches[0][1]), ("日支", chart_branches[2][1])):
                if SANHE_GROUP_OF.get(base) and table[SANHE_GROUP_OF[base]] == zhi:
                    shensha_hits.append(f"{name}({base_pos}起)")
        if SHENSHA_TIANYI.get(day_stem) and zhi in SHENSHA_TIANYI[day_stem]:
            shensha_hits.append("天乙贵人")
        out.append({
            "year": y,
            "pillar": pillar,
            "gan_shishen": shishen(day_stem, gan),
            "branch": zhi,
            "branch_wuxing": ZHI_WUXING[zhi],
            "stage": changsheng(day_stem, zhi),
            "tomb": zhi in ("辰", "戌", "丑", "未"),
            "kongwang_fill": zhi in kong_branches,
            "relations": relation_flags(zhi, chart_branches),
            "shensha": shensha_hits,
        })
    return out


def build_paipan(birth_dt, gender, longitude=None, tz=8.0, liunian_years=None, hour_missing=False):
    """主入口：返回完整排盘 dict。"""
    birth_year = birth_dt.year
    birth_jd = jd_from_datetime(birth_dt)
    terms = collect_terms(birth_year)

    # ── 真太阳时 ──────────────────────────────────────────
    true_solar = None
    effective_dt = birth_dt
    if longitude is not None:
        corrected, lon_corr, eot = true_solar_correct(birth_dt, longitude, tz)
        true_solar = {
            "applied": True,
            "longitude_east": longitude,
            "timezone_offset": tz,
            "longitude_correction_minutes": round(lon_corr, 2),
            "equation_of_time_minutes": round(eot, 2),
            "total_correction_minutes": round(lon_corr + eot, 2),
            "corrected_time": corrected.strftime("%Y-%m-%d %H:%M:%S"),
            "note": "真太阳时 = 北京时间 + 经度修正 + 均时差；四柱按校正后时刻排定",
        }
        effective_dt = corrected

    # 跨日校正后需重算 jd 与节气集合
    if effective_dt.year != birth_year:
        terms = collect_terms(effective_dt.year)
        birth_year = effective_dt.year
        birth_jd = jd_from_datetime(effective_dt)

    # ── 年柱（立春精确分界）─────────────────────────────────
    lichun = latest_before(terms, birth_jd, lambda t: t["name"] == "立春")
    if lichun is None:
        raise ValueError("节气数据不足以定年柱，请确认出生年份在 sxtwl 支持范围内")
    year_num = lichun["time"].year
    year_gz = gz_from_index((year_num - 1984) % 60)

    # ── 月柱（节精确分界 + 最近立春锚定五虎遁）──────────────
    cur_jie = latest_before(terms, birth_jd, lambda t: t["is_jie"])
    if cur_jie is None:
        raise ValueError("节气数据不足以定月柱")
    month_branch = JIE_TO_BRANCH[cur_jie["index"]]
    anchor_offset = (DIZHI.index(month_branch) - DIZHI.index("寅")) % 12
    month_stem = TIANGAN[(TIANGAN.index(WUHU[year_gz[0]]) + anchor_offset) % 10]
    month_gz = month_stem + month_branch

    # ── 日柱、时柱（sxtwl；跨日校正后用校正日期）────────────
    day_obj = sxtwl.fromSolar(effective_dt.year, effective_dt.month, effective_dt.day)
    day_gz = gz_name(day_obj.getDayGZ())
    hour_gz = gz_name(day_obj.getHourGZ(effective_dt.hour))

    # ── 日主、空亡 ────────────────────────────────────────
    day_stem = day_gz[0]
    xun, kong = kongwang(day_gz)

    # ── 原局地支位置索引（神煞/关系用）──────────────────────
    chart_branches = [("年支", None), ("月支", None), ("日支", None), ("时支", None)]
    pillar_names = ["年柱", "月柱", "日柱", "时柱"]
    raw_pillars = {"year": year_gz, "month": month_gz, "day": day_gz, "hour": hour_gz}
    chart_positions = {}
    chart_stem_positions = {}
    for key, pos in zip(("year", "month", "day", "hour"), pillar_names):
        b = raw_pillars[key][1]
        chart_branches[pillar_names.index(pos)] = (pos, b)
        chart_positions.setdefault(b, []).append(pos)
        chart_stem_positions.setdefault(raw_pillars[key][0], []).append(pos)

    # ── 神煞 ─────────────────────────────────────────────
    shensha = compute_shensha(day_stem, raw_pillars["year"][1], raw_pillars["month"][1],
                              chart_positions, chart_stem_positions)

    # ── 起运与大运 ────────────────────────────────────────
    year_stem_yang = (TIANGAN.index(year_gz[0]) % 2 == 0)
    if gender == "男":
        direction = "顺行" if year_stem_yang else "逆行"
    else:
        direction = "逆行" if year_stem_yang else "顺行"
    if direction == "顺行":
        target_jie = next_after(terms, birth_jd, lambda t: t["is_jie"])
    else:
        target_jie = cur_jie
    if target_jie is None:
        raise ValueError("节气数据不足以定起运，请确认出生日期在支持范围内")
    distance_days = abs(target_jie["jd"] - birth_jd)
    by, bm, bd = qiyun_breakdown(distance_days)
    qi_yun_dt = effective_dt + timedelta(days=distance_days * 365.2425 / 3.0)
    dayun = compute_dayun(month_gz, direction, qi_yun_dt, effective_dt, day_stem, chart_branches)

    # ── 当前大运 ─────────────────────────────────────────
    now = datetime.now()
    current_dayun = None
    for du in dayun:
        s = datetime.strptime(du["start_datetime"], "%Y-%m-%d %H:%M:%S")
        e = datetime.strptime(du["end_datetime"], "%Y-%m-%d %H:%M:%S")
        if s <= now < e:
            current_dayun = dict(du)
            break

    # ── 流年 ─────────────────────────────────────────────
    liunian = compute_liunian(liunian_years or [], day_stem, kong, chart_branches, terms)

    # ── 五行计数（三口径，仅供参考）────────────────────────
    gan_count, benqi_count, all_canggan = {}, {}, {}
    for w in ("金", "木", "水", "火", "土"):
        gan_count[w] = benqi_count[w] = all_canggan[w] = 0
    for key in ("year", "month", "day", "hour"):
        p = raw_pillars[key]
        gan_count[GAN_WUXING[p[0]]] += 1
        benqi_count[ZHI_WUXING[p[1]]] += 1
        for c in CANGGAN[p[1]]:
            all_canggan[GAN_WUXING[c]] += 1

    # ── 组装 ─────────────────────────────────────────────
    sizhu = {}
    for key, pos in zip(("year", "month", "day", "hour"), pillar_names):
        sizhu[key] = pillar_dict(raw_pillars[key], day_stem)
        sizhu[key]["position"] = pos
        sizhu[key]["kongwang_branch"] = raw_pillars[key][1] in kong
        sizhu[key]["shensha"] = [n for n, hits in shensha.items()
                                 if any(h["position"] == pos for h in hits)]

    jieqi_info = {
        "current_jie": {"name": cur_jie["name"], "time": cur_jie["time"].strftime("%Y-%m-%d %H:%M:%S")},
        "next_jie": None,
        "month_number_for_tiaohou": (DIZHI.index(month_branch) - DIZHI.index("寅")) % 12 + 1,
        "note": "调候月份以节定月：寅=正月 … 丑=腊月；穷通宝鉴按此月份取篇",
    }
    nxt = next_after(terms, birth_jd, lambda t: t["is_jie"])
    if nxt:
        jieqi_info["next_jie"] = {"name": nxt["name"], "time": nxt["time"].strftime("%Y-%m-%d %H:%M:%S")}

    data = {
        "meta": {
            "tool": "bazi paipan",
            "version": "2.0.0",
            "backend": "sxtwl + 节气JD精确分界",
            "generated_at": now.strftime("%Y-%m-%d %H:%M:%S"),
            "birth_raw": birth_dt.strftime("%Y-%m-%d %H:%M:%S"),
            "birth_input_note": "北京时间" + ("（用户未提供时辰，默认按 00:00 排盘，必须与用户确认时辰！）" if hour_missing else ""),
            "hour_missing": hour_missing,
            "gender": gender,
            "zao": "乾造" if gender == "男" else "坤造",
            "true_solar": true_solar,
        },
        "conventions": CONVENTIONS,
        "day_master": {"stem": day_stem, "wuxing": GAN_WUXING[day_stem],
                       "yinyang": GAN_YINYANG[day_stem]},
        "sizhu": sizhu,
        "kongwang": {"xun": xun, "branches": kong,
                     "note": "全局标记：涉及空亡地支的生克、墓库开闭、根气判断按效率大幅衰减处理"},
        "jiaojie": jieqi_info,
        "wuxing_count": {"天干四字": gan_count, "地支本气": benqi_count, "藏干合计": all_canggan,
                         "note": "仅供肉眼参考，旺衰必须按流程分析，不得以计数代替"},
        "shensha": shensha,
        "qi_yun": {
            "direction": direction,
            "rule": ("乾造阳年顺行、阴年逆行" if gender == "男" else "坤造阴年顺行、阳年逆行"),
            "anchor_jie": {"name": target_jie["name"], "time": target_jie["time"].strftime("%Y-%m-%d %H:%M:%S")},
            "distance_days": round(distance_days, 4),
            "breakdown": {"years": by, "months": bm, "days": bd},
            "qi_yun_datetime": qi_yun_dt.strftime("%Y-%m-%d %H:%M:%S"),
            "qi_yun_year": qi_yun_dt.year,
            "text": f"{by}年{bm}个月{bd}天后起运（{direction}，交{target_jie['name']}折算）",
        },
        "dayun": dayun,
        "current_dayun": current_dayun,
        "as_of": now.strftime("%Y-%m-%d %H:%M:%S"),
    }
    if liunian_years:
        data["liunian"] = liunian
    return data


def summary_text(data):
    """人类可读摘要（stdout 展示用；JSON 仍是唯一事实源）。"""
    lines = []
    meta = data["meta"]
    lines.append(f"【排盘摘要】{meta['zao']}　出生（北京时间）: {meta['birth_raw']}")
    if meta.get("true_solar") and meta["true_solar"].get("applied"):
        ts = meta["true_solar"]
        lines.append(f"  真太阳时: {ts['corrected_time']}（经度修正 {ts['longitude_correction_minutes']:+.1f} 分，"
                     f"均时差 {ts['equation_of_time_minutes']:+.1f} 分）")
    dm = data["day_master"]
    lines.append(f"  日主: {dm['stem']}（{dm['yinyang']}{dm['wuxing']}）")
    for key in ("year", "month", "day", "hour"):
        p = data["sizhu"][key]
        cg = "、".join(f"{c['stem']}({c['shishen']})" for c in p["zhi"]["canggan"])
        kw = " 🈳空亡" if p["kongwang_branch"] else ""
        ss = f"　神煞: {'、'.join(p['shensha'])}" if p["shensha"] else ""
        lines.append(f"  {p['position']}: {p['pillar']}　{p['gan']['shishen']}　"
                     f"{p['zhi']['stage']}　藏干: {cg}{kw}{ss}　纳音{p['nayin']}")
    k = data["kongwang"]
    lines.append(f"  空亡: {k['xun']} → {'、'.join(k['branches'])}空")
    j = data["jiaojie"]
    lines.append(f"  月令: {data['sizhu']['month']['pillar'][1]}月（调候月份第{j['month_number_for_tiaohou']}月，"
                 f"节 {j['current_jie']['name']} {j['current_jie']['time']}）")
    q = data["qi_yun"]
    lines.append(f"  起运: {q['text']}　起运时间 {q['qi_yun_datetime']}")
    if data.get("current_dayun"):
        c = data["current_dayun"]
        lines.append(f"  当前大运: 第{c['index']}步 {c['pillar']}（{c['start_year']}-{c['end_year']}，"
                     f"{c['start_age']}-{c['end_age']} 岁前后）")
    lines.append("  大运: " + " → ".join(f"{d['pillar']}({d['start_year']})" for d in data["dayun"]))
    if data.get("liunian"):
        lines.append("  流年: " + "；".join(
            f"{l['year']} {l['pillar']}({l['gan_shishen']}, {l['stage']}"
            f"{', 填空亡' if l['kongwang_fill'] else ''}{', 墓库' if l['tomb'] else ''})"
            for l in data["liunian"]))
    if data["shensha"]:
        lines.append("  神煞: " + "；".join(
            f"{n}: " + "、".join(f"{h.get('branch') or h.get('stem')}({h['position']})"
                                 + (f"[{h['base']}]" if h.get('base') else "")
                                 for h in hits)
            for n, hits in data["shensha"].items()))
    lines.append("  ⚠ 以上为脚本唯一事实源；分析须按 SKILL.md 流程进行，禁止手推排盘要素。")
    return "\n".join(lines)


def main():
    parser = argparse.ArgumentParser(description="八字排盘引擎（bazi-analysis v2.0 单一事实源）")
    parser.add_argument("--birth", required=True, help='出生时间 "YYYY-MM-DD HH:MM[:SS]"，北京时间')
    parser.add_argument("--gender", required=True, help="男/女（乾造/坤造）")
    parser.add_argument("--longitude", type=float, default=None, help="出生地东经度数（启用真太阳时校正）")
    parser.add_argument("--tz", type=float, default=8.0, help="时区偏移小时（默认 8=东八区）")
    parser.add_argument("--liunian", default="", help="流年年份，逗号分隔，如 2024,2025,2026")
    parser.add_argument("-o", "--output", default=None, help="JSON 输出路径（缺省打到 stdout）")
    args = parser.parse_args()

    try:
        birth_dt, hour_missing = parse_birth(args.birth)
        gender = norm_gender(args.gender)
        years = []
        if args.liunian.strip():
            for tok in args.liunian.split(","):
                tok = tok.strip()
                if tok:
                    y = int(tok)
                    if not 1900 <= y <= 2100:
                        raise ValueError(f"流年年份超出支持范围: {y}")
                    years.append(y)
        data = build_paipan(birth_dt, gender, args.longitude, args.tz, years, hour_missing)
    except ValueError as e:
        sys.stderr.write(f"排盘失败: {e}\n"
                         "请向用户确认出生时间/性别后重试；仍失败则索要用户提供的排盘结果，禁止编造。\n")
        sys.exit(1)
    except Exception as e:  # sxtwl 范围/运行时异常
        sys.stderr.write(f"排盘异常: {type(e).__name__}: {e}\n"
                         "若为出生年份超出支持范围等底层限制，请向用户索要排盘结果，禁止编造。\n")
        sys.exit(1)

    payload = json.dumps(data, ensure_ascii=False, indent=2)
    if args.output:
        with open(args.output, "w", encoding="utf-8") as f:
            f.write(payload)
        print(summary_text(data))
        print(f"\n[JSON 已写入] {args.output}")
    else:
        print(payload)


if __name__ == "__main__":
    configure_stdio()
    main()
