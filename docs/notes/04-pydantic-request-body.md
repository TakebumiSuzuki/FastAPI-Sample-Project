# 04. Pydantic v2：リクエストボディと `response_model`

※ 4-1（リクエストボディ）と 4-2（`response_model`）に、
4-3（`Field` / バリデータ / `model_config`）と 4-4（入力用・出力用・DB 用の描き分け）を追記済み。

※ このノート作成後、`schema.py` は `app/schemas.py` に移動・改名した
（→ `docs/notes/08-settings.md` 以降の構成）。以下の本文は当時の記録のまま残している。

## やったこと

`schema.py` を新設して Pydantic のクラスを置き、`main.py` に POST エンドポイントを追加した。

- 入力用：`name` / `price` / `description` を持つクラス
- 出力用：`ItemPublic`（`id` / `name` / `price` / `description`）
- `@app.post("/items", response_model=ItemPublic)` で返す形を宣言

わざと `secret_memo`（社内メモのつもり）を関数から返して、それが外に出ないことを確認した。

## 学んだこと

### パス／クエリ／ボディの振り分けも型注釈で決まる

```
item_id: int          → パス or クエリから読む
item: ItemCreate      → body から読む（BaseModel を継承したクラスだから）
```

03 章では「引数名がパスの `{}` にあるか」で振り分けられていた。
ボディの場合はそれに加えて「型注釈が `BaseModel` のサブクラスか」で決まる。
宣言は要らず、型を書くだけ。

### 検証には JSON パースという 0 段目がある

03 章で見た3段階の手前に、もう一段あった。

```
[0] 本文を JSON としてパースできるか？ → NG: type "json_invalid"
[1] 値が届いているか？                 → NG: type "missing"
[2] 型に変換できるか？                 → NG: type "float_parsing"
[3] 制約を満たすか？                   → NG: type "greater_than" など
```

`[0]` で落ちると `loc` が `["body", 34]` のように**数字**になる。
これは「本文の 34 文字目でパースに失敗した」という意味で、フィールド名すら
特定できていない状態。`ctx.error` が `"Expecting value"` なら
「値が来るべき場所に値がない」。

JSON で値になれるのは 文字列（必ずダブルクォート）／数値／`true`／`false`／
`null`／配列／オブジェクト だけ。裸の `abc` は違反なのでここで落ちる。

### `loc` の構造は path / query / body で共通

```
03章  ["query", "limit"]     ["path", "item_id"]
04章  ["body",  "price"]     ["body", "name"]
        ↑           ↑
   どこから来たか  どのフィールドか
```

検証の仕組みは1つしかなく、変わるのは先頭のラベルだけ。

### エラーは1件目で打ち切らず、まとめて返る

`name` を省略しつつ `price` に文字列を入れたら、`missing` と `float_parsing` が
**同時に** `detail` に入って返ってきた。

03 章で読んだ `routing.py` の流れの通り、検証結果は `errors` という**リストに積む**形で、
1件目で `raise` しない。積み終えてから空でなければ `RequestValidationError` にする。
フォームで「1項目ずつ直しては送り直す」必要がないのはこのため。

### `input` の中身は `type` によって指すものが違う

- `float_parsing` の `input` … `"abc"`（問題のあった**値そのもの**）
- `missing` の `input` … `{"price": "abc", ...}`（送られてきた**ボディ全体**）

`missing` は「値が無い」エラーなので指し示す値が存在しない。
代わりに「この中に見つからなかった」という**親のオブジェクト**を報告している。

### `response_model` は「返していい形」のフィルタ

```
   関数が return              serialize_response()          外に出る形
   {id, name, price,   ──▶   ItemPublic の field.validate  ──▶  {id, name, price,
    secret_memo}              ├ ItemPublic に有る → 採用          description}
                              └ 無い(secret_memo) → 捨てる
```

重要なのは、`secret_memo` は「返さないように書いた」から消えたのではなく、
**「返していいリストに載っていない」から捨てられた**こと。
関数側が何を返そうと関係ない。DB のレコードを丸ごと返しても、
`response_model` に無い列は外に出ない。これが漏洩事故を防ぐ仕組みになる。

実ソース上は `routing.py:317` あたりの `serialize_response()`。
03 章で見たリクエスト側の検証と**同じ `field.validate()` が方向を変えて使われている**だけで、
`loc` が `("response",)` になっているのが印。ここで失敗すると 422 ではなく
500（`ResponseValidationError`）になる。

