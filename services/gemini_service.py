# gemini_service.py - 페이지 독립성 강화 버전

import io, os, tempfile, json
import streamlit as st
from PyPDF2 import PdfReader, PdfWriter
import google.generativeai as genai
from .pdf_service import upload_pdf_to_gemini

def parse_page_info(gemini_response):
    """개선된 페이지 정보 파싱 - JSON 형식 사용"""
    pages, page_info = [], {}
    
    # JSON 형식으로 응답 파싱 시도
    try:
        # JSON 블록 추출
        if "```json" in gemini_response:
            json_str = gemini_response.split("```json")[1].split("```")[0].strip()
        elif "{" in gemini_response and "}" in gemini_response:
            # JSON 객체 찾기
            start = gemini_response.find("{")
            end = gemini_response.rfind("}") + 1
            json_str = gemini_response[start:end]
        else:
            # 기존 파이프 형식 파싱으로 폴백
            return parse_page_info_legacy(gemini_response)
        
        data = json.loads(json_str)
        
        for item in data.get("pages", []):
            page_num = item.get("page_number")
            if page_num:
                pages.append(page_num)
                page_info[page_num] = {
                    'page_response': item.get('summary', ''),
                    'relevance': item.get('relevance', '하')
                }
                
    except (json.JSONDecodeError, KeyError) as e:
        # JSON 파싱 실패 시 기존 방식으로 폴백
        return parse_page_info_legacy(gemini_response)
    
    return pages, page_info

def parse_page_info_legacy(gemini_response):
    """기존 파이프 형식 파싱 (폴백용)"""
    pages, page_info = [], {}
    for line in gemini_response.strip().split('\n'):
        if '|' in line:
            try:
                parts = line.strip().split('|')
                if len(parts) == 3:
                    physical_page = int(parts[0].strip())
                    page_response = parts[1].strip()
                    relevance = parts[2].strip()
                    pages.append(physical_page)
                    page_info[physical_page] = {
                        'page_response': page_response, 
                        'relevance': relevance
                    }
            except (ValueError, IndexError):
                continue
    return pages, page_info

def find_relevant_pages_with_gemini(uploaded_file, user_prompt):
    """개선된 페이지 찾기 - 페이지 독립성 극대화"""
    try:
        prompt = f"""
        당신은 PDF 문서의 각 페이지를 완전히 독립적으로 분석하는 AI입니다.

        ⚠️ 극도로 중요한 원칙:
        1. **절대적 페이지 격리**: 각 페이지를 분석할 때, 그 페이지 외의 모든 정보를 완전히 무시하고 잊어버리세요.
        2. **물리적 페이지 번호만 사용**: PDF 좌측 상단에 인쇄된 번호만을 사용하세요.
        3. **컨텍스트 전파 금지**: 이전 페이지의 내용이 다음 페이지 분석에 절대 영향을 주어서는 안 됩니다.
        4. **각 페이지는 독립된 문서**: 마치 각 페이지가 완전히 별개의 PDF인 것처럼 취급하세요.

        ## 사용자 질문
        {user_prompt}

        ## 분석 프로세스 (각 페이지마다 반복)
        1. 현재 페이지 N의 좌측 상단 번호를 확인
        2. **오직 페이지 N의 내용만** 읽고 분석
        3. 페이지 N의 내용이 사용자 질문과 관련있는지 판단
        4. 관련이 있다면, **페이지 N에서 직접 추출한 핵심 내용**을 20자 이내로 요약
        5. 페이지 N 분석 완료 후, 그 내용을 **완전히 삭제**하고 다음 페이지로 이동

        ## 관련도 판단 기준
        - **상**: 해당 페이지가 질문에 대한 직접적인 답변 포함
        - **중**: 해당 페이지가 질문과 관련된 배경 정보 포함
        - **하**: 관련성 없음 (결과에서 제외)

        ## 응답 형식
        관련도가 '상' 또는 '중'인 페이지만 포함하여 최대 10개까지 JSON 형식으로 응답:
        
        ```json
        {{
            "pages": [
                {{
                    "page_number": [페이지 좌측 상단의 물리적 번호],
                    "summary": "[해당 페이지에서 직접 추출한 핵심 내용]",
                    "relevance": "[상/중]"
                }}
            ]
        }}
        ```

        ⚠️ 경고: summary는 반드시 해당 페이지의 실제 내용을 반영해야 하며, 다른 페이지의 정보가 섞여서는 안 됩니다.
        """
        
        model = genai.GenerativeModel('gemini-2.0-flash')
        response = model.generate_content([uploaded_file, prompt])
        return response.text.strip()
    except Exception as e:
        st.error(f"Gemini 호출 오류: {e}")
        return ""

def generate_final_answer_from_selected_pages(selected_pages, user_prompt, original_pdf_bytes):
    """개선된 최종 답변 생성"""
    if not selected_pages:
        return "선택된 페이지가 없습니다."

    reader = PdfReader(io.BytesIO(original_pdf_bytes))
    writer = PdfWriter()
    
    # 선택된 페이지만 추출
    page_mapping = {}  # 새 PDF에서의 페이지 -> 원본 페이지 번호
    for idx, p in enumerate(sorted(selected_pages)):
        if 1 <= p <= len(reader.pages):
            writer.add_page(reader.pages[p - 1])
            page_mapping[idx + 1] = p

    with tempfile.NamedTemporaryFile(delete=False, suffix=".pdf") as tmp:
        writer.write(tmp)
        tmp_path = tmp.name
    
    try:
        uploaded_sel = upload_pdf_to_gemini(tmp_path)
    finally:
        os.unlink(tmp_path)

    # 페이지 매핑 정보를 프롬프트에 포함
    mapping_info = "\n".join([f"- 현재 PDF의 {new}페이지 = 원본 PDF의 {orig}페이지" 
                              for new, orig in page_mapping.items()])
    
    prompt = f"""
    당신은 사용자의 질문에 답변하는 문서 분석 전문가입니다.
    
    ## 중요 정보
    이 PDF는 원본에서 선택된 페이지만을 포함합니다.
    페이지 번호 매핑:
    {mapping_info}
    
    ## 사용자 질문
    {user_prompt}
    
    ## 답변 지시사항
    1. 제공된 PDF 내용만을 기반으로 답변하세요
    2. 정보를 인용할 때는 원본 페이지 번호를 명시하세요
       예: "원본 PDF의 10페이지에 따르면..."
    3. 구조화된 형식으로 명확하게 답변하세요
    4. 핵심 내용을 먼저 제시하고 상세 설명을 추가하세요
    """
    
    model = genai.GenerativeModel("gemini-2.0-flash")
    resp = model.generate_content([uploaded_sel, prompt])
    return resp.text