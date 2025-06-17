# app.py (수정 반영 전체 코드)

import streamlit as st
import google.generativeai as genai
from dotenv import load_dotenv
import os, io, tempfile
from PyPDF2 import PdfReader, PdfWriter
from pdf2image import convert_from_bytes
from PIL import Image
# ★NEW★ 번호 오버레이용
from reportlab.pdfgen import canvas
from reportlab.lib.units import mm

# ──────────────────────────
# 0. 환경설정
# ──────────────────────────
load_dotenv()
st.set_page_config(page_title="이창민의 PDF AI 세부 분석 Tool", layout="wide")

def get_api_key():
    if 'gemini_api_key' in st.secrets:
        return st.secrets['gemini_api_key']
    return os.getenv('GEMINI_API_KEY')

api_key = get_api_key()
if not api_key:
    st.error('Gemini API 키가 설정되지 않았습니다. .env 파일이나 Streamlit secrets에 API 키를 설정해주세요.')
    st.stop()
genai.configure(api_key=api_key)

# ──────────────────────────
# 1. PDF에 페이지 번호 새기기 ★NEW★
# ──────────────────────────
def add_page_numbers_to_pdf(pdf_bytes: bytes) -> bytes:
    """PDF 각 페이지 좌측 상단에 'P{물리적번호}'를 새겨서
    다시 PDF 바이트로 반환한다."""
    reader = PdfReader(io.BytesIO(pdf_bytes))
    writer = PdfWriter()

    for idx, page in enumerate(reader.pages, start=1):
        # ReportLab 캔버스 생성 (페이지 크기 동일)
        packet = io.BytesIO()
        width = float(page.mediabox.width)
        height = float(page.mediabox.height)
        c = canvas.Canvas(packet, pagesize=(width, height))
        c.setFont("Helvetica-Bold", 10)
        # 좌측 상단(10, height-20)에 그리기
        c.drawString(10, height - 20, f"P{idx}")
        c.save()

        packet.seek(0)
        overlay = PdfReader(packet)
        page.merge_page(overlay.pages[0])     # 오버레이 결합
        writer.add_page(page)

    out = io.BytesIO()
    writer.write(out)
    return out.getvalue()

# ──────────────────────────
# 2. PDF → 이미지 (번호가 찍힌 PDF 기준) ★MOD★
# ──────────────────────────
def convert_pdf_to_images(pdf_bytes):
    try:
        return convert_from_bytes(pdf_bytes, dpi=100, fmt='jpeg')
    except Exception as e:
        st.warning(f"이미지 변환 오류: {e}")
        return []

# ──────────────────────────
# 3. Gemini 업로드 유틸
# ──────────────────────────
def upload_pdf_to_gemini(pdf_path):
    return genai.upload_file(pdf_path, mime_type="application/pdf")

# (사이드바 & 디버그 영역﻿         – 변경 없음)

# ──────────────────────────
# 4. 세션 상태 초기화
# ──────────────────────────
for k, v in {
    'relevant_pages': [],
    'page_info': {},
    'selected_pages': [],
    'user_prompt': "",
    'original_pdf_bytes': None,
    'annotated_pdf_bytes': None,          # ★NEW★
    'pdf_images': [],
    'step': 1,
}.items():
    if k not in st.session_state:
        st.session_state[k] = v

# ──────────────────────────
# 5. Gemini 응답 파싱 (변경 없음)
# ──────────────────────────
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
            except (ValueError, IndexError): continue
    return pages, page_info

# ──────────────────────────
# 6. Gemini 관련 페이지 찾기 프롬프트 ★MOD★
# ──────────────────────────
def find_relevant_pages_with_gemini(uploaded_file, user_prompt):
    try:
        prompt = f"""
당신은 PDF의 각 페이지를 독립적으로 분석하는 엔진입니다.

## 사용자 질문
{user_prompt}

## 추가 규칙
- 이 PDF는 **모든 페이지 좌측 상단에 'P{{물리적번호}}'** 표기가 있습니다.  
  분석·답변·출력 시 반드시 이 번호만 사용하십시오.
- 관련도 '하'는 제외하고, '상'·'중' 최대 10개.

## 응답 형식
물리적페이지번호|페이지별답변|관련도
        """
        model = genai.GenerativeModel('gemini-2.0-flash')
        resp = model.generate_content([uploaded_file, prompt])
        return resp.text.strip()
    except Exception as e:
        st.error(f"Gemini 호출 오류: {e}")
        return ""

