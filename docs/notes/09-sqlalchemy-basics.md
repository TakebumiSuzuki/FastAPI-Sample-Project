# 09. SQLAlchemy 2.0 の基礎

## やったこと

- `uv add sqlalchemy` で SQLAlchemy 2.0.51 を追加した
- `.env` / `Settings` に `DATABASE_URL` を足し、接続文字列をコードに直書きしない形にした
- `app/models/base.py` に `Base`、`app/models/item.py` に `Item` テーブル定義を書いた
- `app/core/session.py` に `engine` を作った
- `Base.metadata.create_all(engine)` で `backend/app.db` を生成し、DB 側の実物を `inspect()` で確認した
- `app/`・`app/core/`・`app/routes/`・`app/models/` に `__init__.py` を置いた

---

## 実装したコード

```python
# app/models/base.py
from sqlalchemy.orm import DeclarativeBase


class Base(DeclarativeBase):
    pass
```

```python
# app/models/item.py
class Item(Base):
    __tablename__ = "items"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(50), unique=True)
    price: Mapped[Decimal] = mapped_column(Numeric(10, 2))
    sale_price: Mapped[Decimal | None] = mapped_column(Numeric(10, 2))
    description: Mapped[str | None] = mapped_column(String(5000))
    secret_memo: Mapped[str | None] = mapped_column(String(1000))
```

```python
# app/core/session.py
engine = create_engine(
    get_settings().database_url,
    connect_args={"check_same_thread": False},
    echo=True,
)
```

生成された DDL（`echo=True` の出力）：

```sql
CREATE TABLE items (
        id INTEGER NOT NULL,
        name VARCHAR(50) NOT NULL,
        price NUMERIC(10, 2) NOT NULL,
        sale_price NUMERIC(10, 2),
        description VARCHAR(5000),
        secret_memo VARCHAR(1000),
        PRIMARY KEY (id),
        UNIQUE (name)
)
```

---

## 学んだこと

### 全体像

```
[Item クラス]  ← Python 側の「表の設計図」
     │  class Item(Base) が実行された瞬間に登録される
     ▼
[Base.metadata]  ← 「このアプリにはどんな表があるか」の目録
     │  create_all(engine) が目録を見て CREATE TABLE に翻訳
     ▼
[Engine]  ← Pool（接続の使い回し）と Dialect（DBごとの方言）を束ねた部品
     │
     ▼
[backend/app.db]  ← SQLite の実体。1ファイルがそのまま DB
```

### 接続文字列の相対パスは「起動時のカレントディレクトリ」基準

`sqlite:///./app.db` のスラッシュ3本は相対パス、4本が絶対パス。基準はプロジェクトのルートでも
ソースファイルの位置でもなく、**プロセスのカレントディレクトリ**。

スクラッチパッドで `create_engine("sqlite:///rel_test.db")` を実行したところ、ファイルは
カレントディレクトリ側に作られ、`backend/` には作られなかった（実行して確認）。

→ このプロジェクトは「`backend/` から起動する」前提。別の場所から起動すると別の場所に
空の DB ができて「データが消えた」ように見える。

### `Base` は空でも意味がある

`DeclarativeBase` はメタクラスではなく**普通のクラス**（メタクラスは
`DeclarativeAttributeIntercept`）。仕掛けの本体は `__init_subclass__` という
Python 標準のフックで、「自分を継承したクラスが定義された瞬間に呼ばれる」。

```
class Base(DeclarativeBase): pass
        │
        ▼ __init_subclass__ が発火 → _setup_declarative_base(Base)
   Base.registry / Base.metadata が Base 側に作られる
```

`metadata` は `Base` のクラス変数。`DeclarativeBase.__dict__` には実体が無く
（`ClassVar[MetaData]` という型注釈だけ）、`Base.__dict__` に入る（実行して確認）。

### `Mapped[]` と `mapped_column()` の役割分担

- `Mapped[X]`：Python 側の型。`X` から DB の型が既定の対応表で決まる
  （`int`→`Integer()` / `str`→`String()` / `float`→`Float()` / `Decimal`→`Numeric()`）
