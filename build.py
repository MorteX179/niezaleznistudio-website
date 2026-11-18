#!/usr/bin/env python3
"""Generator strony Niezależni Studio.

Czyta  site.config.json  oraz pliki  content/<kategoria>/<nazwa>.json
i tworzy gotową stronę w folderze  _site/  (to on trafia na GitHub Pages).

Użycie:
    python3 build.py           # zbuduj stronę do _site/
    python3 build.py --serve   # zbuduj i uruchom podgląd na http://localhost:8000

Do optymalizacji obrazków potrzebny jest Pillow (Fedora: sudo dnf install python3-pillow)
(bez niego obrazki zostaną skopiowane bez zmian).
"""

import hashlib
import html
import json
import re
import shutil
import sys
import urllib.request
from datetime import date
from pathlib import Path

try:
    from PIL import Image, ImageOps
except ImportError:  # pragma: no cover
    Image = None

ROOT = Path(__file__).resolve().parent
TYPES = {}  # wypełniane z site.config.json -> "types"
CONTENT = ROOT / "content"
STATIC = ROOT / "static"
OUT = ROOT / "_site"
IMAGE_EXTS = (".jpg", ".jpeg", ".png", ".webp")
CARD_W, LARGE_W = 640, 1280
YT_CACHE = ROOT / ".cache" / "youtube"

# Ikonka dobierana automatycznie po nazwie roli (jeśli w JSON nie podano "icon").
ROLE_ICONS = [
    ("reżyser", "clipper"), ("tłumacz", "ksiazka"), ("scenariusz", "ksiazka"), ("tekst", "ksiazka"),
    ("grafik", "pyndzel"), ("miniatur", "pyndzel"), ("rysun", "pyndzel"), ("animac", "pyndzel"),
    ("dźwięk", "glosnik"), ("mix", "glosnik"), ("mastering", "glosnik"),
    ("montaż", "kamera"), ("wideo", "kamera"), ("video", "kamera"),
    ("strona", "klawa"), ("kod", "klawa"), ("głos", "mikrofon"), ("wokal", "mikrofon"),
]

errors = []

# Dla 404: gdy strona działa pod adresem użytkownik.github.io/repo/, popraw linki zaczynające się od "/".
FIX_ROOT_JS = (
    "document.addEventListener('DOMContentLoaded',function(){var h=location.hostname,p=location.pathname.split('/')[1];"
    "if(!/\\.github\\.io$/.test(h)||!p)return;document.querySelectorAll('a[href^=\"/\"],link[href^=\"/\"]').forEach(function(a)"
    "{a.setAttribute('href','/'+p+a.getAttribute('href'))})})"
)


def esc(value):
    return html.escape(str(value or ""), quote=True)


def fail(msg):
    errors.append(msg)


# ---------------------------------------------------------------- dane

def load_json(path):
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as e:
        fail(f"{path.relative_to(ROOT)}: błąd w JSON, linia {e.lineno}, kolumna {e.colno}: {e.msg}")
    except OSError as e:
        fail(f"{path}: nie można odczytać pliku ({e})")
    return None


def load_category(cat):
    folder = CONTENT / cat["folder"]
    items = []
    if not folder.is_dir():
        return items
    for path in sorted(folder.glob("*.json")):
        if path.name.startswith("_"):
            continue  # pliki zaczynające się od _ są pomijane (szkice, szablony)
        data = load_json(path)
        if not isinstance(data, dict):
            if data is not None:
                fail(f"{path.relative_to(ROOT)}: plik musi zawierać obiekt {{ ... }}")
            continue
        if data.get("hidden"):
            continue
        slug = path.stem
        if not re.fullmatch(r"[a-z0-9_-]+", slug):
            fail(f"{path.relative_to(ROOT)}: nazwa pliku może mieć tylko małe litery, cyfry, - i _ (bez polskich znaków i spacji)")
            continue
        if not data.get("title"):
            fail(f"{path.relative_to(ROOT)}: brakuje pola \"title\"")
            continue
        rel = path.relative_to(ROOT)
        data["slug"] = slug
        data["category"] = cat
        data["url"] = f"{cat['folder']}/{slug}.html"
        data["source_image"] = find_image(folder, slug, data.get("image"), path)
        video = data.get("video") or data.get("videoUrl")
        data["video_id"] = youtube_id(video)
        data["is_short"] = "/shorts/" in (video or "")
        if video and not data["video_id"]:
            fail(f"{rel}: nie rozpoznano linku YouTube w \"video\"")
        types = TYPES.get("map", {})
        if data.get("type") and data["type"] not in types:
            fail(f"{rel}: nieznany \"type\": \"{data['type']}\" (dozwolone: {', '.join(types) or 'brak'})")
        # Podstrona powstaje, gdy jest co na niej pokazać (albo gdy wymusisz "page": true / false).
        data["has_page"] = data.get("page", bool(data.get("cast") or data.get("team") or data.get("details") or video))
        items.append(data)
    items.sort(key=lambda i: (i.get("order", 1000), i["title"].lower()))
    return items


