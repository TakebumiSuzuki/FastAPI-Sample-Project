# 16. TDD サイクルで1機能を実装する

## 1. 今回作成した環境・コードの概要

TDD の **Red(失敗するテストを書く)→ Green(通す)→ Refactor(整える)** サイクルを、`GET /categories` と `POST /categories` の2エンドポイントで実践した。

### GET /categories

- `backend/tests/test_categories.py`(Red): `client` / `db_session` フィクスチャを使い、カテゴリを2件作成 → `GET /categories` を叩いて件数と内容を検証するテストを先に書いた。
- `backend/app/crud/category.py`(Green): `get_categories(db)` で `select(Category)` の結果一覧を返す。
- `backend/app/routes/categories.py`(Green): `APIRouter(prefix="/categories")` に `GET ""` を追加し、`crud.get_categories` を呼んで返す。
- `backend/main.py`(Green): `categories_router` を `include_router` で登録。
- Refactor: 既存の `items` 側の実装とパターンが揃っており、今回は整える箇所なし。

### POST /categories

- Red: `test_create_category`(正常系)を先に書き、405(ルート未定義)で失敗することを確認。
- Green(1回目): `name: Annotated[str, Body()]` で受ける実装を書いたが 422 になった。単体の `str` を `Body()` で受けると、ボディ全体がその値そのものとして扱われる(`{"name": "foods"}` という形は想定外)ため。
- Green(2回目): `app/schemas.py` に `CategoryCreate(CategoryBase)` を追加し、`new_category: Annotated[CategoryCreate, Body()]` として受け直して成功。`items` 側の `ItemCreate` と同じパターン。
- 非ハッピー系を3件追加(いずれも Pydantic のバリデーションで自動的に 422 になるため、実装コードの追加なしで Green):
  - `test_create_category_name_too_short`: `name` が `min_length=3` 未満
  - `test_create_category_name_too_long`: `name` が `max_length=30` 超過(`"a" * 31` で表現)
  - `test_create_category_extra_field_forbidden`: `CategoryBase` の `extra="forbid"` により未定義キーを拒否することの確認

**状態**:`GET /categories` / `POST /categories` とも完了。16章はここで区切りとする。

---

## 2. Q&A(学習中の疑問と解決まとめ)

### Q1. `db_session.add([a, b])` で複数オブジェクトをまとめて追加できる?
**A.** できない。`Session.add()` は単一オブジェクト専用(`instance: object`)。複数まとめて追加するときは `add_all([a, b])` を使う(SQLAlchemy 実ソースの `Session.add` シグネチャで確認)。

### Q2. pytest はテスト関数の引数(`client`, `db_session`)をどう fixture に結びつけている?
**A.** テスト収集時に関数の引数名を読み取り、同名の fixture を探して「引数名→fixture定義」の対応表を作っておく。実際のテスト実行時にその対応表を辿って各 fixture を呼び出し、戻り値を引数に注入してからテスト関数を実行する(pytest 公式ソース `FixtureManager.getfixtureinfo` で確認)。

### Q3. `assert` は Python の組み込み関数?
**A.** 違う。`if` や `return` と同じ「文(statement)」であり、キーワードの一種(`keyword.kwlist` に含まれることを確認)。関数ではないので再定義や変数への代入はできない。pytest は素の `assert` 文をそのまま使いつつ、テストモジュール import 時に AST(コードの構文木)を書き換えて `assert 3 == 4` のような内訳付きの失敗メッセージを追加している(pytest 公式ドキュメント「Assertion Rewriting」で確認)。

### Q4. `assert` は元々何のために作られた?
**A.** プログラムを書いた本人が、内部の前提条件が正しいかをデバッグ時に自己チェックするための機構。外部入力の検証用途は想定されていない。`python -O` を付けると `__debug__` が `False` になり、`assert` 文はコンパイル時に丸ごと消える(CPython 公式ドキュメント「simple_stmts」で確認)。

### Q5. `Mapped[list["Item"]]` の `"Item"` が Ruff の F821(未定義の名前)になるのはなぜ?
**A.** 文字列で書いた前方参照(forward reference)も Ruff は中身を解析するため、`Item` がそのファイル内で import も定義もされていないと未定義扱いになる。

### Q6. `from __future__ import annotations` を付ければ直る?
**A.** 直らない(実際に `ruff check` で確認)。この import は型注釈の評価タイミングを遅らせるだけで、Ruff の静的解析には影響しない。`TYPE_CHECKING` ブロックで実際に import する必要がある(実行時は `False` になるため循環 import は避けられる)。

### Q7. `.scalars().all()` の戻り値を `list[Category]` として受けると Pylance がエラーを出すのはなぜ?
**A.** SQLAlchemy 公式の型定義で `.all()` の戻り値は `Sequence[X]` と宣言されている(実行時には実際に list だが、型としては `Sequence`)。`Sequence` は `list` より緩い(変更操作を保証しない)型なので、より狭い `list[X]` に代入しようとすると型エラーになる。対処は関数の戻り値の型を `Sequence[X]` に合わせるか、`list(...)` で明示的に変換するかの2通り。

### Q8. `APIRouter` の `prefix` の書き方のルールは?
**A.** 先頭にスラッシュを付け、末尾には付けない(`"/categories"` であって `"categories/"` ではない)。FastAPI 公式ドキュメントで明記されている。

### Q9. 単体の `str` を `Body()` で受けると何が起こる?
**A.** ボディ全体がその値そのものとして扱われる。`{"name": "foods"}` のようなオブジェクト形式で受けたい場合は Pydantic モデル(`CategoryCreate` 等)を渡すか、`Body(embed=True)` を付ける必要がある(実行して 422 になることを確認、FastAPI 公式リファレンスで `embed` の仕様を確認)。

### Q10. `Body()` は引数を取らない?
**A.** 取る。`embed` / `title` / `description` / `min_length` / `max_length` / `gt` / `ge` など、`Query()` や `Path()` と同様の引数がある(FastAPI 公式リファレンス `fastapi.Body` シグネチャで確認)。ただし Pydantic モデルを渡す場合、バリデーションはモデル側の `Field()` が担うため、`Body()` 自体には通常引数を付けない。

### Q11. 非ハッピー系のテストを先に書いても、実装済みのエンドポイントは必ず一度 Red になる?
**A.** ならない。バリデーションを Pydantic モデル側の `Field()` や `model_config` に任せている場合、FastAPI がルーター関数を呼ぶ前に自動でバリデーションして 422 を返す。そのため入力値のテストは実装を追加しなくても最初から Green になることがある(実行して確認)。

### Q12. 「必須フィールド欠落」と「`extra="forbid"` の検証」、テストとしての優先度は?
**A.** `extra="forbid"` の方が優先度が高い。必須フィールドを求める挙動は Pydantic のデフォルトで、何もしなくても効くため壊れにくい。一方 `extra="forbid"` は明示的に付けた設定で、リファクタ時に消えても気づきにくいため、テストで縛っておく価値が高い。
