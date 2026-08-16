from fastapi import HTTPException


class ItemNotFound(HTTPException):
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
