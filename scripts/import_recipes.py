#!/usr/bin/env python3
"""
多数据源菜谱导入主入口。

数据流：
  公开数据集 (JSON/CSV)
    → 加载为统一格式 (load_*)
    → 规范化 (normalize_recipes.py)
    → 去重 (deduplicate_recipes.py)
    → 写入 .md 文件

用法：
  # 干跑（只统计不写入）
  python scripts/import_recipes.py --input data/datasets/xxx.json --source recipenlg --dry-run

  # 正式导入
  python scripts/import_recipes.py --input data/datasets/xxx.json --source recipenlg

  # 指定最大导入数量
  python scripts/import_recipes.py --input data/datasets/xxx.json --source recipenlg --max 500

  # 仅审核模式：读取规范化数据、去重，但不写入文件
  python scripts/import_recipes.py --input data/normalized/xxx.jsonl --source recipenlg --review-only

环境：
  pip install pandas rapidfuzz pyyaml
"""

import argparse
import json
import sys
from pathlib import Path

import pandas as pd

# 确保可以 import 同目录下的模块
sys.path.insert(0, str(Path(__file__).parent))

from normalize_recipes import normalize_recipe, safe_filename, make_full_md
from deduplicate_recipes import (
    load_index_by_category,
    batch_deduplicate,
    write_review_csv,
)


# ========== 路径配置 ==========

ROOT = Path(__file__).parent.parent
RECIPES_DIR = ROOT / "recipes" / "cooking"
INDEX_PATH = ROOT / ".claude" / "skills" / "juice-n-cook" / "references" / "recipe_index.yaml"
DATA_DIR = ROOT / "data"
REVIEW_CSV_PATH = DATA_DIR / "review_queue.csv"


# ========== 数据集加载器 ==========

def load_recipenlg(filepath: str) -> list[dict]:
    """
    加载 RecipeNLG JSON 数据集，筛选中文菜谱。

    RecipeNLG 格式:
      [
        {"title": "...", "ingredients": ["...", ...], "directions": ["...", ...], "ner": [...]},
        ...
      ]

    返回统一内部格式的 raw dict 列表。
    """
    with open(filepath, 'r', encoding='utf-8') as f:
        data = json.load(f)

    recipes = []
    for item in data:
        title = item.get('title', '').strip()
        if not title:
            continue

        # 简单中文检测：标题含有汉字
        if not any('一' <= ch <= '鿿' for ch in title):
            continue

        ingredients = item.get('ingredients', [])
        if not ingredients:
            continue

        directions = item.get('directions', [])
        if not directions:
            continue

        recipes.append({
            'title': title,
            'raw_ingredients': list(ingredients),
            'raw_steps': list(directions),
            'description': '',
            'tips': [],
        })

    return recipes


def load_chinese_cooking_dataset(filepath: str) -> list[dict]:
    """
    加载 ChineseCooking5k / 标准中文菜谱数据集。

    预期 CSV 列: title, ingredients, steps, category(可选), description(可选)
    或者 JSON 数组 [{title, ingredients, steps, ...}, ...]
    """
    path = Path(filepath)

    if path.suffix.lower() == '.csv':
        df = pd.read_csv(filepath, encoding='utf-8')
        # 标准化列名
        df.columns = [c.strip().lower() for c in df.columns]
        col_map = {
            'title': 'title',
            'name': 'title',
            '菜名': 'title',
            'ingredients': 'ingredients',
            'ingredient': 'ingredients',
            '食材': 'ingredients',
            'steps': 'steps',
            'directions': 'steps',
            '步骤': 'steps',
            'category': 'raw_category',
            '分类': 'raw_category',
            'description': 'description',
        }
        df.rename(columns={k: v for k, v in col_map.items() if k in df.columns}, inplace=True)

        recipes = []
        for _, row in df.iterrows():
            title = str(row.get('title', '')).strip()
            if not title or title == 'nan':
                continue

            # 解析食材
            raw_ings = row.get('ingredients', '')
            if isinstance(raw_ings, str):
                raw_ings = [i.strip() for i in raw_ings.replace(';', ',').split(',') if i.strip()]

            # 解析步骤
            raw_steps = row.get('steps', '')
            if isinstance(raw_steps, str):
                raw_steps = [s.strip() for s in re.split(r'[\n\r]+|\d+[\.\、\s)]', raw_steps) if s.strip()]

            recipes.append({
                'title': title,
                'raw_ingredients': list(raw_ings),
                'raw_steps': list(raw_steps),
                'raw_category': str(row.get('raw_category', '')).strip() if 'raw_category' in df.columns else '',
                'description': str(row.get('description', '')).strip() if 'description' in df.columns else '',
            })

    elif path.suffix.lower() == '.json':
        with open(filepath, 'r', encoding='utf-8') as f:
            data = json.load(f)

        if not isinstance(data, list):
            raise ValueError("JSON 数据集预期为数组格式")

        recipes = []
        for item in data:
            title = (item.get('title') or item.get('name') or '').strip()
            if not title:
                continue

            ings = (item.get('raw_ingredients') or item.get('ingredients') or
                    item.get('ingredient') or [])
            steps = (item.get('raw_steps') or item.get('steps') or
                     item.get('directions') or item.get('instructions') or [])

            recipes.append({
                'title': title,
                'raw_ingredients': list(ings),
                'raw_steps': list(steps),
                'raw_category': item.get('category', ''),
                'description': item.get('description', ''),
                'tips': item.get('tips', []),
            })
    else:
        raise ValueError(f"不支持的文件格式: {path.suffix}（仅支持 .csv .json）")

    return recipes


