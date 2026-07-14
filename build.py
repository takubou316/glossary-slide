import datetime
import json
import pathlib
import re
import subprocess
import sys

TAG_RE = re.compile(r"<[^>]+>")


def strip_tags(text: str) -> str:
    """Remove inline markup (e.g. term-link <a> tags) so the message can be
    safely reused as plain text inside an HTML attribute or another <a>."""
    return TAG_RE.sub("", text)

ROOT = pathlib.Path(__file__).parent
TEMPLATE = (ROOT / "template.html").read_text(encoding="utf-8")
PLAYER_TEMPLATE = (ROOT / "player_template.html").read_text(encoding="utf-8")


def get_created_at(term_dir: pathlib.Path) -> str:
    """Return an ISO date approximating when this term was created, based on
    the oldest git commit that touched its group.json (or meta.json for
    single-slide terms). Falls back to "now" for not-yet-committed terms, so
    brand new drafts sort as the newest until they're committed."""
    marker = term_dir / "group.json"
    if not marker.exists():
        marker = term_dir / "meta.json"
    try:
        result = subprocess.run(
            ["git", "log", "--format=%aI", "--", str(marker.relative_to(ROOT))],
            cwd=ROOT, capture_output=True, text=True, check=True,
        )
        lines = [line for line in result.stdout.strip().splitlines() if line]
        if lines:
            return lines[-1]
    except Exception:
        pass
    return datetime.datetime.now().astimezone().isoformat()


def scope_css(css_text: str, scope_selector: str) -> str:
    """Prefix every selector in a flat CSS block with scope_selector, so that
    class names reused across variants (e.g. .tok) don't leak between panels
    when multiple variants' CSS is concatenated into one <style> block."""
    scoped_rules = []
    for rule in css_text.split("}"):
        rule = rule.strip()
        if not rule or "{" not in rule:
            continue
        selectors, body = rule.split("{", 1)
        scoped_selectors = ", ".join(
            f"{scope_selector} {s.strip()}" for s in selectors.split(",")
        )
        scoped_rules.append(f"{scoped_selectors} {{{body}}}")
    return "\n".join(scoped_rules)


def build_single(term_dir: pathlib.Path) -> tuple[pathlib.Path, str, str, str, str]:
    meta = json.loads((term_dir / "meta.json").read_text(encoding="utf-8"))
    diagram_css = (term_dir / "diagram.css").read_text(encoding="utf-8")
    diagram_html = (term_dir / "diagram.html").read_text(encoding="utf-8")

    html = (
        TEMPLATE
        .replace("{{TERM}}", meta["term"])
        .replace("{{MESSAGE}}", meta["message"])
        .replace("{{DIAGRAM_CSS}}", diagram_css)
        .replace("{{DIAGRAM_HTML}}", diagram_html)
    )

    out_dir = ROOT / "output"
    out_dir.mkdir(exist_ok=True)
    out_path = out_dir / f"{meta['slug']}.html"
    out_path.write_text(html, encoding="utf-8")
    return out_path, meta["term"], meta["message"], meta.get("yomi", ""), meta.get("category", "その他")


def build_group(term_dir: pathlib.Path) -> tuple[pathlib.Path, str, str, str, str]:
    group = json.loads((term_dir / "group.json").read_text(encoding="utf-8"))

    tab_buttons = []
    panels = []
    all_css = []
    intro_message = None

    for i, variant in enumerate(group["variants"]):
        vdir = term_dir / variant["id"]
        meta = json.loads((vdir / "meta.json").read_text(encoding="utf-8"))
        if i == 0:
            intro_message = meta["message"]
        diagram_css = (vdir / "diagram.css").read_text(encoding="utf-8")
        diagram_html = (vdir / "diagram.html").read_text(encoding="utf-8")
        eyebrow = meta.get("eyebrow", "今日のひとこと解説")
        active = " active" if i == 0 else ""

        tab_buttons.append(
            f'<button class="tab-btn{active}" data-variant="{variant["id"]}">{variant["label"]}</button>'
        )
        panels.append(
            f'<div class="slide{active}" id="panel-{variant["id"]}">\n'
            f'  <div class="eyebrow">{eyebrow}</div>\n'
            f'  <h1 class="term">{meta["term"]}</h1>\n'
            f'  <p class="message">{meta["message"]}</p>\n'
            f'  <div class="visual" aria-hidden="true">\n'
            f'    {diagram_html}\n'
            f'  </div>\n'
            f'</div>'
        )
        all_css.append(scope_css(diagram_css, f"#panel-{variant['id']}"))

    html = (
        PLAYER_TEMPLATE
        .replace("{{TITLE}}", group["title"])
        .replace("{{TAB_BUTTONS}}", "\n    ".join(tab_buttons))
        .replace("{{VARIANT_PANELS}}", "\n    ".join(panels))
        .replace("{{ALL_VARIANT_CSS}}", "\n".join(all_css))
    )

    out_dir = ROOT / "output"
    out_dir.mkdir(exist_ok=True)
    out_path = out_dir / f"{group['slug']}.html"
    out_path.write_text(html, encoding="utf-8")
    return out_path, group["title"], intro_message, group.get("yomi", ""), group.get("category", "その他")


