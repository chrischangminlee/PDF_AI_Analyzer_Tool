import streamlit as st

def init_session_state():
    """세션 상태 초기화"""
    if 'relevant_pages' not in st.session_state:
        st.session_state.relevant_pages = []
    if 'page_info' not in st.session_state:
        st.session_state.page_info = {}
    if 'user_prompt' not in st.session_state:
        st.session_state.user_prompt = ""
    if 'original_pdf_bytes' not in st.session_state:
        st.session_state.original_pdf_bytes = None
    if 'pdf_images' not in st.session_state:
        st.session_state.pdf_images = []