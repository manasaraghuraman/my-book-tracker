import streamlit as st
import pandas as pd
import google.generativeai as genai
from github import Github
import io
import json
from datetime import datetime

# --- 1. CONFIGURATION ---
genai.configure(api_key=st.secrets["GEMINI_KEY"])
model = genai.GenerativeModel('gemini-1.5-flash')
g = Github(st.secrets["GITHUB_TOKEN"])
repo = g.get_repo(st.secrets["REPO_NAME"])

# --- 2. SESSION STATE ---
if "interview_step" not in st.session_state:
    st.session_state.update({
        "interview_step": 0, "q_count": 0, "answers": [], "temp_book": {}
    })

# --- 3. DATA HELPERS ---
def get_data():
    try:
        content = repo.get_contents("books.csv")
        return pd.read_csv(io.StringIO(content.decoded_content.decode())), content.sha
    except:
        cols = ["title","author","genre","date_read","score","mood","vibes","ai_review","similarities"]
        return pd.DataFrame(columns=cols), None

def save_data(df, sha):
    csv_buf = io.StringIO()
    df.to_csv(csv_buf, index=False)
    repo.update_file("books.csv", "Updated Emotional Archive", csv_buf.getvalue(), sha)

# --- 4. UI SETUP ---
st.set_page_config(page_title="BookVault AI", layout="wide")
st.title("🌙 The Emotional Book Vault")

tab1, tab2, tab3 = st.tabs(["➕ Archive a Book", "📖 The Collection", "📊 Reading DNA"])

with tab1:
    # --- PHASE 0: PERSONAL INPUT ---
    if st.session_state.interview_step == 0:
        st.subheader("Step 1: Emotional Anchors")
        with st.form("init_form"):
            col1, col2 = st.columns(2)
            with col1:
                t = st.text_input("Book Title")
                a = st.text_input("Author")
                g = st.text_input("Genre")
                # More mood options
                m = st.select_slider("Overall Mood", 
                    options=["Wrecked", "Melancholy", "Comforted", "Inspired", "Challenged", "Awestruck", "Haunted", "Joyful"])
            
            with col2:
                vibe = st.text_input("One-word 'Vibe' (e.g. Atmospheric, Gritty, Cozy)")
                impact = st.selectbox("Personal Impact", 
                    ["It changed my mind", "It broke my heart", "It felt like a hug", "It kept me up at night", "It was a slog but worth it"])
                lingering_thought = st.text_area("What's the one thought you can't shake since finishing it?")
            
            if st.form_submit_button("Begin Personal Interview"):
                if t and a:
                    st.session_state.temp_book = {
                        "title": t, "author": a, "genre": g, 
                        "mood": m, "vibes": vibe, "impact": impact, "seed": lingering_thought
                    }
                    st.session_state.interview_step = 1
                    st.rerun()

    # --- PHASE 1: THE BIO-INTERVIEW ---
    elif st.session_state.interview_step == 1:
        st.subheader(f"Reflecting on '{st.session_state.temp_book['title']}'")
        
        # Determine the Question
        with st.spinner("AI is listening..."):
            try:
                history = " ".join(st.session_state.answers)
                q_prompt = f"""
                The user just finished '{st.session_state.temp_book['title']}'. 
                Context: It felt {st.session_state.temp_book['mood']} and {st.session_state.temp_book['impact']}.
                Lingering thought: {st.session_state.temp_book['seed']}.
                Previous answers: {history}.
                Ask 1 highly personal, psychological question that probes WHY the book made them feel this way. 
                Avoid generic book club questions.
                """
                question = model.generate_content(q_prompt).text
            except:
                question = "Which character's shadow felt most like your own, and why did that unnerve or comfort you?"

        st.info(f"**The Vault asks:** {question}")
        user_ans = st.text_input("Your Response:", key=f"ans_{st.session_state.q_count}")

        if st.button("Continue"):
            if user_ans:
                st.session_state.answers.append(f"Q: {question} A: {user_ans}")
                if st.session_state.q_count < 2:
                    st.session_state.q_count += 1
                else:
                    st.session_state.interview_step = 2
                st.rerun()

    # --- PHASE 2: SYNTHESIS ---
    elif st.session_state.interview_step == 2:
        st.subheader("Step 3: Final Resonance")
        score = st.slider("Where does this sit in your soul? (Rating)", 1, 10, 8)
        
        if st.button("Synthesize My Thoughts"):
            with st.spinner("Writing your personal archive..."):
                all_context = f"""
                Book: {st.session_state.temp_book['title']}
                Mood: {st.session_state.temp_book['mood']}
                Vibe: {st.session_state.temp_book['vibes']}
                Impact: {st.session_state.temp_book['impact']}
                Interview: {" ".join(st.session_state.answers)}
                """
                f_prompt = f"""
                Using the context provided: {all_context}, write a 2-paragraph highly personal review.
                The review should sound like a sophisticated diary entry or a professional critique.
                Don't just repeat the answers; SYNTHESIZE them into a narrative about the user's experience.
                Return ONLY a JSON object:
                {{"genre": "Auto-detect", "review": "text", "similarities": "2 specific books"}}
                """
                try:
                    res = model.generate_content(f_prompt).text
                    res_clean = res.replace("```json", "").replace("```", "").strip()
                    data = json.loads(res_clean)
                except:
                    data = {"genre": st.session_state.temp_book['genre'], "review": "Synthesis failed, but your thoughts are safe.", "similarities": "TBD"}

                df, sha = get_data()
                new_row = {
                    "title": st.session_state.temp_book['title'],
                    "author": st.session_state.temp_book['author'],
                    "genre": st.session_state.temp_book['genre'] or data['genre'],
                    "date_read": datetime.now().strftime("%Y-%m-%d"),
                    "score": score,
                    "mood": st.session_state.temp_book['mood'],
                    "vibes": st.session_state.temp_book['vibes'],
                    "ai_review": data['review'],
                    "similarities": data['similarities']
                }
                
                df = pd.concat([df, pd.DataFrame([new_row])], ignore_index=True)
                save_data(df, sha)
                st.session_state.update({"interview_step": 0, "q_count": 0, "answers": [], "temp_book": {}})
                st.balloons()
                st.rerun()

# --- TAB 2: LIBRARY ---
with tab2:
    df, _ = get_data()
    if not df.empty:
        st.dataframe(df[["title", "author", "score", "mood", "vibes", "date_read"]], use_container_width=True, hide_index=True)
        sel = st.selectbox("Open Archive Entry:", df["title"])
        row = df[df["title"] == sel].iloc[0]
        st.markdown(f"### The Experience of *{sel}*")
        st.write(row["ai_review"])
        st.caption(f"Similar Frequencies: {row['similarities']}")

# --- TAB 3: DNA ---
with tab3:
    df, _ = get_data()
    if not df.empty:
        st.subheader("Your Reading Ecosystem")
        st.bar_chart(df["mood"].value_counts())
        st.write("You tend to finish books that leave you feeling:", df["mood"].mode()[0])
