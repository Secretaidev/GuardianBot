"""
bot/database/mongo.py
─────────────────────
Async MongoDB connection manager using Motor.

Responsibilities
----------------
• Boot-time connection to MONGO_URI
• Create every collection index the bot needs
• Expose `db` (AsyncIOMotorDatabase) and `get_collection()` helper
• Expose `connect_db()` coroutine that must be awaited before any DB call
"""

import logging
from typing import Optional

import motor.motor_asyncio
from pymongo import ASCENDING, DESCENDING, IndexModel
from pymongo.errors import ConnectionFailure, ServerSelectionTimeoutError

from bot.config import MONGO_URI

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Module-level singletons – populated inside connect_db()
# ---------------------------------------------------------------------------
_client: Optional[motor.motor_asyncio.AsyncIOMotorClient] = None
db: Optional[motor.motor_asyncio.AsyncIOMotorDatabase] = None


# ---------------------------------------------------------------------------
# Index definitions per collection
# ---------------------------------------------------------------------------
_INDEXES: dict[str, list[IndexModel]] = {
    "users": [
        IndexModel([("user_id", ASCENDING)], unique=True, name="user_id_unique"),
        IndexModel([("username", ASCENDING)], name="username_idx", sparse=True),
    ],
    "chats": [
        IndexModel([("chat_id", ASCENDING)], unique=True, name="chat_id_unique"),
    ],
    "warns": [
        IndexModel([("chat_id", ASCENDING), ("user_id", ASCENDING)], name="warn_chat_user_idx"),
        IndexModel([("warn_id", ASCENDING)], name="warn_id_idx"),
        IndexModel([("chat_id", ASCENDING)], name="warn_chat_idx"),
    ],
    "notes": [
        IndexModel(
            [("chat_id", ASCENDING), ("note_name", ASCENDING)],
            unique=True,
            name="note_chat_name_unique",
        ),
    ],
    "filters": [
        IndexModel(
            [("chat_id", ASCENDING), ("keyword", ASCENDING)],
            unique=True,
            name="filter_chat_keyword_unique",
        ),
        IndexModel([("chat_id", ASCENDING)], name="filter_chat_idx"),
    ],
    "federations": [
        IndexModel([("fed_id", ASCENDING)], unique=True, name="fed_id_unique"),
        IndexModel([("owner_id", ASCENDING)], name="fed_owner_idx"),
    ],
    "fed_chats": [
        IndexModel([("chat_id", ASCENDING)], name="fed_chat_chat_idx"),
        IndexModel([("fed_id", ASCENDING)], name="fed_chat_fed_idx"),
    ],
    "fed_bans": [
        IndexModel(
            [("fed_id", ASCENDING), ("user_id", ASCENDING)],
            unique=True,
            name="fed_ban_unique",
        ),
    ],
    "fed_admins": [
        IndexModel(
            [("fed_id", ASCENDING), ("user_id", ASCENDING)],
            unique=True,
            name="fed_admin_unique",
        ),
    ],
    "blocklist": [
        IndexModel(
            [("chat_id", ASCENDING), ("trigger", ASCENDING)],
            unique=True,
            name="blocklist_chat_trigger_unique",
        ),
    ],
    "antiflood": [
        IndexModel([("chat_id", ASCENDING)], unique=True, name="antiflood_chat_unique"),
    ],
}


async def _create_indexes() -> None:
    """Create all required indexes on startup (idempotent)."""
    assert db is not None, "Database not initialised"
    for collection_name, index_models in _INDEXES.items():
        collection = db[collection_name]
        try:
            await collection.create_indexes(index_models)
            logger.debug("Indexes ensured for collection '%s'.", collection_name)
        except Exception as exc:  # noqa: BLE001
            logger.error(
                "Failed to create indexes for collection '%s': %s",
                collection_name,
                exc,
            )


async def connect_db() -> None:
    """
    Initialise the Motor client and create indexes.

    Call this once during bot startup before any database operation.
    Raises SystemExit on fatal connection errors.
    """
    global _client, db  # noqa: PLW0603
    mongo_uri = MONGO_URI
    if not mongo_uri:
        logger.critical("MONGO_URI is not set in config. Aborting.")
        raise SystemExit(1)

    logger.info("Connecting to MongoDB …")
    try:
        _client = motor.motor_asyncio.AsyncIOMotorClient(
            mongo_uri,
            serverSelectionTimeoutMS=10_000,
            maxPoolSize=50,
            minPoolSize=5,
            retryWrites=True,
        )
        # Force a real connection attempt so we catch errors early
        await _client.admin.command("ping")
    except (ConnectionFailure, ServerSelectionTimeoutError) as exc:
        logger.critical("MongoDB connection failed: %s", exc)
        raise SystemExit(1) from exc

    db = _client["guardianbot"]
    logger.info("Connected to MongoDB – database: 'guardianbot'.")

    await _create_indexes()
    logger.info("All collection indexes ensured.")


def get_collection(name: str) -> motor.motor_asyncio.AsyncIOMotorCollection:
    """
    Return a Motor collection by name.

    Parameters
    ----------
    name : str
        Name of the MongoDB collection.

    Returns
    -------
    AsyncIOMotorCollection

    Raises
    ------
    RuntimeError
        If called before `connect_db()` has completed successfully.
    """
    if db is None:
        raise RuntimeError(
            "Database is not initialised. Await `connect_db()` before using `get_collection()`."
        )
    return db[name]


async def close_db() -> None:
    """Gracefully close the Motor client (call during shutdown)."""
    global _client  # noqa: PLW0603
    if _client is not None:
        _client.close()
        _client = None
        logger.info("MongoDB connection closed.")
