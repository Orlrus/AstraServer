import os

import httpx
import psycopg
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from openai import OpenAI
from dotenv import load_dotenv
from memory_store import commit_memory, prepare_memory

load_dotenv()

app = FastAPI()
client = OpenAI()

DATABASE_URL = os.environ["DATABASE_URL"]
ORS_API_KEY = os.getenv("ORS_API_KEY")
ORS_DIRECTIONS_URL = (
    "https://api.heigit.org/openrouteservice/v2/"
    "directions/driving-hgv/geojson"
)

class AstraRequest(BaseModel):
    text: str
    user_id: str = "default_user"

class RouteRequest(BaseModel):
    start_latitude: float
    start_longitude: float
    end_latitude: float
    end_longitude: float

    vehicle_height: float
    vehicle_width: float
    vehicle_length: float
    vehicle_weight: float
    axle_load: float

    hazmat: bool = False
    avoid_tollways: bool = False
    avoid_ferries: bool = False

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

@app.post("/route")
async def build_route(request: RouteRequest):
    if not ORS_API_KEY:
        raise HTTPException(
            status_code=503,
            detail="ORS API key is not configured",
        )

    avoid_features = []

    if request.avoid_tollways:
        avoid_features.append("tollways")

    if request.avoid_ferries:
        avoid_features.append("ferries")

    route_options = {
        "vehicle_type": "hgv",
        "profile_params": {
            "restrictions": {
                "height": request.vehicle_height,
                "width": request.vehicle_width,
                "length": request.vehicle_length,
                "weight": request.vehicle_weight,
                "axleload": request.axle_load,
                "hazmat": request.hazmat,
            }
        },
    }

    if avoid_features:
        route_options["avoid_features"] = avoid_features

    request_body = {
        "coordinates": [
            [request.start_longitude, request.start_latitude],
            [request.end_longitude, request.end_latitude],
        ],
        "instructions": True,
        "options": route_options,
    }

    try:
        async with httpx.AsyncClient(timeout=30.0) as ors_client:
            response = await ors_client.post(
                ORS_DIRECTIONS_URL,
                headers={
                    "Authorization": ORS_API_KEY,
                    "Content-Type": "application/json",
                    "Accept": "application/geo+json",
                },
                json=request_body,
            )
            response.raise_for_status()

    except httpx.HTTPStatusError as exc:
        raise HTTPException(
            status_code=502,
           detail=(
    f"ORS route error {exc.response.status_code}: "
    f"{exc.response.text}"
),
        ) from exc

    except httpx.RequestError as exc:
        raise HTTPException(
            status_code=502,
            detail="ORS service is unavailable",
        ) from exc

    return response.json()

@app.post("/ask")
def ask_astra(request: AstraRequest):

    previous_response_id = get_response_id(request.user_id)
    previous_response_id, profile_name, next_turn_count, profile_note = prepare_memory(
        request.user_id,
        request.text,
        previous_response_id,
    )

    params = {
        "model": "gpt-5-mini",
        "reasoning": {"effort": "minimal"},
        "instructions": (
            profile_note +
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
    commit_memory(request.user_id, profile_name, next_turn_count)

    return {
        "answer": response.output_text,
        "response_id": response.id
    }
