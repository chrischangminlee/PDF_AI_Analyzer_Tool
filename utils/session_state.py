import streamlit as st

# 세션 상태 키·초기값 일괄 세팅
def init_session_state():
    if 'relevant_pages' not in st.session_state:
        st.session_state.relevant_pages = []
    if 'page_info' not in st.session_state:
        st.session_state.page_info = {}
    if 'selected_pages' not in st.session_state:
        st.session_state.selected_pages = []
    if 'user_prompt' not in st.session_state:
        st.session_state.user_prompt = ""
    if 'original_pdf_bytes' not in st.session_state:
        st.session_state.original_pdf_bytes = None
    if 'pdf_images' not in st.session_state:
        st.session_state.pdf_images = []
    if 'step' not in st.session_state:
        st.session_state.step = 1
