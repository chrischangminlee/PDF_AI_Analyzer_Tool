import io, os, tempfile
import streamlit as st
from PyPDF2 import PdfReader, PdfWriter
import google.generativeai as genai
from .pdf_service import upload_pdf_to_gemini  # 같은 폴더의 함수 사용

# Gemini 관련 파싱
def parse_page_info(gemini_response):
    pages, page_info = [], {}
    for line in gemini_response.strip().split('\n'):
        if '|' in line:
            try:
                parts = line.strip().split('|')
                if len(parts) == 3:
                    physical_page, page_response, relevance = int(parts[0].strip()), parts[1].strip(), parts[2].strip()
                    pages.append(physical_page)
                    page_info[physical_page] = {'page_response': page_response, 'relevance': relevance}
            except (ValueError, IndexError):
                continue
    return pages, page_info

# 관련 페이지 찾기
def find_relevant_pages_with_gemini(uploaded_file, user_prompt):
    try:
        prompt = f"""(원본 프롬프트 그대로)"""
        model = genai.GenerativeModel('gemini-2.0-flash')
        resp = model.generate_content([uploaded_file, prompt])
        return resp.text.strip()
    except Exception as e:
        st.error(f"Gemini 호출 오류: {e}")
        return ""

# 최종 답변 생성
def generate_final_answer_from_selected_pages(selected_pages, user_prompt, original_pdf_bytes):
    if not selected_pages:
        return "선택된 페이지가 없습니다."

    reader = PdfReader(io.BytesIO(original_pdf_bytes))
    writer = PdfWriter()
    for p in sorted(selected_pages):
        if 1 <= p <= len(reader.pages):
            writer.add_page(reader.pages[p - 1])

    with tempfile.NamedTemporaryFile(delete=False, suffix=".pdf") as tmp:
        writer.write(tmp)
        tmp_path = tmp.name
    try:
        uploaded_sel = upload_pdf_to_gemini(tmp_path)
    finally:
        os.unlink(tmp_path)

    prompt = f"""(원본 프롬프트 그대로)"""
    model = genai.GenerativeModel("gemini-2.0-flash")
    resp = model.generate_content([uploaded_sel, prompt])
    return resp.text
