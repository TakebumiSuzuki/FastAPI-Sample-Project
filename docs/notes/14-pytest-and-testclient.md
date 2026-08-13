# 14. pytest と TestClient の基礎

## 1. TDD（テスト駆動開発）の基本概念
TDD（Test-Driven Development）は「プロダクトコードを書く前に、まずテストコードを書く」開発手法。

### 3つのサイクル（Red → Green → Refactor）
1. 🔴 **Red（失敗）**: 実装したい機能の「仕様」を定義するテストコードを先に書く（未実装なので失敗する）。
2. 🟢 **Green（成功）**: テストを通過させるための必要最小限のコードを書く。
3. 🔵 **Refactor（改善）**: テストが成功した状態を保ったまま、コードをキレイにリファクタリングする。

---

## 2. テストの対象選定（何をテストし、何をテストしないか）

- **テストするもの（〇）**:
  - 自作したビジネスロジックや計算処理
  - APIエンドポイントの振る舞い（レスポンスコード、JSONボディ、ヘッダー）
  - バリデーションエラーやカスタムエラーハンドラーの挙動
- **テストしないもの（×）**:
  - FastAPI, Pydantic, SQLAlchemy などのフレームワーク自体の内部機能
  - 単純な定数定義や、自明すぎる処理

---

## 3. Q&A（学習中の疑問と解決まとめ）

### Q1. エンドポイント、Schema、Error Handler などがある中で、どの単位でテストを書くべき？
**A.** FastAPIでは **「1つのエンドポイント（機能）単位で、`TestClient` を使った統合テストを書く」** のが主軸。
`TestClient` でリクエストを送信することで、以下を一括検証できるため効率的：
- Pydantic Schema（バリデーションやレスポンス型）
- エンドポイント関数（ステータスコードやレスポンス）
- Error Handler（例外発生時のステータスコードとエラーメッセージ）
- DB / CRUD 処理（データが正常に保存・更新されたか）

---

### Q2. Flask では `pytest-flask` が必要だったのに、FastAPI ではなぜ不要？
**A.** **Flaskのプロキシ構造（コンテキスト）** が理由。
- Flaskは `request` や `g` がスレッドローカルコンテキストに依存しており、テスト実行時に `app_context` がないとエラーになる。`pytest-flask` はそのセットアップを自動化するプラグイン。
- FastAPI（Starlette）はコンテキスト依存がなく、公式に `from fastapi.testclient import TestClient` が用意されているため追加プラグインが不要。

---

### Q3. `TestClient` は HTTP 通信をせずに直接関数を叩く感じ？
**A.** **その通り（インメモリ実行）。**
- `client.get("/ path")` と HTTP リクエスト形式で記述するが、TCP/IP ソケットを開いてネットワーク通信を行うわけではない。
- FastAPI（ASGI アプリ）を直接インメモリで呼び出すため、**爆速で動作し、ポート衝突も起きない**。
- 一方で、URLルーティング、Pydanticバリデーション、Depends（依存性注入）などは本番と全く同じパスを通過する。

---

### Q4. `from main import app` で `ModuleNotFoundError: No module named 'main'` になったのはなぜ？
**A.** `pytest` コマンド実行時、**カレント作業ディレクトリ（CWD）が自動で Python の `sys.path` に入らない** ため。
- 通常の `python` コマンド実行時は CWD が `sys.path` に追加されるが、`pytest` 単体で実行するとルート判定により手前のフォルダが対象外になることがある。
- `python -m pytest` だと Python 経由になるため通る。

---

### Q5. `pyproject.toml` に `pythonpath = ["."]` と書く意味は？
**A.** `pytest` に対して「プロジェクトルート（`.`）を `sys.path` に含めてね」と教える設定。
- **相対パス `.` の意味**: `pyproject.toml` があるディレクトリを自動的に絶対パスに解決するため、どの開発者の環境や CI/CD でも移植性が高い。
- **有効範囲**: `pytest` 実行中のみ一時的に有効。OS の環境変数を汚さず、安全にカプセル化される。

---

## 4. 今回作成・テストしたコード

### `backend/pyproject.toml` （設定追加）
```toml
[tool.pytest.ini_options]
pythonpath = ["."]
```

### `backend/tests/test_demo.py`
```python
from fastapi.testclient import TestClient 
from main import app 

client = TestClient(app) 

def test_read_root():
    response = client.get("/")
    assert response.status_code == 200
    data = response.json()
    assert "message" in data
    assert data["message"] == "Hello, FastAPI!"
```

### 実行コマンド
```bash
uv run pytest
```

---

## 5. 次回進める内容
- `pytest` の `fixture` 機構を使ったテストクライアントの共通化（`conftest.py`）
- テスト用データベース（In-memory SQLite など）のセットアップと DB テスト（CRUD/エンドポイント）
