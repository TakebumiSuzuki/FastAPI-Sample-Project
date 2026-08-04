# 05. ステータスコードと例外処理

## やったこと

`main.py` に4つを足した。

- POST を `status_code=201` にした
- 自作の例外クラス3つ（`ItemNotFound` / `ItemNameTaken` / `ItemOutOfStock`）
- それを `{"error": {"code", "message", "details"}}` の形に変換するハンドラ
- 422（Pydantic の検証エラー）を同じ形に揃えるハンドラ

---

## 学んだこと

### 成功にも種類がある

`status_code` を書かないと**全メソッド一律で 200** になる。「GET だから 200」ではなく、
土台の Starlette の `Response(status_code: int = 200)` というデフォルト値がそのまま出ているだけ。

```
200 OK       「成功。本文が結果」
201 Created  「成功し、新しいものを作った」   ← POST はこちらが正確
202 Accepted 「受け付けた。処理はまだ」
204 No Content「成功。返す本文は無い」        ← DELETE でよく使う
```

書く場所は**デコレータの引数**であって関数の引数ではない。`response_model` と同じで、
これは「このエンドポイントはこう返る」という仕様であり、OpenAPI にも載る必要があるため。

制限が1つ。`204 / 205 / 304` と 200 未満は本文を持てないので、`response_model` と併用すると
**アプリ起動時にエラー**になる（`fastapi/utils.py` の `is_body_allowed_for_status_code`）。

エラー用の 4xx / 5xx をここに書くことはない。エラーは `raise` 側で番号を指定するから。

### 失敗は「返す」のではなく「投げる」

最初に思いつく `return {"error": "not found"}` は解決にならない。本文に何を書いても
**1行目の `200 OK` は変わらない**。クライアントはまず番号で成否を判断するので、
本文の中の `error` キーを探すコードは書かれない。

```python
raise HTTPException(status_code=404, detail="Item not found")
```

`raise` した瞬間に関数は終わる。**戻り値は存在しない。** レスポンスを作っているのは
関数ではなく、飛んできた例外を受け止めた側。

公式が `return` ではなく `raise` である理由として挙げているのは、
「パス操作関数から呼ばれた**ユーティリティ関数の中から raise しても効く**」こと。

```
return で報告   crud「見つかりません」→ 呼び出し元がチェックし忘れたら素通り
raise で報告    crud が raise → 途中の関数は何も書かなくていい。素通りできない
```

第3部で DB 操作を `crud/` に分けると、「無い」と気づくのは crud の中の関数になる。
そこで `return None` にすると `if item is None:` を毎回書く必要があり、書き忘れれば
`None` が外に出る。`raise` は**書き忘れが起こりえない**。

### `HTTPException` は「値を運ぶ入れ物」でしかない

実体は Starlette 側にあり、`Exception` に属性を3つ足しただけの普通のクラスだった。

```python
class HTTPException(Exception):
    def __init__(self, status_code, detail=None, headers=None):
        if detail is None:
            detail = http.HTTPStatus(status_code).phrase   # 省略時は "Not Found" 等が入る
        self.status_code = status_code
        self.detail = detail
        self.headers = headers
```

属性は `status_code` / `detail` / `headers` の3つだけ。特別な機能は持っていない。

- `raise` できるのは `Exception` を継承しているから
- 404 になるのは、**受け止める側**が「このクラスなら `status_code` と `detail` を読む」と
  知っているから

docstring に用途が明記されている。「クライアント側の誤り（不正な認証、不正なデータなど）
のためのもの。**あなたのコードのサーバーエラーのためではない**」。
名前の `HTTP` は「通信の異常」ではなく「HTTP のステータス番号を伴って返す」という意味。

### エラーの受け止め先は「例外クラス → 関数」の対応表

`@app.exception_handler(X)` は、この対応表に1行足す行為。

