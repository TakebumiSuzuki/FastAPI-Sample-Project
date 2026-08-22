# 00. モノレポの骨組みと uv プロジェクト初期化

## やったこと

自分の手でターミナルに打って実行した。

```bash
uv init backend --vcs none
cd backend
uv add fastapi
```

## 学んだこと

### `uv init` のオプション
- パスを渡すだけでディレクトリごと自動作成される（`mkdir` は不要）
- `--vcs none`：`uv init` はデフォルトで `git init` まで行う。今回はリポジトリ直下に
  既に `.git` があるため、`backend/` の中に別のリポジトリを作らせないよう明示的に無効化した
- **すでに `backend/` の中に `cd` している場合**は `uv init . --vcs none` でよい。
  `.`（カレントディレクトリ）をパスとして渡す形。パス自体を省略した `uv init --vcs none` も
  同じ結果になる。

### `pyproject.toml` と `uv.lock` の役割の違いと依存関係の解決
- **`pyproject.toml`**：人間が書く「ルールの条件（要件・バージョン制約）」
  - `dependencies`：本番・アプリ実行用の依存パッケージ（PEP 621 標準）
  - `[dependency-groups]`（`dev` など）：テスト・開発環境でのみ使うパッケージ（PEP 735 標準）
  - バージョン制約の書き方例：
    - `"alembic>=1.19.1"`：最低要件（1.19.1 以上）
    - `"pytest>=9.1.1, <10"`：9系の最新まで許可（10.0.0 未満）
    - `"pytest~=9.1"`：互換リリース指定（`>=9.1, <10.0` と同義）
- **`uv.lock`**：`uv` が条件を元に計算して確定させた「正確なバージョンとハッシュ値」
- **依存関係の解決（Dependency Resolution）**：
  - `uv` のリゾルバ（計算機）が `pyproject.toml` の制約と、各ライブラリが要求する推移的依存関係（間接的に必要なライブラリ群）をすべて矛盾なく満たす組み合わせを計算し、`uv.lock` に固定版として記録する。
  - したがって、`uv.lock` に書き出されるバージョンは必ず `pyproject.toml` の条件を満たしている。
- `uv add` は両方を更新する。`uv sync` は `uv.lock` を読んで環境を再現する
- すでに入っているライブラリを再度 `uv add`しても、再インストールはされない。
  バージョンを書いた場合だけ `pyproject.toml` の該当行がその指定に上書きされる

### パッケージを最新の安定版にアップデートする（--upgrade）
`pyproject.toml` の制約を満たす範囲内で、パッケージを最新の安定版に引き上げる。

- **プロジェクト全体を最新にアップデート**:
  ```bash
  uv lock --upgrade       # uv.lock を最新の解決結果で更新
  uv sync --upgrade       # lock を更新して .venv にも即座に反映
  ```
- **特定のパッケージのみを最新にアップデート（`-P` / `--upgrade-package`）**:
  ```bash
  uv lock --upgrade-package fastapi   # fastapi（およびその関連依存）のみ最新化
  uv sync --upgrade-package fastapi
  ```
- **注意点**: `pyproject.toml` に `<10` などの上限制約がある場合は、その制約の範囲内での最新版（例: 9系の最新）までしか上がらないため、意図しない破壊的アップデートを安全に防ぐことができる。

### 仮想環境の場所
- `uv add`（初回）が自動で `backend/.venv` を作成する
- VS Code 側の `.vscode/settings.json` に
  `python.defaultInterpreterPath: "${workspaceFolder}/backend/.venv/bin/python"`
  が**既に設定済み**だった。追加作業は不要だった

## 動作確認

```bash
uv run python -c "import fastapi"
```
エラーなく通った。これが今回の「できるようになること」の達成条件。

### なぜ `uv run` が必須なのか（python の場合）
- `which python` は `/opt/uv-venv/bin/python`（Dockerfile が用意したグローバル Python。
  pandas や pypdf など別ツール用で、fastapi は入っていない）を指していた
- 素の `python -c "import fastapi"` は実際に `ModuleNotFoundError` になった
- `uv run python ...` を使うことで、初めて `backend/.venv/bin/python`
  （fastapi がインストールされている方）が使われる
- 01章で扱った ruff とは逆のパターン：ruff は `.venv` に入れていないので
  `uv run` の有無で結果が変わらなかったが、python は `.venv` に入れた
  ライブラリを使う主体そのものなので `uv run` を省略できない

## 詰まった点・気づき

### `Failed to hardlink files; falling back to full copy` という警告が出た

`uv add` のたびに出るが、インストールは成功している。対処は不要。

```
uv add fastapi
  ├ ① ダウンロード
  ├ ② /home/node/.cache/uv に保存（uv は全プロジェクト共通のキャッシュに一旦置く）
  ├ ③ キャッシュ → backend/.venv へ ハードリンク  → 失敗 ★ここ
  └ ④ 諦めてコピー                                → 成功
```

③でやろうとしたハードリンクは「実物を複製せず、別の場所から参照できる別名を付ける」機能。
速いので uv のデフォルトだが、**実物と別名が同じファイルシステム上にないと張れない**
（ファイルシステム＝OS がディスク領域を管理する単位）。

今回はその条件を満たしていなかった。この2つは、コンテナの中では隣同士に見えるが、
**実物の置き場所が違う**から。

```
キャッシュ  /home/node/.cache/uv   … 実物はコンテナの中にある
backend/.venv                      … 実物は Mac の中にある
                                     （コンテナは Mac のフォルダを窓越しに見ているだけ）
```

この devcontainer を使う限り毎回起きる。実害はコピーのぶん遅いこと。
`UV_LINK_MODE=copy` を設定すれば警告は消える（速くはならない）。今回は未対応。

