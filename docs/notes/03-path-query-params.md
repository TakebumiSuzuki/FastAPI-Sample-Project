# 03. パスパラメータ・クエリパラメータと型による検証

## やったこと

`main.py` の `get_item` に、パスパラメータ1つとクエリパラメータ2つを持たせ、
それぞれに `Path()` / `Query()` で制約を付けた。

```python
def get_item(
    item_id: Annotated[int, Path(ge=1)],
    limit: Annotated[int, Query(ge=1, le=100)] = 10,
    q: Annotated[str | None, Query(min_length=3, max_length=50)] = None,
) -> dict: ...
```

そのうえで、わざと不正な値を投げて 422 のレスポンスボディを読み比べた。

## 学んだこと

### パス／クエリの振り分けは「名前がパスの `{}` にあるか」だけ

```
@app.get("/items/{item_id}")
def get_item(item_id, q):
                 ↑     ↑
        {} にある   {} にない
        → パス      → クエリ
```

宣言や設定は要らない。引数名とパス文字列の照合で自動的に決まる。

### 型注釈は「変換ルール」と「検証ルール」を兼ねている

URL は常に文字列なので、サーバーに届いた時点では `"42"`。それが JSON で `42`
（クォート無し）で返ってきたのは、Pydantic の `field.validate()` が変換に成功した姿。
つまり**変換と検証は別処理ではなく、同じ呼び出しの表と裏**。成功すれば変換済みの値、
失敗すればエラーになる。

### 必須／任意を決めるのは型注釈ではなくデフォルト値の有無

```
q: str | None = None
   └───┬───┘   └─┬─┘
    型注釈     デフォルト値
      │          │
      ▼          ▼
  anyOf[string,null]  required: false
```

- 「必須かどうか」＝ デフォルト値があるか
- 「None を許すか」＝ 型注釈が `| None` を含むか

この2つは別の話。`= 10` を消すだけで `limit` が必須になり、
`type: "missing"` のエラーが出たことで両方向から確認できた。

### 422 が返るまでの流れ（実ソースで追った）

```
リクエスト
  │
  ├ solve_dependencies() が引数を1つずつ組み立てる
  │   → Pydantic の field.validate() で検証
  │   → 失敗を errors リストに積む
  │
  ├ errors が空でない → RequestValidationError を raise  (routing.py:752)
  │                     ★ エンドポイント関数はまだ呼ばれていない
  │
  ├ 起動時に登録済みのハンドラが捕まえる              (applications.py:1005)
  │
  └ JSONResponse(status_code=422, ...)                (exception_handlers.py:24)
```

**関数の手前で検証が完結している**のが要点。だから関数の中に
`if not isinstance(...)` のようなチェックを書かなくていい。

### 422 は FastAPI 側の決め打ち。入力なら 422、出力なら 500

Pydantic は HTTP を知らない汎用のバリデーションライブラリなので、
「どのステータスコードにするか」は FastAPI 側の判断。
`exception_handlers.py:24` に `status_code=422` が直書きされている。

ただし **「Pydantic のエラーは全部 422」ではない**。

| どこで失敗したか | 例外クラス | 結果 |
| --- | --- | --- |
| 入力（リクエスト） | `RequestValidationError` | 422（クライアントが悪い） |
| 出力（レスポンス） | `ResponseValidationError` | 500（サーバーが悪い） |

422 のハンドラが登録されているのは `RequestValidationError` と
`WebSocketRequestValidationError` の2つだけ（`applications.py:1005,1010`）。
`ResponseValidationError` にはハンドラが無いので未処理例外として 500 になる。
`response_model=int` のエンドポイントで文字列を返して `TestClient` で叩き、500 を確認した。

### 検証エラーは3段階あり、`type` で見分けられる

```
値が届いているか？  ── NO ──▶ type: "missing"            input: null
   │ YES
型に変換できるか？  ── NO ──▶ type: "int_parsing"        input: "abc"
   │ YES
制約を満たすか？    ── NO ──▶ type: "greater_than_equal" ctx: {"ge":1}
   │ YES
 関数が呼ばれる
```