```
届いた例外                誰が処理するか
──────────────────────────────────────────
ItemNotFound など        → 自分で書いたハンドラ（登録した場合）
HTTPException            → FastAPI 内蔵の変換（{"detail": ...} を作る）
RequestValidationError   → FastAPI 内蔵の変換（422 のあのリスト）
それ以外（知らない例外）  → 誰も拾わない → 500
```

下2行は `app = FastAPI()` を実行した瞬間に FastAPI 自身が書き込んでいる。
つまり内蔵の変換は魔法ではなく、**自分でやる登録とまったく同じことを先にやってあるだけ**。

判定は `isinstance`（そのクラス**か、そのサブクラスか**）なので、
`HTTPException` を継承した自作クラスは**登録しなくても**内蔵の変換に拾われる。

### 使い回すならサブクラス。ハンドラ登録は「形を変えたいとき」だけ

同じ 404 を複数のエンドポイントで投げるようになると、文言がばらつく。
番号と文言をクラス側に集めれば、投げる側は1行で済む。

```python
class ItemNotFound(HTTPException):
    code = "item_not_found"
    def __init__(self, item_id: int):
        super().__init__(status_code=404, detail=f"Item {item_id} not found")
        self.details = {"item_id": item_id}
```

```
raise ItemNotFound(item_id)     ← 投げる側。番号も文言も知らない
```

`code` はインスタンスごとに変わらないので**クラス変数**、`details` は `item_id` で
中身が変わるので**インスタンス変数**にした。

ハンドラを登録しなくても 409 / 404 は返る（内蔵の変換が拾うため）。
**ハンドラの役割は「返せるようにする」ではなく「返す形を自分で決める」こと。**

### エラーレスポンスの形を揃える

揃える前は、エラーごとにキーが違っていた。

```
404 → {"detail": ..., "item_id": 999999}
409 → {"detail": ..., "name": "りんご"}
422 → {"detail": [{"type": ..., "loc": [...], "msg": ...}]}   ← detail がリスト
```

受け取る側は、エラーごとに見るキーを変える必要がある。`detail` を表示しようとして
型の違うものを掴む事故も起きる。

揃えた形はこれ。

```
{"error": {"code": "item_not_found", "message": "...", "details": {"item_id": 999999}}}
```

- `code` … 機械が分岐に使う文字列。**HTTP の番号より細かく区別できる**
  （400 でも「在庫切れ」か「入力不正」か分かる）。文言で分岐すると文言を直した瞬間に壊れる
- `message` … 人間が読む文
- `details` … エラーごとに違う値の置き場。**形が違う部分をここに閉じ込める**

ハンドラは `HTTPException` に1つ登録すれば、サブクラス全部が拾われる。
`code` / `details` を持たない素の `HTTPException` にも対応するため `getattr` の既定値を使う。

### 422 も同じ形にできる

Pydantic 自身が投げるのは `ValidationError` だが、FastAPI がそれを
**`RequestValidationError` に包み直して**投げている。登録するのはこちら。

`exc.errors()` があの `loc` / `msg` / `type` のリスト。`loc` の先頭は `"body"` / `"query"` と
いう出所なので落とし、残りを `.` でつなぐとフィールド名になる（ネストなら `address.zip`）。

```
POST {"price": "abc"}
→ details: {"name": "Field required", "price": "Input should be a valid number, ..."}
```

ボディでもクエリでも同じ形になることを確認した（`?limit=999` → `{"limit": "..."}`）。

### 自分で書くのはどれか

```
422（入力不正）      FastAPI が自動         → 書くコードは無い
500（バグ）          放置すれば自動で返る    → 書くコードは無い
404 / 409 / 400 など  自分のコードだけが気づく → raise を書く   ★ここだけが仕事
```

### 500 は「返し方を工夫するもの」ではなく「出たら直すもの」

ゼロ除算するエンドポイントを作って実際に確認した。

```
ブラウザに届く    500 Internal Server Error （text/plain。JSON ですらない）
ターミナルに出る  ZeroDivisionError を含むトレースバック（ファイル名・行番号つき）
```

