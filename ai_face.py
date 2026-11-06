"""AI child face prediction with ChatGPT's image model (OpenAI Image API).

Dad's and Mom's photos go to the OpenAI image edit endpoint as two
reference images. The model returns a photorealistic portrait of their child.
By default it uses chatgpt-image-latest, the same image model ChatGPT uses.

Settings (in .env or the Settings page):
  OPENAI_API_KEY      required
  OPENAI_IMAGE_MODEL  optional. Empty = try OPENAI_MODELS in order.
  OPENAI_IMAGE_QUALITY optional: low | medium | high | auto (default: medium)
"""
from __future__ import annotations

import base64
import io
import os
import urllib.request
import uuid
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

from PIL import Image, ImageOps

# ChatGPT's image model first, then newest GPT Image models.
# The first name the API accepts is remembered for later calls.
OPENAI_MODELS = [
    "chatgpt-image-latest",
    "gpt-image-2.6-sunburst",
    "gpt-image-2.5-sunburst",
    "gpt-image-2",
    "gpt-image-1.5",
]
_working_model: str | None = None

VARIANTS = [
    ("balanced", "Balanced mix", None),
    ("dad", "More like Dad", "father"),
    ("mom", "More like Mom", "mother"),
]


class AIFaceError(Exception):
    """Readable error shown to the user."""


def provider() -> str | None:
    """'openai' when a key is set, else None (face prediction off)."""
    return "openai" if os.environ.get("OPENAI_API_KEY") else None


def _load_photo(path: Path) -> bytes:
    """Fix rotation, shrink to max 1024 px and return PNG bytes."""
    img = ImageOps.exif_transpose(Image.open(path)).convert("RGB")
    img.thumbnail((1024, 1024))
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()


def _age_text(age: int) -> str:
    if age <= 0:
        return "a baby about 1 year old"
    if age <= 2:
        return f"a toddler about {age} years old"
    return f"a {age}-year-old"


def build_prompt(age: int, gender: str, mix: float, lean: str | None) -> str:
    kid = {"boy": "boy", "girl": "girl"}.get(gender, "child")
    if lean is None:
        dad_pct = round((1 - mix) * 100)
        weighting = f"Take about {dad_pct}% of the facial features from the father and {100 - dad_pct}% from the mother."
    else:
        weighting = f"The child should clearly resemble the {lean} more, while still having some features of the other parent."
    return (
        "The first image is the father and the second image is the mother. "
        f"Create one photorealistic portrait of their biological {kid}, {_age_text(age)}. "
        "The child must inherit real features from both parents: face shape, eye shape and color, "
        "eyebrows, nose, lips, ears, skin tone, and hair color and texture. "
        f"{weighting} "
        "Make the face look natural and age-appropriate for the child, not a copy of either parent. "
        "Head-and-shoulders, facing the camera, gentle happy expression, simple casual clothing, "
        "soft natural studio light, plain light blue background. One person only, no text."
    )


def _client():
    try:
        from openai import OpenAI
    except ImportError as exc:
        raise AIFaceError("The 'openai' package is not installed. Run: pip install -r requirements.txt") from exc
    return OpenAI(api_key=os.environ.get("OPENAI_API_KEY"), timeout=180, max_retries=2)


def _edit(client, model: str, dad: bytes, mom: bytes, prompt: str) -> bytes:
    result = client.images.edit(
        model=model,
        image=[("father.png", dad, "image/png"), ("mother.png", mom, "image/png")],
        prompt=prompt,
        size="1024x1024",
        quality=os.environ.get("OPENAI_IMAGE_QUALITY", "medium") or "medium",
        n=1,
    )
    data = result.data[0] if result.data else None
    if data is not None and data.b64_json:
        return base64.b64decode(data.b64_json)
    if data is not None and getattr(data, "url", None):
        with urllib.request.urlopen(data.url, timeout=60) as resp:
            return resp.read()
    raise AIFaceError("OpenAI returned no image.")


def _generate(dad: bytes, mom: bytes, prompt: str) -> bytes:
    global _working_model
    from openai import (APIConnectionError, APIError, AuthenticationError, BadRequestError,
                        NotFoundError, PermissionDeniedError, RateLimitError)

    client = _client()
    custom = (os.environ.get("OPENAI_IMAGE_MODEL") or "").strip()
    models = [custom] if custom else ([_working_model] if _working_model else OPENAI_MODELS)
    last: Exception | None = None
    for model in models:
        try:
            png = _edit(client, model, dad, mom, prompt)
            if not custom:
                _working_model = model
            return png
        except AuthenticationError as exc:
            raise AIFaceError("The OpenAI API key is not valid. Check it in Settings.") from exc
        except RateLimitError as exc:
            raise AIFaceError("OpenAI rate limit or quota reached. Check billing at platform.openai.com.") from exc
        except APIConnectionError as exc:
            raise AIFaceError("Could not reach OpenAI. Check your internet connection.") from exc
        except PermissionDeniedError as exc:
            # Some image models need organization verification first.
            if not custom:
                last = exc
                continue
            raise AIFaceError(f"Your OpenAI account can't use {model} yet: {exc.message}") from exc
        except (NotFoundError, BadRequestError) as exc:
            msg = str(exc).lower()
            if "safety" in msg or "moderation" in msg:
                raise AIFaceError("OpenAI's safety filter blocked these photos. Try other clear face photos.") from exc
            if "model" in msg and not custom:
                last = exc
                continue
            raise AIFaceError(f"OpenAI rejected the request: {exc.message}") from exc
        except APIError as exc:  # server errors, timeouts
            raise AIFaceError(f"OpenAI had a problem ({exc.__class__.__name__}). Please try again.") from exc
    raise AIFaceError(f"No OpenAI image model worked for this key ({last}). Set the model in Settings.")


def predict_child_faces(father: Path, mother: Path, out_dir: Path, *, age: int = 0,
                        gender: str = "any", mix: float = 0.5) -> list[dict]:
    """Generate 3 AI portraits in parallel. Returns [{"file", "label"}].
    Raises AIFaceError if no key is set or every request fails."""
    if provider() is None:
        raise AIFaceError("No OpenAI API key yet. Open Settings and add your key.")
    dad, mom = _load_photo(father), _load_photo(mother)
    out_dir.mkdir(parents=True, exist_ok=True)

    def run(variant):
        key, label, lean = variant
        png = _generate(dad, mom, build_prompt(age, gender, mix, lean))
        img = Image.open(io.BytesIO(png)).convert("RGB")
        fname = f"child_{key}_{uuid.uuid4().hex[:10]}.jpg"
        img.save(out_dir / fname, quality=92)
        return {"file": fname, "label": label}

    # Find a working model with the first variant, then run the other two in parallel.
    results = [run(VARIANTS[0])]
    with ThreadPoolExecutor(max_workers=2) as pool:
        for fut in [pool.submit(run, v) for v in VARIANTS[1:]]:
            try:
                results.append(fut.result())
            except Exception:  # keep the faces that worked
                pass
    return results
