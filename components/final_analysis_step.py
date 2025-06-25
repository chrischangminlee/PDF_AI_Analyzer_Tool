import streamlit as st
from services.gemini_service import generate_final_answer_from_selected_pages

# === 3단계 UI & 로직 (원본 섹션 6) ===
def run_final_analysis_step():
    if st.session_state.step >= 3 and st.session_state.selected_pages:
        st.header("3단계: 최종 분석 결과")
        with st.spinner("선별된 페이지로 PDF 최종 AI 분석 중..."):
            answer = generate_final_answer_from_selected_pages(
                st.session_state.selected_pages,
                st.session_state.user_prompt,
                st.session_state.original_pdf_bytes
            )

        st.subheader("📋 분석 결과")
        st.write(f"**질문:** {st.session_state.user_prompt}")
        st.write(f"**분석에 사용된 페이지 수:** {len(st.session_state.selected_pages)}개")
        st.markdown(answer)

        if st.button("새로운 분석 시작"):
            for key in list(st.session_state.keys()):
                del st.session_state[key]
            st.rerun()