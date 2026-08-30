# POST リクエストから DB 保存・取得までのデータ型ライフサイクル

FastAPI における POST リクエストの受信から、DB 保存、データ取り出し、レスポンス返却までの「データの流れ」と「各段階での型の変化」、および SQLAlchemy における型注釈と実動作の関係について解説します。

---

## 1. 全体の流れとデータ型の変遷（概要）

小数の数値データ（例: `123.45`）を中心とした全体のライフサイクルです。

```text
【1. リクエスト受信 〜 DB 保存】
  HTTP リクエスト（ソケットからのバイト列）
    │
    ▼ ① Uvicorn
  HTTP ヘッダを解析し、ボディのチャンクを ASGI 経由で順次 FastAPI へ転送
    │
    ▼ ② FastAPI / Starlette（Request.body / json.loads）
  チャンクを最後まで蓄積・結合し、辞書にパース（★ここで小数値は float に確定）
    │
    ▼ ③ Pydantic（ItemCreate バリデーション）
  ItemCreate.price：float
    │
    ▼ ④ SQLAlchemy モデル代入（Item(**item_in.model_dump())）
  Item.price：float（インスタンス化時は値がそのまま代入されるだけ）
    │
    ▼ ⑤ DB 送信（SQLAlchemy + psycopg 等の DB ドライバ）
  SQL 文と float パラメータをバイナリ形式にエンコードして送信
    │
    ▼ ⑥ PostgreSQL
  バイナリを受信し、NUMERIC(10, 2) 列にデコードして保存

────────────────────────────────────────────────────────────

【2. DB 取り出し 〜 レスポンス返却】
  PostgreSQL から SELECT（または commit 後の再取得）
    │
    ▼ ⑦ DB ドライバ + SQLAlchemy（Numeric カラム設定）
  DB の数値を Python の Decimal に変換（★ここで Decimal に確定）
    │
    ▼ ⑧ エンドポイント関数
  Item インスタンスを受け取る（item.price は Decimal 型）
    │
    ▼ ⑨ Pydantic レスポンス変換（response_model=ItemPublic）
  ItemPublic.price（float 定義）により float に変換
    │
    ▼ ⑩ JSONResponse
  レスポンス JSON（"price": 123.45）としてクライアントへ返却
```

---

## 2. 各ステップの詳細解説

### ① Uvicorn の処理（バイト列の受信と ASGI への受け渡し）
- ソケット通信で届いた生のバイト列を読み取り、HTTP メソッドやヘッダを切り分けます。
- チャンクデータ（ボディの分割送信）は、Uvicorn がすべて結合するのを待つのではなく、届いたチャンクを順次 ASGI イベントとして FastAPI（Starlette）へストリーム転送します。

### ② FastAPI / Starlette によるボディ蓄積と JSON パース
- FastAPI（Starlette の `Request.body()`）は、Uvicorn から届くボディのチャンクを内部で最後まで蓄積・結合（プール）します。
- すべてのボディデータが揃った段階で `Content-Type: application/json` をもとに `json.loads(body)` を呼び出し、辞書にパースします。
- `json.loads` は小数の文字列リテラルに対して標準の `float()` を適用して辞書を作成するため、**この時点で値が `float` になります**。

### ③ Pydantic によるリクエストバリデーション
- FastAPI は ② で生成された辞書を Pydantic の `ItemCreate` モデルに渡して検証します。
- `price: float = Field(gt=0)` に従い、値が `float` として検証されます。

### ④ SQLAlchemy モデルへの代入
- `crud.create_item` 内で `Item(**item_in.model_dump())` を実行した際、SQLAlchemy は単に辞書の値を属性に代入するだけです。
- この時点では型変換は一切行われず、`item.price` には `float` がそのまま入っています。

### ⑤ & ⑥ DB ドライバによる送信と DB での保存
- SQLAlchemy が SQL（`INSERT INTO items (price, ...) VALUES (%s, ...)`）を組み立てます。
- PostgreSQL 用の DB ドライバ（`psycopg` 等）が、Python の `float` 値と SQL 文を PostgreSQL の通信プロトコルに従ったバイナリデータに変換してネットワーク送信します。
- PostgreSQL は受信したバイナリを自身の `NUMERIC(10, 2)` 型の内部表現にデコードし、四捨五入などの丸め処理を行って保存します。

### ⑦ & ⑧ DB からの取り出しとエンドポイント関数
- `crud.get_item_from_id()` などでデータを読み出す際、または `commit()` 後の属性参照時に DB からデータが取得されます。
- SQLAlchemy の `Numeric(10, 2)`（デフォルトで `asdecimal=True`）および DB ドライバの連携により、数値データが Python の **`Decimal` 型** に変換されます。
- エンドポイント関数が受け取る `Item` モデルインスタンスの `item.price` は **`Decimal`** になっています。

### ⑨ & ⑩ レスポンス変換と返却
- エンドポイントの `response_model=ItemPublic` の定義（`price: float`）により、Pydantic が `Decimal` を `float` に変換してシリアライズします。
- 最終的に JSON 文字列（バイト列）に変換され、HTTP レスポンスとしてクライアントに返されます。

---

## 3. SQLAlchemy の型注釈と実行時動作の違い

SQLAlchemy モデルの定義における `Mapped[Decimal]` と `mapped_column(Numeric(10, 2))` は、それぞれ役割が完全に分離されています。

```python
price: Mapped[Decimal] = mapped_column(Numeric(10, 2))
```

### 役割の違い

1. **左辺（`Mapped[Decimal]`）**
   - **静的型チェッカー（Pylance, mypy など）の型ヒント** に加え、SQLAlchemy 2.0 では **`nullable=False`（NOT NULL 制約）を自動推論する情報源** として機能します（`| None` がないため）。

2. **右辺（`mapped_column(Numeric(10, 2))`）**
   - **実際の DB カラム定義と実行時のデータ変換処理** を担当します。
   - `Numeric` はデフォルトで `asdecimal=True` になっており、DB からデータを取得した際に Python の `Decimal` 型へ変換します。

### 書き方による動作の違い

| 書き方 | 実行時の型（DB取得後） | テーブル制約 | エディタが認識する型 |
| :--- | :--- | :--- | :--- |
| `price: Mapped[Decimal] = mapped_column(Numeric(10, 2))` | `Decimal` | `NOT NULL` | `Decimal`（正常） |
| `price: Mapped[Decimal \| None] = mapped_column(Numeric(10, 2))` | `Decimal` または `None` | `NULL 許容` | `Decimal \| None`（正常） |
| `price = mapped_column(Numeric(10, 2))`（注釈なし） | `Decimal` | `NULL 許容`（★消える） | `Any` |