# ──────────────────────────
# 7. 최종 답변 생성 (annotated PDF 사용) ★MOD★
# ──────────────────────────
def generate_final_answer_from_selected_pages(selected_pages, user_prompt):
    if not selected_pages:
        return "선택된 페이지가 없습니다."

    reader = PdfReader(io.BytesIO(st.session_state.annotated_pdf_bytes))
    writer = PdfWriter()
    sorted_pages = sorted(selected_pages)

    for p in sorted_pages:
        if 1 <= p <= len(reader.pages):
            writer.add_page(reader.pages[p - 1])

    with tempfile.NamedTemporaryFile(delete=False, suffix=".pdf") as tmp:
        writer.write(tmp)
        tmp_path = tmp.name
    try:
        uploaded_sel = upload_pdf_to_gemini(tmp_path)
    finally:
        os.unlink(tmp_path)

    prompt = f"""
당신은 문서 분석 전문가입니다.  
주어진 PDF는 좌측 상단 'P{{n}}' 번호가 찍혀 있으며, 사용자 질문에 맞춰 답하십시오.

## 사용자 질문
{user_prompt}
    """
    model = genai.GenerativeModel("gemini-2.0-flash")
    resp = model.generate_content([uploaded_sel, prompt])
    return resp.text

# ──────────────────────────
# 8. 1단계: 업로드 & 질문 입력 ★MOD★
# ──────────────────────────
st.header("1단계: PDF 업로드 및 질문 입력")
with st.form("upload_form"):
    col1, col2 = st.columns(2)
    with col1:
        pdf_file = st.file_uploader("PDF 파일을 선택하세요", type=['pdf'])
    with col2:
        user_prompt_input = st.text_input("분석 요청사항 입력", placeholder="예: 요구자본의 정의 알려줘")
    submitted = st.form_submit_button("PDF 분석 시작", type="primary")

if submitted and pdf_file and user_prompt_input:
    with st.spinner("PDF 업로드 및 AI 분석 중..."):
        # 세션 리셋
        for k in ['relevant_pages', 'page_info', 'selected_pages', 'pdf_images']:
            st.session_state[k] = []
        st.session_state.original_pdf_bytes = pdf_file.read()
        st.session_state.user_prompt = user_prompt_input

        # ★번호 오버레이 적용★
        annotated_bytes = add_page_numbers_to_pdf(st.session_state.original_pdf_bytes)
        st.session_state.annotated_pdf_bytes = annotated_bytes

        # Gemini 업로드
        with tempfile.NamedTemporaryFile(delete=False, suffix=".pdf") as tmp:
            tmp.write(annotated_bytes)
            tmp_path = tmp.name
        try:
            uploaded_file = upload_pdf_to_gemini(tmp_path)
        finally:
            os.unlink(tmp_path)

        # 이미지 변환 (번호가 찍힌 PDF 기준)
        st.session_state.pdf_images = convert_pdf_to_images(annotated_bytes)

        # Gemini로 관련 페이지 찾기
        pages_response = find_relevant_pages_with_gemini(uploaded_file, user_prompt_input)
        pages, page_info = parse_page_info(pages_response)
        total_pages = len(st.session_state.pdf_images)
        st.session_state.relevant_pages = list(dict.fromkeys([p for p in pages if 1 <= p <= total_pages]))
        st.session_state.page_info = page_info
        st.session_state.step = 2
        st.success("AI가 관련 페이지를 찾았습니다!")
        st.rerun()

# ──────────────────────────
# 9. 2단계·3단계 로직 (변경 없음 – pdf_images/annotated_pdf_bytes 사용)
#     … 이하 기존 코드 그대로 …
# ──────────────────────────
# ───────────────────────────────────────────────
# 5. 2단계: 페이지 선택
# ───────────────────────────────────────────────
if st.session_state.step >= 2 and st.session_state.relevant_pages:
    st.header("2단계: 관련 페이지 확인 & 선택")
    st.write(f"**AI 추천 페이지 수:** {len(st.session_state.relevant_pages)}개")

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
                    
                    if relevance == '상': color, bg_color = "🔴", "#ffe6e6"
                    elif relevance == '중': color, bg_color = "🟡", "#fff9e6"
                    else: color, bg_color = "⚪", "#f0f0f0"
                    
                    st.markdown(f"""
                    <div style="background-color: {bg_color}; padding: 8px; border-radius: 5px; margin: 5px 0;">
                        <div style="font-size: 0.8em; font-weight: bold;">{color} 관련도: {relevance}</div>
                        <div style="font-size: 0.75em; color: #666;">🔑 {page_response}</div>
                    </div>""", unsafe_allow_html=True)
                
                if p-1 < len(st.session_state.pdf_images):
                    st.image(st.session_state.pdf_images[p-1], use_column_width=True)

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

# ───────────────────────────────────────────────
# 6. 3단계: 최종 분석
# ───────────────────────────────────────────────
if st.session_state.step >= 3 and st.session_state.selected_pages:
    st.header("3단계: 최종 분석 결과")
    with st.spinner("선택한 페이지만으로 AI가 답변 생성 중..."):
        answer = generate_final_answer_from_selected_pages(
            st.session_state.selected_pages,
            st.session_state.user_prompt
        )

    st.subheader("📋 분석 결과")
    st.write(f"**질문:** {st.session_state.user_prompt}")
    st.write(f"**분석에 사용된 페이지 수:** {len(st.session_state.selected_pages)}개")
    st.markdown(answer)

    if st.button("새로운 분석 시작"):
        for key in list(st.session_state.keys()): del st.session_state[key]
        st.rerun()

