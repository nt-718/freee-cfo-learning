# -*- coding: utf-8 -*-
import re
import time
import xml.etree.ElementTree as ET
from pathlib import Path

import requests
from bs4 import BeautifulSoup
from markdownify import markdownify as md

BASE_URL = "https://www.freee.co.jp"
OUTPUT_DIR = Path("kb")
WAIT_SEC = 1.0

EXCLUDE_SUBCATEGORIES = {
    "タグから記事を探す",
    "無料ビジネステンプレート集",
}

session = requests.Session()
session.headers.update({
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/120.0.0.0 Safari/537.36"
    ),
})


def fetch(url):
    resp = session.get(url, timeout=30)
    resp.raise_for_status()
    resp.encoding = "utf-8"
    return resp.text


def build_category_map():
    html = fetch(f"{BASE_URL}/kb/")
    soup = BeautifulSoup(html, "html.parser")
    mapping = {}
    for box in soup.select("h3.wwwfreee-category-box__title a"):
        href = box.get("href", "")
        title = box.get_text(strip=True)
        slug = href.rstrip("/").split("/")[-1]
        if slug:
            mapping[slug] = title
    return mapping


def get_category_structure(category_slug):
    url = f"{BASE_URL}/kb/{category_slug}/"
    html = fetch(url)
    soup = BeautifulSoup(html, "html.parser")

    subcategories = []
    for row in soup.select("div.wwwfreee-categorypost-items__row"):
        title_el = row.select_one("h3.wwwfreee-categorypost-items__title")
        if not title_el:
            continue
        sub_name = title_el.get_text(strip=True)
        if sub_name in EXCLUDE_SUBCATEGORIES:
            continue
        articles = []
        for a in row.select("a.wwwfreee-categorypost-items-list__link"):
            href = a.get("href", "")
            text = a.get_text(strip=True)
            if href and text:
                full_url = href if href.startswith("http") else BASE_URL + href
                articles.append({"url": full_url, "title": text})
        if articles:
            subcategories.append({"name": sub_name, "articles": articles})

    # Fallback: if no subcategory structure found, collect article links directly
    if not subcategories:
        seen = set()
        articles = []
        prefix = f"/kb/{category_slug}/"
        for a in soup.select(f"a[href*='{prefix}']"):
            href = a.get("href", "").rstrip("/")
            # Skip links to the category page itself
            if href.rstrip("/") == f"/kb/{category_slug}":
                continue
            if href in seen:
                continue
            seen.add(href)
            full_url = href if href.startswith("http") else BASE_URL + href + "/"
            articles.append({"url": full_url, "title": ""})
        if articles:
            subcategories.append({"name": "記事一覧", "articles": articles})

    return subcategories


def sanitize_filename(name):
    name = name.replace("/", "\uff0f")
    name = name.replace("\\", "\uff3c")
    name = name.replace(":", "\uff1a")
    name = name.replace("*", "\uff0a")
    name = name.replace("?", "\uff1f")
    name = name.replace('"', "\u201d")
    name = name.replace("<", "\uff1c")
    name = name.replace(">", "\uff1e")
    name = name.replace("|", "\uff5c")
    name = name.replace("\n", " ")
    return name.strip()


def scrape_article(url):
    html = fetch(url)

    # Handle JS redirects (may be chained)
    for _ in range(5):
        redirect_match = re.search(r'window\.location\.href="([^"]+)"', html)
        if not redirect_match:
            break
        url = redirect_match.group(1)
        html = fetch(url)

    soup = BeautifulSoup(html, "html.parser")

    title_el = soup.select_one("h1.wwwfreee-blogpost__title")
    if not title_el:
        return None
    title = title_el.get_text(strip=True)

    date_el = soup.select_one(".kb-article-date time")
    last_updated = date_el.get("datetime", "") if date_el else ""

    content_el = soup.select_one("div.blog-post-content.wwwfreee-blogpost__content")
    if not content_el:
        return None

    for tag in content_el.select(
        ".kbArticleProfile-articleHead, .kb-article-date, "
        "script, style, .ncms-mod-adarea, .wwwfreee-blogpost__cta, "
        ".wwwfreee-blogpost__related, .wwwfreee-blogpost__share"
    ):
        tag.decompose()

    content_md = md(str(content_el), heading_style="ATX", strip=["img"])
    content_md = re.sub(r"\n{3,}", "\n\n", content_md).strip()

    return {
        "title": title,
        "last_updated": last_updated,
        "url": url,
        "content": content_md,
    }


def save_article(dir_path, seq, article):
    dir_path.mkdir(parents=True, exist_ok=True)

    file_name = f"{seq:03d}_{sanitize_filename(article['title'])}.md"
    file_path = dir_path / file_name

    header = f"# {article['title']}\n\n"
    if article["last_updated"]:
        header += f"最終更新日: {article['last_updated']}  \n"
    header += f"出典: {article['url']}\n\n---\n\n"

    file_path.write_text(header + article["content"], encoding="utf-8")
    return file_path


def scrape_category(category_slug):
    print("カテゴリマップを構築中...")
    cat_map = build_category_map()
    category_name = cat_map.get(category_slug, category_slug)
    print(f"カテゴリ: {category_name} ({category_slug})")

    print("カテゴリページからサブカテゴリ構造を取得中...")
    subcategories = get_category_structure(category_slug)

    total = sum(len(sc["articles"]) for sc in subcategories)
    print(f"サブカテゴリ: {len(subcategories)}件, 記事合計: {total}件")

    cat_dir = OUTPUT_DIR / sanitize_filename(category_name)
    success = 0
    fail = 0
    done = 0

    for si, subcat in enumerate(subcategories, 1):
        sub_dir_name = f"{si:02d}_{sanitize_filename(subcat['name'])}"
        sub_dir = cat_dir / sub_dir_name
        print(f"\n[{si:02d}] {subcat['name']} ({len(subcat['articles'])}件)")

        for ai, art_info in enumerate(subcat["articles"], 1):
            done += 1
            try:
                article = scrape_article(art_info["url"])
                if article:
                    path = save_article(sub_dir, ai, article)
                    print(f"  {done}/{total} OK {ai:03d}_{article['title']}")
                    success += 1
                else:
                    print(f"  {done}/{total} NG: {art_info['url']}")
                    fail += 1
            except Exception as e:
                print(f"  {done}/{total} ERR: {art_info['url']} - {e}")
                fail += 1
            time.sleep(WAIT_SEC)

    print(f"\n完了: 成功 {success}, 失敗 {fail}")

def scrape_all_categories():
    print("全カテゴリを取得中...")
    cat_map = build_category_map()
    total_categories = len(cat_map)
    print(f"合計 {total_categories} 個のカテゴリが見つかりました。")

    for i, category_slug in enumerate(cat_map.keys(), 1):
        print(f"\n========================================")
        print(f"[{i}/{total_categories}] カテゴリ開始: {category_slug}")
        print(f"========================================")
        try:
            scrape_category(category_slug)
        except Exception as e:
            print(f"カテゴリ '{category_slug}' の取得中にエラーが発生しました: {e}")
            continue

if __name__ == "__main__":
    import sys

    slug = sys.argv[1] if len(sys.argv) > 1 else "all"
    if slug == "all":
        scrape_all_categories()
    else:
        scrape_category(slug)
