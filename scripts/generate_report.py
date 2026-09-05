#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
八字分析 HTML 报告生成器 — bazi-analysis v2.0

用法：
  python generate_report.py --input bazi-data.json --validate     # 只校验（铁律 15：先验证后生成）
  python generate_report.py --input bazi-data.json --output report.html

输入 JSON schema 见 references/html-report-guide.md 第二节：
  meta    : {birth, zao, question, mode[, true_solar]}
  paipan  : paipan_result.json 全文原样嵌入
  md_full : {step0, step1, step1_5, step2 ... step8} 各步骤 md 逐字全文

校验规则（--validate）：
  - meta 四要素齐全
  - paipan 关键域齐全（sizhu 四柱 / kongwang / qi_yun / dayun×10 / conventions）
  - md_full 长度下限 + 【第N步·输出】标记 + 占位签名检测（全文保真，禁止压缩）
  - 完整分析模式必须含 step8 审查记录；step7 必须含「小白总结」
依赖：仅 Python 标准库。
"""

import sys
import json
import html
import re
import argparse
from datetime import datetime

VERSION = "2.0.0"

PLACEHOLDER_SIGNATURES = ["未做分析", "未做解卦分析", "TODO", "[待填]", "待补充", "此处占位"]

MIN_LENGTHS = {"step0": 20, "step1": 50, "step1_5": 20, "step2": 50, "step3": 50,
               "step4": 50, "step5": 50, "step6": 50, "step7": 200, "step8": 30}

STEP_MARKERS = {f"step{i}": f"【第{i}步·输出】" for i in (0, 1, 2, 3, 4, 5, 6, 7)}

STEP_TITLES = {
    "step0": "第零步 · 排盘与意图路由",
    "step1": "第一步 · 原局结构",
    "step1_5": "第1.5步 · 验前事校验",
    "step2": "第二步 · 气象与调候",
    "step3": "第三步 · 格局判断",
    "step4": "第四步 · 寻根与权属",
    "step5": "第五步 · 做功结构",
    "step6": "第六步 · 大运与流年",
    "step7": "第七步 · 综合判断与策略",
    "step8": "第八步 · 子代理审查报告",
    "step9": "第九步 · 报告生成记录",
}

PILLAR_ORDER = [("year", "年柱"), ("month", "月柱"), ("day", "日柱"), ("hour", "时柱")]


# ═══════════════════════════════════════════════════════════════
#  校验
# ═══════════════════════════════════════════════════════════════

def validate(data):
    """返回 (errors, warnings)。errors 非空 = 禁止生成。"""
    errors, warnings = [], []

    meta = data.get("meta")
    if not isinstance(meta, dict):
        errors.append("meta 域缺失")
        meta = {}
    for k in ("birth", "zao", "question", "mode"):
        if not str(meta.get(k, "")).strip():
            errors.append(f"meta.{k} 缺失或为空")

    pp = data.get("paipan")
    if not isinstance(pp, dict):
        errors.append("paipan 域缺失（必须原样嵌入 paipan_result.json 全文）")
        pp = {}
    else:
        for k in ("sizhu", "kongwang", "jiaojie", "qi_yun", "dayun", "conventions"):
            if k not in pp:
                errors.append(f"paipan.{k} 缺失")
        sz = pp.get("sizhu") or {}
        for key, _ in PILLAR_ORDER:
            if key not in sz:
                errors.append(f"paipan.sizhu.{key} 缺失")
        dayun = pp.get("dayun")
        if not isinstance(dayun, list) or len(dayun) != 10:
            errors.append(f"paipan.dayun 必须为 10 步大运（当前 {len(dayun) if isinstance(dayun, list) else '非列表'}）")

    md = data.get("md_full")
    if not isinstance(md, dict):
        errors.append("md_full 域缺失")
        md = {}

    required = ["step0", "step1", "step2", "step3", "step4", "step5", "step6", "step7"]
    if str(meta.get("mode", "")) == "完整分析":
        required.append("step8")

    for k in required:
        v = md.get(k)
        if not isinstance(v, str) or not v.strip():
            errors.append(f"md_full.{k} 缺失（须为步骤文件逐字全文）")
            continue
        if len(v) < MIN_LENGTHS.get(k, 20):
            errors.append(f"md_full.{k} 长度 {len(v)} < 下限 {MIN_LENGTHS.get(k, 20)}（疑似被压缩改写）")
        marker = STEP_MARKERS.get(k)
        if marker and marker not in v:
            errors.append(f"md_full.{k} 缺少强制输出标记「{marker}」")
        if k == "step7" and "小白总结" not in v:
            errors.append("md_full.step7 缺少「小白总结」段（铁律 11）")
        if k == "step8" and "审查" not in v:
            errors.append("md_full.step8 缺少审查记录")

    v15 = md.get("step1_5")
    if isinstance(v15, str) and v15.strip() and len(v15) < 10 and "未触发" not in v15:
        warnings.append("md_full.step1_5 内容过短，若为条件未触发请写明「本步未触发」")

    for k, v in md.items():
        if isinstance(v, str):
            for sig in PLACEHOLDER_SIGNATURES:
                if sig in v:
                    errors.append(f"md_full.{k} 命中占位签名「{sig}」")

    return errors, warnings


# ═══════════════════════════════════════════════════════════════
#  轻量 Markdown → HTML
# ═══════════════════════════════════════════════════════════════

def md_inline(s):
    s = html.escape(s, quote=False)
    s = re.sub(r"\*\*(.+?)\*\*", r"<strong>\1</strong>", s)
    s = re.sub(r"`([^`]+)`", r"<code>\1</code>", s)
    return s


def md_to_html(text):
    out = []
    in_ul = in_ol = in_table = in_quote = False

    def close_all():
        nonlocal in_ul, in_ol, in_table, in_quote
        if in_ul:
            out.append("</ul>")
            in_ul = False
        if in_ol:
            out.append("</ol>")
            in_ol = False
        if in_table:
            out.append("</table>")
            in_table = False
        if in_quote:
            out.append("</blockquote>")
            in_quote = False

    for raw in text.split("\n"):
        stripped = raw.strip()
        if stripped.startswith("|") and stripped.endswith("|"):
            cells = [c.strip() for c in stripped.strip("|").split("|")]
            if cells and all(re.fullmatch(r":?-{3,}:?", c) for c in cells):
                continue  # 表头分隔行
            if not in_table:
                close_all()
                out.append('<table class="mdt">')
                in_table = True
                out.append("<tr>" + "".join(f"<th>{md_inline(c)}</th>" for c in cells) + "</tr>")
            else:
                out.append("<tr>" + "".join(f"<td>{md_inline(c)}</td>" for c in cells) + "</tr>")
            continue
        if in_table:
            out.append("</table>")
            in_table = False
        if not stripped:
            close_all()
            continue
        m = re.match(r"^(#{1,4})\s+(.*)$", stripped)
        if m:
            close_all()
            lvl = min(len(m.group(1)) + 1, 5)
            out.append(f"<h{lvl}>{md_inline(m.group(2))}</h{lvl}>")
            continue
        if stripped.startswith("- ") or stripped.startswith("* "):
            if not in_ul:
                close_all()
                out.append("<ul>")
                in_ul = True
            out.append(f"<li>{md_inline(stripped[2:])}</li>")
            continue
        mnum = re.match(r"^(\d+)[.、)）]\s*(.*)$", stripped)
        if mnum:
            if not in_ol:
                close_all()
                out.append("<ol>")
                in_ol = True
            out.append(f"<li>{md_inline(mnum.group(2))}</li>")
            continue
        if stripped.startswith("> "):
            if not in_quote:
                close_all()
                out.append("<blockquote>")
                in_quote = True
            out.append(f"<p>{md_inline(stripped[2:])}</p>")
            continue
        if re.fullmatch(r"-{3,}", stripped):
            close_all()
            out.append("<hr>")
            continue
        close_all()
        out.append(f"<p>{md_inline(stripped)}</p>")
    close_all()
    return "\n".join(out)


# ═══════════════════════════════════════════════════════════════
#  渲染
# ═══════════════════════════════════════════════════════════════

def fmt_relations(rel):
    if not isinstance(rel, dict):
        return "—"
    parts = []
    if rel.get("冲"):
        parts.append("冲:" + "、".join(rel["冲"]))
    if rel.get("合"):
        parts.append("合:" + "、".join(rel["合"]))
    return "<br>".join(md_inline(p) for p in parts) if parts else "—"


def build_header(meta, pp):
    ts = meta.get("true_solar") or "未校正真太阳时"
    return f"""
