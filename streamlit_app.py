import streamlit as st
import pandas as pd
import google.generativeai as genai
from github import Github
import io
from datetime import datetime

# --- CONFIGURATION (Use Streamlit Secrets for Keys) ---
GITHUB_TOKEN = st.secrets["GITHUB_TOKEN"]
REPO_NAME = st.secrets["REPO_NAME"]  # e.g., "username/repo-name"
GEMINI_KEY = st.secrets["GEMINI_KEY"]

# Setup Gemini
genai.configure(api_key=GEMINI_KEY)
model = genai.GenerativeModel('gemini-1.5-flash')

# Setup GitHub
g = Github(GITHUB_TOKEN)
repo = g.get_repo(REPO_NAME)

# --- HELPER FUNCTIONS ---
def get_csv_from_github():
    file_content = repo.get_contents("books.csv")
    return pd.read_csv(io.StringIO(file_content.decoded_content.decode())), file_content.sha

def save_to_github(df, sha):
    csv_buffer = io.StringIO()
    df.to_csv(csv_buffer, index=False)
    repo.update_file("books.csv", "Update books from App", csv_buffer.getvalue(), sha)

# --- APP UI ---
st.title("📚 AI Book Vault")

tab1, tab2 = st.tabs(["Add New Book", "My Library"])

with tab1:
    st.header("Log a Read")
    with st.form("book_form", clear_on_submit=True):
        title = st.text_input("Book Title")
        author = st.text_input("Author")
        notes = st.text_area("Your rough thoughts/rating (The AI will interview these notes)")
        mood = st.selectbox("Your Current Mood", ["Happy", "Melancholy", "Adventurous", "Tired", "Curious"])
        submit = st.form_submit_button("Analyze & Save")

    if submit:
        with st.spinner("AI is analyzing..."):
            # The AI Logic
            prompt = f"""
            I just read '{title}' by {author}. My notes: {notes}. 
            Current mood: {mood}.
            Please:
            1. Assign a Score (1-10).
            2. Write a 2-paragraph review for my blog.
            3. List 2 similar books I might like.
            Return ONLY in this format: Score|Review|Similarities
            """
            response = model.generate_content(prompt).text
            score, review, similarities = response.split("|")

            # Update CSV
            df, sha = get_csv_from_github()
            new_row = {
                "title": title, "author": author, "genre": "Auto-Detecting...", 
                "date_read": datetime.now().strftime("%Y-%m-%d"),
                "score": score.strip(), "mood": mood, 
                "ai_review": review.strip(), "similarities": similarities.strip()
            }
            df = pd.concat([df, pd.DataFrame([new_row])], ignore_index=True)
            save_to_github(df, sha)
            st.success(f"Saved {title}!")

with tab2:
    st.header("Your Organized Library")
    df, _ = get_csv_from_github()
    
    # Auto-Organizer: Top 10
    st.subheader("⭐ Top 10 Books Ever")
    top_10 = df.sort_values(by="score", ascending=False).head(10)
    st.table(top_10[["title", "author", "score"]])

    # Full List with Search
    st.subheader("All Records")
    st.dataframe(df)
