from sqlalchemy import MetaData
from sqlalchemy.orm import DeclarativeBase

# 以下の５種類が制約やインデックスの自動命名のための種類として定義されている。
# 順に、Index, UniqueConstraint, CheckConstraint,
# ForeignKeyConstraint, PrimaryKeyConstraint
# これらは、mysql でも postgres でも、カラムオブジェクトとは別に、名前付きの
# オブジェクトとして登録される。デフォルトではこれらの多くの名前はDB側で自動設定される。
# ここでは、以下のように、アプリ側(sqlalchemy側)で命名規則を明示指定している。
# 一方、NOT NULL, VARCHAR(30), name, DEFAULT などはカラム属性。
# また、pkについては、複数のカラムを組み合わせることができるが、その組み合わせ一つが上限。
# これらのルールで作られた名前が DDLの SQL の中で使われ、DBに送られることになる。
naming_convention = {
    "ix": "ix_%(table_name)s_%(column_0_N_name)s",
    "uq": "uq_%(table_name)s_%(column_0_N_name)s",
    "ck": "ck_%(table_name)s_%(constraint_name)s",
    "fk": "fk_%(table_name)s_%(column_0_N_name)s_%(referred_table_name)s",
    "pk": "pk_%(table_name)s",
}


# DeclarativeBase にある、__init_subclass__ の働きで、直接のサブクラスの場合のみ、
# クラス変数 metadata として、自動的に 空の MetaData インスタンスが生成される。または、
# この例のようにすでに metadata がある場合にはそれをそのまま使うというという挙動をする。
class Base(DeclarativeBase):
    metadata = MetaData(naming_convention=naming_convention)
