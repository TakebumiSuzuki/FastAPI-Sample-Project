from logging.config import fileConfig

from sqlalchemy import engine_from_config, pool

from alembic import context
from app.core.config import get_settings
from app.models.base import Base

# this is the Alembic Config object, which provides
# access to the values within the .ini file in use.
config = context.config

# Interpret the config file for Python logging.
# This line sets up loggers basically.

# config.config_file_name は Config オブジェクトの属性で、
# CLI（alembic コマンド）で実行時は "alembic.ini" がデフォルト値
# つまり、ここでは "alembic.ini" にかいてあるロガー設定を読み込んでいる。
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# add your model's MetaData object here
# for 'autogenerate' support
# from myapp import mymodel
# target_metadata = mymodel.Base.metadata
target_metadata = Base.metadata

# other values from the config, defined by the needs of env.py,
# can be acquired:
# my_important_option = config.get_main_option("my_important_option")
# ... etc.

config.set_main_option(
    "sqlalchemy.url",
    get_settings().database_url.replace("+aiosqlite", ""),
)


def run_migrations_offline() -> None:
    """Run migrations in 'offline' mode.

    This configures the context with just a URL
    and not an Engine, though an Engine is acceptable
    here as well.  By skipping the Engine creation
    we don't even need a DBAPI to be available.

    Calls to context.execute() here emit the given string to the
    script output.

    """
    url = config.get_main_option("sqlalchemy.url")
    context.configure(
        render_as_batch=True,
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )

    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    """Run migrations in 'online' mode.

    In this scenario we need to create an Engine
    and associate a connection with the context.

    """
    # conncectable はエンジンそのもの。Alembic のテンプレートが .connect() を呼べる対象
    # という意味で connectable という変数名をつけていル。
    connectable = engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        # スロットなし（毎回その場で新規接続） ──> 終わったら即座に切断（close）して捨てる、つまり、
        # 接続を保管・再利用しないタイプの Pool オブジェクトを使う設定
        poolclass=pool.NullPool,
    )
    # NullPool（プールせず毎回新規接続する設定）を使っているため、with に入るたびに「実際に DB ファイル（または DB サーバー）へ接続を開く I/O」が発生し、ブロックを抜けると即座に切断されます。
    with connectable.connect() as connection:
        # Alembic 本体（context.run_migrations() の内部）は「同期の Connection を使ってそのまま SQL を実行する」作りになっているため、取得した connection を直接渡して実行します。
        context.configure(
            # render_as_batch は、SQLite用の設定
            render_as_batch=True,
            connection=connection,
            target_metadata=target_metadata,
        )

        # Session のように別階層の SessionTransaction が作られるわけではなく、トランザクションの
        # 実体は Connection 側の RootTransaction のみ（connection.begin() 等で取得し、context 側は
        # それを中継する薄いラッパー _ProxyTransaction を with に返しているだけ）。
        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
