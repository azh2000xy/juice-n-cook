#!/usr/bin/env python3
"""
分类优先的菜谱去重模块。

核心思路：先确定新菜谱的品类，仅与同品类的现有菜谱比对，
而非全量 461 道。这消除了跨品类误判，并将比对效率提升 10-50 倍。

比对方法：
  - 标题模糊匹配（rapidfuzz token_sort_ratio）
  - 食材 Jaccard 相似度
  - 加权综合评分
"""

import csv
from pathlib import Path
from typing import Optional

import yaml
from rapidfuzz import fuzz


# ========== 配置 ==========

# 综合评分权重
TITLE_WEIGHT = 0.6
INGREDIENT_WEIGHT = 0.4

# 判定阈值
STRONG_DUPLICATE = 0.85   # ≥ 自动跳过
POSSIBLE_DUPLICATE = 0.65  # ≥ 且 < STRONG → 人工审核
# < POSSIBLE → 自动接受


# ========== 标题规范化 ==========

def normalize_title(title: str) -> str:
    """
    规范化标题用于比较。
    - 去掉"的做法""的家常做法"等后缀
    - 全角转半角
    - 去掉括号内容（如 "(家常版)"）
    - 统一空格
    """
    import re
    t = title.strip()
    t = re.sub(r'的?(做法|家常做法|简易做法|正宗做法)$', '', t)
    t = re.sub(r'[（(][^）)]*[）)]', '', t)  # 去掉括号内容
    t = re.sub(r'【[^】]*】', '', t)
    # 全角转半角（常见情况）
    t = t.replace('０', '0').replace('１', '1').replace('２', '2')
    t = t.replace('３', '3').replace('４', '4').replace('５', '5')
    t = t.replace('６', '6').replace('７', '7').replace('８', '8').replace('９', '9')
    t = re.sub(r'\s+', '', t)  # 去掉所有空白
    return t


# ========== 索引加载 ==========

def load_index_by_category(index_path: str | Path) -> dict[str, list[dict]]:
    """
    从 recipe_index.yaml 加载现有菜谱，按品类分组。

    返回格式:
      {
        'meat_dish': [
          {'title': '红烧肉', 'ingredients': ['猪肉', '酱油', ...]},
          ...
        ],
        'aquatic': [...],
        ...
      }
    """
    with open(index_path, 'r', encoding='utf-8') as f:
        data = yaml.safe_load(f)

    by_category: dict[str, list[dict]] = {}

    for recipe in data.get('recipes', []):
        cat = recipe.get('category', 'other')
        entry = {
            'title': recipe.get('title', ''),
            'ingredients': set(recipe.get('ingredients', [])),
        }
        by_category.setdefault(cat, []).append(entry)

    return by_category


# ========== 相似度计算 ==========

def title_similarity(title1: str, title2: str) -> float:
    """
    计算两个菜谱标题的相似度 [0.0, 1.0]。
    使用 rapidfuzz token_sort_ratio（对词序不敏感）。
    """
    t1 = normalize_title(title1)
    t2 = normalize_title(title2)
    if not t1 or not t2:
        return 0.0
    return fuzz.token_sort_ratio(t1, t2) / 100.0


def ingredient_jaccard(ingredients1: list[str] | set[str],
                       ingredients2: list[str] | set[str]) -> float:
    """
    计算两个食材集合的 Jaccard 相似度。
    """
    s1 = set(ingredients1) if isinstance(ingredients1, list) else ingredients1
    s2 = set(ingredients2) if isinstance(ingredients2, list) else ingredients2

    if not s1 or not s2:
        return 0.0

    intersection = len(s1 & s2)
    union = len(s1 | s2)
    return intersection / union if union > 0 else 0.0


def combined_score(title1: str, ingredients1: list[str],
                   title2: str, ingredients2: list[str] | set[str]) -> float:
    """加权综合评分"""
    ts = title_similarity(title1, title2)
    js = ingredient_jaccard(ingredients1, ingredients2)
    return TITLE_WEIGHT * ts + INGREDIENT_WEIGHT * js


# ========== 去重判定 ==========

def deduplicate_candidate(
    title: str,
    ingredients: list[str],
    category: str,
    index_by_category: dict[str, list[dict]],
) -> tuple[str, float, Optional[str]]:
    """
    对一条新菜谱候选进行去重判定。

    参数:
      title: 新菜谱标题
      ingredients: 新菜谱食材列表
      category: 新菜谱的自动分类结果
      index_by_category: 按品类分组的现有索引

    返回:
      (verdict, score, matched_title)
      verdict: 'skip' | 'review' | 'accept'
      score: 与最佳匹配的综合评分
      matched_title: 最佳匹配的现有菜谱标题（如无则为 None）
    """
    # 仅与该品类的现有菜谱比对
    existing = index_by_category.get(category, [])

    if not existing:
        # 该品类无现有菜谱，直接接受
        return ('accept', 0.0, None)

    best_score = 0.0
    best_match = None

    for entry in existing:
        score = combined_score(title, ingredients, entry['title'], entry['ingredients'])
        if score > best_score:
            best_score = score
            best_match = entry['title']

    if best_score >= STRONG_DUPLICATE:
        return ('skip', best_score, best_match)
    elif best_score >= POSSIBLE_DUPLICATE:
        return ('review', best_score, best_match)
    else:
        return ('accept', best_score, best_match)


# ========== 批量去重 ==========

def batch_deduplicate(
    candidates: list[dict],
    index_by_category: dict[str, list[dict]],
) -> tuple[list[dict], list[dict], list[dict]]:
    """
    批量去重，返回三个列表: (accepted, skipped, review)。

    每个 candidate 需包含: title, ingredients, category
    """
    accepted = []
    skipped = []
    review = []

    for c in candidates:
        verdict, score, matched = deduplicate_candidate(
            c['title'], c['ingredients'], c['category'], index_by_category
        )

        c['dedup_score'] = score
        c['dedup_matched'] = matched

        if verdict == 'accept':
            accepted.append(c)
        elif verdict == 'skip':
            skipped.append(c)
        else:
            review.append(c)

    return accepted, skipped, review


# ========== 审核队列文件 ==========

def write_review_csv(review_items: list[dict], output_path: str | Path):
    """将待审核项写入 CSV 文件"""
    fieldnames = ['title', 'category', 'source', 'dedup_score', 'dedup_matched',
                  'ingredients', 'steps_preview']

    with open(output_path, 'w', newline='', encoding='utf-8-sig') as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        for item in review_items:
            writer.writerow({
                'title': item.get('title', ''),
                'category': item.get('category', ''),
                'source': item.get('source', ''),
                'dedup_score': f"{item.get('dedup_score', 0):.3f}",
                'dedup_matched': item.get('dedup_matched', ''),
                'ingredients': '; '.join(item.get('ingredients', [])[:10]),
                'steps_preview': '; '.join(item.get('steps', [])[:3]),
            })


def read_review_decisions(csv_path: str | Path) -> dict[str, bool]:
    """
    读取人工审核后的 CSV（增加了 'decision' 列）。
    返回 {title: True=接受, False=跳过}。
    """
    decisions = {}
    with open(csv_path, 'r', encoding='utf-8-sig') as f:
        reader = csv.DictReader(f)
        for row in reader:
            decision = row.get('decision', '').strip().lower()
            if decision in ('y', 'yes', 'accept', '1', 'true'):
                decisions[row['title']] = True
            elif decision in ('n', 'no', 'skip', '0', 'false'):
                decisions[row['title']] = False
    return decisions
