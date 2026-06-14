#!/usr/bin/env python3
"""
批量给 HowToCook 菜谱添加 YAML frontmatter，统一格式。

用法: python unify_format.py [--dry-run] [--preview]
  --dry-run  只检查不写入
  --preview  预览前 N 个文件的转换结果
"""

import sys
import re
import yaml
from pathlib import Path

ROOT = Path(__file__).parent.parent
COOKING_DIR = ROOT / "recipes" / "cooking"

# 做法关键词映射
METHOD_KEYWORDS = {
    '炒': '炒', '蒸': '蒸', '煮': '煮', '炖': '炖', '炸': '炸',
    '凉拌': '凉拌', '烤': '烤', '煎': '煎', '焖': '焖', '卤': '卤',
    '拌': '凉拌', '烧': '烧', '煲': '煲', '烩': '烩', '焗': '焗',
}


def extract_title(content: str) -> str:
    """从 # 标题提取菜名，去掉'的做法'后缀"""
    m = re.search(r'^#\s+(.+)', content, re.MULTILINE)
    if m:
        title = m.group(1).strip()
        title = re.sub(r'的做法$', '', title)
        return title
    return ""


def extract_difficulty(content: str) -> int:
    """从 预估烹饪难度：★★★ 提取星数"""
    m = re.search(r'预估烹饪难度[：:]\s*([★☆]+)', content)
    if m:
        return m.group(1).count('★')
    m = re.search(r'烹饪难度[：:]\s*([★☆]+)', content)
    if m:
        return m.group(1).count('★')
    return 3  # default


def extract_cooking_method(content: str, title: str, category: str) -> str:
    """推断烹饪方法：标题 > 正文前部 > 分类名"""
    # 从菜名中找
    for kw, method in METHOD_KEYWORDS.items():
        if kw in title:
            return method
    # 从正文前 500 字符中找
    head = content[:500]
    for kw, method in METHOD_KEYWORDS.items():
        if kw in head:
            return method
    # 从分类名推断
    cat_methods = {
        'meat_dish': '炒', 'vegetable_dish': '炒',
        'soup': '煮', 'staple': '煮',
        'aquatic': '蒸', 'breakfast': '煮',
        'dessert': '烤', 'drink': '调',
    }
    return cat_methods.get(category, '通用')


def extract_ingredients(content: str) -> list:
    """从 ## 必备原料和工具 提取食材名"""
    ingredients = []
    in_section = False
    for line in content.split('\n'):
        if re.match(r'^##\s+必备原料和工具', line):
            in_section = True
            continue
        if in_section:
            if line.startswith('## '):
                break
            m = re.match(r'^[-*]\s+(.+)', line)
            if not m:
                continue
            item = m.group(1).strip()

            # 过滤掉纯工具/设备行
            if re.search(r'锅|刀|碗|盘|勺|铲|砧板|烤箱|微波炉|蒸锅|炒锅|汤锅|平底锅|高压锅|砂锅|空气炸锅|冰箱|保鲜膜|厨房纸', item):
                continue
            # 过滤纯数字/英文混杂的行（通常是 OCR 乱码或误识别）
            if re.match(r'^[\d\s\.\,a-zA-Z\-\+]+$', item):
                continue

            # 提取食材名：取第一个中文词段
            # 策略：按常见分隔符切分，取第一段有意义的中文
            name = re.split(
                r'\s+\d|[（(]|[=＝]|[：:]|\d+\s*(g|ml|kg|个|根|只|条|勺|大勺|小勺|茶匙|汤匙|片|段|块|颗|杯|把|盒|袋)',
                item
            )[0].strip()
            name = name.rstrip(' ，。,，.、:：')
            # 去掉"拇指大小的""灯笼椒大小的"等修饰
            name = re.sub(r'^(拇指大小的|灯笼椒大小的|拳头大小的|鸡蛋大小的)', '', name)

            if name and len(name) >= 1 and len(name) <= 15:
                ingredients.append(name)

    # 去重，保持顺序
    seen = set()
    unique = []
    for ing in ingredients:
        if ing not in seen:
            seen.add(ing)
            unique.append(ing)
    return unique


