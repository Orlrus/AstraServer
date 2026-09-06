import os
import re

import psycopg


DATABASE_URL = os.environ["DATABASE_URL"]
MAX_CHAIN_TURNS = 8

NAME_PATTERNS = (
    r"\bмене\s+звати\s+([A-Za-zА-Яа-яІіЇїЄєҐґ'’\-]{2,40})",
    r"\bмо[єе]\s+ім['’]я\s+([A-Za-zА-Яа-яІіЇїЄєҐґ'’\-]{2,40})",
    r"\bменя\s+зовут\s+([A-Za-zА-Яа-яЁёІіЇїЄєҐґ'’\-]{2,40})",
    r"\bмо[её]\s+имя\s+([A-Za-zА-Яа-яЁёІіЇїЄєҐґ'’\-]{2,40})",
    r"\bmy\s+name\s+is\s+([A-Za-z'’\-]{2,40})",
)


def init_profile_table() -> None:
    with psycopg.connect(DATABASE_URL) as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                CREATE TABLE IF NOT EXISTS astra_profile (
                    user_id TEXT PRIMARY KEY,
                    name TEXT,
                    turn_count INTEGER NOT NULL DEFAULT 0
                )
                """
            )
        conn.commit()


def _extract_name(text: str) -> str | None:
    for pattern in NAME_PATTERNS:
        match = re.search(pattern, text, flags=re.IGNORECASE)
        if match:
            name = match.group(1).strip(" .,!?:;")
            return name[:1].upper() + name[1:]
    return None


def _get_profile(user_id: str) -> tuple[str | None, int]:
    with psycopg.connect(DATABASE_URL) as conn:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT name, turn_count FROM astra_profile WHERE user_id = %s",
                (user_id,),
            )
            row = cur.fetchone()
    return (row[0], row[1]) if row else (None, 0)


def prepare_memory(
    user_id: str,
    text: str,
    previous_response_id: str | None,
) -> tuple[str | None, str | None, int, str]:
    saved_name, turn_count = _get_profile(user_id)
    name = _extract_name(text) or saved_name

    if previous_response_id and turn_count < MAX_CHAIN_TURNS:
        usable_response_id = previous_response_id
        next_turn_count = turn_count + 1
    else:
        usable_response_id = None
        next_turn_count = 1

    if name:
        profile_note = (
            f"\nВідомий профіль користувача: ім'я — {name}. "
            "Звертайся по імені природно, але не в кожній відповіді."
        )
    else:
        profile_note = "\nПрофіль користувача поки порожній. Не вигадуй персональні дані."

    return usable_response_id, name, next_turn_count, profile_note


def commit_memory(user_id: str, name: str | None, turn_count: int) -> None:
    with psycopg.connect(DATABASE_URL) as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO astra_profile (user_id, name, turn_count)
                VALUES (%s, %s, %s)
                ON CONFLICT (user_id)
                DO UPDATE SET
                    name = COALESCE(EXCLUDED.name, astra_profile.name),
                    turn_count = EXCLUDED.turn_count
                """,
                (user_id, name, turn_count),
            )
        conn.commit()


init_profile_table()
