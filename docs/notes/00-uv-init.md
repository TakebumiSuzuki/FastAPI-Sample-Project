# 00. モノレポの骨組みと uv プロジェクト初期化

## やったこと

自分の手でターミナルに打って実行した。

```bash
uv init backend --app --vcs none
cd backend
uv add fastapi
```

## 学んだこと

### `uv init` のオプション
- パスを渡すだけでディレクトリごと自動作成される（`mkdir` は不要）
- `--app`：uv 公式ドキュメントによると、**アプリケーションは `uv init` のデフォルトの種類**。
  何もオプションを付けなくても `--app` と同じ結果になる。明示するかどうかは意図表明の意味合いが強い
  （`--lib` を付けた場合との違い：ライブラリは `src/<name>/` レイアウトになり、
  `[build-system]` セクション付きの `pyproject.toml` になる。PyPI配布前提の構成）
- `--vcs none`：`uv init` はデフォルトで `git init` まで行う。今回はリポジトリ直下に
  既に `.git` があるため、`backend/` の中に別のリポジトリを作らせないよう明示的に無効化した
- `--author-from git` は付けなかった。付けないと `pyproject.toml` に `authors` の行が
  単に無いだけで、他は変わらない（`git config` の名前・メールを自動転記する機能を使わなかっただけ）

### `pyproject.toml` と `uv.lock` の役割の違い
- `pyproject.toml`：「fastapi の 0.141.1 以上が欲しい」という**ゆるい**依存の宣言
- `uv.lock`：実際にインストールされた全パッケージの**正確なバージョンとハッシュ**
- `uv add` は両方を更新する。`uv sync` は `uv.lock` を読んで環境を再現する
- `uv.lock` は git にコミットする。`.venv/` はコミットしない（`.gitignore` 済み）

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

- `uv add` 実行時に `Failed to hardlink files; falling back to full copy` という警告が
  2回とも出た。`df -T` で調べたところ原因が特定できた：
  - uv のキャッシュ `/home/node/.cache/uv` → `overlay` ファイルシステム（コンテナ内部）
  - `backend/.venv` → `fakeowner` ファイルシステム（`/workspaces/cc-dev-container` が
    Mac ホスト側のフォルダを bind mount している領域）
  - ハードリンクは同一ファイルシステム内でしか使えないため、別ファイルシステムをまたぐ
    このマウント構成では常にコピーにフォールバックする。動作は正常、依存追加のたびに
    毎回やや遅くなるだけ。`UV_LINK_MODE=copy` を設定すれば警告自体は消える（今回は未対応）
- `.vscode/settings.json` を覗いたら以下が既に設定済みだった（01章の内容の一部）
  - `python.defaultInterpreterPath: "${workspaceFolder}/backend/.venv/bin/python"`
  - `python.analysis.typeCheckingMode: "standard"`
- `rm -rf backend` を別ターミナルで打ったら消えなかった一幕があった。原因は
  カレントディレクトリが `/workspaces/cc-dev-container` でなかったこと
  （`rm -rf` の `-f` は対象が存在しなくてもエラーを出さないため気づきにくい）。
  コマンドを打つ前は `pwd` で場所を確認する習慣が大事、という教訓
