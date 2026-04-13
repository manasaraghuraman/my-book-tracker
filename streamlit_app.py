# --- REFRESHED INTERVIEW LOGIC ---
if st.session_state.interview_step == 1:
    st.subheader(f"Interview for: {st.session_state.temp_book['title']}")
    
    # Generate the question if it doesn't exist
    if "ai_question" not in st.session_state:
        with st.spinner("AI is reading the summary..."):
            q_prompt = f"I finished '{st.session_state.temp_book['title']}'. Ask me 2-3 deep, serious questions to help you rank this book and write a blog review. Be specific to the book if you know it."
            try:
                q_res = model.generate_content(q_prompt)
                st.session_state.ai_question = q_res.text
            except Exception as e:
                st.error(f"Model Error: {e}. Try changing the model name to gemini-3.1-flash-lite-preview.")

    st.info(st.session_state.ai_question)
    user_response = st.text_area("Your deep thoughts:", placeholder="Type your answers here...")

    if st.button("Finish & Rank"):
        if len(user_response) < 10:
            st.warning("Write a bit more so the AI can give you a better ranking!")
        else:
            with st.spinner("Analyzing your responses..."):
                final_prompt = f"""
                Review the book '{st.session_state.temp_book['title']}' based on these answers: {user_response}.
                Provide:
                SCORE: [number 1-10] | GENRE: [Type] | REVIEW: [2 paragraphs] | SIMILAR: [2 books]
                """
                full_res = model.generate_content(final_prompt).text
                
                # Bulletproof Parsing
                try:
                    # We look for the pipes, but if the AI forgets them, we don't crash
                    parts = full_res.split("|")
                    score = parts[0].split(":")[-1].strip() if ":" in parts[0] else "5"
                    genre = parts[1].split(":")[-1].strip() if len(parts) > 1 else "Unknown"
                    review = parts[2].split(":")[-1].strip() if len(parts) > 2 else "No review generated."
                    sims = parts[3].split(":")[-1].strip() if len(parts) > 3 else "None"

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
                    st.success("Book logged and ranked!")
                    st.session_state.interview_step = 0
                    if "ai_question" in st.session_state: del st.session_state.ai_question
                except Exception as e:
                    st.error("The AI got a bit confused by the formatting. Try clicking 'Finish & Rank' again.")
