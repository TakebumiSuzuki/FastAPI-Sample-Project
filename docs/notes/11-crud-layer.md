# 11. CRUD 層の分離と models ↔ schemas 変換

## 1. 今回学んだこと・理解したポイント

### ① Pydantic の `from_attributes=True` の役割
- `ItemPublic` スキーマに `model_config = ConfigDict(from_attributes=True)` を設定。
- これにより、FastAPI のレスポンス生成時（ルーター側）で、SQLAlchemy の ORM モデル（`Item` インスタンス）の**属性**（`item.id`, `item.name` 等）から Pydantic が自動的にデータを読み取ってレスポンス JSON に変換・バリデーションしてくれる。

### ② CRUD 層（データアクセス層）と Service 層の違い・慣例
- **`crud/` (データアクセス層)**: DB への直接的な読み書き（SQLAlchemy のクエリ操作）に特化。FastAPI 公式でも標準的なパターン。
- **`services/` (ビジネスロジック層)**: 複数 CRUD の組み合わせ、外部 API 連携、メール送信、業務ルールのチェック等を担当する。

---

## 2. SQLAlchemy 2.0 クエリの内部挙動と Q&A（重要）

### Q1. `db_session.execute(stmt)` 実行直後、データはどこでどうなっている？
- **答え**: `db_session.execute(stmt)` が完了した時点で、DB からのレスポンス受信・`Item` オブジェクトのインスタンス化・SQLAlchemy `Session` への登録まで完了している。
- データの場所は **アプリケーション（Python）メモリ上の SQLAlchemy `Session` 内**。

### Q2. なぜ `execute()` の結果はタプルで包まれているの？
- `select(...)` は複数のモデルやカラム（例: `select(Item, User)` や `select(Item, Item.price * 1.1)`）をカンマ区切りで一度に取得できる設計になっている。
- 複数指定時には 2 つ目・3 つ目の要素にそれぞれのオブジェクトや計算結果が入るため、SQLAlchemy は常に **「1行 ＝ タプル `(要素1, 要素2, ...)`」** という共通フォーマットで結果を返す。
- 取得対象が `select(Item)` のみでも `(Item,)` という要素 1 つのタプルで包まれる。

### Q3. `scalar_one_or_none()` や `.scalars()` の内部挙動は？
- **`.scalars()`**: タプルの「包み」を外し、0 番目（デフォルト）の要素（`Item` オブジェクト本体等）を取り出す**イテレータ（`ScalarResult`）**に変換するフィルター。**この時点ではまだリストにはならず、イテレータのまま**返される。
- **`.all()`**: イテレータを最後まで回し、全件を Python のリスト（`list[Item]`）として即座にメモリ上に展開する。そのため、リストとして操作したい場合は `.scalars().all()` とセットで呼び出す。
- **`scalar_one_or_none()`**: 内部的にイテレータの `next()` を呼んで 1 件目を取り出しつつ、0 件なら `None`、2 件以上なら `MultipleResultsFound` エラーを発生させる（直接単一のオブジェクトまたは `None` が取れる）。

### Q4. `scalars()` で 2 列目などの特定カラムだけ取り出したい場合は？
- `scalars()` はデフォルトで `index=0`（1 列目）を取り出す。
- `select(User.id, User.name)` のように複数カラムを指定し、2 列目（`User.name`）だけを取り出したい場合は **`scalars(1)`** または **`scalars(index=1)`** と引数でインデックスを指定する。
  ```python
  names = session.execute(select(User.id, User.name)).scalars(1).all()
  # -> ["Alice", "Bob", "Charlie"] （名前だけのリストが得られる）
  ```

### 補足：関連・類似メソッドの整理

| メソッド | 挙動・用途 |
| :--- | :--- |
| **`.scalars().all()`** | 1列目の要素（オブジェクト等）のみを全件回収して `list` で取得 |
| **`.scalars().first()`** | 最初に見つかった 1 件のみ取得（無ければ `None`）。複数件あってもエラーにならない |
| **`.scalar_one_or_none()`** | 0件または1件の期待値で取得（1件ならオブジェクト直接、0件なら `None`、2件以上は例外） |
| **`.one_or_none()`** | `.scalar_one_or_none()` のタプル版（複数カラム選択時などに使用） |
| **`.fetchmany(size=N)`** | 大量データ時に指定サイズ `N` 件ずつ分割して取得 |

---

---

## 3. CRUD 実装で学んだポイントとハマりどころ

### ① `create_item` におけるデータ受け渡しとレスポンス
- **引数の設計**: 単体の `name: str` ではなく、ルーターでバリデーション済みの Pydantic スキーマ `item_in: ItemCreate` を受けるのが標準的。
- **ORM化**: `Item(**item_in.model_dump())` で一括辞書展開して ORM インスタンス化する。
- **`db_session.refresh(obj)` の要不要**: 
  - `db_session.commit()` 直後に `db_session.refresh(obj)` を呼ぶと DB 側の最新状態（自動発番 `id` など）を明示的に同期できる。
  - ただし、デフォルト設定（`expire_on_commit=True`）では属性アクセス時に遅延ロードで自動取得されるため省略可能。

