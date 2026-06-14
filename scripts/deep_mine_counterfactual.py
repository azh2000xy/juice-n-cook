#!/usr/bin/env python3
"""
深度挖掘 Counterfactual Recipe 数据集。
处理全部 2,500 条变体（而非仅 50 道唯一菜名），改进食材提取。
"""

import json
import os
import re
import sys
from collections import Counter

import requests
import yaml

sys.stdout.reconfigure(encoding='utf-8')

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ING_INDEX = os.path.join(ROOT, '.claude', 'skills', 'juice-n-cook', 'references', 'ingredients_index.yaml')

# --- 1. 下载源数据 ---
print("[1/4] Downloading source data...")
resp = requests.get(
    'https://raw.githubusercontent.com/xxxiaol/counterfactual-recipe-generation/main/data/base_recipes.txt',
    timeout=60
)
lines = [l.strip() for l in resp.text.strip().split('\n') if l.strip()]

resp2 = requests.get(
    'https://raw.githubusercontent.com/xxxiaol/counterfactual-recipe-generation/main/data/dish_pairs.txt',
    timeout=30
)
pairs = [l.strip().split() for l in resp2.text.strip().split('\n') if l.strip()]

resp3 = requests.get(
    'https://raw.githubusercontent.com/xxxiaol/counterfactual-recipe-generation/main/data/changing_ingres.txt',
    timeout=30
)
raw_ing_pairs = [l.strip().split() for l in resp3.text.strip().split('\n') if l.strip()]
ing_pairs = [p for p in raw_ing_pairs if len(p) == 2]
pairs = [p for p in pairs if len(p) == 2]

# Build dish -> key ingredient mapping
dish_key_ingredient = {}
for pair_entry, ing_entry in zip(pairs, ing_pairs):
    orig_dish, mod_dish = pair_entry
    orig_ing, mod_ing = ing_entry
    dish_key_ingredient[orig_dish] = orig_ing
    dish_key_ingredient[mod_dish] = mod_ing

print(f"  base_recipes.txt: {len(lines)} lines")
print(f"  dish_pairs: {len(pairs)}, changing_ingres: {len(ing_pairs)}")
print(f"  dish->ingredient mappings: {len(dish_key_ingredient)}")

# --- 2. 构建食材词库 ---
print("[2/4] Building ingredient lexicon...")
with open(ING_INDEX, 'r', encoding='utf-8') as f:
    ing_data = yaml.safe_load(f)

known_ings = set()
for item in ing_data.get('ingredients', []):
    known_ings.add(item['name'])
    for alias in item.get('aliases', []):
        known_ings.add(alias)

# 补充常见中式烹饪食材（我们的食材索引偏果汁方向）
COMMON_CN_INGREDIENTS = [
    '盐', '糖', '白糖', '冰糖', '红糖', '酱油', '生抽', '老抽', '蚝油', '醋',
    '陈醋', '白醋', '香醋', '料酒', '黄酒', '啤酒', '白酒',
    '淀粉', '玉米淀粉', '土豆淀粉', '生粉',
    '花椒', '花椒粉', '干辣椒', '小米辣', '辣椒面', '辣椒粉',
    '豆瓣酱', '甜面酱', '番茄酱', '辣椒油', '芝麻油', '香油',
    '八角', '桂皮', '香叶', '草果', '丁香', '陈皮', '孜然', '孜然粉',
    '五香粉', '十三香', '白胡椒粉', '黑胡椒粉', '胡椒粉',
    '味精', '鸡精', '鸡粉', '浓汤宝',
    '食用油', '色拉油', '花生油', '菜籽油', '橄榄油', '猪油', '黄油',
    '葱', '姜', '蒜', '香菜', '葱花', '姜丝', '姜片', '蒜末', '蒜蓉',
    '鸡蛋', '鸭蛋', '鹌鹑蛋', '皮蛋',
    '豆腐', '嫩豆腐', '老豆腐', '豆皮', '豆干', '腐竹',
    '粉丝', '粉条', '面条', '方便面',
    '土豆', '马铃薯', '茄子', '豆角', '四季豆', '豇豆',
    '萝卜', '白萝卜', '胡萝卜', '红萝卜',
    '白菜', '大白菜', '小白菜', '娃娃菜',
    '番茄', '西红柿', '黄瓜', '冬瓜', '苦瓜', '丝瓜', '南瓜',
    '韭菜', '韭黄', '菠菜', '西兰花', '菜花', '花菜',
    '莲藕', '藕', '山药', '豆芽', '绿豆芽', '黄豆芽',
    '洋葱', '芹菜', '西芹', '生菜', '油菜', '上海青',
    '茭白', '芦笋', '海带', '木耳', '银耳', '香菇', '金针菇', '平菇', '杏鲍菇',
    '猪肉', '猪瘦肉', '五花肉', '里脊肉', '排骨', '猪蹄', '猪脚', '猪肝', '猪肚',
    '鸡肉', '鸡胸肉', '鸡腿', '鸡翅', '鸡爪', '鸡杂', '鸡胗', '鸡心',
    '牛肉', '牛腩', '牛腱', '牛柳', '羊肉', '羊排',
    '鸭肉', '鸭腿', '烤鸭',
    '鱼肉', '鱼', '虾', '虾仁', '蟹', '鱿鱼', '花蛤', '花甲', '扇贝', '蛤蜊',
    '年糕', '米饭', '馒头', '饺子', '馄饨', '米粉', '米线', '河粉',
    '面包', '吐司', '面粉', '糯米', '大米', '小米', '紫米',
    '生抽', '老抽', '蒸鱼豉油', '鱼露', '味极鲜',
    '豆豉', '腐乳', '榨菜', '酸菜', '泡菜', '雪菜',
    '椰奶', '牛奶', '淡奶油', '奶酪', '黄油', '芝士', '马斯卡彭',
    '柠檬', '橙子', '苹果', '香蕉', '草莓', '蓝莓',
    '枸杞', '红枣', '桂圆', '莲子', '百合', '银耳', '燕窝',
    '辣椒', '青椒', '红椒', '甜椒', '彩椒', '尖椒',
    '蒜苗', '蒜苔', '大葱', '小葱', '香葱', '生姜', '老姜',
]
known_ings.update(COMMON_CN_INGREDIENTS)

