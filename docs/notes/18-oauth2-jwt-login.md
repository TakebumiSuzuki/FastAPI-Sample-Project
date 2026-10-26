# 18. JWT + Cookie（リフレッシュトークン）によるログイン認証

## 1. 今回作成した環境・コードの概要

第18章として、JWT（JSON Web Token）によるログイン認証、およびアクセストークン（メモリ管理）とリフレッシュトークン（HttpOnly Cookie）の発行エンドポイントの実装を行った。

### 1. ライブラリ選定と設定追加
- `pyjwt` を `uv add` でインストール（現代の FastAPI 公式推奨）。コード内では `import jwt` で使用。
- `backend/app/core/config.py` と `.env` に JWT 署名および有効期限の設定値を追加：
  - `secret_key: str`: 署名用の秘密鍵（漏洩厳禁のランダム文字列）
  - `algorithm: str = "HS256"`: 共通鍵暗号方式の定番アルゴリズム
  - `access_token_expire_minutes: int = 10`: アクセストークンの有効期間（短め）
  - `refresh_token_expire_days: int = 7`: リフレッシュトークンの有効期間（長め）

### 2. トークン生成関数 (`backend/app/core/security.py`)
- `create_access_token(data: dict[str, Any]) -> str`:
  - 呼び出し元の辞書を書き換えないよう `data.copy()` で複製（副作用の防止）。
  - 有効期限 `"exp"` を UTC 時刻の `datetime` 型で設定（`datetime.now(tz=UTC) + timedelta(...)`）。
  - 種別として `to_encode["type"] = "access"`、トークン固有の識別子として `to_encode["jti"] = str(uuid.uuid4())` を付与。
  - `jwt.encode()` でデジタル署名付きの JWT 文字列を生成して返却。
- `create_refresh_token(data: dict[str, Any]) -> str`:
  - アクセストークンと同様に `data.copy()` で複製。
  - 有効期限を有効期間（日数単位）で設定し、`to_encode["type"] = "refresh"` と `to_encode["jti"] = str(uuid.uuid4())` を付与して生成。

### 3. スキーマ定義 (`backend/app/schemas.py`)
- `UserLogin(BaseModel)`:
  - `email: EmailStr`
  - `password: str`
  - `model_config = ConfigDict(extra="forbid")`
  - フロントエンドとの通信を JSON に統一し、自然な項目名（`email`）で受け取るためのリクエストスキーマ。
- `Token(BaseModel)`:
  - `access_token: str`: レスポンスボディで返す JWT 文字列
  - `token_type: str = "bearer"`: トークン種別（既定値 `"bearer"`）

### 4. ユーザー認証 CRUD 関数 (`backend/app/crud/user.py`)
- `authenticate_user(db_session, email, password) -> User | None`:
  - 引数設計：保存処理（`create_item` 等）ではなく「照合の条件」（`get_item_by_name` 等）であるため、スキーマを展開して `email`, `password` を個別に受け取る。
  - タイミング攻撃（ハッシュ計算の時間差からユーザーの有無を推測する攻撃）を防止するため、モジュール読み込み時に `dummy_hash = hash_password("dummy")` を用意。
  - ユーザー不在時でもダミーハッシュを用いて必ず `verify_password` を1回実行。
  - 不在・不一致を問わず失敗時は一律 `return None` を返却（ユーザー列挙攻撃の防止）。

### 5. ログインエンドポイント (`backend/app/routes/users.py`)
- `@router.post("/login", response_model=Token)`:
  - リクエストボディから `login_in: Annotated[UserLogin, Body()]` を受け取る（JSON 形式）。
  - 引数に `response: Response` を受け取り、FastAPI から下書き用レスポンスオブジェクトを注入。
  - `authenticate_user` で認証失敗時は `HTTPException(401, detail="Incorrect email or password")` を送出。
  - 成功時は `access_token` と `refresh_token` を生成。
  - `response.set_cookie(key="refresh_token", value=refresh_token, httponly=True)` で Cookie に書き込み（`httponly=True` により JS からの盗難を防止）。
  - 戻り値として `{"access_token": access_token}` の辞書を返却（FastAPI が自動で JSON ボディと Cookie を合体して送信）。

