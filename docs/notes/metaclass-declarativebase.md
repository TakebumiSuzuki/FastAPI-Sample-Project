
---

# Pythonのメタクラスと SQLAlchemy 2.0 Declarative システムの仕組み

---

## 1. Pythonにおけるメタクラスの本質

### ① 暗黙的な `metaclass=type`
Pythonで通常クラスを定義すると、明示的に指定しなくても暗黙的に `metaclass=type` が適用されています。

```python
# 下記の2つは同義
class User:
    pass


class User(metaclass=type):
    pass
```

### ② デフォルトメタクラス `type` の役割
* `type` は CPython の C 言語レベル（`PyType_Type`）で実装された組み込み型です。
* 味付けのない「素のクラス生成機」であり、メモリを確保し、クラス名・継承元（bases）・属性辞書（dict）をまとめて内部のデータ構造（`PyHeapTypeObject`）を作成します。

### ③ 自作メタクラス `class MyMeta(type)` の役割
* `type` を継承して自作メタクラスを定義することで、C言語レベルのクラス作成処理の**前後**に割り込み（フック）を行い、属性の自動追加・バリデーション・クラスの自動登録などの処理を追加できます。

---

## 2. SQLAlchemy 2.0 における 2 つのフック機構の役割分担

SQLAlchemy 2.0 の `DeclarativeBase` では、**「`__init_subclass__`」** と **「メタクラス（`DeclarativeAttributeIntercept`）」** が連携して動作しています。

```
【DeclarativeBase】
 ├── メタクラス: DeclarativeAttributeIntercept （type を継承）
 └── フック関数: __init_subclass__
```

### 役割の違いまとめ

| 機構 | 担当する役割 | 動作するタイミング |
| :--- | :--- | :--- |
| **`__init_subclass__`**<br>(Python標準のサブクラスフック) | **【クラス定義時の登録・解析】**<br>・`registry` と `metadata` (クラス変数)の初期化<br>・`__tablename__` や `Mapped[...]`、`mapped_column()` のスキャン<br>・SQLAlchemy Core の `Table` / `Column` オブジェクトの自動生成と登録 | `class Base(...)` や `class User(Base)` のコードが評価（インポート）された瞬間 |
| **メタクラス**<br>(`DeclarativeAttributeIntercept`) | **【クラス定義後の動的変更の検知】**<br>・クラス定義完了後に、後からクラス変数が代入・更新された時の検知（`__setattr__` のフック）<br>・特殊なクラス属性アクセスの横取り | `User.nickname = mapped_column(...)` のように後から属性が追加・変更された時 |

---

## 3. クラス定義時のライフサイクル（実行順序）

### Step 1: `class Base(DeclarativeBase): pass` の定義時
1. `DeclarativeBase.__init_subclass__` が作動。
2. このグループ専用の **新しい `registry`** と **`metadata`（`registry.metadata`）** が生成される。
3. `Base.registry` および `Base.metadata` としてクラス変数にセットされる。

### Step 2: `class User(Base):` の定義時
1. `Base.__init_subclass__` が作動（内部関数 `_as_declarative` が実行される）。
2. クラス内の属性をスキャン：
   * `__tablename__ = "users"` からテーブル名を特定。
   * `Mapped[int]`, `mapped_column(primary_key=True)` 等を解析。
3. SQLAlchemy が内部で `Table('users', Base.metadata, ...)` を自動組み立て。
4. `Base.registry` に対し、「Pythonクラス `User`」と「テーブル `users`」のマッピング情報を登録。
5. `User` クラスの各カラム属性を SQLAlchemy の ORM ディスクリプタに置き換える。

### Step 3: 定義完了後の動的操作
1. 後から動的にカラムを追加した場合（例: `User.age = mapped_column(Integer)`）。
2. ここで **メタクラス（`DeclarativeAttributeIntercept`）の `__setattr__`** が反応し、追加されたカラムを検知してテーブル定義を自動更新する。

---

## 4. なぜ `Base` を間に挟むのか？

```python
# なぜ直接 DeclarativeBase を継承せず、Base を経由するのか？
class Base(DeclarativeBase):
    pass


class User(Base):
    __tablename__ = "users"
```

