import streamlit as st
import pandas as pd
import google.generativeai as genai
from github import Github
import io
from datetime import datetime

# 1. SETUP CONFIG (Must be at the top)
GITHUB_TOKEN = st.secrets["GITHUB_TOKEN"]
REPO_NAME = st.secrets["REPO_NAME"] 
GEMINI_KEY = st.secrets["GEMINI_KEY"]

genai.configure(api_key=GEMINI_KEY)
model = genai.GenerativeModel('gemini-1.5-flash')

g = Github(GITHUB_TOKEN)
repo = g.get_repo(REPO_NAME)

# 2. INITIALIZE SESSION STATE
if "interview_step" not in st.session_state:
    st.session_state.interview_step = 0
if "temp_book" not in st.session_state:
    st.session_state.temp_book = {}

# 3. HELPER FUNCTIONS
def get_csv_from_github():
    try:
        file_content = repo.get_contents("books.csv")
        df = pd.read_csv(io.StringIO(file_content.decoded_content.decode()))
        return df, file_content.sha
    except:
        cols = ["title","author","genre","date_read","score","mood","ai_review","similarities"]
        return pd.DataFrame(columns=cols), None

def save_to_github(df, sha):
    csv_buffer = io.StringIO()
    df.to_csv(csv_buffer, index=False)
    if sha:
        repo.update_file("books.csv", "AI Interview Entry", csv_buffer.getvalue(), sha)
    else:
        repo.create_file("books.csv", "Initial Create", csv_buffer.getvalue())

# 4. APP UI
st.set_page_config(page_title="Book Vault", page_icon="📚")
st.title("📚 AI Book Interviewer")

tab1, tab2 = st.tabs(["➕ Record Book", "📖 Library"])

with tab1:
    # STEP 0: THE INPUT FORM
    if st.session_state.interview_step == 0:
        with st.form("init_form"):
            t = st.text_input("What book did you finish?")
            a = st.text_input("Who is the author?")
            m = st.selectbox("Your mood while reading?", ["Curious", "Emotional", "Adventurous", "Tired"])
            if st.form_submit_button("Start Interview"):
                if t and a:
                    st.session_state.temp_book = {"title": t, "author": a, "mood": m}
                    st.session_state.interview_step = 1
                    st.rerun()
                else:
                    st.error("Please provide a title and author.")

    # STEP 1: THE INTERVIEW
    elif st.session_state.interview_step == 1:
        st.subheader(f"Interview for: {st.session_state.temp_book['title']}")
        
        if "ai_question" not in st.session_state:
            with st.spinner("AI is preparing questions..."):
                q_prompt = f"I finished '{st.session_state.temp_book['title']}'. Ask me 2 serious, specific questions to help you rate it."
                st.session_state.ai_question = model.generate_content(q_prompt).text
        
        st.info(st.session_state.ai_question)
        user_response = st.text_area("Your Answer:", height=150)

        if st.button("Submit & Finalize"):
            with st.spinner("Analyzing and saving..."):
                final_prompt = f"""
                Book: {st.session_state.temp_book['title']} by {st.session_state.temp_book['author']}
                User notes: {user_response}
                Based on this, return EXACTLY this format:
                SCORE: [1-10] | GENRE: [1 word] | REVIEW: [2 paragraphs] | SIMILAR: [2 books]
                """
                res = model.generate_content(final_prompt).text
                
                try:
                    parts = res.split("|")
                    score = parts[0].split(":")[1].strip()
                    genre = parts[1].split(":")[1].strip()
                    review = parts[2].split(":")[1].strip()
                    sims = parts[3].split(":")[1].strip()

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
                    
                    st.balloons()
                    st.success("Successfully Saved!")
                    st.session_state.interview_step = 0
                    del st.session_state.ai_question
                    st.rerun()
                except:
                    st.error("AI formatting error. Try clicking 'Submit' again.")

with tab2:
    df, _ = get_csv_from_github()
    if not df.empty:
        df["score"] = pd.to_numeric(df["score"], errors='coerce')
        st.subheader("⭐ Top 10 Books")
        st.table(df.sort_values(by="score", ascending=False).head(10)[["title", "author", "score"]])
        st.subheader("All Records")
        st.dataframe(df)
    else:
        st.info("Your library is empty.")
