# KidBloom

A full-stack Python website for parents. It previews a child's face from both parents' photos, predicts the child's talents from the parents' hobbies, interests, food, habits and hidden talents, and builds a growth roadmap plus a weekly schedule for one special field.

Stack: Flask (backend + Jinja templates), SQLite (saved profiles), Pillow (face preview), plain HTML/CSS/JS (frontend).

## Run on your computer (Python 3.14)

Windows:

```
cd kidbloom
py -3.14 -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
python app.py
```

macOS / Linux:

```
cd kidbloom
python3.14 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python app.py
```

Then open http://127.0.0.1:5000. You can also double-click `run_windows.bat` or run `./run_mac_linux.sh`.

## Project layout

```
app.py             routes, database, file uploads, JSON API
talent_engine.py   talent scoring, age roadmap, weekly schedule
ai_face.py         AI child face prediction (ChatGPT image model)
.env               your API keys (created by the Settings page)
templates/         pages: home, start form, result, my families
static/            CSS, JS and the illustrations (SVG)
uploads/           parent photos (created at runtime)
generated/         child face previews (created at runtime)
kidbloom.db        SQLite database (created at first run)
```

## AI face prediction (ChatGPT)

The child's face is made by ChatGPT's image model (`chatgpt-image-latest`) through the OpenAI Image API. Both parents' photos go to the image edit endpoint as two reference images, with a prompt that asks for their child at the given age and gender. It makes 3 portraits: balanced (uses the face-mix slider), more like Dad, more like Mom.

1. Create an API key at platform.openai.com → API keys, and add billing credit. A ChatGPT Plus subscription does not include API access, so the key needs its own credit.
2. Start the site, open **Settings** and paste the key. It is saved in `.env` in this folder. You can also copy `.env.example` to `.env` and fill it in by hand.
3. Use front-facing photos with good light. Each prediction takes about 20-60 seconds and makes 3 paid image calls.

With the model field empty, the app uses `chatgpt-image-latest` and falls back to `gpt-image-2.6-sunburst`, `gpt-image-2.5-sunburst`, `gpt-image-2` and `gpt-image-1.5` if your key can't use it, then remembers the one that worked. To force a model, type its name in Settings or set `OPENAI_IMAGE_MODEL` in `.env`. Some newer models need organization verification on your OpenAI account first.

Quality is `low`, `medium` (default) or `high`. Higher quality looks better and costs more.

Without a key the talent plan still works and the face section asks for a key.

Privacy: profiles are stored on your computer. Parent photos are sent only to OpenAI.

## Customizing

- Talent fields, keywords, roadmap text and schedules are plain Python dicts at the top of `talent_engine.py`.
- Colors are CSS variables at the top of `static/css/style.css`.
- JSON API: `POST /api/predict` with `{"father": {...}, "mother": {...}, "child": {"age": 5}}` returns the full plan.

Before putting it on the internet, set a `SECRET_KEY` environment variable and run it with a production server such as waitress or gunicorn.
