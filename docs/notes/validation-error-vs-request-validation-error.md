# ValidationError と RequestValidationError の違い

## pydantic の ValidationError

```python
[
  {
    "type": "greater_than",
    "loc": ["price"],                # フィールド名から始まる
    "msg": "Input should be greater than 0",
    "input": -1,
    "ctx": {"gt": 0},
    "url": "https://errors.pydantic.dev/2.13/v/greater_than"   # ある
  }
]
```

## RequestValidationError

```python
[
  {
    "type": "int_parsing",
    "loc": ["query", "q"],           # 出所が先頭に付く
    "msg": "Input should be a valid integer, unable to parse string as an integer",
    "input": "abc"
  },
  {
    "type": "greater_than",
    "loc": ["body", "price"],        # 出所が先頭に付く
    "msg": "Input should be greater than 0",
    "input": -1,
    "ctx": {"gt": 0}
                                     # url は無い
  }
]
```

## 違い

どちらも `errors()` で dict のリストが取れ、1件でも `[...]` で囲まれます。違いは3点です。

1. **`loc` の先頭**。pydantic は `["price"]`、RequestValidationError は `["body", "price"]` / `["query", "q"]` と出所が付く。あなたのコードの `error["loc"][1:]` はこれを落とすためのもの。
2. **まとめられる範囲**。pydantic は1つのモデルの結果だけ。RequestValidationError は query と body のエラーを1個の例外にまとめて持つ（上の例は2件で1つのリスト）。
3. **`url` キー**。pydantic にはあり、RequestValidationError には無い。

クラスとしては継承関係がなく、`errors()` は同じ名前で別々に定義された別物です。持っている属性も違い、RequestValidationError だけが `body`（受け取った生のボディ）を持ちます。


---

はい、ご認識の通りです。

Pydanticの `ValidationError` からエラーの詳細なリスト（辞書）を取得するには、プロパティ（`e.errors` のような直接のアクセス）ではなく、**必ず `e.errors()` や `e.json()` といった専用のメソッド（関数）を呼び出す必要があります。**

これらがメソッドとして実装されている（単なるゲッター以上の役割を持っている）のには、主に **2つの重要な理由** があります。

### 1. オプション引数で出力をカスタマイズできるため
`errors()` メソッドや `json()` メソッドは、呼び出し時に引数を渡すことで、取得するエラー情報の中身を動的にコントロールできるように設計されています。

たとえば、Pydantic V2の `errors()` メソッドは以下のような引数（デフォルトはすべて `True`）を取ります。

```python
# input（入力値）や url（ドキュメントURL）を結果に含めないようにする
error_list = e.errors(include_url=False, include_input=False)
```

単に内部のデータを返すだけのプロパティではなく、「指定された条件に合わせてエラー情報のリストを生成して返す」という処理を行っているため、メソッドになっています。

### 2. 内部データからPythonの辞書/JSONへの変換処理を行っているため
Pydantic V2は、パフォーマンスを劇的に向上させるために、コア部分（バリデーションエンジン）が **Rust言語** で書かれています（`pydantic-core` というライブラリ）。

エラーが発生した際、内部的にはRust側の複雑なデータ構造でエラー情報が保持されています。
- `e.errors()` を呼ぶと → Rust側のデータを、Pythonで扱いやすい `list[dict]` に変換（シリアライズ）して返す
- `e.json()` を呼ぶと → Rust側のデータを、直接JSON文字列に変換して返す

つまり、単にPythonクラス内にあるリスト変数を `return` しているわけではなく、**メソッドが呼ばれたタイミングでデータ変換（構築）を行っている**ため、メソッドという形をとっています。

---

### まとめ
*   **プロパティとしてはアクセスできない:** エラーの詳細なリストが格納されている `e.error_list` のようなプロパティは存在しません。
*   **メソッドを使う理由:** 出力のカスタマイズ（URLを含めない等）を可能にし、かつ内部のRustレイヤーからPythonネイティブな型へ変換する処理を伴うためです。

---

ご指摘の通り、**「動的にデータを生成・フォーマットして返す高度なゲッター」** として `errors()` や `json()` が機能していると捉えていただいて間違いありません。


Pydanticでバリデーションエラーが発生した際に送出される `ValidationError` の中身は、**エラーの詳細情報を持つ辞書（dict）のリスト（配列）**という構造になっています。

現在主流の **Pydantic V2** を基準に、エラーオブジェクトから `e.errors()` メソッドで取得できるリストの中身（各辞書の構造）を解説します。

### エラー詳細辞書の基本構造（各キーの意味）

1つのエラーにつき、以下のようなキーを持つ辞書が生成されます。

