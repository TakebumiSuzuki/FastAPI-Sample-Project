# 15. フィクスチャとテスト用 DB の分離

## 1. 今回作成した環境・コードの概要

テスト実行時に本番 DB を汚さず、テスト同士が影響し合わないよう **インメモリ SQLite** と **pytest フィクスチャ** を導入。

### `backend/tests/conftest.py`
- `@pytest.fixture` を定義し、`yield` の前後に準備・後片付けを記述。
- `db_session` フィクスチャ: テスト実行直前に `create_all` でテーブル作成、`yield` 後に `drop_all` で削除。
- `client` フィクスチャ: `app.dependency_overrides[get_db_session]` にテスト用セッションを割り当て、`TestClient(app)` を作成。
- `StaticPool`: スレッド間（FastAPI の非同期処理）でインメモリ DB を共有するために `poolclass=StaticPool` を指定。

---

## 2. Q&A（学習中の疑問と解決まとめ）

### Q1. `SessionLocal` というネーミングの理由は？
**A.** FastAPI 公式由来の慣例。SQLAlchemy の `Session` クラスと区別し、「1リクエスト（スレッド）内でローカルに使い回すセッション」であることを示す。

### Q2. `create_all` / `drop_all` に `bind=engine` が必要な理由は？
**A.** `Base.metadata` はテーブル構造の設計図しか持たないため、`CREATE TABLE` や `DROP TABLE` といった DDL 文をどの DB に送信・実行するかを指定するために `bind=engine` が必要。

### Q3. `app/models/__init__.py` に `from app.models.base import Base` を書いてまとめるのは推奨される？
**A.** 推奨される（再エクスポート）。呼び出し側で `from app.models import Base` と簡潔に書け、モジュールの内部階層を隠蔽（カプセル化）できるため。

### Q4. `import app.models` ではなく `from app.models import Base` と書くべき？
**A.** `from app.models import Base` が強く推奨される。何を使っているかが一目で分かり（可読性）、リンターによる未使用インポート検出や型チェックが正確になる。

### Q5. `engine` はフィクスチャの外（モジュールレベル）に置いてよい？
**A.** 問題ない。`engine` は接続設定（プール）を持つだけであり、実際のテーブル作成・破棄・データ操作は `db_session` 内でテストごとに制御されるため。

### Q6. `dependency_overrides` とは？
**A.** FastAPI が持つ「依存関係を上書きする辞書（`dict`）」。
- **キー**: 本番用関数（`get_db_session`）
- **値**: テスト用差し替え関数（`override_get_db`）  
テスト実行時に `Depends(get_db_session)` を検知すると、自動でテスト用関数へ差し替えて呼び出してくれる。

### Q7. `db_session` と `client` のフィクスチャを分ける理由は？
**A.** API 通信を介さない CRUD 関数の単体テストなどで `db_session` だけを単体で再利用（使い回し）できるようにするため。

### Q8. `Generator[TestClient, None, None]` の第2・第3引数は何？
**A.** `Generator[YieldType, SendType, ReturnType]`。
- 第1引数: `yield` で渡す型（`TestClient`）
- 第2引数: 外部から受け取る型（使わないので `None`）
- 第3引数: 最終的に `return` する型（使わないので `None`）

### Q9. `response.json()` は内部で何をしている？
**A.** `response.text`（JSON 文字列）を取り出し、`json.loads(response.text)` を実行して Python の辞書（`dict`）に復元している便利ショートカットメソッド。

### Q10. `no such table` や Pydantic バリデーションエラーが起きた原因は？
**A.** 
1. **`no such table`**: SQLite in-memory は接続スレッドごとに別の空 DB になるため、`StaticPool` で接続を共有して解決。
2. **`ResponseValidationError`**: `Category` の `name` が `min_length=3` 以上を要求していたため、テスト用カテゴリ名を 3 文字以上（`"家電製品"`）に変更して解決。
