# 19. 認可：現在のユーザー依存性とエンドポイント保護

## 1. 今回作成・修正したコードの概要

第19章として、第18章で構築した JWT 認証基盤（`get_user` 依存性）を既存エンドポイントへ適用し、未認証リクエストを遮断する認可ガードの実装、アカウント状態管理カラム（`is_active`）の追加、およびテストの認証対応を完了した。

### 1. User モデルへの `is_active` 追加とマイグレーション
- `backend/app/models/user.py`:
  - `is_active: Mapped[bool] = mapped_column(Boolean(), default=True, server_default="1")` を追加。
  - アカウント停止や論理削除の基盤を用意。
  - 既存データがある状態でのマイグレーション（NOT NULL 制約）を考慮し、DB 側のデフォルト値（`server_default="1"`）を指定。
- Alembic によるマイグレーション実行：
  - `uv run alembic revision --autogenerate -m "add is_active column to User table"`
  - `uv run alembic upgrade head`

### 2. 現在のユーザー取得 Dependency (`backend/app/deps.py`) の拡張
- `get_user`:
  - DB から取得したユーザーが非アクティブ（`user.is_active is False`）の場合にも `AuthenticationError()`（401）を送出してアクセスを遮断。

### 3. エンドポイントの保護設計 (`backend/app/routes/categories.py`)
- **GET /categories**:
  - 一般公開（未ログインでも誰でも閲覧可能）。
  - `dependencies` は付与せず、既存の誰でも見られる仕様を維持。
- **POST /categories**:
  - `dependencies=[Depends(get_user)]` を付与し、ログイン済みユーザーのみにデータ作成を許可。
  - ルート関数内で `user` の値自体を使わないため、引数ではなくデコレータの `dependencies` リストで指定。

### 4. テストの修正と新規追加 (`backend/tests/test_categories.py`)
- **既存 POST テスト（6件）の認証対応**:
  - `conftest.py` の `logged_in_context` フィクスチャを活用し、各 POST リクエストに `headers={"Authorization": f"Bearer {access_token}"}` を付与。
  - 変数に `logged_in_client: TestClient` の型注釈を付与し、エディタ上での `response.status_code` や属性補完を有効化。
- **未認証ガードテストの追加**:
  - `test_create_category_unauthorized(client)`:
    - トークンなしで POST した際、FastAPI の `HTTPBearer` により手前で弾かれ、`status_code == 401` かつ `code == "http_error"`（`message == "Not authenticated"`）になることを検証。
- **実行結果**: 全31件のテストが全件 PASS。

---

## 2. Q&A (学習中の疑問と解決まとめ)

### Q1. エンドポイントを保護する際、Flask と FastAPI でどう書き方が違う？
**A.**
- **Flask**: `@login_required` などのデコレータを用いて関数を修飾し、手前で弾くのが一般的。
- **FastAPI**: 関数の引数に `user: Annotated[User, Depends(get_user)]` と依存性注入（Depends）を指定するか、引数で値を使わない場合は `@router.post(..., dependencies=[Depends(get_user)])` とルートデコレータに渡す。FastAPI が関数本体を実行する手前で依存関係を自動解決し、不正時は例外で弾く。

### Q2. `get_user` は毎回 DB を見に行くのか？ トークン検証だけで済ませてはいけない理由は？
**A.** 毎回必ず DB を検索して存在確認と状態確認を行う。
トークンの署名や期限が正しくても、「その間にユーザーが退会・削除された」「管理者にアカウントを凍結（`is_active = False`）された」といった事態に対応するため。署名検証だけで DB 検索をスキップすると、すでに無効化されたユーザーがトークンの期限までアクセスし続けられてしまう。

### Q3. User モデルに `default=True` と `server_default="1"` の両方を書く理由は？
**A.**
- **`default=True` (Python 側)**: Python で `User(email=..., hashed_password=...)` とインスタンスを生成した瞬間に、メモリ上のオブジェクトに `is_active=True` をセットする。
- **`server_default="1"` (DB 側)**: データベース側で INSERT されたときの初期値。特に既存データが存在するテーブルに `NOT NULL` カラムを追加するマイグレーション時、DB が既存行に埋める初期値として必須となる（ないと `Cannot add a NOT NULL column with default value NULL` で失敗する）。
- SQLite では真偽値が整数 `1` / `0` で扱われるため、文字列 `"1"` を渡す。

### Q4. ロール（権限）を導入する場合、トークンと User テーブルのどちらで管理すべき？
**A.** 安全性を最優先するなら **User テーブル** で管理する。
JWT トークンは一度発行されるとサーバー側から途中で中身を書き換えられない。そのため、トークン内に `role: "admin"` を入れてしまうと、管理者が一般ユーザーへ降格（権限剥奪）しても、トークンの有効期限が切れるまで管理者権限を悪用され続けるリスクがある。User テーブルで管理し、リクエストごとに DB を参照すれば、権限変更が全端末で即時反映される。

### Q5. Web API におけるエンドポイント保護のよくある設計パターンは？
**A.** HTTP メソッドごとに公開範囲を分ける設計が一般的。
- **GET（閲覧系）**: 未ログインの訪問者でも画面表示できるよう一般公開にする。
- **POST / PUT / DELETE（更新系）**: データの改変・破壊を伴うため、ログイン済みユーザー（または管理者）に限定する。

