"""KidBloom: grow healthy, talented children.

Run:  python app.py   then open http://127.0.0.1:5000
"""
from __future__ import annotations

import json
import os
import sqlite3
import uuid
from datetime import datetime
from pathlib import Path

from flask import (Flask, abort, flash, g, jsonify, redirect, render_template,
                   request, send_from_directory, url_for)
from dotenv import load_dotenv, set_key
from werkzeug.utils import secure_filename

from ai_face import AIFaceError, predict_child_faces, provider
from talent_engine import FIELDS, make_plan

BASE = Path(__file__).resolve().parent
ENV_FILE = BASE / ".env"
load_dotenv(ENV_FILE)
UPLOADS = BASE / "uploads"
GENERATED = BASE / "generated"
DB_PATH = BASE / "kidbloom.db"
ALLOWED = {"png", "jpg", "jpeg", "webp"}

app = Flask(__name__)
app.config["SECRET_KEY"] = os.environ.get("SECRET_KEY", "change-me-in-production")
app.config["MAX_CONTENT_LENGTH"] = 16 * 1024 * 1024


# ---------- database ----------
def get_db() -> sqlite3.Connection:
    if "db" not in g:
        g.db = sqlite3.connect(DB_PATH)
        g.db.row_factory = sqlite3.Row
    return g.db


@app.teardown_appcontext
def close_db(_exc):
    db = g.pop("db", None)
    if db is not None:
        db.close()


def init_db() -> None:
    with sqlite3.connect(DB_PATH) as db:
        db.execute("""
            CREATE TABLE IF NOT EXISTS family (
                id TEXT PRIMARY KEY,
                created TEXT NOT NULL,
                child_name TEXT,
                child_age INTEGER,
                data TEXT NOT NULL,
                faces TEXT NOT NULL,
                plan TEXT NOT NULL
            )""")


# ---------- helpers ----------
def allowed(filename: str) -> bool:
    return "." in filename and filename.rsplit(".", 1)[1].lower() in ALLOWED


def save_upload(file, prefix: str) -> Path | None:
    if not file or not file.filename or not allowed(file.filename):
        return None
    UPLOADS.mkdir(exist_ok=True)
    name = f"{prefix}_{uuid.uuid4().hex[:10]}_{secure_filename(file.filename)}"
    path = UPLOADS / name
    file.save(path)
    return path


def parent_from_form(prefix: str, label: str) -> dict:
    keys = ["name", "hobby", "interest", "food", "habit", "talent", "job"]
    data = {k: request.form.get(f"{prefix}_{k}", "").strip()[:300] for k in keys}
    data["label"] = data["name"] or label
    return data


# ---------- pages ----------
@app.route("/")
def index():
    return render_template("index.html", fields=FIELDS)


@app.route("/start", methods=["GET", "POST"])
def start():
    if request.method == "GET":
        return render_template("start.html", fields=FIELDS)

    father = parent_from_form("dad", "Dad")
    mother = parent_from_form("mom", "Mom")
    child = {
        "name": request.form.get("child_name", "").strip()[:60] or "Little one",
        "age": request.form.get("child_age", "0"),
        "gender": request.form.get("child_gender", "any"),
        "focus": request.form.get("focus", ""),
    }
    try:
        child["age"] = max(0, min(18, int(child["age"])))
    except ValueError:
        child["age"] = 0

    faces: list[str] = []
    dad_photo = save_upload(request.files.get("dad_photo"), "dad")
    mom_photo = save_upload(request.files.get("mom_photo"), "mom")
    if dad_photo and mom_photo:
        try:
            mix = float(request.form.get("mix", 50)) / 100
            faces = predict_child_faces(dad_photo, mom_photo, GENERATED, age=child["age"],
                                        gender=child["gender"], mix=mix)
        except AIFaceError as exc:
            flash(f"AI face prediction failed: {exc} The talent plan is still ready.")
        except Exception as exc:  # unreadable image file etc.
            flash(f"Could not read the photos ({exc}). The talent plan is still ready.")
    elif dad_photo or mom_photo:
        flash("Upload both parents' photos to see the face preview.")

    plan = make_plan([father, mother], child)
    fid = uuid.uuid4().hex[:12]
    db = get_db()
    db.execute(
        "INSERT INTO family VALUES (?,?,?,?,?,?,?)",
        (fid, datetime.now().isoformat(timespec="seconds"), child["name"], child["age"],
         json.dumps({"father": father, "mother": mother, "child": child}),
         json.dumps(faces), json.dumps(plan)),
    )
    db.commit()
    return redirect(url_for("result", fid=fid))


