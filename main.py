from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
import json
from pydantic import BaseModel

# AI
from dotenv import load_dotenv
import os

load_dotenv()

from groq import Groq

client = Groq(
    api_key=os.getenv("OPENAI_KEY")
)

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

with open("data/scenarios.json", "r", encoding="utf-8") as f:
    scenarios = json.load(f)

@app.get("/")
def root():
    return {"message": "server is running"}

# ping
@app.get("/ping")
def ping():
    return {"status": "alive"}

@app.get("/scenarios")
def get_scenarios():
    return [
        {"id": s["id"], "title": s["title"], "field": s["field"]}
        for s in scenarios
    ]

@app.get("/scenarios/{id}")
def get_scenario(id: str):
    for s in scenarios:
        if s["id"] == id:
            return s
    return {"error": "not found"}

#AI 챗
class ChatRequest(BaseModel):
    id: str
    message: str

@app.post("/chat")
def chat(req: ChatRequest):

    completion = client.chat.completions.create(
        model="llama-3.3-70b-versatile",
        messages=[
            {
                "role": "system",
                "content": """
너는 외교 협상 시뮬레이터의 상대국 대표다.

- 외교적이고 정중한 어조를 사용한다.
- 사용자의 의견을 무조건 수용하지 않는다.
- 국가 이익을 우선 고려한다.
- 실제 외교 협상처럼 답변한다.
- 답변은 3~5문장 정도로 작성한다.
"""
            },
            {
                "role": "user",
                "content": req.message
            }
        ]
    )

    reply = completion.choices[0].message.content

    return {
        "reply": reply,
        "id": req.id,
        "status": "ok"
    }
"""
#리포트
@app.post("/report")
def report(req: ChatRequest):
    return {
        "summary": "협상 결과 요약 (임시)",
        "missed_issues": [],
        "used_treaties": []
    }
"""

@app.get("/report/{id}")
def report(id: str):
    return {"id": id}