def find_image(folder, slug, explicit, json_path):
    if explicit:
        p = folder / explicit
        if not p.is_file():
            fail(f"{json_path.relative_to(ROOT)}: nie znaleziono obrazka \"{explicit}\" w {folder.relative_to(ROOT)}/")
            return None
        return p
    for ext in IMAGE_EXTS:
        p = folder / (slug + ext)
        if p.is_file():
            return p
    return None


# ---------------------------------------------------------------- obrazki

def youtube_thumbnail(vid):
    """Pobiera najlepszą dostępną miniaturę z YouTube (z pamięcią podręczną w .cache/)."""
    YT_CACHE.mkdir(parents=True, exist_ok=True)
    cached = YT_CACHE / f"{vid}.jpg"
    if cached.is_file() and cached.stat().st_size > 2000:
        return cached
    for name in ("maxresdefault", "sddefault", "hqdefault"):
        try:
            req = urllib.request.Request(f"https://i.ytimg.com/vi/{vid}/{name}.jpg", headers={"User-Agent": "Mozilla/5.0"})
            with urllib.request.urlopen(req, timeout=15) as resp:
                data = resp.read()
        except Exception:
            continue
        if len(data) > 2000:  # YouTube zwraca malutki obrazek-zaślepkę, gdy danej wersji nie ma
            cached.write_bytes(data)
            return cached
    return None


def trim_black_bars(im):
    """Obcina czarne pasy (miniatury YouTube 4:3 i pionowe shorty)."""
    mask = im.convert("L").point(lambda v: 255 if v > 20 else 0)
    box = mask.getbbox()
    if box and (box[2] - box[0]) > im.width * 0.3 and (box[3] - box[1]) > im.height * 0.3:
        return im.crop(box)
    return im


def process_image(item):
    """Tworzy wersje WebP 640/1280 px oraz JPG do podglądu linków (og:image).

    Źródło: obrazek obok pliku JSON, a gdy go nie ma — miniatura filmu z YouTube.
    """
    item["img"] = None
    src = item["source_image"]
    from_youtube = False
    vid = item.get("video_id")
    if not src and vid:
        src = youtube_thumbnail(vid)
        from_youtube = True
        if not src or Image is None:
            # brak internetu / Pillow: użyj miniatury prosto z YouTube
            url = f"https://i.ytimg.com/vi/{vid}/hqdefault.jpg"
            item["img"] = {"small": url, "large": url, "og": url, "w": None, "h": None, "vertical": item["is_short"]}
            return
    if not src:
        return

    folder = item["category"]["folder"]
    out_dir = OUT / "images" / folder
    out_dir.mkdir(parents=True, exist_ok=True)
    base = f"images/{folder}/{item['slug']}"

    if Image is None:
        dest = out_dir / (item["slug"] + src.suffix.lower())
        shutil.copy2(src, dest)
        rel = f"images/{folder}/{dest.name}"
        item["img"] = {"small": rel, "large": rel, "og": rel, "w": None, "h": None, "vertical": item["is_short"]}
        return

    with Image.open(src) as im:
        im = ImageOps.exif_transpose(im).convert("RGB")
        if from_youtube:
            im = trim_black_bars(im)
        w, h = im.size
        vertical = h > w
        large_w = min(LARGE_W if not vertical else 720, w)
        small_w = min(CARD_W if not vertical else 360, w)
        for width, suffix in ((small_w, "640"), (large_w, "1280")):
            dest = out_dir / f"{item['slug']}-{suffix}.webp"
            im.resize((width, round(h * width / w)), Image.LANCZOS).save(dest, quality=80, method=6)
        og = ImageOps.fit(im, (1200, 630), Image.LANCZOS)
        og.save(out_dir / f"{item['slug']}-og.jpg", quality=82, optimize=True, progressive=True)
    item["img"] = {
        "small": f"{base}-640.webp",
        "large": f"{base}-1280.webp",
        "og": f"{base}-og.jpg",
        "w": large_w,
        "h": round(h * large_w / w),
        "sw": small_w,
        "vertical": vertical,
    }


