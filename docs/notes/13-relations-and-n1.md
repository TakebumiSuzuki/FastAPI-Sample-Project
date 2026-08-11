# 13. リレーションと N+1

## 1. 今回学んだこと・理解したポイント

### ① 1対多のリレーション定義（SQLAlchemy 2.0）
- **DB レベル（外部キー）**:
  - `category_id: Mapped[int] = mapped_column(ForeignKey("categories.id"))`
  - `ForeignKey` には Python のクラス名ではなく、**DB のテーブル名（`categories.id`）** を指定する。
- **ORM レベル（相互参照）**:
  - `Category` 側: `items: Mapped[list["Item"]] = relationship(back_populates="category")`
  - `Item` 側: `category: Mapped["Category"] = relationship(back_populates="items")`
  - SQLAlchemy 2.0 では型注釈（`Mapped["Category"]`）から対象モデルが自動推論される。

### ② SQLite と Alembic バッチモードの注意点
- **`ALTER TABLE` の制限**: SQLite は既存テーブルへの制約追加（`ALTER TABLE`）を非サポート。
- **バッチモード (`render_as_batch=True`)**: Alembic はテーブル再作成＋データコピーで迂回する。
- **制約命名規則 (`naming_convention`)**: バッチモード実行時に制約名が `None` だとエラーになるため `Base.metadata` に設定が必須。

### ③ N+1 問題と Eager Loading（`joinedload` / `selectinload`）
- **N+1 問題（Lazy Loading）**: 親取得 SQL 1回 ＋ 関連要素のアクセス毎に子取得 SQL N 回が発行され、DB 負荷が激増する問題。
- **使い分け**:
  - **`joinedload`（推奨: 多対1 / 1対1）**: `Item` -> `Category` のように関連先が1件の場合に使用。`LEFT OUTER JOIN` を使い1回の SQL クエリで一括取得する。
  - **`selectinload`（推奨: 1対多）**: `Category` -> `Items` のように関連先が複数の場合に使用。`WHERE id IN (...)` 句を用いて2回の SQL クエリで効率よく取得する。
- **Eager Loading を忘れた場合の挙動**:
  - 同期セッションではエラーにならず、Pydantic のシリアライズ時に裏で Lazy Load（N+1 クエリ）が走る。

### ④ ネストしたレスポンススキーマと Python の型評価
- **ネスト構造**: `ItemPublic` スキーマ内に `category: CategoryPublic` を指定することで、1つの API レスポンスで親子のネストした JSON 構造を自動返却できる。
- **前方参照（Forward Reference）**: Python は上から順にクラスを評価するため、未定義クラスを参照すると `NameError` になる。文字列（`"CategoryPublic"`）で型注釈を書くことで即時評価を回避し、型定義順序の制約を解除できる（PEP 484 仕様）。

### ⑤ スキーマ設計とバリデーションのポイント
- **`id` を `Base` に入れない理由**: 新規作成時（`ItemCreate`）には ID が存在しないため。
- **`model_config` の継承**: Pydantic v2 では親クラスの `model_config`（`extra="forbid"` 等）が子クラスへ継承（マージ）される。
- **`extra="forbid"` と必須項目**: スキーマにない未知のフィールドが含まれるとエラーを返す。デフォルト値がないフィールドは `extra` の設定に関わらず必須項目（未指定でエラー）。
- **`Field(ge=1)`**: 主キーなどの ID に負の値が入らないよう境界値制約（Greater than or Equal）を付ける。

---

## 2. 進捗状況

### 進捗状況
1. `Category` モデルおよび `Item` モデルへの 1対多リレーション追加完了。
2. マイグレーション作成と反映完了（バッチモード・命名規則適用）。
3. `CategoryPublic` スキーマおよび `ItemPublic` へのネストスキーマ定義完了。
4. CRUD 層での `joinedload` による Eager Loading（N+1問題対策）の実装完了。

第13章「リレーションと N+1」が完了しました！
