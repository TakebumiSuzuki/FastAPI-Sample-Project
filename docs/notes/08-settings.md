# 08. 設定管理（pydantic-settings と .env）

## やったこと

- `backend/app/core/config.py` を作成し、`BaseSettings` で環境変数を型付きで読む仕組みを実装した
- `backend/.env` に実際の値を書き、`backend/.env.example` にチーム向けの雛形を置いた
- `.gitignore` で `.env` が git に載らず、`.env.example` は追跡されることを確認した

---

## 実装したコード

```python
# backend/app/core/config.py
from functools import lru_cache

from pydantic import EmailStr
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_name: str = "FastAPI App"
    admin_email: EmailStr
    items_per_user: int = 50

    model_config = SettingsConfigDict(env_file=".env")


@lru_cache
def get_settings() -> Settings:
    return Settings()  # type: ignore[call-arg]
```

---

## 学んだこと

### 設定管理の全体像

```
[backend/.env]
    │  python-dotenv が読み込んで OS の環境変数（文字列）に注入
    ▼
[環境変数（os.environ）]
    │  BaseSettings が取り出して型変換・バリデーション
    ▼
[Settings インスタンス（型付き・検証済み）]
    │  lru_cache により2回目以降はキャッシュを返す
    ▼
[get_settings() の返り値]
```

### `fastapi[standard]` に含まれるライブラリ

`uv add fastapi[standard]` でインストールした時点で、`pydantic-settings` と `python-dotenv` の両方がすでに入っている。`uv tree` で依存関係を確認できる（実際に確認済み）。

```
fastapi[standard]
└── pydantic-settings
    └── python-dotenv   ← これも一緒に入る
```

### `python-dotenv` と `pydantic-settings` の役割分担

| ライブラリ | 役割 |
| :--- | :--- |
| `python-dotenv` | `.env` ファイルを読んで OS の環境変数（文字列）に注入する |
| `pydantic-settings` | 環境変数を取り出し、型変換・バリデーションして設定オブジェクトにする |

`pydantic-settings` が内部で `python-dotenv` を使うため、開発者がコード上で `import dotenv` や `load_dotenv()` を書く必要はない。`SettingsConfigDict(env_file=".env")` がその呼び出しの窓口になっている。

### `pydantic-settings` を使う理由

`os.environ["ADMIN_EMAIL"]` で直接読む方法と比べた違い。

```
os.environ["ADMIN_EMAIL"]  → 文字列しか返らない。未設定でも KeyError になるまで気づかない
settings.admin_email       → 型付き。起動時点で未設定・不正値なら即 ValidationError
```

「型の安全性」と「起動時に設定が揃っているかを一括チェックする」ことが使う主な理由。

### `.env` と `.env.example` の運用

- `.env`：実際のパスワード・秘密鍵が入るファイル。**git に含めない**
- `.env.example`：チームメンバー向けの雛形。どんな変数を書けばよいかを示す。**git に含める**

```
# .env（git 管理外。本物の値）
ADMIN_EMAIL="your_name@company.com"

# .env.example（git 管理下。雛形）
ADMIN_EMAIL="your_email@example.com"
```

新メンバーの手順は `cp .env.example .env` して自分の値を書くだけになる。

### `core/` ディレクトリの意味

特定のエンドポイントに属さない、アプリ全体の共通基盤を置く場所。今後 `security.py`（JWT 等）が増えても `core/` にまとめることで、どこに何があるかが分かりやすくなる。

### `lru_cache` について

`functools` モジュールの標準ライブラリ。`LRU` は **Least Recently Used** の略で、容量が足りなくなったとき最も長く使われていないものから捨てるキャッシュアルゴリズム。

`get_settings()` に付けると、同じ引数（引数なし）での呼び出し結果をメモリに保持し、2回目以降はキャッシュを返す。実際に `get_settings() is get_settings()` が `True` になることで確認済み。

設定の読み込み自体は軽い処理なのでパフォーマンス上の差はほぼない。意味があるとすれば「アプリ全体で Settings インスタンスが必ず1つ」という保証。`settings = Settings()` をモジュールレベルに書けば同じことができるため、`lru_cache` が必須ではなく慣習として使われている。

### `# type: ignore[call-arg]` について

Pylance（静的型チェッカー）は `.env` ファイルを読まないため、「必須引数 `admin_email` が渡されていない」と誤検知してしまう。実行時には `.env` から値が取れるため動作上は問題ない。

デフォルト値なし（`admin_email: EmailStr`）にすることで「未設定なら起動時エラー」というバリデーション機能を維持し、静的解析の誤検知だけを黙らせるために `# type: ignore[call-arg]` を使う。これは `pydantic-settings` の公式ドキュメントでも示されている対処法（未検証・要確認）。

### `EmailStr` 型

`pydantic.EmailStr` を使うと、`str` より厳密なメールアドレス形式のバリデーションができる。`fastapi[standard]` に含まれる `email-validator` パッケージが内部で機能する。

