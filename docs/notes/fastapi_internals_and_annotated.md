# FastAPIの内部動作と `Annotated` の仕組み完全ガイド

本書は、Pythonの型注釈 `Annotated` の仕様から、FastAPIにおけるデコレータの評価フロー、起動時の型・引数解析（`get_dependant`）、内部データ構造（`Dependant`）、そしてリクエスト実行時の依存解決・バリデーションまでの仕組みを体系的にまとめた技術ノートです。

---

## 1. Python `typing.Annotated` の仕様と型チェッカーの挙動

### ① 第2引数以降の仕様（メタデータ）
`Annotated` は [PEP 593](https://peps.python.org/pep-0593/) で導入された型注釈です。
シグネチャは概念的に以下のようになっています：

$$\text{Annotated}[T, *metadata]$$

- **第1引数 ($T$)**: 実際の型（`int`, `str`, 自作クラスなど）
- **第2引数以降 ($*metadata$)**: **任意のPythonオブジェクト（実質 `Any`）**

Pythonの文法・仕様上、第2引数以降には何を入れても構いません。文字列、数値、クラスインスタンス（`Path(ge=1)`）、関数、辞書などをいくつでも渡せます。

```python
# すべて文法・型仕様として有効
item_id: Annotated[int, Path(ge=1)]
user_id: Annotated[int, "ユーザーID", {"example": 42}, Path(gt=0)]
```

### ② 静的型チェッカー（mypy, pyright等）の扱い
**型チェッカーは第2引数以降のメタデータを無視（透過）します。**
型チェッカーにとって、`Annotated[int, Path(ge=1)]` は単なる `int` として認識されます。そのため、静的型チェックの厳密性を保ちながら、フレームワーク（FastAPIなど）に対して任意の実行時メタデータを付与できます。(ただし、pythonのインタープリタは 3.13以下のバージョンでは、ランタイムの読み取り時に評価してエラーなども出しうることに注意。3.14以降はlazyに、実際に必要とされときに初めて評価する)

---

## 2. FastAPIのデコレータと評価順序

> **📌 まとめ**
>
> アプリを起動するときに、各エンドポイントにつき、デコレーターの働きにより、`APIRoute` オブジェクトが1つずつ作られ、リストに保持されます。この `APIRoute` は、そのエンドポイントを動かすのに何が必要か（引数、つまり依存の一覧）をまとめた `Dependant` オブジェクトを属性としてあらかじめ持っています。
>
> リクエストが来ると、そのリストから該当する `APIRoute` を探し（マッチング）、見つかったら、その `Dependant` をもとに実際の値（パスパラメータやDB接続など）を集めます（依存解決）。集める過程でエラーがなければ、その値をエンドポイント関数の引数として渡して実行します。

### ① 引数付きデコレータの仕組み
FastAPIでエンドポイントを定義する際、以下のように記述します：

```python
@router.get("/{item_id}", response_model=ItemPublic)
def read_item(item_id: Annotated[int, Path(ge=1)]):
    ...
```

Pythonの構文糖（`@`）において、実行は以下の順序で行われます：

1. **`router.get(...)` の評価（先に実行）**:
   - パス文字列 `/{item_id}` や設定引数を受け取り、**デコレータ関数（`decorator`）自体を生成して返す**（デコレータファクトリ）。
2. **関数 `read_item` の定義**を読み取る。
3. **`@` によるデコレート処理の実行**:
   - `read_item = decorator(read_item)` が実行される。

```python
# fastapi/routing.py の内部イメージ
class APIRouter:
    def get(self, path: str, ...):
        def decorator(func):
            # ルーター内部のエンドポイント登録処理
            self.add_api_route(path, func, methods=["GET"], ...)
            return func  # 関数自体はそのまま返す
        return decorator
```

### ② `@app.get` と `@router.get` の関係
`app = FastAPI()` と書いた場合も同様です。`FastAPI` クラス自身が `get` メソッドを持っており、内部で保持しているメインルーターの `app.router.get(...)` を呼び出して委譲しています。

---

## 3. 起動時（初期化時）の内部解析処理

FastAPIアプリケーションの起動時（モジュール読み込み時）、`self.add_api_route` を起点に関数の引数や型注釈が解析されます。

```
def add_api_route(self, path: str, endpoint: Callable, **kwargs):
   # 1. ルーター共通の設定と、引数の個別設定を合成する
   # tags（タグ）: Swagger に使われるだけ。ドキュメントの見出し分けの用途。
   current_tags = self.tags + (kwargs.get("tags") or [])
   current_dependencies = self.dependencies + (kwargs.get("dependencies") or [])

   # 2. 1つのエンドポイント定義を表す APIRoute オブジェクトを作成する
   # ┌──────────────────────────────────────────────────────────────┐
   # │ ★ get_dependant はこの APIRoute(...) の生成処理の中で呼ばれます！ │
   # │   (具体的には、init関数の中で、間接的に get_dependant が呼ばれる)  │
   # │   引数の endpoint（関数）の型ヒントや Depends を解析して、   │
   # │   リクエストから引数を受け取る設計図（Dependant）を作成します。  │
   # └──────────────────────────────────────────────────────────────┘
   route = APIRoute(
      path=self.prefix + path,
      endpoint=endpoint,
      tags=current_tags,
      dependencies=current_dependencies,
      **kwargs,
   )

   # 3. ルーターの保持するルート一覧リストに追加する
   self.routes.append(route)
```

### `get_dependant` 関数とは？
    エンドポイント関数と URL パスを解析し、「HTTPリクエストからどのようにデータを取り出して関数に渡すか」の実行設計図（`Dependant`）を作る関数です。

    * **何をしているのか**:
      1. **引数の判別**: `path`（URL）と引数名を比較し、パスパラメータかクエリパラメータかを自動で仕分ける。
      2. **依存関係の解析**: 引数に書かれた `Depends(...)` や型ヒントを解析し、実行すべき前処理（DB接続など）のツリーを組み立てる。


### ① なぜ `get_dependant` にパス文字列（`path`）を渡すのか？
FastAPIは関数の引数が **「どこから取得されるべき値か」** を判別するために、URLパス文字列と照合します。

- **URLパス文字列**: `"/items/{item_id}"`
- **引数リスト**: `item_id: int`, `limit: int = 10`

1. `item_id` はパス文字列の中に `{item_id}` として存在するため ➔ **パスパラメータ**（`path_params`）と判定。
2. `limit` はパス文字列に含まれていないため ➔ **クエリパラメータ**（`query_params`）と判定。

### ② `Annotated` と Pydantic バリデータの構築
`get_dependant` は `typing.get_type_hints(endpoint, include_extras=True)` を用いて引数情報を取得します。

- 型が `int` であることを抽出。
- メタデータから `Path(ge=1)`（実態は Pydantic の `FieldInfo`）を抽出。
- これらをもとに Pydantic のバリデータ（型変換＋制約チェック `ge=1`）を構築し、後述の `Dependant` オブジェクトに格納します。

---

## 4. 統一データ構造：`Dependant` クラス

`Dependant` クラス（`fastapi.dependencies.models.Dependant`）は、関数の引数をどのように解決（収集・検証）するかを記録した**統一設計図オブジェクト**です。

### 固定された主要属性
`Dependant` の属性名は固定で決まっており、あらゆる複雑な引数の組み合わせを整然と分類・格納します。

| 属性名 | 格納されるデータ | 具体例 |
| :--- | :--- | :--- |
| `call` | 最終的に実行する関数本体 | `read_item`（エンドポイント関数）や `get_db`（依存関数） |
| `path_params` | URLパスから抽出・検証する引数 | `item_id: Annotated[int, Path(ge=1)]` |
| `query_params` | クエリ文字列から抽出する引数 | `limit: int = 10`, `q: str \| None = None` |
| `header_params` | HTTPリクエストヘッダーから抽出する引数 | `user_agent: Annotated[str, Header()]` |
| `cookie_params` | Cookieから抽出する引数 | `session_id: Annotated[str, Cookie()]` |
| `body_params` | リクエストボディ（JSON, Form, File） | `item: ItemCreate`, `file: UploadFile` |
| `dependencies` | `Depends(...)` で指定された依存関係 | `db: Annotated[Session, Depends(get_db)]` |
| `security_requirements` | 認証・認可に関するセキュリティ定義 | `OAuth2PasswordBearer` 等のスキーム |

> **ポイント**:
> 関数の引数がいかに複雑であっても（パス＋クエリ＋ボディ＋ヘッダー＋多段のDepends）、すべてこの `Dependant` オブジェクトの各リストに過不足なく分類されて収まります。

---

## 5. リクエスト受信時（実行時）の動作フロー

起動時に `Dependant` という設計図が完成しているため、リクエスト受信時に毎回 `inspect` や型注釈の解析をする必要がなく、極めて高速に処理されます。

```
[クライアントから HTTP Request 到着]
                     │
                     ▼
[Starlette ルーティング層]
  URLパスから文字列パラメータを抽出 (scope["path_params"] = {"item_id": "123"})
                     │
                     ▼
[fastapi.dependencies.utils.solve_dependencies()]
  route.dependant を参照しながら各引数を解決：
  1. path_params のバリデータで "123" を int(123) かつ ge=1 を検証・変換
  2. query_params, body_params 等を同様に収集・検証
  3. dependencies (Depends) の関数を再帰的に実行して結果を取得
                     │
                     ▼
[バリデーション成否の判定]
  ├─ エラーあり ➔ 即座に 422 Unprocessable Entity レスポンスを返却
  └─ 正常 ➔ 解決された引数辞書 values = {"item_id": 123, ...} を作成
                     │
                     ▼
[エンドポイント関数の呼び出し]
  endpoint(**values) を実行し、戻り値をレスポンスモデルに適合させて返却
```

---

## 6. ソースコード参照マップ（FastAPI リポジトリ）

FastAPIの内部実装を追う際の主要ファイルとポイントです：

1. **`fastapi/routing.py`**
   - `APIRouter.get` / `add_api_route`: デコレータの実装とルート登録リスト（`self.routes`）。
   - `APIRoute.__init__`: ルート初期化時に `get_dependant` を呼び出す。
2. **`fastapi/dependencies/models.py`**
   - `class Dependant`: 各種パラメータや依存関係を保持するデータ構造。
3. **`fastapi/dependencies/utils.py`**
   - `get_dependant`: 起動時に関数・型注釈（`Annotated`）・URLパスを解析して `Dependant` を組み立てる関数。
   - `solve_dependencies`: リクエスト時に `Dependant` を使って実際にパラメータを検証・注入する関数。
