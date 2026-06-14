#!/usr/bin/env python3
"""
从 EPUB 菜谱大全提取结构化菜谱数据。

输入: 菜谱pdf/最牛的菜谱：6744道菜谱大全.epub
输出: data/datasets/epub_recipes.json（供 import_recipes.py 使用）

EPUB 结构：
  - 6744 个 HTML 章节，每章一道菜
  - <h3> 菜名 </h3>
  - <p> 原料: ... </p>     ← 食材列表（顿号/逗号分隔，带量）
  - <p> 制作方法: ... </p>  ← 步骤（1、2、3、... 编号）
  - <p> 特点: ... </p>     ← 口味描述
  - <p> 所属菜系：... </p> ← 鲁菜/川菜/粤菜...
"""

import json
import os
import re
import sys
import zipfile
from collections import Counter
from pathlib import Path

sys.stdout.reconfigure(encoding='utf-8')

ROOT = Path(__file__).parent.parent
EPUB_PATH = ROOT / "菜谱pdf" / "最牛的菜谱：6744道菜谱大全 (菜谱大全) (z-library.sk, 1lib.sk, z-lib.sk).epub"
OUT_PATH = ROOT / "data" / "datasets" / "epub_recipes.json"


# ========== HTML 解析 ==========

def parse_html(content: str) -> dict | None:
    """从单个 HTML 文件中提取菜谱字段"""
    # Title
    title_m = re.search(r'<h3>(.+?)</h3>', content)
    if not title_m:
        return None
    title = title_m.group(1).strip()
    # 清理标题中的 HTML 实体
    title = title.replace('&nbsp;', ' ').replace('&amp;', '&').replace('&lt;', '<').replace('&gt;', '>')

    # Ingredients — 在 "原料:" 或 "原料：" 后面的 <p> 中
    ing_m = re.search(r'原料[：:]\s*</p>\s*<p>(.+?)</p>', content, re.DOTALL)
    if not ing_m:
        # 尝试无换行的格式
        ing_m = re.search(r'原料[：:]\s*(.+?)(?:</p>|制作方法)', content, re.DOTALL)
    raw_ingredients = ing_m.group(1).strip() if ing_m else ""

    # Steps — 在 "制作方法:" 后面的 <p> 中
    steps_m = re.search(r'制作方法[：:]\s*</p>\s*<p>(.+?)</p>', content, re.DOTALL)
    if not steps_m:
        steps_m = re.search(r'【制作过程】\s*</p>\s*<p>(.+?)</p>', content, re.DOTALL)
    if not steps_m:
        steps_m = re.search(r'制作方法[：:]\s*(.+?)(?:</p>|特点)', content, re.DOTALL)
    raw_steps_text = steps_m.group(1).strip() if steps_m else ""

    # Cuisine
    cuisine_m = re.search(r'所属菜系[：:]\s*(.+?)(?:</p>|$)', content)
    cuisine = cuisine_m.group(1).strip() if cuisine_m else ""

    # Characteristics
    char_m = re.search(r'特点[：:]\s*</p>\s*<p>(.+?)</p>', content, re.DOTALL)
    if not char_m:
        char_m = re.search(r'特点[：:]\s*(.+?)(?:</p>|所属菜系)', content, re.DOTALL)
    characteristics = char_m.group(1).strip() if char_m else ""

    if not raw_ingredients or not raw_steps_text:
        return None  # 关键字段缺失

    # Parse ingredients into list
    ingredients = parse_ingredients(raw_ingredients)

    # Parse steps
    steps = parse_steps(raw_steps_text)

    if not ingredients or not steps:
        return None

    return {
        'title': title,
        'raw_ingredients': ingredients,
        'raw_steps': steps,
        'cuisine': cuisine,
        'characteristics': characteristics,
    }


def parse_ingredients(text: str) -> list[str]:
    """将原料文本解析为食材名列表（保留带量的原始描述）"""
    # 去掉引号和首尾空白
    text = text.strip().strip('"').strip("'")
    text = re.sub(r'<[^>]+>', '', text)  # 去掉可能的 HTML 标签

    # 按句号、逗号、顿号、分号分拆，但保留"各XX克"这类
    # 先按主要分隔符切分
    items = re.split(r'[，,。．、；;]', text)
    items = [i.strip() for i in items if i.strip()]

    # 进一步处理"XX各YY克"模式（如"冬菇、盐笋、口蘑各25克" → 拆分）
    result = []
    for item in items:
        # 跳过纯数字或过短
        if re.match(r'^[\d\s\.\,]+$', item) or len(item) < 2:
            continue
        # 处理"各XX克"模式
        if '各' in item and re.search(r'各\d+', item):
            # "冬菇、盐笋、口蘑各25克" → split by 、 first
            sub_items = re.split(r'[、]', item)
            measure = re.search(r'各(\d+(?:\.\d+)?\s*(?:克|g|毫升|ml|只|个|条|根|块|段))', item)
            if measure and len(sub_items) > 1:
                for sub in sub_items[:-1]:  # last one is "各XX克"
                    sub = sub.strip()
                    if len(sub) >= 1:
                        result.append(sub + measure.group(1))
                continue
        result.append(item)

    return [r for r in result if len(r) >= 1 and len(r) <= 50]


