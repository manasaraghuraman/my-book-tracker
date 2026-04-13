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
# Using the April 2026 stable model
model = genai.GenerativeModel('gemini-3.1-flash-lite-preview')

g = Github(GITHUB_TOKEN)
repo = g.get_repo(REPO_NAME)

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
    repo.update_file("books.csv", "Update books", csv_buffer.getvalue(), sha)

st.title("📚 My Smart Book Vault")

tab1, tab2 = st.tabs(["➕ Add Book", "📖 Library"])

with tab1:
    with st.form("book_form", clear_on_submit=True):
        title = st.text_input("Book Title")
        author = st.text_input("Author")
        notes = st.text_area("Notes (What did you think?)")
        mood = st.selectbox("Mood", ["Happy", "Sad", "Adventurous", "Tired", "Curious"])
        submit = st.form_submit_button("Analyze & Save")

    if submit and title:
        with st.spinner("AI is analyzing..."):
            # Refined prompt for better reliability
            prompt = (f"Analyze the book '{title}' by {author}. Notes: {notes}. Mood: {mood}. "
                      "Provide: 1. A score (1-10), 2. A 2-paragraph review, 3. Two similar books. "
                      "Format your response exactly like this: SCORE: [num] | REVIEW: [text] | SIMILAR: [text]")
            
            response = model.generate_content(prompt).text
            
            # SAFE PARSING: This prevents the 'index out of range' error
            if "|" in response and len(response.split("|")) >= 3:
                parts = response.split("|")
                score = parts[0].replace("SCORE:", "").strip()
                review = parts[1].replace("REVIEW:", "").strip()
                sims = parts[2].replace("SIMILAR:", "").strip()

                df, sha = get_csv_from_github()
                new_row = {
                    "title": title, "author": author, "genre": "TBD",
                    "date_read": datetime.now().strftime("%Y-%m-%d"),
                    "score": score, "mood": mood, "ai_review": review, "similarities": sims
                }
                df = pd.concat([df, pd.DataFrame([new_row])], ignore_index=True)
                save_to_github(df, sha)
                st.success(f"Successfully added {title}!")
            else:
                st.error("The AI gave a messy response. Try typing more than just 'hello' so it has something to analyze!")

with tab2:
    df, _ = get_csv_from_github()
    if not df.empty:
        st.subheader("⭐ Top 10")
        df["score"] = pd.to_numeric(df["score"], errors='coerce')
        st.table(df.sort_values(by="score", ascending=False).head(10)[["title", "author", "score"]])
        st.subheader("Full History")
        st.dataframe(df)
    else:
        st.write("No books yet!")
