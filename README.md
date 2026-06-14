# 🥕 果蔬汁菜谱 (Juice & Cook)

[![Python](https://img.shields.io/badge/Python-3.8%2B-blue)](https://www.python.org/)
[![License](https://img.shields.io/badge/License-MIT-green)](LICENSE)
[![Recipes](https://img.shields.io/badge/Recipes-423-orange)]()

输入冰箱里的食材，智能推荐中式菜谱和果蔬汁。支持手机端访问。

> 蔬菜 → 菜谱 | 水果 → 果蔬汁 | 番茄/黄瓜等双栖食材 → 两者都推

## 快速开始

```bash
# 1. 克隆仓库
git clone https://github.com/azh2000xy/juice-n-cook.git
cd juice-n-cook

# 2. 安装依赖
pip install -r requirements_web.txt

# 3. 启动
python app.py
```

打开浏览器访问 `http://127.0.0.1:5000`，或用手机访问 `http://<电脑IP>:5000`

## 功能

| 功能 | 说明 |
|------|------|
| 🔍 食材搜索 | 输入食材（空格/逗号分隔），自动匹配食谱 |
| 🧠 智能分类 | 蔬菜→菜谱、水果→果蔬汁、双栖食材→两者 |
| 📋 缺失食材 | 高亮显示已有哪些、还缺哪些，方便采购 |
| 🍳 做法过滤 | 按炒/蒸/煮/榨汁等做法筛选 |
| 📱 手机适配 | 移动优先设计，320px-768px 完美显示 |

## 项目结构

```
juice-n-cook/
├── app.py                         # Flask Web 后端
├── templates/
│   └── index.html                 # 移动优先前端
├── recipes/
│   ├── cooking/                   # 365 道中式菜谱
│   │   ├── meat_dish/             #   荤菜
│   │   ├── vegetable_dish/        #   素菜
│   │   ├── soup/                  #   汤羹
│   │   ├── staple/                #   主食
│   │   ├── aquatic/               #   水产
│   │   ├── breakfast/             #   早餐
│   │   ├── dessert/               #   甜品
│   │   ├── drink/                 #   饮品
│   │   ├── condiment/             #   调料
│   │   └── semi-finished/         #   半成品
│   └── juice/                     # 58 道果蔬汁
│       ├── fruit_juice/           #   纯果汁
│       ├── vegetable_juice/       #   蔬菜汁
│       └── mixed_juice/           #   混合果蔬汁
├── references/                    # 索引 & 食材库
│   ├── recipe_index.yaml          #   食谱索引（build_index.py 生成）
│   ├── ingredients_index.yaml     #   食材分类（水果/蔬菜/双栖）
│   └── matching_rules.yaml        #   匹配规则
├── scripts/
│   ├── build_index.py             #   构建食谱索引
│   ├── unify_format.py            #   批量添加 YAML frontmatter
│   ├── ocr_pipeline.py            #   OCR 管道（扫描版 PDF → 文本）
│   ├── extract_pdf.py             #   文本 PDF 提取
│   └── pdf_to_images.py           #   PDF 转图片
├── .claude/skills/juice-n-cook/
│   └── SKILL.md                   #   Claude Code Skill
├── requirements_web.txt
├── README.md
├── LICENSE
└── .gitignore
```

## 数据来源

| 数据 | 来源 | 数量 |
|------|------|------|
| 中式菜谱 | [Anduin2017/HowToCook](https://github.com/Anduin2017/HowToCook) (MIT) | 365 道 |
| 果蔬汁 | 《蔬果汁轻断食》(韩)全周漓 著，经 OCR + AI 结构化提取 | 58 道 |

## 添加新食谱

### 手动添加
1. 在 `recipes/cooking/` 或 `recipes/juice/` 下创建 `.md` 文件
2. 填写 YAML frontmatter（参考现有文件格式）
3. 运行 `python scripts/build_index.py` 重建索引

### 从 PDF 批量提取
1. 将 PDF 放到 `菜谱pdf/` 目录
2. 扫描版 PDF：`python scripts/ocr_pipeline.py <pdf路径> <输出目录>`
3. 文字版 PDF：`python scripts/extract_pdf.py <pdf路径> <输出目录>`
4. 将提取文本发给 AI 结构化，生成 `.md` 文件

### YAML Frontmatter 格式

```yaml
---
title: 西红柿炒鸡蛋
category: vegetable_dish
cooking_method: 炒
difficulty: 2          # 1-5
tags: [西红柿, 鸡蛋, 家常菜]
ingredients: [西红柿, 鸡蛋, 食用油, 盐, 糖, 葱花]
source: howtocook
---
```

## 作为 Claude Code Skill 使用

本项目同时是一个 Claude Code Skill。克隆后，在项目目录下打开 Claude Code，Skill 会自动注册。

使用方式：直接说"我有番茄和鸡蛋"、"苹果胡萝卜能榨什么汁"即可。

Skill 定义文件：`.claude/skills/juice-n-cook/SKILL.md`

## 手机端使用

```
电脑启动: python app.py
手机访问: http://<电脑IP>:5000
（确保手机和电脑在同一 WiFi）
```

## License

MIT License - 详见 [LICENSE](LICENSE)

菜谱数据来自 [HowToCook](https://github.com/Anduin2017/HowToCook)，同样使用 MIT License。
