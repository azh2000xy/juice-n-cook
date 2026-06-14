#!/usr/bin/env python3
"""
构建食谱索引 — 扫描 recipes/ 目录生成 recipe_index.yaml

所有食谱统一使用 YAML frontmatter + Markdown 格式。
统一格式后删除了旧的 HowToCook 正则解析逻辑。

用法: python build_index.py
输出: .claude/skills/juice-n-cook/references/recipe_index.yaml
"""

import re
import yaml
from pathlib import Path

ROOT = Path(__file__).parent.parent
RECIPES_DIR = ROOT / "recipes"
OUTPUT_PATH = ROOT / ".claude" / "skills" / "juice-n-cook" / "references" / "recipe_index.yaml"


def parse_frontmatter(content: str) -> dict:
    """解析 YAML frontmatter"""
    match = re.match(r'^---\s*\n(.*?)\n---\s*\n', content, re.DOTALL)
    if match:
        try:
            return yaml.safe_load(match.group(1)) or {}
        except yaml.YAMLError:
            pass
    return {}


def parse_recipe(fm: dict, filepath: str, source: str) -> dict:
    """从 YAML frontmatter 提取食谱索引条目"""
    difficulty = fm.get('difficulty', 3)
    if isinstance(difficulty, str):
        difficulty = difficulty.count('★')

    return {
        'title': fm.get('title', Path(filepath).stem),
        'category': fm.get('category', 'other'),
        'cooking_method': fm.get('cooking_method', '通用'),
        'difficulty': difficulty,
        'ingredients': fm.get('ingredients', []),
        'tags': fm.get('tags', []),
        'file': str(Path(filepath).relative_to(ROOT)).replace('\\', '/'),
        'source': source,
    }


def build_index():
    """扫描所有食谱并构建索引"""
    recipes = []

    for md_file in sorted(RECIPES_DIR.rglob("*.md")):
        with open(md_file, "r", encoding="utf-8") as f:
            content = f.read()

        fm = parse_frontmatter(content)
        if not fm or 'title' not in fm:
            print(f"  SKIP (no frontmatter): {md_file.name}")
            continue

        # 判断来源
        if 'cooking' in md_file.parts:
            source = 'howtocook'
        elif 'juice' in md_file.parts:
            source = 'juice-book'
        else:
            source = 'unknown'

        info = parse_recipe(fm, str(md_file), source)
        recipes.append(info)

    # 构建索引结构
    index = {
        'total': len(recipes),
        'by_category': {},
        'by_ingredient': {},
        'recipes': recipes,
    }

    for r in recipes:
        cat = r.get('category', 'other')
        index['by_category'].setdefault(cat, []).append(r['title'])

    for r in recipes:
        for ing in r.get('ingredients', []):
            index['by_ingredient'].setdefault(ing, []).append(r['title'])

    # 写入输出
    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    with open(OUTPUT_PATH, "w", encoding="utf-8") as f:
        yaml.dump(index, f, allow_unicode=True, default_flow_style=False, sort_keys=False)

    # 摘要
    cooking_count = sum(1 for r in recipes if r['source'] == 'howtocook')
    juice_count = sum(1 for r in recipes if r['source'] == 'juice-book')

    print(f"Index built successfully!")
    print(f"  Total recipes: {len(recipes)}")
    print(f"    - Cooking: {cooking_count}")
    print(f"    - Juice:   {juice_count}")
    print(f"  Unique ingredients: {len(index['by_ingredient'])}")
    print(f"  Categories: {list(index['by_category'].keys())}")
    print(f"  Output: {OUTPUT_PATH}")


if __name__ == "__main__":
    build_index()
