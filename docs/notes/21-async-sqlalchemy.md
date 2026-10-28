# 21. 非同期 SQLAlchemy への移行（前半：エンジン・セッション・Alembic・Dependency・CRUD）

## 1. 今回作成・修正したコードの概要（途中経過）

第21章の前半として、DB ドライバと SQLAlchemy のエンジン・セッション・マイグレーション環境（Alembic）・依存性注入（`deps.py`）・CRUD 層（`app/crud/`）の非同期化を実施した。

### 完了した箇所
1. **非同期 SQLite ドライバの導入 (`backend/pyproject.toml`)**
   - `uv add aiosqlite` で `aiosqlite` を追加。
2. **接続 URL とエンジン・セッションの非同期化 (`backend/.env`, `backend/app/core/session.py`)**
   - `DATABASE_URL` を `sqlite:///./app.db` から `sqlite+aiosqlite:///./app.db` に変更。
   - `create_engine` → `create_async_engine`（`sqlalchemy.ext.asyncio`）に変更。
   - `sessionmaker` → `async_sessionmaker`（`sqlalchemy.ext.asyncio`）に変更し、`expire_on_commit=False` を設定。
3. **Alembic の非同期エンジン対応 (`backend/alembic/env.py`)**
   - `engine_from_config` → `async_engine_from_config` に変更。
   - マイグレーション実行本体を同期関数 `do_run_migrations(connection: Connection)` として切り出し、非同期関数 `run_async_migrations_online()` 内の `await connection.run_sync(do_run_migrations)` から呼び出す形に変更。
   - エントリポイントで `asyncio.run(run_async_migrations_online())` を実行。
4. **Dependency の非同期化 (`backend/app/deps.py`)**
   - `get_db_session`: `async def` 化し、戻り値の型注釈を `AsyncGenerator[AsyncSession]` に変更。クローズ処理を `await db_session.close()` に変更。
   - `get_user`: `async def` 化し、`user = await db_session.get(User, id)` に変更。
5. **CRUD 層の非同期化 (`backend/app/crud/category.py`, `item.py`, `user.py`)**
   - 各 CRUD 関数を `async def` 化し、`db_session` の型を `AsyncSession` に変更。
   - `execute()`・`commit()`・`refresh()`・`delete()` に `await` を追加。
   - `create_item` で遅延読み込みエラーを防ぐため `await db_session.refresh(new_item, ["category"])` を追加。

### 次回以降の残りタスク
- **ステップ3**: ルート層の非同期化（`app/routes/categories.py`, `items.py`, `users.py`）
- **ステップ4**: テストの非同期化（`tests/conftest.py` と各テストファイル）

---

## 2. Q&A（学習中の疑問と解決まとめ）

### Q1. `sqlalchemy.ext` の `ext` とはどういう意味か？ 別途インストールが必要か？
**A.**
- `ext` は **extensions（拡張機能）** の略。
- `sqlalchemy` パッケージ本体に最初から同梱されており、内部で必要な `greenlet` ライブラリも `sqlalchemy` の依存関係として自動でインストールされるため、別途インストールする必要はない。

### Q2. `aiosqlite`（ドライバ）と `create_async_engine` / `async_sessionmaker`（SQLAlchemy）では、どちらに「イベントループへ制御を渡すコード」が書かれているのか？
**A.**
- **イベントループへ制御を返す主役は最下層のドライバ（`aiosqlite`）側**。
  - `aiosqlite` の `Connection._execute` 内で `future = asyncio.get_event_loop().create_future()` を作り、`return await future` することで I/O 待ちのあいだイベントループへ制御を返している。
- **SQLAlchemy 側（`AsyncEngine` / `AsyncSession`）は、それを上から下まで `await` で中継する役目**。
  - 内部的には SQLAlchemy の全関数を `async def` で書き直したわけではなく、入口（`AsyncSession.execute` など）と出口（ドライバ呼び出し部分）を `greenlet` で橋渡しして既存の同期ロジックを流用している。

