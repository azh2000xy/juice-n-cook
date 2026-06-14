# 果蔬汁菜谱 — 项目全貌

## 当前状态

| 指标 | 数据 |
|------|------|
| 菜谱 | 5,851 道（HowToCook 365 + 3000例提取 38 + Counterfactual 100 + EPUB菜谱大全 5,348） |
| 果蔬汁 | 178 道（30手创 + 28 OCR提取 + 120 EPUB果蔬汁断食法） |
| **总计** | **6,029 道** |
| 独立食材 | 18,451 个 |
| 格式 | 全部统一 YAML frontmatter + Markdown |
| Web App | https://juice-n-cook.onrender.com |
| GitHub | https://github.com/azh2000xy/juice-n-cook |
| 匹配模式 | 双模式 — 🎯尽量少补食材 / 🔍包括该食材即可 |

## 项目结构

```
D:\D\果蔬汁菜谱\
├── app.py                         ← Flask Web 后端（搜索/详情/做法API）
├── templates/index.html            ← 移动优先单页面（PWA，可装到桌面）
├── static/                         ← manifest.json + sw.js + 图标
├── render.yaml                     ← Render 一键部署配置
├── requirements_web.txt            ← flask + pyyaml + gunicorn
├── recipes/
│   ├── cooking/  5851道            ← 全部统一 YAML frontmatter
│   │   ├── meat_dish/      荤菜
│   │   ├── vegetable_dish/ 素菜
│   │   ├── aquatic/        水产
│   │   ├── soup/           汤羹
│   │   ├── staple/         主食
│   │   ├── breakfast/      早餐
│   │   ├── dessert/        甜品
│   │   ├── drink/          饮品
│   │   ├── condiment/      调料
│   │   └── semi-finished/  半成品
│   └── juice/     178道
│       ├── fruit_juice/     纯果汁
│       ├── vegetable_juice/ 蔬菜汁
│       └── mixed_juice/     混合果蔬汁
├── .claude/skills/juice-n-cook/
│   ├── SKILL.md                   ← Claude Code Skill 定义
│   └── references/
│       ├── recipe_index.yaml      ← 食谱索引（build_index.py 生成）
│       ├── ingredients_index.yaml ← 食材分类+别名
│       └── matching_rules.yaml   ← 打分规则
├── scripts/
│   ├── build_index.py             ← 扫描 recipes/ → 生成 recipe_index.yaml
│   ├── unify_format.py            ← 给纯MD批量加YAML frontmatter
│   ├── normalize_recipes.py       ← 外部数据集字段映射+自动分类
│   ├── deduplicate_recipes.py     ← 分类优先的标题+食材去重
│   ├── import_recipes.py          ← 多数据源导入主入口
│   ├── requirements_import.txt    ← 导入脚本依赖（pandas, rapidfuzz）
│   ├── ocr_pipeline.py            ← 扫描PDF → Tesseract OCR → 文本
│   ├── pdf_to_images.py           ← PDF → PNG（PyMuPDF）
│   ├── extract_pdf.py             ← 文字PDF直接提取
│   └── extract_cooking_recipes.py ← OCR文本 → 自动识别食谱边界
├── data/                          ← 中间产物（不提交git）
│   ├── datasets/                  ← 下载的公开数据集原始文件
│   └── review_queue.csv           ← 待人工审核的疑似重复项
├── 菜谱pdf/                       ← 原始PDF（不提交git）
├── .gitignore / LICENSE / README.md
└── CLAUDE.md                      ← 本文件
```

## 数据来源与缺口

