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

### `pyproject.toml` と `uv.lock` の役割の違い
- `pyproject.toml`：「fastapi の 0.141.1 以上が欲しい」という**ゆるい**依存の宣言
- `uv.lock`：実際にインストールされた全パッケージの**正確なバージョンとハッシュ**
- `uv add` は両方を更新する。`uv sync` は `uv.lock` を読んで環境を再現する
- すでに入っているライブラリを再度 `uv add` しても、再インストールはされない。
  バージョンを書いた場合だけ `pyproject.toml` の該当行がその指定に上書きされる

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
- `rm -rf backend` を別ターミナルで打ったら消えなかった一幕があった。原因は
  カレントディレクトリが `/workspaces/cc-dev-container` でなかったこと
  （`rm -rf` の `-f` は対象が存在しなくてもエラーを出さないため気づきにくい）。
  コマンドを打つ前は `pwd` で場所を確認する習慣が大事、という教訓