外には何も教えず、中には全部残す。パスや変数の中身が漏れると攻撃の材料になるため。
`try` / `except` を書く必要はない。やることはトレースバックを読んでバグを直すことだけ。

`ServerError` のようなクラスは FastAPI に用意されていない。
`from fastapi import ...` で公開されている例外は `HTTPException` と `WebSocketException` の2つだけ。

### DB のエラーは「故障」と「客が直せるもの」に分かれる

第3部の先取り。SQLAlchemy の例外も FastAPI にとっては知らないクラスなので、
何もしなければゼロ除算と同じ 500 になる。

```
① コード      session.commit() を実行
② DB         「name が重複してる。無理」→ IntegrityError
③ FastAPI    「知らないクラスだ」
④ 客の画面     500 Internal Server Error
```

だが「名前が重複している」は故障ではなく、**名前を変えれば登録できる**という連絡事項。
それが「サーバーが壊れました」に化けている。

```python
try:
    session.commit()
except IntegrityError:
    raise ItemNameTaken(item.name)     # → 409。客は名前を変えて再挑戦できる
```

- DB サーバーが落ちた → 客には直せない → 500 のまま
- 名前の重複（一意制約違反）→ 客が直せる → 409 に翻訳

---

## 詰まった点・気づき

### 「`raise` して返す」と書いて指摘された

`raise HTTPException(...)` を「で返す」と説明したが、関数は何も返していない。投げているだけ。
戻り値は存在せず、レスポンスを作るのは受け止めた側。

この混同は理解の順序に直結する。「関数がレスポンスを作っている」と思っていると、
`@app.exception_handler` が何のためにあるのか分からなくなる。

### 中間クラス `AppError` を作ったが、要らなかった

最初 `AppError(HTTPException)` という共通の親を作り、3つの例外をそこから継承させた。
だが `HTTPException` を直接継承して、ハンドラを `HTTPException` に登録すれば同じことができる。
`isinstance` 判定がサブクラスを拾うので、共通の親を自分で用意する必要がなかった。

### `Exception` から自作 + ハンドラ登録は「必須」ではない

```
HTTPException のサブクラス  → 登録なしでも 404 が返る（内蔵の変換が拾う）
Exception から自作          → 登録しないと 500
```

「カスタム例外を作るならハンドラ登録が要る」と思い込んでいたが、それは下の行だけの話。
`Exception` から作る意味が出るのは、投げる側のファイルを FastAPI に依存させたくないとき
（DB 操作の関数をバッチからも呼びたい等）。それは第3部以降の話。

### `code` という名前が Flask と衝突する

werkzeug の `HTTPException.code` は**HTTP のステータス番号（整数）**。

```python
class PaymentRequired(HTTPException):   # werkzeug
    code = 402
```

このプロジェクトの `code = "item_not_found"` は**文字列の識別子**で、別物。
同じ名前で違うものを指すので、Flask 経験者は誤読する。

### エラー形式の標準は RFC 9457 だけ

IETF が定めた HTTP API のエラー形式は **RFC 9457「Problem Details for HTTP APIs」**
（2023年7月公開、2016年の RFC 7807 を置き換え）。

```json
{"type": "https://example.com/probs/out-of-stock", "title": "Out of stock",
 "status": 400, "detail": "...", "instance": "/items/50"}
```

- `type` … エラー種別の識別子。URL 形式にするが**クライアントは自動アクセスしてはいけない**
  （SHOULD NOT）。開けば人間向けの解説が読めるようにすべき（SHOULD）
- `instance` … その1回の発生を指す識別子。ログ追跡用

採用率の統計は探したが**見つからなかった**。Spring / ASP.NET Core は標準サポートを持つが、
FastAPI 界隈では見かけない。中間に位置する「もっと普及した標準」は存在せず、
選択肢は「RFC 9457」か「独自形式」の2つ。

今回は独自形式（`{"error": {"code", "message", "details"}}`）を選んだ。自社フロントが叩く
API であり、標準に乗る利点（未知のクライアントが解釈できる）が効かないため。
