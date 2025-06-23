import streamlit as st

# 세션 상태 키·초기값 일괄 세팅
def init_session_state():
    defaults = {
        'relevant_pages': [],
        'page_info': {},
        'selected_pages': [],
        'user_prompt': "",
        'original_pdf_bytes': None,
        'pdf_images': [],
        'step': 1,
    }
    for k, v in defaults.items():
        if k not in st.session_state:
            st.session_state[k] = v