### ② `update_item` でのハマりどころ（SQLAlchemy の低レイヤーな側面）
- **`db_item.update(...)` は存在しない**:
  - SQLAlchemy のモデルインスタンスは辞書ではないため `.update()` メソッドを持たない。
  - 代わりに Python の属性代入（`db_item.name = "..."`）によって変更をトラッキングする設計になっている。
- **`setattr` による一括更新**:
  - 部分更新（`item_in.model_dump(exclude_unset=True)`）で抽出した辞書を `for k, v in ...` で回し、`setattr(db_item, k, v)` を使って動的に属性更新を行う。
- **`item_id` ではなく `db_item` オブジェクトを渡す理由**:
  - CRUD 関数内で ID 検索を行うと、ルーター側での「404 チェック」や「名前の重複チェック」とクエリが重複して無駄になる。
  - ルーターで取得済みの `db_item: Item` を直接渡す設計にする。

### ③ FastAPI の `response_model` と ORM オブジェクト返却の内部フロー（重要）
- **`return item` で OK な理由**:
  - ルーター関数内で ORM オブジェクト（`Item` インスタンス）を直接返しても、`response_model=ItemPublic` と `ConfigDict(from_attributes=True)` の連携により、FastAPI が ORM オブジェクトの属性を自動的に読み取って `ItemPublic` スキーマへ変換してくれる。
  - そのため、手動で `**item` のように展開（辞書化）する必要はない。
- **データ返却の全体パイプライン**:
  1. **関数からの返却**: ルーターが SQLAlchemy の `Item` オブジェクトを返す。
  2. **Pydantic 変換・バリデーション**: `response_model=ItemPublic` が適用され、属性から値が抽出されて `ItemPublic` インスタンスが生成される（非公開フィールドの除去・バリデーション）。
  3. **JSON 化（シリアライズ）**: `jsonable_encoder` / `model_dump(mode='json')` 等を通じて JSON 互換の構造にシリアライズされる。
  4. **HTTP レスポンス化**: Starlette の `JSONResponse` に包まれ、ステータスコードやヘッダーとともにクライアントへ送信される。
- **404 エラー時の制御**:
  - DB 取得結果が `None` の場合は `return None`（200 OK で空データを返す）ではなく、`raise ItemNotFound(item_id)` で明示的に HTTPException を発生させて 404 ステータスコードを返すのが正解。

### ④ `CommonQueryParams` と `Depends()` の引数省略
- **`CommonQueryParams` の役割**:
  - `skip`（offset）や `limit` などの共通クエリパラメータをまとめた Python クラス（FastAPI 公式チュートリアル由来）。
  - クラスとして定義し、ルーター側で `params: Annotated[CommonQueryParams, Depends()]` と受け取ることでパラメータのバリデーションや初期値設定を一箇所に共通化・再利用できる。
- **`Depends()` の省略**:
  - `Annotated[CommonQueryParams, Depends()]` のように型アノテーション側で指定している場合、`Depends()` の引数は省略可能。

### ⑤ `DELETE /items/{item_id}` と 204 No Content
- **`status_code=204`**: レスポンスボディを伴わない成功レスポンスとして 204 No Content を明示指定。
- **`if item is None:`**: Python 標準のイディオムに従い、データが存在しない場合は 404 (`ItemNotFound`) を raise する。
- **`crud_delete_item(db_session=db_session, db_item=item)`**: ルーターで存在確認済みの ORM オブジェクトを渡し、CRUD 層で `db_session.delete(db_item)` および `db_session.commit()` を呼び出して削除を確定する。

---

## 4. 進捗状況と次回（第12章）への引き継ぎ

### 進捗状況
1. `app/crud/item.py` の全 CRUD 関数実装完了 (`get_item_from_id`, `get_item_by_name`, `get_items`, `create_item`, `update_item`, `delete_item`)。
2. `app/routes/items.py` の全エンドポイント接続・書き換え完了：
   - `GET /items/{item_id}`（1件取得）
   - `GET /items`（一覧取得・`CommonQueryParams` 連携）
   - `POST /items`（新規作成・名前重複チェック・201 Created）
   - `PUT /items/{item_id}`（更新・存在チェック）
   - `DELETE /items/{item_id}`（削除・204 No Content）

第11章「CRUD 層の分離と models ↔ schemas 変換」が完了しました！

### 次回やること（第12章：Alembic でマイグレーション）
- `alembic` の導入と初期化 (`alembic init`)
- `env.py` の設定（`models` を読み込ませる）
- `alembic revision --autogenerate` によるマイグレーション自動生成とレビュー
- `alembic upgrade head` による DB 変更の適用





