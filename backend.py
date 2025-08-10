# backend.py
from fact_checker import get_web_snippets, verify_claim

def check_fact(statement: str) -> dict:
    # Step 1: Search for evidence
    search_query = f'{statement} site:snopes.com OR site:politifact.com OR site:bbc.com OR site:reuters.com'
    snippets = get_web_snippets(search_query, num_results=6)

    if not snippets:
        return {
            "verdict": "Unclear",
            "confidence": 0.0,
            "summary": "No evidence found.",
            "evidence": []
        }

    # Step 2: Verify claim with Gemini
    result = verify_claim(statement, snippets)

    # Step 3: Map fact_checker result to frontend expected format
    if "error" in result:
        return {
            "verdict": "Unclear",
            "confidence": 0.0,
            "summary": result["error"],
            "evidence": []
        }

    return {
        "verdict": (
            "True" if result.get("verdict") == "SUPPORTED" else
            "False" if result.get("verdict") == "REFUTED" else
            "Unclear"
        ),
        "confidence": (result.get("confidence", 0) / 100),
        "summary": result.get("explanation", ""),
        "evidence": [{"source": "Web", "snippet": s["text"], "url": s["url"]} for s in snippets]
    }
