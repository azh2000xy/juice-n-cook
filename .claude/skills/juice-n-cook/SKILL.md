---
name: juice-n-cook
description: |
  菜谱与果蔬汁推荐技能。当用户询问菜谱建议、用特定食材做饭/榨汁、或 meal planning 时自动激活。根据食材类型智能推荐。
---

# 果蔬汁与菜谱推荐 Skill

## 核心逻辑

根据用户提供的食材和偏好，智能推荐菜谱或果蔬汁：

- 🥬 **纯蔬菜** → 推荐菜谱（cooking）
- 🍎 **纯水果** → 推荐果蔬汁（juice）
- 🍅 **双栖食材**（番茄/黄瓜/南瓜/青椒/胡萝卜/玉米等 fruit-vegetable）→ 同时推荐菜谱和果蔬汁
- 🔧 **用户指定做法**（炒/蒸/煮/炖/炸/凉拌）→ 强制菜谱模式，按做法过滤
- 🧃 **用户指定"榨汁"** → 强制果蔬汁模式

## 食材分类

食材分类依据 `references/ingredients_index.yaml`：

| 分类 | 含义 | 处理方式 |
|------|------|----------|
| `fruit` | 水果 | 归入水果集合 |
| `vegetable` | 蔬菜 | 归入蔬菜集合 |
| `fruit-vegetable` | 双栖食材 | **同时归入**水果和蔬菜两个集合 |

## 推荐流程（Step 1-4）

### Step 1: 分类用户食材

对于用户输入的每个食材，查找 `references/ingredients_index.yaml`：
- 精确匹配 `name` 字段
- 若无精确匹配，模糊匹配 `aliases` 列表
- 若仍匹配不到，**反问用户确认该食材的分类**

### Step 2: 决定推荐类型

```
纯水果（vegetable_set 为空）  → type = "juice"
纯蔬菜（fruit_set 为空）      → type = "cooking"
混合或双栖食材                → type = "both"
用户指定"炒/蒸/煮/炖/炸/凉拌" → 强制 type = "cooking"，cooking_method 过滤
用户指定"榨汁"               → 强制 type = "juice"
```

### Step 3: 匹配打分

对 `references/recipe_index.yaml` 中目标类型的所有食谱：

1. 计算 `overlap = 用户食材 ∩ 食谱食材`
2. 计算 `score = |overlap| / |食谱食材| × WEIGHT_OVERLAP`
3. 额外加分：完全匹配 +BONUS_EXACT，应季 +BONUS_SEASON
4. 按 score 降序排序，取 Top N（默认 5）

打分权重参考 `references/matching_rules.yaml`。

### Step 4: 展示结果

对每个推荐食谱，按以下格式展示：

```markdown
### 🍳 [菜名/果汁名] | ⭐难度 | ⏱耗时 | 🔥[做法]

**✅ 你已有：** [匹配到的食材列表]
**📋 还需要：** [缺失的食材列表]
**📝 做法：** [前 2-3 步操作简述]

[📂 查看完整食谱](recipes/cooking/xxx.md)
```

## 数据文件结构

所有食谱（菜谱 + 果蔬汁）统一使用 **YAML frontmatter + Markdown 正文** 格式。

### 统一 frontmatter 字段

```yaml
---
title: 西红柿炒鸡蛋          # 菜名
category: vegetable_dish     # 分类（cooking: aquatic/meat_dish/soup/... juice: fruit_juice/vegetable_juice/mixed_juice）
cooking_method: 炒           # 做法（炒/蒸/煮/炖/炸/凉拌/榨汁/搅拌/烤...）
difficulty: 2                # 难度 1-5
tags: [西红柿, 鸡蛋, 家常菜]  # 标签
ingredients: [西红柿, 鸡蛋, 食用油, 盐]  # 食材列表（匹配核心字段）
source: howtocook            # 来源（howtocook / juice-book）
---
```

### 果蔬汁额外字段（juice 专属）
- `ingredient_types`: [fruit/vegetable/fruit-vegetable] — 食材类型
- `benefits`: 功效描述（排毒/美白/减脂…）
- `season`: 适宜季节
- `equipment`: 所需工具（榨汁机/搅拌机…）

### 数据来源
- **菜谱**（`recipes/cooking/`）：[Anduin2017/HowToCook](https://github.com/Anduin2017/HowToCook) + 统一格式转换
- **果蔬汁**（`recipes/juice/`）：《蔬果汁轻断食》PDF OCR 提取 + 手工创建

### 添加新食谱
1. 在对应目录下创建 `.md` 文件，填写 YAML frontmatter
2. 运行 `python scripts/build_index.py` 重建索引
3. Skill 立即生效，无需其他修改

## 边界情况处理

1. **用户只输入 1 个食材**：放宽 overlap 阈值，也推荐需要额外 2-3 个食材的食谱
2. **用户输入"随便"或空输入**：推荐当季热门食谱（从 recipe_index 随机取 5 个）
3. **用户输入做法与食材冲突**（如"香蕉 炒"）：提示"香蕉通常用于榨汁而非炒菜，是否改为果汁推荐？"
4. **完全无匹配**：降级策略 — 忽略 category 过滤，全局搜索匹配度最高的食谱
