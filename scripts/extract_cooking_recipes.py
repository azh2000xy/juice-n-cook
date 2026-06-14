#!/usr/bin/env python3
"""从 OCR 文本批量提取食谱 → 生成 .md 文件"""
import re
from pathlib import Path

COMBINED = Path(__file__).parent.parent / "data/raw/cooking_ocr/_combined.txt"
OUT_DIR = Path(__file__).parent.parent / "recipes/cooking/meat_dish"
OUT_DIR.mkdir(parents=True, exist_ok=True)

def clean(s):
    """清洗 OCR 乱码"""
    s = re.sub(r'[a-zA-Z]{4,}[,.!?\s]*', '', s)  # 长英文串
    s = re.sub(r'[@#\$%^&*]{2,}', '', s)          # 符号串
    s = s.replace('ER', '').replace('AR', '').replace('HR', '').strip()
    return s

def extract():
    with open(COMBINED, "r", encoding="utf-8") as f:
        text = f.read()

    # 按 === PAGE N === 分段
    pages = re.split(r'=+\s*\n=== PAGE \d+\s*\n=+', text)
    print(f"Total pages: {len(pages)}")

    recipes = []
    for pi, page in enumerate(pages):
        lines = page.strip().split('\n')
        if len(lines) < 5:
            continue

        # 找食谱名: 纯中文行, 3-15 字, 不含英文/数字串
        name = None
        in_main = in_sub = in_steps = False
        mains, subs, steps = [], [], []

        for li, line in enumerate(lines):
            s = line.strip()
            if not s:
                continue

            # 找食材标记
            if re.match(r'.{0,3}[主料]', s) and len(s) <= 10:
                in_main = True; in_sub = False; in_steps = False
                continue
            if re.match(r'.{0,3}[辅料]', s) and len(s) <= 10:
                in_sub = True; in_main = False; in_steps = False
                continue
            if re.search(r'(制作|操作).{0,3}(过程|步骤)', s):
                in_steps = True; in_main = False; in_sub = False
                continue

            # 收集内容
            if in_main and len(s) > 3:
                mains.append(clean(s))
            elif in_sub and len(s) > 3 and not re.match(r'^[A-Za-z\s]{4,}$', s):
                subs.append(clean(s))
            elif in_steps and re.match(r'\d+', s):
                step = clean(re.sub(r'^[A-Za-z\s\d\W]*', '', s))
                if step and len(step) > 4:
                    steps.append(step)

            # 找食谱名: 在食材标记前的纯中文短行
            if not name and not in_main and not in_steps:
                if re.match(r'^[一-鿿\s·\-（）]{4,20}$', s):
                    if not re.search(r'(制作|过程|主料|辅料|调料|工具)', s):
                        name = s

        # 保存有效食谱
        if name and (len(mains) + len(subs) + len(steps)) >= 3 and len(name) <= 15:
            # 合并主料辅料文本 → 提取食材名
            all_ings = []
            for txt in mains + subs:
                ings = re.split(r'[，,、\s]+', txt)
                for ing in ings:
                    ing = re.sub(r'\d+.*$', '', ing)  # 去数量
                    ing = re.sub(r'[各每]', '', ing)
                    ing = ing.strip('。，,、；;：:（）() .')
                    if 2 <= len(ing) <= 8 and re.search(r'[一-鿿]', ing):
                        all_ings.append(ing)

            recipes.append({
                'name': name,
                '主料': '；'.join(mains[:3]),
                '辅料': '；'.join(subs[:2]),
                'steps': steps[:4],
                'ingredients': list(set(all_ings))[:12],
            })

    print(f"Found {len(recipes)} recipes")

    # 生成 MD 文件
    created = 0
    for r in recipes:
        # 过滤明显错误的名称
        name = r['name']
        if re.search(r'[a-zA-Z]{4,}|\d{3,}|出版社|印刷|版权', name):
            continue

        safe_name = re.sub(r'[\\/:*?"<>|]', '', name)
        filepath = OUT_DIR / f"{safe_name}.md"

        # 跳过已存在的
        if filepath.exists():
            continue

        ings = r['ingredients']
        if len(ings) < 2:
            continue

        md = f"""---
title: {name}
category: meat_dish
cooking_method: 凉拌
difficulty: 2
tags: {ings[:4]}
ingredients: {ings[:10]}
source: 超人气家常菜3000例
---

## 必备原料和工具

{r['主料']}

{r['辅料']}

## 操作

"""
        for i, step in enumerate(r['steps'], 1):
            md += f"{i}. {step}\n"

        with open(filepath, "w", encoding="utf-8") as f:
            f.write(md)
        created += 1

    print(f"Created {created} new recipe files in {OUT_DIR}")

if __name__ == "__main__":
    extract()
