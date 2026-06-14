# 果蔬汁菜谱 — 项目全貌

## 当前状态

| 指标 | 数据 |
|------|------|
| 菜谱 | 403 道（HowToCook 365 + 3000例提取 38） |
| 果蔬汁 | 58 道（30手创 + 28 OCR提取） |
| **总计** | **461 道** |
| 独立食材 | 1,048 个 |
| 格式 | 全部统一 YAML frontmatter + Markdown |
| Web App | https://juice-n-cook.onrender.com |
| GitHub | https://github.com/azh2000xy/juice-n-cook |

## 项目结构

```
D:\D\果蔬汁菜谱\
├── app.py                         ← Flask Web 后端（搜索/详情/做法API）
├── templates/index.html            ← 移动优先单页面（PWA，可装到桌面）
├── static/                         ← manifest.json + sw.js + 图标
├── render.yaml                     ← Render 一键部署配置
├── requirements_web.txt            ← flask + pyyaml + gunicorn
├── recipes/
│   ├── cooking/  403道             ← 全部统一 YAML frontmatter
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
│   └── juice/     58道
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
│   ├── ocr_pipeline.py            ← 扫描PDF → Tesseract OCR → 文本
│   ├── pdf_to_images.py           ← PDF → PNG（PyMuPDF）
│   ├── extract_pdf.py             ← 文字PDF直接提取
│   └── extract_cooking_recipes.py ← OCR文本 → 自动识别食谱边界
├── data/                          ← 中间产物（不提交git）
├── 菜谱pdf/                       ← 原始PDF（不提交git）
├── .gitignore / LICENSE / README.md
└── CLAUDE.md                      ← 本文件
```

## 数据来源与缺口

| 来源 | 已提取 | 总量 | 提取率 | 缺口原因 |
|------|------|------|------|------|
| HowToCook | 365 | 365 | 100% | — |
| 蔬果汁轻断食 PDF | 58 | ~80 | ~72% | OCR 损失 20% |
| 超人气家常菜3000例 PDF | 38 | ~500+ | ~7% | OCR 极差，水产/热菜漏掉 |

**已知缺口**：鲍鱼、海参、龙虾等高端水产，部分热菜（炒/烧/炖），面点烘焙。

## 所有脚本速查

| 脚本 | 用法 | 用途 |
|------|------|------|
| `build_index.py` | `python scripts/build_index.py` | **每次增删食谱后必跑** |
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

### D. 部署更新
```
git push → Render 自动部署（约2分钟）
手机刷新 https://juice-n-cook.onrender.com 即可
```

## 核心设计决策

1. **统一YAML frontmatter**：365个HowToCook菜谱已批量转换
2. **食材别名扩展**：用户输入"咸猪蹄"→匹配索引中的"猪蹄"（通过ingredients_index.yaml别名）
3. **步骤预计算**：build_index.py提取前3步存入索引，搜索API不读文件
4. **双栖食材**：番茄/黄瓜/胡萝卜等标记为fruit-vegetable，同时推荐菜谱+果蔬汁

## 已知问题

1. **OCR 质量瓶颈**：《超人气家常菜3000例》提取率仅7%，需更高DPI或不同OCR引擎
2. **食材覆盖不全**：高端水产(鲍鱼)、部分西式食材、烘焙原料缺失
3. **Render 休眠**：15分钟无人访问自动休眠，首次打开等30秒
4. **路径分隔符**：索引用 `/` 统一，代码已处理 Windows/Linux 兼容

## 下一步可做的

- [ ] 提高大PDF OCR质量（200+ DPI重跑，或用PaddleOCR）
- [ ] 补充鲍鱼/海参/龙虾等水产食谱（手工或新PDF）
- [ ] 加营养数据字段（卡路里/蛋白质）
- [ ] 用户反馈机制（"做过""好吃""太麻烦"）
- [ ] 购物清单自动汇总
