from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from dotenv import load_dotenv
from key_manager import get_client, next_client

import json
import os

load_dotenv()

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

chat_store = {}

class ChatRequest(BaseModel):
    id: str
    message: str
    round: int | None = None


class StartChatRequest(BaseModel):
    id: str

@app.get("/")
def root():
    return {"message": "server is running"}


@app.get("/ping")
def ping():
    return {"status": "alive"}


@app.get("/scenarios")
def get_scenarios():
    return [
        {
            "id": s["id"],
            "title": s["title"],
            "field": s["field"],
            "country": s.get("country", ""),
        }
        for s in scenarios
    ]


@app.get("/scenarios/{id}")
def get_scenario(id: str):
    scenario = next((s for s in scenarios if s["id"] == id), None)

    if scenario is None:
        return {"error": "not found"}

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


@app.post("/chat/start")
def start_chat(req: StartChatRequest):
    scenario = next((s for s in scenarios if s["id"] == req.id), None)

    if scenario is None:
        return {"error": "Scenario not found"}

    if req.id in chat_store and len(chat_store[req.id]) > 0:
        first_ai_message = next(
            (
                chat["message"]
                for chat in chat_store[req.id]
                if chat["role"] == "assistant"
            ),
            None,
        )

        if first_ai_message:
            return {
                "reply": first_ai_message,
                "id": req.id,
                "status": "already_started",
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
            "message": opening_message,
        }
    ]

    return {
        "reply": opening_message,
        "id": req.id,
        "status": "ok",
    }


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

    위 JSON의 opponent_goals을 최우선으로 고려하며,
    opponent_constraints를 반드시 준수하라.

    너의 역할
    - 대한민국 대표와 협상하는 상대국 대표이다.
    - 객관적인 분석가가 아니라 상대국의 국익을 대변하는 협상 당사자이다.
    - 모든 답변은 상대국의 목표와 이해관계를 중심으로 판단한다.
    - 대한민국의 주장에 자동으로 동의하거나 중립적인 의견을 제시하지 않는다.

    협상 판단 원칙
    - 상대국의 정치적, 경제적, 안보적 이해관계를 우선 고려한다.
    - 상대국의 목표 달성에 불리한 제안은 거절하거나 수정 요청한다.
    - 상대방의 요구가 상대국에 어떤 영향을 주는지 평가한 후 답변한다.
    - 쉽게 양보하지 않는다.
    - 양보가 필요한 경우 상대국이 얻을 수 있는 이익이나 조건을 함께 고려한다.
    - 합의보다 상대국의 핵심 이익 보호를 우선한다.

    대화 방식
    - 실제 외교관처럼 공손하지만 단호하게 말한다.
    - 사용자의 주장에 반드시 반응한다.
    - 사용자의 의견을 무조건 수용하지 않는다.
    - 상대국 입장에서 우려 사항과 요구 사항을 명확하게 제시한다.
    - 필요할 경우 추가 설명이나 조건을 요구한다.
    - 단순히 양측 입장을 정리하는 답변은 하지 않는다.

    규칙
    - 항상 한국어로만 답변한다. 다른 언어는 사용하지 않는다.
    - 사용자는 대한민국 대표다.
    - 한 번에 하나의 주장만 제시한다.
    - 협상은 최대 10턴까지 진행한다.
    - 합의에 도달하지 못해도 된다.

    매 응답마다 아래 중 하나의 방식으로 대응한다.
    - 상대국 입장 표명
    - 사용자 주장에 대한 반응
    - 우려 사항 제기
    - 요구 사항 제시
    - 조건 확인
    - 수정 제안

    답변 생성 과정은 출력하지 말고 최종 협상 발언만 출력한다.
    """

    if req.id not in chat_store:
        chat_store[req.id] = []

    chat_store[req.id].append(
        {
            "role": "user",
            "message": req.message,
        }
    )

    messages = [
        {
            "role": "system",
            "content": system_prompt,
        }
    ]

    for item in chat_store[req.id]:
        messages.append(
            {
                "role": item["role"],
                "content": item["message"],
            }
        )

    full_reply = ""

    def generate():
        full_reply = ""

        for _ in range(len(API_KEYS)):
            client = get_client()

            try:
                stream = client.chat.completions.create(
                    model="deepseek-ai/deepseek-v4-flash",
                    messages=messages,
                    temperature=0.2,
                    top_p=0.95,
                    extra_body={"chat_template_kwargs": {"thinking": False}},
                    stream=True,
                )

                for chunk in stream:
                    if chunk.choices:
                        delta = chunk.choices[0].delta
                        if delta and delta.content:
                            text = delta.content
                            full_reply += text
                            yield text

                break  # 정상 종료

            except Exception as e:
                print("[AI ERROR]", e)
                error = str(e).lower()

                is_limit = (
                    "resourceexhausted" in error
                    or "429" in error
                    or "503" in error
                    or "rate limit" in error
                    or "quota" in error
                )

                if is_limit:
                    if next_client() is not None:
                        continue
                    else:
                        yield "\n[ERROR] API 키 모두 소진"
                        return

                raise

        chat_store[req.id].append(
            {
                "role": "assistant",
                "message": full_reply,
            }
        )

    return StreamingResponse(
        generate(),
        media_type="text/plain; charset=utf-8",
    )


@app.get("/report/{id}")
def report(id: str):
    history = chat_store.get(id, [])

    scenario = next((s for s in scenarios if s["id"] == id), None)

    if scenario is None:
        return {"error": "Scenario not found"}

    if not history:
        return {
            "summary": "아직 협상이 진행되지 않았습니다.",
            "koreaClaims": [],
            "aiRebuttals": [],
            "flow": "",
            "actualResult": "",
            "missed": [],
            "insufficient": [],
            "overlooked": [],
            "expressionRisk": [],
            "betterDirection": [],
            "total_score": 0,
            "detailed_scores": {
                "national_interest": {
                    "score": 0,
                    "reason": "아직 협상이 진행되지 않아 평가할 수 없습니다.",
                },
                "reciprocity_compromise": {
                    "score": 0,
                    "reason": "아직 협상이 진행되지 않아 평가할 수 없습니다.",
                },
                "logic_data": {
                    "score": 0,
                    "reason": "아직 협상이 진행되지 않아 평가할 수 없습니다.",
                },
                "diplomatic_etiquette": {
                    "score": 0,
                    "reason": "아직 협상이 진행되지 않아 평가할 수 없습니다.",
                },
            },
            "overall_feedback": "아직 협상이 진행되지 않았습니다.",
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
[역할 정의]
당신은 대한민국 외교부의 수석 조약 평가관이자, 공모전 시뮬레이션의 공정하고 장려책을 가진 심사위원입니다.
사용자가 AI와 진행한 조약 협상 대화록을 바탕으로 협상 결과 리포트와 최종 점수를 작성해 주세요.

[채점 원칙]
- 본 평가는 외교적 타협과 합의의 가치를 높게 평가합니다.
- 사용자가 자신의 주장만 고집하지 않고, 상대국과 합리적인 양보를 통해 윈윈 모델을 만들었다면 관대하게 점수를 부여하세요.
- 지나치게 엄격한 기준을 지양하고, 사용자의 논리적 시도와 외교적 매너를 격려하는 방향으로 채점합니다.
- 사소한 실수로 큰 점수를 감점하지 마십시오.

[평가 항목 및 기준]
총점은 100점이며, 각 항목은 25점 만점입니다.

1. 국익 및 목적 달성도
- 대한민국 측의 핵심 요구사항과 경제적·정치적 실리를 일정 부분 확보했는가?
- 목표를 대부분 달성함: 22~25점
- 절반 수준 달성 및 대안 마련: 17~21점
- 미흡: 15점 이하

2. 상호 호혜성 및 타협 능력
- 상대국의 제안을 경청하고, 합리적인 주고받기를 통해 교착 상태를 해결하려 노력했는가?
- 가장 관대하게 평가할 것
- 창의적 타협안 제시 및 합의 성공: 22~25점
- 무난한 상호 양보: 17~21점
- 일방적 주장 고수: 15점 이하

3. 논리성 및 데이터 활용도
- 한국이 체결한 기존 조약 사례나 객관적인 통계, 역사적 맥락을 바탕으로 설득력 있게 대화를 이끌었는가?
- 명확한 근거 제시: 22~25점
- 상식적인 수준의 논리 전개: 17~21점
- 근거 없는 주장: 15점 이하

4. 외교적 태도 및 실현 가능성
- 감정적인 언사를 자제하고, 정중하고 신중한 외교적 어조를 유지했는가?
- 최종 도출된 합의가 실제 국가 간에 이행 가능한 수준인가?
- 매우 정중하며 현실적인 합의: 22~25점
- 무난한 태도: 17~21점
- 외교 격식 파괴: 15점 이하

[리포트 작성 기준]
summary
- 협상 결과를 3~5문장으로 요약합니다.

koreaClaims
- 사용자가 제시한 핵심 주장과 요구사항을 배열로 정리합니다.

aiRebuttals
- AI 상대국 대표가 제시한 핵심 반론, 요구사항, 조건을 배열로 정리합니다.

flow
- 협상이 어떤 흐름으로 진행되었는지 간략히 설명합니다.

actualResult
- 실제 조약, 협정, 역사적 사례 또는 유사 외교 사례와 비교하여 설명합니다.

missed
- 사용자가 놓친 협상 쟁점이나 추가로 고려할 수 있었던 포인트를 배열로 작성합니다.

insufficient
- 근거가 부족했던 부분을 배열로 작성합니다.

overlooked
- 고려하지 못한 상대국 입장, 국제정세, 경제·외교 요소를 배열로 작성합니다.

expressionRisk
- 외교적으로 오해를 살 수 있었던 표현이나 주의할 표현을 배열로 작성합니다.

betterDirection
- 다음 협상에서 더 좋은 결과를 얻기 위한 개선 방향을 배열로 작성합니다.

[출력 형식]
반드시 아래 JSON 형태로만 결과를 반환하세요.

{
  "summary": "",
  "koreaClaims": [],
  "aiRebuttals": [],
  "flow": "",
  "actualResult": "",
  "missed": [],
  "insufficient": [],
  "overlooked": [],
  "expressionRisk": [],
  "betterDirection": [],
  "total_score": 0,
  "detailed_scores": {
    "national_interest": {
      "score": 0,
      "reason": ""
    },
    "reciprocity_compromise": {
      "score": 0,
      "reason": ""
    },
    "logic_data": {
      "score": 0,
      "reason": ""
    },
    "diplomatic_etiquette": {
      "score": 0,
      "reason": ""
    }
  },
  "overall_feedback": ""
}

[출력 규칙]
- 설명은 출력하지 말고 JSON 객체만 출력하세요.
- 코드블록은 사용하지 마세요.
- 반드시 유효한 JSON만 출력하세요.
- 모든 키를 반드시 포함하세요.
- 값이 없으면 [] 또는 ""를 사용하세요.
- total_score는 네 항목 score의 합산값이며 0~100 사이의 정수여야 합니다.
- detailed_scores의 각 score는 반드시 0~25 사이의 정수여야 합니다.
- 각 reason은 점수를 준 긍정적인 이유와 개선 방향을 함께 담아 작성하세요.
- overall_feedback은 전체적인 협상 총평과 격려 메시지를 작성하세요.
""",
        },
        {
            "role": "user",
            "content": f"""
아래는 외교 협상 시뮬레이션 정보입니다.

[시나리오]
{json.dumps(report_scenario, ensure_ascii=False, indent=2)}

[전체 대화]
{json.dumps(history, ensure_ascii=False, indent=2)}

위 내용을 바탕으로 협상 결과 리포트와 점수 평가를 작성하세요.
반드시 JSON만 출력하세요.
""",
        },
    ]

    for _ in range(len(API_KEYS)):
        client = get_client()

        try:
            completion = client.chat.completions.create(
                model="deepseek-ai/deepseek-v4-flash",
                messages=messages,
                temperature=0.2,
                top_p=0.95,
                extra_body={"chat_template_kwargs": {"thinking": False}},
                max_tokens=2500,
            )
            break

        except Exception as e:
            error = str(e).lower()

            if (
                "resourceexhausted" in error
                or "429" in error
                or "503" in error
                or "rate limit" in error
                or "quota" in error
            ):
                if next_client() is not None:
                    continue

            raise

    response = completion.choices[0].message.content

    response = response.replace("```json", "")
    response = response.replace("```", "")
    response = response.strip()

    try:
        result = json.loads(response)
    except json.JSONDecodeError:
        return {
            "error": "AI returned invalid JSON",
            "raw": response,
        }

    return result