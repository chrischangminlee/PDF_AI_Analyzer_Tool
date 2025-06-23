import streamlit as st
from services.pdf_service import convert_pdf_to_images  # 필요 시

# === 2단계 UI & 로직 (원본 섹션 5) ===
def run_page_selection_step():
    # ... 원본 섹션 5 코드 전부 ...
    if st.session_state.step >= 2 and st.session_state.relevant_pages:
        st.header("2단계: 관련 페이지 확인 & 선택")
        st.write(f"**AI 추천 페이지 수:** {len(st.session_state.relevant_pages)}개")
        st.write("선별된 페이지위에 마우스를 올리면 나타나는 확대 버튼으로 내용을 확인할 수 있어요.")

        top_msg, top_btn = st.empty(), st.empty()
        selected_pages = []

        cols = st.columns(3)
        for i, p in enumerate(st.session_state.relevant_pages):
            with cols[i % 3]:
                with st.container(border=True):
                    cb_col, txt_col = st.columns([1, 5])
                    with cb_col:
                        if st.checkbox("", key=f"cb_{p}", label_visibility="collapsed"):
                            selected_pages.append(p)
                    with txt_col:
                        st.markdown(f"**📄 관련 페이지**")

                    if p in st.session_state.page_info:
                        info = st.session_state.page_info[p]
                        page_response, relevance = info.get('page_response', ''), info.get('relevance', '')

                        if relevance == '상':
                            color, bg_color = "🔴", "#ffe6e6"
                        elif relevance == '중':
                            color, bg_color = "🟡", "#fff9e6"
                        else:
                            color, bg_color = "⚪", "#f0f0f0"

                        st.markdown(f"""
                        <div style="background-color: {bg_color}; padding: 8px; border-radius: 5px; margin: 5px 0;">
                            <div style="font-size: 0.8em; font-weight: bold;">{color} 관련도: {relevance}</div>
                            <div style="font-size: 0.75em; color: #666;">🔑 {page_response}</div>
                        </div>""", unsafe_allow_html=True)

                    if p - 1 < len(st.session_state.pdf_images):
                        st.image(st.session_state.pdf_images[p - 1], use_column_width=True)

        st.session_state.selected_pages = selected_pages

        if selected_pages:
            top_msg.success(f"선택된 페이지: {len(selected_pages)}개")
            if top_btn.button("선택된 페이지만으로 최종 분석 실행", type="primary", key="run_top"):
                st.session_state.step = 3
                st.rerun()
        else:
            top_msg.info("분석할 페이지를 선택해주세요.")

        st.markdown("---")
        if selected_pages:
            if st.button("선택된 페이지만으로 최종 분석 실행", type="primary", key="run_bottom"):
                st.session_state.step = 3
                st.rerun()