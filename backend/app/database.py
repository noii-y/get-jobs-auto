"""数据库连接与初始化"""
import logging
from sqlalchemy import create_engine, inspect, text
from sqlalchemy.orm import sessionmaker, declarative_base
from app.config import settings

logger = logging.getLogger(__name__)

engine = create_engine(
    settings.database_url,
    connect_args={"check_same_thread": False},  # SQLite多线程支持
    echo=settings.debug,
)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()


def get_db():
    """获取数据库会话（依赖注入用）"""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def auto_migrate():
    """自动迁移：检测并补全缺失的表和列

    对于个人项目足够用：
    - 表不存在 → 自动创建
    - 表存在但缺少列 → 自动 ALTER TABLE ADD COLUMN
    - 列已存在 → 跳过（不修改类型，不删除列）
    """
    from app import models  # noqa: F401 确保模型被注册

    inspector = inspect(engine)
    existing_tables = inspector.get_table_names()

    for table_name, table in Base.metadata.tables.items():
        if table_name not in existing_tables:
            # 表不存在，create_all 会创建
            continue

        # 表存在，检查缺失的列
        existing_columns = {col["name"] for col in inspector.get_columns(table_name)}
        model_columns = {col.name: col for col in table.columns}

        for col_name, col in model_columns.items():
            if col_name not in existing_columns:
                # 拼接列定义
                col_type = col.type.compile(dialect=engine.dialect)
                nullable = "NULL" if col.nullable else "NOT NULL"
                default = ""
                if col.default is not None:
                    default_val = col.default.arg
                    if isinstance(default_val, str):
                        default = f" DEFAULT '{default_val}'"
                    else:
                        default = f" DEFAULT {default_val}"

                sql = f"ALTER TABLE {table_name} ADD COLUMN {col_name} {col_type} {nullable}{default}"
                logger.info(f"自动迁移: {sql}")
                try:
                    with engine.connect() as conn:
                        conn.execute(text(sql))
                        conn.commit()
                except Exception as e:
                    logger.warning(f"自动迁移列 {table_name}.{col_name} 失败: {e}")


def init_db():
    """初始化数据库表（含自动迁移）"""
    from app import models  # noqa: F401 确保模型被注册
    Base.metadata.create_all(bind=engine)
    auto_migrate()
