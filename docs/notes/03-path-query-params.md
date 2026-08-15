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
GET /items/42?limit=5
          └┬┘  └──┬──┘
           │      └ ? の後ろに書かれた値
           └ URL の一部として書かれた値
```

```python
@app.get("/items/{item_id}")   # ← 42 の位置に item_id と名前を付ける
def get_item(
    item_id: Annotated[int, Path(ge=1)],                # 42 が入る
    limit:   Annotated[int, Query(ge=1, le=100)] = 10,  # 5 が入る
): ...
```

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

### `/docs` の 422 は自動注入されている

`openapi/utils.py:517` に条件があり、**そのルートにパラメータが1つでもあるか
ボディがある場合だけ** `422` のレスポンス定義が追加される。
引数を取らない `/` には 422 が付かない。`/docs` で見比べると確認できる。

## 詰まった点・気づき

### Swagger UI は `exclusiveMinimum` / `exclusiveMaximum` を表示しない

`gt=1, lt=100` と書いたとき `/docs` の `limit` 欄に制約が出なかったが、
`app.openapi()` を直接叩くとスキーマには
`exclusiveMinimum: 1, exclusiveMaximum: 100` が入っていた。
FastAPI 側は正しく、**Swagger UI が描いていないだけ**。
（なぜ省くのかは未確認）`ge`/`le` なら `minimum`/`maximum` として表示される。


### `q` の型が `/docs` で `string | (string | null)` と表示される

`str | None` から `anyOf: [{"type":"string"}, {"type":"null"}]` が生成されており、
スキーマ自体はおかしくない。外側の `string |` は Swagger UI の表示の癖。

## Q&A

### Q. `Path(ge=1)` や `Query(ge=1, le=100)` は FastAPI 側で定義されていて、アプリ起動時に評価され、内部的に Pydantic の `Field` に変換される、と考えていい？

**① FastAPI 側で定義されているか → はい。**
`Query` も `Path` も FastAPI が用意した関数。呼ぶと、制約（`ge=1`, `le=100`）を抱えたオブジェクトが返る。

**② 起動時に評価されるか → はい。**
`@app.get(...)` が実行される瞬間、つまり Python がファイルを読み込んだ時点。

**③ Pydantic の `Field` に変換されるか → 変換されない。継承関係にあるから。**

`Field()` が返すのは Pydantic の `FieldInfo` というクラスのオブジェクト。
一方 `Query()` が返す `params.Query` は、その `FieldInfo` を**継承したサブクラス**。

```
        FieldInfo （Pydantic）      ← Field() が返すのはこれ
             ▲
             │ 継承
        params.Query （FastAPI）    ← Query() が返すのはこれ
```

継承しているということは、`params.Query` は `FieldInfo` の一種だということ。
Pydantic から見れば `Query()` が返したものは最初から `FieldInfo` として扱えるので、
変換する段階が存在しない。
