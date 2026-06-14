# 果蔬汁菜谱 - 项目说明

## 项目简介

这是一个 Claude Code Skill 项目，提供基于食材的智能菜谱和果蔬汁推荐。

**核心逻辑**：蔬菜 → 菜谱，水果 → 果蔬汁，番茄/黄瓜等双栖食材 → 两者都推。

## 项目结构

```
D:\D\果蔬汁菜谱\
├── .claude\skills\juice-n-cook\    # Claude Code Skill
│   ├── SKILL.md                    # Skill 入口和推荐逻辑
│   └── references\                 # 数据文件
│       ├── ingredients_index.yaml  # 食材分类索引
│       ├── recipe_index.yaml       # 食谱索引（由 build_index.py 生成）
│       └── matching_rules.yaml     # 匹配规则配置
├── recipes\
│   ├── cooking\                    # 菜谱（来源：HowToCook + 用户 PDF）
│   └── juice\                      # 果蔬汁（来源：蔬果汁轻断食 PDF）
│       ├── fruit_juice\            # 纯果汁
│       ├── vegetable_juice\        # 纯蔬菜汁
│       └── mixed_juice\            # 混合果蔬汁
├── scripts\                        # 工具脚本
│   ├── extract_pdf.py              # PDF 文本提取
│   ├── parse_to_markdown.py        # AI 辅助结构化
│   └── build_index.py              # 构建食谱索引
├── data\                           # 数据处理中间产物
└── 菜谱pdf\                        # 原始 PDF 文件（不可变）
```

## 使用方法

### 启用 Skill
在 Claude Code 中输入 `/juice-n-cook` 或直接描述需求即可自动触发。

### 使用示例
```
- "我有番茄、鸡蛋和葱，想炒个菜"
- "苹果、胡萝卜、芹菜可以榨什么汁？"
- "晚上只有白菜和豆腐，推荐个简单的菜"
- "我想做鱼，但不知道买什么配菜"
```

## 数据来源

- **菜谱**：[Anduin2017/HowToCook](https://github.com/Anduin2017/HowToCook)（MIT License）
- **果蔬汁**：《蔬果汁轻断食》(韩)全周漓 著
- **补充菜谱**：《超人气家常菜3000例》全国畅销经典纪念版

## 扩展指南

### 添加新食谱
1. 在 `recipes/cooking/` 或 `recipes/juice/` 下创建 Markdown 文件
2. 确保 YAML frontmatter 包含所有必需字段
3. 运行 `python scripts/build_index.py` 更新索引

### 添加新食材
在 `ingredients_index.yaml` 中新增条目：
- 正确设置 `category` (fruit/vegetable/fruit-vegetable)
- 补充常用别名到 `aliases`
- 标注 `season` 以便季节推荐

### 调整匹配规则
编辑 `matching_rules.yaml` 中的权重和阈值。