### 理由①：`registry` / `metadata` のグループ境界（シングルトン共有）を作るため
* `DeclarativeBase` は「それを直接継承したクラスに対して新しい `registry` を発行する」という仕様です。
* `User` と `Post` が直接 `DeclarativeBase` を継承すると別々のレジストリに分離してしまい、テーブル間のリレーション（ForeignKey）が組めなくなります。
* `Base` を1つ挟むことで、**「`Base` の傘下にいる全モデルが同じ `metadata` / `registry` を共有する」** という境界が作られます。

### 理由②：マルチデータベース（複数DB）への対応
* DBが複数ある場合、`BaseA(DeclarativeBase)` と `BaseB(DeclarativeBase)` を作ることで、互いに干渉しない完全に独立したスキーマコンテナを構築できます。

### 理由③：共通処理・型マッピングの集約
* `Base` に共通の型設定（`type_annotation_map`）や共通メソッド（`to_dict()` など）を記述しておくことで、全モデルに一括適用できます。

### 理由④：静的型チェッカー（mypy / Pylance）への完全対応
* 2.0 の `DeclarativeBase` は、型推論エンジンが「通常のクラス継承ツリー」として解釈できるように設計されています。

---

## 5. 本質まとめ

1. **クラス定義**は、デフォルトでは `type` というC言語レベルの基本工場がメモリを確保して作成する。
2. **SQLAlchemy 2.0** は、このPythonの仕組みに乗っかり、**メタクラス**と **`__init_subclass__`** を組み合わせてORMの構築を自動化している。
3. **`__init_subclass__`** がインポート時の「テーブル情報スキャン＆ `registry` / `metadata` 登録」を担当し、**メタクラス** が「定義後の属性変更の監視」を担当する。
4. **`Base`** は、1つのデータベースに属するテーブル群（`User`, `Item` 等）が同じ `metadata` を共有するための「親コンテナ」である。


## 以下、Q＆A

### 1. v2 では `__init_subclass__` がテーブル定義・レジストリ登録の主軸なのか？

**はい、その通りです。**

SQLAlchemy 2.0 では、クラス定義の記述（`Mapped[...]` や `mapped_column()`、`__tablename__` など）を読み取って、SQLAlchemy の `Table` や `Mapper` に構造化し、`registry` に登録する一連のメイン処理は **`__init_subclass__` が起点（エントリーポイント）となって動いています。**

---

### 2. `__init_subclass__` は `User` がインポート（評価）された時にも発動するのか？

**はい、確実に発動します。**

Pythonの `__init_subclass__` の仕様として、**「それを定義している親クラスを継承した子クラスが作られるたびに、毎回自動で実行される」** というルールがあります。

Pythonがファイル（モジュール）をインポートして上からコードを読み、

```python
class User(Base):
    __tablename__ = "users"
    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str]
```

という部分を通過（評価）した**まさにその瞬間**に、`Base` から継承されている `__init_subclass__` が呼び出されます。

---

### 3. `User` 作成時、`metadata` や `registry` は新しく作られず `Base` のものを参照するのか？

**はい、完全にその通りです。**

SQLAlchemy 2.0 の内部処理では、以下のように「自分が大元の `Base` なのか、それともテーブルになる子クラス（`User`）なのか」を判定しています。

1. **`Base` 定義時**:
   * まだ `registry` を持っていないため、「新しい `registry` と `metadata` を1つ生成して `Base` に持たせる」。
2. **`User` 定義時（インポート時）**:
   * 親である `Base` がすでに `registry` を持っているかを検知します。
   * 新しく作り直すことは**絶対にせず**、`Base.registry` をそのまま参照して、**「この `User` クラスを `Base` の既存の `registry` / `metadata` に追加登録する」** という処理を行います。

そのため、Pythonの通常のクラス継承ルールにより：
* `User.metadata is Base.metadata` ➔ **`True`（全く同じオブジェクトを参照）**
* `User.registry is Base.registry` ➔ **`True`（全く同じオブジェクトを参照）**

となります。

---