def parse_steps(text: str) -> list[str]:
    """将制作方法文本解析为步骤列表"""
    text = text.strip().strip('"').strip("'")
    text = re.sub(r'<[^>]+>', '', text)

    # 尝试按编号拆分 (1、2、3、 或 1. 2. 3. 或 ① ②)
    # 先找编号模式
    numbered = re.split(r'(?:\d+[\.、\s)）]\s*)', text)
    numbered = [s.strip() for s in numbered if len(s.strip()) >= 4]

    if len(numbered) >= 2:
        return numbered

    # 回退：按句号/分号拆分
    items = re.split(r'[。；]', text)
    items = [s.strip() for s in items if len(s.strip()) >= 4]

    if items:
        return items

    return [text]


# ========== 主流程 ==========

def main():
    print(f"EPUB: {EPUB_PATH}")
    print(f"Size: {os.path.getsize(EPUB_PATH)/1024/1024:.1f} MB\n")

    with zipfile.ZipFile(EPUB_PATH, 'r') as z:
        html_files = sorted([f for f in z.namelist() if f.endswith('.html') or f.endswith('.xhtml')])
        print(f"HTML chapters: {len(html_files)}")

        recipes = []
        errors = 0
        dup_titles = Counter()  # 追踪重复标题

        for i, fname in enumerate(html_files):
            try:
                content = z.read(fname).decode('utf-8', errors='replace')
                recipe = parse_html(content)
                if recipe:
                    # 去重：同一标题已有→跳过
                    title = recipe['title']
                    dup_titles[title] += 1
                    if dup_titles[title] > 1:
                        continue  # 跳过重复
                    recipes.append(recipe)
                else:
                    errors += 1
            except Exception as e:
                errors += 1
                if errors <= 5:
                    print(f"  Error in {fname}: {e}")

            if (i + 1) % 1000 == 0:
                print(f"  Processed {i+1}/{len(html_files)}... extracted {len(recipes)} unique")

    print(f"\n=== Extraction Results ===")
    print(f"  Total chapters: {len(html_files)}")
    print(f"  Unique recipes extracted: {len(recipes)}")
    print(f"  Parse errors: {errors}")
    print(f"  Duplicates removed: {sum(c-1 for c in dup_titles.values() if c > 1)}")

    # Cuisine distribution
    cuisines = Counter(r.get('cuisine', '') for r in recipes)
    print(f"\n  Cuisine distribution:")
    for cu, cnt in cuisines.most_common(20):
        print(f"    {cu}: {cnt}")

    # Ingredient counts
    ing_counts = [len(r['raw_ingredients']) for r in recipes]
    step_counts = [len(r['raw_steps']) for r in recipes]
    print(f"\n  Avg ingredients per recipe: {sum(ing_counts)/len(ing_counts):.1f}")
    print(f"  Avg steps per recipe: {sum(step_counts)/len(step_counts):.1f}")

    # Sample
    print(f"\n  Sample recipes:")
    for r in recipes[:5]:
        print(f"    [{r['cuisine']}] {r['title']}")
        print(f"      ings ({len(r['raw_ingredients'])}): {', '.join(r['raw_ingredients'][:5])}...")
        print(f"      steps ({len(r['raw_steps'])}): {r['raw_steps'][0][:80]}...")

    # Save
    os.makedirs(OUT_PATH.parent, exist_ok=True)
    with open(OUT_PATH, 'w', encoding='utf-8') as f:
        json.dump(recipes, f, ensure_ascii=False, indent=2)

    fsize = os.path.getsize(OUT_PATH)
    print(f"\n  Saved: {OUT_PATH}")
    print(f"  Size: {fsize/1024/1024:.1f} MB")
    print(f"  Ready for: python scripts/import_recipes.py -i {OUT_PATH} --source epub-cookbook")


if __name__ == '__main__':
    main()