| 来源 | 已提取 | 总量 | 提取率 | 缺口原因 |
|------|------|------|------|------|
| HowToCook | 365 | 365 | 100% | — |
| EPUB 果蔬汁断食法 | 120 | ~150 | ~80% | EPUB中部分配方与已有重复 |
| EPUB 菜谱大全 (6744道) | 5,348 | 6,744 | 79% | 内部重复 1,201 道，解析失败 86 道 |
| Counterfactual Recipe（北大） | 100 | ~2,500 | 4% | 深度挖掘：50菜×2最优变体 |
| 蔬果汁轻断食 PDF | 58 | ~80 | ~72% | OCR 损失 20% |
| 果蔬汁断食法 EPUB | 120 | ~150 | ~80% | 子串匹配+去重 24 道 |
| 超人气家常菜3000例 PDF | 38 | ~500+ | ~7% | OCR 极差 |

### 缺口填补情况

| 缺口 | 之前 | 之后 | 状态 |
|------|------|------|------|
| 鲍鱼 | 0 | **42** | ✅ 已填补 |
| 海参 | 0 | **170** | ✅ 已填补 |
| 龙虾 | 0 | **6** | ✅ 已填补 |
| 螃蟹 | ~30 | **106** | ✅ 大幅改善 |
| 面点 | ~20 | **33** | ⚠️ 改善，仍有缺口 |
| 甜品 | ~23 | **213** | ✅ 已填补 |
| 汤羹 | ~26 | **945** | ✅ 已填补 |
| RecipeNLG 全量 | 未导入 | 2.2M | — | **评估结论：不适合**（见下方） |

### RecipeNLG 评估结论（2026-06）

经过详细评估，**决定不导入 RecipeNLG**：

- 下载需人工浏览器操作（Angular SPA，无 API），或 Kaggle 凭证
- 数据集构建自英文网站（Allrecipes/Food.com），中文菜谱占比 < 0.1%
- 即使下载 1GB CSV 扫描完 2.2M 条，预计仅 0-2000 条中文，且为英译中质量低
- 零 LLM token 消耗（纯 Python 本地处理），但投入产出比不划算
- 评估文件：`C:\Users\WINDOWS\.claude\plans\recipe_nlg_assessment.md`

### 公开数据集优先级（更新）

| 优先级 | 来源 | 中文菜谱量 | 获取 | 状态 |
|--------|------|-----------|------|------|
| P0 | Counterfactual Recipe（北大） | ~2500 条变体 | GitHub 直接下载 | ✅ 已深度挖掘：100道（50菜名×2最优变体） |
| P1 | Kaggle 中文菜谱（60K Dishes 等） | 数千 | Kaggle 账号下载 | 待评估 |
| P2 | DiNeR 关联 1.5M 下厨房语料 | 1.5M | 需联系作者 | 待探索 |
| P3 | RecipeNLG | 极少 | 人工/Kaggle | ❌ 已评估放弃 |

**已知缺口**：鲍鱼、海参、龙虾等高端水产，部分热菜（炒/烧/炖），面点烘焙。

## 所有脚本速查

| 脚本 | 用法 | 用途 |
|------|------|------|
| `build_index.py` | `python scripts/build_index.py` | **每次增删食谱后必跑** |
| `import_recipes.py` | `python scripts/import_recipes.py -i <数据集.json> --source <来源>` | 从公开数据集导入菜谱 |
| `extract_epub_recipes.py` | `python scripts/extract_epub_recipes.py` | 从 EPUB 菜谱书提取结构化数据 |
| `deep_mine_counterfactual.py` | `python scripts/deep_mine_counterfactual.py` | 深度挖掘 Counterfactual 数据集 |
| `normalize_recipes.py` | `import normalize_recipes` (被 import_recipes 调用) | 字段映射、自动分类/做法/难度 |
| `deduplicate_recipes.py` | `import deduplicate_recipes` (被 import_recipes 调用) | 分类优先去重 |
| `unify_format.py` | `python scripts/unify_format.py` | 批量给纯MD添加YAML头 |
| `ocr_pipeline.py` | `python scripts/ocr_pipeline.py <pdf> <out> --tesseract-path D:\E\TOOL\tesseract\tesseract.exe` | OCR扫描PDF |
| `pdf_to_images.py` | `python scripts/pdf_to_images.py <pdf> <out>` | PDF转PNG |
| `extract_pdf.py` | `python scripts/extract_pdf.py <pdf> <out>` | 文字PDF提取 |
| `extract_cooking_recipes.py` | `python scripts/extract_cooking_recipes.py` | OCR文本自动识别食谱 |