### 全体の流れのイメージ

```
【1. アプリ起動時: Base の定義】
class Base(DeclarativeBase): pass
  └─► __init_subclass__ 発動
        └─► 「新規 registry & metadata」を作成して Base に保持

--------------------------------------------------

【2. models/user.py がインポートされた時】
class User(Base):
    __tablename__ = "users"
    ...
  └─► __init_subclass__ が再び発動！
        └─► 新規作成はせず、Base.registry を取得
        └─► users テーブル定義を作って Base.metadata に登録
        └─► User クラスを Base.registry に登録
```

この流れがあるため、インポートが終わった段階で `Base.metadata.create_all(engine)` を呼ぶだけで、インポートされた全モデルのテーブルが一括でDBに作成できるようになっています。

---

Pythonの言語仕様として、クラスが定義・評価された時点で「クラスオブジェクト（`type` のインスタンス）」がメモリ上に作成されます。

そして、SQLAlchemyのDeclarativeの仕組みによって、その `User` クラスオブジェクトに**テーブル情報やマッピング情報がクラス属性として自動注入されます**。

属性名について細かなアンダースコアのルール（SQLAlchemyの命名規則）を含めて正確に整理すると、以下のようになります。

---

### `User` クラスオブジェクトに生える主な属性

| 属性名 | 型 / 実体 | 役割・内容 |
| :--- | :--- | :--- |
| **`User.__table__`** <br>*(※ `table` ではなく前後に `__`)* | `sqlalchemy.Table` | SQLAlchemy Core のテーブルオブジェクト。DB上の物理テーブル定義。 |
| **`User.__table__.columns`**<br>*(短縮形: `User.__table__.c`)* | `ColumnCollection` | Core レベルのカラム一覧辞書（`User.__table__.c.id` など）。 |
| **`User.metadata`** | `sqlalchemy.MetaData` | `Base` から引き継いだスキーマ全体のメタデータコンテナ。 |
| **`User.registry`** | `sqlalchemy.orm.registry` | `Base` から引き継いだマッピング管理用のレジストリ。 |
| **`User.__mapper__`** | `sqlalchemy.orm.Mapper` | Python の `User` クラスと `User.__table__` を結びつけているマッパー。 |
| **`User.name` や `User.id`** | `InstrumentedAttribute` | 定義した各カラム。単なる値ではなく、SQL式を組み立てるための特殊な記述子（ディスクリプタ）。 |

※ SQLAlchemyでは、ユーザーが独自に定義するカラム名（`table` というカラム名など）と内部属性が衝突しないよう、システム的な属性には **`__table__`** や **`__mapper__`** のようにダンダー（`__`）が付いています。

---

### 実際のコードで確認できる動作

以下のように、`User()` で**1回もインスタンス化しなくても**、クラスオブジェクト自体がこれらの情報を持っています。

```python
from sqlalchemy import String
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column

class Base(DeclarativeBase):
    pass

class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(50))

# --------------------------------------------------
# インスタンス化しなくても、クラスオブジェクトから参照可能
# --------------------------------------------------

# 1. テーブル名やTableオブジェクト
print(User.__table__)          # => users (Tableオブジェクト)
print(User.__table__.name)     # => 'users'

# 2. カラム情報 (Core レベル)
print(User.__table__.columns)  # => ['users.id', 'users.name']
print(User.__table__.c.name)   # => users.name (Columnオブジェクト)

# 3. Metadata
print(User.metadata)           # => MetaData() (Base.metadataと同じインスタンス)
print(User.metadata.tables.keys()) # => dict_keys(['users'])

# 4. クラス属性そのもの（クエリ構築に使われる記述子）
print(User.name == "alice")    # => users.name = :name_1 (二項演算子式オブジェクト)
```

### まとめ
* クラス定義が読み込まれた瞬間に、`User` クラスオブジェクトが生成される。
* その直後にフック（`__init_subclass__`）が走り、Core の `Table` が生成されて `User.__table__` に格納される。
* これにより、`User.__table__.columns` や `User.metadata` など、テーブルやカラムの全容にクラスから直接アクセスできるようになります。


