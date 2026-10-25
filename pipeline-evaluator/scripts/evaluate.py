"""
파이프라인 평가 스크립트 (Step 4 품질 평가)

concerns.json의 구매 고민 질문과 매핑된 리뷰를 Claude Haiku로 평가한다.

평가 지표:
  - 구체성 지수 (Specificity): 0~2점 — 질문 자체의 디테일 수준
  - 리뷰-질문 적합도 (Relevance): 1~5점 — 각 리뷰가 질문의 답변이 되는 정도
  - 커버리지 (Coverage): 적합도 3점 이상 리뷰 비율

사용법:
  python evaluate.py \\
    --concerns step2_review_analysis/concerns.json \\
    --reviews  step2_review_analysis/sample_reviews_context_tag.json \\
    --output   eval_report.json
"""

import json
import os
import sys
import time
import argparse
from datetime import datetime
from pathlib import Path

try:
    from dotenv import load_dotenv
    _here = Path(__file__).resolve().parent
    for candidate in [_here.parent.parent.parent / ".env", _here / ".env"]:
        if candidate.exists():
            load_dotenv(candidate)
            break
except ImportError:
    pass

try:
    import anthropic
except ImportError:
    print("anthropic 패키지가 필요합니다: pip install anthropic")
    sys.exit(1)


# ─── 설정 ───
MODEL = "claude-haiku-4-5-20251001"
MAX_RETRIES = 3
RETRY_DELAY = 2
DEFAULT_MAX_REVIEWS = 10   # 태그당 평가할 최대 리뷰 수

EVAL_SYSTEM_PROMPT = """당신은 이커머스 플랫폼의 '리뷰 기반 질문 생성 파이프라인'을 평가하는 객관적이고 엄격한 품질 관리(QA) 평가자입니다.
당신의 임무는 주어진 [질문]과 그에 매핑된 [리뷰 목록]을 분석하여, 두 가지 지표(구체성, 적합도)를 정해진 루브릭에 따라 평가하는 것입니다.

평가 지표 및 루브릭은 다음과 같습니다:

1. 구체성 지수 (Specificity) - 질문 1개에 대해 평가
- 2점: 특정 상황, 조건, 피부 타입, 사용감 등 사용자의 실제 구매 결정에 도움을 줄 수 있는 디테일이 명확히 포함됨. (예: "수부지 피부가 겨울에 썼을 때 속당김은 없나요?", "화장 완성 후에 뿌려도 뭉치지 않을까?")
- 1점: 일반적인 속성이나 기능에 대해 묻지만 디테일이 다소 부족함. (예: "보습력은 오래 유지되나요?", "향은 어떤가요?")
- 0점: 지나치게 포괄적이거나 단순 찬반을 묻는 무의미한 질문. (예: "이 제품은 좋은가요?", "추천할 만한가요?")

2. 리뷰-질문 적합도 (Relevance Score) - 각 리뷰마다 개별 평가
- 5점: 리뷰가 질문에 대한 명확하고 직접적인 답변(긍정/부정 무관)을 제공함.
- 4점: 직접적인 키워드는 없으나, 맥락상 질문에 대한 충분한 유추가 가능함.
- 3점: 질문과 같은 주제(카테고리)를 다루지만, 질문에 대한 명확한 답변이 되기엔 약간 부족함.
- 2점: 카테고리만 겨우 겹칠 뿐, 질문이 묻는 특정 상황이나 맥락과는 무관함.
- 1점: 질문과 리뷰 내용이 전혀 상관없음.

반드시 아래의 JSON 포맷으로만 응답해야 하며, 다른 부연 설명은 추가하지 마세요.

{
  "specificity": {
    "score": [0, 1, 2 중 택 1],
    "reason": "평가 사유를 1~2문장으로 간략히 작성"
  },
  "relevance": [
    {
      "reviewId": "리뷰 ID",
      "score": [1, 2, 3, 4, 5 중 택 1],
      "reason": "평가 사유를 1문장으로 간략히 작성"
    }
  ]
}"""


