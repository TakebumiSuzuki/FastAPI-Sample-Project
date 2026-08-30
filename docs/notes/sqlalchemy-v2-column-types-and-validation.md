# SQLAlchemy 2.0 のカラム定義・型推論・実行時エラー

SQLAlchemy 2.0 におけるカラム定義の型情報の役割、型推論の仕組み、および実行時における型検証・エラーの発生タイミングについてのまとめ。

---

## 1. カラム定義における左辺と右辺の役割

SQLAlchemy 2.0 では、左辺の Python 型注釈を **SSOT（信頼できる唯一の情報源）** として扱い、右辺には Python 型だけでは表現できない DB の物理制約のみを記述する。

```text
[左辺: Python型 (Mapped[T])] ──(自動推論)──> [右辺: DB側のカラム設定 (mapped_column)]
  ・エディタ補完・静的型検査                    ・主キー (primary_key=True)
  ・型推論の基準 (SSOT)                         ・NULL許容 / 既定値 (server_default)
                                               ・物理的な長さ・精度 (String(50), Numeric(10, 2))
```

### 役割分担

| 記述箇所 | 役割 | 主な指定項目 |
|---|---|---|
| 左辺 (`Mapped[T]`) | Python 側の型注釈・型推論の入力 | 型（`int`, `str`, `datetime` 等）、NULL 許容（`T | None`） |
| 右辺 (`mapped_column()`) | DB スキーマ定義・物理制約 | `primary_key`, `ForeignKey`, `unique`, `server_default`, 物理型指定 |

- **基本原則**: 右辺の型指定は原則省略し、左辺の型から自動推論させる。
- **右辺に型を書くケース**: 文字数制限（`String(50)`）や小数の精度（`Numeric(10, 2)`）、特定の DB 型（`BigInteger`）など、Python の型表現を超える物理制約が必要な場合のみ指定する。

---

## 2. 型推論の仕組みと集約（`Annotated` + `type_annotation_map`）

### 推論の解決順序

1. `Mapped[X]` から `Optional` / `| None` を剥がして基本型を取り出す（`| None` があれば nullable=True、なければ NOT NULL）。
2. `Base` クラスに定義された `type_annotation_map`（カスタム対応表）を検索する。
3. なければ SQLAlchemy デフォルトの対応表（`int` → `Integer`, `str` → `String` 等）で解決する。
4. ※ 右辺の `mapped_column(Type)` で型が明示された場合は、右辺が優先される。

### 型定義の集約

プロジェクト全体で共通する制約（例: 50文字の文字列、タイムゾーン付き日時）は、`Annotated` と `type_annotation_map` で集約する。

```python
from datetime import datetime
from typing import Annotated
from sqlalchemy import String, TIMESTAMP, func
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column

str50 = Annotated[str, 50]

class Base(DeclarativeBase):
    type_annotation_map = {
        str50: String(50),
        datetime: TIMESTAMP(timezone=True),
    }

class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str50]                  # VARCHAR(50) NOT NULL
    email: Mapped[str50 | None]          # VARCHAR(50) NULL
    created_at: Mapped[datetime] = mapped_column(server_default=func.now())
```

---

## 3. 実行時の型検証とエラー発生の仕組み

### 代入時は検証されない

Python の型注釈は実行時には強制力を持たず、モデル属性への代入（例: `user.flag = "invalid"`）時点ではエラーにならない。
検証や型変換が実行されるのは、**`flush()`（`commit()` を含む SQL 発行時）** のタイミングとなる。

### エラーの種類と発生場所

```text
[属性代入: user.val = x]
      │ (代入時は素通り)
      ▼
[flush() / commit() 呼び出し]
      │
      ├─① bind_processor による変換処理 (SQLAlchemy 側)
      │     └─ 変換失敗 ──> StatementError (ValueError / TypeError をラップ)
      │
      ▼ (DB へ SQL 送信)
[DB エンジンでの実行]
      ├─② DB 側の型不整合 ──> DataError / ProgrammingError
      └─③ 制約違反 (NOT NULL / UNIQUE / FK / CHECK) ──> IntegrityError
```

| 例外の種類 | 発生フェーズ | 主な原因 |
|---|---|---|
| `StatementError` | SQLAlchemy（Python 側） | `bind_processor` での型変換失敗（例: `Float` に `"abc"` を代入） |
| `DataError` / `ProgrammingError` | データベース側 | DB が受け付けない値・型（例: `Integer` に変換不能な文字列が到達） |
| `IntegrityError` | データベース側 | 制約違反（NOT NULL 違反、主キー/ユニーク重複、外部キー違反） |

※ 型の取り違え自体は `IntegrityError` ではなく、`StatementError` または `DataError` になる点に注意する。
