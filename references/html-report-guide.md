# HTML 报告生成指南

> 对应主 Skill 第九步：生成 HTML 可交付报告。第八步审查通过后执行。
> **脚本版本**：v2.0.0 — 排盘盘面（四柱十神藏干长生）+ 起运大运表 + 流年表 + 神煞 + 逐步分析全文附录（md_full 保真）。

---

## 一、生成方式（脚本优先）

### 1.1 首选：Python 脚本生成（省 tokens）

第八步审查通过后，**不在对话中输出完整 HTML**。改为：

1. 将排盘 JSON 与各步骤 md 组装为结构化 JSON（见第二节 schema）
2. JSON 写入案例目录 `bazi-data.json`
3. 先验证再生成（铁律 15）：
   ```bash
   python <skill_dir>/scripts/generate_report.py --input "{案例目录}/bazi-data.json" --validate
   python <skill_dir>/scripts/generate_report.py --input "{案例目录}/bazi-data.json" --output "{案例目录}/report.html"
   ```
4. `--validate` 报错时**禁止生成**，先按报错修正 `bazi-data.json`

### 1.2 回退

仅当本地 Python 不可用时，按第三、四节手动拼接 HTML（消耗大，仅紧急回退），且仍须自查第五节清单。

---

## 二、bazi-data.json Schema

> ⛔ 传给脚本的 JSON 必须包含以下顶层域。字段名固定，不得随意增删。

```json
{
  "meta": { ... },      // 报告元数据（必填）
  "paipan": { ... },    // paipan_result.json 全文原样嵌入（必填）
  "md_full": { ... }    // 各步骤 md 文件逐字全文（必填）
}
```

### 2.1 `meta` 字段

| 字段 | 类型 | 必填 | 说明 |
|------|------|------|------|
| birth | string | ✅ | 出生时间原文（北京时间），如 "1990-06-15 14:30" |
| zao | string | ✅ | "乾造" / "坤造" |
| question | string | ✅ | 用户请求原文或主题简称（信息不足时写当前已知诉求） |
| mode | string | ✅ | "完整分析" / "单点问答" / "排盘确认" |
| true_solar | string |  | 真太阳时说明一句话；未校正写"未校正真太阳时" |

### 2.2 `paipan` 字段

`paipan_result.json` 的**完整内容原样嵌入**（meta/conventions/sizhu/kongwang/jiaojie/wuxing_count/shensha/qi_yun/dayun/current_dayun/liunian）。禁止摘抄、压缩、改字段名——报告盘面表格全部由此渲染。

### 2.3 `md_full` 字段（逐字全文 · 必填）

> 🚨 **全文保真铁则**：`md_full` 必须**逐字**承载 `步骤N-*.md` 文件的完整原文——以文件读取内容为准，**禁止总结、压缩、改写、删节**。它是 HTML「📜 推演过程全文」附录的数据源，`--validate` 会做长度下限与标记检查。

| 字段 | 必填 | 校验下限 | 额外检查 |
|------|------|---------|---------|
| step0 | ✅ | ≥ 20 字符 | 须含 `【第0步·输出】` |
| step1 | ✅ | ≥ 50 字符 | 须含 `【第1步·输出】` |
| step1_5 | 条件 | ≥ 20 字符（"未触发"两字亦可） | 无 |
| step2 | ✅ | ≥ 50 字符 | 须含 `【第2步·输出】` |
| step3 | ✅ | ≥ 50 字符 | 须含 `【第3步·输出】` |
| step4 | ✅ | ≥ 50 字符 | 须含 `【第4步·输出】` |
| step5 | ✅ | ≥ 50 字符 | 须含 `【第5步·输出】` |
| step6 | ✅ | ≥ 50 字符 | 须含 `【第6步·输出】` |
| step7 | ✅ | ≥ 200 字符 | 须含 `【第7步·输出】` 且含"小白总结" |
| step8 | 完整模式必填 | ≥ 30 字符 | 须含"审查" |
| step9 | 可选 | — | 校验通过记录 |

> ⛔ 占位检测：任何字段命中占位签名（"未做分析""TODO""占位""[待填]""待补充"）直接报错阻断。条件步骤（step1_5）未触发时写入"本步未触发（用户未提供过往事件）"。