### 6. 現在のユーザー取得 Dependency (`backend/app/deps.py`) と認証例外 (`backend/app/exceptions.py`)
- `AuthenticationError(HTTPException)`: ステータスコード `401`（認証失敗）用のカスタム例外クラス。
- `get_user(db_session, credentials) -> User`:
  - `Depends(HTTPBearer())` で `Authorization: Bearer <token>` ヘッダからトークンを抽出。
  - `jwt.decode()` で署名と有効期限を検証し、`payload.get("type") == "access"` を確認。
  - `db_session.get(User, ident=id)` で主キー検索し、失敗時はすべて `AuthenticationError`（401）を送出。

### 7. リフレッシュトークン管理モデル (`backend/app/models/refresh_token.py`) とログアウト (`POST /users/logout`)
- `RefreshToken(Base)`: ホワイトリスト兼監査履歴用のテーブル（`id`, `user_id`, `refresh_token`, `active`）。
- `revoke_refresh_token(db_session, refresh_token)` (`backend/app/crud/user.py`):
  - `RefreshToken.refresh_token == refresh_token` で検索し、`scalar_one_or_none()` で取得したレコード（存在する場合）を `active = False` に更新。
- `@router.post("/logout", status_code=204)`:
  - 状態を変更する操作のため `POST` で定義。
  - `response.delete_cookie("refresh_token")` で Cookie を削除し、Cookie に `refresh_token` があれば `revoke_refresh_token` で DB 側も無効化する（Cookie の有無にかかわらず `204` を返す冪等な設計）。

---

## 2. Q&A (学習中の疑問と解決まとめ)

### Q1. なぜ `OAuth2PasswordRequestForm` ではなく通常の Pydantic スキーマ（JSON）を使うのか？
**A.** フロントエンドの実装負担を減らし、通信形式を JSON に統一するため。
OAuth2 の仕様に沿った `OAuth2PasswordRequestForm` はフォーム形式（`x-www-form-urlencoded`）かつ項目名が `username` 固定になるが、自作 SPA などの Web 開発では JSON 形式で `email` を受け取る方が自然で扱いやすい。FastAPI の `/docs`（Swagger UI）の鍵ボタン連携を優先しない限り、Pydantic スキーマを使う方が実用的。

### Q2. `authenticate_user` の引数にスキーマ（`login_in`）ではなく `email, password` を個別に渡す理由は？
**A.** 処理の役割が「DB へのデータ保存」ではなく「検索・照合の条件」だから。
`create_item` や `create_user` などの作成・更新処理は、モデルの属性を一括登録するためにスキーマオブジェクトを直接渡すのが自然。一方、認証処理は「メールアドレスで検索しパスワードを照合する」という検証処理であり、`get_item_by_name` に `item_name` を渡すのと同様に、必要な値を展開して渡す方がコードベース全体と一貫する。

### Q3. アクセストークンとリフレッシュトークンはデータとして区別があるのか？
**A.** データ形式上の区別はない。
どちらも `pyjwt` で署名したただの JWT 文字列。見分けをつけるために、作成時にペイロードに `"type": "access"` や `"type": "refresh"` といった独自項目を入れ、アプリ側のロジックで検証・区別して利用する。

### Q4. `response: Response` はどういう時に使い、引数に書くだけでなぜ `return` せずに Cookie が送れるのか？
**A.**
#### どういう時に使うのか
エンドポイントから通常のデータ（辞書や Pydantic モデル）を返しつつ、**Cookie のセット・削除、カスタムヘッダーの追加、ステータスコードの動的な変更**といった「HTTP レスポンスの付帯情報（メタ情報）」だけを操作したい時に使う。
今回は、レスポンスボディ（JSON）として `access_token` を返しつつ、**`refresh_token` を Cookie（HttpOnly）に入れてクライアントへ渡すため**に使用している。

#### `return` せずに反映される仕組み（参照渡しと自動合体）
FastAPI の内部ラッパー関数が一時的な `Response` インスタンス（ミュータブル＝変更可能なオブジェクト）を作り、その**参照**を引数に渡して後から合体してくれるため。

