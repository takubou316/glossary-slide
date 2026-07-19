# CLAUDE.md

このファイルはClaude Code（claude.ai/code）がこのリポジトリで作業する際のガイドです。

## アプリ概要

会話中に出てくる難しい用語をその場で解説する「1枚スライド」を静的サイトとして量産するプロジェクト。ビルドステップは`build.py`（Python）のみで、フロントエンドはビルド不要のvanilla HTML/JS/CSS。将来的には「Claudeとの会話中に難しい用語が出たら自動でスライドを呼び出す」のが本来のゴールだが、現状は手動でスライドを増やしている段階（二段構えの方針は[[project_glossary_explainer_two_stage]]参照。動画化(VOICEVOX/Remotion)は保留中）。

公開URL: https://takubou316.github.io/glossary-slide/ （GitHub Pages）

## アーキテクチャ

- `terms/<slug>/` — 用語1つぶんのソース。2パターンある:
  - **単発スライド**: `meta.json`(term/message/slug/category等) + `diagram.html` + `diagram.css`
  - **タブ切り替えあり**（現在の標準。新規作成時は基本編+発展編を必ずセットで作る）: `group.json`（`variants`配列でタブの並びを宣言）+ 各variant用サブフォルダ（`intro/`, `advanced/`, `compare/`等）にそれぞれ`meta.json`/`diagram.html`/`diagram.css`
- `build.py` — `terms/`以下を全走査し、`template.html`（単発用）/`player_template.html`（タブ用）に流し込んで`output/<slug>.html`を生成。引数に用語名を渡すと該当分だけビルド（例: `python build.py token agent`）、無引数なら全件ビルド＋`output/index.html`（検索付き一覧）も再生成
- `output/index.html` — 一覧ページ。タイトル/読み/説明文で検索（ひらがな・カタカナ正規化、ローマ字入力にも対応。`pykakasi`が入っていればローマ字インデックスも生成、無ければ警告だけ出してスキップ）
- `output/create.html` — 「用語を作成」ページ。APIは呼ばず、下記の作成ルール一式を埋め込んだClaude Code貼り付け用の依頼文を組み立てるだけの静的ページ（コスト0円版）

## ローカルビルド

```
python build.py          # 全件ビルド
python build.py token     # termsの特定フォルダ名だけビルド
```
`pip install pykakasi` でローマ字検索対応（無くても動くが警告が出る）。

## 新しい用語を作るときのルール（確立済み・毎回守る）

1. **基本編(`intro`)は必ずシンプルに保ち、発展的な話は`advanced`タブに分離する。** 前提知識が要る話をintroに詰め込むと「逆にわかりにくい」と過去に指摘された。ただし発展編自体は省略せず、基本的に毎回セットで作る（2026-07-09に「省略せずデフォルトで付けて」と方針転換済み）。
2. **比較・応用系のスライドを単体で渡さない。** 必ず基本概念を説明するタブと同じ`group.json`の中に含め、「基本→比較→発展」の1つの流れにする。
3. **図解は[[feedback_intuitive_diagram_design]]のチェックリストに従う**: ラベルは対象に直接くっつける（凡例任せにしない）、複数の要素を並べるときは種類ラベルを直接添える、離れたクラスターではなく1つの連続した図にする。「キャプションを隠しても図だけで話が伝わるか」で自己チェックする。
4. **固有名詞・慣用句・比喩表現は`term-link`の対象にする。** 前提知識が要る語（専門用語だけでなく「縁の下の力持ち」のような慣用句も含む）は`<a class="term-link" href="slug.html">語</a>`でリンクし、対象スライドが無ければ新規作成する。
5. **誰が作ったか分かるなら明記する。** 場所・企業・作品・制度のスライドでWeb検索の結果に創業者/作者名が出てきたら、必ず本文に反映する。1スライドにしか関わらない人物は文中に名前を足すだけ、複数スライドに関わる「ハブ」になる人物（例: 宮本茂→マリオ+ゼルダ）は独立のterm-linkスライドを作る。
6. **数値・史実の主張は3段構えで裏取りする**: (1)計算で検証できるものはBash/PowerShellで実際に計算、(2)ライブラリで検証できるもの（トークン化など）は実際に実行（`tiktoken`など）、(3)史実・時事ネタはWebSearch。記憶や推測で数値を書かない。
7. 漢字を含む見出しには`<ruby><rt>` でふりがなを付ける。

## 既知のバグパターン・実装上の注意

- **CSSスコープ**: `build_group()`が各variantの`diagram.css`を`scope_css()`で`#panel-<variant-id>`配下に自動スコープしてから結合する。手動でクラス名を分ける必要はない（過去にスコープなしで`.tok`のような使い回しクラス名が別variantに漏れて崩れたバグがあった）。
- **一覧ページでのtag除去**: `output/index.html`の各カードはタイトル+説明文全体を1つの`<a>`で囲む構造。message内に`term-link`の`<a>`が入っているとネストして壊れるため、`build_index()`で`strip_tags()`を通してからプレーンテキスト化して使う（新しい一覧的UIを足すときも同じ処理を通すこと）。
- **カスタムボタンのリセット**: タブボタンやピル型ボタンには最初から`appearance:none; -webkit-appearance:none; -moz-appearance:none; display:inline-flex; align-items:center; justify-content:center; line-height:1; touch-action:manipulation;`を入れる。リセット漏れがあるとクリック判定が見た目とズレるバグが起きる。
- **組織図の接続線**: 横線を`position:absolute; top:0`、縦線を通常配置の`padding-top`で作ると、paddingの内外でY座標がズレて隙間ができる。横線・縦線の基準Y座標は揃え、間隔は`padding`ではなく`gap`や明示`height`で作る。
- **ハイライトカード内のterm-link**: 背景がaccent色になるカード（`.highlight`系）の中にterm-linkを置くとデフォルトのaccent文字色が背景と同化する。`.xxx.highlight .term-link { color: var(--paper); }`のような上書きを追加する。
- **図解の実データ整合性**: タイル数・バッジの数字・実測結果は必ず一致させる（トークン数の例文とintro/advancedタブ間で矛盾していたバグが過去に発生・修正済み）。

## ブラウザプレビューが不安定な場合

`preview_screenshot`/`computer`/`get_page_text`が頻繁にタイムアウトすることがある。再起動しても直らない場合は、`grep`でタグの対応（`<a>`と`</a>`の数）やリンク先ファイルの実在確認など、ブラウザなしで構造的に検証できる手段に切り替える。
