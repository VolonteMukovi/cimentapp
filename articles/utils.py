"""Images articles : JSON [{image, is_main}, …] et enregistrement fichiers."""

from __future__ import annotations

import json
import uuid
from pathlib import Path

from django.conf import settings


def normalize_images_json(items: list) -> list:
    """
    Garde une liste d’objets {image: str, is_main: bool}.
    Au plus une entrée avec is_main True ; si plusieurs True, seules les suivantes passent à False.
    Si aucune principale mais des images existent, la première devient principale.
    """
    out: list[dict] = []
    for raw in items:
        if isinstance(raw, str):
            raw = {'image': raw, 'is_main': False}
        if not isinstance(raw, dict):
            continue
        img = raw.get('image')
        if not img:
            continue
        out.append({'image': str(img).strip(), 'is_main': bool(raw.get('is_main'))})
    seen_main = False
    for x in out:
        if x['is_main']:
            if seen_main:
                x['is_main'] = False
            else:
                seen_main = True
    if out and not seen_main:
        out[0]['is_main'] = True
    return out


def save_uploaded_image(uploaded_file, entreprise_id: int, article_id: str) -> str:
    """
    Enregistre le fichier sous MEDIA_ROOT/articles/<entreprise_id>/<article_id>/.
    Retourne le chemin relatif (pour MEDIA_URL + JSON), ex. articles/1/art_xxx/uuid.jpg
    """
    ext = Path(uploaded_file.name).suffix[:12] or '.bin'
    if ext.lower() not in ('.jpg', '.jpeg', '.png', '.gif', '.webp', '.bin'):
        ext = '.bin'
    name = f'{uuid.uuid4().hex}{ext}'
    rel_dir = Path('articles') / str(entreprise_id) / article_id
    abs_dir = Path(settings.MEDIA_ROOT) / rel_dir
    abs_dir.mkdir(parents=True, exist_ok=True)
    dest = abs_dir / name
    with dest.open('wb') as fh:
        for chunk in uploaded_file.chunks():
            fh.write(chunk)
    return str(rel_dir / name).replace('\\', '/')


def build_images_from_post(
    request,
    *,
    form_prefix: str,
    entreprise_id: int,
    article_id: str,
) -> list:
    """
    Fusionne les images existantes (JSON POST) et les nouveaux fichiers.
    `main_image_index` : index 0-based dans la liste fusionnée (existantes puis nouvelles).
    """
    raw_existing = request.POST.get(f'{form_prefix}existing_images_json', '[]')
    try:
        existing = json.loads(raw_existing)
    except json.JSONDecodeError:
        existing = []
    if not isinstance(existing, list):
        existing = []
    cleaned_existing: list[dict] = []
    for e in existing:
        if isinstance(e, dict) and e.get('image'):
            cleaned_existing.append(
                {'image': str(e['image']).strip(), 'is_main': bool(e.get('is_main'))},
            )
    new_files = request.FILES.getlist(f'{form_prefix}image_files')
    new_entries: list[dict] = []
    for f in new_files:
        if not f.name:
            continue
        rel = save_uploaded_image(f, entreprise_id, article_id)
        new_entries.append({'image': rel, 'is_main': False})
    merged = cleaned_existing + new_entries
    try:
        main_idx = int(request.POST.get(f'{form_prefix}main_image_index', '0') or 0)
    except ValueError:
        main_idx = 0
    if merged:
        if main_idx < 0 or main_idx >= len(merged):
            main_idx = 0
        for i, item in enumerate(merged):
            item['is_main'] = i == main_idx
    return normalize_images_json(merged)


def delete_article_media(entreprise_id: int, article_id: str) -> None:
    root = Path(settings.MEDIA_ROOT) / 'articles' / str(entreprise_id) / article_id
    if root.is_dir():
        import shutil

        shutil.rmtree(root, ignore_errors=True)
