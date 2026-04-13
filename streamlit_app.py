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
model = genai.GenerativeModel('gemini-3-flash') # 2026 stable

g = Github(GITHUB_TOKEN)
repo = g.get_repo(REPO_NAME)

# --- SESSION STATE INITIALIZATION ---
if "interview_step" not in st.session_state:
    st.session_state.interview_step = 0
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
    repo.update_file("books.csv", "AI Interview Entry", csv_buffer.getvalue(), sha)

st.title("📚 AI Book Interviewer")

tab1, tab2 = st.tabs(["➕ Record Book", "📖 Library"])

with tab1:
    # STEP 1: Basic Info
    if st.session_state.interview_step == 0:
        with st.form("init_form"):
            t = st.text_input("What book did you finish?")
            a = st.text_input("Who is the author?")
            m = st.selectbox("Your mood while reading?", ["Curious", "Emotional", "Adventurous", "Tired"])
            if st.form_submit_button("Start Interview"):
                st.session_state.temp_book = {"title": t, "author": a, "mood": m}
                st.session_state.interview_step = 1
                st.rerun()

    # STEP 2: The AI Questions
    elif st.session_state.interview_step == 1:
        st.subheader(f"Interview for: {st.session_state.temp_book['title']}")
        
        # AI generates a specific question based on the title
        if "ai_question" not in st.session_state:
            q_prompt = f"I just finished {st.session_state.temp_book['title']}. Ask me 2 short, serious questions to help you rate and review it."
            st.session_state.ai_question = model.generate_content(q_prompt).text
        
        st.write(f"**AI:** {st.session_state.ai_question}")
        user_response = st.text_area("Your Answer:")

        if st.button("Submit Answers"):
            with st.spinner("Ranking and organizing..."):
                final_prompt = f"""
                Book: {st.session_state.temp_book['title']} by {st.session_state.temp_book['author']}
                User Answers: {user_response}
                Mood: {st.session_state.temp_book['mood']}
                
                Based on this, provide:
                SCORE: [1-10] | REVIEW: [2 paragraphs] | SIMILAR: [2 books] | GENRE: [1 word]
                """
                res = model.generate_content(final_prompt).text
                
                # Parsing
                try:
                    parts = res.split("|")
                    score = parts[0].split(":")[1].strip()
                    review = parts[1].split(":")[1].strip()
                    sims = parts[2].split(":")[1].strip()
                    genre = parts[3].split(":")[1].strip()

                    df, sha = get_csv_from_github()
                    new_row = {
                        "title": st.session_state.temp_book['title'],
                        "author": st.session_state.temp_book['author'],
                        "genre": genre,
                        "date_read": datetime.now().strftime("%Y-%m-%d"),
                        "score": score,
                        "mood": st.session_state.temp_book['mood'],
                        "ai_review": review,
                        "similarities": sims
                    }
                    df = pd.concat([df, pd.DataFrame([new_row])], ignore_index=True)
                    save_to_github(df, sha)
                    
                    st.success("Entry Complete!")
                    # Reset
                    st.session_state.interview_step = 0
                    del st.session_state.ai_question
                except:
                    st.error("AI formatting error. Let's try again.")

with tab2:
    df, _ = get_csv_from_github()
    if not df.empty:
        st.subheader("⭐ Top 10 Books")
        df["score"] = pd.to_numeric(df["score"], errors='coerce')
        st.table(df.sort_values(by="score", ascending=False).head(10)[["title", "author", "score"]])
        st.dataframe(df)