def build_user_prompt(question: str, reviews: list[dict]) -> str:
    """LLM 평가용 유저 프롬프트 생성. reviews = [{ reviewId, content }]"""
    review_lines = "\n\n".join(
        f"{i + 1}. reviewId: {r['reviewId']}\ncontent: {r['content']}"
        for i, r in enumerate(reviews)
    )
    return f"[질문]\n{question}\n\n[리뷰 목록]\n{review_lines}"


def call_eval(client: anthropic.Anthropic, question: str, reviews: list[dict]) -> dict | None:
    """Claude로 구체성 + 적합도 평가. 실패 시 None 반환."""
    user_msg = build_user_prompt(question, reviews)
    text = ""
    for attempt in range(MAX_RETRIES):
        try:
            resp = client.messages.create(
                model=MODEL,
                max_tokens=1024,
                system=EVAL_SYSTEM_PROMPT,
                messages=[{"role": "user", "content": user_msg}],
            )
            text = resp.content[0].text.strip()
            if text.startswith("```"):
                text = text.split("\n", 1)[1].rsplit("```", 1)[0].strip()
            return json.loads(text)

        except anthropic.RateLimitError:
            wait = RETRY_DELAY * (attempt + 1) * 2
            print(f"  ⏳ Rate limit, {wait}초 대기...")
            time.sleep(wait)
        except json.JSONDecodeError as e:
            print(f"  ⚠️  JSON 파싱 실패 (시도 {attempt + 1}): {e} | 원문: {text[:100]}")
            if attempt < MAX_RETRIES - 1:
                time.sleep(RETRY_DELAY)
        except Exception as e:
            print(f"  ❌ API 오류 (시도 {attempt + 1}): {e}")
            if attempt < MAX_RETRIES - 1:
                time.sleep(RETRY_DELAY)
    return None


def coverage_status(pct: float) -> str:
    if pct < 40:
        return "danger"
    elif pct > 90:
        return "warning"
    return "good"


def coverage_emoji(status: str) -> str:
    return {"danger": "🔴", "warning": "🟡", "good": "🟢"}.get(status, "⚪")


def load_reviews(path: str) -> dict[str, str]:
    """원본 리뷰 JSON → { reviewId: content } 매핑"""
    with open(path, "r", encoding="utf-8") as f:
        raw = json.load(f)
    review_list = raw if isinstance(raw, list) else raw.get("results", [])
    return {str(r["reviewId"]): r["content"] for r in review_list if r.get("reviewId") and r.get("content")}


