# 17. ユーザー登録とパスワードハッシュ（前半）

## 1. 今回作成した環境・コードの概要

第17章の前半として、パスワードの安全なハッシュ化の仕組み理解から、ライブラリ選定、DB モデル・スキーマ定義、および TDD による「失敗するテスト（Red）」の作成までを完了した。

### 1. ハッシュライブラリの選定と導入
- `pwdlib` はパスワードのハッシュ化と照合を扱うライブラ
- `pwdlib[argon2]` を `uv add` でインストール。Argon2id は、現在のパスワード保存で第一候補になる方式。
- `Python`には、`hashlib`というハッシュを扱う標準モジュールがあるが、`Argon2`を扱うことができないため、`pwdlib`を使う

### 2. セキュリティ共通モジュール (`backend/app/core/security.py`)
- `from pwdlib import PasswordHash` の後、`password_hash = PasswordHash.recommended()` をモジュールレベルで1度だけ生成（Python のモジュール仕様によるシングルトン化）。
- `password_hash.hash(password)`: 平文パスワードを受け取り、内部でソルトの自動生成・結合・Argon2id ハッシュ計算を行った約97文字の文字列を返す。
- `password_hash.verify(plain_password, hashed_password)`: 平文パスワードと DB 内のハッシュ文字列を照合し、一致判定を返す。

ソルトについて：
- なぜ必要？ ハッシュは逆算できなくても、候補のパスワードを決めうちし、次々にハッシュ化し、保存された値と比較することで推測できる。
- 何なの？ ハッシュ化のたびに自動生成されるランダムなデータです。保存時には文字列で表されます。
- どこに保存？ 返される約97文字の中に含まれ、ハッシュ値と一緒に DB に保存されます。秘密にする必要はなく、照合時に再利用されます。

### 3. User モデル (`backend/app/models/user.py`)
- `User(Base)` を作成: `id` (PK), `email` (一意制約), `hashed_password` (平文保存用カラムは作らない)。
- `hashed_password` は Argon2id の実測長（97文字）を収めるため `String(128)` で定義。

### 4. Pydantic スキーマ (`backend/app/schemas.py`)
- `UserCreate`: `email: EmailStr`, `password: str = Field(min_length=8, max_length=255)`, `extra="forbid"`。
- `UserPublic`: `id: int`, `email: EmailStr`, `model_config = ConfigDict(from_attributes=True)`。
- **重要設計**: パスワード漏洩を絶対に防ぐため、レスポンス用の `UserPublic` には平文・ハッシュ値を問わずパスワードフィールドを一切含めない。

### 5. ユーザー登録テストの作成 (Red) (`backend/tests/test_users.py`)
- `test_register_user`:
  - API レスポンス検証: ステータス 201、レスポンスに `password` / `hashed_password` が含まれないこと。
  - DB 検証: `db_session` を使い、保存された `hashed_password` が平文でないこと、および `verify_password()` で照合可能であることを検証。


## 2. Q&A (学習中の疑問と解決まとめ)

### Q1. ソルト（salt）はハッシュ化する前にパスワードに加えるもの？何のために加える？
**A.** その通り。ハッシュ計算の直前にパスワードへ結合する。同じパスワードでも人ごとに異なるハッシュ値になるようにし、レインボーテーブル攻撃（事前計算された対照表を用いた逆引き）を防ぐために考案された。

### Q2. ソルトは安全性を保つために定期的に変更するもの？
**A.** 変更しない。ログイン照合時には「登録時と同じソルト」を入力パスワードにくっつけて再計算する必要があるため、ソルトを変えると認証不能になる。ユーザーごとの登録時に一度生成され、DB に固定保存される（パスワード再設定時のみ新しくなる）。

### Q3. ソルトの文字列はどこに何文字で保存される？自前で生成・連結するの？
**A.** ハッシュ値と一体化した1本の文字列（bcryptなら22文字ソルト+31文字ハッシュ=計60文字、Argon2idなら計約97文字）として DB の同じカラムに保存される。`pwdlib` が暗号学的に安全な乱数によるソルト生成、結合、保存用文字列の生成、照合時のソルト抽出まで全自動で行うため、自前で処理コードを書く必要はない。

### Q4. Python でパスワードハッシュを扱う場合、現代は `pwdlib` が標準？
**A.** Python 全体というより、現代の FastAPI エコシステムにおける公式推奨の標準。長年デファクトだった `passlib` がメンテナンス停止により Python 3.13 等で動かなくなったため、FastAPI 公式チュートリアルが後継として `pwdlib`（内部で最新の Argon2id を使用）を全面採用した。

### Q5. `password_hash = PasswordHash.recommended()` はシングルトン？
**A.** その通り。Python のモジュール読み込み（`sys.modules` キャッシュ）により、初回 import 時に1度だけ生成されアプリ全体で共有される。関数呼び出しごとにインスタンスを作り直すオーバーヘッドを防ぐ定石パターン。

### Q6. User モデルの `hashed_password` はなぜ `String(90)` ではダメだった？
**A.** `pwdlib`（Argon2id）が生成するハッシュ文字列の実測値が約97文字だったため。90文字では桁あふれ（DB の文字数上限超過エラー）になる。最低128文字（通常は余裕を持って255文字）が必要。

### Q7. `alembic revision --autogenerate` で「Target database is not up to date」が出た原因は？
**A.** DB 側に未適用の過去マイグレーションが存在したため。Alembic の `--autogenerate` は「最新状態の DB」と「Python の models」の差分を比較する仕組みのため、DB 側が古いと差分が取れずエラーになる。

### Q8. `EmailStr` を使うには別途インストールが必要？
**A.** 不要。`fastapi[standard]` を導入した時点で、依存関係として `email-validator` が既にインストールされているため、`from pydantic import EmailStr` でそのまま使える。

### Q9. Pylance で `response.status_code` が認識されなかった原因は？バージョンが古い？
**A.** 古いわけではなく最新（Starlette 1.3.1）。Starlette 内部の型定義が `if TYPE_CHECKING: import httpx2 as httpx` となっており、未インストールの `httpx2` を参照しているため Pylance 上で型解決できず `Any` になっていただけ。実行時は通常の `httpx` で問題なく動作する。