<div class="report-header">
  <h1>八字命理分析报告</h1>
  <div class="badge">bazi-analysis v{VERSION} · {html.escape(str(meta.get('mode', '')))}</div>
  <p class="question">{md_inline(str(meta.get('question', '')))}</p>
  <p class="date">出生（北京时间）：{md_inline(str(meta.get('birth', '')))}　{html.escape(str(meta.get('zao', '')))}　{md_inline(ts)}</p>
</div>"""


def build_info_bar(pp):
    dm = pp.get("day_master") or {}
    kw = pp.get("kongwang") or {}
    qy = pp.get("qi_yun") or {}
    cur = pp.get("current_dayun") or {}
    jj = pp.get("jiaojie") or {}
    items = [
        ("日主", f"{dm.get('stem', '—')}（{dm.get('yinyang', '')}{dm.get('wuxing', '')}）"),
        ("空亡", f"{kw.get('xun', '—')} → {'、'.join(kw.get('branches', []))}"),
        ("调候月份", f"第 {jj.get('month_number_for_tiaohou', '—')} 月"),
        ("起运", qy.get("text", "—")),
        ("当前大运", f"{cur.get('pillar', '—')}（{cur.get('start_year', '—')}-{cur.get('end_year', '—')}）" if cur else "—"),
    ]
    cells = "".join(f'<div class="info-item"><span class="label">{k}</span><span class="value">{md_inline(v)}</span></div>'
                    for k, v in items)
    return f'<div class="info-bar">{cells}</div>'


def build_pillar_table(pp):
    kw_branches = set((pp.get("kongwang") or {}).get("branches", []))
    rows = []
    for key, pos in PILLAR_ORDER:
        p = (pp.get("sizhu") or {}).get(key) or {}
        gan = p.get("gan") or {}
        zhi = p.get("zhi") or {}
        cg = "<br>".join(f"{md_inline(c.get('stem', ''))}({md_inline(c.get('shishen', ''))}·{md_inline(c.get('stage', ''))})"
                         for c in zhi.get("canggan", []))
        shensha = "、".join(md_inline(s) for s in p.get("shensha", [])) or "—"
        kong = "🈳 空亡" if p.get("kongwang_branch") else ""
        cls = ' class="kongwang"' if p.get("kongwang_branch") else ""
        rows.append(
            f"<tr{cls}><td>{pos}</td><td>{md_inline(gan.get('shishen', ''))}</td>"
            f"<td class='pillar-gz'>{md_inline(p.get('pillar', ''))}</td><td>{md_inline(p.get('nayin', ''))}</td>"
            f"<td class='cg'>{cg}</td><td>{md_inline(zhi.get('stage', ''))}</td>"
            f"<td>{shensha}</td><td>{kong}{'<br>' if kong and zhi.get('branch') in kw_branches else ''}"
            f"{'支空' if zhi.get('branch') in kw_branches else ''}</td></tr>")
    return f"""