1. **ラッパー関数でのローカル生成**
   - エンドポイント関数を包む FastAPI の「内部ラッパー関数」がリクエストごとに動く。
   - そのラッパー関数内のローカル変数として、その通信専用の空の `Response` インスタンスが作られる（リクエストごとのローカル変数なので、他のユーザーの通信と混ざることはない）。
2. **引数への参照の注入**
   - エンドポイント関数の引数に `response: Response` と書くと、FastAPI がそれを検知し、1 で作ったインスタンスの**参照（メモリアドレス）**を引数として渡す。
3. **参照越しの書き換え（ミューテーション）**
   - `Response` インスタンスはミュータブル（後から中身を変更可能）なため、関数内で `response.set_cookie(...)` や `response.headers`・`response.status_code` を操作すると、ラッパー関数側が握っている同じインスタンスの中身が直接書き換わる。
   - そのため、エンドポイント関数から `response` 自体を `return` する必要がない。
4. **返却データとメタ情報の自動合体**
   - 関数が `return {"access_token": ...}` で返したデータ（ボディ）と、3 で書き換えられた `Response` インスタンス（Cookie やヘッダーなどのメタ情報）を、ラッパー関数が最後に合体させてクライアントへ送信する。
   - これにより、関数側でわざわざ `return JSONResponse(...)` と包み直す必要がなく、`response_model=Token` による型検証や自動ドキュメント生成を活かしたままデータ返却に専念できる。

### Q5. `response: Response` に `Annotated` は使えないのか？
**A.** 使えない。
`Annotated[型, Body()]` や `Annotated[型, Depends()]` は「リクエストからどこを抜き出すか」を指示するための記法。`Response`（や `Request`）は FastAPI が型を見て直接渡す特別枠のため、`Annotated` で追加の指示を付けると起動時エラーになる。

### Q6. `status.HTTP_401_UNAUTHORIZED` と `401` は同じ？ `headers={"WWW-Authenticate": "Bearer"}` は必須？
**A.** `status.HTTP_401_UNAUTHORIZED` の実体は単なる整数の `401` なので、直接 `401` と書いて問題ない。
`WWW-Authenticate` ヘッダーは RFC 仕様上の推奨ルールだが、ブラウザ標準のダイアログを使わない一般的な Web/SPA 開発では省略しても動作に支障はない。

### Q7. トークン生成関数で `data["exp"] = expire` を直接代入してはいけない理由は？
**A.** Python の辞書は参照渡しであるため、呼び出し元の変数を直接書き換えてしまう（副作用が起きる）。後続の処理でその辞書を再利用した際に意図しないキー（`"exp"`）が混入してバグの原因になるのを防ぐため、`to_encode = data.copy()` で複製してから代入するのが定石。

### Q8. ユーザー認証で未登録時とパスワード不一致時で例外を分けてはいけない理由は？
**A.** エラーメッセージを区別すると、攻撃者に「そのメールアドレスが登録済みである」ことを見破られる（ユーザー列挙攻撃）ため。また、ハッシュ計算にかかる時間の差（数十ミリ秒）からユーザーの有無を特定されるタイミング攻撃を防ぐため、結果を区別せず同じ計算時間・同じ 401 エラーに統一する。

### Q9. 型注釈が `data: dict[str, Any]` なのに、なぜ `"sub": str(user.id)` と文字列化が必須なのか？
**A.** Python の型注釈としては `int` でも通るが、PyJWT ライブラリが `jwt.decode` 時に「`sub` の値は文字列でなければならない（RFC 7519 準拠）」という厳格な型チェックを行っており、数値のままだと `InvalidSubjectError` でクラッシュするため。

