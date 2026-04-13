import streamlit as st
import pandas as pd
import google.generativeai as genai
from github import Github
import io
import json
from datetime import datetime

# --- CONFIG ---
genai.configure(api_key=st.secrets["GEMINI_KEY"])
model = genai.GenerativeModel('gemini-1.5-flash-latest')
g = Github(st.secrets["GITHUB_TOKEN"])
repo = g.get_repo(st.secrets["REPO_NAME"])

# --- SESSION STATE INITIALIZATION ---
if "interview_step" not in st.session_state:
    st.session_state.interview_step = 0
if "temp_book" not in st.session_state:
    st.session_state.temp_book = {}
if "ai_question" not in st.session_state:
    st.session_state.ai_question = ""

# --- DATA HELPERS ---
def get_data():
    try:
        content = repo.get_contents("books.csv")
        return pd.read_csv(io.StringIO(content.decoded_content.decode())), content.sha
    except:
        return pd.DataFrame(columns=["title","author","genre","date_read","score","mood","ai_review","similarities"]), None

def save_data(df, sha):
    csv_buf = io.StringIO()
    df.to_csv(csv_buf, index=False)
    repo.update_file("books.csv", "Update", csv_buf.getvalue(), sha)

# --- UI SETUP ---
st.set_page_config(page_title="BookVault AI", layout="wide")
st.title("📚 BookVault AI")

tabs = st.tabs(["➕ Add Book", "📖 Library", "📊 Insights & Recs"])

# --- TAB 1: INTERVIEW ---
with tabs[0]:
    if st.session_state.interview_step == 0:
        with st.form("start"):
            t = st.text_input("Book Title")
            a = st.text_input("Author")
            m = st.selectbox("Mood", ["Happy", "Sad", "Adventurous", "Tired", "Reflective"])
            if st.form_submit_button("Start Interview"):
                st.session_state.update({"temp_book": {"title":t, "author":a, "mood":m}, "interview_step": 1})
                st.rerun()

    elif st.session_state.interview_step == 1:
        st.subheader(f"Interviewing: {st.session_state.temp_book.get('title', 'Unknown')}")
        
        # Safer check using st.session_state.get()
        if not st.session_state.get("ai_question"):
            with st.spinner("AI is preparing questions..."):
                q_res = model.generate_content(f"Ask 2 deep questions about '{st.session_state.temp_book.get('title')}' to help me review it.")
                st.session_state.ai_question = q_res.text
        
        st.info(st.session_state.ai_question)
        ans = st.text_area("Your thoughts:")
        
        # New Feature: Manual Rating Slider
        manual_score = st.slider("Manual Rating (1-10)", 1, 10, 7)
        
        if st.button("Finalize"):
            with st.spinner("AI is organizing your data..."):
                prompt = f"""
                Analyze the book '{st.session_state.temp_book['title']}' using my notes: '{ans}'.
                The user manually rated it {manual_score}/10. 
                Return a JSON object exactly like this:
                {{"score": {manual_score}, "genre": "one word", "review": "2 paragraphs", "similarities": "2 books"}}
                """
                res = model.generate_content(prompt).text
                # Clean JSON string from AI
                res_clean = res.replace("```json", "").replace("```", "").strip()
                data = json.loads(res_clean)

                df, sha = get_data()
                new_row = {**st.session_state.temp_book, "date_read": datetime.now().strftime("%Y-%m-%d"), **data, "ai_review": data['review']}
                df = pd.concat([df, pd.DataFrame([new_row])], ignore_index=True)
                save_data(df, sha)
                
                st.session_state.update({"interview_step": 0, "ai_question": ""})
                st.success("Saved!")
                st.rerun()

# --- TAB 2: CLEAN LIBRARY ---
with tabs[1]:
    df, _ = get_data()
    if not df.empty:
        # Custom Column Formatting
        st.dataframe(df[["title", "author", "score", "genre", "date_read", "mood"]], 
                     use_container_width=True, hide_index=True)
        
        selected_book = st.selectbox("View AI Review for:", df["title"])
        review_text = df[df["title"] == selected_book]["ai_review"].values[0]
        st.write(f"**AI Review:** {review_text}")
    else:
        st.write("Library empty.")

# --- TAB 3: INSIGHTS & RECS ---
with tabs[2]:
    df, _ = get_data()
    if not df.empty:
        col1, col2 = st.columns(2)
        with col1:
            st.subheader("⭐ Top 10")
            st.table(df.sort_values(by="score", ascending=False).head(10)[["title", "score"]])
        
        with col2:
            st.subheader("🧠 Reading Moods")
            st.bar_chart(df["mood"].value_counts())

        st.divider()
        st.subheader("✨ AI Recommendations")
        if st.button("Get Future Recommendations"):
            history = ", ".join(df["title"].tolist())
            rec_res = model.generate_content(f"Based on my history: {history}, suggest 3 books I should read next and why.")
            st.write(rec_res.text)