<h2>四柱盘面</h2>
<table class="pz">
<tr><th>柱位</th><th>十神</th><th>干支</th><th>纳音</th><th>藏干（十神·长生态）</th><th>地支长生</th><th>神煞</th><th>空亡</th></tr>
{''.join(rows)}
</table>"""


def build_dayun_table(pp):
    cur_idx = (pp.get("current_dayun") or {}).get("index")
    rows = []
    for d in pp.get("dayun", []):
        cls = ' class="current"' if cur_idx is not None and d.get("index") == cur_idx else ""
        rows.append(
            f"<tr{cls}><td>{d.get('index', '')}</td><td class='pillar-gz'>{md_inline(d.get('pillar', ''))}</td>"
            f"<td>{md_inline(d.get('gan_shishen', ''))}</td><td>{d.get('start_year', '')}-{d.get('end_year', '')}</td>"
            f"<td>{d.get('start_age', '')}-{d.get('end_age', '')}</td><td>{md_inline(d.get('stage', ''))}</td>"
            f"<td>{fmt_relations(d.get('relations'))}</td></tr>")
    return f"""
<h2>起运与大运</h2>
<p class="qiyun-note">{md_inline((pp.get('qi_yun') or {}).get('text', ''))}</p>
<table class="pz">
<tr><th>步</th><th>大运</th><th>十神</th><th>年份</th><th>年龄</th><th>长生</th><th>与原局</th></tr>
{''.join(rows)}
</table>"""


def build_liunian_table(pp):
    ln = pp.get("liunian") or []
    if not ln:
        return ""
    rows = []
    for l in ln:
        marks = []
        if l.get("tomb"):
            marks.append("墓库")
        if l.get("kongwang_fill"):
            marks.append("填空亡")
        rows.append(
            f"<tr><td>{l.get('year', '')}</td><td class='pillar-gz'>{md_inline(l.get('pillar', ''))}</td>"
            f"<td>{md_inline(l.get('gan_shishen', ''))}</td><td>{md_inline(l.get('stage', ''))}</td>"
            f"<td>{'、'.join(marks) if marks else '—'}</td><td>{fmt_relations(l.get('relations'))}</td></tr>")
    return f"""
