"""Create Wallet schema and append-only ledger guard."""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "0001_wallet_schema"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "accounts",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("owner_type", sa.String(10), nullable=False),
        sa.Column("owner_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("balance_minor", sa.BigInteger(), nullable=False, server_default="0"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.UniqueConstraint("owner_type", "owner_id", name="uq_account_owner"),
        sa.CheckConstraint("owner_type IN ('USER','PLATFORM')", name="ck_account_owner_type"),
    )
    op.create_table(
        "ledger_entries",
        sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column("tx_group_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("account_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("accounts.id"), nullable=False),
        sa.Column("direction", sa.String(6), nullable=False),
        sa.Column("amount_minor", sa.BigInteger(), nullable=False),
        sa.Column("reason", sa.String(40), nullable=False),
        sa.Column("ref_type", sa.String(20)),
        sa.Column("ref_id", sa.String(64)),
        sa.Column("correlation_id", sa.String(64)),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.CheckConstraint("amount_minor >= 0", name="ck_ledger_amount_nonnegative"),
        sa.CheckConstraint("direction IN ('DEBIT','CREDIT')", name="ck_ledger_direction"),
    )
    op.create_index("ix_ledger_account", "ledger_entries", ["account_id", "created_at"])
    op.create_index("ix_ledger_group", "ledger_entries", ["tx_group_id"])
    op.create_table(
        "gift_cards",
        sa.Column("code", sa.String(32), primary_key=True),
        sa.Column("amount_minor", sa.BigInteger(), nullable=False),
        sa.Column("redeemed_by", postgresql.UUID(as_uuid=True)),
        sa.Column("redeemed_at", sa.DateTime(timezone=True)),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.CheckConstraint("amount_minor > 0", name="ck_giftcard_amount_positive"),
    )
    op.create_table(
        "topups",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("amount_minor", sa.BigInteger(), nullable=False),
        sa.Column("status", sa.String(15), nullable=False, server_default="PENDING"),
        sa.Column("psp_payment_id", sa.String(64), unique=True),
        sa.Column("redirect_url", sa.String(500)),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.CheckConstraint("amount_minor > 0", name="ck_topup_amount_positive"),
        sa.CheckConstraint("status IN ('PENDING','SUCCEEDED','FAILED')", name="ck_topup_status"),
    )
    op.create_table(
        "idempotency_keys",
        sa.Column("key", sa.String(128), primary_key=True),
        sa.Column("request_hash", sa.String(64), nullable=False),
        sa.Column("response", postgresql.JSONB(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )
    op.create_table(
        "outbox",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("event_name", sa.String(100), nullable=False),
        sa.Column("payload", postgresql.JSONB(), nullable=False),
        sa.Column("correlation_id", sa.String(64), nullable=False, server_default="-"),
        sa.Column("producer", sa.String(50), nullable=False, server_default="wallet"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("published_at", sa.DateTime(timezone=True)),
    )
    op.create_index("ix_outbox_unpublished", "outbox", ["published_at", "created_at"])
    op.create_table(
        "processed_events",
        sa.Column("event_id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("processed_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )
    op.execute(
        """
        CREATE FUNCTION reject_ledger_mutation() RETURNS trigger AS $$
        BEGIN
          RAISE EXCEPTION 'ledger_entries is append-only';
        END;
        $$ LANGUAGE plpgsql;
        """
    )
    op.execute(
        """
        CREATE TRIGGER ledger_entries_append_only
          BEFORE UPDATE OR DELETE ON ledger_entries
          FOR EACH ROW EXECUTE FUNCTION reject_ledger_mutation();
        """
    )


def downgrade() -> None:
    op.execute("DROP TRIGGER IF EXISTS ledger_entries_append_only ON ledger_entries")
    op.execute("DROP FUNCTION IF EXISTS reject_ledger_mutation")
    op.drop_table("processed_events")
    op.drop_index("ix_outbox_unpublished", table_name="outbox")
    op.drop_table("outbox")
    op.drop_table("idempotency_keys")
    op.drop_table("topups")
    op.drop_table("gift_cards")
    op.drop_index("ix_ledger_group", table_name="ledger_entries")
    op.drop_index("ix_ledger_account", table_name="ledger_entries")
    op.drop_table("ledger_entries")
    op.drop_table("accounts")
