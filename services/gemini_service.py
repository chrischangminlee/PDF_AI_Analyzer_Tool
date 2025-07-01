# gemini_service.py - 개선된 버전

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
                    'relevance': item.get('relevance', '하'),
                    'confidence': item.get('confidence', 0.5)
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
    """개선된 페이지 찾기 - 더 명확한 지시사항과 JSON 응답"""
    try:
        prompt = f"""
        당신은 PDF 문서의 각 페이지를 독립적으로 분석하는 전문가입니다.
        
        **중요**: PDF의 좌측 상단에 표시된 물리적 페이지 번호를 반드시 사용하세요.
        
        ## 사용자 질문
        {user_prompt}
        
        ## 분석 절차
        1. PDF의 각 페이지를 순차적으로 검토합니다
        2. 각 페이지의 좌측 상단에 표시된 번호를 확인합니다
        3. 해당 페이지의 내용이 사용자 질문과 얼마나 관련이 있는지 평가합니다
        4. 관련도가 '중' 이상인 페이지만 결과에 포함합니다
        
        ## 관련도 기준
        - **상**: 질문에 대한 직접적인 답변이나 핵심 정보 포함
        - **중**: 질문과 관련된 배경 정보나 부가 설명 포함
        - **하**: 관련성이 낮거나 없음
        
        ## 응답 형식
        다음 JSON 형식으로 응답하세요:
        ```json
        {{
            "pages": [
                {{
                    "page_number": 10,
                    "summary": "요구자본의 정의와 계산 방법 설명",
                    "relevance": "상",
                    "confidence": 0.9
                }},
                {{
                    "page_number": 15,
                    "summary": "관련 규제 요건 설명",
                    "relevance": "중",
                    "confidence": 0.7
                }}
            ]
        }}
        ```
        
        - page_number: PDF 좌측 상단의 물리적 페이지 번호
        - summary: 해당 페이지의 핵심 내용 요약 (20자 이내)
        - relevance: 관련도 (상/중/하)
        - confidence: 신뢰도 (0.0~1.0)
        
        최대 10개의 관련 페이지만 포함하세요.
        """
        
        model = genai.GenerativeModel('gemini-2.0-flash')
        resp = model.generate_content([uploaded_file, prompt])
        return resp.text.strip()
    except Exception as e:
        st.error(f"Gemini 호출 오류: {e}")
        return ""

def verify_page_content(uploaded_file, page_number, expected_content):
    """특정 페이지의 내용을 검증하는 함수"""
    try:
        prompt = f"""
        PDF의 {page_number}페이지(좌측 상단 번호 기준)를 확인하고, 
        다음 내용이 실제로 포함되어 있는지 검증하세요:
        
        예상 내용: {expected_content}
        
        응답 형식:
        - 일치: True/False
        - 실제 내용: (페이지의 실제 핵심 내용 요약)
        """
        
        model = genai.GenerativeModel('gemini-2.0-flash')
        resp = model.generate_content([uploaded_file, prompt])
        return resp.text.strip()
    except Exception as e:
        return f"검증 실패: {e}"

def generate_final_answer_from_selected_pages(selected_pages, user_prompt, original_pdf_bytes):
    """개선된 최종 답변 생성 - 페이지 번호 명시"""
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

# 추가 유틸리티 함수들

def batch_analyze_pages(uploaded_file, user_prompt, start_page=1, end_page=10):
    """페이지를 배치로 분석하는 함수"""
    try:
        prompt = f"""
        PDF의 {start_page}페이지부터 {end_page}페이지까지 분석하세요.
        각 페이지의 좌측 상단 번호를 확인하고, 다음 질문과의 관련성을 평가하세요.
        
        질문: {user_prompt}
        
        JSON 형식으로 각 페이지의 관련성을 보고하세요.
        관련성이 낮은 페이지는 제외하세요.
        """
        
        model = genai.GenerativeModel('gemini-2.0-flash')
        resp = model.generate_content([uploaded_file, prompt])
        return resp.text.strip()
    except Exception as e:
        return f"배치 분석 실패: {e}"

def extract_page_metadata(pdf_bytes):
    """PDF에서 페이지별 메타데이터 추출"""
    reader = PdfReader(io.BytesIO(pdf_bytes))
    metadata = {}
    
    for idx, page in enumerate(reader.pages):
        page_num = idx + 1
        text = page.extract_text()
        
        # 페이지 특성 분석
        metadata[page_num] = {
            'text_length': len(text),
            'has_images': '/XObject' in page.get('/Resources', {}).get('/ProcSet', []),
            'has_tables': '|' in text or '\t' in text,  # 간단한 테이블 감지
            'first_100_chars': text[:100].strip()
        }
    
    return metadata