# ---------------------------------------------------------------- szablony

def layout(cfg, *, path, title, description, body, current=None, og_image=None, head_extra="", noindex=False):
    depth = path.count("/")
    standalone = path == "404.html"  # 404 jest serwowana pod dowolnym adresem -> wszystko wbudowane w plik
    r = "/" if standalone else "../" * depth
    logo = cfg["_logo_data"] if standalone else f"{r}images/logo.webp"
    site = cfg["url"].rstrip("/")
    canonical = site + "/" + (path[: -len("index.html")] if path.endswith("index.html") else path)
    full_title = cfg["name"] if title == cfg["name"] else f"{title} | {cfg['name']}"
    og = og_image if (og_image or "").startswith("http") else site + "/" + (og_image or "images/og-image.jpg")

    nav_links = [(f"{r}{c['folder']}/", c["nav"], c["folder"]) for c in cfg["categories"]]
    nav_links += [(f"{r}index.html#o-nas", "O nas", "o-nas"), (f"{r}index.html#kontakt", "Kontakt", "kontakt")]
    nav = "\n        ".join(
        '<a href="%s"%s>%s</a>' % (href, ' aria-current="page"' if key == current else "", esc(label))
        for href, label, key in nav_links
    )
    robots = '<meta name="robots" content="noindex">' if noindex else f'<link rel="canonical" href="{canonical}">'
    email = esc(cfg["email"])
    yt_link = f'<a href="{esc(cfg["youtube"])}" target="_blank" rel="noopener">YouTube</a>' if cfg.get("youtube") else ""
    if standalone:
        head_assets = f"<style>{cfg['_css_text']}</style>\n  <script>{FIX_ROOT_JS}</script>"
    else:
        head_assets = (f'<link rel="stylesheet" href="{r}assets/style.css?v={cfg["_v_css"]}">\n'
                       f'  <script src="{r}assets/site.js?v={cfg["_v_js"]}" defer></script>')

    return f"""<!DOCTYPE html>
<html lang="pl">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>{esc(full_title)}</title>
  <meta name="description" content="{esc(description)}">
  {robots}
  <meta name="theme-color" content="#4a3fe0">
  <link rel="icon" href="{r}favicon.ico" sizes="16x16 32x32 48x48 64x64">
  <link rel="icon" type="image/png" sizes="192x192" href="{r}images/icon-192.png">
  <link rel="apple-touch-icon" href="{r}images/apple-touch-icon.png">
  <link rel="manifest" href="{r}site.webmanifest">
  <meta property="og:type" content="website">
  <meta property="og:locale" content="pl_PL">
  <meta property="og:site_name" content="{esc(cfg['name'])}">
  <meta property="og:title" content="{esc(full_title)}">
  <meta property="og:description" content="{esc(description)}">
  <meta property="og:url" content="{canonical}">
  <meta property="og:image" content="{og}">
  <meta name="twitter:card" content="summary_large_image">
  {head_assets}
  <script type="speculationrules">{{"prefetch":[{{"where":{{"href_matches":"/*"}},"eagerness":"moderate"}}]}}</script>{head_extra}
</head>
<body>
  <a class="skip-link" href="#main">Przejdź do treści</a>
  <header class="site-header">
    <div class="container header-inner">
      <a class="logo" href="{r}index.html">
        <img src="{logo}" alt="" width="44" height="44">
        <span>{esc(cfg['name'])}</span>
      </a>
      <nav class="site-nav" aria-label="Główna nawigacja">
        {nav}
      </nav>
    </div>
  </header>

  <main id="main">
{body}
  </main>

  <footer class="site-footer">
    <div class="container footer-inner">
      <div class="footer-brand">
        <img src="{logo}" alt="" width="32" height="32">
        <span>{esc(cfg['name'])} © <span data-year>{date.today().year}</span></span>
      </div>
      <div class="footer-links">
        {yt_link}<a href="mailto:{email}">{email}</a>
      </div>
    </div>
  </footer>
</body>
</html>
"""


