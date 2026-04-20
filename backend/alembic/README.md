# Alembic migration authoring guidelines

## Concurrent index policy

For large tables, create and drop indexes with PostgreSQL concurrent mode.
This avoids long blocking locks during production migrations.

Use `autocommit_block()` for concurrent index operations:

```python
def upgrade() -> None:
    with op.get_context().autocommit_block():
        op.create_index(
            "ix_chat_messages_session_id",
            "chat_messages",
            ["session_id"],
            postgresql_concurrently=True,
        )


def downgrade() -> None:
    with op.get_context().autocommit_block():
        op.drop_index("ix_chat_messages_session_id", postgresql_concurrently=True)
```

## Data and schema changes

Do not mix schema changes and data backfill in the same migration revision.
Create separate revisions to keep rollback behavior predictable.

## Downgrade parity

Every upgrade migration must include a tested downgrade path.
