import json
import pathlib
import sys

ROOT = pathlib.Path(__file__).parent
TEMPLATE = (ROOT / "template.html").read_text(encoding="utf-8")
PLAYER_TEMPLATE = (ROOT / "player_template.html").read_text(encoding="utf-8")


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


def build_single(term_dir: pathlib.Path) -> tuple[pathlib.Path, str, str]:
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
    return out_path, meta["term"], meta["message"]


def build_group(term_dir: pathlib.Path) -> tuple[pathlib.Path, str, str]:
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
    return out_path, group["title"], intro_message


def build(term_dir: pathlib.Path) -> tuple[pathlib.Path, str, str]:
    if (term_dir / "group.json").exists():
        return build_group(term_dir)
    return build_single(term_dir)


def build_index(entries: list[tuple[pathlib.Path, str, str]]) -> pathlib.Path:
    items = "\n".join(
        f'      <li class="item" data-search="{(title + " " + message).lower()}">\n'
        f'        <a href="{out_path.name}">\n'
        f'          <div class="item-title">{title}</div>\n'
        f'          <div class="item-desc">{message}</div>\n'
        f'        </a>\n'
        f'      </li>'
        for out_path, title, message in sorted(entries, key=lambda e: e[1])
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
  h1 {{ font-size: 28px; color: #262322; margin: 0 0 24px; }}
  .search-box {{
    width: 100%;
    box-sizing: border-box;
    padding: 14px 18px;
    font-size: 17px;
    font-family: inherit;
    border: 2px solid #DDD9D2;
    border-radius: 14px;
    margin-bottom: 20px;
    color: #262322;
  }}
  .search-box:focus {{
    outline: none;
    border-color: #D97757;
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
  .item a:hover .item-title, .item a:hover .item-desc {{ color: #FAF9F5; }}
  .item-title {{ font-size: 20px; font-weight: 700; color: #D97757; }}
  .item-desc {{ font-size: 14px; font-weight: 600; color: #8A8681; margin-top: 6px; }}
  .empty-note {{ display: none; color: #8A8681; font-size: 15px; padding: 8px 4px; }}
</style>
</head>
<body>
  <div class="card">
    <h1>今日のひとこと解説 一覧</h1>
    <input type="text" class="search-box" id="search" placeholder="用語を検索...">
    <ul id="list">
{items}
    </ul>
    <div class="empty-note" id="empty-note">見つかりませんでした</div>
  </div>
  <script>
    var search = document.getElementById('search');
    var items = [].slice.call(document.querySelectorAll('#list .item'));
    var emptyNote = document.getElementById('empty-note');
    search.addEventListener('input', function () {{
      var q = search.value.trim().toLowerCase();
      var visibleCount = 0;
      items.forEach(function (item) {{
        var match = item.dataset.search.indexOf(q) !== -1;
        item.style.display = match ? '' : 'none';
        if (match) visibleCount++;
      }});
      emptyNote.style.display = visibleCount === 0 ? 'block' : 'none';
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
        out_path, title, message = build(term_dir)
        entries.append((out_path, title, message))
        print(f"built: {out_path}")

    if not targets:
        index_path = build_index(entries)
        print(f"built: {index_path}")


if __name__ == "__main__":
    main()