def src(r, path):
    return path if path.startswith("http") else r + path


def type_badge(item, cls="badge type"):
    t = TYPES.get("map", {}).get(item.get("type"))
    return f'<span class="{cls}">{esc(t["badge"])}</span>' if t else ""


def card(item, r, lazy=True):
    cat = item["category"]
    img = item.get("img")
    media_cls = "card-media"
    if img:
        srcset = (f' srcset="{src(r, img["small"])} {img["sw"]}w, {src(r, img["large"])} {img["w"]}w"'
                  if img.get("w") and img["small"] != img["large"] else "")
        media = (
            f'<img src="{src(r, img["small"])}"{srcset} sizes="(min-width: 1100px) 340px, (min-width: 640px) 50vw, 100vw" '
            'alt="" width="640" height="360"' + (' loading="lazy"' if lazy else "") + ' decoding="async">'
        )
        if img.get("vertical"):
            media_cls += " vertical"
            media = f'<span class="bg" style="background-image: url(\'{src(r, img["small"])}\')"></span>' + media
    else:
        media_cls += " placeholder"
        media = f'<img src="{r}images/logo.webp" alt="" width="96" height="96" loading="lazy">'
    badge_cls = "badge done" if cat.get("badgeStyle") == "done" else "badge"
    desc = f'\n              <p class="muted">{esc(item["desc"])}</p>' if item.get("desc") else ""
    data_type = f' data-type="{esc(item["type"])}"' if item.get("type") else ""
    if item.get("has_page"):
        open_tag, close_tag = f'<a class="card" href="{r}{item["url"]}"{data_type}>', "</a>"
    else:
        open_tag, close_tag = f'<div class="card static"{data_type}>', "</div>"
    return f"""          {open_tag}
            <div class="{media_cls}">{media}</div>
            <span class="{badge_cls}">{esc(cat['badge'])}</span>{type_badge(item)}
            <div class="card-body">
              <h3>{esc(item['title'])}</h3>{desc}
            </div>
          {close_tag}"""


def grid(items, r, empty="Wkrótce pojawią się tu nowe projekty.", lazy=True):
    if not items:
        return f'        <div class="grid"><p class="status">{esc(empty)}</p></div>'
    cards = "\n".join(card(i, r, lazy) for i in items)
    return f'        <div class="grid">\n{cards}\n        </div>'


def filters(items):
    """Przyciski Wszystkie / Oficjalne / Fanowskie (gdy w kategorii są różne typy)."""
    present = [t for t in TYPES.get("map", {}) if any(i.get("type") == t for i in items)]
    if len(present) < 2:
        return ""
    buttons = ['<button type="button" class="chip" data-filter="" aria-pressed="true">Wszystkie</button>']
    buttons += [f'<button type="button" class="chip" data-filter="{esc(t)}" aria-pressed="false">{esc(TYPES["map"][t]["filter"])}</button>'
                for t in present]
    return '      <div class="filters" role="group" aria-label="Filtruj projekty" hidden>' + "".join(buttons) + "</div>"


def role_icon(role):
    role = (role or "").lower()
    for key, icon in ROLE_ICONS:
        if key in role:
            return icon
    return None


def icon_src(name, r):
    if not name:
        return None
    if "/" in name or "." in name:
        return r + name.lstrip("./").replace("../", "")
    return f"{r}images/{name}.webp"


