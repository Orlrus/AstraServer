import os

import psycopg
from fastapi import FastAPI
from pydantic import BaseModel
from openai import OpenAI

app = FastAPI()
client = OpenAI()

DATABASE_URL = os.environ["DATABASE_URL"]


class AstraRequest(BaseModel):
    text: str
    user_id: str = "default_user"


def init_database():
    with psycopg.connect(DATABASE_URL) as conn:
        with conn.cursor() as cur:
            cur.execute("""
                CREATE TABLE IF NOT EXISTS astra_memory (
                    user_id TEXT PRIMARY KEY,
                    response_id TEXT
                )
            """)
        conn.commit()


def get_response_id(user_id: str):
    with psycopg.connect(DATABASE_URL) as conn:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT response_id FROM astra_memory WHERE user_id = %s",
                (user_id,)
            )
            row = cur.fetchone()

    return row[0] if row else None


def save_response_id(user_id: str, response_id: str):
    with psycopg.connect(DATABASE_URL) as conn:
        with conn.cursor() as cur:
            cur.execute("""
                INSERT INTO astra_memory (user_id, response_id)
                VALUES (%s, %s)
                ON CONFLICT (user_id)
                DO UPDATE SET response_id = EXCLUDED.response_id
            """, (user_id, response_id))
        conn.commit()


init_database()


@app.get("/")
def root():
    return {"status": "AstraServer is running"}


@app.post("/ask")
def ask_astra(request: AstraRequest):

    previous_response_id = get_response_id(request.user_id)

    params = {
        "model": "gpt-5-mini",
        "instructions": (
            "Ти Astra, український голосовий AI-асистент. "
            "Відповідай українською мовою природно, зрозуміло і по суті. "
            "Довжину відповіді визначай залежно від запитання користувача. "
            "Якщо запитання потребує пояснення, давай повну і корисну відповідь."
        ),
        "input": request.text
    }

    if previous_response_id:
        params["previous_response_id"] = previous_response_id

    response = client.responses.create(**params)

    save_response_id(request.user_id, response.id)

    return {
        "answer": response.output_text,
        "response_id": response.id
    }
