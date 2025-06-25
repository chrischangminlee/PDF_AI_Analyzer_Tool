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
        prompt = f"""
        당신은 PDF의 각 페이지를 개별적으로 분석하는 고도로 전문화된 '페이지 단위 분석 엔진'입니다. 
        당신의 유일한 임무는 지시에 따라 **물리적 페이지(좌측 상단 번호 기준)**를 하나씩, 완전히 독립적으로 처리하는 것입니다.

        ## 사용자 질문
        {user_prompt}

        ## 처리 절차
        1. **페이지 격리**  
        - 현재 분석할 물리적 페이지 N만을 인식합니다.  
        - 다른 모든 페이지 정보는 **완벽히 무시**합니다.

        2. **독립적 내용 분석**  
        - N페이지 내부의 텍스트·표·이미지 **전용**으로, 사용자 질문과의 **관련도**를 평가합니다.  
        - 관련도 등급  
            • **상** : 질문에 대한 해답을 제공  
            • **중** : 질문의 핵심 키워드를 포함함 
            • **하** : 키워드가 희박하거나 문맥이 사실상 무관

        3. **페이지별 답변 추출**  
        - **오직 N페이지 내용에서만** 질문과 가장 밀접한 정보를 요약‧추출합니다.  
        - 외부 지식·다른 페이지 내용은 절대 사용하지 않습니다.

        4. **결과 생성**  
        - 아래 **“응답 형식”**으로 N페이지 결과 1줄을 작성합니다.  
        - 관련도 **‘하’이거나 무관**할 경우, **출력하지 않습니다**.

        5. **메모리 리셋**  
        - N페이지 작업 종료 즉시, 그 내용과 메타데이터를 **완전 삭제**하고 다음 페이지로 이동합니다.

        ## 추가 지시사항
        - 최대 **10행**만 출력합니다.  
        - **응답 형식**에서 파이프(`|`)는 정확히 **두 개**여야 하며, 그 이외 문자는 금지입니다. 형식 오류가 있으면 결과 전체를 무효로 간주합니다.
        - 최종 결과는 질문과의 관련도가 '상' 또는 '중'인 페이지들만, 최대 10개까지 보여주세요.

        ## 응답 형식 (각 줄마다 하나의 페이지 정보, 파이프(|)로 구분)
        물리적페이지번호|페이지별답변(요약)|관련도

        ## 예시
        10|요구자본 정의 요약|상
        """
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

    prompt = f"""
    당신은 사용자의 질문에 답변하는 매우 유능하고 친절한 문서 분석 전문가입니다.
    주어진 PDF는 사용자가 원본 문서에서 일부 페이지만을 선택하여 생성한 것입니다.

## 사용자 질문
{user_prompt}

## 상세 지시사항
1. 제공된 PDF 내용만을 기반으로 사용자 질문에 대해 상세하고 구조적으로 답변하세요.
    """
    model = genai.GenerativeModel("gemini-2.0-flash")
    resp = model.generate_content([uploaded_sel, prompt])
    return resp.text