## 常规更新流程

### A. 新增PDF食谱
```
1. 放到 菜谱pdf/ 目录
2. 扫描版: python scripts/ocr_pipeline.py "菜谱pdf/xxx.pdf" "data/raw/xxx_ocr/" --tesseract-path D:\E\TOOL\tesseract\tesseract.exe
   文字版: python scripts/extract_pdf.py "菜谱pdf/xxx.pdf" "data/raw/xxx_text/"
3. 告诉Claude: "帮我把 data/raw/xxx_ocr/_combined.txt 结构化生成食谱"
4. python scripts/build_index.py
5. git add -A && git commit -m "Add xxx recipes" && git push
```

### B. 手动加几道食谱
```
1. 在 recipes/cooking/<分类>/ 下创建 .md（参考已有格式的YAML头）
2. python scripts/build_index.py
3. git add -A && git commit -m "Add recipes" && git push
```

### C. 补充食材别名
```
编辑 .claude/skills/juice-n-cook/references/ingredients_index.yaml
（Web app 重启后生效）
```

### C. 从公开数据集导入食谱
```
1. 下载数据集放到 data/datasets/ 目录
2. 干跑预览: python scripts/import_recipes.py -i data/datasets/xxx.json --source <来源> --dry-run
3. 正式导入: python scripts/import_recipes.py -i data/datasets/xxx.json --source <来源>
4. 审核处理: 检查 data/review_queue.csv 中的疑似重复项
5. python scripts/build_index.py
6. git add -A && git commit -m "Add recipes from xxx dataset" && git push
```

### D. 部署更新
```
git push → Render 自动部署（约2分钟）
手机刷新 https://juice-n-cook.onrender.com 即可
```

## 核心设计决策

1. **统一YAML frontmatter**：全部6,029道菜谱统一使用YAML frontmatter + Markdown格式
2. **食材别名扩展**：用户输入"咸猪蹄"→匹配索引中的"猪蹄"（通过ingredients_index.yaml别名）
3. **步骤预计算**：build_index.py提取前3步存入索引，搜索API不读文件
4. **双栖食材**：番茄/黄瓜/胡萝卜等标记为fruit-vegetable，同时推荐菜谱+果蔬汁
5. **多数据源**：从YAML frontmatter的`source`字段读取来源标签（howtocook/juice-book/chinese-cooking-dataset等），build_index.py自动统计
6. **分类先去重**：导入新食谱时先自动推断品类，仅与同品类现有菜谱比对（效率10-50x提升，消除跨品类误判）

## 已知问题

1. **OCR 质量瓶颈**：《超人气家常菜3000例》提取率仅7%，需更高DPI或不同OCR引擎
2. **自动分类精度**：约85%准确率，部分食谱可能跨品类（如甜品被分到主食），可手动修正
3. **Render 休眠**：15分钟无人访问自动休眠，首次打开等30秒
4. **路径分隔符**：索引用 `/` 统一，代码已处理 Windows/Linux 兼容
5. **食材名含量词**：EPUB食材保留原始量词（如"海参一只250克"），搜索结果中食材显示不够简洁

## 下一步可做的

- [ ] 食材名后处理：从带量食材中提取纯净食材名（如"海参一只250克"→"海参"）
- [ ] 提高大PDF OCR质量（200+ DPI重跑，或用PaddleOCR）
- [ ] 加营养数据字段（卡路里/蛋白质）
- [ ] 用户反馈机制（"做过""好吃""太麻烦"）
- [ ] 购物清单自动汇总
- [ ] 自动分类精度提升（EPUB 来自 28 个菜系的精确标签可辅助分类）
