# 02. 最初のエンドポイントと自動ドキュメント

## やったこと

```bash
uv add "fastapi[standard]"
```

`backend/main.py` を書き換え：

```python
from fastapi import FastAPI

app = FastAPI()


@app.get("/")
def read_root():
    return {"message": "Hello, FastAPI!"}
```

```bash
uv run fastapi dev
```

VS Code の自動ポート転送経由で `http://localhost:8000/docs` を開き、Swagger UI を確認した。

## 学んだこと

### extras（`fastapi[standard]` の `[...]`）
- Python パッケージングの正式な仕組み。PyPA の Packaging User Guide に規定されている
- パッケージ作者が `[project.optional-dependencies]` で「`standard` という名前で
  これらも一緒に入れられる」と定義しており、利用側は `パッケージ名[extra名]` と書くだけで済む
- FastAPI は 0.112.0 以降、素の `fastapi` に `uvicorn` / `fastapi-cli` を含めなくなった。
  `fastapi[standard]` にしないと `fastapi dev` が使えない（実際 `.venv/bin/` に
  `uvicorn` がなく、`fastapi` 実行ファイルはあってもサーバーを起動できなかった）

### `"fastapi[standard]"` をダブルクォートで囲う理由
- Python/uv の文法とは無関係。**シェル（zsh）側の理由**
- `[...]` は zsh・bash 共通で glob（ワイルドカードのファイル名展開）に使われる特殊文字
- 無引用符だと `zsh: no matches found: fastapi[standard]` のようなエラーになりうる
- ダブルクォートで囲むと、シェルはそれを glob 展開せず「ただの文字列」として扱う

### エンドポイント関数の名前は自由
- `@app.get("/")` の **`"/"` が URL パスを決めている**
- 直下の `def 関数名():` の関数名は、Python の通常の命名ルールに従えば何でもよい
  （`read_root` は単なる慣習的な名前で、パスとは無関係）

### `/docs` と `/openapi.json` はファイルではない
- `/openapi.json` はディスク上に存在しない。リクエストが来るたびに
  `app.openapi()` がその場で JSON を組み立てて返すエンドポイントの一つ
- 中身は `app.routes`（`@app.get` 等で登録した全エンドポイントの型ヒント情報）から
  組み立てられる。初回だけ計算し、結果を `app.openapi_schema` にキャッシュして使い回す
  （毎回作り直すコストを避けるため、と公式ドキュメントに明記）
- `/docs` は Swagger UI という外部の JS ライブラリが `/openapi.json` を読み込んで
  画面を描画しているだけ。`/docs` 自体が特別なファイルなわけではない

### `/docs` `/openapi.json` `/redoc` は予約語ではなくデフォルト値
- `FastAPI()` のコンストラクタ引数 `docs_url="/docs"` / `openapi_url="/openapi.json"` /
  `redoc_url="/redoc"` のデフォルト値にすぎない
- `FastAPI(docs_url="/documentation", redoc_url=None)` のように変更・無効化できる

### ASGI と uvicorn の役割（例え：シェフとホール係）
- `main.py`（FastAPI アプリ本体）＝厨房のシェフ。「どの注文に何を作るか」を決める
- `uvicorn`＝ホール係。実際に TCP ソケットでリクエストを受け付け、シェフに伝え、
  レスポンスを届ける。FastAPI 自身はネットワーク通信を待ち受けない
- ASGI（Asynchronous Server Gateway Interface）＝シェフとホール係の間の共通の伝え方の規格。
  この規格のおかげで uvicorn を Hypercorn 等の別の ASGI サーバーに差し替えても
  アプリ側のコードは変えなくてよい

### `fastapi dev` は uvicorn のラッパー
- 公式ドキュメント（fastapi-cli のページ）に "It uses Uvicorn... under the hood" と明記
- `fastapi dev` がやっていること：①`main.py` から `app` という名前の変数を自動検出
  ②`watchfiles` で自動リロードを設定 ③その上で uvicorn を起動
- 実際、起動ログに `Uvicorn running on http://127.0.0.1:8000` と表示され、
  裏で uvicorn が動いている証拠がそのまま見えていた

## 追記：Q&A で深掘りしたこと

（検証は `backend/.venv` 内の実物のソースを読み、TestClient で実際に叩いて確認。
fastapi 0.141.1 / starlette 1.3.1 / uvicorn 0.52.0）

### 末尾スラッシュ：`/items` と `/items/` は別のパス
- Starlette は書いた形のパスだけを登録する。どのルートにも当たらなかったとき、
  末尾スラッシュを足した／剥がした形で再照合し、当たれば **307 リダイレクト**を返す。
  この補正は**双方向**（`/items` → `/items/` も、`/items/` → `/items` も効く）
  （`Router.app()` / `starlette/routing.py:695`）
