# FastAPI 学習シラバス

前提と技術選定は `docs/project-overview.md` を参照。

## 使い方

- 原則としてこの順に進める。飛ばしたい章があればその都度相談する。
- **1章終わるごとに `docs/notes/NN-<topic>.md` にまとめを書く。**
- 各章の「できるようになること」が満たせたら次へ進む。満たせなければ同じ章に留まる。

## 全体像

```
第0部 環境構築          ── 手を動かす前の土台          (2章)
第1部 FastAPI の基礎    ── 1ファイルで API の形を掴む   (4章)
第2部 アプリの構造化    ── app/ の各フォルダを埋める    (3章)
第3部 データベース      ── SQLite + SQLAlchemy + Alembic (5章)
第4部 テストと TDD      ── ここから TDD に切り替える     (3章)
第5部 認証・認可        ── JWT でログインを作る          (3章)
第6部 非同期            ── async/await へ移行            (2章)
第7部 PostgreSQL と Docker ── 本番に近づける             (3章)
                                                    計 25章
```

---

## 第0部 環境構築

### 00. モノレポの骨組みと uv プロジェクト初期化
- `backend/` を作り `uv init` でプロジェクトを作る（`pyproject.toml` の読み方）
- `uv add fastapi` と `uv sync` の違い、`uv.lock` が何を保証するか
- 仮想環境（`.venv`）がどこに作られ、VS Code にどう認識させるか
- グローバルの `/opt/uv-venv`（devcontainer 備え付け）とプロジェクト venv の使い分け

**できるようになること**：`uv run python -c "import fastapi"` が通る

### 01. 型チェックと Lint の土台
- `.vscode/settings.json` で `python.analysis.typeCheckingMode: "standard"` を設定
- Pylance の 4 段階（off / basic / standard / strict）の違いを理解する
- ruff の設定（`pyproject.toml` の `[tool.ruff]`）、フォーマットと Lint の役割分担
- ※CLI 側の型チェック（pyright CLI か mypy か）はこの章で相談して決める

**できるようになること**：型注釈の抜けをエディタが指摘してくれる状態になる

---

## 第1部 FastAPI の基礎

### 02. 最初のエンドポイントと自動ドキュメント
- `FastAPI()` インスタンス、`@app.get("/")`、`fastapi dev` での起動
- `/docs`（Swagger UI）と `/openapi.json` が自動生成される仕組み
- ASGI とは何か、uvicorn の役割

**できるようになること**：ブラウザで自作 API のドキュメントを開ける

### 03. パスパラメータ・クエリパラメータと型による検証
- `/items/{item_id}` の受け取りと型変換
- クエリパラメータの必須／任意、デフォルト値
- `Annotated[int, Path(ge=1)]` / `Query()` による制約
- 型注釈を書くだけでバリデーションとドキュメントが同時に付いてくる仕組み

**できるようになること**：不正な入力に 422 が返る理由を説明できる

### 04. Pydantic v2：リクエストボディと response_model
- `BaseModel` でリクエストボディを定義する
- `response_model` で返す形を明示し、余計なフィールドを漏らさない
- `model_config` / `Field` / バリデータの基本
- **schemas（外向きの形）と models（DB の形）を分ける理由**

**できるようになること**：入力用・出力用・DB 用のスキーマを描き分けられる

### 05. ステータスコードと例外処理
- `status_code` の指定、`HTTPException` の使い方
- カスタム例外と `@app.exception_handler`
- エラーレスポンスの形を揃える意味

**できるようになること**：404 / 400 / 422 を意図通りに返せる

---

## 第2部 アプリの構造化

### 06. APIRouter でファイル分割
- `APIRouter` を作り `app.include_router()` で登録する
- `prefix` / `tags` / `dependencies` / `responses`
- `app/routes/` へ振り分ける。`main.py` を薄く保つ
- import の名前衝突を避ける書き方（公式が明示している注意点）

**できるようになること**：エンドポイントが増えても `main.py` が膨らまない

### 07. Depends（依存性注入）の基礎
- `Depends` が解決する問題（毎回の共通前処理をどう共有するか）
- 関数依存・クラス依存・`yield` を使う依存（後片付け付き）
- 依存のキャッシュとスコープ
- `app/api/deps.py` に置く方針

**できるようになること**：共通処理を各エンドポイントから引き剥がせる

### 08. 設定管理（pydantic-settings と .env）
- `BaseSettings` で環境変数を型付きで読む
- `.env` と `.env.example`、秘密情報を git に載せない運用
- 設定オブジェクトを `lru_cache` で使い回す定石
- `app/core/config.py` に集約する

**できるようになること**：接続文字列や秘密鍵をコードに直書きしない

---

## 第3部 データベース（SQLite）

### 09. SQLAlchemy 2.0 の基礎
- `DeclarativeBase` / `Mapped[]` / `mapped_column()` という 2.0 系の書き方
- 1.x 系の古い記法（`Column`）との違い ※ネット記事は 1.x が多いので要注意
- `create_engine` と SQLite への接続
- `app/models/` にテーブル定義を置く

**できるようになること**：テーブル定義を型注釈付きで書ける

### 10. セッション管理を Depends に載せる
- `sessionmaker` / `Session` のライフサイクル
- `yield` 依存でリクエストごとにセッションを開いて閉じる
- コミットとロールバックをどこで行うか
- `app/db/session.py` と `app/api/deps.py` の連携

**できるようになること**：DB 接続が漏れない構造を説明できる