### 返す形の宣言方法は2つあり、`response_model=` が優先される

```
① 戻り値注釈    def create_item(...) -> ItemPublic:      ← 公式の推奨
② 引数で指定    @app.post("/items", response_model=ItemPublic)
```

`routing.py:1081` に `if isinstance(response_model, DefaultPlaceholder):` という分岐があり、
**②が明示されているときは①を一切見ない**。
`response_model=Pub` と `-> dict` を両方書いた小さなアプリを `TestClient` で試したところ、
レスポンスも OpenAPI スキーマも `Pub` になった。

①が推奨されるのは、FastAPI だけでなく**型チェッカー（Pylance）にも同じ情報が伝わる**から。
②は FastAPI にしか伝わらない。
今回②を選んだのは、関数が `ItemPublic` オブジェクトではなく**辞書を返しているため**。
①で書くと「`ItemPublic` を返すと宣言して `dict` を返している」ことになり、
`typeCheckingMode: "standard"` の Pylance が警告するはず（未検証）。
第3部で DB のオブジェクトを返すようになったら①に統一できる。

## `/docs`（Swagger UI）の読み方

1つのエンドポイントの画面は3ブロックに分かれている。

```
① Parameters       ← 【送る】URL に乗る値の仕様
② Request body     ← 【送る】本文の仕様。ここを編集して Execute
─────── Execute を押すと以下が現れる ───────
③ Curl / Request URL  ← 今の操作を curl に翻訳したもの
④ Server response  ← 【実際に返ってきたもの】
⑤ Responses        ← 【返りうる形の"仕様"】実行結果ではない
```

- **④ Server response**（単数）＝ たった今返ってきた**実物**
- **⑤ Responses**（複数）＝ 返る**可能性のある形の一覧**。実行前から表示されている

⑤ の `{"detail":[{"loc":["string",0],...}]}` はエラーが起きた表示ではなく、
「422 のときはこの形で返る」という**説明書**。`"string"` や `0` は型のプレースホルダ。

`Example Value` / `Schema` のトグルは、同じ情報を「例で見るか」「定義で見るか」の違い。

### `{"additionalProp1": {}}` の意味

「中身の決まっていない辞書」を表す Swagger UI の表現（additional property の略）。
関数の戻り値注釈が `-> dict` だと、FastAPI に「辞書を返す」としか伝わらないのでこうなる。
`response_model=ItemPublic` を付けると
`"schema": {"$ref": "#/components/schemas/ItemPublic"}` に変わる。

## 詰まった点・気づき

### JSON を壊して、狙っていたエラーが出せなかった

`price` に文字列を入れる実験のつもりで `"price": abc` とクォート無しで書き、
`float_parsing` ではなく `json_invalid` が返ってきた。
`name` を省く実験でも、値だけ消してカンマを残してしまい同じことが起きた。
**検証の 0 段目で落ちていて、Pydantic まで届いていなかった。**
`loc` の2番目が文字列（フィールド名）か数字（文字位置）かで見分けられる。

### `/docs` の欄を見間違えた

`response_model` を付けたのに 200 欄が `{"additionalProp1": {}}` のままに見えたが、
見ていたのは `GET /items/{item_id}` の欄だった（そちらは `-> dict` のまま）。
`app.openapi()` を直接叩けば、どちらが何になっているか確実に分かる。

```bash
uv run python -c "from main import app; import json; print(json.dumps(app.openapi(), indent=2))"
```

---

# 4-3. `Field` / バリデータ / `model_config`

## やったこと

`ItemCreate` に3種類の検証を足した。不正な入力が入り口で弾かれる状態にした。

## 学んだこと

### `Field` は `Path` / `Query` の親

03 章で `Path(ge=1)` と書けたのに `{"price": -100}` が 200 で通ってしまう、という
ところから始まった。「`Body(gt=0)` と書けばいいのでは」と考えたが書けない。

```
item_id: Annotated[int, Path(ge=1)]     ← 値が1個。条件も1個で済む
item:    Annotated[ItemCreate, Body()]  ← Body が指すのは箱全体。
                                           箱の中の price には手が届かない
```

制約は箱の中の各フィールドに付けるしかない。それが `Field`。

継承関係を実ソースで確認したら、そもそも同じものだった。

