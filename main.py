from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
import json
from pydantic import BaseModel

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

"""
@app.post("/chat")
def chat(req: ChatRequest):
    return {
        "role": "opponent",
        "message": "이건 임시 응답입니다. AI 붙이면 여기서 LLM 호출됨"
    }
"""

@app.post("/chat")
def chat(payload: dict):
    return {
        "reply": "stub response - AI 연결 전 임시 응답",
        "id": payload.get("id", "temp-session"),
        "status": "ok"
    }

#리포트
@app.post("/report")
def report(req: ChatRequest):
    return {
        "summary": "협상 결과 요약 (임시)",
        "missed_issues": [],
        "used_treaties": []
    }