- 307 なのはメソッドとボディを保持するため（301/302 だと POST が GET に化ける）
- Flask とは向きが違う。**Flask はルール定義が正で片方向**：
  `@app.route('/projects/')` に `/projects` で来たらリダイレクト、
  `@app.route('/about')` に `/about/` で来たら **404**（URL を一意に保つため、と公式が明記）
- 止めたければ `FastAPI(redirect_slashes=False)`

### `@app.get("")` は書けてしまうが、届かない
- `""` と書くと「パスが空文字のときだけ呼ばれるルート」が登録される。エラーは出ない
- ところがブラウザは `http://localhost:8000` と打っても `/` を付けて送る。
  サーバに空文字のパスが届くことはないので、このルートは一生呼ばれず 404
- 末尾スラッシュのリダイレクト救済（`/` を足す／剥がす）も、695行の条件
  `route_path != "/"` で `/` 宛てを除外しているため、ここでは働かない
- `app` 直下は必ず `@app.get("/")`
- 例外：`APIRouter(prefix="/api")` と組み合わせた `@r.get("")` は `/api` になる正しい書き方
  （`prefix` は末尾スラッシュ禁止なので、こう書くしかない）

### エンドポイントのレジストリの正体はただのリスト
- `FastAPI()` は内部に `APIRouter` を1つ持ち、その `.routes`（`list[BaseRoute]`）が全登録簿。
  `@app.get()` は `APIRoute` を作って append しているだけ
- ルーティングは**上から線形走査で最初にマッチしたもの勝ち**。つまり登録順に意味がある
- `/openapi.json` `/docs` `/redoc` は `FastAPI.__init__` → `setup()` の中で
  `include_in_schema=False` で登録される**普通のルート**。自分のルートより先頭に並ぶ
- `get_openapi()` はこのリストを走査し、**`APIRoute` のインスタンスだけ**を拾って
  `route.path_format`（`/items/{item_id}` の形）をキーに組み立てる。
  素の Starlette `Route` や `Mount` は無視される＝ドキュメントに出ない
- 型ヒントが JSON スキーマになるのは、`APIRoute` が生成時に解析結果を属性として
  抱えているから。ドキュメント生成時にソースを読み直しているわけではない

### イベントループを持っているのは uvicorn の方
- FastAPI アプリは「呼ばれるだけの async な関数」で、ループは自分で持たない
- uvicorn がソケットを開き、ループを回し、HTTP を dict（scope）に変換してアプリを呼ぶ
- だから `uvicorn main:app` と、**店長（uvicorn）にシェフ（app）を渡す**形で起動する

### `async def` と `def` の使い分け（重要）
- `async def` → そのままイベントループ上で実行
- `def` → FastAPI が自動でスレッドプールに逃がす（`run_in_threadpool`、
  `fastapi/routing.py:354`）。同時実行スレッド数の既定は **40**
- GIL があるので Python バイトコードを実行できるスレッドは常に1つ。だが
  **「同期関数を回すとループが止まる」わけではない**：
  - GIL は 5ms ごとに手放される（`sys.getswitchinterval() == 0.005`）
  - そもそも I/O 待ちの間は GIL を解放するので、その間ループは自由に動く
  - スレッドに逃がすのは、まさにこの効果を狙った仕組み
- **本当に全体が止まる地雷は `async def` の中にブロッキング処理を書くこと**。
  この場合スレッドへの退避が起きず、待っている間サーバー全体が停止する

| 書き方 | 中身 | 結果 |
| --- | --- | --- |
| `def` | I/O 待ち | 別スレッド。影響ほぼ無し |
| `def` | CPU 計算 | 別スレッド。全体が遅くなるが停止はしない |
| `async def` | ブロッキング呼び出し | **全体が停止** ← 最悪 |
| `async def` | `await` のみ | 理想形 |

### gunicorn はもう不要
- 昔は「複数プロセスの起動・監視・再起動」が uvicorn では貧弱だったので、
  その役目だけ gunicorn に任せて uvicorn をワーカーとして動かしていた
- 今はその機能が uvicorn 本体に入った（`uvicorn/supervisors/multiprocess.py`）ので
  `uvicorn --workers 4` で足りる。FastAPI 公式のデプロイページからも gunicorn の記述は消えた
- uvicorn 側の連携モジュールも `"The uvicorn.workers module is deprecated"` と警告を出す
- なお Docker / K8s では `--workers` を使わず「1コンテナ1プロセス、レプリカ数で増やす」が公式推奨

## 詰まった点・気づき

- devcontainer の `devcontainer.json` に `forwardPorts` の明示設定はなかったが、
  VS Code の Dev Containers 拡張がリッスン中のポートを自動検出して転送してくれるため、
  追加設定なしで `localhost:8000` にアクセスできた