- `mapped_column()`：型注釈で表せない情報（主キー・桁数・一意制約）を足す場所

対応表の右側はどれも**桁数の指定が無い**。`Mapped[Decimal]` だけだと DDL は桁なしの
`NUMERIC` になる。`(10, 2)` は Python の `Decimal` 型には表現できないので
`mapped_column(Numeric(10, 2))` で補う。

NULL 可否も注釈から決まる。`Mapped[str]` → NOT NULL、`Mapped[str | None]` → NULL 可。
よって `nullable=False` は書く必要がない。ただし優先順位は **`nullable` 引数 > 注釈**で、
`Mapped[str]` に `nullable=True` と書けば NULL 可になってしまう。

型も同じで、`mapped_column()` 側が勝つ。`Mapped[Decimal] = mapped_column(String(3))` と
食い違わせると、エラーにならず `VARCHAR(3)` になった（実行して確認）。

### `mapped_column()` の位置引数は実行時に見分けられている

シグネチャは `mapped_column(__name_pos=None, __type_pos=None, ...)`。1番目は
「列名（str）または型」、2番目は「型」。`sqlalchemy/sql/schema.py` の実物：

```python
l_args = [__name_pos, __type_pos] + list(args)
if l_args:
    if isinstance(l_args[0], str):   # 文字列なら列名として取り出す
        name = l_args.pop(0)
if l_args:
    coltype = l_args[0]              # 残った先頭を型として扱う
```

静的な型判別ではなく `isinstance` による動的な振り分け。

書き分けは次の5通り（実行して DDL を確認）。

```python
class Demo(Base):
    __tablename__ = "demo"

    # 1) 何も渡さない … 列名=属性名、型=Mapped[] から
    id: Mapped[int] = mapped_column(primary_key=True)

    # 2) 型だけ … 1番目が str でないので「型」と判定される
    name: Mapped[str] = mapped_column(String(50))

    # 3) 列名だけ … 1番目が str なので「列名」と判定され、型は Mapped[] から
    memo: Mapped[str] = mapped_column("memo_text")

    # 4) 両方 … 1番目=列名、2番目=型
    price: Mapped[Decimal] = mapped_column("unit_price", Numeric(10, 2))

    # 5) キーワードで明示（位置引数を使わない書き方）
    note: Mapped[str] = mapped_column(name="note_col", type_=String(20))
```

生成される DDL：

```sql
CREATE TABLE demo (
	id INTEGER NOT NULL,
	name VARCHAR(50) NOT NULL,
	memo_text VARCHAR NOT NULL,
	unit_price NUMERIC(10, 2) NOT NULL,
	note_col VARCHAR(20) NOT NULL,
	PRIMARY KEY (id)
)
```

3) と 4) のように列名を指定しても、Python 側の属性名は `memo` / `price` のまま
（`d.memo` でアクセスできることを実行して確認）。列名だけ変えたいのは、DB の命名規則に
合わせつつ Python では別名で扱いたいとき。

### `check_same_thread: False` が要る理由

SQLite は既定で「接続を作ったスレッド以外からの使用」を拒否する。一方 FastAPI は
`def`（非 async）のエンドポイントをスレッドプールで動かすため、1回のリクエストが
複数スレッドをまたぐことがある。

```
リクエスト → スレッドA で依存関係を解決
           → スレッドB でエンドポイント本体
              └─ SQLite「作ったスレッドと違う。拒否」
```

FastAPI 公式チュートリアルにも「1つのリクエストが複数のスレッドを使いうるため必要」と
明記されている。安全性は「1リクエスト＝1セッション」を守ることで担保する（第10章）。

### `create_all` の落とし穴：モデルを import しないと何も作られない

`create_all` が見るのは `Base.metadata` の中身だけ。`Item` が登録されるのは
`app/models/item.py` が import された瞬間。この import を忘れると、**エラーも出ないまま
中身が空の `app.db` ができる**。

