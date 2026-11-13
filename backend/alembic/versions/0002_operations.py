"""Durable releases, collection observations, side effects and event receipts."""
from alembic import op
import sqlalchemy as sa
revision="0002"
down_revision="0001"
branch_labels=None
depends_on=None

def upgrade():
    op.create_table("protocol_config",sa.Column("id",sa.String(64),primary_key=True),sa.Column("commitment",sa.String(64),nullable=False),sa.Column("payload",sa.JSON,nullable=False))
    op.create_table("weekly_releases",sa.Column("number",sa.Integer,primary_key=True),sa.Column("sunday",sa.BigInteger,unique=True,nullable=False),sa.Column("freeze_at",sa.BigInteger,nullable=False),sa.Column("state",sa.String(32),nullable=False,index=True),sa.Column("payload",sa.JSON,nullable=False),sa.Column("error",sa.String(80)),sa.Column("updated_at",sa.BigInteger,nullable=False))
    op.create_table("collection_observations",sa.Column("id",sa.Integer,primary_key=True),sa.Column("release_number",sa.Integer,sa.ForeignKey("weekly_releases.number"),nullable=False,index=True),sa.Column("started_at",sa.BigInteger,nullable=False),sa.Column("completed_at",sa.BigInteger,nullable=False),sa.Column("snapshot_hash",sa.String(64),nullable=False),sa.Column("evidence",sa.JSON,nullable=False))
    op.create_table("chain_effects",sa.Column("key",sa.String(160),primary_key=True),sa.Column("account",sa.String(64),nullable=False),sa.Column("contract",sa.String(64),nullable=False),sa.Column("method",sa.String(64),nullable=False),sa.Column("args_hash",sa.String(64),nullable=False),sa.Column("state",sa.String(24),nullable=False),sa.Column("signed_transaction",sa.Text,nullable=False),sa.Column("transaction_hash",sa.String(64),nullable=False,unique=True),sa.Column("created_at",sa.BigInteger,nullable=False),sa.Column("payload",sa.JSON,nullable=False))
    op.create_table("chain_events",sa.Column("key",sa.String(160),primary_key=True),sa.Column("transaction_hash",sa.String(64),nullable=False),sa.Column("receipt_id",sa.String(64),nullable=False),sa.Column("contract",sa.String(64),nullable=False,index=True),sa.Column("token_id",sa.String(80),index=True),sa.Column("kind",sa.String(32),nullable=False,index=True),sa.Column("payload",sa.JSON,nullable=False),sa.Column("block_height",sa.BigInteger,nullable=False),sa.Column("timestamp_ns",sa.String(32),nullable=False))

def downgrade():
    for name in ["chain_events","chain_effects","collection_observations","weekly_releases","protocol_config"]:op.drop_table(name)
