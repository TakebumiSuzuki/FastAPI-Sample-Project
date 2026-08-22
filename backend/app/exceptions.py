from fastapi import HTTPException

# FastAPI の HTTPExceptionが持つ属性は以下の３つ
# self.status_code
# self.detail # 型は Any
# self.headers # 未指定なら None


class ItemNotFound(HTTPException):
    # code はこのクラスそのものと紐づいた値。よってクラス変数として定義する。
    # そして同名のインスタンス変数がないので、この値が self.codeで取り出せる。
    code = "item_not_found"

    def __init__(self, item_id: int):
        super().__init__(status_code=404, detail=f"Item {item_id} not found")
        self.details = {"item_id": item_id}


class ItemNameTaken(HTTPException):
    code = "item_name_taken"

    def __init__(self, name: str):
        super().__init__(status_code=409, detail=f"Item name '{name}' is already used")
        self.details = {"name": name}


class ItemOutOfStock(HTTPException):
    code = "item_out_of_stock"

    def __init__(self, item_id: int):
        super().__init__(status_code=400, detail=f"Item {item_id} is out of stock")
        self.details = {"item_id": item_id}