`input` を見れば、値そのものが来ていない（`null`）のか、
来ているが中身が悪い（`"abc"`）のかが区別できる。

### エラー辞書の読み方

- `loc` … どこで失敗したか。`["path","item_id"]` / `["query","limit"]`
- `type` … Pydantic のエラー種別コード
- `msg` … 人間向けの文
- `input` … 実際に届いた値
- `ctx` … 破られた制約の中身（`{"ge": 1}` など）

`limit=abc` のとき `type` は `item_id=abc` と同じ `int_parsing` のままで、
`loc` の先頭だけ `path` → `query` に変わった。
**検証の仕組みは1つしかなく、違うのは「どこから値を拾ったか」というラベルだけ**。

### `ge`/`gt`/`le`/`lt` と OpenAPI キーの対応

| 書き方 | 意味 | 生成される OpenAPI キー |
| --- | --- | --- |
| `ge=1` | 1 以上（含む） | `minimum: 1` |
| `gt=1` | 1 より大きい（含まない） | `exclusiveMinimum: 1` |
| `le=100` | 100 以下 | `maximum: 100` |
| `lt=100` | 100 未満 | `exclusiveMaximum: 100` |

`g`/`l` が大小の向き、`e` が「等しいを含む」の e。

### `Query(default=10)` ではなく `Annotated[...] = 10` を使う理由

FastAPI を通さずに関数を直接呼んだときの挙動が違う。

```
def old(limit: int = Query(default=10, ge=1))   →  old()  returns Query(10)
def new(limit: Annotated[int, Query(ge=1)] = 10) →  new()  returns 10
```

古い書き方では Python から見たデフォルト値が `Query` オブジェクトそのものなので、
リクエスト経由では動くが直接呼ぶと壊れる。第4部でテストを書くときに効いてくる。
`Annotated` は「型注釈にメタ情報を添える」形なので、デフォルト値は素の `10` のまま。

### `/docs` の 422 は自動注入されている

`openapi/utils.py:517` に条件があり、**そのルートにパラメータが1つでもあるか
ボディがある場合だけ** `422` のレスポンス定義が追加される。
引数を取らない `/` には 422 が付かない。`/docs` で見比べると確認できる。

## 詰まった点・気づき

### デフォルト値ありの引数の後ろにデフォルト値なしの引数は置けない

`limit` から `= 10` を消したらサーバーが起動しなくなった。

```
def f(a, b=1, c): pass
→ SyntaxError: parameter without a default follows parameter with a default
```

**これは Python の文法の話で FastAPI とは無関係。**
URL 上の `?q=...&limit=...` の順番とも一切関係ない。
デフォルト値を外すなら、その引数をデフォルト持ちの引数より前に移す必要がある。

### Swagger UI は `exclusiveMinimum` / `exclusiveMaximum` を表示しない

`gt=1, lt=100` と書いたとき `/docs` の `limit` 欄に制約が出なかったが、
`app.openapi()` を直接叩くとスキーマには
`exclusiveMinimum: 1, exclusiveMaximum: 100` が入っていた。
FastAPI 側は正しく、**Swagger UI が描いていないだけ**。
（なぜ省くのかは未確認）`ge`/`le` なら `minimum`/`maximum` として表示される。

### `ge` と `gt` を書き間違えた

「1以上100以下」のつもりで `gt=1, lt=100` と書き、実際には 2以上99以下になっていた。
エラーの `type` が `greater_than`（`ge` なら `greater_than_equal`）、
`ctx` が `{"gt": 1}` になっているので、レスポンスを読めば気づける。

### `q` の型が `/docs` で `string | (string | null)` と表示される

`str | None` から `anyOf: [{"type":"string"}, {"type":"null"}]` が生成されており、
スキーマ自体はおかしくない。外側の `string |` は Swagger UI の表示の癖。
