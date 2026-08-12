from fastapi import FastAPI
from pydantic import BaseModel
from openai import OpenAI

app = FastAPI()
client = OpenAI()


class AstraRequest(BaseModel):
    text: str
    previous_response_id: str | None = None


@app.post("/ask")
def ask_astra(request: AstraRequest):

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

    if request.previous_response_id:
        params["previous_response_id"] = request.previous_response_id

    response = client.responses.create(**params)

    return {
        "answer": response.output_text,
        "response_id": response.id
    }