### Q3. 本来の非同期 I/O は1スレッドでタスクを切り替えるだけなのに、なぜ `aiosqlite` は内部で別スレッドを使っているのか？
**A.**
- **本来の非同期 I/O（PostgreSQL の `asyncpg` や HTTP 通信など）は、ネットワークソケットを使うため別スレッドを一切使わず1スレッドだけで動く。**
- 一方、**SQLite は通信相手（DB サーバー）がおらずローカルディスク上のファイルを直接読み書きする仕組み**であり、OS や SQLite 本体にソケットのような非同期イベント通知の仕組みがない。
- そのため、`aiosqlite` は例外的に「裏で専用ワーカースレッドを1つ立てて `sqlite3` のファイル読み書きを代行させ、メインスレッドのイベントループには `Future`（`await`）で制御を返す」という擬似的な仕組みで非同期インターフェースを実現している。

```
[本来の非同期 (PostgreSQL + asyncpg 等)]
メインスレッド (Event Loop) ──(ソケット送信・別タスクへ切替)──> DBサーバー (別プロセス)

[SQLite の非同期 (aiosqlite)]
メインスレッド (Event Loop) ──(Futureで待って別タスクへ切替)──> 裏の専用スレッド (sqlite3ファイル読込)
```

### Q4. `expire_on_commit` はなぜ同期のデフォルトで `True` なのか？ また、なぜ非同期では `True` のまま `select` で取り直すのではなく `False`（手動管理）にするのか？
**A.**
- **デフォルトで `True` な理由（自動管理の利便性）**:
  - コミット時に DB 側のトリガーやデフォルト値で値が変わったり、同じセッションを使い回す間に別トランザクションが DB を書き換えたりして、「Python 側のメモリ上のデータ」と「DB 側の最新データ」がズレるのを防ぐため。`True` にしておけば、コミット後に属性へアクセスした瞬間に自動で再 `SELECT` が走って最新値を取り直してくれる。
- **非同期で `False` にする理由**:
  - 非同期セッション（`AsyncSession`）では `await` なしの暗黙の DB 通信が禁止されているため、期限切れ（expired）の属性に触ると `MissingGreenlet` エラーになる。
  - `True` のまま毎回手動で `select` / `refresh` しても動かすこと自体は可能だが、それをせず `False` にするのは以下の2つの無駄・事故を防ぐため：
    1. **無関係なオブジェクトの巻き添え防止**: `commit()` は更新したオブジェクトだけでなく、**そのセッション内で読み込んだ全オブジェクト**を一斉に期限切れにする（例：ログイン処理で `user` を取得した後に `RefreshToken` を `commit()` すると、無関係な `user` まで期限切れになって触れなくなる）。
    2. **不要な2回目の `SELECT` 通信の削減**: 通常の `INSERT` / `UPDATE` では主キー `id` などは `commit()`（内部の `flush()`）時点で既にメモリ上に入っているため、毎回取り直すのは無駄な DB 往復になる。
  - したがって、「自動の一括 expire はオフ（`expire_on_commit=False`）にし、DB 側で値が変わる可能性がある箇所だけ手動で `await db_session.refresh(obj)` を呼ぶ」という手動管理にするのが定石。

### Q5. FastAPI と Alembic でイベントループの扱いが違う（Alembic 側で `asyncio.run()` が要る）のはなぜか？
**A.**
- **FastAPI**: サーバーである Uvicorn が起動時にイベントループを立ち上げ、そのイベントループ上で FastAPI の `async def` 関数を直接動かす。
- **Alembic**: `alembic` コマンド自体は同期で動く CLI ツールでありイベントループを持っていないため、`alembic/env.py` の最後で `asyncio.run(...)` を呼んで、マイグレーション実行用のイベントループをその場で立ち上げる必要がある。

