from datetime import datetime
from typing import Dict, List, Optional
from uuid import UUID
import asyncpg
from .models import ChatMessage, ChatMessageType, ChatChannelInfo, ChatChannelSubscription


async def create_message(
    conn: asyncpg.Connection,
    text: str,
    sender: str,
    msg_type: ChatMessageType,
    channel: Optional[str] = None,
    ipfs_hash: Optional[str] = None
) -> ChatMessage:
    """Create a new chat message"""
    row = await conn.fetchrow(
        """
        INSERT INTO chat_messages (text, sender, type, channel, ipfs_hash)
        VALUES ($1, $2, $3, $4, $5)
        RETURNING id, text, sender, type, channel, ipfs_hash, edited, deleted, created_at as timestamp
        """,
        text, sender, msg_type.value, channel, ipfs_hash
    )
    
    # Get reactions for the message
    reactions: Dict[str, List[str]] = {}
    reaction_rows = await conn.fetch(
        "SELECT emoji, user_address FROM chat_reactions WHERE message_id = $1",
        row['id']
    )
    for r in reaction_rows:
        if r['emoji'] not in reactions:
            reactions[r['emoji']] = []
        reactions[r['emoji']].append(r['user_address'])
    
    return ChatMessage(
        id=row['id'],
        text=row['text'],
        sender=row['sender'],
        type=ChatMessageType(row['type']),
        channel=row['channel'],
        ipfs_hash=row['ipfs_hash'],
        edited=row['edited'],
        deleted=row['deleted'],
        timestamp=row['timestamp'],
        reactions=reactions
    )


async def get_messages(
    conn: asyncpg.Connection,
    msg_type: ChatMessageType,
    channel: Optional[str] = None,
    limit: int = 20,
    before: Optional[datetime] = None
) -> List[ChatMessage]:
    """Get messages for a channel"""
    query = """
        SELECT m.id, m.text, m.sender, m.type, m.channel, m.ipfs_hash, 
               m.edited, m.deleted, m.created_at as timestamp
        FROM chat_messages m
        WHERE m.type = $1
    """
    params = [msg_type.value]
    
    if channel:
        query += " AND m.channel = $2"
        params.append(channel)
    
    if before:
        query += f" AND m.created_at < ${len(params) + 1}"
        params.append(before)
    
    query += " ORDER BY m.created_at DESC LIMIT $" + str(len(params) + 1)
    params.append(limit)
    
    rows = await conn.fetch(query, *params)
    messages = []
    
    for row in rows:
        # Get reactions for each message
        reactions: Dict[str, List[str]] = {}
        reaction_rows = await conn.fetch(
            "SELECT emoji, user_address FROM chat_reactions WHERE message_id = $1",
            row['id']
        )
        for r in reaction_rows:
            if r['emoji'] not in reactions:
                reactions[r['emoji']] = []
            reactions[r['emoji']].append(r['user_address'])
        
        messages.append(ChatMessage(
            id=row['id'],
            text=row['text'],
            sender=row['sender'],
            type=ChatMessageType(row['type']),
            channel=row['channel'],
            ipfs_hash=row['ipfs_hash'],
            edited=row['edited'],
            deleted=row['deleted'],
            timestamp=row['timestamp'],
            reactions=reactions
        ))
    
    return messages


async def edit_message(
    conn: asyncpg.Connection,
    message_id: UUID,
    sender: str,
    text: str
) -> Optional[ChatMessage]:
    """Edit a message"""
    row = await conn.fetchrow(
        """
        UPDATE chat_messages
        SET text = $1, edited = true, updated_at = now()
        WHERE id = $2 AND sender = $3 AND deleted = false
        RETURNING id, text, sender, type, channel, ipfs_hash, edited, deleted, created_at as timestamp
        """,
        text, message_id, sender
    )
    
    if not row:
        return None
    
    # Get reactions
    reactions: Dict[str, List[str]] = {}
    reaction_rows = await conn.fetch(
        "SELECT emoji, user_address FROM chat_reactions WHERE message_id = $1",
        row['id']
    )
    for r in reaction_rows:
        if r['emoji'] not in reactions:
            reactions[r['emoji']] = []
        reactions[r['emoji']].append(r['user_address'])
    
    return ChatMessage(
        id=row['id'],
        text=row['text'],
        sender=row['sender'],
        type=ChatMessageType(row['type']),
        channel=row['channel'],
        ipfs_hash=row['ipfs_hash'],
        edited=row['edited'],
        deleted=row['deleted'],
        timestamp=row['timestamp'],
        reactions=reactions
    )


