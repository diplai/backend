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
             return {
                "id": scenario["id"],
                "title": scenario["title"],
                "field": scenario["field"],
                "country": scenario["country"],
                "summary": scenario["summary"],
                "briefing": scenario["briefing"],
                "stakeholders": scenario["stakeholders"],
                "timeline": scenario["timeline"],
                "treaties": scenario["treaties"],
                "issues": scenario["issues"],
                "suggestedSentences": scenario["suggestedSentences"],
                "drafts": scenario["drafts"],
            }
    return {"error": "not found"}

#AI 챗
class ChatRequest(BaseModel):
    id: str
    message: str

chat_store = {}

@app.post("/chat")
def chat(req: ChatRequest):

    scenario = next((s for s in scenarios if s["id"] == req.id), None)

    if scenario is None:
        return {"error": "Scenario not found"}

    prompt_scenario = {
        "id": scenario["id"],
        "title": scenario["title"],
        "field": scenario["field"],
        "country": scenario["country"],
        "summary": scenario["summary"],
        "briefing": scenario["briefing"],
        "timeline": scenario["timeline"],
        "opponent_goals": scenario["opponent_goals"],
        "opponent_constraints": scenario["opponent_constraints"],
    }

    system_prompt = f"""
                너는 외교 협상 시뮬레이터의 상대국 대표다.

                아래 시나리오 정보를 참고하여 협상을 진행하라.

                {json.dumps(prompt_scenario, ensure_ascii=False, indent=2)}

                위 JSON의 opponent_goals을 최우선으로 하며,
                opponent_constraints를 반드시 준수하라.

                규칙
                - 항상 한국어로만 답변한다. 다른 언어는 사용하지 않는다.
                - 사용자는 대한민국 대표다.
                - 한 번에 하나의 주장만 제시한다.
                - 사용자의 주장에 반드시 반응한다.
                - 협상은 최대 10턴까지 진행한다.
                - 실제 외교관처럼 공손하지만 단호하게 대화한다.
                - 사용자의 의견을 무조건 수용하지 않는다.
                - 양보할 경우 반드시 그에 상응하는 조건을 요구한다.
                - 합의에 도달하지 못해도 된다

                매 응답마다 아래 중 하나를 수행하라.
                - 반박
                - 조건부 수용
                - 추가 요구
                - 대안 제시
                - 정보 요청
                """

    if req.id not in chat_store:
        chat_store[req.id] = []

    chat_store[req.id].append({
        "role": "user",
        "message": req.message
    })

    messages = [
                {
                    "role": "system",
                    "content": system_prompt
                }
            ]

    for chat in chat_store[req.id]:
                messages.append({
                    "role": chat["role"],
                    "content": chat["message"]
                })

    completion = client.chat.completions.create(
        model="llama-3.3-70b-versatile",
            messages=messages,
            temperature=0.2,
            max_completion_tokens=700
    )
    
    reply = completion.choices[0].message.content

    chat_store[req.id].append({
        "role": "assistant",
        "message": reply
    })

    return {
        "reply": reply,
        "id": req.id,
        "status": "ok"
    }

    print(chat_store)

@app.get("/report/{id}") 
def report(id: str):

    print(chat_store)
    print(history)

    scenario = next((s for s in scenarios if s["id"] == id), None)

    if scenario is None:
        return {"error": "Scenario not found"}

    history = chat_store.get(id, [])
    print("history =", history)

    if not history:
        return {
            "summary": "아직 협상이 진행되지 않았습니다.",
            "koreaClaims": [],
            "aiRebuttals": [],
            "flow": "",
            "actualResult": "",
            "references": [],
            "missed": [],
            "insufficient": [],
            "overlooked": [],
            "expressionRisk": [],
            "betterDirection": [],
            "scores": {
                "evidence": 0,
                "expression": 0,
                "strategy": 0,
                "perspective": 0
            }
        }

    report_scenario = {
        "id": scenario["id"],
        "title": scenario["title"],
        "field": scenario["field"],
        "country": scenario["country"],
        "summary": scenario["summary"],
        "briefing": scenario["briefing"],
        "timeline": scenario["timeline"],
        "treaties": scenario["treaties"],
        "actualResult": scenario["actualResult"],
        "korea_goals": scenario["korea_goals"],
        "korea_constraints": scenario["korea_constraints"],
    }

    messages=[
            {
                "role": "system",
                "content": """
                너는 외교 협상 평가관이다.
                
                반드시 아래 JSON 형식을 그대로 사용하라.

                {
                    "summary": "",
                    "koreaClaims": [],
                    "aiRebuttals": [],
                    "flow": "",
                    "actualResult": "",
                    "references": [],
                    "missed": [],
                    "insufficient": [],
                    "overlooked": [],
                    "expressionRisk": [],
                    "betterDirection": [],
                    "scores": {
                        "evidence": 0,
                        "expression": 0,
                        "strategy": 0,
                        "perspective": 0
                    }
                }

                설명은 출력하지 말고 위 JSON 객체만 출력하라.
                반드시 유효한 JSON 객체만 출력하라.
                코드블록(```json)은 사용하지 말라.
                모든 키는 반드시 포함하라.
                값이 없으면 [] 또는 ""를 사용하라.
                """
            },
            {
                "role": "user",
                "content": f"""
                아래는 외교 협상 시뮬레이션 정보이다.
                [시나리오]
                {json.dumps(report_scenario, ensure_ascii=False, indent=2)}

                [전체 대화]
                {json.dumps(history, ensure_ascii=False, indent=2)}

                를 바탕으로

                아래 형식으로 협상 리포트를 작성하라.

                평가 항목
                ++

                1. 사용자와 AI의 협상 결과 요약
                2. 실제 협정 또는 역사적 결과 요약 등등...++

                 시나리오 {id}에 대한 협상 결과 리포트
                 놓친 쟁점은 반드시 issue....
                 """
            }
        ]

    completion = client.chat.completions.create(
        model="llama-3.3-70b-versatile",
        messages=messages,
        temperature=0.2,
        max_completion_tokens=700
    )

    response = completion.choices[0].message.content

    response = response.replace("```json", "")
    response = response.replace("```", "")
    response = response.strip()

    try:
        result = json.loads(response)
    except json.JSONDecodeError:
        return {
            "error": "AI returned invalid JSON",
            "raw": response
        }

    return result