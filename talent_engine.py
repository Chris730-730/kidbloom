"""Talent prediction and growth-plan engine.

Scores each talent field from keywords found in both parents' answers, then
builds an age-based growth roadmap and a weekly schedule for the top field.
This is a fun, inspiration-level estimate. Real talent comes from exposure,
practice and the child's own interest.
"""
from __future__ import annotations

import re

FIELDS: dict[str, dict] = {
    "music": {
        "name": "Music",
        "icon": "🎵",
        "keywords": ["sing", "song", "music", "piano", "guitar", "violin", "drum", "karaoke",
                     "choir", "dance", "rhythm", "concert", "band", "hum", "whistle"],
        "famous_path": "performer, composer or music producer",
    },
    "art": {
        "name": "Art & Design",
        "icon": "🎨",
        "keywords": ["paint", "draw", "sketch", "art", "design", "photo", "craft", "knit",
                     "sew", "fashion", "decor", "color", "pottery", "doodle", "film"],
        "famous_path": "illustrator, designer or film maker",
    },
    "sports": {
        "name": "Sports",
        "icon": "⚽",
        "keywords": ["run", "soccer", "football", "basketball", "swim", "tennis", "gym",
                     "hike", "bike", "cycling", "yoga", "martial", "climb", "ski", "baseball",
                     "fast", "strong", "athlet", "golf", "skate"],
        "famous_path": "pro athlete, coach or sports scientist",
    },
    "science": {
        "name": "Science & Nature",
        "icon": "🔬",
        "keywords": ["science", "biology", "chemistry", "physics", "nature", "garden",
                     "plant", "animal", "star", "space", "doctor", "nurse", "medic",
                     "experiment", "bird", "fish", "insect", "curious"],
        "famous_path": "researcher, doctor or explorer",
    },
    "tech": {
        "name": "Math & Technology",
        "icon": "💻",
        "keywords": ["math", "code", "coding", "program", "computer", "game", "puzzle",
                     "chess", "engineer", "robot", "build", "lego", "number", "logic",
                     "sudoku", "tech", "fix", "electronics"],
        "famous_path": "engineer, inventor or tech founder",
    },
    "language": {
        "name": "Language & Writing",
        "icon": "📚",
        "keywords": ["read", "book", "write", "writing", "poem", "story", "language",
                     "talk", "speech", "debate", "journal", "blog", "translate", "english",
                     "spanish", "korean", "chinese", "french", "teach"],
        "famous_path": "author, journalist or diplomat",
    },
    "leadership": {
        "name": "Leadership & Business",
        "icon": "🏆",
        "keywords": ["business", "sell", "sales", "manage", "lead", "organize", "plan",
                     "money", "invest", "volunteer", "social", "friend", "team", "market",
                     "negotiat", "start"],
        "famous_path": "entrepreneur, CEO or public leader",
    },
    "cooking": {
        "name": "Cooking & Food",
        "icon": "🍳",
        "keywords": ["cook", "bake", "chef", "food", "kitchen", "recipe", "taste",
                     "restaurant", "coffee", "spicy", "dessert", "barbecue"],
        "famous_path": "chef, food scientist or restaurant owner",
    },
}

# Bad habits hint at a hidden strength. Small bonus, never a penalty.
HABIT_HINTS = {
    "late": "science", "night": "art", "phone": "tech", "game": "tech",
    "talk": "language", "messy": "art", "snack": "cooking", "sweet": "cooking",
    "impatient": "sports", "restless": "sports", "stubborn": "leadership",
    "daydream": "art", "procrastinat": "art", "loud": "music",
}

INPUT_WEIGHTS = {
    "hobby": 3, "interest": 3, "talent": 4, "job": 2, "food": 1, "habit": 1,
}

STAGES = [
    (0, 2, "Baby (0-2)"),
    (3, 5, "Preschool (3-5)"),
    (6, 9, "Early school (6-9)"),
    (10, 13, "Middle years (10-13)"),
    (14, 18, "Teen (14-18)"),
]

ROADMAP: dict[str, list[str]] = {
    "music": [
        "Sing to the baby every day, play calm music, use shakers and soft drums.",
        "Music and movement class once a week, short rhythm games at home.",
        "Start one instrument (piano or violin), 15-20 min practice a day.",
        "Join a choir or band, learn music theory, first small recitals.",
        "Private teacher, competitions, record and share own music online.",
    ],
    "art": [
        "High-contrast picture books, finger paint, many colors and textures.",
        "Crayons and clay every day, keep a fridge gallery of their work.",
        "Weekly art class, sketchbook habit, visit museums each month.",
        "Try digital drawing and photography, enter school art contests.",
        "Build a portfolio, summer art camp, study design or film basics.",
    ],
    "sports": [
        "Lots of tummy time, crawling, safe climbing and ball rolling.",
        "Swimming lessons, running games, try many sports for fun.",
        "Pick 1-2 sports, join a local club team, learn the basics well.",
        "Regular training 3x a week, local tournaments, healthy sleep and food.",
        "Specialize in one sport, coach feedback, regional competitions.",
    ],
    "science": [
        "Name animals and plants on walks, water and sand play.",
        "Ask 'why?' together, simple kitchen experiments, zoo and aquarium trips.",
        "Science kits, nature journal, library books on space and animals.",
        "Science fair projects, microscope or telescope, summer STEM camp.",
        "Olympiad or research program, lab volunteering, mentor in the field.",
    ],
    "tech": [
        "Stacking blocks, shape sorters, counting songs.",
        "Lego, puzzles, simple board games, counting in daily life.",
        "Math games, Scratch coding, chess club.",
        "Python or robotics club, math competitions, build a small app.",
        "Advanced courses, hackathons, open source or a startup project.",
    ],
    "language": [
        "Talk all day, read aloud every night, nursery rhymes.",
        "Picture books, storytelling games, a second language through songs.",
        "Daily reading time, write short stories, library card.",
        "Journal, school paper or debate team, read classics.",
        "Publish writing online, speech contests, deep study of a second language.",
    ],
    "leadership": [
        "Play dates, sharing games, give small choices every day.",
        "Simple chores, pretend shop play, group games with turn taking.",
        "Class helper roles, piggy bank and saving, team activities.",
        "Student council, lemonade-stand style business, volunteering.",
        "Lead a club, internship, small online business or community project.",
    ],
    "cooking": [
        "Taste many new foods, let baby explore textures safely.",
        "Wash vegetables, stir and mix, name foods and smells.",
        "Kids cooking class, cook one family meal a week together.",
        "Follow recipes alone, learn food science, try world cuisines.",
        "Culinary camp, part-time kitchen job, create own recipes and a food blog.",
    ],
}