### Q10. ログアウト時になぜ `refresh_token` を DB（ホワイトリスト）で管理するのか？
**A.**
- **JWT の性質と有効期間**：JWT は署名だけで検証する仕組みのため、サーバー側から一方的に消せない（`httponly=True` で JS からの取得は防げても、画面の開発者ツール等から控えられれば期限まで使えてしまう）。そのため、`access_token` は有効期間を短く（10〜30分程度）して失効リスト無しで運用し、有効期間が長い `refresh_token` は DB で失効管理を行う。
- **ホワイトリスト vs ブラックリスト**：ブラックリスト（失効分のみ記録）は DB 書き込みが少ない利点がある一方、ホワイトリスト（発行時に DB 保存）は「パスワード変更時の全端末一括ログアウト」や「ログイン中端末の把握」が容易であり、`refresh_token` の管理ではホワイトリストが主流。
- **ログアウト時の特定方法**：`user.id` で消すと全端末がログアウトされるため、通常のログアウトでは Cookie（`Cookie()`）の `refresh_token` で操作端末の分だけを無効化するのが一般的（監査目的を残す場合は行削除ではなく `active=False` に更新する）。

### Q11. `HTTPBearer` と `HTTPAuthorizationCredentials` の役割は？
**A.**
- HTTP ヘッダは封筒の表書きのように `キー: 値` の1行テキストが並ぶ場所であり、アクセストークンは `Authorization: Bearer <トークン>` の形で送られる（原理的には `Header()` + Pydantic スキーマ + `field_validator` で `"Bearer "` を剥がすことも可能だが手間がかかる）。
- `HTTPBearer()` は `__call__` を持つコーラブルなインスタンスで、`Depends(HTTPBearer())` と括弧付きで指定すると、ヘッダから `"Bearer "` を自動で剥がして `HTTPAuthorizationCredentials`（`scheme: str` と `credentials: str` を持つ Pydantic `BaseModel`）を返してくれる。`OAuth2PasswordBearer` と違い form 送信も不要。
- なお、単一の文字列なのに `credentials` と複数形なのは、英語の慣習および HTTP 規格（RFC 9110）の用語に合わせているため。

### Q12. `get_user` での例外処理と `401` / `403` の使い分け、`db_session.get()` とは？
**A.**
- **`try ... except` が必須な理由**：`jwt.decode()` が投げる `jwt.InvalidTokenError` 等を捕まえて `HTTPException` 系に変換しないと、未処理例外として `500` エラーになってしまうため。
- **`401` と `403` の違い**：トークン無効・期限切れなど「誰だか確認できない（認証＝Authentication の失敗）」は **`401`（`AuthenticationError`）**。本人確認後に「権限がない（認可＝Authorization の失敗）」は **`403`（`AuthorizationError`）**。
- **`db_session.get(User, ident=id)`**：主キー（`ident` は identity / identifier の略で、組み込み関数 `id()` との衝突回避）を指定して1件取得する SQLAlchemy の短縮メソッド。

### Q13. `RefreshToken` モデルに `unique=True` や `ForeignKey` を付けない理由は？
**A.**
- **`unique=True` を付けない理由**：トークン生成時に `jti`（`uuid.uuid4()`）を付与しており、かつサーバー自身が生成した値しか保存しないため、論理的に同じトークン文字列が重複することがないため。
- **`ForeignKey` を付けない理由**：`user_id` は外部入力ではなく認証直後の実在する `user.id` のみが入るため不正値の心配がなく、また将来ユーザーを削除しても監査履歴を独立して残せるため。

### Q14. JWT はパスワードハッシュと違い「元に戻せる（可逆）」のか？ 同じ辞書からは同じ文字列になる？
**A.**
- **可逆性**：パスワードハッシュ（一方通行）と違い、JWT のデータ部分（ヘッダ・ペイロード）は単なる **Base64 変換**なので可逆であり、秘密鍵がなくても誰でも元の辞書に復元して中身を読める（末尾の「署名」部分のみが改ざん検知用のハッシュ計算）。そのため、JWT にパスワード等の秘密情報は入れない。
- **同じ辞書なら同じ文字列（`jti` による一意化）**：JWT 自体にはパスワードハッシュのように毎回ランダムなソルトを混ぜる仕組みはないため、辞書の中身（`sub`、`email`、秒単位の `exp`、`type`）と秘密鍵が同じなら、同一秒内の発行で全く同じ JWT 文字列になってしまう。これを防ぐため、ペイロードに `jti`（JWT ID：`uuid.uuid4()` によるランダムな一意識別子）を含めて毎回異なるトークン文字列になるようにしている。