---

## 三、HTML 板块结构（脚本自动渲染，回退手拼用）

1. **报告头**：标题「八字命理分析报告」+ 问题 + 出生时间 + 造 + 版本徽章
2. **信息条**：日主｜空亡｜调候月份｜起运｜当前大运｜真太阳时
3. **四柱盘面表**：列 = 柱位/十神/干支/纳音/藏干(十神·长生态)/地支长生/神煞/空亡；空亡支行高亮
4. **起运与大运表**：十步大运（步/干支/十神/起止年份/年龄段/长生/冲合），当前大运行高亮
5. **流年表**（`liunian` 存在时）：年份/干支/十神/长生/标记(墓库/填空亡)/冲合
6. **神煞榜**：神煞名 → 落柱明细（含起组）
7. **排盘约定**：`paipan.conventions` 逐条列出（保证口径透明）
8. **📜 推演过程全文**：`md_full` step0→step8 逐字附录，每步一个 `<section class="md-step">`
9. **页脚**：验证印记（✅ validate 通过 / 审查判定）+ 生成时间 + 免责声明

## 四、CSS 样式规范（回退方案用）

> ⛔ 最低要求：宣纸/赭石/墨色传统配色、`max-width: 780px` 居中、打印友好、空亡与当前大运行高亮。

```css
* { margin: 0; padding: 0; box-sizing: border-box; }
body { font-family: "Noto Serif SC", "Source Han Serif SC", "SimSun", "宋体", serif;
       background: #f5f0e8; color: #3a3226; line-height: 1.8; }
.container { max-width: 780px; margin: 0 auto; padding: 40px 24px 60px; }
.report-header { text-align: center; padding: 32px 0 24px; border-bottom: 2px solid #8b7355; margin-bottom: 24px; }
.report-header h1 { font-size: 28px; color: #5c3d2e; letter-spacing: 4px; }
.badge { display: inline-block; background: #5c3d2e; color: #f5f0e8; border-radius: 4px;
         padding: 2px 10px; font-size: 12px; margin-top: 8px; }
.info-bar { display: flex; flex-wrap: wrap; gap: 10px; justify-content: center; margin-bottom: 28px; }
.info-item { background: #fff; border: 1px solid #d4c5b2; border-radius: 6px; padding: 6px 14px; }
.info-item .label { font-size: 12px; color: #9e8b7a; display: block; }
.info-item .value { font-size: 15px; color: #5c3d2e; font-weight: bold; }
table.pz { width: 100%; border-collapse: collapse; margin-bottom: 28px; font-size: 14px; background: #fff; }
table.pz th { background: #5c3d2e; color: #f5f0e8; padding: 8px 6px; }
table.pz td { padding: 8px 6px; text-align: center; border-bottom: 1px solid #d4c5b2; }
tr.kongwang { background: #fdeaea; }
tr.current { background: #fdf2e0; font-weight: bold; }
h2 { font-size: 20px; color: #5c3d2e; border-left: 4px solid #8b7355; padding-left: 12px; margin: 32px 0 16px; }
.md-step { background: #fff; border: 1px solid #d4c5b2; border-radius: 8px; padding: 20px; margin-bottom: 16px; }
.md-step h3 { font-size: 16px; color: #6b5a4e; margin-bottom: 8px; }
.report-footer { margin-top: 48px; padding-top: 24px; border-top: 1px solid #d4c5b2;
                 text-align: center; font-size: 12px; color: #9e8b7a; }
.verify-stamp { font-size: 14px; color: #5c8a5c; margin-bottom: 8px; }
@media print { body { background: #fff; } .container { max-width: 100%; padding: 20px; } }
```

---

## 五、生成后验证清单

1. `--validate` 已通过且板块计数正常（报告头/信息条/盘面/大运/神煞/约定/全文附录/页脚）
2. 四柱盘面表与 `paipan_result.json` 抽查一致（至少核对日柱与当前大运）
3. 空亡行有 `class="kongwang"`、当前大运行有 `class="current"`
4. `md_full` 抽查：任取 1–2 句步骤文件独有原文，确认逐字出现在 HTML 中
5. 文件写入磁盘成功且可用浏览器打开