### Q6. `alembic/env.py` の `async with connectable.connect()` と `await connection.run_sync(do_run_migrations)` は内部で何をしていて、なぜここで同期が出てくるのか？
**A.**
- **`async with connectable.connect() as connection:`**:
  - 単なるメモリ上のオブジェクト取得ではなく、内部でドライバ（`aiosqlite`）を通じて実際に DB への接続を開く I/O が発生するため、ドライバ側でイベントループへ制御を返す処理（`await`）が走る（特に `env.py` では `NullPool` を使うため毎回新規接続が開かれる）。
- **なぜ `connection.run_sync(do_run_migrations)` が必要なのか**:
  - Alembic 本体のマイグレーション実行処理（`context.configure` や `context.run_migrations()`）が非同期（`async/await`）に対応しておらず、**同期の `Connection` しか受け取れない設計**になっているため。
  - `connection.run_sync(関数)` は、「同期専用に書かれた関数に、見た目は同期の `Connection` を渡して動かしつつ、内部で発行される SQL 通信は裏で非同期ドライバへ `await` で橋渡しする」ための変換アダプタとして機能する。

### Q7. `deps.py` の `get_db_session` を `async def` に変えたとき、戻り値の型が `Generator[AsyncSession]` のままだとエラーになるのはなぜか？
**A.**
- 通常の `def` の中で `yield` を使う関数は同期ジェネレータ（`collections.abc.Generator`）を返すが、`async def` の中で `yield` を使う関数は**非同期ジェネレータ（`collections.abc.AsyncGenerator`）**を返すため、型注釈も `AsyncGenerator[AsyncSession]` に合わせる必要がある。


### Q8. `db_session.add()` には `await` が不要なのに、なぜ削除マークを付けるだけの `db_session.delete()` には `await` が必要なのか？
**A.**
- 実際の `DELETE` SQL が発行されるのは `commit()`（内部の `flush()`）の時点であり、「削除予定としてマークする作業」自体はメモリ上の処理である。
- ただし、モデルにカスケード削除（親を消したら関連する子レコードも連動して消す設定）がある場合、まだメモリに読み込まれていない関連レコードを調べるために `delete()` を呼んだ時点で DB へ `SELECT` が走ることがあるため、`AsyncSession.delete()` は `async def`（`await` 必須）として定義されている。

### Q9. `await db_session.refresh()` はデフォルトでリレーション先を取得しないのか？ また、第2引数のリスト（`["category"]`）や `update_item` での挙動はどう違うのか？
**A.**
- **デフォルトの動作（第2引数なし `await db_session.refresh(obj)`）**:
  - 原則として**そのテーブル自身のカラムだけ**を再取得し、通常の（遅延読み込み設定の）リレーション先は取得しない。
  - **例外（`update_item` の `db_item` のケース）**: すでに `get_item_from_id()` の `joinedload(Item.category)` などで**事前読み込み（Eager Load）された履歴があるオブジェクト**に対しては、最初と同じ `JOIN` を使って本体のカラムと一緒にリレーション先（`category`）も再取得してくれる。
  - 一方、`create_item` の `new_item = Item(...)` は Python 上で新規作成しただけで `joinedload` の履歴がないため、第2引数なしの `refresh(new_item)` では `category` が読み込まれず、レスポンス変換時に `MissingGreenlet` エラーになる。
- **第2引数にリストを渡したときの動作（`await db_session.refresh(obj, ["category"])`）**:
  - 「本体のカラムと一緒に」ではなく、**リストに書いた属性（この場合は `category`）だけ**を DB から取得する（本体の他のカラムはすでにメモリ上にある値がそのまま残る）。
  - もし `refresh()` の第2引数だけで全カラム＋リレーションを取り直そうとすると全属性名をリストに列挙する必要があるため、実務で両方まとめて取り直したい場合は `select(...).options(joinedload(...))` でクエリを発行し直す。
  - なお、`update_item` でも「確実に `category` を読み込む」という安全のために `await db_session.refresh(db_item, ["category"])` と書いても問題なく動作する。