### Q15. ログアウト処理（`logout_user` / `revoke_refresh_token`）の設計のポイントは？
**A.**
- **`refresh_token` の `jwt.decode` 検証が不要な理由**：DB には自サーバーが発行したトークンしか入っていないため DB 検索自体が検証になり、また期限切れトークンであってもエラーにせずログアウト完了にするのが自然なため。
- **検索条件に `user.id` が不要な理由**：`refresh_token` 文字列自体に `sub`（`user.id`）が含まれており、他人のトークンと文字列が一致することはないため。
- **`scalar_one_or_none()` を使う理由**：`jti` によってトークン文字列は常に一意（該当は0件か1件）になるため、`scalar_one_or_none()` で取得し、存在するときのみ `active = False` に更新する（0件のときも例外にならず `None` が返る）。
- **冪等性（べきとうせい / idempotency）**：Cookie に `refresh_token` があってもなくても、何度呼んでも同じ「ログアウト済み状態」になり `204` が返る性質のこと。

### Q16. `authenticate_user` の中でトークン登録（`register_refresh_token`）や commit を一括で行わない理由は？
**A.**
- **commit する変更がない**：`authenticate_user` は DB からユーザーを検索してパスワードを照合する「読み取り処理」だけを行うため、commit するデータ自体が存在しない。
- **責務の分離（単一責任の原則）**：`authenticate_user` の役割は「認証（メールとパスワードの照合）」であり、「トークンの発行・永続化」ではない。トークン生成は認証成功後にルート層で行われるため、生成された文字列を DB に保存する `register_refresh_token` もその直後に呼ぶのが自然。

### Q17. ログイン状態を作るフィクスチャーと、未認証テストでのクライアントの使い分けは？
**A.**
- **ログイン状態を作るフィクスチャー（`logged_in_context`）**：
  - 認証必須のエンドポイント（正常系のログアウトや、今後の保護されたルート）をテストする際、都度ログイン処理を書く手間を省くために使う。
- **未認証テストで通常の `client` を使う理由**：
  - 未認証（ログインしていない状態）の振る舞いを確かめるテストで、事前にユーザー作成やログイン処理を行うのはテストの意図と矛盾し、実行速度も無駄になる。まっさらな素の `client` からリクエストを送るのが最もシンプルで意図が明確になる。
- **ヘッダー有無とエラーの種類（検証レイヤーの違い）**：
  - `headers={"Authorization": "Bearer fake_token"}`（不正なトークン）：トークンの中身を検証するアプリのロジック（`get_user`）に到達し、独自の認証エラー（`code: "invalid_credentials"`）になる。
  - ヘッダーなし：FastAPI の標準セキュリティ機構（`HTTPBearer`）で手前で弾かれ、共通エラー（`code: "http_error"`, `message: "Not authenticated"`）になる。

### Q18. DB 検証や 204 レスポンスをテストする際の注意点は？
**A.**
- **モデルインスタンスと値の比較**：`scalar_one()` 等で取得した結果はテーブルモデルのインスタンス（オブジェクト）であるため、トークン文字列と比較する場合は属性を指定して `saved.refresh_token == token` と比較する。
- **論理削除の検証**：レコードを `DELETE` するのではなく `active = False` に更新する論理削除の場合、レコードが消える（`is None`）のではなく、レコードが存在した上で `result.active is False` であることを検証する。
- **204 (No Content) レスポンスの検証**：ステータスコード `204` は仕様上レスポンスボディが空のため、`response.json()` を呼ぶと JSON デコードエラーになる。本文が空であることを検証したい場合は `response.text == ""`（または `not response.content`）を用いる。

### Q19. トークンの中身に不備があるとき、401 / 422 / 500 のどれにすべき？
**A.**
- **署名・期限・`type` の不備 → 401**：トークンは身元証明なので、中身がおかしければ「認証失敗」。422 は FastAPI（Pydantic）がリクエストの形式・型の不備に対して返すもので、認証ロジックの判定には使わない。
- **キャッチし忘れると 500**：`payload["type"]` の `KeyError` などを放置すると、クライアント起因なのにサーバーのバグ（500）扱いになる。
- **署名検証を通った後の `sub` / `email` 欠落 → 500 のままでよい**：署名が正しい＝自サーバーが発行したトークンなので、欠落は発行側のバグ。401 にするとバグが「認証失敗」に紛れて気づきにくくなる（`secret_key` が漏れていない前提）。

