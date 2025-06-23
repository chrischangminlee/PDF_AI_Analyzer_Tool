import streamlit as st
import tempfile, os
from services.pdf_service import annotate_pdf_with_page_numbers, upload_pdf_to_gemini, convert_pdf_to_images
from services.gemini_service import find_relevant_pages_with_gemini, parse_page_info

# === 1단계 UI & 로직 (원본 섹션 4) 전체 붙여넣기 ===
def run_upload_step():
    st.header("1단계: PDF 업로드 및 질문 입력")
    # ... (원본 섹션 4의 코드 전부) ...
