from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
import json
from pydantic import BaseModel

# AI
from dotenv import load_dotenv
import os
from fastapi.responses import StreamingResponse

load_dotenv()

from openai import OpenAI

client = OpenAI(
    base_url="https://integrate.api.nvidia.com/v1",
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

    scenario = next((s for s in scenarios if s["id"] == id), None)

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

    stream = client.chat.completions.create(
        model="deepseek-ai/deepseek-v4-flash",
        messages=messages,
        temperature=0.2,
        top_p=0.95,
        extra_body={"chat_template_kwargs": {"thinking": False}},
        stream=True,
    )

    full_reply = ""

    # 생성기
    def generate():
        nonlocal full_reply

        for chunk in stream:
            if not chunk.choices:
                continue

            delta = chunk.choices[0].delta

            if delta and delta.content:
                text = delta.content
                full_reply += text
                yield text

        chat_store[req.id].append({
            "role": "assistant",
            "message": full_reply
        })
        
    return StreamingResponse(
        generate(),
        media_type="text/plain; charset=utf-8",
    )

    print(chat_store)

class StartChatRequest(BaseModel):
    id: str

@app.post("/chat/start")
def start_chat(req: StartChatRequest):
    scenario = next((s for s in scenarios if s["id"] == req.id), None)
    if scenario is None:
        return {"error": "Scenario not found"}
    if req.id in chat_store and len(chat_store[req.id]) > 0:
        first_ai_message = next(
            (chat["message"] for chat in chat_store[req.id] if chat["role"] == "assistant"),
            None
        )
        if first_ai_message:
            return {
                "reply": first_ai_message,
                "id": req.id,
                "status": "already_started"
            }
    opening_message = (
        f"안녕하십니까. 저는 {scenario['country']} 측 대표입니다. "
        f"오늘 협상 의제는 '{scenario['title']}'입니다. "
        "우리 측은 이번 사안에 대해 신중한 입장을 가지고 있으며, "
        "대한민국 측의 제안과 근거를 듣고 협의를 이어가고자 합니다. "
        "먼저 한국 측의 기본 입장을 말씀해주시기 바랍니다."
    )
    chat_store[req.id] = [
        {
            "role": "assistant",
            "message": opening_message
        }
    ]
    return {
        "reply": opening_message,
        "id": req.id,
        "status": "ok"
    }

@app.get("/report/{id}") 
def report(id: str):

    history = chat_store.get(id, [])

    print(chat_store)
    print(history)

    scenario = next((s for s in scenarios if s["id"] == id), None)

    if scenario is None:
        return {"error": "Scenario not found"}

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

    messages = [
            {
                "role": "system",
                "content": """
                너는 대한민국 외교부의 수석 조약 평가관이자, 공모전 시뮬레이션의 공정하고 장려책을 가진 심사위원이다.

                [평가 원칙]
                - 외교적 타협과 합의를 가장 중요하게 평가한다.
                - 사용자가 자신의 주장만 고집하지 않고 상대국과 합리적인 양보를 통해 윈윈(Win-Win) 결과를 만들었다면 높은 점수를 부여한다.
                - 지나치게 엄격한 감점은 하지 말고, 논리적인 시도와 외교적 태도를 긍정적으로 평가한다.
                - 사소한 실수로 큰 감점을 하지 않는다.

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

                각 score는 아래 기준으로 평가한다.

                - evidence
                = 국익 및 목적 달성도(0~25점)
                대한민국의 핵심 요구사항과 경제적·정치적 실리를 얼마나 확보했는지 평가한다.

                - expression
                = 외교적 태도 및 실현 가능성(0~25점)
                정중한 외교적 표현을 사용했는지, 실제 국가 간 협상으로 이어질 수 있는 현실적인 합의인지 평가한다.

                - strategy
                = 상호 호혜성 및 타협 능력(0~25점)
                상대국의 입장을 고려하고 Give & Take를 통해 합리적인 타협을 이루었는지 가장 중요하게 평가한다.

                - perspective
                = 논리성 및 데이터 활용도(0~25점)
                객관적인 근거, 역사적 사례, 국제 정세 등을 활용하여 설득력 있게 주장했는지 평가한다.

                추가 작성 기준

                summary
                - 협상 결과를 3~5문장으로 요약한다.

                koreaClaims
                - 사용자가 제시한 핵심 주장만 정리한다.

                aiRebuttals
                - AI가 제시한 핵심 반론 또는 요구사항을 정리한다.

                flow
                - 협상이 어떤 과정으로 진행되었는지 간략히 설명한다.

                actualResult
                - 실제 역사적 협정이나 국제사례와 비교하여 설명한다.

                references
                - 실제 협정, 조약, 국제기구, 역사적 사례 등을 배열로 작성한다.

                missed
                - 사용자가 놓친 협상 포인트를 작성한다.

                insufficient
                - 근거가 부족했던 부분을 작성한다.

                overlooked
                - 고려하지 못한 국제정세, 경제, 외교 요소를 작성한다.

                expressionRisk
                - 외교적으로 오해를 살 수 있었던 표현을 작성한다.

                betterDirection
                - 다음 협상에서 더 좋은 결과를 얻기 위한 개선 방향을 작성한다.

                설명은 출력하지 말고 JSON 객체만 출력하라.
                코드블록(```json`)은 사용하지 말라.
                반드시 유효한 JSON만 출력하라.
                모든 키를 반드시 포함하라.
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

                위 내용을 바탕으로 협상 리포트를 작성하라.

                반드시 JSON만 출력하라.
                """
                }
            ]

    completion = client.chat.completions.create(
        model="deepseek-ai/deepseek-v4-flash",
        messages=messages,
        temperature=0.2,
        top_p=0.95,
        extra_body={"chat_template_kwargs": {"thinking": False}},
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