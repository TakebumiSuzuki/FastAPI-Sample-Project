# プロジェクトの目的と前提

## このプロジェクトは何か

FastAPI によるバックエンド API を**学習しながら実装していく**プロジェクト。
最終的には Vue のフロントエンドを同居させたモノレポにする（フロントは後回し）。

**単なる実装代行ではなく、学習が主目的。** そのため Claude は下記の進め方に従うこと。

## 学習の進め方（Claude 向けの運用ルール）

- カリキュラムは `@docs/syllabus.md` に定義されている。原則としてこの順に進める。
- **1章が終わるたびに、学習内容のまとめを `docs/notes/NN-<topic>.md` として新規作成する**
  （`NN` はシラバスの章番号。例：`docs/notes/09-sqlalchemy-basics.md`）。
  - まとめには「何を学んだか」「なぜそう書くのか」「詰まった点」を書く。コードの丸写しはしない。
  - 既存のノートを書き換えるのではなく、章ごとに新しいファイルを追加していく。
- ユーザーはエンジニア一年目。**先回りして完成コードを提示しない。** まず設計と理由を説明し、
  ユーザーが書く／Claude が書くをその都度確認する。
- **コマンド（`mkdir` / `uv init` / `uv add` 等）は原則ユーザー自身が打つ。**
  Claude が Bash で先回りして実行しない。Claude の役割は「次に何を・なぜ打つか」を説明し、
  実行結果を一緒に確認すること。Claude が手を動かすのは、ユーザーが明示的に依頼したときのみ。
- ライブラリの仕様（引数名・戻り値・設定キー）は記憶で書かず、必ず一次情報で確認する。

## 技術スタックと決定事項

| 項目 | 選択 | 備考 |
| --- | --- | --- |
| 言語 | Python 3.13 | devcontainer に uv 管理で導入済み |
| パッケージ管理 | uv | Dockerfile に導入済み（v0.11.8） |
| フレームワーク | FastAPI | |
| ディレクトリ構成 | レイヤー別（`backend/app/`） | 機能別ではなくレイヤー別を採用 |
| ORM | SQLAlchemy 2.x | SQLModel ではなく本家を使う |
| マイグレーション | Alembic | |
| DB | SQLite → 途中で PostgreSQL | 第7部で移行する |
| Lint / Format | ruff | Dockerfile に導入済み（v0.16.0） |
| 型チェック | Pylance `standard` | `python.analysis.typeCheckingMode: "standard"` |
| テスト | pytest | 第4部から TDD で進める |
| フロント | Vue | 未着手。`frontend/` に置く予定 |

### 選定理由（後から見返す用）

- **レイヤー別を選んだ理由**：FastAPI 公式ドキュメント・公式テンプレートと同じ形なので、
  詰まったときに世の中の資料をそのまま参照できる。機能が増えて往復が苦になったら機能別へ移行する。
- **`app/` という名前**：`src/` レイアウトの利点（配布パッケージとのズレ防止）は、
  Docker で動かす Web API には効かない。公式に合わせて `app/` にした。
- **SQLModel ではなく SQLAlchemy**：DB モデルと API スキーマが別物であることを
  最初にきちんと理解するため。実務・求人でも本家の知識が問われる。

## ディレクトリ構成

```
cc-dev-container/
├── backend/                  # FastAPI（本プロジェクトの主戦場）
│   ├── app/
│   │   ├── core/
│   │   │   ├── config.py     # 設定（Settings）
│   │   │   └── exceptions.py # 例外ハンドラーの定義と登録
│   │   ├── deps.py           # 依存性注入（共通クエリ、DBセッションなど）
│   │   ├── routes/           # エンドポイント定義（items.py など）
│   │   └── schemas.py        # API の入出力の形（Pydantic）
│   ├── main.py               # FastAPI() の生成と router の登録
│   ├── pyproject.toml
│   └── uv.lock
├── frontend/                 # Vue（未着手）
├── docs/
│   ├── project-overview.md   # このファイル
│   ├── syllabus.md           # 学習カリキュラム
│   └── notes/                # 章ごとの学習まとめ
├── .devcontainer/
├── AGENTS.md -> Claude.md
├── GEMINI.md -> Claude.md
└── Claude.md
```

**原則**：`backend/` と `frontend/` で依存管理を混ぜない。
`pyproject.toml` は `backend/` の中、`package.json` は `frontend/` の中に置く。