# 清洗单字通用词（太容易误匹配）
for word in ['油', '水', '米', '面', '肉', '鱼', '虾', '蟹', '鸡', '鸭', '牛', '羊', '猪',
             '盐', '糖', '酱', '醋', '酒', '茶', '奶', '蛋', '豆', '菜', '瓜', '果',
             '葱', '姜', '蒜', '椒', '辣', '粉', '汁', '汤', '饭', '粥', '饼']:
    known_ings.discard(word)

print(f"  Known ingredients: {len(known_ings)}")

# 工具/动作词（用于过滤误提取）
FILTER_WORDS = {
    '锅', '刀', '碗', '盘', '勺', '铲', '砧板', '烤箱', '微波炉', '蒸锅',
    '炒锅', '汤锅', '平底锅', '高压锅', '砂锅', '空气炸锅', '冰箱', '保鲜膜',
    '厨房纸', '筷子', '蒸架', '菜板', '保鲜袋',
    '倒入', '放入', '加入', '翻炒', '搅拌', '煮开', '烧开', '切好', '洗净',
    '备用', '捞出', '关火', '开火', '出锅', '装盘', '热锅', '起锅', '下锅',
    '大火', '小火', '中火', '转小火', '转中火', '盛出', '取出', '沥干',
    '几分钟', '半小时', '一小时', '十分钟', '五分钟',
}


def extract_ingredients(text):
    """从自由文本中提取食材"""
    found = set()

    # 1. 直接匹配已知食材
    for ing in known_ings:
        if len(ing) >= 2 and ing in text:
            found.add(ing)

    # 2. 量词+食材模式
    measure_re = re.compile(
        r'(?:[一两二三四五六七八九十半]+|[少许适量若干])\s*'
        r'(?:勺|匙|个|根|只|条|块|段|瓣|颗|杯|碗|把|盒|袋|片|滴|克|斤|两|汤匙|茶匙|大勺|小勺|汤勺)\s*'
        r'([一-鿿]{2,6})'
    )
    for m in measure_re.findall(text):
        found.add(m)

    # 3. 食材+量词模式（反向）
    reverse_measure_re = re.compile(
        r'([一-鿿]{2,4})(?:适量|少许|若干|一把|几个|几片|几根|几块|几段|数片)'
    )
    for m in reverse_measure_re.findall(text):
        found.add(m)

    # 4. 清洗
    cleaned = set()
    for ing in found:
        if ing in FILTER_WORDS:
            continue
        # 过滤纯数字/符号
        if re.match(r'^[\d\s\.\,\;\:\!\?\[\]\(\)\{\}％％％]+$', ing):
            continue
        # 过滤太短或太长
        if len(ing) < 2 or len(ing) > 10:
            continue
        # 过滤以动词结尾的（如"洗干净""切好"）
        if re.search(r'(干净|好|完|熟|透|软|烂|开|起|下|出|入)$', ing):
            continue
        cleaned.add(ing)

    return sorted(cleaned)


