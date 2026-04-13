import streamlit as st
import pandas as pd
import google.generativeai as genai
from github import Github
import io
import json
from datetime import datetime

# --- 1. CONFIGURATION ---
genai.configure(api_key=st.secrets["GEMINI_KEY"])
# Using the most stable 2026 alias
model = genai.GenerativeModel('gemini-1.5-flash')

g = Github(st.secrets["GITHUB_TOKEN"])
repo = g.get_repo(st.secrets["REPO_NAME"])

# --- 2. SESSION STATE (The App's Memory) ---
if "interview_step" not in st.session_state:
    st.session_state.update({
        "interview_step": 0,
        "q_count": 0,
        "answers": [],
        "temp_book": {}
    })

# --- 3. DATA HELPERS ---
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
    repo.update_file("books.csv", "Deep Interview Entry", csv_buf.getvalue(), sha)

# --- 4. UI SETUP ---
st.set_page_config(page_title="BookVault AI", layout="wide", page_icon="📚")
st.title("📚 Deep Interview Book Vault")

tab1, tab2, tab3 = st.tabs(["➕ Add Book", "📖 Library", "📊 Insights"])

with tab1:
    # --- PHASE 0: EXPANDED INPUT ---
    if st.session_state.interview_step == 0:
        st.subheader("Step 1: Book Essentials")
        with st.form("init_form"):
            col1, col2 = st.columns(2)
            t = col1.text_input("Book Title", placeholder="e.g. Night Road")
            a = col1.text_input("Author", placeholder="e.g. Kristin Hannah")
            g = col2.text_input("Genre", placeholder="e.g. Contemporary Fiction")
            m = col2.selectbox("Your Reading Mood", ["Reflective", "Emotional", "Adventurous", "Tired", "Stressed"])
            
            if st.form_submit_button("Start Multi-Question Interview"):
                if t and a:
                    st.session_state.temp_book = {"title": t, "author": a, "genre": g, "mood": m}
                    st.session_state.interview_step = 1
                    st.rerun()
                else:
                    st.error("Title and Author are required to start.")

    # --- PHASE 1: LOOPING INTERVIEW (3 QUESTIONS) ---
    elif st.session_state.interview_step == 1:
        current_q = st.session_state.q_count + 1
        st.subheader(f"Step 2: The Interview ({current_q} of 3)")
        
        # Determine the Question
        with st.spinner("AI is formulating a question..."):
            try:
                context = " ".join(st.session_state.answers)
                q_prompt = f"I am reviewing '{st.session_state.temp_book['title']}'. My current thoughts: {context}. Ask one serious, short question about the plot or characters."
                question = model.generate_content(q_prompt).text
            except Exception:
                # Fallback Questions if API fails
                fallbacks = [
                    "What was the most difficult choice a character had to make?",
                    "How did the setting of the book influence the story's mood?",
                    "Would you recommend this book to someone else? Why or why not?"
                ]
                question = fallbacks[st.session_state.q_count]

        st.info(f"**AI asks:** {question}")
        user_ans = st.text_input("Your Response:", key=f"ans_{st.session_state.q_count}")

        if st.button("Submit Answer"):
            if user_ans:
                st.session_state.answers.append(f"Q: {question} A: {user_ans}")
                if st.session_state.q_count < 2:
                    st.session_state.q_count += 1
                else:
                    st.session_state.interview_step = 2
                st.rerun()
            else:
                st.warning("Please provide an answer before moving on.")

    # --- PHASE 2: FINALIZING ---
    elif st.session_state.interview_step == 2:
        st.subheader("Step 3: Final Rating")
        manual_score = st.slider("Select your final score (1-10)", 1, 10, 7)
        
        if st.button("Synthesize & Save Library Entry"):
            with st.spinner("Compiling your deep review..."):
                all_notes = " ".join(st.session_state.answers)
                f_prompt = f"""
                Review '{st.session_state.temp_book['title']}' using these notes: {all_notes}.
                User manually rated it {manual_score}/10. 
                Return ONLY a JSON object:
                {{"score": {manual_score}, "genre": "{st.session_state.temp_book['genre'] or 'Auto'}", "review": "2 paragraphs", "similarities": "2 books"}}
                """
                try:
                    res = model.generate_content(f_prompt).text
                    res_clean = res.replace("```json", "").replace("```", "").strip()
                    data = json.loads(res_clean)
                except:
                    data = {"score": manual_score, "genre": st.session_state.temp_book['genre'] or "Fiction", "review": all_notes, "similarities": "TBD"}

                df, sha = get_data()
                new_row = {
                    "title": st.session_state.temp_book['title'],
                    "author": st.session_state.temp_book['author'],
                    "genre": data['genre'] if data['genre'] != "Auto" else "General",
                    "date_read": datetime.now().strftime("%Y-%m-%d"),
                    "score": manual_score,
                    "mood": st.session_state.temp_book['mood'],
                    "ai_review": data['review'],
                    "similarities": data['similarities']
                }
                
                df = pd.concat([df, pd.DataFrame([new_row])], ignore_index=True)
                save_data(df, sha)
                
                # Full Reset
                st.session_state.update({"interview_step": 0, "q_count": 0, "answers": [], "temp_book": {}})
                st.balloons()
                st.success("Deep Review successfully logged to GitHub!")
                st.rerun()

# --- TAB 2: LIBRARY VIEW ---
with tab2:
    df, _ = get_data()
    if not df.empty:
        st.subheader("Your Organized Library")
        st.dataframe(df[["title", "author", "genre", "score", "mood", "date_read"]], use_container_width=True, hide_index=True)
        
        with st.expander("Read Full AI Reviews"):
            for _, row in df.iterrows():
                st.write(f"**{row['title']}** ({row['score']}/10)")
                st.write(row["ai_review"])
                st.divider()
    else:
        st.info("No books logged yet.")

# --- TAB 3: INSIGHTS ---
with tab3:
    df, _ = get_data()
    if not df.empty:
        st.subheader("Your Reading DNA")
        st.bar_chart(df["mood"].value_counts())
        st.subheader("Top Rated Books")
        st.table(df.sort_values(by="score", ascending=False).head(5)[["title", "score"]])