WEEKLY_ACTIVITY = {
    "music": ("Music practice", "Listen to new music together"),
    "art": ("Drawing / painting time", "Museum or gallery visit"),
    "sports": ("Sport training", "Family outdoor game"),
    "science": ("Experiment or nature walk", "Science museum / zoo trip"),
    "tech": ("Puzzles, chess or coding", "Build project (Lego / robot)"),
    "language": ("Reading and writing time", "Library visit + storytelling"),
    "leadership": ("Team or club activity", "Family meeting led by the child"),
    "cooking": ("Cook with parents", "Market trip, try a new food"),
}

DAYS = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]


def _count(text: str, keyword: str) -> int:
    return len(re.findall(re.escape(keyword), text.lower()))


def score_parents(parents: list[dict]) -> list[dict]:
    scores = {key: 0.0 for key in FIELDS}
    reasons: dict[str, set[str]] = {key: set() for key in FIELDS}

    for parent in parents:
        label = parent.get("label", "Parent")
        for input_key, weight in INPUT_WEIGHTS.items():
            text = parent.get(input_key, "") or ""
            if not text.strip():
                continue
            for field_key, field in FIELDS.items():
                hits = sum(_count(text, kw) for kw in field["keywords"])
                if hits:
                    scores[field_key] += hits * weight
                    reasons[field_key].add(f"{label}'s {input_key}")
            if input_key == "habit":
                for kw, field_key in HABIT_HINTS.items():
                    if kw in text.lower():
                        scores[field_key] += 1.5
                        reasons[field_key].add(f"{label}'s habit")

    total = sum(scores.values())
    results = []
    for key, field in FIELDS.items():
        # A small base so every field shows some potential.
        raw = scores[key] + 1
        pct = round(100 * raw / (total + len(FIELDS)))
        results.append({
            "key": key,
            "name": field["name"],
            "icon": field["icon"],
            "percent": pct,
            "reasons": sorted(reasons[key]),
            "famous_path": field["famous_path"],
        })
    results.sort(key=lambda r: r["percent"], reverse=True)
    return results


def stage_index(age: int) -> int:
    for i, (low, high, _) in enumerate(STAGES):
        if low <= age <= high:
            return i
    return 0 if age < 0 else len(STAGES) - 1


def build_roadmap(field_key: str, age: int) -> list[dict]:
    current = stage_index(age)
    return [
        {"stage": label, "advice": ROADMAP[field_key][i], "current": i == current, "done": i < current}
        for i, (_, _, label) in enumerate(STAGES)
    ]


def build_weekly_schedule(top: list[dict], age: int) -> list[dict]:
    """Weekly plan. Main field gets most days, the second field gets two days."""
    main, second = top[0]["key"], top[1]["key"]
    minutes = 15 if age <= 2 else 25 if age <= 5 else 40 if age <= 9 else 60 if age <= 13 else 90
    main_daily, main_weekend = WEEKLY_ACTIVITY[main]
    second_daily, _ = WEEKLY_ACTIVITY[second]

    plan = []
    for day in DAYS:
        if day in ("Tue", "Thu"):
            plan.append({"day": day, "activity": second_daily, "field": top[1]["name"], "minutes": minutes})
        elif day == "Sat":
            plan.append({"day": day, "activity": main_weekend, "field": top[0]["name"], "minutes": minutes * 2})
        elif day == "Sun":
            plan.append({"day": day, "activity": "Free play and family rest", "field": "Balance", "minutes": 0})
        else:
            plan.append({"day": day, "activity": main_daily, "field": top[0]["name"], "minutes": minutes})
    return plan


def healthy_basics(age: int) -> list[str]:
    if age <= 2:
        sleep = "12-16 hours of sleep a day including naps"
    elif age <= 5:
        sleep = "10-13 hours of sleep a day"
    elif age <= 12:
        sleep = "9-12 hours of sleep a night"
    else:
        sleep = "8-10 hours of sleep a night"
    return [
        sleep,
        "At least 1 hour of active play every day",
        "Fruits and vegetables at every meal, water instead of sugary drinks",
        "Keep screen time low and never right before bed",
        "Regular check-ups with the pediatrician",
        "Praise effort more than results, and let the child choose sometimes",
    ]


def make_plan(parents: list[dict], child: dict) -> dict:
    age = max(0, min(18, int(child.get("age", 0) or 0)))
    talents = score_parents(parents)
    focus = child.get("focus") or talents[0]["key"]
    if focus not in FIELDS:
        focus = talents[0]["key"]
    ordered = [t for t in talents if t["key"] == focus] + [t for t in talents if t["key"] != focus]
    return {
        "talents": talents,
        "focus": ordered[0],
        "roadmap": build_roadmap(focus, age),
        "schedule": build_weekly_schedule(ordered, age),
        "basics": healthy_basics(age),
        "age": age,
    }