```python
admin_email: EmailStr   # "not-an-email" を入れると起動時に ValidationError
```

### クラス定義とインスタンス化のライフサイクル

- **モジュール読み込み時（起動時）**：`class Settings(BaseSettings): ...` というクラスオブジェクト（設計図・工場）が定義されるだけで、インスタンス化（`Settings()`）はまだ行われない。この時点では `.env` や環境変数は読み込まれない。
- **初回 `get_settings()` 呼び出し時（ランタイム）**：初めて `Settings()` が実行され、`.env` や環境変数から値を取り出してバリデーション・インスタンス化が行われる。
- **2回目以降**：`@lru_cache` により初回生成されたインスタンスがそのまま返される。

### デフォルト値と環境変数の優先順位

`app_name: str = "FastAPI App"` のように定義した場合、イコール右辺は**デフォルト値**となる。
- **優先順位**：環境変数（OS / `.env`） > デフォルト値
- 環境変数に `APP_NAME="My Custom API"` が存在すればそれが優先して代入され、存在しない場合のみデフォルト値 `"FastAPI App"` が使われる。

### `Field()` を用いた詳細バリデーション

`BaseSettings` は Pydantic の `BaseModel` をベースにしているため、`Field()` を使った各種バリデーション（`ge`、`le`、`min_length` など）もそのまま利用できる。

```python
from pydantic import Field

class Settings(BaseSettings):
    # デフォルト値 50、かつ 10 以上 100 以下
    items_per_user: int = Field(default=50, ge=10, le=100)

    # 必須項目、かつ 1 以上
    db_pool_size: int = Field(ge=1)
```

---

## 作成・変更したファイル

- `backend/app/core/config.py`：`BaseSettings` を使った設定クラスと `get_settings()` を定義
- `backend/.env`：実際の環境変数の値（git 管理外）
- `backend/.env.example`：チーム向けの雛形（git 管理下）

---

## Q&A

### Q1. `fastapi[standard]` を入れれば `pydantic-settings` は別途インストール不要？
- **A**：不要。`fastapi[standard]` の依存に `pydantic-settings` が含まれており、`python-dotenv` もその依存として一緒に入る。`uv tree` で確認できる。

### Q2. `SettingsConfigDict(env_file=".env")` で `.env` を読むのは誰の仕事？
- **A**：実際に読むのは `python-dotenv` の仕事。`SettingsConfigDict(env_file=".env")` は `pydantic-settings` が内部で `python-dotenv` を呼ぶときのファイルパスを渡している窓口。開発者が `python-dotenv` を直接書く必要はない。

### Q3. `lru_cache` は必須か？
- **A**：必須ではない。設定の読み込みは軽い処理なのでパフォーマンス差はほぼない。モジュールレベルに `settings = Settings()` を1行書いても同様に「インスタンスを1つだけ持つ」ことが実現できる。慣習として `lru_cache` が使われることが多い。

### Q4. `admin_email: EmailStr` にデフォルト値を入れないと Pylance がエラーを出す。どう対処するか？
- **A**：`Settings()` の呼び出しに `# type: ignore[call-arg]` を付けて静的解析の誤検知を黙らせる。デフォルト値なし（必須）のまま保つことで「未設定なら起動時エラー」というバリデーション機能は維持される。

### Q5. `.env.example` は開発環境で使うファイルか？
- **A**：開発環境で実際に使うのは `.env`。`.env.example` はリポジトリをクローンしたチームメンバーが「どんな変数を書けばよいか」を知るための雛形。新メンバーは `cp .env.example .env` して自分の値を書くだけになる。

### Q6. `str` ではなく `EmailStr` を使う利点は？
- **A**：`str` はどんな文字列でも受け付けるが、`EmailStr` は `@` を含む正しいメールアドレス形式でないと起動時に `ValidationError` を出す。不正な設定値で API が動き続ける事故を防げる。

### Q7. `core/` ディレクトリは何のためにあるか？
- **A**：特定のエンドポイント（`items` 等）に属さない、アプリ全体の共通基盤を集める場所。`config.py`（設定）や将来追加する `security.py`（JWT 等）を置く。

### Q8. `Settings` のインスタンス化と環境変数読み込みのタイミングは？
- **A**：モジュール読み込み（import）時点ではクラス定義が作られるだけで、インスタンス化はされない。アプリ実行中に `get_settings()` が初回実行されたタイミングで初めてインスタンス化され、環境変数や `.env` から値が読み込まれる。

### Q9. デフォルト値と環境変数の優先順位は？
- **A**：環境変数が優先される。`app_name: str = "FastAPI App"` と設定していても、環境変数 `APP_NAME` が設定されていればその値で上書きされる。

### Q10. `BaseSettings` で `Field()` による数値範囲などのバリデーションは可能か？
- **A**：可能。`items_per_user: int = Field(default=50, ge=10)` のように指定でき、環境変数から読み込んだ値が条件（10以上など）を満たさない場合はインスタンス化時に `ValidationError` となる。
