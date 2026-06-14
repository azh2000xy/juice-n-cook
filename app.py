#!/usr/bin/env python3
"""
果蔬汁菜谱 Web App — Flask 后端

启动: python app.py
手机访问: http://<电脑IP>:5000
"""

import re
from pathlib import Path

import yaml
from flask import Flask, jsonify, render_template, request

app = Flask(__name__)

BASE = Path(__file__).parent
RECIPES_DIR = BASE / "recipes"
INDEX_PATH = BASE / ".claude" / "skills" / "juice-n-cook" / "references" / "recipe_index.yaml"
INGREDIENTS_PATH = BASE / ".claude" / "skills" / "juice-n-cook" / "references" / "ingredients_index.yaml"
RULES_PATH = BASE / ".claude" / "skills" / "juice-n-cook" / "references" / "matching_rules.yaml"

# ── 启动时加载数据 ──────────────────────────────────────────
with open(INDEX_PATH, "r", encoding="utf-8") as f:
    recipe_data = yaml.safe_load(f)
RECIPES = recipe_data["recipes"]

with open(INGREDIENTS_PATH, "r", encoding="utf-8") as f:
    ingredients_data = yaml.safe_load(f)

ING_LOOKUP = {}
for ing in ingredients_data["ingredients"]:
    ING_LOOKUP[ing["name"]] = ing
    for alias in ing.get("aliases", []):
        ING_LOOKUP[alias] = ing

with open(RULES_PATH, "r", encoding="utf-8") as f:
    rules = yaml.safe_load(f)
SCORING = rules["scoring"]
THRESHOLDS = rules["thresholds"]


# ── 匹配逻辑 ────────────────────────────────────────────────
def classify_ingredients(user_ings: list[str]) -> tuple[set, set]:
    """食材分类：返回 (水果集合, 蔬菜集合)"""
    fruits, veggies = set(), set()
    for name in user_ings:
        info = ING_LOOKUP.get(name.strip())
        if info:
            cat = info["category"]
            if cat in ("fruit", "fruit-vegetable"):
                fruits.add(name.strip())
            if cat in ("vegetable", "fruit-vegetable"):
                veggies.add(name.strip())
        else:
            # 未知食材 → 两个集合都放
            fruits.add(name.strip())
            veggies.add(name.strip())
    return fruits, veggies


def expand_aliases(user_ings: list[str]) -> set:
    """将用户输入的食材扩展为所有可能的别名"""
    result = set()
    for name in user_ings:
        name = name.strip()
        result.add(name)
        info = ING_LOOKUP.get(name)
        if info:
            for alias in info.get("aliases", []):
                result.add(alias)
    return result


def get_steps_preview(filepath: str) -> list[str]:
    """从食谱文件中提取前 3 步操作步骤"""
    full_path = BASE / filepath
    if not full_path.exists():
        return []
    with open(full_path, "r", encoding="utf-8") as f:
        content = f.read()

    steps = []
    in_ops = False
    for line in content.split('\n'):
        # Look for ## 操作 or ## 操作步骤
        if re.match(r'^##\s+操作', line):
            in_ops = True
            continue
        if in_ops:
            if line.startswith('## '):
                break
            # Match numbered step
            m = re.match(r'^\d+\.\s*(.+)', line)
            if m:
                step = m.group(1).strip()
                if len(step) > 3 and len(steps) < 3:
                    steps.append(step)
    return steps