<h2>流年干支（脚本计算）</h2>
<table class="pz">
<tr><th>年份</th><th>干支</th><th>十神</th><th>长生</th><th>标记</th><th>与原局</th></tr>
{''.join(rows)}
</table>"""


def build_shensha(pp):
    ss = pp.get("shensha") or {}
    if not ss:
        return "<h2>神煞</h2><p>原局未命中常用神煞。</p>"
    items = "".join(
        f"<li><strong>{md_inline(name)}</strong>：" +
        "、".join(f"{md_inline(h.get('branch') or h.get('stem', ''))}（{md_inline(h.get('position', ''))}"
                  f"{('，' + md_inline(h['base'])) if h.get('base') else ''}）" for h in hits) +
        "</li>"
        for name, hits in ss.items())
    return f"<h2>神煞</h2><ul class='ss-list'>{items}</ul>"


def build_conventions(pp):
    conv = pp.get("conventions") or {}
    items = "".join(f"<li>{md_inline(v)}</li>" for v in conv.values())
    return f"<h2>排盘约定（口径透明）</h2><ul class='conv'>{items}</ul>"


def build_md_appendix(md_full):
    order = ["step0", "step1", "step1_5", "step2", "step3", "step4", "step5", "step6", "step7", "step8", "step9"]
    sections, count = [], 0
    for key in order:
        v = md_full.get(key)
        if not isinstance(v, str) or not v.strip():
            continue
        count += 1
        title = STEP_TITLES.get(key, key)
        sections.append(f'<section class="md-step"><h3>{md_inline(title)}</h3>\n{md_to_html(v)}\n</section>')
    return f"<h2>📜 推演过程全文</h2>\n{''.join(sections)}", count


CSS = """
* { margin: 0; padding: 0; box-sizing: border-box; }
body { font-family: "Noto Serif SC", "Source Han Serif SC", "SimSun", "宋体", serif;
       background: #f5f0e8; color: #3a3226; line-height: 1.8; }
.container { max-width: 780px; margin: 0 auto; padding: 40px 24px 60px; }
.report-header { text-align: center; padding: 32px 0 24px; border-bottom: 2px solid #8b7355; margin-bottom: 24px; }
.report-header h1 { font-size: 28px; color: #5c3d2e; letter-spacing: 4px; }
.badge { display: inline-block; background: #5c3d2e; color: #f5f0e8; border-radius: 4px; padding: 2px 10px; font-size: 12px; margin-top: 8px; }
.report-header .question { font-size: 15px; color: #6b5a4e; margin-top: 12px; }
.report-header .date { font-size: 13px; color: #9e8b7a; margin-top: 4px; }
.info-bar { display: flex; flex-wrap: wrap; gap: 10px; justify-content: center; margin-bottom: 28px; }
.info-item { background: #fff; border: 1px solid #d4c5b2; border-radius: 6px; padding: 6px 14px; }
.info-item .label { font-size: 12px; color: #9e8b7a; display: block; }
.info-item .value { font-size: 15px; color: #5c3d2e; font-weight: bold; }
h2 { font-size: 20px; color: #5c3d2e; border-left: 4px solid #8b7355; padding-left: 12px; margin: 32px 0 16px; }
h3 { font-size: 16px; color: #6b5a4e; margin: 12px 0 8px; }
table.pz { width: 100%; border-collapse: collapse; margin-bottom: 28px; font-size: 14px; background: #fff; }
table.pz th { background: #5c3d2e; color: #f5f0e8; padding: 8px 6px; }
table.pz td { padding: 8px 6px; text-align: center; border-bottom: 1px solid #d4c5b2; }
table.pz td.pillar-gz { font-size: 18px; font-weight: bold; color: #5c3d2e; letter-spacing: 2px; }
table.pz td.cg { text-align: left; font-size: 13px; }
tr.kongwang { background: #fdeaea; }
tr.current { background: #fdf2e0; font-weight: bold; }
.qiyun-note { font-size: 14px; color: #6b5a4e; margin-bottom: 10px; }
ul.ss-list, ul.conv { background: #fff; border: 1px solid #d4c5b2; border-radius: 8px; padding: 16px 16px 16px 36px; margin-bottom: 28px; }
ul.conv { font-size: 13px; color: #6b5a4e; }
.md-step { background: #fff; border: 1px solid #d4c5b2; border-radius: 8px; padding: 20px; margin-bottom: 16px; }
.md-step h3 { border-bottom: 1px dashed #d4c5b2; padding-bottom: 6px; }
.md-step p { margin: 6px 0; }
.md-step ul, .md-step ol { margin: 6px 0 6px 24px; }
.md-step blockquote { border-left: 3px solid #c49a3c; background: #fdf8ef; padding: 6px 12px; margin: 8px 0; }
.md-step code { background: #f1e9dc; border-radius: 3px; padding: 0 4px; }
table.mdt { border-collapse: collapse; margin: 10px 0; font-size: 13px; }
table.mdt th, table.mdt td { border: 1px solid #d4c5b2; padding: 4px 8px; }
table.mdt th { background: #efe6d6; }
.report-footer { margin-top: 48px; padding-top: 24px; border-top: 1px solid #d4c5b2; text-align: center; font-size: 12px; color: #9e8b7a; }
.verify-stamp { font-size: 14px; color: #5c8a5c; margin-bottom: 8px; }
.disclaimer { margin-top: 12px; font-style: italic; }
@media print { body { background: #fff; } .container { max-width: 100%; padding: 20px; }
  table.pz th { -webkit-print-color-adjust: exact; } }
"""


def render(data):
    meta = data.get("meta", {})
    pp = data.get("paipan", {})
    md_full = data.get("md_full", {})
    appendix, md_count = build_md_appendix(md_full)
    liunian_block = build_liunian_table(pp)
    block_count = 7 + (1 if liunian_block else 0)  # 头/信息条/盘面/大运/神煞/约定/附录/页脚 + 流年
    body = "".join([
        build_header(meta, pp),
        build_info_bar(pp),
        build_pillar_table(pp),
        build_dayun_table(pp),
        liunian_block,
        build_shensha(pp),
        build_conventions(pp),
        appendix,
        f"""
<div class="report-footer">
  <p class="verify-stamp">✅ validate 校验通过 · {md_count} 步全文附录</p>
  <p class="generate-time">报告生成时间：{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}</p>
  <p class="disclaimer">此报告由 AI 八字命理分析 Skill 自动生成，供决策参考之用，不替代专业意见；重大决策请咨询相应专业人士。</p>
</div>""",
    ])
    page = f"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>八字命理分析报告 · {html.escape(str(meta.get('birth', '')))}</title>
<style>{CSS}</style>
</head>
<body>
<div class="container">
{body}
</div>
</body>
</html>"""
    return page, block_count, md_count


def main():
    parser = argparse.ArgumentParser(description="八字分析 HTML 报告生成器")
    parser.add_argument("--input", required=True, help="bazi-data.json 路径")
    parser.add_argument("--output", help="report.html 输出路径")
    parser.add_argument("--validate", action="store_true", help="只校验不生成（铁律 15）")
    args = parser.parse_args()

    try:
        with open(args.input, "r", encoding="utf-8") as f:
            data = json.load(f)
    except Exception as e:
        sys.stderr.write(f"读取失败: {e}\n")
        sys.exit(1)

    errors, warnings = validate(data)
    if warnings:
        for w in warnings:
            print(f"⚠ {w}")
    if errors:
        for e in errors:
            print(f"❌ {e}")
        print(f"\n校验未通过（{len(errors)} 项错误）。禁止生成报告，请先修正 bazi-data.json。")
        sys.exit(1)
    print("✅ 校验通过：meta 四要素、paipan 关键域、md_full 长度/标记/占位检测全部合格。")

    if args.validate:
        return

    page, block_count, md_count = render(data)
    if not args.output:
        sys.stderr.write("未指定 --output，校验通过但未生成。加上 --output report.html 重跑。\n")
        sys.exit(1)
    with open(args.output, "w", encoding="utf-8") as f:
        f.write(page)
    print(f"📄 报告已生成: {args.output}（板块 {block_count}（含全文附录 {md_count} 步），约 {len(page) // 1024} KB）")


if __name__ == "__main__":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    except Exception:
        pass
    main()
