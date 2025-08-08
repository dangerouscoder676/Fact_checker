import os
import json
import requests
from googlesearch import search
from bs4 import BeautifulSoup
from dotenv import load_dotenv


# Use Google Gen AI SDK (Gemini)
import google.generativeai as genai

# Load environment variables from .env
load_dotenv()

# Support two common env names: GEMINI_API_KEY (preferred) or OPENAI_API_KEY (if you previously used OpenAI)
gemini_key = os.getenv("GEMINI_API_KEY") 
if gemini_key:
    # Ensure environment variable is set for the client (the SDK looks for GEMINI_API_KEY by default)
    os.environ["GEMINI_API_KEY"] = gemini_key
else:
    raise RuntimeError("No API key found. Please set GEMINI_API_KEY in your .env (or OPENAI_API_KEY as fallback).")

# Create the Gemini client (the client will read GEMINI_API_KEY from the environment).
genai.configure(api_key=os.getenv("GEMINI_API_KEY"))

def get_web_snippets(query, num_results=5, char_limit=1000):
    """Search and scrape short text snippets from result pages."""
    snippets = []
    for url in search(query, num_results=num_results):
        try:
            r = requests.get(url, timeout=7, headers={"User-Agent": "Mozilla/5.0"})
            r.raise_for_status()
            soup = BeautifulSoup(r.text, "html.parser")
            text = " ".join([p.get_text(separator=" ", strip=True) for p in soup.find_all("p")])
            if text:
                snippets.append({"url": url, "text": text[:char_limit]})
        except requests.RequestException as e:
            # Print a small warning but continue with other results
            print(f"[warning] Error fetching {url}: {e}")
    return snippets

def verify_claim(claim, snippets, model="gemini-2.5-flash"):
    """Ask Gemini to judge the claim based on the collected evidence.
       Returns a Python dict parsed from the model's JSON reply (if possible),
       otherwise returns raw text under 'raw_response'.
    """
    # Build a compact context from snippets
    context = "\n".join([f"{i+1}) {s['text']}\nSource: {s['url']}" for i, s in enumerate(snippets)])
    # Prompt asking for JSON output (the model often follows this but we handle parsing defensively)
    prompt = f"""
You are a fact-checking assistant.
Claim: "{claim}"
Evidence:
{context}

Task:
1. Decide if the claim is SUPPORTED, REFUTED, or NOT ENOUGH INFO based only on the evidence.
2. Give a short explanation (3-5 sentences).
3. Provide a confidence score (0-100).

Respond ONLY in JSON with keys: "verdict", "explanation", "confidence", "sources".
Example:
{{"verdict":"SUPPORTED","explanation":"...","confidence":85,"sources":["https://...","https://..."]}}
"""

    try:
        # Use the Google Gen AI SDK to generate content from the chosen Gemini model.
        # (Quickstart example uses client.models.generate_content(...)). :contentReference[oaicite:1]{index=1}
        resp = genai.GenerativeModel(model).generate_content(prompt)
    except Exception as e:
        return {"error": f"API request failed: {e}"}
    
    # The SDK exposes response.text() style helpers; many examples show reading `.text` or `.response`:
    # We'll try a few common places for returned text.
    model_text = None
    # 1) Some SDK responses expose `.text` property:
    try:
        model_text = resp.text
    except Exception:
        pass

    # 2) Some responses keep candidates/parts (fallback)
    if not model_text:
        try:
            # resp.candidates -> first candidate -> content -> parts -> first part -> text
            cand = getattr(resp, "candidates", None)
            if cand and len(cand) > 0:
                part = cand[0].content.get("parts", [{}])[0]
                model_text = part.get("text") if isinstance(part, dict) else None
        except Exception:
            model_text = None

    # 3) As a last fallback, convert full resp to string
    if not model_text:
        try:
            model_text = str(resp)
        except Exception:
            model_text = ""

    model_text = model_text.strip()

    # Try to parse JSON returned by the model
    try:
        parsed = json.loads(model_text)
        return parsed
    except json.JSONDecodeError:
        # Model didn't return strict JSON — try to extract a JSON substring
        start = model_text.find("{")
        end = model_text.rfind("}")
        if start != -1 and end != -1 and end > start:
            maybe_json = model_text[start:end+1]
            try:
                return json.loads(maybe_json)
            except json.JSONDecodeError:
                pass

    # If parsing fails, return the raw text so the caller can inspect it
    return {"raw_response": model_text}

if __name__ == "__main__":
    claim = input("Enter a claim to check: ").strip()
    if not claim:
        print("No claim entered; exiting.")
        raise SystemExit(1)

    print("\nSearching for evidence...")
    search_query = f'{claim} site:snopes.com OR site:politifact.com OR site:bbc.com OR site:reuters.com'
    snippets = get_web_snippets(search_query, num_results=6)

    if not snippets:
        print("No evidence found.")
        raise SystemExit(0)

    print("\nVerifying claim...")
    result = verify_claim(claim, snippets)

    # Nicely print structured result
    if isinstance(result, dict):
        if "error" in result:
            print("Error:", result["error"])
        elif "raw_response" in result:
            print("Model returned (couldn't parse JSON):\n")
            print(result["raw_response"])
        else:
            # Expected parsed JSON: verdict/explanation/confidence/sources
            print("\nFact-check result:")
            print("Verdict    :", result.get("verdict"))
            print("Confidence :", result.get("confidence"))
            print("Explanation:", result.get("explanation"))
            print("Sources    :", result.get("sources"))
    else:
        print("\nUnexpected result (not a dict):")
        print(result)