def search(user_ings: list[str], recipe_type: str = "both",
           method_filter: str = None) -> list[dict]:
    """搜索匹配食谱"""
    results = []
    # 扩展别名：猪肉 → 五花肉, 猪瘦肉, 里脊肉...
    user_set = expand_aliases(user_ings)
    original_set = set(name.strip() for name in user_ings)

    for r in RECIPES:
        r_ings = set(r.get("ingredients", []))
        overlap = user_set & r_ings
        if not overlap:
            continue

        # 类型过滤
        src = r.get("source", "")
        if recipe_type == "cooking" and src == "juice-book":
            continue
        if recipe_type == "juice" and src == "howtocook":
            continue

        # 做法过滤
        if method_filter and method_filter != "全部":
            r_method = r.get("cooking_method", "")
            if r_method != method_filter:
                continue

        # 打分
        score = len(overlap) / len(r_ings) if r_ings else 0
        if score < 0.08:  # 极低阈值，确保单食材也能匹配
            continue

        missing = list(r_ings - user_set)
        matched = list(overlap & r_ings)  # 用户实际能提供的（含别名扩展）
        results.append({
            "title": r.get("title", ""),
            "category": r.get("category", ""),
            "cooking_method": r.get("cooking_method", ""),
            "difficulty": r.get("difficulty", 3),
            "difficulty_stars": "★" * r.get("difficulty", 3),
            "ingredients": r.get("ingredients", []),
            "matched": matched,
            "missing": missing[:THRESHOLDS.get("max_missing_show", 6)],
            "missing_count": len(missing),
            "steps": get_steps_preview(r.get("file", "")),
            "file": r.get("file", ""),
            "source": src,
            "score": round(score, 2),
        })

    results.sort(key=lambda x: (-x["score"], x["difficulty"]))
    return results[:THRESHOLDS.get("max_results", 10)]


def determine_type(fruit_set: set, veggie_set: set, method: str) -> str:
    """决定推荐类型"""
    if method == "榨汁":
        return "juice"
    if method and method not in ("全部", ""):
        return "cooking"  # 炒/蒸/煮... 都是做菜
    if veggie_set and not fruit_set:
        return "cooking"
    if fruit_set and not veggie_set:
        return "juice"
    return "both"


# ── API 路由 ────────────────────────────────────────────────
@app.route("/")
def index():
    return render_template("index.html")


@app.route("/api/search", methods=["POST"])
def api_search():
    data = request.get_json(force=True)
    user_input = data.get("ingredients", "")
    method = data.get("method", "")

    if not user_input.strip():
        return jsonify({"error": "请输入食材"}), 400

    # 解析食材：支持 中文逗号/英文逗号/空格 分隔
    user_ings = re.split(r"[，,\s]+", user_input.strip())
    user_ings = [x for x in user_ings if x]

    # Step 1-2: 分类 + 决定类型
    fruits, veggies = classify_ingredients(user_ings)
    recipe_type = determine_type(fruits, veggies, method)

    # Step 3: 匹配
    results = search(user_ings, recipe_type, method if method else None)

    return jsonify({
        "recipe_type": recipe_type,
        "fruits": list(fruits),
        "veggies": list(veggies),
        "total": len(results),
        "results": results,
    })


@app.route("/api/recipe")
def api_recipe():
    filepath = request.args.get("file", "")
    if not filepath:
        return jsonify({"error": "missing file param"}), 400

    full_path = BASE / filepath
    if not full_path.exists():
        return jsonify({"error": "recipe not found"}), 404

    with open(full_path, "r", encoding="utf-8") as f:
        content = f.read()

    # 解析 YAML frontmatter
    fm_match = re.match(r"^---\s*\n(.*?)\n---\s*\n", content, re.DOTALL)
    frontmatter = {}
    body = content
    if fm_match:
        try:
            frontmatter = yaml.safe_load(fm_match.group(1)) or {}
        except yaml.YAMLError:
            pass
        body = content[fm_match.end():]

    return jsonify({
        "title": frontmatter.get("title", ""),
        "difficulty": "★" * frontmatter.get("difficulty", 3) if isinstance(frontmatter.get("difficulty"), int) else str(frontmatter.get("difficulty", "")),
        "cooking_method": frontmatter.get("cooking_method", ""),
        "ingredients": frontmatter.get("ingredients", []),
        "tags": frontmatter.get("tags", []),
        "benefits": frontmatter.get("benefits", ""),
        "body": body,
    })


@app.route("/api/methods")
def api_methods():
    """返回所有可用的做法列表"""
    methods = set()
    for r in RECIPES:
        m = r.get("cooking_method", "")
        if m:
            methods.add(m)
    return jsonify(sorted(methods))


if __name__ == "__main__":
    import socket
    hostname = socket.gethostname()
    ip = socket.gethostbyname(hostname)
    print(f"\n  >> 果蔬汁菜谱 Web App")
    print(f"  ========================")
    print(f"  本机: http://127.0.0.1:5000")
    print(f"  手机: http://{ip}:5000")
    print(f"  ========================")
    print(f"  手机和电脑需在同一 WiFi\n")
    app.run(host="0.0.0.0", port=5000, debug=True)
