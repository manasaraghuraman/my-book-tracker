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
        cols = ["title","author","genre","date_read","score","mood","vibes","impact","ai_review","similarities"]
        return pd.DataFrame(columns=cols), None

def save_data(df, sha):
    csv_buf = io.StringIO()
    df.to_csv(csv_buf, index=False)
    repo.update_file("books.csv", "Updated Archive", csv_buf.getvalue(), sha)

# --- 4. UI SETUP ---
st.set_page_config(page_title="BookVault AI", layout="wide")
st.title("⚖️ The Honest Book Vault")

tab1, tab2, tab3 = st.tabs(["➕ Archive a Book", "📖 The Collection", "📊 Reading DNA"])

with tab1:
    if st.session_state.interview_step == 0:
        st.subheader("Step 1: The Initial Impression")
        with st.form("init_form"):
            col1, col2 = st.columns(2)
            with col1:
                t = st.text_input("Book Title")
                a = st.text_input("Author")
                g = st.text_input("Genre")
                # Expanded Moods as a dropdown
                m = st.selectbox("Overall Mood", 
                    ["Enchanted", "Awestruck", "Inspired", "Comforted", "Neutral / Fine", 
                     "Bored", "Frustrated", "Wrecked", "Melancholy", "Haunted", "Repulsed", "Angry"])
            
            with col2:
                vibe = st.text_input("Vibe (e.g. Gritty, Preachy, Dreamy, Clinical)")
                # Brutally honest personal impact
                impact = st.selectbox("Personal Impact", 
                    ["It changed my life", "It broke my heart", "It felt like a hug", 
                     "I didn't care at all", "It felt like a waste of time", 
                     "I hated every minute", "It was a slog but okay", "It made me angry"])
                lingering_thought = st.text_area("One thing you'd tell the author if they were standing here?")
            
            if st.form_submit_button("Start Honest Interview"):
                if t and a:
                    st.session_state.temp_book = {
                        "title": t, "author": a, "genre": g, 
                        "mood": m, "vibes": vibe, "impact": impact, "seed": lingering_thought
                    }
                    st.session_state.interview_step = 1
                    st.rerun()

    # --- PHASE 1: DYNAMIC INTERVIEW ---
    elif st.session_state.interview_step == 1:
        st.subheader(f"Dissecting '{st.session_state.temp_book['title']}'")
        
        with st.spinner("AI is analyzing your tone..."):
            try:
                # We pass the question count to the AI so it knows to change topics
                history = " | ".join(st.session_state.answers)
                q_prompt = f"""
                The user is archiving '{st.session_state.temp_book['title']}'. 
                Impression: They felt {st.session_state.temp_book['mood']} and said it '{st.session_state.temp_book['impact']}'.
                Seed thought: {st.session_state.temp_book['seed']}.
                Previous Questions/Answers: {history}.
                
                This is question #{st.session_state.q_count + 1}. 
                CRITICAL: Do NOT repeat previous topics. If you already asked about characters, ask about the ending, the writing style, or the user's frustration. 
                If the user hates the book, be a 'cynical critic' and ask why it failed. If they love it, be a 'philosopher'. 
                Keep it to ONE short, sharp question.
                """
                question = model.generate_content(q_prompt).text
            except:
                question = "What was the specific moment you realized this book wasn't (or was) for you?"

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

    # --- PHASE 2: CRITICAL SYNTHESIS ---
    elif st.session_state.interview_step == 2:
        st.subheader("Final Verdict")
        score = st.slider("Final Rating (1=Trash, 10=Masterpiece)", 1, 10, 5)
        
        if st.button("Seal the Archive"):
            with st.spinner("Writing the definitive review..."):
                all_context = f"""
                Book: {st.session_state.temp_book['title']}
                Impact: {st.session_state.temp_book['impact']}
                Mood: {st.session_state.temp_book['mood']}
                Interview: {" ".join(st.session_state.answers)}
                """
                f_prompt = f"""
                Synthesize a 2-paragraph review for '{st.session_state.temp_book['title']}'. 
                User rating: {score}/10. 
                The user felt: {st.session_state.temp_book['impact']}.
                
                CRITICAL INSTRUCTION: If the rating is low or impact is negative, the review MUST be critical and reflect that dissatisfaction. Do not sugarcoat. 
                Write it like a high-end literary journal entry.
                
                Return ONLY a JSON object:
                {{"genre": "Auto-detect", "review": "text", "similarities": "2 books"}}
                """
                try:
                    res = model.generate_content(f_prompt).text
                    res_clean = res.replace("```json", "").replace("```", "").strip()
                    data = json.loads(res_clean)
                except:
                    data = {"genre": "Unknown", "review": "Synthesis failed. Check logs.", "similarities": "N/A"}

                df, sha = get_data()
                new_row = {
                    "title": st.session_state.temp_book['title'],
                    "author": st.session_state.temp_book['author'],
                    "genre": st.session_state.temp_book['genre'] or data['genre'],
                    "date_read": datetime.now().strftime("%Y-%m-%d"),
                    "score": score,
                    "mood": st.session_state.temp_book['mood'],
                    "vibes": st.session_state.temp_book['vibes'],
                    "impact": st.session_state.temp_book['impact'],
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
        st.dataframe(df[["title", "author", "score", "mood", "impact", "date_read"]], use_container_width=True, hide_index=True)
        sel = st.selectbox("View Entry:", df["title"])
        row = df[df["title"] == sel].iloc[0]
        st.markdown(f"### Analysis: *{sel}*")
        st.write(row["ai_review"])
        st.caption(f"If you felt {row['impact']}, you might try: {row['similarities']}")

# --- TAB 3: DNA ---
with tab3:
    df, _ = get_data()
    if not df.empty:
        st.subheader("Your Honest Reading DNA")
        col1, col2 = st.columns(2)
        with col1:
            st.write("**Mood Distribution**")
            st.bar_chart(df["mood"].value_counts())
        with col2:
            st.write("**Impact Distribution**")
            st.bar_chart(df["impact"].value_counts())