```
              FieldInfo          ← pydantic。Field() が返すのはこれ
                  │
        ┌─────────┴─────────┐
      Param                Body    ← fastapi が継承。in_ = どこから拾うか
   ┌────┴────┐
 Path       Query
```

`fastapi/params.py:26,137,221`。`Path(ge=1).metadata` と
`pydantic.Field(ge=1).metadata` はどちらも `[Ge(ge=1)]` で同一だった。

**`gt` / `ge` / `min_length` の引数名が両方で同じなのは偶然ではなく、同じ入れ物だから。**
道具が増えたのではなく、**制約を書く場所が関数の引数からクラスの中に移った**だけ。

### 書く場所の決まり方＝値が URL に乗るか本文に乗るか

```
POST /items/5?limit=10   ← URL。平らな値しか置けない → 関数の引数（Path/Query）
{"name": "りんご", ...}   ← 本文。入れ子も配列も置ける → クラスの中（Field）
```

URL は1本の文字列なので構造を持てない。だから関数の引数の並びとそのまま対応する。
本文は JSON なので引数の並びでは表せず、クラスで形を書く必要がある。

例外はあり、クラスをクエリに使う（`Annotated[F, Query()]`）ことも、
素の値を本文に使う（`Body(embed=True)`）こともできる。両方 200 を確認した。

### `Field` はデフォルト値の位置を占領する

```python
limit: Annotated[int, Query(ge=1)] = 10   # 03章。デフォルトは外
price: float = Field(default=10.0, gt=0)  # Field はデフォルトの位置に座るので中に書く
```

`default=` は**キーワードで書く**。位置引数 `Field(None, gt=0)` でも実行時は同じだが、
Pylance / pyright は `default` がキーワードのときだけ「省略可能」と推論する
（Pydantic 公式ドキュメントに明記）。このプロジェクトは `typeCheckingMode: "standard"` なので
キーワードで統一する。

### `Field` は自分1つしか見えない → `model_validator`

セール価格を足したら、`{"price": 100, "sale_price": 200}` が 200 で通った。
`sale_price: 200` **単体**を見れば `gt=0` を満たしているので `Field` は文句を言えない。
おかしさは2つのフィールドを**見比べて初めて**分かる。

```python
@model_validator(mode="after")
def check_sale_price(self):
    if self.sale_price is not None and self.sale_price >= self.price:
        raise ValueError("sale_price must be lower than price")
    return self
```

- `self` を受け取れるのがすべて。`Field` にはこれに当たるものがなかった
- `raise ValueError` が「弾く」、`return self` が「通す」
- `raise` する例外は **Python 標準の `ValueError`**（`ValueError.__module__` は `builtins`）。
  特別なのは例外側ではなく、それを捕まえて検証エラーに変換する Pydantic 側。
  公式によると使えるのは `ValueError` / `AssertionError` / `PydanticCustomError` の3つで、
  `ValueError` が最も一般的（`AssertionError` は `-O` 実行で assert がスキップされる）

エラーの `loc` は `["body"]` 止まりになる。特定のフィールドではなく**箱全体**に対する
エラーだから。

### `mode="after"` を使う理由と、`before` の使いどころ

```
[1] model_validator(mode="before")   ← まだ生の dict。price は "100"（文字列）かも
[2] field_validator(mode="before")
[3] 型変換 + Field の制約
    ★ ここでインスタンスが誕生する
[4] field_validator(mode="after")
[5] model_validator(mode="after")    ← self を受け取る
```

各段に print を仕込んで実行し、この順序を確認した。`gt=0` 違反のときは `[3]` で止まり
`[4]` `[5]` は呼ばれない。

`after` なら「型が合っていて制約も通った値」を前提に書けるので、比較に余計な防御が要らない。
公式のフィールド間検証の例（パスワード一致・幅と高さの一致）も全部 `after`。

**インスタンスは `[5]` の前にできている。** `after` が `self` を受け取れる時点で存在している。
ただし `after` で `raise` すると、できていたインスタンスは呼び出し元に渡らず捨てられる。

`before` は「弾く」より「**検証に通る形に直してから流す**」用途。
旧クライアントが `price` を `"1,980"` とカンマ区切りで送ってくる場合など、
`float` 変換の前にカンマを抜く。引数が `self` でなく生の dict なのは、
インスタンスがまだ存在しない時点だから。

### `model_config` は「知らないフィールドが来たとき」の方針

