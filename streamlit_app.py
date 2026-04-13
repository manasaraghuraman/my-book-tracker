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
    st.session_state.interview_step = 0 # 0=Input, 1=Interviewing, 2=Finalizing
if "q_count" not in st.session_state:
    st.session_state.q_count = 0
if "answers" not in st.session_state:
    st.session_state.answers = []
if "temp_book" not in st.session_state:
    st.session_state.temp_book = {}

# --- DATA HELPERS ---
def get_data():
    try:
        content = repo.get_contents("books.csv")
        return pd.read_csv(io.StringIO(content.decoded_content.decode())), content.sha
    except:
        cols = ["title","author","genre","date_read","score","mood","ai_review","similarities"]
        return pd.DataFrame(columns=cols), None

def save_data(df, sha):
    csv_buf = io.StringIO()
    df.to_csv(csv_buf, index=False)
    repo.update_file("books.csv", "Deep Interview Update", csv_buf.getvalue(), sha)

# --- UI ---
st.set_page_config(page_title="BookVault AI", layout="wide")
st.title("📚 Deep Interview Book Vault")

tab1, tab2, tab3 = st.tabs(["➕ Add Book", "📖 Library", "📊 Insights"])

with tab1:
    # --- PHASE 0: DETAILED INPUT ---
    if st.session_state.interview_step == 0:
        st.subheader("Initial Book Details")
        with st.form("init_form"):
            col1, col2 = st.columns(2)
            t = col1.text_input("Book Title")
            a = col1.text_input("Author")
            g = col2.text_input("Genre (Optional - AI can fill)")
            m = col2.selectbox("Your Reading Mood", ["Reflective", "Happy", "Stressed", "Adventurous"])
            
            if st.form_submit_button("Start Deep Interview"):
                if t and a:
                    st.session_state.temp_book = {"title": t, "author": a, "genre": g, "mood": m}
                    st.session_state.interview_step = 1
                    st.rerun()

    # --- PHASE 1: THE MULTI-QUESTION INTERVIEW ---
    elif st.session_state.interview_step == 1:
        st.subheader(f"Question {st.session_state.q_count + 1} of 3")
        
        # AI generates a question based on the book and previous answers
        context = " ".join(st.session_state.answers)
        q_prompt = f"I am reviewing '{st.session_state.temp_book['title']}'. So far I've said: {context}. Ask me one short, serious question to help you understand my take on the book."
        
        with st.spinner("AI is thinking..."):
            question = model.generate_content(q_prompt).text
        
        st.write(f"### {question}")
        user_ans = st.text_input("Your answer:", key=f"q_{st.session_state.q_count}")

        if st.button("Next Question" if st.session_state.q_count < 2 else "Finish Interview"):
            if user_ans:
                st.session_state.answers.append(user_ans)
                if st.session_state.q_count < 2:
                    st.session_state.q_count += 1
                else:
                    st.session_state.interview_step = 2 # Move to Finalize
                st.rerun()

    # --- PHASE 2: FINALIZING ---
    elif st.session_state.interview_step == 2:
        st.subheader("Final Review")
        manual_score = st.slider("Final Rating", 1, 10, 7)
        
        if st.button("Generate & Save"):
            with st.spinner("Synthesizing your answers..."):
                all_notes = " ".join(st.session_state.answers)
                f_prompt = f"""
                Review '{st.session_state.temp_book['title']}' using these interview answers: {all_notes}.
                The user rated it {manual_score}/10.
                Return JSON: {{"score": {manual_score}, "genre": "{st.session_state.temp_book['genre'] or 'Auto'}", "review": "2 paragraphs", "similarities": "2 books"}}
                """
                res = model.generate_content(f_prompt).text
                res_clean = res.replace("```json", "").replace("```", "").strip()
                data = json.loads(res_clean)

                df, sha = get_data()
                new_row = {**st.session_state.temp_book, "date_read": datetime.now().strftime("%Y-%m-%d"), **data, "ai_review": data['review']}
                # Ensure we use the AI's detected genre if user left it blank
                if new_row['genre'] == "Auto": new_row['genre'] = data['genre']
                
                df = pd.concat([df, pd.DataFrame([new_row])], ignore_index=True)
                save_data(df, sha)
                
                # RESET EVERYTHING
                for key in ["interview_step", "q_count", "answers", "temp_book"]:
                    st.session_state[key] = 0 if key == "interview_step" or key == "q_count" else ([] if key == "answers" else {})
                st.success("Deep Review Saved!")
                st.rerun()

# --- TABS 2 & 3: REMAINS THE SAME BUT CLEANER ---
with tab2:
    df, _ = get_data()
    if not df.empty:
        st.dataframe(df, use_container_width=True, hide_index=True)
with tab3:
    st.write("Reading insights here...")