def load_jsonl(filepath: str) -> list[dict]:
    """
    加载之前规范化好的 JSONL 中间产物。
    每行一个 JSON 对象，已有 title/ingredients/steps/category 等字段。
    """
    recipes = []
    with open(filepath, 'r', encoding='utf-8') as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                obj = json.loads(line)
                recipes.append(obj)
            except json.JSONDecodeError:
                pass
    return recipes


# ========== 主导入流程 ==========

def import_dataset(
    filepath: str,
    source: str,
    recipe_index_path: str | Path = INDEX_PATH,
    output_dir: str | Path = RECIPES_DIR,
    dry_run: bool = False,
    max_recipes: int = 0,
    review_csv_path: str | Path = REVIEW_CSV_PATH,
) -> dict:
    """
    主入口：加载数据集 → 规范化 → 去重 → 写入 .md 文件。

    返回统计字典:
      {
        'total_raw': int,        # 数据集原始条数
        'normalized': int,       # 成功规范化条数
        'accepted': int,         # 通过去重
        'skipped': int,          # 因去重跳过
        'review': int,           # 待人工审核
        'written': int,          # 实际写入文件数（干跑为 0）
        'errors': int,           # 规范化失败
        'by_category': dict,     # {category: count}
      }
    """
    import re

    # --- 1. 加载数据集 ---
    print(f"\n{'='*60}")
    print(f"导入数据集: {filepath}")
    print(f"来源标签: {source}")
    print(f"{'='*60}")

    path = Path(filepath)
    suffix = path.suffix.lower()

    if suffix == '.jsonl':
        raw_recipes = load_jsonl(filepath)
        loader_name = 'jsonl (pre-normalized)'
    elif source == 'recipenlg' or (suffix == '.json' and path.stem.startswith('recipenlg')):
        raw_recipes = load_recipenlg(filepath)
        loader_name = 'RecipeNLG'
    else:
        raw_recipes = load_chinese_cooking_dataset(filepath)
        loader_name = 'Chinese Cooking Dataset'

    print(f"\n[加载] {loader_name}: {len(raw_recipes)} 条原始记录")

    if max_recipes > 0 and len(raw_recipes) > max_recipes:
        raw_recipes = raw_recipes[:max_recipes]
        print(f"  → 限制为前 {max_recipes} 条")

    # --- 2. 规范化 ---
    print(f"\n[规范化] 开始...")
    normalized = []
    errors = 0

    for i, raw in enumerate(raw_recipes):
        try:
            # 如果是 JSONL 预规范化数据，跳过 normalize_recipe
            if suffix == '.jsonl':
                norm = raw  # 已有所有字段
            else:
                norm = normalize_recipe(raw, source)

            if norm:
                normalized.append(norm)
            else:
                errors += 1
        except Exception as e:
            errors += 1
            if errors <= 5:
                print(f"  错误 [{i}]: {e}")

    print(f"  成功: {len(normalized)}, 失败: {errors}")

    if not normalized:
        return {'total_raw': len(raw_recipes), 'normalized': 0, 'accepted': 0,
                'skipped': 0, 'review': 0, 'written': 0, 'errors': errors, 'by_category': {}}

    # --- 3. 加载现有索引用作去重 ---
    print(f"\n[去重] 加载现有索引: {recipe_index_path}")
    index_by_category = load_index_by_category(recipe_index_path)
    total_existing = sum(len(v) for v in index_by_category.values())
    print(f"  现有菜谱: {total_existing} 道，{len(index_by_category)} 个品类")

    # --- 4. 去重 ---
    accepted, skipped, review = batch_deduplicate(normalized, index_by_category)

    print(f"  接受: {len(accepted)}, 跳过(重复): {len(skipped)}, 待审: {len(review)}")

    if review:
        print(f"\n[审核队列] 写入: {review_csv_path}")
        write_review_csv(review, review_csv_path)

    # --- 5. 写入文件 ---
    written = 0
    by_category = {}

    if dry_run:
        print(f"\n[干跑模式] 以下是将被写入的菜谱（未实际写入）:")
        for r in accepted[:20]:
            print(f"  [{r['category']}] {r['title']}  ({r['cooking_method']}, ★{r['difficulty']})")
        if len(accepted) > 20:
            print(f"  ... 以及其他 {len(accepted) - 20} 道")
    else:
        print(f"\n[写入] 开始写入 {len(accepted)} 道菜谱...")
        for r in accepted:
            category = r['category']
            category_dir = Path(output_dir) / category
            category_dir.mkdir(parents=True, exist_ok=True)

            filename = safe_filename(r['title']) + '.md'
            filepath = category_dir / filename

            # 如果文件已存在，加序号
            if filepath.exists():
                stem = safe_filename(r['title'])
                counter = 2
                while (category_dir / f"{stem}_{counter}.md").exists():
                    counter += 1
                filepath = category_dir / f"{stem}_{counter}.md"

            content = make_full_md(r)
            with open(filepath, 'w', encoding='utf-8') as f:
                f.write(content)

            written += 1
            by_category[category] = by_category.get(category, 0) + 1

        print(f"  已写入: {written} 个文件")
        print(f"  品类分布: {dict(sorted(by_category.items()))}")

    # --- 6. 摘要 ---
    print(f"\n{'='*60}")
    print(f"导入完成摘要")
    print(f"{'='*60}")
    print(f"  原始记录:     {len(raw_recipes)}")
    print(f"  规范化成功:   {len(normalized)}")
    print(f"  规范化失败:   {errors}")
    print(f"  接受(新菜谱): {len(accepted)}")
    print(f"  跳过(重复):   {len(skipped)}")
    print(f"  待人工审核:   {len(review)}")
    if dry_run:
        print(f"  → 干跑模式，未写入任何文件")
    else:
        print(f"  实际写入:     {written}")
    print(f"{'='*60}\n")

    return {
        'total_raw': len(raw_recipes),
        'normalized': len(normalized),
        'accepted': len(accepted),
        'skipped': len(skipped),
        'review': len(review),
        'written': written,
        'errors': errors,
        'by_category': by_category,
    }