def load_concerns(path: str) -> dict:
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def main():
    parser = argparse.ArgumentParser(description="Step 4 파이프라인 품질 평가")
    parser.add_argument("--concerns", "-c", required=True, help="concerns.json 경로")
    parser.add_argument("--reviews",  "-r", required=True, help="원본 리뷰 JSON 경로")
    parser.add_argument("--output",   "-o", default="",    help="결과 JSON 저장 경로 (생략 시 자동 생성)")
    parser.add_argument("--max-reviews", type=int, default=DEFAULT_MAX_REVIEWS,
                        help=f"태그당 평가할 최대 리뷰 수 (기본: {DEFAULT_MAX_REVIEWS})")
    args = parser.parse_args()

    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        print("❌ ANTHROPIC_API_KEY 환경변수를 설정해주세요")
        sys.exit(1)

    client = anthropic.Anthropic(api_key=api_key)

    print(f"📖 리뷰 원문 로드 중: {args.reviews}")
    review_map = load_reviews(args.reviews)
    print(f"   → {len(review_map)}건 로드 완료\n")

    concerns_data = load_concerns(args.concerns)
    by_product = concerns_data.get("concerns", {})

    total_concerns = sum(len(v) for v in by_product.values())
    print(f"📂 제품 {len(by_product)}개 / 질문 총 {total_concerns}건 평가 시작")
    print("=" * 65)

    all_results = []
    done = 0

    for product_name, concern_list in by_product.items():
        print(f"\n[{product_name}]")

        for idx, concern in enumerate(concern_list, 1):
            concern_id = concern.get("concernId", f"concern_{idx}")
            tag = concern.get("tag", "")
            question = concern.get("question", "")
            review_ids = [str(r) for r in concern.get("reviewIds", [])]

            # 리뷰 원문 수집 (최대 max-reviews건)
            sampled_reviews = []
            for rid in review_ids[: args.max_reviews]:
                content = review_map.get(rid, "")
                if content:
                    sampled_reviews.append({"reviewId": rid, "content": content})

            print(f"  [{idx}] {tag}")
            print(f"       Q: {question}")
            print(f"       리뷰 {len(sampled_reviews)}/{len(review_ids)}건 평가 중...", end=" ", flush=True)

            if not sampled_reviews:
                print("⚠️  리뷰 원문 없음, 건너뜀")
                continue

            eval_result = call_eval(client, question, sampled_reviews)
            done += 1

            if not eval_result:
                print("❌ 평가 실패")
                continue

            specificity = eval_result.get("specificity", {})
            relevance_list = eval_result.get("relevance", [])

            # 커버리지 계산
            above_threshold = sum(1 for r in relevance_list if r.get("score", 0) >= 3)
            total_eval = len(relevance_list)
            coverage_pct = round(above_threshold / total_eval * 100, 1) if total_eval else 0
            cov_status = coverage_status(coverage_pct)
            avg_relevance = round(
                sum(r.get("score", 0) for r in relevance_list) / total_eval, 2
            ) if total_eval else 0

            print(f"완료")
            print(f"       구체성: {specificity.get('score', '?')}점 — {specificity.get('reason', '')}")
            print(f"       커버리지: {coverage_pct}% {coverage_emoji(cov_status)} ({above_threshold}/{total_eval}건 적합)  평균 적합도: {avg_relevance}점")

            all_results.append({
                "product": product_name,
                "concernId": concern_id,
                "tag": tag,
                "question": question,
                "representativeQuote": concern.get("representativeQuote", ""),
                "reviewCount": concern.get("reviewCount", len(review_ids)),
                "specificity": specificity,
                "coverage": coverage_pct,
                "coverageStatus": cov_status,
                "avgRelevance": avg_relevance,
                "relevance": relevance_list,
            })

            time.sleep(0.3)

    # ─── 전체 요약 ───
    print(f"\n{'=' * 65}")
    print("📈 전체 요약")

    if all_results:
        avg_spec = round(sum(r["specificity"].get("score", 0) for r in all_results) / len(all_results), 2)
        avg_rel  = round(sum(r["avgRelevance"] for r in all_results) / len(all_results), 2)
        avg_cov  = round(sum(r["coverage"] for r in all_results) / len(all_results), 1)
        dist = {"danger": 0, "good": 0, "warning": 0}
        for r in all_results:
            dist[r["coverageStatus"]] += 1

        print(f"  질문 수: {len(all_results)}건")
        print(f"  평균 구체성: {avg_spec} / 2")
        print(f"  평균 적합도: {avg_rel} / 5")
        print(f"  평균 커버리지: {avg_cov}%")
        print(f"  커버리지 분포: 🔴 위험 {dist['danger']}건 | 🟢 적정 {dist['good']}건 | 🟡 경고 {dist['warning']}건")
        print("=" * 65)

        summary = {
            "avgSpecificity": avg_spec,
            "avgRelevance": avg_rel,
            "avgCoverage": avg_cov,
            "coverageDistribution": dist,
        }
    else:
        summary = {}
        print("  평가 결과 없음")

    # ─── JSON 저장 ───
    output_path = args.output or f"eval_report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
    output_data = {
        "meta": {
            "evaluatedAt": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "model": MODEL,
            "totalConcerns": len(all_results),
            "concernsFile": args.concerns,
            "reviewsFile": args.reviews,
            "maxReviewsPerConcern": args.max_reviews,
        },
        "summary": summary,
        "results": all_results,
    }

    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(output_data, f, ensure_ascii=False, indent=2)
    print(f"\n💾 평가 결과 저장 → {output_path}")


if __name__ == "__main__":
    main()
