"""add_fulltext_search_indexes

Revision ID: fe956b638cc9
Revises: 5d6021a9f1e5
Create Date: 2025-10-21 08:14:35.173208

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'fe956b638cc9'
down_revision: Union[str, None] = '5d6021a9f1e5'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """
    Add full-text search capabilities following Telegram/Messenger patterns.

    Features:
    1. PostgreSQL tsvector for full-text search
    2. Trigram indexes for fuzzy/partial matching
    3. Automatic trigger to maintain tsvector column
    4. GIN indexes for fast search performance
    """

    # 1. Enable pg_trgm extension for trigram similarity search
    op.execute("CREATE EXTENSION IF NOT EXISTS pg_trgm;")

    # 2. Add tsvector column for full-text search
    op.add_column(
        'messages',
        sa.Column('content_tsv', sa.dialects.postgresql.TSVECTOR(), nullable=True)
    )

    # 3. Create GIN index on tsvector column for fast full-text search
    # This enables O(log n) search performance like Telegram
    op.create_index(
        'idx_messages_content_tsv',
        'messages',
        ['content_tsv'],
        postgresql_using='gin'
    )

    # 4. Create trigram GIN index for fuzzy/partial matching
    # This allows "did you mean?" and partial word matching like Messenger
    op.execute("""
        CREATE INDEX idx_messages_content_trgm
        ON messages
        USING GIN (content gin_trgm_ops);
    """)

    # 5. Create function to update tsvector column
    op.execute("""
        CREATE OR REPLACE FUNCTION messages_content_tsv_trigger()
        RETURNS trigger AS $$
        BEGIN
            NEW.content_tsv := to_tsvector('english', COALESCE(NEW.content, ''));
            RETURN NEW;
        END
        $$ LANGUAGE plpgsql;
    """)

    # 6. Create trigger to auto-update tsvector on INSERT/UPDATE
    op.execute("""
        CREATE TRIGGER messages_content_tsv_update
        BEFORE INSERT OR UPDATE ON messages
        FOR EACH ROW
        EXECUTE FUNCTION messages_content_tsv_trigger();
    """)

    # 7. Populate existing data with tsvector values
    op.execute("""
        UPDATE messages
        SET content_tsv = to_tsvector('english', COALESCE(content, ''))
        WHERE content_tsv IS NULL;
    """)

    # 8. Create regular B-tree index on conversation_id for scoped searches
    # When searching within a conversation, we filter by conversation_id first
    # Then use the GIN index on content_tsv
    # Note: Can't create composite GIN index with UUID columns
    op.execute("""
        CREATE INDEX IF NOT EXISTS idx_messages_conversation_id_search
        ON messages(conversation_id)
        WHERE deleted_at IS NULL;
    """)

    print("✅ Full-text search indexes created successfully")
    print("📊 Search capabilities:")
    print("  - Full-text search with ranking")
    print("  - Fuzzy matching for typos")
    print("  - Partial word matching")
    print("  - Conversation-scoped search")


def downgrade() -> None:
    """Remove full-text search capabilities."""

    # Drop trigger
    op.execute("DROP TRIGGER IF EXISTS messages_content_tsv_update ON messages;")

    # Drop function
    op.execute("DROP FUNCTION IF EXISTS messages_content_tsv_trigger();")

    # Drop indexes
    op.execute("DROP INDEX IF EXISTS idx_messages_conversation_id_search;")
    op.execute("DROP INDEX IF EXISTS idx_messages_content_trgm;")
    op.drop_index('idx_messages_content_tsv', table_name='messages')

    # Drop column
    op.drop_column('messages', 'content_tsv')

    # Note: We don't drop pg_trgm extension as other tables might use it

    print("✅ Full-text search indexes removed")