### Q20. `scalar_one()` / `scalar_one_or_none()` / `scalars()` の使い分けは？
**A.** `scalar_one()` は「ちょうど1件」が前提で、0件なら `NoResultFound`、2件以上なら `MultipleResultsFound` を投げる（未処理なら 500）。0件か1件の検索（`jti` で一意化されたトークンの検索など）は `scalar_one_or_none()` を使い、複数件ありうる検索は `scalars()` で受ける。

### Q21. リフレッシュ時の `active` 検証を `revoke_refresh_token` に入れない理由は？
**A.** 目的が逆だから。ログアウトは「既に無効・不在でも 204 で終わる（冪等）」べきで、リフレッシュは「無効・不在なら 401 で拒否」すべき。`revoke_refresh_token` に 401 を入れるとログアウトが壊れるため、検証はリフレッシュ側の関数で行う。

### Q22. JWT の `sub` と重複するのに `RefreshToken.user_id` カラムを持つ理由は？
**A.** 「パスワード変更時に全端末ログアウト」「ログイン中端末の一覧」など、ユーザー単位の操作を `WHERE user_id = ?` で行うため。カラムがないと全トークンをデコードして `sub` を調べるしかない。トークン1件の特定には不要なので、今の機能だけ見れば冗長。

### Q23. トークン処理を `core/security.py` と `crud` にどう分ける？
**A.**
- **DB を使わない JWT 検証（decode + `type` チェック）→ `security.py`**：`decode_token(token, expected_type)` にまとめ、`deps.py` の `get_user` と `reissue_tokens` の重複をなくす。
- **DB 操作（検索・無効化・登録）→ `crud`**。
- **core 層は HTTP の例外を投げない**：`type` 不一致も `jwt.InvalidTokenError` で投げ、呼び出し側で `AuthenticationError`（401）に変換する。core 層が HTTP（FastAPI）に依存しない。
- **命名**：古いリフレッシュトークンを無効化して新しいものを発行することを「トークンローテーション」と呼ぶ。`refresh_tokens` は名詞（モデル名・テーブル名）とも読めて紛らわしい。

### Q24. `settings = get_settings()` をモジュールのトップに書くべき？
**A.** 書かない方がよい。`get_settings` は `@lru_cache` 付きなので関数内で毎回呼んでもコストはほぼない。トップに書くと import 時の設定で固定され、テストで `get_settings.cache_clear()` しても反映されない。また import しただけで `.env` を読みにいく。

### Q25. 例外まわりの Python の書き方
**A.**
- **`except A, B, C:`**：Python 3.14 からは括弧なしでも OK（PEP 758）。それ以前は `except (A, B, C):` が必須。
- **`raise ... from None`**：`except` 内で別の例外を投げるとき、元の例外がエラー表示に連鎖して出るのを止める（ruff の B904 が指摘する）。
- **`return a, b` と `return (a, b)` は同じ**：タプルを作るのは括弧ではなくカンマ。

### Q26. Cookie の `path` と `delete_cookie` の仕組みは？
**A.**
- **`path` は1つだけ**：カンマ区切りで複数指定はできない（カンマも path の文字列の一部になる）。
- **前方一致で送られる**：`path="/users"` なら `/users`・`/users/refresh`・`/users/logout` には送られ、`/items` や `/usersXYZ` には送られない（直後が `/` のときだけ一致）。refresh と logout の両方で Cookie を読むので `"/users"` にしている。
- **set と delete で path をそろえる**：ブラウザは Cookie を「名前 + ドメイン + path」で区別する。`delete_cookie` の既定値は `path="/"` なので、`/users` で保存したら削除時も `path="/users"` が必要。
- **`delete_cookie` の正体**：サーバーはブラウザの Cookie を直接消せない。同じ名前・path で `Max-Age=0` の `Set-Cookie` を送ると、ブラウザが上書き → 期限切れ → 即削除する（RFC 6265 5.3 節）。