`sale_price` を `salePrice` と綴り間違えて送っても 200 で通り、**黙って捨てられていた**。
クライアントは設定できたと思い込み、誰も気づかない。
`Field` でも validator でも防げない。どちらも「**存在するフィールド**」を検証する道具で、
「知らないフィールドが**来たこと**」はクラス全体の受け入れ方針の話だから。

```python
model_config = ConfigDict(extra="forbid")
```

`extra` は3択。`ignore`（既定・黙って捨てる）/ `forbid`（422）/ `allow`（捨てずに
`__pydantic_extra__` に保持）。**エラーにするかしないかの軸で独立しているのは `forbid` だけ**で、
「`allow` の逆」と言うと `ignore` との差が消える。

`forbid` にすると `{"type": "extra_forbidden", "loc": ["body", "salePrice"]}` が返り、
綴り間違えた名前がそのまま `loc` に出る。クライアントは何を直せばいいか分かる。

選択は用途次第。公式は3択を並べるだけで `forbid` を推奨とは書いていない。判断軸は
「送り手のミスを教えたいか、送り手の自由を許したいか」。自社フロントが叩くなら `forbid`、
不特定多数が叩く公開 API なら `ignore` が無難。

## 詰まった点・気づき

### `BaseModel` はメタクラスではない

「`BaseModel` はメタクラスだから挙動が違う」と思っていたが違った。

```
ModelMetaclass  ← これがメタクラス（クラスを作る側）
      │ が作る
BaseModel       ← 普通のクラス
```

`type(BaseModel)` は `ModelMetaclass`、`isinstance(BaseModel, type)` は `True`。
挙動が普通と違って見えるのは `ModelMetaclass` の仕業で、クラス定義を読み込む瞬間に
`name: str = Field(...)` を拾い上げて検証器を組み立ててクラスに埋め込んでいる。

### `model_config` はメタクラスの中には無い

`ConfigDict` の実体は `TypedDict`（`pydantic/config.py:36`）。実行時はただの `dict`。
`TypedDict` にしてある利点は、`extras` のようなキーの綴り間違いをエディタが指摘できること。

設定が置かれるのは**書いたクラス自身**。

```
A.model_config = {'extra': 'forbid'}   ← A に書いたものは A に付く
B.model_config = {}                     ← B は影響を受けない
ModelMetaclass に model_config はあるか: False
```

**だから `ItemCreate` に書いても `ItemPublic` には効かない。**
メタクラスの役割は設定を保持することではなく、クラス定義時にそれを読んで検証器を組むこと。

### `ItemPublic` に業務ルールの validator は書かない

検証の役割が入力側と違う。

```
ItemCreate が疑う相手 … 外部のクライアント → 弾いたら 422「あなたの入力が悪い」
ItemPublic が疑う相手 … 自分たち（DB とコード） → 失敗したら 500「サーバーのバグ」
```

`sale_price >= price` のデータが DB から出てくるなら、それは入り口をすり抜けたか
DB を直接いじったかで、つまりバグ。出口で握りつぶさず 500 で表面化させ、入り口を直すのが筋。

ただし「DB の値は正しい」は自動では成り立たない。**書き込みは必ず検証済みスキーマを通す**
という規律を守って初めて成り立つ前提。

---

# 4-4. 入力用・出力用・DB 用の描き分け

## やったこと

`schema.py` を `ItemBase` / `ItemCreate` / `ItemUpdate` / `ItemPublic` の4つに分けた。

## 学んだこと

### 1つのクラスでは両立できないことがある

更新エンドポイントを `ItemCreate` を使い回して作り、`{"name": "みかん"}` を投げたら
`{"type": "missing", "loc": ["body", "price"]}` で 422。値段を変えないのに `price` を送れと言われる。

`ItemCreate` の `price` が必須なのは「新規登録では必須」という理由で、更新には当てはまらない。
かといって任意にすれば、今度は**値段のない商品が新規登録できてしまう**。

### 分ける基準は「誰が書き込む値か・誰が読む値か」

```
                    name  price  id   secret_memo
Create（登録の入力）  必須   必須   ×        ○
Update（更新の入力）  任意   任意   ×        ○
Public（出力）        ○     ○     ○        ×
DB（テーブル）        ○     ○     ○        ○
```

`id` が分かりやすい。**登録時にはまだ存在せず**（DB が採番する）、**出力には必要**。
`ItemCreate` に `id` を書くと「クライアントが id を指定できる」間違った API になる。

