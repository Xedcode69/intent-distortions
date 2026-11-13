from alembic import context
from sqlalchemy import create_engine
from app.config import settings
from app.database import Base

config=context.config
if context.is_offline_mode():
    context.configure(url=settings.database_url,target_metadata=Base.metadata,literal_binds=True)
    with context.begin_transaction():context.run_migrations()
else:
    url=settings.database_url.replace("postgresql://","postgresql+psycopg://",1)
    with create_engine(url).connect() as connection:
        context.configure(connection=connection,target_metadata=Base.metadata)
        with context.begin_transaction():context.run_migrations()
