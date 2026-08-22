# 12. Alembic でマイグレーション

## 1. 今回学んだこと・理解したポイント

### ① Alembic の役割と構成
- **Alembic の役割**: データベースのテーブル構成（スキーマ）の変更履歴をバージョン管理し、安全に作成・更新・ダウングレードするツール。
- **構成ファイルの役割**:
  - `alembic.ini`: 静的な全体設定ファイル（ログ設定やスクリプトパスなど）。
  - `alembic/env.py`: マイグレーション実行時に呼ばれる Python スクリプト。SQLAlchemy の `Base.metadata` を読み込んで Alembic にモデル構造を伝える。
  - `alembic/versions/`: 自動生成されたリビジョンファイル（マイグレーションスクリプト）が保存されるフォルダ。

### ② 設定ファイルは `alembic.ini` か `pyproject.toml` か
- `alembic init alembic`（このプロジェクトで使った標準テンプレート）は `alembic.ini` を生成する。これが従来からのやり方。
- Alembic 1.16 以降は、設定を `pyproject.toml` の `[tool.alembic]` セクションに書くこともできる。
  （PEP 621 = Python プロジェクトの設定を `pyproject.toml` の一箇所に集約しようという規約。ruff や pytest の設定を同じファイルに書けるのと同じ流れ）
- 始めるときは、標準テンプレートの代わりにこちらを指定する：
  ```bash
  uv run alembic init --template pyproject alembic
  ```
  既存の `pyproject.toml` があればそこに `[tool.alembic]` を追記してくれる。
- ただし **書ける設定に線引きがある**。

  | 置き場所 | 書ける設定 |
  | :--- | :--- |
  | `pyproject.toml` の `[tool.alembic]` | `script_location`、`prepend_sys_path`、`version_locations`、`file_template`、`post_write_hooks` |
  | `alembic.ini` または `env.py` | `sqlalchemy.url`（DB 接続情報）、`[loggers]` などのログ設定 |

- この線引きの理由は、作者 zzzeek が Issue #1082 で述べているとおり「DB URL は dev と production で変わる値だから」。
  つまり **ソースコードの配置に関する設定** と **環境ごとに変わるデプロイ設定** を分ける、という設計判断。
  Git にコミットされる `pyproject.toml` に、環境依存の値を置かせないようにしている。