### 11. CRUD 層の分離と models ↔ schemas 変換
- `app/crud/` に読み書き関数をまとめ、routes から DB 操作を追い出す
- `select()` / `session.scalars()` など 2.0 系のクエリ記法
- Pydantic の `from_attributes`（旧 `orm_mode`）で ORM オブジェクトをスキーマに変換
- 「routes は薄く、crud は DB だけ」の線引き

**できるようになること**：ルート関数に SQL 相当の処理が現れない

### 12. Alembic でマイグレーション
- `alembic init` と `env.py` の設定（models を読み込ませる）
- `alembic revision --autogenerate` と `alembic upgrade head`
- 自動生成されたマイグレーションを**必ず読んでから適用する**理由
- ダウングレードとリビジョン履歴

**できるようになること**：テーブル変更を履歴として残しながら反映できる

### 13. リレーションと N+1
- 1対多のリレーション（`relationship()` / 外部キー）
- 遅延読み込みと N+1 問題（1件取るのに何十回もクエリが飛ぶ現象）
- `selectinload` / `joinedload` による解決
- ネストしたレスポンススキーマの書き方

**できるようになること**：関連データを含む API を作り、発行される SQL を説明できる

---

## 第4部 テストと TDD

**ここから開発スタイルを TDD（テストを先に書く）に切り替える。**

### 14. pytest と TestClient の基礎
- pytest の書き方（`test_` 関数、`assert`、実行方法）
- FastAPI の `TestClient` でエンドポイントを叩く
- 何をテストし、何をテストしないか

**できるようになること**：既存エンドポイントにテストを後付けできる

### 15. フィクスチャとテスト用 DB の分離
- `conftest.py` と `fixture` のスコープ
- テスト専用 DB を用意し、テストごとに状態をリセットする
- `dependency_overrides` で本番 DB 依存をテスト用に差し替える
- テストデータの作り方（factory 的な補助関数）

**できるようになること**：テストが互いに影響しない状態を作れる

### 16. TDD サイクルで1機能を実装する
- Red（失敗するテストを書く）→ Green（通す）→ Refactor（整える）
- 「テストを先に書く」と設計がどう変わるかを体験する
- どこまでをテストで縛り、どこを自由にしておくか

**できるようになること**：新機能をテストから書き始められる

---

## 第5部 認証・認可

### 17. ユーザー登録とパスワードハッシュ
- パスワードを平文で保存してはいけない理由、ハッシュとソルト
- ハッシュライブラリの選定（この章で相談して決める）
- ユーザー登録エンドポイントを TDD で作る
- レスポンスにパスワードを絶対に含めないスキーマ設計

**できるようになること**：安全にユーザーを登録できる

### 18. OAuth2 + JWT でログイン
- `OAuth2PasswordBearer` と password flow の流れ
- JWT の構造（ヘッダ・ペイロード・署名）と有効期限
- トークン発行エンドポイントと `app/core/security.py`
- リフレッシュトークンを扱うかどうかの判断

**できるようになること**：ログインしてトークンを受け取れる

### 19. 認可：現在のユーザー依存性と権限
- `get_current_user` 依存を作り、保護したいルートに差す
- 無効・期限切れトークンの扱い（401 と 403 の使い分け）
- 「自分のデータしか触れない」チェックの入れ方
- ロール／権限を持たせる場合の設計

**できるようになること**：認証必須のエンドポイントを作れる

---

## 第6部 非同期

### 20. `async def` と `def` の使い分け
- FastAPI が `def` をスレッドプールで動かす仕組み
- 「非同期にすれば速い」が成り立たないケース（同期 I/O を async 関数で呼ぶ事故）
- イベントループをブロックするとは何が起きることか

**できるようになること**：どちらで書くべきかを理由付きで選べる

### 21. 非同期 SQLAlchemy への移行
- `create_async_engine` / `AsyncSession` / `aiosqlite`
- 既存の crud 層を async に書き換える
- テストの非同期対応（`pytest-asyncio` 等）
- 遅延読み込みが非同期では使えない問題と対処

**できるようになること**：DB アクセスを含めて非同期で動かせる

---

## 第7部 PostgreSQL と Docker

### 22. PostgreSQL への移行
- `compose.yml` に db サービスを追加する（永続化ボリューム、ヘルスチェック）
- ドライバを `asyncpg` に切り替え、接続文字列を設定から差し替える
- SQLite と PostgreSQL の差異で壊れる箇所を洗い出す
- Alembic を PostgreSQL に対して流し直す

**できるようになること**：DB を差し替えてもアプリが動く

### 23. backend の Dockerfile
- uv を使ったイメージビルド（依存インストールとレイヤーキャッシュ）
- マルチステージビルドでイメージを小さくする
- 開発用と本番用の起動コマンドの違い
- compose で backend と db を一緒に立ち上げる

**できるようになること**：`docker compose up` で API が立つ

### 24. デプロイ前の仕上げ
- ヘルスチェックエンドポイント
- 構造化ログと、エラー時に何を残すか
- CORS 設定（Vue から叩けるようにする）
- 本番設定のチェックリスト（DEBUG、秘密鍵、DB 接続数、マイグレーション実行タイミング）

**できるようになること**：フロント着手に進める状態にする

---

## この後（範囲外・必要になったら）

- Vue フロントエンドの実装、OpenAPI からのクライアント自動生成
- CI（GitHub Actions でテストと型チェック）
- バックグラウンドタスク、WebSocket、ファイルアップロード