def people_section(heading, members, r, default_icon=None):
    order, by_name = [], {}
    for m in members or []:
        if isinstance(m, str):
            m = {"name": m}
        if not isinstance(m, dict):
            continue
        # "Adrian Kolos, Patryk Kuczyński" = dwie osoby z tą samą rolą
        for name in str(m.get("name", "")).split(","):
            name = name.strip()
            if not name:
                continue
            if name not in by_name:
                by_name[name] = {"name": name, "icons": {}, "roles": []}
                order.append(by_name[name])
            p = by_name[name]
            role = m.get("role")
            icon = m.get("icon") or role_icon(role) or default_icon
            if icon:
                p["icons"].setdefault(icon, [])
                if role and role not in p["icons"][icon]:
                    p["icons"][icon].append(role)
            if role and role not in p["roles"]:
                p["roles"].append(role)
    if not order:
        return ""
    rows = []
    for p in order:
        icons = "".join(
            '<img src="%s" alt="" width="26" height="26" loading="lazy"%s>'
            % (icon_src(i, r), ' title="%s"' % esc(", ".join(roles)) if roles else "")
            for i, roles in p["icons"].items()
        )
        icons = f'<span class="icons">{icons}</span>' if icons else ""
        roles = f'<span class="role"> — {esc(", ".join(p["roles"]))}</span>' if p["roles"] else ""
        rows.append(f"            <li>{icons}<span><strong>{esc(p['name'])}</strong>{roles}</span></li>")
    return f"""        <section class="details">
          <h2>{esc(heading)}</h2>
          <ul class="people">
{chr(10).join(rows)}
          </ul>
        </section>"""


def rich_text(text):
    """Zwykły tekst -> akapity; puste linie dzielą akapity, linki są klikalne."""
    paras = [p.strip() for p in re.split(r"\n\s*\n", str(text)) if p.strip()]
    out = []
    for p in paras:
        p = esc(p)
        p = re.sub(r"(https?://[^\s<]+)", r'<a href="\1" target="_blank" rel="noopener">\1</a>', p)
        out.append(f"<p>{p}</p>")
    return "".join(out)


def youtube_id(url):
    m = re.search(r"(?:youtu\.be/|v=|embed/|shorts/)([\w-]{11})", url or "")
    return m.group(1) if m else None


def media_block(item, r):
    img = item.get("img")
    vid = item.get("video_id")
    img_tag = ""
    if img:
        srcset = (f' srcset="{src(r, img["small"])} {img["sw"]}w, {src(r, img["large"])} {img["w"]}w"'
                  if img.get("w") and img["small"] != img["large"] else "")
        dims = f' width="{img["w"]}" height="{img["h"]}"' if img.get("w") else ""
        img_tag = (f'<img src="{src(r, img["large"])}"{srcset} sizes="(min-width: 900px) 520px, 100vw" '
                   f'alt="{esc(item["title"])}"{dims} fetchpriority="high" decoding="async">')
    if vid:
        url = esc(item.get("video") or item.get("videoUrl"))
        short = " short" if item.get("is_short") else ""
        return f"""        <div class="project-media{short}">
          <button class="video{short}" type="button" data-video="{vid}" aria-label="Odtwórz wideo: {esc(item['title'])}">
            {img_tag}
            <span class="play" aria-hidden="true"></span>
          </button>
          <a class="video-link" href="{url}" target="_blank" rel="noopener">Obejrzyj na YouTube ↗</a>
        </div>"""
    if img_tag:
        return f'        <div class="project-media">\n          {img_tag}\n        </div>'
    return ""


# ---------------------------------------------------------------- strony

