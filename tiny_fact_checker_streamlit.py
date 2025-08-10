import streamlit as st
import pandas as pd
import time
from datetime import datetime

st.set_page_config(page_title="Tiny Fact Checker", layout="wide", page_icon="🕵️‍♂️")

# --- Helper: try to import user's backend ---
def call_backend(statement: str):
    """Tries to call a backend.check_fact function if available.
    If not found, returns a mock response useful for UI testing.
    """
    try:
        import backend
        if hasattr(backend, 'check_fact'):
            return backend.check_fact(statement)
    except Exception:
        # fallthrough to mock
        pass

    # Mock response (UI/demo mode)
    mock = {
        "verdict": "Unclear",
        "confidence": 0.64,
        "summary": (
            "Couldn't reach a real backend — this is a demo response. "
            "If you provide your backend.py with check_fact(statement) I'll wire it up."
        ),
        "evidence": [
            {"source": "Example News", "snippet": "A report states...", "url": "https://example.com/article"},
        ],
    }
    # simple heuristics for demo: look for numbers or 'not' words
    s = statement.lower()
    if any(w in s for w in ["always", "never"]) or any(ch.isdigit() for ch in s):
        mock['verdict'] = 'False'
        mock['confidence'] = 0.78
        mock['summary'] = 'Demo heuristic matched strong claim — flagged as likely False.'
    elif any(w in s for w in ["maybe", "might", "could"]):
        mock['verdict'] = 'Unclear'
        mock['confidence'] = 0.45
        mock['summary'] = 'Modal language detected — claim is uncertain.'
    else:
        mock['verdict'] = 'True'
        mock['confidence'] = 0.62
        mock['summary'] = 'Short demo: statement seems plausible.'
    return mock

# --- Session state for history ---
if 'history' not in st.session_state:
    st.session_state.history = []
if 'statement' not in st.session_state:
    st.session_state.statement = ""

# --- CSS tweaks for nicer look ---
st.markdown(
    """
    <style>
    .big-emoji { font-size:48px }
    .verdict-True { background-color: #e6ffed; padding:10px; border-radius:8px }
    .verdict-False { background-color: #ffeaea; padding:10px; border-radius:8px }
    .verdict-Unclear { background-color: #fff7e6; padding:10px; border-radius:8px }
    .source-link { text-decoration: none; color: inherit }
    </style>
    """,
    unsafe_allow_html=True,
)

# --- Layout ---
with st.container():
    left, right = st.columns([3, 1])
    with left:
        st.markdown("# 🕵️ Tiny Fact Checker")
        st.markdown("*Paste a claim or sentence below and press **Check** — results include a verdict, confidence score, a short explanation, and evidence.*")
    with right:
        st.write("\n")
        st.image("https://static.streamlit.io/examples/cat.jpg", width=120)

# Sidebar
with st.sidebar:
    st.header("Options")
    st.write("Quick examples to try:")
    examples = [
        "The Eiffel Tower is in Paris.",
        "The moon is made of cheese.",
        "India's population is over 1.3 billion.",
        "Drinking two liters of water daily always prevents headaches.",
        "COVID-19 vaccines contain microchips.",
    ]
    example = st.selectbox("Choose an example", ["-- pick one --"] + examples)
    st.write("---")
    st.write("Preferences")
    show_sources = st.checkbox("Show evidence sources by default", value=True)
    enable_history = st.checkbox("Save query history in this session", value=True)
    st.write("\n")

# Main input area
st.markdown("### Enter a claim")
col1, col2 = st.columns([4, 1])
with col1:
    statement = st.text_area("Claim / Statement", value=st.session_state.statement, height=120)
with col2:
    st.write("\n")
    if example and example != "-- pick one --":
        if st.button("Load example"):
            st.session_state.statement = example
            st.rerun()

# Buttons
submit_col, clear_col = st.columns([1, 1])
with submit_col:
    check = st.button("🔎 Check")
with clear_col:
    clear = st.button("✖ Clear")

if clear:
    st.session_state.history = []
    st.session_state.statement = ""
    st.rerun()

# When user checks
if check and statement.strip():
    with st.spinner("Checking claim..."):
        # small UX delay
        time.sleep(0.6)
        result = call_backend(statement)
        # normalize keys
        verdict = result.get('verdict', 'Unclear')
        confidence = float(result.get('confidence', 0.0))
        summary = result.get('summary', '')
        evidence = result.get('evidence', [])

        # Save to history
        entry = {
            'time': datetime.utcnow().isoformat() + 'Z',
            'statement': statement,
            'verdict': verdict,
            'confidence': confidence,
            'summary': summary,
            'evidence_count': len(evidence)
        }
        if enable_history:
            st.session_state.history.insert(0, entry)

    # Show results
    cola, colb = st.columns([3, 1])
    with cola:
        st.markdown(f"### Verdict: <span class='big-emoji'>{'✅' if verdict == 'True' else ('❌' if verdict == 'False' else '❓')}</span> <small>{verdict}</small>", unsafe_allow_html=True)
        box_class = f"verdict-{verdict}"
        st.markdown(f"<div class='{box_class}'>\n**Confidence:** {confidence*100:.0f}%  \n\n**Summary:** {summary}\n</div>", unsafe_allow_html=True)

        if show_sources and evidence:
            st.markdown("---\n**Evidence & Sources**")
            for e in evidence:
                src = e.get('source', 'Source')
                snippet = e.get('snippet', '')
                url = e.get('url', '')
                st.markdown(f"**{src}** — {snippet} <a class='source-link' href='{url}' target='_blank'>[link]</a>", unsafe_allow_html=True)

    with colb:
        st.markdown("### Confidence")
        st.progress(int(confidence*100))
        st.markdown("\n---\n### Quick actions")
        st.download_button("Download result JSON", data=pd.Series([result]).to_json(orient='records'), file_name='fact_check_result.json')
        st.write("\n")
        st.button("Report problem")

# History panel
st.markdown("---")
hist_col, log_col = st.columns([2, 3])
with hist_col:
    st.subheader("Session history")
    if st.session_state.history:
        for i, h in enumerate(st.session_state.history[:10]):
            st.markdown(f"**{h['verdict']}** — {h['statement']}")
            st.caption(f"{h['time']}  • Confidence {h['confidence']*100:.0f}%")
    else:
        st.info("No checks yet. Run your first check above!")

with log_col:
    st.subheader("Analysis log / export")
    if st.session_state.history:
        df = pd.DataFrame(st.session_state.history)
        df_display = df.copy()
        # show human-friendly time
        df_display['time'] = pd.to_datetime(df_display['time']).dt.tz_localize(None)
        st.dataframe(df_display)
        st.download_button("Download CSV", df.to_csv(index=False), file_name='fact_checks.csv')
    else:
        st.write("Nothing to show yet.")

# Footer / integration notes
st.markdown("---")
with st.expander("Integration & deployment notes (click)"):
    st.markdown(
        """
        **How to integrate your backend**

        1. Create a file named `backend.py` in the same folder.
        2. Implement a function `def check_fact(statement: str) -> dict` that returns a dictionary with keys: `verdict`, `confidence`, `summary`, `evidence`.
        3. Re-run the app. The UI will automatically call your function.

        **Deploying**
        - Simple: host on Streamlit Community Cloud or any server with `pip install -r requirements.txt` then `streamlit run tiny_fact_checker_streamlit.py`.
        - For production: wrap backend so it is stateless and scalable (e.g., expose a REST endpoint) and update `call_backend` to `requests.post` to your service.
        """
    )
