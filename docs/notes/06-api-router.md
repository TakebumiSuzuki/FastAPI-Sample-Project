# 06. APIRouter でファイル分割

## 学んだこと
- `APIRouter` を使うことで、エンドポイントが増えても `main.py` を薄く保てる。
- `router = APIRouter(prefix="/items", tags=["items"])` のようにルーター側に prefix や tags を設定すると、ファイル単体で共通パスやドキュメント分類が分かりやすくなる。
- `app.include_router(router)` で親の FastAPI インスタンスにまとめて登録できる。

## 作成・変更したファイル
- `backend/app/routes/items.py`: items 関連のエンドポイントと例外を分離
- `backend/main.py`: `include_router` を使って登録する形にスリム化