なお `from app.models.base import Base` の行は、モジュール読み込みの意味では不要
（`item.py` が `base.py` を import 済み）。`Base` という名前を使うために書いているだけで、
`Item.metadata.create_all(engine)` でも同じ（`Item.metadata is Base.metadata` は `True`）。

### `__init__.py` は基本的に置く

`__init__.py` の有無でパッケージの種類が変わる。

| 形 | 呼び名 |
| :--- | :--- |
| `__init__.py` あり | 通常パッケージ（Python 標準の形） |
| `__init__.py` なし | 名前空間パッケージ（PEP 420。1つのパッケージを複数の配布物に分割する用途） |

無くても動くのは後者として扱われているだけ。pytest 公式も「同名のテストモジュールを
置きたい場合は `__init__.py` を追加してパッケージにする」と書いている。
`backend/` 直下には置かない（そこはパッケージではなくプロジェクトのルート）。

---

## 詰まった点

- `__tablename__` を `table_name` / `__table_name__` と書いてしまい、
  `InvalidRequestError: ... does not have a __table__ or __tablename__ specified` になった。
  前後にアンダースコア2本ずつで、`table` と `name` の間には入らない。
- `sqlite3` コマンドが入っていないのに `app.db` ができて混乱した。→ Q&A 参照。

---

## 作成・変更したファイル

- `backend/app/models/base.py`：`Base`（新規）
- `backend/app/models/item.py`：`Item` テーブル定義（新規）
- `backend/app/core/session.py`：`engine`（新規）
- `backend/app/core/config.py`：`database_url` を追加
- `backend/.env` / `.env.example`：`DATABASE_URL` を追加
- `backend/app/{,core/,routes/,models/}__init__.py`：空ファイルを追加
- `backend/pyproject.toml`：`sqlalchemy>=2.0.51`

---

## Q&A

### Q1. `DATABASE_URL` を `backend/app.db` のような「プロジェクトルートからのパス」で書ける？
- **A**：書けない。先頭が `/` でない以上それも相対パスで、基準はカレントディレクトリ。
  `backend/` から起動すれば `backend/backend/app.db` を探しに行く。絶対パスにするなら
  スラッシュ4本（`sqlite:////workspaces/.../app.db`）だが、`.env.example` に書くと
  他の人の環境で外れる。

### Q2. `.env` は大文字、`Settings` のフィールドは小文字でよい？
- **A**：よい。`pydantic-settings` の `case_sensitive` は既定値が `False` で、大文字小文字を
  区別せず照合する。大文字は Unix の環境変数の慣習、小文字は PEP 8 の慣習で、その差を
  この既定値が吸収している。厳密に一致させたいなら `case_sensitive=True`。

### Q3. `DeclarativeBase` はメタクラス？ `metadata` はクラス変数？
- **A**：`DeclarativeBase` は普通のクラス（メタクラスは `DeclarativeAttributeIntercept`）。
  `metadata` は `Base` のクラス変数。ただし親の `DeclarativeBase` には実体が無く、
  `class Base(DeclarativeBase)` を書いた瞬間に `__init_subclass__` が `Base` 側に作る。

### Q4. `engine` はコネクションプールのようなもの？
- **A**：半分正しい。`Engine` は Pool（実測 `QueuePool`）と Dialect（DB ごとの方言）を
  束ねた部品で、プールは `engine.pool` として中にいる。また `create_engine` の時点では
  接続しない。`create_all` やクエリなど、実際に接続が要る操作で初めて開く。

### Q5. `sqlite3` コマンドが無いのに DB ファイルができたのはなぜ？
- **A**：`sqlite3` コマンド（対話用 CLI）と SQLite 本体（C ライブラリ）は別物。
  SQLite はサーバーではなくライブラリで、その実体は Python 標準ライブラリの
  `sqlite3` モジュールに含まれている。この環境では `_sqlite3` に `__file__` が無く、
  Python 実行ファイルに静的リンクされていた（内蔵バージョン 3.50.4）。