| キー | 型 | 説明 |
| :--- | :--- | :--- |
| **`loc`** | `tuple[str \| int, ...]` | **エラーの発生場所（Location）**。<br>どのフィールドでエラーが起きたかを示します。ネストされたモデルやリストの場合は `('users', 0, 'age')` のように階層構造になります。 |
| **`msg`** | `str` | **エラーメッセージ**。<br>人間に読める形式のメッセージです（例: `"Input should be a valid integer"`）。 |
| **`type`** | `str` | **エラーの種類（識別子）**。<br>プログラムでエラーを判別する際に使います（例: `"int_parsing"`, `"missing"`, `"greater_than"` など）。 |
| **`input`** | `Any` | **エラーの原因となった実際の入力値**。<br>（※Pydantic V2からの新機能です） |
| **`ctx`** | `dict[str, Any]` | **コンテキスト（付加情報）** ※オプション<br>バリデーションの条件などの追加情報が含まれます。例えば「〇〇以上であること」というエラーの場合、`{'gt': 0}` のように条件値が入ります。 |
| **`url`** | `str` | **エラー詳細の公式ドキュメントURL** ※オプション<br>このエラーについて詳しく知るためのPydantic公式ページへのリンクです。（※Pydantic V2からの新機能） |

---

### 具体的な構造の例

実際にエラーを発生させて、構造を確認してみましょう。

#### サンプルコード
```python
from pydantic import BaseModel, Field, ValidationError

class User(BaseModel):
    name: str
    age: int = Field(gt=0) # 0より大きい整数

# わざとエラーになるデータを渡す
try:
    User(name=["Taro"], age=-5) # nameにリスト、ageにマイナスの値を渡す
except ValidationError as e:
    # エラーの構造をリスト（辞書）で取得して表示
    import json
    print(json.dumps(e.errors(), indent=2, ensure_ascii=False))
```

#### 出力されるエラー構造の中身（JSON）
上記を実行すると、以下のような構造のデータが取得できます。

```json
[
  {
    "type": "string_type",
    "loc": [
      "name"
    ],
    "msg": "Input should be a valid string",
    "input": [
      "Taro"
    ],
    "url": "https://errors.pydantic.dev/2.x/v/string_type"
  },
  {
    "type": "greater_than",
    "loc": [
      "age"
    ],
    "msg": "Input should be greater than 0",
    "ctx": {
      "gt": 0
    },
    "input": -5,
    "url": "https://errors.pydantic.dev/2.x/v/greater_than"
  }
]
```

### 補足: エラー情報の取得方法
- **Pythonの辞書のリストとして取得したい場合:** `e.errors()`
- **JSON文字列として直接取得したい場合:** `e.json()` （APIのレスポンスとしてそのまま返す時などに便利です）

※もし Pydantic V1 をお使いの場合は、`input` と `url` キーは存在せず、`loc`, `msg`, `type` (, `ctx`) のみを持つ構造となります。

---


おっしゃる通り、**入れ子になっていない（フラットな）Pydanticモデルの場合は、基本的に要素が一つだけのタプル**になります。（例: `('name',)` や `('age',)`）

ただし、後半の「入れ子になっている（ネストされたモデルの）場合**だけ**複数の要素のタプルになるの？」という点については、**答えは「No（それだけではない）」**です。

モデルが入れ子になっている場合だけでなく、**リスト（配列）や辞書（Dict）などのコレクション型が含まれている場合**にも、どの要素でエラーが起きたかを特定するために複数の要素を持つタプルになります。

`loc` は、エラーが発生した場所までの**「パス（経路）」**を表していると考えると分かりやすいです。

階層が深くなって要素が複数になる主なパターンを3つ紹介します。

### 1. Pydanticモデルが入れ子（ネスト）になっている場合
別のモデルをフィールドとして持っているパターンです。

```python
class Address(BaseModel):
    city: str

class User(BaseModel):
    address: Address

# addressの中のcityでエラーが発生した場合
# loc: ('address', 'city')
```

### 2. リスト（List）やタプル（Tuple）などの場合
リストの中の特定の要素でエラーが起きた場合は、**リストのインデックス番号（整数）**が追加されます。

```python
class User(BaseModel):
    tags: list[int]

# tagsの2番目（インデックス1）の要素に文字列を渡してエラーになった場合
# User(tags=[10, "文字列", 30])
# loc: ('tags', 1)  ← 1はインデックス番号
```

### 3. 辞書（Dict）の場合
辞書のバリュー（値）でエラーが起きた場合は、**辞書のキー（文字列など）**が追加されます。

```python
class User(BaseModel):
    scores: dict[str, int]

# scoresの 'math' キーの値に文字列を渡してエラーになった場合
# User(scores={"english": 80, "math": "欠席"})
# loc: ('scores', 'math')
```

---

### さらに複雑な組み合わせの場合
これらが組み合わさると、タプルの要素はどんどん長くなっていきます。

例えば、「Userモデル」が「Addressモデル」の「リスト」を持っている場合で、2番目のAddressのcityでエラーが起きたとします。
```python
# loc: ('addresses', 1, 'city')
```
このように、`loc` のタプルを最初から順番にたどっていくことで、**「どのフィールドの、何番目の要素の、どのプロパティでエラーが起きたのか」**をプログラム的に正確に特定できるようになっています。
