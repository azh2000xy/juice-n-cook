#!/usr/bin/env python3
"""
将外部数据集的原始菜谱字段映射为项目的 YAML frontmatter + Markdown 格式。

复用 unify_format.py 中的 METHOD_KEYWORDS 和分类逻辑，扩展了自动分类规则。
"""

import re
from typing import Optional

# ========== 常量 ==========

# 10 个品类及其触发关键词（用于自动分类）
# 按优先级排列：先匹配的品类优先
# 注意 condiment 的"酱"会错误匹配到酱油，因此使用更精确的关键词并降低优先级
CATEGORY_RULES: list[tuple[str, list[str]]] = [
    ('drink',     ['果汁', '饮料', '奶昔', '冰沙', '茶饮', '奶茶', '咖啡', '气泡水', '柠檬水']),
    ('dessert',   ['蛋糕', '面包', '甜品', '糖水', '布丁', '冰淇淋', '月饼', '糕点',
                   '饼干', '蛋挞', '提拉米苏', '慕斯', '冰棍', '雪糕', '派', '酥']),
    ('aquatic',   ['鱼', '虾', '蟹', '贝', '海鲜', '鲍鱼', '海参', '龙虾', '鱿鱼',
                   '扇贝', '蛤蜊', '蛏', '鳝', '鲈', '鲫', '鲤', '鳊', '带鱼', '生蚝']),
    ('soup',      ['汤', '羹']),
    ('staple',    ['饭', '面', '面条', '粥', '饼', '馒头', '包子', '饺子', '馄饨',
                   '米粉', '米线', '河粉', '炒饭', '盖饭', '焖饭', '炒面', '拌面',
                   '烧饼', '馅饼', '锅贴', '花卷', '烧麦', '粽']),
    ('breakfast', ['早餐', '早茶', '豆浆', '油条', '荷包蛋', '水煮蛋', '茶叶蛋',
                   '煎饼果子', '肠粉']),
    ('semi-finished', ['面团', '馅料', '酥皮', '塔皮', '预拌', '面糊']),
    ('vegetable_dish', ['青菜', '蔬菜', '素菜', '豆腐', '菌菇', '凉拌菜', '沙拉',
                        '土豆', '茄子', '豆角', '萝卜', '白菜', '番茄', '西红柿',
                        '黄瓜', '冬瓜', '苦瓜', '丝瓜', '南瓜', '韭菜', '菠菜',
                        '西兰花', '菜花', '莲藕', '山药', '豆芽', '洋葱', '芹菜',
                        '生菜', '油菜', '茭白', '芦笋', '海带', '木耳']),
    ('condiment', ['油泼辣子', '辣椒油', '沙拉酱', '糖色', '卤水', '腌料', '泡菜水',
                   '酱料', '蘸料', '调味汁', '蛋黄酱', '番茄酱', '甜面酱', '豆瓣酱',
                   '炸串酱', '蒜蓉酱', '花生酱', '芝麻酱', '果酱']),
    ('meat_dish', ['肉', '排骨', '鸡', '鸭', '牛', '羊', '猪', '腊肉', '火腿',
                   '红烧肉', '回锅肉', '宫保', '鱼香']),
]
# 注意：
#   - meat_dish 是默认兜底，所以放最后
#   - condiment 使用精确关键词（如"辣椒油"而非"酱"），避免酱油/蚝油等通用调料误匹配
#   - aquatic 提前（"鱼"比"酱"更独特，不应被 condiment 抢走）
#   - vegetable_dish 扩充了常见蔬菜名称

# 做法关键词映射（来自 unify_format.py，扩展）
METHOD_KEYWORDS: dict[str, str] = {
    '炒': '炒', '蒸': '蒸', '煮': '煮', '炖': '炖', '炸': '炸',
    '凉拌': '凉拌', '烤': '烤', '煎': '煎', '焖': '焖', '卤': '卤',
    '拌': '凉拌', '烧': '烧', '煲': '煲', '烩': '烩', '焗': '焗',
    '调': '调', '泡': '调', '腌': '调',
}