def build(term_dir: pathlib.Path) -> tuple[pathlib.Path, str, str, str, str]:
    if (term_dir / "group.json").exists():
        return build_group(term_dir)
    return build_single(term_dir)


def build_index(entries: list[tuple[pathlib.Path, str, str, str, str, str]]) -> pathlib.Path:
    categories = sorted({category for _, _, _, _, _, category in entries})
    category_buttons = "\n      ".join(
        f'<button type="button" class="cat-btn" data-category="{cat}">{cat}</button>'
        for cat in categories
    )
    items = "\n".join(
        f'      <li class="item" data-title="{(title + " " + yomi).strip().lower()}" data-desc="{strip_tags(message).lower()}" data-created="{created_at}" data-category="{category}">\n'
        f'        <a href="{out_path.name}">\n'
        f'          <div class="item-title">{title}</div>\n'
        f'          <div class="item-desc">{strip_tags(message)}</div>\n'
        f'          <div class="item-category">{category}</div>\n'
        f'        </a>\n'
        f'      </li>'
        for out_path, title, message, yomi, created_at, category in sorted(entries, key=lambda e: e[1])
    )
    html = f"""<!DOCTYPE html>
<html lang="ja">
<head>
<meta charset="UTF-8">
<title>用語解説スライド一覧</title>
<style>
  body {{
    margin: 0;
    min-height: 100vh;
    display: flex;
    align-items: flex-start;
    justify-content: center;
    background: #EAE8E3;
    font-family: "Hiragino Sans", "Yu Gothic", "Segoe UI", sans-serif;
    padding: 60px 20px;
  }}
  .card {{
    background: #FAF9F5;
    border-radius: 24px;
    padding: 48px 56px;
    box-shadow: 0 8px 40px rgba(0,0,0,0.12);
    width: 560px;
  }}
  .title-row {{ display: flex; align-items: center; justify-content: space-between; margin-bottom: 24px; }}
  h1 {{ font-size: 28px; color: #262322; margin: 0; }}
  .create-link {{
    font-size: 14px;
    font-weight: 700;
    color: #D97757;
    text-decoration: none;
    padding: 8px 16px;
    border-radius: 999px;
    border: 2px solid #D97757;
    white-space: nowrap;
  }}
  .create-link:hover {{ background: #D97757; color: #FAF9F5; }}
  .search-box {{
    width: 100%;
    box-sizing: border-box;
    padding: 14px 18px;
    font-size: 17px;
    font-family: inherit;
    border: 2px solid #DDD9D2;
    border-radius: 14px;
    margin-bottom: 16px;
    color: #262322;
  }}
  .search-box:focus {{
    outline: none;
    border-color: #D97757;
  }}
  .sort-row {{ display: flex; gap: 8px; margin-bottom: 20px; }}
  .sort-btn {{
    appearance: none;
    -webkit-appearance: none;
    -moz-appearance: none;
    border: 2px solid #DDD9D2;
    background: transparent;
    color: #8A8681;
    font-family: inherit;
    font-size: 13px;
    font-weight: 700;
    padding: 8px 14px;
    border-radius: 999px;
    cursor: pointer;
    display: inline-flex;
    align-items: center;
    justify-content: center;
    line-height: 1;
    touch-action: manipulation;
  }}
  .sort-btn.active {{
    border-color: #D97757;
    background: #D97757;
    color: #FAF9F5;
  }}
  .cat-row {{ display: flex; flex-wrap: wrap; gap: 8px; margin-bottom: 20px; }}
  .cat-btn {{
    appearance: none;
    -webkit-appearance: none;
    -moz-appearance: none;
    border: 2px solid #DDD9D2;
    background: transparent;
    color: #8A8681;
    font-family: inherit;
    font-size: 13px;
    font-weight: 700;
    padding: 8px 14px;
    border-radius: 999px;
    cursor: pointer;
    display: inline-flex;
    align-items: center;
    justify-content: center;
    line-height: 1;
    touch-action: manipulation;
  }}
  .cat-btn.active {{
    border-color: #D97757;
    background: #D97757;
    color: #FAF9F5;
  }}
  ul {{ list-style: none; margin: 0; padding: 0; display: flex; flex-direction: column; gap: 14px; }}
  .item a {{
    display: block;
    text-decoration: none;
    padding: 16px 20px;
    border: 2px solid #D97757;
    border-radius: 14px;
  }}
  .item a:hover {{ background: #D97757; }}
  .item a:hover .item-title, .item a:hover .item-desc, .item a:hover .item-category {{ color: #FAF9F5; }}
  .item-title {{ font-size: 20px; font-weight: 700; color: #D97757; }}
  .item-desc {{ font-size: 14px; font-weight: 600; color: #8A8681; margin-top: 6px; }}
  .item-category {{ display: inline-block; font-size: 11px; font-weight: 700; color: #8A8681; margin-top: 10px; padding: 3px 10px; border: 1px solid #DDD9D2; border-radius: 999px; }}
  .item a:hover .item-category {{ border-color: #FAF9F5; }}
  .empty-note {{ display: none; color: #8A8681; font-size: 15px; padding: 8px 4px; }}
</style>
</head>
<body>
  <div class="card">
    <div class="title-row">
      <h1>今日のひとこと解説 一覧</h1>
      <a class="create-link" href="create.html">+ 新しい用語を作成</a>
    </div>
    <input type="text" class="search-box" id="search" placeholder="用語を検索...">
    <div class="cat-row" id="cat-row">
      <button type="button" class="cat-btn active" data-category="all">すべて</button>
      {category_buttons}
    </div>
    <div class="sort-row">
      <button type="button" class="sort-btn active" data-sort="alpha">アルファベット順</button>
      <button type="button" class="sort-btn" data-sort="new">新しい順</button>
    </div>
    <ul id="list">
{items}
    </ul>
    <div class="empty-note" id="empty-note">見つかりませんでした</div>
  </div>
  <script>
    // カタカナをひらがなに変換して、ひらがな/カタカナのどちらで入力しても
    // 同じ結果になるようにする（漢字の用語は各データの「よみ」で拾う）
    function kataToHira(text) {{
      return text.replace(/[ァ-ヶ]/g, function (ch) {{
        return String.fromCharCode(ch.charCodeAt(0) - 0x60);
      }});
    }}

    var search = document.getElementById('search');
    var list = document.getElementById('list');
    var items = [].slice.call(document.querySelectorAll('#list .item'));
    var emptyNote = document.getElementById('empty-note');
    var sortButtons = [].slice.call(document.querySelectorAll('.sort-btn'));
    var catButtons = [].slice.call(document.querySelectorAll('.cat-btn'));
    var currentSort = 'alpha';
    var currentCategory = 'all';

    items.forEach(function (item, i) {{
      item.dataset.titleNorm = kataToHira(item.dataset.title);
      item.dataset.descNorm = kataToHira(item.dataset.desc);
      item.dataset.orderAlpha = i;
    }});

    // 新しい順（作成日時が新しいものが先頭）のインデックスを事前に振っておく
    items.slice().sort(function (a, b) {{
      return (b.dataset.created || '').localeCompare(a.dataset.created || '');
    }}).forEach(function (item, i) {{
      item.dataset.orderNew = i;
    }});

    // タイトルの先頭一致 > タイトル内一致 > 説明文一致、の順で並べる
    function rank(item, q) {{
      if (item.dataset.titleNorm.indexOf(q) === 0) return 0;
      if (item.dataset.titleNorm.indexOf(q) !== -1) return 1;
      if (item.dataset.descNorm.indexOf(q) !== -1) return 2;
      return -1;
    }}

    function orderValue(item) {{
      return Number(currentSort === 'new' ? item.dataset.orderNew : item.dataset.orderAlpha);
    }}

    function render() {{
      var q = kataToHira(search.value.trim().toLowerCase());
      var ranked = items
        .map(function (item) {{ return {{ item: item, rank: rank(item, q) }}; }})
        .filter(function (r) {{ return r.rank !== -1; }})
        .filter(function (r) {{ return currentCategory === 'all' || r.item.dataset.category === currentCategory; }})
        .sort(function (a, b) {{
          if (a.rank !== b.rank) return a.rank - b.rank;
          return orderValue(a.item) - orderValue(b.item);
        }});

      items.forEach(function (item) {{ item.style.display = 'none'; }});
      ranked.forEach(function (r) {{
        r.item.style.display = '';
        list.appendChild(r.item);
      }});
      emptyNote.style.display = ranked.length === 0 ? 'block' : 'none';
    }}

    search.addEventListener('input', render);
    sortButtons.forEach(function (btn) {{
      btn.addEventListener('click', function () {{
        currentSort = btn.dataset.sort;
        sortButtons.forEach(function (b) {{ b.classList.remove('active'); }});
        btn.classList.add('active');
        render();
      }});
    }});
    catButtons.forEach(function (btn) {{
      btn.addEventListener('click', function () {{
        currentCategory = btn.dataset.category;
        catButtons.forEach(function (b) {{ b.classList.remove('active'); }});
        btn.classList.add('active');
        render();
      }});
    }});
  </script>
</body>
</html>
"""
    out_dir = ROOT / "output"
    out_dir.mkdir(exist_ok=True)
    out_path = out_dir / "index.html"
    out_path.write_text(html, encoding="utf-8")
    return out_path


def main():
    terms_dir = ROOT / "terms"
    targets = sys.argv[1:]

    if targets:
        term_dirs = [terms_dir / name for name in targets]
    else:
        term_dirs = [p for p in terms_dir.iterdir() if p.is_dir()]

    entries = []
    for term_dir in term_dirs:
        out_path, title, message, yomi, category = build(term_dir)
        created_at = get_created_at(term_dir)
        entries.append((out_path, title, message, yomi, created_at, category))
        print(f"built: {out_path}")

    if not targets:
        index_path = build_index(entries)
        print(f"built: {index_path}")


if __name__ == "__main__":
    main()