# ========== CLI ==========

def main():
    parser = argparse.ArgumentParser(
        description='多数据源菜谱导入工具',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例:
  python scripts/import_recipes.py -i data/datasets/recipes.json --source recipenlg --dry-run
  python scripts/import_recipes.py -i data/datasets/recipes.csv --source kaggle --max 200
  python scripts/import_recipes.py -i data/normalized/batch1.jsonl --source huggingface --review-only
        """,
    )
    parser.add_argument('-i', '--input', required=True, help='数据集文件路径 (.json/.csv/.jsonl)')
    parser.add_argument('--source', required=True, help='来源标签 (e.g. recipenlg, kaggle, chinese-cooking-5k)')
    parser.add_argument('--dry-run', action='store_true', help='干跑模式，只统计不写入')
    parser.add_argument('--review-only', action='store_true', help='仅做去重分析，不写入文件')
    parser.add_argument('--max', type=int, default=0, help='最大处理数量（0=无限制）')
    parser.add_argument('--output-dir', default=str(RECIPES_DIR), help='输出目录')
    parser.add_argument('--review-csv', default=str(REVIEW_CSV_PATH), help='审核队列 CSV 路径')

    args = parser.parse_args()

    if not Path(args.input).exists():
        print(f"错误: 文件不存在: {args.input}")
        sys.exit(1)

    result = import_dataset(
        filepath=args.input,
        source=args.source,
        output_dir=args.output_dir,
        dry_run=args.dry_run or args.review_only,
        max_recipes=args.max,
        review_csv_path=args.review_csv,
    )

    if result['accepted'] > 0 and not args.dry_run:
        print("提示: 请运行 'python scripts/build_index.py' 更新索引。")


if __name__ == '__main__':
    main()