def extract_steps(text):
    """从自由文本中拆分步骤"""
    # 尝试查找数字编号的步骤
    numbered = re.findall(r'(?:^|[。！；])\s*(\d+[\.、\s)）]\s*.+?)(?=[。！；]|\Z)', text)
    if len(numbered) >= 2:
        steps = [re.sub(r'^\d+[\.、\s)）]\s*', '', s).strip() for s in numbered]
        steps = [s for s in steps if len(s) >= 5]
        if len(steps) >= 2:
            return steps

    # 回退：按句号分句
    raw_steps = re.split(r'[。！；]', text)
    steps = [s.strip() for s in raw_steps if len(s.strip()) >= 5]
    # 过滤明显不是步骤的行
    steps = [s for s in steps if not re.match(r'^[仅只]供参考', s)]
    return steps


# --- 3. 提取所有变体 ---
print("[3/4] Extracting recipes from all variants...")
recipes = []
seen_keys = set()  # (title, text_fingerprint) 内部去重

for i, line in enumerate(lines):
    parts = line.split('\t')
    if len(parts) < 3:
        continue

    base_name = parts[0].strip()
    variant_name = parts[1].strip()
    recipe_text = parts[2].strip()

    if len(recipe_text) < 30:
        continue

    # 使用变体菜名（更有趣的替代食材版本）
    title = variant_name

    # 内部去重：title + 文本前80字指纹
    fp = recipe_text[:80]
    key = (title, fp)
    if key in seen_keys:
        continue
    seen_keys.add(key)

    # 从 dish_pairs 获取关键替代食材
    key_ing = dish_key_ingredient.get(variant_name, '')

    # 提取食材和步骤
    ingredients = extract_ingredients(recipe_text)
    if key_ing and key_ing not in ingredients:
        ingredients.insert(0, key_ing)

    steps = extract_steps(recipe_text)

    if not ingredients:
        continue
    if not steps:
        steps = [recipe_text]

    recipes.append({
        'title': title,
        'raw_ingredients': ingredients,
        'raw_steps': steps,
    })

print(f"  Total variants: {len(lines)}")
print(f"  After dedup: {len(recipes)}")
print(f"  Removed: {len(lines) - len(recipes)}")

# --- 4. 统计并保存 ---
print("[4/4] Statistics and save...")

# 快速品类估算
cat_counter = Counter()
for r in recipes:
    t = r['title']
    if any(kw in t for kw in ['鱼', '虾', '蟹', '贝', '鱿', '蛤', '海', '螺', '蛏', '鳝']):
        cat_counter['aquatic'] += 1
    elif any(kw in t for kw in ['蛋糕', '面包', '甜品', '布丁', '派', '酥', '饼干']):
        cat_counter['dessert'] += 1
    elif '汤' in t or '羹' in t:
        cat_counter['soup'] += 1
    elif any(kw in t for kw in ['饭', '面', '粥', '饼', '年糕', '粉', '米线', '河粉', '馒头', '包子', '饺子']):
        cat_counter['staple'] += 1
    elif any(kw in t for kw in ['鸡', '鸭', '鹅', '牛', '羊', '猪', '肉', '排骨', '蹄', '腿', '肝', '肚', '肠']):
        cat_counter['meat_dish'] += 1
    elif any(kw in t for kw in ['菜', '豆', '瓜', '菇', '菌', '茄', '椒', '藕', '笋', '芹', '菠', '韭']):
        cat_counter['vegetable_dish'] += 1
    elif any(kw in t for kw in ['蛋', '奶', '早餐', '吐司']):
        cat_counter['breakfast'] += 1
    elif any(kw in t for kw in ['酱', '汁', '卤', '蘸']):
        cat_counter['condiment'] += 1
    else:
        cat_counter['other'] += 1

print(f"\n  Estimated categories:")
for cat, cnt in cat_counter.most_common():
    print(f"    {cat}: {cnt}")

# 食材覆盖
all_ings = set()
for r in recipes:
    all_ings.update(r['raw_ingredients'])
print(f"\n  Unique ingredients: {len(all_ings)}")

# 保存
outdir = os.path.join(ROOT, 'data', 'datasets')
os.makedirs(outdir, exist_ok=True)
outpath = os.path.join(outdir, 'chinese_recipes_deep.json')
with open(outpath, 'w', encoding='utf-8') as f:
    json.dump(recipes, f, ensure_ascii=False, indent=2)

fsize = os.path.getsize(outpath)
print(f"\n  Saved: {outpath}")
print(f"  File size: {fsize/1024:.0f}KB")
print(f"  Recipes: {len(recipes)}")

# 显示一些样例
print(f"\n  Sample recipes:")
for r in recipes[:5]:
    print(f"    [{r['title']}] ings={len(r['raw_ingredients'])} steps={len(r['raw_steps'])}")
    print(f"      ings: {', '.join(r['raw_ingredients'][:8])}")