- なお `alembic.ini` は必須ではない。公式チュートリアルにも「接続情報とログ設定を他の場所で管理していれば `alembic.ini` が無い環境も可能」とある。
  このプロジェクトは既にその条件を満たしている：
  - DB URL → `env.py` で `.env` から読んでいる（ini を見ていない）
  - ログ設定 → `env.py` の該当行が `if config.config_file_name is not None:` でガードされているので、ini が無ければスキップされるだけ

  参考: [Alembic Tutorial](https://alembic.sqlalchemy.org/en/latest/tutorial.html) / [Issue #1082](https://github.com/sqlalchemy/alembic/issues/1082)

---

## 2. `alembic/env.py` の設定ポイント

### ① モデルのインポートと `target_metadata`
- Python が `class Item(Base):` などのクラス定義コードを読み込んだ時点で、`Base.metadata` にテーブル構造情報が登録される。
- そのため、`env.py` 内で `import app.models.item` 等を行って全モデルを評価させ、`target_metadata = Base.metadata` にセットすることで Alembic が差分を検知できるようになる。

### ② `.env` からの DB 接続 URL 動的ロード
- `alembic.ini` に DB 接続情報を直書きせず、`env.py` 内で以下のように設定することで `.env` の設定（`database_url`）を安全かつ動的に利用できる：
  ```python
  config.set_main_option("sqlalchemy.url", get_settings().database_url)
  ```

### ③ Alembic はどうやって DB に接続しているか
- `SessionLocal` は使わない。`env.py` の `run_migrations_online()` が **Engine を自前で作って Connection を取っている**。

  ```
  ①  config.set_main_option("sqlalchemy.url", ...)   # .env の URL を Config に書き込む
  ②  config.get_section(...)                          # [alembic] セクションを辞書で取り出す
  ③  engine_from_config(辞書, prefix="sqlalchemy.")   # Engine を生成
  ④  connectable.connect()                            # Connection を取得
  ⑤  context.configure(connection=connection, ...)    # Alembic にその接続を渡す
  ```

- `engine_from_config` は **SQLAlchemy の関数**（`from sqlalchemy import engine_from_config`）で、中身は `create_engine()` を呼ぶだけ。Alembic 独自の Engine ではない。
  - `create_engine(url)` … URL を直に渡す
  - `engine_from_config(辞書, prefix="sqlalchemy.")` … 辞書から `sqlalchemy.` で始まるキーを拾って `create_engine` に渡す
  - 後者を使うのは、本来 URL が `alembic.ini` に書かれている想定で、ini から読んだ内容は辞書で出てくるため。
- ただし `app/core/session.py` の `engine` とは **別インスタンス**。マイグレーションは `uv run alembic upgrade head` という独立したプロセスで走るので、FastAPI 側の Engine とは共有しようがない。
- `Session` が不要な理由: Session は「Python オブジェクト ←→ 行」の変換係。Alembic が発行するのは DDL（`CREATE TABLE` / `ALTER TABLE` などテーブルの形を変える SQL）なので、変換係は要らず、SQL を送る通信路である Connection だけで足りる。

### ④ `revision --autogenerate` と `upgrade` はそれぞれ何をしているか

```
uv run alembic revision --autogenerate
  └─ env.py を実行 → Engine 作成 → connect
       ├─ [実物]   DB をリフレクションで読む ──┐
       └─ [青写真] Base.metadata ─────────────┴→ 差分を比較
            └→ alembic/versions/xxxx_.py に op.add_column(...) 等を書き出す

uv run alembic upgrade head
  └─ env.py を実行 → Engine 作成 → connect
       └─ versions/ のファイルの op.* を順に実行 → DDL を発行
```

- **リフレクション（reflection）**: DB に接続してカタログ情報（PostgreSQL なら `information_schema` など）を問い合わせ、既存のテーブル・カラム定義を Python オブジェクトとして読み戻すこと。Alembic はこれを SQLAlchemy の `Inspector` 経由で行っている（`alembic/autogenerate/api.py` の `inspector` プロパティが `inspect(self.connection)` を返す）。
- **`upgrade` のときは比較を一切しない**。`versions/` のファイルに書かれた `op.*` をそのまま DDL に変換して流すだけ。
- どこまで適用済みかは、DB 内の `alembic_version` テーブルに記録されたリビジョン ID で判断している。

---

## 3. マイグレーション運用の基本コマンド

| コマンド | 役割・用途 |
| :--- | :--- |
| `uv run alembic revision --autogenerate -m "message"` | モデル定義と現在の DB 状態を比較し、差分マイグレーションファイルを生成 |
| `uv run alembic upgrade head` | 未適用のマイグレーションをすべて DB に反映する |
| `uv run alembic downgrade -1` | 1つ前のバージョン状態に戻す（ロールバック） |
| `uv run alembic current` | 現在 DB に適用されているリビジョンID を表示 |
| `uv run alembic history` | マイグレーションの変更履歴一覧を表示 |

---

## 4. 自動生成（`--autogenerate`）の注意点

- **必ず目視で生成コードを確認してから適用する**:
  - Alembic の自動生成は完璧ではなく、テーブル名・カラム名の変更が「削除＋新規作成」と判定されてデータが消えるリスクがある。
  - カスタム型や特定の制約（インデックスやドロップ等）を正しく検知しない場合があるため、`alembic/versions/` に生成されたファイルの `upgrade()` / `downgrade()` を必ずチェックする習慣をつける。

---

## 5. 進捗状況と次回（第13章）への引き継ぎ

### 進捗状況
1. `uv add alembic` および `alembic init alembic` による初期化完了。
2. `alembic/env.py` の編集完了（`Base.metadata` 連携、モデルインポート、`.env` 接続情報取得）。
3. 初回のマイグレーション作成（`create items table`）と `alembic upgrade head` による DB 反映の動作確認完了。

第12章「Alembic でマイグレーション」が完了しました！

### 次回やること（第13章：リレーションと N+1）
- 1対多のリレーション（`relationship()` / 外部キー）
- 遅延読み込みと N+1 問題の理解
- `selectinload` / `joinedload` による解決
- ネストしたレスポンススキーマの書き方
