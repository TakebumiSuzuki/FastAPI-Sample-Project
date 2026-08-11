# 12. Alembic でマイグレーション

## 1. 今回学んだこと・理解したポイント

### ① Alembic の役割と構成
- **Alembic の役割**: データベースのテーブル構成（スキーマ）の変更履歴をバージョン管理し、安全に作成・更新・ダウングレードするツール。
- **構成ファイルの役割**:
  - `alembic.ini`: 静的な全体設定ファイル（ログ設定やスクリプトパスなど）。
  - `alembic/env.py`: マイグレーション実行時に呼ばれる Python スクリプト。SQLAlchemy の `Base.metadata` を読み込んで Alembic にモデル構造を伝える。
  - `alembic/versions/`: 自動生成されたリビジョンファイル（マイグレーションスクリプト）が保存されるフォルダ。

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
