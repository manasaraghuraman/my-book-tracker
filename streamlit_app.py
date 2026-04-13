import streamlit as st
import pandas as pd
import google.generativeai as genai
from github import Github
import io
import json
from datetime import datetime

# --- 1. CORE CONFIGURATION ---
# These must be set in your Streamlit Cloud "Secrets"
try:
    GITHUB_TOKEN = st.secrets["GITHUB_TOKEN"]
    REPO_NAME = st.secrets["REPO_NAME"] 
    GEMINI_KEY = st.secrets["GEMINI_KEY"]
except KeyError:
    st.error("Missing Secrets! Check GITHUB_TOKEN, REPO_NAME, and GEMINI_KEY.")
    st.stop()

# Set up Gemini with the most stable 2026 endpoint
genai.configure(api_key=GEMINI_KEY)
model = genai.GenerativeModel('gemini-1.5-flash')

# Set up GitHub
try:
    g = Github(GITHUB_TOKEN)
    repo = g.get_repo(REPO_NAME)
except Exception as e:
    st.error(f"GitHub Connection Failed: {e}")
    st.stop()

# --- 2. SESSION STATE (The App's Memory) ---
if "interview_step" not in st.session_state:
    st.session_state.interview_step = 0
if "temp_book" not in st.session_state:
    st.session_state.temp_book = {}
if "ai_question" not in st.session_state:
    st.session_state.ai_question = ""

# --- 3. DATA HELPERS ---
def get_data():
    try:
        content = repo.get_contents("books.csv")
        df = pd.read_csv(io.StringIO(content.decoded_content.decode()))
        return df, content.sha
    except:
        # Initial headers if file doesn't exist or is empty
        cols = ["title","author","genre","date_read","score","mood","ai_review","similarities"]
        return pd.DataFrame(columns=cols), None

def save_data(df, sha):
    csv_buffer = io.StringIO()
    df.to_csv(csv_buffer, index=False)
    if sha:
        repo.update_file("books.csv", "BookVault Sync", csv_buffer.getvalue(), sha)
    else:
        repo.create_file("books.csv", "Initialize Library", csv_buffer.getvalue())

# --- 4. APP INTERFACE ---
st.set_page_config(page_title="BookVault AI", layout="wide", page_icon="📖")
st.title("📚 BookVault AI")

tab1, tab2, tab3 = st.tabs(["➕ Add Book", "📖 My Library", "📊 Insights & Recs"])

# --- TAB 1: AI INTERVIEW ---
with tab1:
    if st.session_state.interview_step == 0:
        with st.form("book_init"):
            st.subheader("What are we reading?")
            t = st.text_input("Book Title")
            a = st.text_input("Author")
            m = st.selectbox("Your Current Mood", ["Happy", "Reflective", "Adventurous", "Tired", "Sad"])
            if st.form_submit_button("Start AI Interview"):
                if t and a:
                    st.session_state.temp_book = {"title": t, "author": a, "mood": m}
                    st.session_state.interview_step = 1
                    st.rerun()
                else:
                    st.warning("Please enter both a title and author.")

    elif st.session_state.interview_step == 1:
        st.subheader(f"Interview: {st.session_state.temp_book.get('title')}")
        
        # 🧠 Get AI Question (with Fallback)
        if not st.session_state.ai_question:
            with st.spinner("AI is reading the summary..."):
                try:
                    q_res = model.generate_content(f"Ask 2 deep questions about '{st.session_state.temp_book.get('title')}' to help me review it.")
                    st.session_state.ai_question = q_res.text
                except:
                    st.session_state.ai_question = "1. What was the most memorable part? \n 2. How did the ending make you feel?"

        st.info(st.session_state.ai_question)
        user_ans = st.text_area("Your thoughts:", placeholder="Type your response here...")
        
        # Manual Input for Rating
        manual_score = st.slider("Your Rating", 1, 10, 7)

        if st.button("Finalize & Save to GitHub"):
            with st.spinner("Generating Review..."):
                try:
                    # Request Structured JSON
                    f_prompt = f"""
                    Review '{st.session_state.temp_book['title']}' based on: {user_ans}.
                    The user rated it {manual_score}/10.
                    Return ONLY a JSON object:
                    {{"score": {manual_score}, "genre": "one word", "review": "2 paragraphs", "similarities": "2 books"}}
                    """
                    raw_res = model.generate_content(f_prompt).text
                    clean_res = raw_res.replace("```json", "").replace("```", "").strip()
                    data = json.loads(clean_res)
                except:
                    # Fallback Data
                    data = {"score": manual_score, "genre": "Fiction", "review": user_ans, "similarities": "TBD"}

                # Update DataFrame
                df, sha = get_data()
                new_entry = {
                    "title": st.session_state.temp_book['title'],
                    "author": st.session_state.temp_book['author'],
                    "genre": data.get("genre", "TBD"),
                    "date_read": datetime.now().strftime("%Y-%m-%d"),
                    "score": data.get("score", manual_score),
                    "mood": st.session_state.temp_book['mood'],
                    "ai_review": data.get("review", "Manual Entry"),
                    "similarities": data.get("similarities", "TBD")
                }
                df = pd.concat([df, pd.DataFrame([new_entry])], ignore_index=True)
                save_data(df, sha)
                
                # Reset State
                st.session_state.update({"interview_step": 0, "ai_question": ""})
                st.balloons()
                st.success("Book successfully logged!")
                st.rerun()

# --- TAB 2: ORGANIZED LIBRARY ---
with tab2:
    df, _ = get_data()
    if not df.empty:
        st.subheader("Your Full Collection")
        # Clean up the table for reading
        st.dataframe(
            df[["title", "author", "score", "genre", "mood", "date_read"]],
            use_container_width=True,
            hide_index=True
        )
        
        # Detailed Viewer
        st.divider()
        selected = st.selectbox("Select a book to read the full AI Review:", df["title"].tolist())
        book_info = df[df["title"] == selected].iloc[0]
        st.markdown(f"### Review for {selected}")
        st.write(book_info["ai_review"])
        st.info(f"✨ **Similar Reads:** {book_info['similarities']}")
    else:
        st.info("No books in your vault yet.")

# --- TAB 3: INSIGHTS & RECS ---
with tab3:
    df, _ = get_data()
    if not df.empty:
        c1, c2 = st.columns(2)
        with c1:
            st.subheader("⭐ Top Rated")
            df["score_num"] = pd.to_numeric(df["score"], errors='coerce')
            st.table(df.sort_values(by="score_num", ascending=False).head(5)[["title", "score"]])
        
        with c2:
            st.subheader("🧠 Mood Patterns")
            st.bar_chart(df["mood"].value_counts())

        st.divider()
        st.subheader("🤖 AI Reading Recommendation")
        if st.button("Generate Personal Recommendation"):
            titles = ", ".join(df["title"].tail(5).tolist())
            rec_prompt = f"Based on my recent reads: {titles}, what are 2 books I should read next? Give a serious reason for each."
            rec = model.generate_content(rec_prompt).text
            st.write(rec)
