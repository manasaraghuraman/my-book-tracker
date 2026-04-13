import streamlit as st
import pandas as pd
import google.generativeai as genai
from github import Github
import io
from datetime import datetime

# --- CONFIGURATION ---
GITHUB_TOKEN = st.secrets["GITHUB_TOKEN"]
REPO_NAME = st.secrets["REPO_NAME"] 
GEMINI_KEY = st.secrets["GEMINI_KEY"]

# Setup Gemini (Updated for 2026)
genai.configure(api_key=GEMINI_KEY)
model = genai.GenerativeModel('gemini-3-flash-preview') # Current 2026 version

# Setup GitHub
g = Github(GITHUB_TOKEN)
repo = g.get_repo(REPO_NAME)

def get_csv_from_github():
    try:
        file_content = repo.get_contents("books.csv")
        df = pd.read_csv(io.StringIO(file_content.decoded_content.decode()))
        return df, file_content.sha
    except Exception:
        # If file is missing or broken, return empty DF with correct headers
        cols = ["title","author","genre","date_read","score","mood","ai_review","similarities"]
        return pd.DataFrame(columns=cols), None

def save_to_github(df, sha):
    csv_buffer = io.StringIO()
    df.to_csv(csv_buffer, index=False)
    if sha:
        repo.update_file("books.csv", "Update books", csv_buffer.getvalue(), sha)
    else:
        repo.create_file("books.csv", "Initial books file", csv_buffer.getvalue())

# --- APP UI ---
st.set_page_config(page_title="Book Vault", layout="wide")
st.title("📚 AI Book Vault")

tab1, tab2 = st.tabs(["➕ Add New Book", "📖 My Library"])

with tab1:
    with st.form("book_form", clear_on_submit=True):
        col1, col2 = st.columns(2)
        title = col1.text_input("Book Title")
        author = col1.text_input("Author")
        mood = col2.selectbox("Your Reading Mood", ["Curious", "Emotional", "Stressed", "Adventurous"])
        notes = st.text_area("Your thoughts (AI will use these to rate the book)")
        submit = st.form_submit_button("Analyze & Save")

    if submit and title:
        with st.spinner("AI is thinking..."):
            prompt = f"Analyze '{title}' by {author}. Notes: {notes}. Mood: {mood}. Return format: Score(1-10)|2-para review|2 similar books"
            try:
                response = model.generate_content(prompt).text
                parts = response.split("|")
                score = parts[0].strip()
                review = parts[1].strip()
                sims = parts[2].strip()

                df, sha = get_csv_from_github()
                new_data = {
                    "title": title, "author": author, "genre": "TBD",
                    "date_read": datetime.now().strftime("%Y-%m-%d"),
                    "score": score, "mood": mood, "ai_review": review, "similarities": sims
                }
                df = pd.concat([df, pd.DataFrame([new_data])], ignore_index=True)
                save_to_github(df, sha)
                st.success(f"Added {title}!")
            except Exception as e:
                st.error(f"AI Error: {e}")

with tab2:
    df, _ = get_csv_from_github()
    
    # SAFETY: Check if 'score' exists before sorting
    if not df.empty and "score" in df.columns:
        df["score"] = pd.to_numeric(df["score"], errors='coerce')
        
        st.subheader("⭐ Top 10 Books")
        st.table(df.sort_values(by="score", ascending=False).head(10)[["title", "author", "score"]])
        
        st.subheader("Full Library")
        st.dataframe(df)
    else:
        st.info("Your library is empty! Go to the first tab to add a book.")