def load_family(fid: str) -> dict:
    row = get_db().execute("SELECT * FROM family WHERE id=?", (fid,)).fetchone()
    if row is None:
        abort(404)
    return {
        "id": row["id"], "created": row["created"],
        "data": json.loads(row["data"]), "faces": json.loads(row["faces"]),
        "plan": json.loads(row["plan"]),
    }


@app.route("/result/<fid>")
def result(fid):
    return render_template("result.html", fam=load_family(fid), fields=FIELDS)


@app.route("/result/<fid>/focus", methods=["POST"])
def change_focus(fid):
    fam = load_family(fid)
    child = fam["data"]["child"] | {"focus": request.form.get("focus", "")}
    plan = make_plan([fam["data"]["father"], fam["data"]["mother"]], child)
    db = get_db()
    db.execute("UPDATE family SET plan=?, data=? WHERE id=?",
               (json.dumps(plan), json.dumps(fam["data"] | {"child": child}), fid))
    db.commit()
    return redirect(url_for("result", fid=fid) + "#plan")


@app.route("/families")
def families():
    rows = get_db().execute(
        "SELECT id, created, child_name, child_age, plan FROM family ORDER BY created DESC LIMIT 50"
    ).fetchall()
    items = [{"id": r["id"], "created": r["created"], "name": r["child_name"],
              "age": r["child_age"], "focus": json.loads(r["plan"])["focus"]} for r in rows]
    return render_template("families.html", items=items)


@app.route("/families/<fid>/delete", methods=["POST"])
def delete_family(fid):
    fam = load_family(fid)
    for face in fam["faces"]:
        (GENERATED / face["file"]).unlink(missing_ok=True)
    db = get_db()
    db.execute("DELETE FROM family WHERE id=?", (fid,))
    db.commit()
    flash("Profile deleted.")
    return redirect(url_for("families"))


@app.route("/settings", methods=["GET", "POST"])
def settings():
    if request.method == "POST":
        ENV_FILE.touch(exist_ok=True)
        for field in ("OPENAI_API_KEY", "OPENAI_IMAGE_MODEL"):
            value = request.form.get(field, "").strip()
            if request.form.get(f"clear_{field}") or (not value and "MODEL" in field):
                set_key(str(ENV_FILE), field, "")
                os.environ.pop(field, None)
            elif value and not value.startswith("•"):  # bullets = unchanged masked key
                set_key(str(ENV_FILE), field, value)
                os.environ[field] = value
        quality = request.form.get("OPENAI_IMAGE_QUALITY", "medium")
        if quality in ("low", "medium", "high"):
            set_key(str(ENV_FILE), "OPENAI_IMAGE_QUALITY", quality)
            os.environ["OPENAI_IMAGE_QUALITY"] = quality
        flash("Settings saved.")
        return redirect(url_for("settings"))

    def masked(field):
        v = os.environ.get(field, "")
        return ("•" * 8 + v[-4:]) if v else ""
    return render_template(
        "settings.html", active=provider(),
        openai=masked("OPENAI_API_KEY"),
        openai_model=os.environ.get("OPENAI_IMAGE_MODEL", ""),
        quality=os.environ.get("OPENAI_IMAGE_QUALITY", "medium"))


@app.context_processor
def inject_ai():
    return {"ai_ready": provider() is not None}


@app.route("/generated/<path:name>")
def generated(name):
    return send_from_directory(GENERATED, name)


# ---------- JSON API ----------
@app.route("/api/predict", methods=["POST"])
def api_predict():
    body = request.get_json(force=True, silent=True) or {}
    parents = [body.get("father", {}) | {"label": "Dad"}, body.get("mother", {}) | {"label": "Mom"}]
    return jsonify(make_plan(parents, body.get("child", {})))


@app.errorhandler(404)
def not_found(_e):
    return render_template("404.html"), 404


init_db()

if __name__ == "__main__":
    app.run(debug=True, host="127.0.0.1", port=int(os.environ.get("PORT", 5000)))