# 品类的默认做法
CATEGORY_DEFAULT_METHOD: dict[str, str] = {
    'meat_dish': '炒', 'vegetable_dish': '炒', 'soup': '煮',
    'staple': '煮', 'aquatic': '蒸', 'breakfast': '煮',
    'dessert': '烤', 'drink': '调', 'condiment': '调',
    'semi-finished': '调',
}

# 品类 → 中文标签（用于 tags 第一个元素）
CATEGORY_TAG: dict[str, str] = {
    'meat_dish': '荤菜', 'vegetable_dish': '素菜', 'soup': '汤羹',
    'staple': '主食', 'aquatic': '水产', 'breakfast': '早餐',
    'dessert': '甜品', 'drink': '饮品', 'condiment': '调料',
    'semi-finished': '半成品',
}

# 合法品类集合
VALID_CATEGORIES = set(CATEGORY_RULES[idx][0] for idx in range(len(CATEGORY_RULES)))


# ========== 自动分类 ==========

def auto_classify(title: str, ingredients: list[str], steps_text: str = "") -> str:
    """
    基于菜名 + 食材 + 步骤文本中的关键词推断 category。
    返回品类名（如 'meat_dish', 'aquatic' 等）。

    策略：
      1. 强标题信号优先（title 中包含特定关键词 → 直接判定）
      2. 关键词匹配计分（按 CATEGORY_RULES 优先级）
      3. 全部未命中返回 'meat_dish'（默认兜底）
    """
    # === 第 1 层：标题强信号 ===
    # 标题中的关键词权重最高，几乎确定品类

    # 肉类强信号（含"鸡/鸭/牛/猪/羊/肉"等但非水产）——需在水产检测前
    # 注意：这些关键词可能也出现在水产菜名中（如"鱼香肉丝"），所以放在水产后面检测
    # 实际上肉类检测应在食材层级，标题级别只检测明确信号

    # 水产强信号：标题含"鱼/虾/蟹/贝/蛤/鱿"等 → 水产
    aquatic_title_kw = ['鱼', '虾', '蟹', '贝', '鲍鱼', '海参', '龙虾', '鱿鱼',
                        '扇贝', '蛤蜊', '蛤', '蛏', '鳝', '鲈', '鲫', '鲤', '鳊',
                        '带鱼', '生蚝', '花蛤', '花甲', '海螺']
    if any(kw in title for kw in aquatic_title_kw):
        return 'aquatic'

    # 甜品强信号
    dessert_title_kw = ['蛋糕', '面包', '甜品', '糖水', '布丁', '冰淇淋', '蛋挞', '饼干',
                        '提拉米苏', '慕斯', '派', '酥', '月饼', '糕点', '冰棍', '雪糕',
                        '拔丝', '冰糖雪梨', '银耳', '双皮奶', '杨枝甘露']
    if any(kw in title for kw in dessert_title_kw):
        return 'dessert'

    # 汤羹强信号
    if '汤' in title or '羹' in title:
        return 'soup'

    # 饮品强信号
    drink_title_kw = ['果汁', '奶昔', '冰沙', '奶茶', '咖啡', '饮料', '茶饮', '气泡水',
                      '柠檬水', '酸梅汤']
    if any(kw in title for kw in drink_title_kw):
        return 'drink'

    # 主食强信号
    staple_title_kw = ['饭', '面', '粥', '饼', '馒头', '包子', '饺子', '馄饨',
                       '米粉', '米线', '河粉', '锅贴', '花卷', '烧麦', '粽',
                       '焖面', '炒面', '拌面', '炒饭', '盖饭']
    if any(kw in title for kw in staple_title_kw):
        return 'staple'

    # 调料强信号
    condiment_title_kw = ['油泼辣子', '辣椒油', '沙拉酱', '卤水', '腌料', '泡菜水',
                          '酱料', '蘸料', '糖色', '调味汁', '番茄酱', '甜面酱', '豆瓣酱']
    if any(kw in title for kw in condiment_title_kw):
        return 'condiment'

    # 肉类强信号（仅限标题明确含肉/鸡/鸭/牛/羊等字眼的）
    meat_title_kw = ['红烧肉', '回锅肉', '宫保鸡丁', '鱼香肉丝', '糖醋排骨',
                     '炖鸡', '烧鸡', '烤鸡', '炸鸡', '辣子鸡', '白切鸡', '盐焗鸡',
                     '炖牛肉', '烧牛肉', '卤牛肉', '烤羊', '炖羊', '烤鸭', '烧鹅',
                     '红烧排骨', '粉蒸肉', '扣肉', '腊肉', '酱牛肉', '羊肉串',
                     '鸡丁', '肉丁', '鸡翅', '鸡爪', '鸡腿', '牛肉', '羊肉',
                     '牛腩', '排骨', '猪蹄', '猪脚', '五花肉', '里脊', '肘子']
    if any(kw in title for kw in meat_title_kw):
        return 'meat_dish'

    # 蔬菜强信号（仅限标题以蔬菜+做法组合的）
    veg_title_kw = ['炒白菜', '炒青菜', '炒豆芽', '炒土豆', '炒茄子', '炒豆角',
                    '炒豆腐', '煮豆腐', '炖豆腐', '拌豆腐', '烧茄子',
                    '白灼菜心', '白灼生菜', '蚝油生菜', '蒜蓉西兰花',
                    '清炒', '素炒', '蒜蓉', '凉拌黄瓜', '凉拌木耳']
    if any(kw in title for kw in veg_title_kw):
        return 'vegetable_dish'

    # === 第 2 层：食材 + 步骤关键词计分 ===
    # 拼接所有可搜索文本
    text = f"{title} {' '.join(ingredients)} {steps_text}"

    scores: dict[str, int] = {}
    for category, keywords in CATEGORY_RULES:
        score = sum(1 for kw in keywords if kw in text)
        scores[category] = score

    # 选最高分，平局取先出现的
    best = max(scores, key=lambda c: (scores[c], -list(scores.keys()).index(c)))

    if scores[best] == 0:
        return 'meat_dish'  # 无关键词命中，默认荤菜

    return best


