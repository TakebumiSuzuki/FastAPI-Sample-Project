from sqlalchemy import MetaData
from sqlalchemy.orm import DeclarativeBase

# 以下の５種類が制約やインデックスの自動命名のための種類として定義されている。
# 順に、Index, UniqueConstraint, CheckConstraint,
# ForeignKeyConstraint, PrimaryKeyConstraint
# これらは、mysql でも postgres でも、カラムオブジェクトとは別に、名前付きの
# オブジェクトとして登録される。デフォルトではこれらの多くの名前はDB側で自動設定される。
# ここでは、以下のように、アプリ側(sqlalchemy側)で名前規則を明示指定している。
# ちなみに、これは、Alembic 公式ドキュメントに載っているものと同一の設定
# 逆に、NOT NULL, VARCHAR(30), name, default などはカラム属性。
naming_convention = {
    "ix": "ix_%(column_0_label)s",
    "uq": "uq_%(table_name)s_%(column_0_name)s",
    "ck": "ck_%(table_name)s_%(constraint_name)s",
    "fk": "fk_%(table_name)s_%(column_0_name)s_%(referred_table_name)s",
    "pk": "pk_%(table_name)s",
}


# 通常は、Base クラスを読み込んだ時点で、クラス変数 metadata として、自動的に
# MetaData インスタンスが生成される。
# しかし、ここでは、naming_convention=naming_convention の引数を入れ、
# デフォルトの MetaData ではなく、独自の命名規則を持った
# MetaData インスタンスを作っている
class Base(DeclarativeBase):
    metadata = MetaData(naming_convention=naming_convention)