async def delete_message(
    conn: asyncpg.Connection,
    message_id: UUID,
    sender: str
) -> bool:
    """Delete a message"""
    result = await conn.execute(
        """
        UPDATE chat_messages
        SET deleted = true, updated_at = now()
        WHERE id = $1 AND sender = $2
        """,
        message_id, sender
    )
    return result == "UPDATE 1"


async def add_reaction(
    conn: asyncpg.Connection,
    message_id: UUID,
    user_address: str,
    emoji: str
) -> bool:
    """Add a reaction to a message"""
    try:
        await conn.execute(
            """
            INSERT INTO chat_reactions (message_id, user_address, emoji)
            VALUES ($1, $2, $3)
            """,
            message_id, user_address, emoji
        )
        return True
    except asyncpg.UniqueViolationError:
        return False


async def remove_reaction(
    conn: asyncpg.Connection,
    message_id: UUID,
    user_address: str,
    emoji: str
) -> bool:
    """Remove a reaction from a message"""
    result = await conn.execute(
        """
        DELETE FROM chat_reactions
        WHERE message_id = $1 AND user_address = $2 AND emoji = $3
        """,
        message_id, user_address, emoji
    )
    return result == "DELETE 1"


async def get_channel_info(
    conn: asyncpg.Connection,
    channel: str,
    channel_type: ChatMessageType
) -> Optional[ChatChannelInfo]:
    """Get information about a channel"""
    # Get participant count
    participant_count = await conn.fetchval(
        """
        SELECT COUNT(DISTINCT user_address)
        FROM chat_channel_subscriptions
        WHERE channel = $1 AND type = $2
        """,
        channel, channel_type.value
    )
    
    if participant_count is None:
        return None
    
    # Get last message
    last_message = await conn.fetchval(
        """
        SELECT text
        FROM chat_messages
        WHERE channel = $1 AND type = $2 AND deleted = false
        ORDER BY created_at DESC
        LIMIT 1
        """,
        channel, channel_type.value
    )
    
    return ChatChannelInfo(
        name=channel,
        type=channel_type,
        participants=participant_count,
        last_message=last_message
    )


async def get_user_channels(
    conn: asyncpg.Connection,
    user_address: str
) -> List[ChatChannelSubscription]:
    """Get all channels a user is subscribed to"""
    rows = await conn.fetch(
        """
        WITH unread_counts AS (
            SELECT channel, COUNT(*) as unread
            FROM chat_messages m
            JOIN chat_channel_subscriptions s ON m.channel = s.channel
            WHERE s.user_address = $1
            AND m.created_at > s.last_read_at
            GROUP BY m.channel
        )
        SELECT s.channel, s.type,
               COALESCE(u.unread, 0) as unread_count,
               (
                   SELECT text
                   FROM chat_messages
                   WHERE channel = s.channel
                   ORDER BY created_at DESC
                   LIMIT 1
               ) as last_message
        FROM chat_channel_subscriptions s
        LEFT JOIN unread_counts u ON s.channel = u.channel
        WHERE s.user_address = $1
        """,
        user_address
    )
    
    return [
        ChatChannelSubscription(
            name=row['channel'],
            type=ChatMessageType(row['type']),
            unread_count=row['unread_count'],
            last_message=row['last_message']
        )
        for row in rows
    ]


async def subscribe_to_channel(
    conn: asyncpg.Connection,
    user_address: str,
    channel: str,
    channel_type: ChatMessageType
) -> bool:
    """Subscribe a user to a channel"""
    try:
        await conn.execute(
            """
            INSERT INTO chat_channel_subscriptions
                (user_address, channel, type)
            VALUES ($1, $2, $3)
            """,
            user_address, channel, channel_type.value
        )
        return True
    except asyncpg.UniqueViolationError:
        return False


async def unsubscribe_from_channel(
    conn: asyncpg.Connection,
    user_address: str,
    channel: str
) -> bool:
    """Unsubscribe a user from a channel"""
    result = await conn.execute(
        """
        DELETE FROM chat_channel_subscriptions
        WHERE user_address = $1 AND channel = $2
        """,
        user_address, channel
    )
    return result == "DELETE 1" 