def build_pages(cfg, cats):
    pages = {}
    r0 = ""

    # strona główna
    sections = []
    for cat, items in cats:
        more = f'<a href="{cat["folder"]}/">Zobacz wszystkie ({len(items)}) →</a>' if items else ""
        sections.append(f"""    <section id="{cat['folder']}" class="section">
      <div class="container">
        <div class="section-head">
          <h2>{esc(cat['homeTitle'])}</h2>
          {more}
        </div>
{grid(items[: cfg.get('homeLimit', 3)], r0)}
      </div>
    </section>""")
    about = "\n            ".join(
        '<p%s>%s</p>' % (' class="muted"' if i else "", esc(p)) for i, p in enumerate(cfg.get("about", []))
    )
    email = esc(cfg["email"])
    yt_button = (f'<a class="button secondary" href="{esc(cfg["youtube"])}" target="_blank" rel="noopener">Kanał YouTube ↗</a>'
                 if cfg.get("youtube") else "")
    first = cats[0][0]["folder"] if cats else ""
    jsonld = json.dumps({
        "@context": "https://schema.org", "@type": "Organization", "name": cfg["name"],
        "url": cfg["url"].rstrip("/") + "/", "logo": cfg["url"].rstrip("/") + "/images/icon-512.png",
        "email": cfg["email"], "description": cfg["description"],
        **({"sameAs": [cfg["youtube"]]} if cfg.get("youtube") else {}),
    }, ensure_ascii=False)
    body = f"""    <section class="hero">
      <div class="container hero-inner">
        <div>
          <p class="muted">{esc(cfg.get('eyebrow'))}</p>
          <h1><span class="gradient-text">{esc(cfg['name'])}</span></h1>
          <p class="lead">{esc(cfg.get('tagline'))}</p>
          <div class="actions">
            <a class="button" href="#{first}">Nasze projekty</a>
            <a class="button secondary" href="#kontakt">Kontakt</a>
          </div>
        </div>
        <img class="hero-logo" src="images/logo-560.webp" alt="Logo {esc(cfg['name'])} – płyta winylowa z mikrofonem" width="280" height="280" fetchpriority="high">
      </div>
    </section>

{chr(10).join(sections)}

    <section id="o-nas" class="section">
      <div class="container">
        <h2>O nas</h2>
        <div class="panel about">
          <div class="bio">
            {about}
          </div>
          <div id="kontakt" class="contact">
            <h3>Kontakt</h3>
            <p><a href="mailto:{email}">{email}</a></p>
            <div class="actions center">
              <a class="button" href="mailto:{email}">Napisz wiadomość</a>
              {yt_button}
            </div>
          </div>
        </div>
      </div>
    </section>"""
    pages["index.html"] = layout(cfg, path="index.html", title=cfg["name"], description=cfg["description"], body=body,
                                 head_extra=f'\n  <script type="application/ld+json">{jsonld}</script>')

    for cat, items in cats:
        f = cat["folder"]
        # lista w kategorii
        body = f"""    <div class="container section">
      <h1>{esc(cat['pageTitle'])}</h1>
{filters(items)}
{grid(items, '../', lazy=False)}
    </div>"""
        pages[f"{f}/index.html"] = layout(cfg, path=f"{f}/index.html", title=cat["pageTitle"],
                                          description=cat["pageDescription"], body=body, current=f)
        # strony projektów
        for idx, item in enumerate(items):
            if not item.get("has_page"):
                continue
            r = "../"
            tags = f'<span class="tag">{esc(cat["badge"])}</span>' + type_badge(item, "tag")
            info = [
                f"          <h1>{esc(item['title'])}</h1>",
                f'          <p class="tags">{tags}</p>',
                f'          <p class="project-meta muted">{esc(item["desc"])}</p>' if item.get("desc") else "",
                people_section("Obsada", item.get("cast"), r, default_icon="mikrofon"),
                people_section("Ekipa projektu", item.get("team"), r),
                f'        <section class="details">\n          <h2>Szczegóły</h2>\n          {rich_text(item["details"])}\n        </section>'
                if item.get("details") else "",
            ]
            others = [i for i in items[idx + 1:] + items[:idx] if i.get("has_page")][:3]
            more = ""
            if others:
                more = f"""      <section class="section related">
        <h2>Inne: {esc(cat['nav'].lower())}</h2>
{grid(others, r)}
      </section>"""
            body = f"""    <div class="container">
      <nav class="breadcrumb" aria-label="Ścieżka"><a href="../index.html">Strona główna</a> / <a href="./">{esc(cat['nav'])}</a></nav>
      <article class="project">
{media_block(item, r)}
        <div class="project-info">
{chr(10).join(x for x in info if x)}
        </div>
      </article>
{more}
    </div>"""
            desc = item.get("seo") or f"{item['title']} – {item.get('desc', '')}. {cfg['name']}."
            pages[item["url"]] = layout(cfg, path=item["url"], title=item["title"], description=desc, body=body,
                                        current=f, og_image=(item.get("img") or {}).get("og"))

    # 404
    body = """    <div class="container not-found">
      <p class="code gradient-text">404</p>
      <h1>Nie znaleziono strony</h1>
      <p class="muted">Strona, której szukasz, nie istnieje albo została przeniesiona.</p>
      <div class="actions">
        <a class="button" href="/">Strona główna</a>
      </div>
    </div>"""
    pages["404.html"] = layout(cfg, path="404.html", title="Nie znaleziono strony",
                               description="Ta strona nie istnieje.", body=body, noindex=True)
    return pages