def auto_method(title: str, steps_text: str = "") -> str:
    """
    从菜名和步骤文本中推断 cooking_method。
    优先匹配菜名 → 步骤前 500 字符 → 默认按品类。
    """
    # 从菜名中找
    for kw, method in METHOD_KEYWORDS.items():
        if kw in title:
            return method

    # 从步骤文本中找
    head = steps_text[:500] if steps_text else ""
    for kw, method in METHOD_KEYWORDS.items():
        if kw in head:
            return method

    return '通用'


def auto_difficulty(steps: list[str], ingredient_count: int) -> int:
    """
    启发式推断难度 1-5：
    基于步骤数 + 食材数。
    """
    step_count = len(steps)

    # 综合考虑
    if step_count <= 3 and ingredient_count <= 5:
        return 1
    elif step_count <= 5 and ingredient_count <= 8:
        return 2
    elif step_count <= 8 and ingredient_count <= 12:
        return 3
    elif step_count <= 12:
        return 4
    else:
        return 5


# ========== 食材清洗 ==========

def clean_ingredient(raw: str) -> str:
    """
    将数据集中的食材字符串清洗为纯净食材名。
    去掉数量、单位、括号注释等。

    例: "鸡蛋 2个" → "鸡蛋"
        "生抽（适量）" → "生抽"
        "盐 5g" → "盐"
    """
    if not raw or not isinstance(raw, str):
        return ""

    raw = raw.strip()

    # 过滤纯数字/纯符号
    if re.match(r'^[\d\s\.\,\;\:\!\?\[\]\(\)\{\}]+$', raw):
        return ""

    # 去掉括号内容
    raw = re.sub(r'[（(][^）)]*[）)]', '', raw)

    # 按分隔符取第一段
    name = re.split(
        r'\s+\d|[（(]|[=＝]|[：:]|\d+\s*(g|ml|kg|个|根|只|条|勺|大勺|小勺|茶匙|汤匙|片|段|块|颗|杯|把|盒|袋)',
        raw
    )[0].strip()

    # 去掉尾部标点
    name = name.rstrip(' ，。,，.、:：;；')

    # 去掉描述性前缀
    name = re.sub(r'^(拇指大小的|灯笼椒大小的|拳头大小的|鸡蛋大小的|少许|适量|若干)', '', name)

    # 过滤掉工具词
    if re.search(r'^(锅|刀|碗|盘|勺|铲|砧板|烤箱|微波炉|蒸锅|炒锅|汤锅|平底锅|高压锅|砂锅|空气炸锅|冰箱|保鲜膜|厨房纸)$', name):
        return ""

    if name and len(name) >= 1 and len(name) <= 20:
        return name
    return ""


