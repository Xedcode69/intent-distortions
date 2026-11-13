"""Immutable epoch/artwork/job foundation."""
from alembic import op
from sqlalchemy import Column,Table,MetaData,String,Integer,JSON,Text,ForeignKey,UniqueConstraint
revision="0001"
down_revision=None
branch_labels=None
depends_on=None

def schema():
    m=MetaData()
    Table("epochs",m,Column("id",String(80),primary_key=True),Column("number",Integer,nullable=False),Column("mode",String(24),nullable=False),Column("status",String(32),nullable=False),Column("start",Integer,nullable=False),Column("end",Integer,nullable=False),Column("payload",JSON,nullable=False),UniqueConstraint("mode","number"))
    Table("artworks",m,Column("id",String(80),primary_key=True),Column("epoch_id",ForeignKey("epochs.id"),unique=True,nullable=False),Column("image_hash",String(64),unique=True,nullable=False),Column("payload",JSON,nullable=False))
    Table("epoch_transactions",m,Column("id",Integer,primary_key=True),Column("epoch_id",ForeignKey("epochs.id"),nullable=False),Column("record_key",String(64),nullable=False),Column("position",Integer,nullable=False),Column("record",JSON,nullable=False),UniqueConstraint("epoch_id","position"),UniqueConstraint("epoch_id","record_key"))
    Table("intents_swaps",m,Column("key",String(64),primary_key=True),Column("created_at_unix",Integer,index=True,nullable=False),Column("status",String(32),index=True,nullable=False),Column("normalized",JSON,nullable=False),Column("last_verified_at",Integer,nullable=False))
    Table("pipeline_jobs",m,Column("key",String(160),primary_key=True),Column("kind",String(64),nullable=False),Column("status",String(24),index=True,nullable=False),Column("attempts",Integer,nullable=False),Column("updated_at",Integer,nullable=False),Column("error",Text),Column("payload",JSON,nullable=False))
    return m

def upgrade():schema().create_all(op.get_bind())
def downgrade():schema().drop_all(op.get_bind())