def extract_tags(content: str, title: str, ingredients: list, category: str) -> list:
    """生成标签"""
    tags = []
    # 从分类映射标签
    cat_tags = {
        'meat_dish': '荤菜', 'vegetable_dish': '素菜',
        'soup': '汤羹', 'staple': '主食',
        'aquatic': '水产', 'breakfast': '早餐',
        'dessert': '甜品', 'drink': '饮品',
        'condiment': '调料', 'semi-finished': '半成品',
    }
    if category in cat_tags:
        tags.append(cat_tags[category])
    # 从菜名取前几个食材做标签
    for ing in ingredients[:3]:
        if ing not in tags:
            tags.append(ing)
    return tags[:8]  # 不超过 8 个标签


def extract_category(filepath: str) -> str:
    """获取第一级分类目录名（cooking/ 下的直接子目录）"""
    path = Path(filepath)
    parts = path.parts
    # 找到 'cooking' 在路径中的位置，取下一级
    if 'cooking' in parts:
        idx = parts.index('cooking')
        if idx + 1 < len(parts):
            return parts[idx + 1]
    return path.parent.name


def generate_frontmatter(content: str, filepath: str) -> dict:
    """从纯 Markdown 提取所有元数据"""
    title = extract_title(content)
    category = extract_category(filepath)
    difficulty = extract_difficulty(content)
    cooking_method = extract_cooking_method(content, title, category)
    ingredients = extract_ingredients(content)
    tags = extract_tags(content, title, ingredients, category)

    return {
        'title': title,
        'category': category,
        'cooking_method': cooking_method,
        'difficulty': difficulty,
        'tags': tags,
        'ingredients': ingredients,
        'source': 'howtocook',
    }


def apply_frontmatter(filepath: Path, dry_run: bool = False) -> dict:
    """给单个文件添加 YAML frontmatter，返回元数据"""
    with open(filepath, 'r', encoding='utf-8') as f:
        content = f.read()

    # 如果已有 frontmatter 则跳过
    if content.startswith('---'):
        return {'skipped': True, 'reason': 'already has frontmatter'}

    fm = generate_frontmatter(content, str(filepath))

    if not fm['title']:
        return {'skipped': True, 'reason': 'no title found'}

    # 生成 YAML frontmatter 字符串
    yaml_str = yaml.dump(fm, allow_unicode=True, default_flow_style=False, sort_keys=False).strip()
    new_content = f"---\n{yaml_str}\n---\n\n{content}"

    if not dry_run:
        with open(filepath, 'w', encoding='utf-8') as f:
            f.write(new_content)

    return {
        'skipped': False,
        'title': fm['title'],
        'category': fm['category'],
        'method': fm['cooking_method'],
        'difficulty': fm['difficulty'],
        'ing_count': len(fm['ingredients']),
    }


def main():
    dry_run = '--dry-run' in sys.argv
    preview = '--preview' in sys.argv

    files = sorted(COOKING_DIR.rglob("*.md"))
    print(f"Found {len(files)} cooking recipe files\n")

    if preview:
        n = int(sys.argv[sys.argv.index('--preview') + 1]) if '--preview' in sys.argv and sys.argv.index('--preview') + 1 < len(sys.argv) else 5
        files = files[:n]

    success = 0
    skipped = 0
    errors = 0

    for f in files:
        try:
            result = apply_frontmatter(f, dry_run=dry_run)
            if result.get('skipped'):
                skipped += 1
            else:
                success += 1
                if preview or success % 50 == 0:
                    print(f"  [{result['category']}] {result['title']} "
                          f"| {result['method']} | ★{result['difficulty']} "
                          f"| {result['ing_count']} 食材")
        except Exception as e:
            errors += 1
            print(f"  ERROR: {f.name} - {e}")

    print(f"\n{'[DRY RUN] ' if dry_run else ''}"
          f"Success: {success}, Skipped: {skipped}, Errors: {errors}")

    if dry_run:
        print("Run without --dry-run to apply changes.")


if __name__ == "__main__":
    main()