def sitemap(cfg, pages):
    site = cfg["url"].rstrip("/")
    urls = []
    for path in pages:
        if path == "404.html":
            continue
        loc = site + "/" + (path[: -len("index.html")] if path.endswith("index.html") else path)
        urls.append(f"  <url><loc>{esc(loc)}</loc></url>")
    return ('<?xml version="1.0" encoding="UTF-8"?>\n'
            '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n' + "\n".join(urls) + "\n</urlset>\n")


def file_hash(path):
    return hashlib.md5(path.read_bytes()).hexdigest()[:8]


# ---------------------------------------------------------------- start

def main():
    cfg = load_json(ROOT / "site.config.json")
    if not cfg:
        report_and_exit()
    TYPES["map"] = cfg.get("types", {})
    cfg["_v_css"] = file_hash(STATIC / "assets" / "style.css")
    cfg["_v_js"] = file_hash(STATIC / "assets" / "site.js")
    css = (STATIC / "assets" / "style.css").read_text(encoding="utf-8")
    css = re.sub(r"/\*.*?\*/", "", css, flags=re.S)
    cfg["_css_text"] = re.sub(r"\s*\n\s*", "", css)
    import base64
    cfg["_logo_data"] = "data:image/webp;base64," + base64.b64encode((STATIC / "images" / "logo.webp").read_bytes()).decode()

    if OUT.exists():
        shutil.rmtree(OUT)
    shutil.copytree(STATIC, OUT)

    cats = []
    seen = set()
    for cat in cfg["categories"]:
        if cat["folder"] in seen:
            fail(f"site.config.json: kategoria \"{cat['folder']}\" jest wpisana dwa razy")
        seen.add(cat["folder"])
        items = load_category(cat)
        for item in items:
            process_image(item)
        cats.append((cat, items))

    pages = build_pages(cfg, cats)
    report_and_exit(only_if_errors=True)

    for path, content in pages.items():
        dest = OUT / path
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_text(content, encoding="utf-8")
    (OUT / "sitemap.xml").write_text(sitemap(cfg, pages), encoding="utf-8")

    total = sum(len(i) for _, i in cats)
    yt_missing = [i["title"] for _, items in cats for i in items
                  if (i.get("img") or {}).get("small", "").startswith("https://i.ytimg.com")]
    if yt_missing:
        print("Uwaga: nie udało się pobrać miniatur z YouTube (brak internetu?) – strona użyje ich bezpośrednio z YouTube:")
        for t in yt_missing:
            print("  - " + t)
    print(f"Gotowe! Stron: {len(pages)}, projektów: {total} -> {OUT.relative_to(ROOT)}/")
    if Image is None:
        print("Uwaga: brak Pillow – obrazki skopiowano bez optymalizacji (pip install pillow).")


def report_and_exit(only_if_errors=False):
    if errors:
        print("Nie udało się zbudować strony:\n", file=sys.stderr)
        for e in errors:
            print("  ✗ " + e, file=sys.stderr)
        sys.exit(1)
    if not only_if_errors:
        sys.exit(1)


def serve(port=8000):
    import functools
    import http.server

    handler = functools.partial(http.server.SimpleHTTPRequestHandler, directory=str(OUT))
    print(f"Podgląd: http://localhost:{port}  (Ctrl+C kończy)")
    http.server.ThreadingHTTPServer(("127.0.0.1", port), handler).serve_forever()


if __name__ == "__main__":
    main()
    if "--serve" in sys.argv:
        serve()