def clean_ingredients(raw_list: list[str]) -> list[str]:
    """清洗食材列表，去重保持顺序"""
    seen = set()
    result = []
    for item in raw_list:
        name = clean_ingredient(item)
        if name and name not in seen:
            seen.add(name)
            result.append(name)
    return result


# ========== 标签生成 ==========

def generate_tags(title: str, ingredients: list[str], category: str) -> list[str]:
    """
    生成标签列表（最多 8 个）。
    第一个是品类标签，后续是主要食材。
    """
    tags = []
    # 品类标签
    if category in CATEGORY_TAG:
        tags.append(CATEGORY_TAG[category])

    # 从食材中取前几个
    for ing in ingredients[:5]:
        if ing not in tags:
            tags.append(ing)

    # 从菜名中提取关键食材
    common_ing = ['鸡', '鸭', '鱼', '虾', '蟹', '牛', '羊', '猪', '豆腐', '蛋',
                  '土豆', '番茄', '茄子', '豆角', '白菜', '萝卜', '黄瓜']
    for ing in common_ing:
        if ing in title and ing not in tags:
            tags.append(ing)
            break

    return tags[:8]


# ========== Markdown 正文生成 ==========

def make_recipe_body(
    title: str,
    difficulty: int,
    ingredients: list[str],
    steps: list[str],
    description: str = "",
    tips: list[str] = [],
) -> str:
    """
    生成 Markdown 正文（frontmatter 之下的部分）。
    遵循现有 HowToCook 格式。
    """
    stars = '★' * difficulty + '☆' * (5 - difficulty)
    lines = [
        f"# {title}的做法",
        "",
        description if description else f"{title}是一道家常美味。",
        "",
        f"预估烹饪难度：{stars}",
        "",
        "## 必备原料和工具",
        "",
    ]

    for ing in ingredients:
        lines.append(f"- {ing}")

    lines.extend([
        "",
        "## 操作",
        "",
    ])

    for i, step in enumerate(steps, 1):
        lines.append(f"{i}. {step}")

    if tips:
        lines.extend([
            "",
            "## 附加内容",
            "",
        ])
        for tip in tips:
            lines.append(f"- {tip}")
    else:
        lines.extend([
            "",
            "## 附加内容",
            "",
            "本菜谱来源于公开数据集，经自动化处理整合。如有疑问请参考原始数据源。",
        ])

    return '\n'.join(lines) + '\n'


# ========== 主规范化函数 ==========

