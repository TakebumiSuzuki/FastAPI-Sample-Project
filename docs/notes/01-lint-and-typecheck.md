# 01. 型チェックと Lint の土台

## やったこと

- `.vscode/settings.json` を確認 → Pylance 側は既に設定済みだった（作業不要）
  - `python.defaultInterpreterPath: "${workspaceFolder}/backend/.venv/bin/python"`
  - `python.analysis.typeCheckingMode: "standard"`
- `backend/pyproject.toml` に ruff の設定を追記（自分で編集）

```toml
[tool.ruff.lint]
extend-select= ["UP","I","B"]
```

- `ruff check .`（backend/ 内）で `All checks passed!` を確認

## 学んだこと

### Pylance の `typeCheckingMode` は4段階
- `off` → `basic` → `standard` → `strict` の順に厳しくなる
- 「medium」という値は存在しない（最初勘違いしていた）。中間の強さは `standard`

### ruff：`select` と `extend-select` の違い
- 何も設定しなくても `E4`/`E7`/`E9`/`F`（構文エラー・未定義変数など）はデフォルトで有効
- `select` で書くと**デフォルトを上書き**してしまう
- `extend-select` は**デフォルトに追加**する。今回はこちらを使った
- 追加したコード：
  - `I`（isort）：import の並び順を統一
  - `UP`（pyupgrade）：Python のバージョンに応じて古い書き方を新しい構文に置き換える提案
  - `B`（flake8-bugbear）：バグを誘発しやすいパターンの検出
- `target-version` は明示していない。ruff は `[project] requires-python` を見て
  自動推定する仕様があり、`backend/pyproject.toml` の `requires-python = ">=3.13"` が
  そのまま使われる

### `uv run <コマンド>` はプロジェクトの `.venv` になければ PATH にフォールバックする
- `uv run ruff check .` を実行したが、`backend/.venv/bin/` に ruff は入っていなかった
- 実際に動いていたのは Dockerfile でグローバルに入れた `/usr/local/bin/ruff`（0.16.0）
- 確認：`uv run` の公式ドキュメントに
  "The command executed with `uv run` can either be provided by the project's
  environment **or exist independently**." と明記されている
- 結論：ruff はプロジェクトの依存に加えていないので、`uv run` を付けても付けなくても
  同じグローバル ruff が使われる。**素の `ruff check .` の方が実態に合っている**
  （`uv run` を付けると「プロジェクト固有の ruff がある」ように誤解を招く）
- 対照的に `python` はグローバルにも別の実体（`/opt/uv-venv/bin/python`、fastapi 未インストール）
  があるため、`uv run python ...` を省略すると `ModuleNotFoundError` になる
  （詳細は `docs/notes/00-uv-init.md` に記録）

## 保留にした判断

- CLI（pre-commit・CI）用の型チェッカー（pyright CLI / mypy）は今は導入しない。
  第7部（Docker・デプロイ）のあたりで改めて検討する
