# Changelog

## 2026-05-16 — v1.3 SKILL.md 增强

### SKILL.md 质量提升（9 项）
- **SOP 步骤挂载 reference 钩子**：Step 3（气象）→ 核心法则.md，Step 4（寻根）→ 比劫规则.md，Step 5（做功）→ 地支互动 + 天干五合
- **内联十神速查**：Step 1 嵌入十神定义规则（同我/我生/我克/克我/生我 × 阴阳）
- **内联空亡速查**：Step 1 嵌入六旬空亡口诀
- **Reasoning Principle 格式清理**：行为约束独立为第 6 条，消除混排
- **Advanced References 去重**：删除核心法则重复引用
- **Advanced References 重排序**：按 SOP 步骤 1→7 排列，标注各文献的调用步骤
- **穷通宝鉴示例归位**：孤例合并到调候速查条目内
- **括号修复**：`(\references\...)` → 标准 markdown 链接
- **frontmatter 中文化**

### 配套更新
- README.md 目录树重排（按 SOP 调用顺序）、导航覆盖全部 reference 文件

---

## 2026-05-16 — v1.2 四墓库合并

### 文件合并
- `references/墓库.md` + `辰土.md` + `戌土.md` + `丑土.md` + `未土.md` → `references/四墓库.md`（349 行）
- 提取四篇中重复的三合/三会/卯辰相争等共用逻辑到通用框架
- 交叉引用标注（"见辰土/丑土章节"）替代重复内容

### 配套更新
- SKILL.md 中 5 条分散引用 → 1 条合并引用
- SKILL.md SOP Step 3「四墓库专判」引用路径更新
- README.md 目录树和导航同步

---

## 2026-05-16 — v1.1 比劫规则重写 + 文件中文化

### 比劫规则内容重写
- `references/比劫规则.md`（原 `bijie_rules.md`）：从"十一诀"（40 行）重写为"法则八条 + 夺财专论七条"（135 行）
- 新增核心认知章：印星归属不可一概而论、官星在外制劫财的双重夹击逻辑
- 新增法则：比劫生食伤、合官杀、职业取向（金木实优于水火虚）、羊刃合杀
- 新增夺财专论七条：按「财在内外 × 比劫敌友」穷举矩阵
- 保留原有的宫位、能量路线、主导权排行榜、连体结构等基础架构

### 文件重命名
- `references/bijie_rules.md` → `references/比劫规则.md`
- `references/core_principles.md` → `references/核心法则.md`

### 配套更新
- SKILL.md 中 4 处引用路径 + 1 处描述文本同步
- README.md 中 2 处目录条目同步