def normalize_recipe(raw: dict, source: str) -> Optional[dict]:
    """
    将数据集的一条原始记录映射为项目的规范格式。

    raw 预期字段（各数据集预处理后统一）:
      - title: str
      - raw_ingredients: list[str]  原始食材字符串列表（含数量）
      - raw_steps: list[str]        步骤字符串列表
      - raw_category: Optional[str] 原始分类（如有）
      - description: Optional[str]  简介
      - tips: Optional[list[str]]   小贴士

    返回:
      - title: str
      - category: str
      - cooking_method: str
      - difficulty: int (1-5)
      - tags: list[str]
      - ingredients: list[str]
      - steps: list[str]
      - source: str
      - body_md: str

      若无法处理（无标题/无食材/无步骤）返回 None。
    """
    title = (raw.get('title') or '').strip()
    if not title:
        return None

    # 去掉常见后缀
    title = re.sub(r'的做法$', '', title)
    title = re.sub(r'的家常做法$', '', title)
    title = re.sub(r'【[^】]*】', '', title)  # 去掉【】标记

    raw_ingredients = raw.get('raw_ingredients', [])
    if isinstance(raw_ingredients, str):
        raw_ingredients = [i.strip() for i in raw_ingredients.split(',') if i.strip()]

    raw_steps = raw.get('raw_steps', [])
    if isinstance(raw_steps, str):
        # 按换行或数字分隔符拆分
        raw_steps = [s.strip() for s in re.split(r'[\n\r]+|\d+[\.\、\s)]', raw_steps) if s.strip()]

    # 过滤太短或无关的步骤
    steps = [s for s in raw_steps if len(s) >= 3 and not re.match(r'^[仅只]供参考', s)]

    ingredients = clean_ingredients(raw_ingredients)

    # 最低质量要求
    if not ingredients:
        return None
    if not steps:
        steps = [f"准备{', '.join(ingredients[:5])}等食材", f"按照常规方法烹饪{title}"]

    # 自动推断
    steps_text = ' '.join(steps)
    category = raw.get('raw_category', '')
    if category and category in VALID_CATEGORIES:
        pass  # 信任数据自带的分类
    else:
        category = auto_classify(title, ingredients, steps_text)

    cooking_method = auto_method(title, steps_text)
    if cooking_method == '通用' and category in CATEGORY_DEFAULT_METHOD:
        cooking_method = CATEGORY_DEFAULT_METHOD[category]

    difficulty = auto_difficulty(steps, len(ingredients))

    tags = generate_tags(title, ingredients, category)

    body_md = make_recipe_body(
        title=title,
        difficulty=difficulty,
        ingredients=ingredients,
        steps=steps,
        description=raw.get('description', ''),
        tips=raw.get('tips', []),
    )

    return {
        'title': title,
        'category': category,
        'cooking_method': cooking_method,
        'difficulty': difficulty,
        'tags': tags,
        'ingredients': ingredients,
        'steps': steps,
        'source': source,
        'body_md': body_md,
    }


# ========== YAML frontmatter 生成 ==========

def make_frontmatter(recipe: dict) -> str:
    """生成 YAML frontmatter 字符串"""
    import yaml

    fm = {
        'title': recipe['title'],
        'category': recipe['category'],
        'cooking_method': recipe['cooking_method'],
        'difficulty': recipe['difficulty'],
        'tags': recipe['tags'],
        'ingredients': recipe['ingredients'],
        'source': recipe['source'],
    }

    return yaml.dump(fm, allow_unicode=True, default_flow_style=False, sort_keys=False).strip()


def make_full_md(recipe: dict) -> str:
    """生成完整的 .md 文件内容（frontmatter + body）"""
    fm = make_frontmatter(recipe)
    body = recipe.get('body_md', '')
    return f"---\n{fm}\n---\n\n{body}"


# ========== 安全文件名 ==========

def safe_filename(title: str) -> str:
    """将菜名转为安全的文件名（去掉 Windows/Linux 不允许的字符）"""
    # 去掉或替换非法字符
    safe = re.sub(r'[<>:"/\\|?*]', '', title)
    safe = safe.strip().strip('.')
    if not safe:
        safe = 'untitled'
    # 限制长度
    if len(safe) > 50:
        safe = safe[:50]
    return safe
