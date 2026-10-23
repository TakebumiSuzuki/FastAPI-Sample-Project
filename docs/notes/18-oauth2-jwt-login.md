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
  - 種別として `to_encode["type"] = "access"` を付与。
  - `jwt.encode()` でデジタル署名付きの JWT 文字列を生成して返却。
- `create_refresh_token(data: dict[str, Any]) -> str`:
  - アクセストークンと同様に `data.copy()` で複製。
  - 有効期限を有料期間（日数単位）で設定し、`to_encode["type"] = "refresh"` を付与して生成。

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