### Q6. なぜ実際の開発では早い段階で認証（JWT）を作っておくべきなのか？
**A.** 後から認証を入れると、それまでに書いた全エンドポイントのテスト（正常系・異常系・バリデーション）すべてに「認証ヘッダーを付与する」という大規模な書き直し作業が発生するため。初期に認証の土台とテスト用フィクスチャ（`logged_in_context` 等）を用意しておけば、最初から認証を前提にしたテストをスムーズに書き進められる。

### Q7. `TestClient` で認証ヘッダーを渡す際、なぜクライアント全体ではなくリクエストごとに渡すのか？
**A.** 他のテストへの副作用（テストの汚染）を防ぐため。
`client.headers["Authorization"] = ...` のようにクライアントオブジェクト自体のヘッダーを書き換えてしまうと、後続の「未認証で弾かれることを確かめるテスト」にヘッダーが残ってしまい、テスト同士が干渉して誤作動の原因になる。`client.post(..., headers={...})` とリクエスト単位で渡すのが安全で確実。

### Q8. テストコードで `response.status_code` などの属性チェック・補完が効かなかった理由は？
**A.** テスト関数の引数や変数に型注釈がなく、エディタ（Pylance）が型を `Any`（型不明）と判定していたため。
pytest のフィクスチャは実行時に動的注入されるため、コードの文字だけを見る静的解析ツールには型が分からない。
`logged_in_client: TestClient = logged_in_context["logged_in_client"]` のように明示的に型注釈を添えることで、戻り値 `response` の型が特定され、属性補完やチェックが正常に機能する。

### Q9. 未認証時のエラーコードが `invalid_credentials` ではなく `http_error` になった理由は？
**A.** エラーを検出して弾いたレイヤー（場所）が異なるため。
- **ヘッダーなし**: FastAPI 標準のセキュリティ機構（`HTTPBearer`）がルートの手前で弾くため、共通エラーハンドラー経由で `code: "http_error"`, `message: "Not authenticated"`（401）になる。
- **不正なトークン**: ヘッダーは届いたが、自作の `get_user` 内の検証ロジックで弾かれた場合に、自作例外の `AuthenticationError`（`code: "invalid_credentials"`）になる。

### Q10. トークンの期限切れテストをテスト側で「過去日付で再署名」して作る手法への違和感と、実務でのアプローチは？
**A.** 実際の利用シーン（時間が自然に経過すること）から乖離しており、ライブラリ（PyJWT）の内部検証をアプリ側がわざわざ自作テストしている形になるため違和感が生じる。
実務では以下のどちらかで対応するのが一般的：
1. **書かない（割り切り）**: 期限切れ判定は PyJWT の責務なので、アプリ側は「不正トークンで 401 になる」ことの確認で十分とする。
2. **時刻をモックする**: `freezegun` などのライブラリを使い、サーバーの時計を仮想的に11分進めることで、自然に発行されたトークンが期限切れになる様子をそのまま検証する。

### Q11. 「自分のデータしか触れない認可」はどう実装する？ Dependency に入れることはある？
**A.** 関数内でのチェックと、Dependency への切り出しの両方が使われる。
- **関数内でチェック**: 直感的でわかりやすい。
- **Dependency に切り出し**: `item_id: Annotated[int, Path()]` と `current_user: Annotated[User, Depends(get_user)]` を受け取る依存関数（例: `get_owned_item`）を作成する。Update や Delete など複数ルートで発生する「404 チェック」と「本人のデータ確認（403）」を共通化できるため、FastAPI では定石の手法。

### Q12. ユーザー関連のエンドポイント設計と `/me` の使い分けは？
**A.**
- **新規登録 (`POST /users`)**: 登録前は「me（ログイン中の自分）」が存在しないため、`/me` ではなくコレクションへの追加として `POST /users` にする。
- **自分自身の操作 (`/users/me`)**: `GET`（情報表示・ログイン維持確認）、`PATCH`（プロフィール変更）、`DELETE`（退会）。URL に `user_id` を含めずトークンから自分自身を特定するため、他人の ID を誤爆・改ざんする事故を根本から防止できる。
- **管理者による強制停止 (`DELETE /users/{user_id}`)**: 管理者が特定ユーザーを BAN する操作。本人の退会とは目的が異なるため、URL で対象 ID を指定させ、管理者権限チェックを挟む別エンドポイントとして分離する。

### Q13. `GET /users`（一覧取得）のセキュリティ上の注意点は？
**A.** 個人情報の漏洩を防ぐため、一般公開は絶対にせず管理者専用にする。
誰でも叩ける状態だと登録者全員のメールアドレスや ID が第三者に流出してしまう。そのため、管理者（Admin）ロールを必須にするか、管理画面を別システムとして分離している場合はエンドポイント自体を作らないのが基本。

### Q14. 管理者専用エンドポイント（ロール判定）を FastAPI で綺麗に実装するには？
**A.** サブ依存関係（Dependency の連鎖）を活用し、`get_user` を受け取る `get_admin` 依存関数を作る。
FastAPI は依存関数の中で別の依存関数を引数に受け取れるため、以下のように連鎖させるのが王道：

```python
def get_admin(current_user: Annotated[User, Depends(get_user)]) -> User:
    if not current_user.is_admin:
        raise HTTPException(status_code=403, detail="The user doesn't have enough privileges")
    return current_user
```
未ログインなら手前の `get_user` で 401、一般ユーザーなら `get_admin` で 403 が返る。管理者用エンドポイントやルーター全体に `Depends(get_admin)` を適用するだけで、権限チェックを簡潔に一元管理できる。
