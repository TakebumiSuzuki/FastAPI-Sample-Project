# 05. ステータスコードと例外処理（エラーハンドリング）

## 1. この章でやったこと

FastAPI における「適切なステータスコードの返し方」と「エラー（例外）の扱い方・レスポンスの統一」を実装しました。

- **成功時ステータスコードの明示**: POST (`201 Created`) や DELETE (`204 No Content`) など、操作に応じた適切なコードを設定。
- **自作例外クラスの定義**: `ItemNotFound` (404), `ItemNameTaken` (409), `ItemOutOfStock` (400) を作成。
- **エラーレスポンスの形式統一**: 自作例外や FastAPI の `HTTPException` を `{"error": {"code", "message", "details"}}` の統一フォーマットで返すハンドラを実装。
- **バリデーションエラー (422) の統一**: Pydantic / FastAPI が自動で出す 422 エラーも同じ統一フォーマットに変換。

---

## 2. ステータスコードの基本

### 成功にも種類がある
FastAPI では、特に指定しない場合すべてのエンドポイントが **`200 OK`** で応答します。
しかし、HTTP では「何が起きたか」に応じてステータスコードを使い分けるのが原則です。

| コード | 名称 | 意味 | 主な用途 |
| :--- | :--- | :--- | :--- |
| **`200`** | OK | 成功。レスポンス本文に結果を含む | GET, PUT など |
| **`201`** | Created | 成功。新しいリソースを作成した | POST |
| **`202`** | Accepted | リクエストを受理したが、処理は未完了（非同期処理など） | 時間のかかるバッチ受付 |
| **`204`** | No Content | 成功。返すレスポンス本文（Body）は無い | DELETE |

### 設定する場所
成功時のステータスコードは、関数の引数ではなく **デコレータ（ルーター）の引数** に指定します。

```python
@router.post("", response_model=ItemPublic, status_code=201)
def create_item(...):
    ...

@router.delete("/{item_id}", status_code=204)
def delete_item(...):
    ...
```

> **注意（204 No Content の制限）**
> `204` や `304` などの「本文を持ってはいけないコード」に対して `response_model` を同時に指定すると、FastAPI 起動時（スキーマ生成・バリデーション時）にエラーになります。`204` を使うエンドポイントには `response_model` を付けず、関数の戻り値も `None`（空）にします。

---

## 3. エラー（失敗）の扱い方

### なぜ `return` ではなく `raise` なのか？
エラーが起きたとき、`return {"error": "not found"}` のように辞書を返してはいけません。

1. **ステータスコードが `200 OK` のままになってしまう**
   クライアント（フロントエンドや外部アプリ）はまずステータスコードを見て成否を判定します。200 が返ってくると「成功した」と誤認してしまいます。
2. **呼び出し階層が深くなっても確実に処理できる**
   関数が別の関数（CRUD や DB 操作ロジック）を呼んでいる場合、`return None` だと呼び出し元すべてで `if item is None:` とチェックし直す必要があります（チェック漏れがあるとバグの原因に）。
   `raise`（例外を投げる）を使えば、途中の関数をすり抜けて FastAPI のエラーハンドラまで一直線にジャンプするため、処理漏れが起きません。

```python
# ✕ 間違い: 200 OK でエラーメッセージが返ってしまう
return {"error": "Item not found"}

# ○ 正しい: 404 Not Found として例外を投げる
raise HTTPException(status_code=404, detail="Item not found")
```

---

## 4. `HTTPException` と自作例外クラス

### `HTTPException` の正体
FastAPI（Starlette）の `HTTPException` は、特別な魔法ではなく「HTTP ステータス番号と詳細メッセージを運ぶための入れ物（Python の `Exception` を継承したクラス）」です。

```python
# イメージ
class HTTPException(Exception):
    def __init__(self, status_code: int, detail: Any = None, headers: dict = None):
        self.status_code = status_code
        self.detail = detail
        self.headers = headers
```

### 自作例外クラスを作って再利用する
エンドポイントごとに毎回 `raise HTTPException(status_code=404, detail=f"Item {item_id} not found")` と書いていると、ステータスコードの指定ミスやメッセージの表記揺れが起きます。

`HTTPException` を継承した専用の例外クラスを作ることで、投げる側はシンプルになり、コードの保守性が上がります。

```python
class ItemNotFound(HTTPException):
    code = "item_not_found"  # 機械判別用のエラーコード

    def __init__(self, item_id: int):
        super().__init__(status_code=404, detail=f"Item {item_id} not found")
        self.details = {"item_id": item_id}  # 付加情報
```

