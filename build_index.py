#!/usr/bin/env python3
"""Indexa las recetas de varomeando.es para la rotacion de Reels.

La API REST de WordPress no expone el tipo de contenido de las recetas (osetin_recipe), asi que se leen sus
sitemaps y, de cada pagina, el JSON-LD schema.org/Recipe. Salida:
  data/index.json         lista ligera [{id, slug, url, title, image}] ordenada por id
  data/recipes/<id>.json  receta completa (ingredientes, pasos, tiempos) para el prompt de Gemini

Solo se descargan las paginas nuevas o modificadas (lastmod del sitemap). Variable SECTIONS: secciones de la URL a
incluir, por defecto solo recetathermomix (las otras son versiones Mambo y tradicional de los mismos platos).
"""
import html
import json
import os
import re
import sys
import time
import urllib.request

BASE = "https://varomeando.es"
SECTIONS = [s.strip() for s in os.environ.get("SECTIONS", "recetathermomix").split(",") if s.strip()]
UA = "Mozilla/5.0 (compatible; VaromeandoReelsBot/1.0; +https://github.com/franmrr7-ctrl/reels-varomeando)"
DELAY = float(os.environ.get("DELAY", "0.5"))
OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data")


def fetch(url, tries=3):
    for i in range(tries):
        try:
            req = urllib.request.Request(url, headers={"User-Agent": UA})
            with urllib.request.urlopen(req, timeout=40) as r:
                return r.read().decode("utf-8", "ignore")
        except Exception as e:  # noqa: BLE001
            if i == tries - 1:
                raise
            time.sleep(2 * (i + 1))


def clean(t):
    t = re.sub(r"<[^>]+>", " ", html.unescape(str(t or "")))
    return re.sub(r"\s+", " ", t).strip()


def sitemap_urls():
    idx = fetch(f"{BASE}/sitemap_index.xml")
    maps = [m for m in re.findall(r"<loc>([^<]+)</loc>", idx) if "osetin_recipe" in m]
    found = {}
    for m in maps:
        xml = fetch(m)
        for blk in re.findall(r"<url>(.*?)</url>", xml, re.S):
            loc = re.search(r"<loc>([^<]+)</loc>", blk)
            if not loc:
                continue
            url = loc.group(1).strip()
            parts = url.replace(BASE, "").strip("/").split("/")
            if len(parts) < 2 or parts[0] not in SECTIONS:
                continue
            lm = re.search(r"<lastmod>([^<]+)</lastmod>", blk)
            img = re.search(r"<image:loc>([^<]+)</image:loc>", blk)
            found[url] = {"lastmod": lm.group(1) if lm else "", "image": img.group(1) if img else ""}
        time.sleep(DELAY)
    return found


def find_recipe(node):
    if isinstance(node, dict):
        t = node.get("@type")
        if t == "Recipe" or (isinstance(t, list) and "Recipe" in t):
            return node
        for v in node.values():
            r = find_recipe(v)
            if r:
                return r
    elif isinstance(node, list):
        for v in node:
            r = find_recipe(v)
            if r:
                return r
    return None


def steps_of(instr):
    out = []
    for s in instr or []:
        if isinstance(s, dict) and s.get("itemListElement"):
            out += steps_of(s["itemListElement"])
        elif isinstance(s, dict):
            txt = clean(s.get("text") or s.get("name"))
            if txt:
                out.append(txt)
        elif isinstance(s, str) and clean(s):
            out.append(clean(s))
    return out


def parse(url, meta):
    page = fetch(url)
    pid = re.search(r"postid-(\d+)", page) or re.search(r"[?&]p=(\d+)", page)
    rec = None
    for b in re.findall(r'<script type="application/ld\+json"[^>]*>(.*?)</script>', page, re.S):
        try:
            rec = find_recipe(json.loads(b))
        except Exception:  # noqa: BLE001
            continue
        if rec:
            break
    if not pid or not rec:
        return None
    og = re.search(r'property="og:image"\s+content="([^"]+)"', page)
    image = (og.group(1) if og else "") or meta.get("image", "")
    ing = [clean(i) for i in rec.get("recipeIngredient", []) if clean(i)]
    steps = steps_of(rec.get("recipeInstructions"))
    if not image.startswith("http") or len(ing) < 2 or len(steps) < 2:
        return None
    return {
        "id": int(pid.group(1)),
        "slug": url.rstrip("/").split("/")[-1],
        "url": url,
        "title": clean(rec.get("name")),
        "description": clean(rec.get("description")),
        "image": image,
        "prepTime": rec.get("prepTime", ""),
        "cookTime": rec.get("cookTime", ""),
        "totalTime": rec.get("totalTime", ""),
        "yield": clean(rec.get("recipeYield") if not isinstance(rec.get("recipeYield"), list) else " ".join(rec["recipeYield"])),
        "category": clean(rec.get("recipeCategory")),
        "ingredients": ing,
        "steps": steps,
        "lastmod": meta.get("lastmod", ""),
    }


def main():
    os.makedirs(os.path.join(OUT, "recipes"), exist_ok=True)
    idx_path = os.path.join(OUT, "index.json")
    old = {}
    if os.path.exists(idx_path):
        for r in json.load(open(idx_path, encoding="utf-8")):
            old[r["url"]] = r
    urls = sitemap_urls()
    print(f"{len(urls)} URLs en los sitemaps ({', '.join(SECTIONS)})")
    index, fetched, skipped = {}, 0, 0
    for url, meta in sorted(urls.items()):
        prev = old.get(url)
        f = os.path.join(OUT, "recipes", f"{prev['id']}.json") if prev else None
        if prev and prev.get("lastmod") == meta["lastmod"] and os.path.exists(f):
            index[url] = prev
            continue
        try:
            rec = parse(url, meta)
        except Exception as e:  # noqa: BLE001
            print("ERROR", url, e)
            if prev:
                index[url] = prev  # conserva la entrada anterior si la web falla un momento
            continue
        time.sleep(DELAY)
        if not rec:
            skipped += 1
            print("omitida (sin JSON-LD completo o sin foto):", url)
            continue
        fetched += 1
        json.dump(rec, open(os.path.join(OUT, "recipes", f"{rec['id']}.json"), "w", encoding="utf-8"),
                  ensure_ascii=False, indent=1)
        index[url] = {"id": rec["id"], "slug": rec["slug"], "url": url, "title": rec["title"],
                      "image": rec["image"], "lastmod": meta["lastmod"]}
    if len(index) < 20:
        sys.exit(f"Indice sospechosamente pequeno ({len(index)}); no se sobrescribe nada.")
    rows = sorted(index.values(), key=lambda r: r["id"])
    # elimina fichas de recetas que ya no estan
    keep = {f"{r['id']}.json" for r in rows}
    for fn in os.listdir(os.path.join(OUT, "recipes")):
        if fn not in keep:
            os.remove(os.path.join(OUT, "recipes", fn))
    json.dump(rows, open(idx_path, "w", encoding="utf-8"), ensure_ascii=False, separators=(",", ":"))
    print(f"indice: {len(rows)} recetas ({fetched} descargadas, {skipped} omitidas)")


if __name__ == "__main__":
    main()