### 共通部分は継承でまとめる。ただし Update は継承できない

`model_config` も `model_validator` も子クラスに継承される（実行して確認）。
だから制約は `ItemBase` に1か所書けば `ItemCreate` / `ItemPublic` に効く。

`ItemUpdate` だけは別に書く。「全フィールドが任意」なので、必須で定義された親を継承しても
必須のまま。**「必須かどうか」と「制約」は別物**なので、任意にしても `gt=0` は効く
（03章の「必須／任意を決めるのはデフォルト値の有無」がそのまま当てはまる）。

継承しない代償として、`check_sale_price` も `ItemUpdate` に別途書く必要がある。
書き忘れると更新経由で価格の逆転を作れてしまう（実際に通ってしまうのを確認した）。

### `float | None` に付けた `gt=0` は None には効かない

```json
"anyOf": [
  {"type": "number", "exclusiveMinimum": 0},   ← gt=0 はこの枝にだけ付く
  {"type": "null"}                              ← 制約なし
]
```

2つの枝の選択で、null は別の枝を通るので制約に触れない。
03章で見た `str | None` → `anyOf[string, null]` と同じ構造。

## 詰まった点・気づき

### 明示的な `null` と「省略」は属性では区別できない

PATCH では `{"sale_price": null}`（セール解除したい）と `{}`（触るな）を区別する必要がある。
だが両方とも `.sale_price` は `None` になる。

区別は Pydantic が別に記録している `model_fields_set`（**実際に送られてきたフィールド名の集合**）で行う。

```
{"name":"みかん","sale_price":null} → .sale_price=None  fields_set={'name','sale_price'}
{"name":"みかん"}                    → .sale_price=None  fields_set={'name'}
                                          ↑同じ            ↑ここで区別できる
```

実用上は `model_dump(exclude_unset=True)` を使う。送られてこなかったフィールドが dict から落ちる。

```python
data = item.model_dump(exclude_unset=True)
for key, value in data.items():
    setattr(db_item, key, value)      # 送られた項目だけ上書き
```

**`exclude_unset` を付け忘れると、触っていないセール価格が `None` で消える。** 一番の落とし穴。

### 「空のリクエストを弾く」を `is None` で書いて失敗した

最初こう書いた。

```python
if self.name is None and self.price is None and self.sale_price is None:
    raise ValueError("All fields are None")
```

これだと `{"sale_price": null}`（**中身のあるセール解除の要求**）まで弾かれる。
まさに上で学んだ「省略」と「明示的な null」の区別が消えていた。

```python
if not self.model_fields_set:
    raise ValueError("no fields to update")
```

に変えると意図通りになった。フィールドが増えても条件式を書き足さなくて済む利点もある。

### `ItemUpdate` の validator では `is not None` を先に置く

```python
if self.price is not None and self.sale_price is not None and self.sale_price >= self.price:
```

`{"sale_price": 200}` だけ送られたとき、これがないと `None >= 200` で `TypeError` になる。
なおこの形は `price` を知らないので判定不能で、通ってしまう。
**完全な検証には DB の現在値と突き合わせる必要があり、それは crud 層の仕事**（第3部）。

### Zod と比べて Pydantic が冗長なのは事実

Zod には派生スキーマを作る演算子がある（公式ドキュメントで確認）。

```typescript
const ItemUpdate = ItemBase.partial();               // 全部を任意に
const ItemPublic = ItemBase.extend({ id: z.number() });
ItemBase.pick({...}) / ItemBase.omit({...})
```

`ItemUpdate` で4フィールド分の `default=None` を手書きしたところが `.partial()` の一語で済む。
Pydantic に相当する公式メソッドはない（`create_model` で動的生成はできるが程遠い）。

差の理由は作り方の違い。

```
Zod       スキーマが「値」  → 加工する関数が自然に書ける。TS 型は z.infer で導出
Pydantic  スキーマが「クラス」→ 加工手段が継承しかない
```

ただし Pydantic 側の見返りもある。型注釈がそのまま Python の型なので Pylance が
追加の仕掛けなしに理解する（Zod は `z.infer<typeof X>` が要る）。validator をメソッドとして
クラス内に書けて継承もされる。FastAPI が同じクラスから OpenAPI を生成する。
**「派生の作りやすさ」は Zod、「型システムとの一体感・振る舞いの持たせやすさ」は Pydantic** という
トレードオフ。