呼び出す側（エンドポイント）:
```python
# 投げる側は「何が起きなかったか」を呼ぶだけ
if item is None:
    raise ItemNotFound(item_id)
```

---

## 5. エラーレスポンスの形式統一（例外ハンドラ）

### デフォルトのエラー形式の問題点
FastAPI 標準のままだと、エラーの種類によってレスポンスの JSON 構造がバラバラです。

- 通常の 404 / 409: `{"detail": "文字列"}`
- バリデーションエラー (422): `{"detail": [{"loc": [...], "msg": "...", "type": "..."}]}` （detail が配列）

これではフロントエンド側が「エラーメッセージを取り出すコード」をエラーごとに分岐して書かなければならず、扱いづらくなります。

### 統一フォーマットの設計
本プロジェクトでは、エラー時のレスポンス Body を以下の形式に統一します。

```json
{
  "error": {
    "code": "item_not_found",
    "message": "Item 99 not found",
    "details": {
      "item_id": 99
    }
  }
}
```

- **`code`**: プログラム（フロントエンドの `if` 文など）がエラー種別を判別するための固定文字列。
- **`message`**: 画面表示やログで人間が読むための説明文。
- **`details`**: エラーごとの付加情報（どの項目がどう間違っているか等）。

### 例外ハンドラ (`exception_handler`) の実装
`app.exception_handler(例外クラス)` を登録することで、指定した例外が発生した際のレスポンス生成処理をカスタマイズできます。

```python
# app/core/exceptions.py
from fastapi import FastAPI, Request
from fastapi.exceptions import HTTPException, RequestValidationError
from fastapi.responses import JSONResponse


def register_error_handlers(app: FastAPI) -> None:

    # 1. HTTPException (および自作の継承例外) を受け止めるハンドラ
    @app.exception_handler(HTTPException)
    async def http_exception_handler(request: Request, exc: HTTPException):
        return JSONResponse(
            status_code=exc.status_code,
            content={
                "error": {
                    "code": getattr(exc, "code", "http_error"),
                    "message": exc.detail,
                    "details": getattr(exc, "details", {}),
                }
            },
        )

    # 2. Pydantic のバリデーションエラー (422) を受け止めるハンドラ
    @app.exception_handler(RequestValidationError)
    async def validation_error_handler(request: Request, exc: RequestValidationError):
        return JSONResponse(
            status_code=422,
            content={
                "error": {
                    "code": "validation_error",
                    "message": "入力内容を確認してください",
                    # loc の先頭 ("body" や "query") を除き、フィールド名を抽出
                    "details": {
                        ".".join(str(part) for part in error["loc"][1:]): error["msg"]
                        for error in exc.errors()
                    },
                }
            },
        )
```

---

## 6. ハンドラの詳細（例外はどこで処理されるのか）

前節でハンドラを2つ登録しました。では、そのどちらにも当てはまらない例外が起きたら誰が受け止めるのでしょうか。たとえば、返そうとしたデータの型がレスポンススキーマと合わないときの `ResponseValidationError` や、単なる書き間違いによる `ZeroDivisionError` です。

### 例外は外側へ運ばれていく

Python の例外は、捕まえられなければ呼び出し元へ伝わります。FastAPI では、おおむね次の入れ子の内側から外側へ進みます。

```
┌ ServerErrorMiddleware ────────────────┐  外側
│  ┌ ユーザー定義ミドルウェア ────────┐ │
│  │ ┌ ExceptionMiddleware ────────┐ │ │
│  │ │   ルーター → 自分のコード    │ │ │  内側
│  │ └─────────────────────────────┘ │ │
│  └──────────────────────────────────┘ │
└───────────────────────────────────────┘
```

※ ユーザー定義ミドルウェアは、開発者がアプリに追加する共通処理（アクセスログ、認証チェック、CORS など）です。このアプリでは追加していないため、図のこの層はありません。

- **`ExceptionMiddleware`**（内側）— 例外の種類に応じて、登録されたハンドラを選ぶ担当者。
- **`ServerErrorMiddleware`**（外側）— 内側で処理されなかった例外を受け止める最後の守衛。共通ハンドラを1つ持てます。
- **Uvicorn**（アプリの外）— FastAPI アプリを呼び出すサーバー本体。

※ ミドルウェアは、リクエストとレスポンスの通り道に挟まる処理の層です。

以下は、通常の HTTP リクエストで、レスポンスの送信開始前に例外が起きる場合の説明です。

### ケース1：登録済みの例外が起きたとき（`ItemNotFound`）

1. 自分のコードが `ItemNotFound` を `raise` する。
2. 内側の例外処理で、親クラス `HTTPException` に登録したハンドラが見つかる。
3. 前節の自作ハンドラが、404 と統一フォーマットの JSON を返す。

