from fastapi import FastAPI
from pydantic import BaseModel
from openai import OpenAI

app = FastAPI()
client = OpenAI()


class AstraRequest(BaseModel):
    text: str


@app.post("/ask")
def ask_astra(request: AstraRequest):
    response = client.responses.create(
        model="gpt-5-mini",
        instructions=(
            "Ти Astra, український голосовий AI-асистент. "
            "Відповідай українською мовою, природно і стисло."
        ),
        input=request.text
    )

    return {
        "answer": response.output_text
    }