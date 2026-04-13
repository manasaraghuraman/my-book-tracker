import streamlit as st
import pandas as pd
import google.generativeai as genai
from github import Github
import io
from datetime import datetime

# --- CONFIG ---
GITHUB_TOKEN = st.secrets["GITHUB_TOKEN"]
REPO_NAME = st.secrets["REPO_NAME"] 
GEMINI_KEY = st.secrets["GEMINI_KEY"]

genai.configure(api_key=GEMINI_KEY)
# Use 'latest' to avoid NotFound errors
model = genai.GenerativeModel('gemini-1.5-flash-latest')

g = Github(GITHUB_TOKEN)
repo = g.get_repo(REPO_NAME)

if "interview_step" not in st.session_state:
    st.session_state.interview_step = 0
if "temp_book" not in st.session_state:
    st.session_state.temp_book = {}

def get_csv_from_github():
    try:
        file_content = repo.get_contents("books.csv")
        return pd.read_csv(io.StringIO(file_content.decoded_content.decode())), file_content.sha
    except:
        cols = ["title","author","genre","date_read","score","mood","ai_review","similarities"]
        return pd.DataFrame(columns=cols), None

def save_to_github(df, sha):
    csv_buffer = io.StringIO()
    df.to_csv(csv_buffer, index=False)
    repo.update_file("books.csv", "Book Entry Update", csv_buffer.getvalue(), sha)

st.title("📚 AI Book Vault")

tab1, tab2 = st.tabs(["➕ Add Book", "📖 Library"])

with tab1:
    if st.session_state.interview_step == 0:
        with st.form("init_form"):
            t = st.text_input("Title")
            a = st.text_input("Author")
            m = st.selectbox("Reading Mood", ["Curious", "Emotional", "Adventurous", "Tired"])
            if st.form_submit_button("Start Interview"):
                if t and a:
                    st.session_state.temp_book = {"title": t, "author": a, "mood": m}
                    st.session_state.interview_step = 1
                    st.rerun()

    elif st.session_state.interview_step == 1:
        st.subheader(f"Interviewing: {st.session_state.temp_book['title']}")
        
        if "ai_question" not in st.session_state:
            try:
                q_prompt = f"I finished '{st.session_state.temp_book['title']}'. Ask 2 serious questions to help rate it."
                st.session_state.ai_question = model.generate_content(q_prompt).text
            except:
                st.session_state.ai_question = "What was the most memorable part of this book?"

        st.info(st.session_state.ai_question)
        ans = st.text_area("Your thoughts:")

        if st.button("Finalize Entry"):
            with st.spinner("Processing..."):
                try:
                    f_prompt = f"Review '{st.session_state.temp_book['title']}' based on: {ans}. Format: SCORE: [1-10] | GENRE: [word] | REVIEW: [text] | SIMILAR: [text]"
                    res = model.generate_content(f_prompt).text
                    parts = res.split("|")
                    
                    # Safe extract
                    score = parts[0].split(":")[-1].strip() if ":" in parts[0] else "7"
                    genre = parts[1].split(":")[-1].strip() if len(parts) > 1 else "Fiction"
                    review = parts[2].split(":")[-1].strip() if len(parts) > 2 else ans
                    sims = parts[3].split(":")[-1].strip() if len(parts) > 3 else "N/A"
                except:
                    # Backup if AI fails again
                    score, genre, review, sims = "TBD", "TBD", ans, "TBD"

                df, sha = get_csv_from_github()
                new_row = {
                    "title": st.session_state.temp_book['title'], "author": st.session_state.temp_book['author'],
                    "genre": genre, "date_read": datetime.now().strftime("%Y-%m-%d"),
                    "score": score, "mood": st.session_state.temp_book['mood'],
                    "ai_review": review, "similarities": sims
                }
                df = pd.concat([df, pd.DataFrame([new_row])], ignore_index=True)
                save_to_github(df, sha)
                
                st.success("Saved!")
                st.session_state.interview_step = 0
                if "ai_question" in st.session_state: del st.session_state.ai_question
                st.rerun()

with tab2:
    df, _ = get_csv_from_github()
    if not df.empty:
        st.dataframe(df)
    else:
        st.write("No books yet.")