例外の伝播はここで止まり、以降はレスポンスが外側へ返ります。例外は `ServerErrorMiddleware` や Uvicorn に届きません。

- 利用者に見えるもの … 404 と `{"error": {...}}` の JSON
- サーバーのログ … アクセスログは出るが、例外のトレースバックは自動では出ない

### ケース2：登録していない例外が起きたとき（`ResponseValidationError`）

1. FastAPI がレスポンスの検証中に `ResponseValidationError` を `raise` する。
2. 内側に該当するハンドラがなく、例外が外側へ伝わる。
3. `ServerErrorMiddleware` が、内部の例外情報を含まないプレーンテキストの 500 を送り（これはデフォルトのエラーハンドラの仕組み）、そして、同じ例外を再スローする。（なお、`Exception`／`500` のカスタムエラーハンドラーの登録により置き換え可能。このアプリではそうしている）
4. Uvicorn が再スローされたトレースバック付きのエラーログを出し、伝播を止める。（再スローをオフにすることはできないので、Uvicorn内部でのlogger.error()と重複でログが出てしまうことになる点だけ注意）

再スローはサーバーがエラーを記録できるようにするためで、Starlette の実装にもコメントがあります。

- 利用者に見えるもの … 500 と `Internal Server Error` という文字列
- サーバーのログ … トレースバックが出る
- サーバー … 落ちない。次のリクエストの処理を続ける


### 登録先が2つに分かれる理由

`@app.exception_handler(...)` の登録先は、カッコ内の**例外クラスまたはステータスコード**でフレームワークが決めます。

- `Exception` または `500` … `ServerErrorMiddleware`（外側）
- それ以外（`HTTPException`、`IntegrityError`、`404` など）… `ExceptionMiddleware`（内側）

登録時は同じ辞書に保存され、アプリが最初に呼び出されて入れ子を構築するときに仕分けされます。通常は起動時の lifespan 呼び出しで構築されます。

内側の `ExceptionMiddleware` は、ユーザー定義ミドルウェアで起きた例外を捕まえられません。共通ハンドラを外側に置くことで、その例外も扱えます。

外側の共通ハンドラがレスポンスを返した場合も再スローされるため、通常は Uvicorn のエラーログに残ります。

### ここから分かる実務上の注意

**内側のハンドラで処理した例外は、Uvicorn に伝わりません。** DB エラーなどの詳細やトレースバックを記録したい場合は、ハンドラ内などでログを出します。外側の共通ハンドラは、処理後も再スローする点が違います。

---

## 7. エラーの種類と開発者の対応方針

| エラー | 発生原因 | 誰がハンドリングするか | 開発者がやること |
| :--- | :--- | :--- | :--- |
| **`422`** (Validation Error) | リクエストの型や必須項目が不正 | FastAPI / Pydantic が自動検知 | 特になし（スキーマを正しく定義するだけ） |
| **`400` / `404` / `409`** (業務エラー) | データが存在しない、重複している等 | アプリのロジック | 条件分岐を書き、適切な例外を `raise` する |
| **`500`** (Internal Server Error) | プログラムの未考慮バグ、ゼロ除算など | FastAPI が自動で 500 を返却 | `try-except` で握りつぶさず、ログ（トレースバック）を見てバグを修正する |

> **500 エラーのポイント**
> サーバー内の想定外のエラー（500）は、ユーザーに内部の詳細（PythonのスタックトレースやDBの生エラー）を見せてはいけません（セキュリティリスクになるため）。サーバー側のコンソールやログに詳細を出力し、バグそのものを修正するのが正しいアプローチです。

---

## 8. 補足・現場でのTips

1. **RFC 9457 (Problem Details for HTTP APIs)**
   HTTP API のエラーフォーマット標準仕様として [RFC 9457](https://datatracker.ietf.org/doc/html/rfc9457)（旧 RFC 7807）が存在します。外部公開 API などで業界標準に厳密に合わせたい場合は RFC 9457 形式（`type`, `title`, `status`, `detail`, `instance` などのキー）を採用しますが、社内アプリや自社フロントエンド向け API では今回のような分かりやすい独自統一フォーマット（`{"error": {...}}`）も広く使われています。
2. **フレームワーク間の用語の違い**
   Flask / Werkzeug では `HTTPException.code` が「HTTP ステータス番号（整数: 404 等）」を指しますが、本プロジェクトの自作プロパティ `code` は「エラー識別用文字列 (`"item_not_found"` 等)」として定義しています。チーム開発時に混同しないよう意識しておくとスムーズです。
