# gemini_service.py - 배치 분석 및 검증 기능 추가

import io, os, tempfile, json
import streamlit as st
from PyPDF2 import PdfReader, PdfWriter
import google.generativeai as genai
from .pdf_service import upload_pdf_to_gemini

def parse_page_info(gemini_response):
    """개선된 페이지 정보 파싱 - JSON 형식 사용"""
    pages, page_info = [], {}
    
    try:
        if "```json" in gemini_response:
            json_str = gemini_response.split("```json")[1].split("```")[0].strip()
        elif "{" in gemini_response and "}" in gemini_response:
            start = gemini_response.find("{")
            end = gemini_response.rfind("}") + 1
            json_str = gemini_response[start:end]
        else:
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

def split_pdf_for_batch_analysis(pdf_bytes, batch_size=5):
    """PDF를 배치로 나누어 처리하기 위한 함수"""
    reader = PdfReader(io.BytesIO(pdf_bytes))
    total_pages = len(reader.pages)
    batches = []
    
    for start_idx in range(0, total_pages, batch_size):
        end_idx = min(start_idx + batch_size, total_pages)
        
        # 배치 PDF 생성
        writer = PdfWriter()
        for i in range(start_idx, end_idx):
            writer.add_page(reader.pages[i])
        
        # 임시 파일로 저장
        with tempfile.NamedTemporaryFile(delete=False, suffix=".pdf") as tmp:
            writer.write(tmp)
            tmp_path = tmp.name
        
        batches.append({
            'path': tmp_path,
            'start_page': start_idx + 1,
            'end_page': end_idx,
            'pages': list(range(start_idx + 1, end_idx + 1))
        })
    
    return batches

def analyze_pdf_batch(batch_file, user_prompt, batch_info):
    """단일 배치 PDF 분석"""
    try:
        prompt = f"""
        이 PDF는 전체 문서의 {batch_info['start_page']}페이지부터 {batch_info['end_page']}페이지까지만 포함합니다.
        
        중요: 각 페이지의 좌측 상단에 표시된 번호를 반드시 확인하고 사용하세요.
        
        ## 사용자 질문
        {user_prompt}
        
        ## 분석 지시사항
        1. 이 PDF에 포함된 각 페이지를 독립적으로 분석하세요
        2. 각 페이지의 좌측 상단 번호를 확인하세요
        3. 해당 페이지의 실제 내용만을 기반으로 관련성을 판단하세요
        4. 관련성이 있는 페이지만 보고하세요
        
        ## 응답 형식
        ```json
        {{
            "pages": [
                {{
                    "page_number": [좌측 상단의 실제 페이지 번호],
                    "summary": "[해당 페이지의 핵심 내용 20자 이내]",
                    "relevance": "[상/중]"
                }}
            ]
        }}
        ```
        """
        
        model = genai.GenerativeModel('gemini-2.0-flash')
        response = model.generate_content([batch_file, prompt])
        return response.text.strip()
    except Exception as e:
        return f"배치 분석 오류: {e}"

def find_relevant_pages_with_gemini(uploaded_file, user_prompt, pdf_bytes=None):
    """배치 단위로 PDF 분석"""
    all_pages = []
    all_page_info = {}
    
    if pdf_bytes:
        # PDF를 배치로 나누어 분석
        batches = split_pdf_for_batch_analysis(pdf_bytes, batch_size=5)
        
        progress_bar = st.progress(0)
        for idx, batch in enumerate(batches):
            progress_bar.progress((idx + 1) / len(batches))
            
            try:
                # 배치 파일 업로드
                batch_file = upload_pdf_to_gemini(batch['path'])
                
                # 배치 분석
                batch_response = analyze_pdf_batch(batch_file, user_prompt, batch)
                
                # 결과 파싱
                pages, page_info = parse_page_info(batch_response)
                
                # 전체 결과에 병합
                all_pages.extend(pages)
                all_page_info.update(page_info)
                
            finally:
                # 임시 파일 삭제
                if os.path.exists(batch['path']):
                    os.unlink(batch['path'])
        
        progress_bar.empty()
        
        # 중복 제거 및 정렬
        unique_pages = list(dict.fromkeys(all_pages))
        return unique_pages[:10], all_page_info
    
    else:
        # 기존 방식 (전체 PDF 한 번에 분석)
        response = analyze_full_pdf(uploaded_file, user_prompt)
        pages, page_info = parse_page_info(response)
        return pages[:10], page_info

def analyze_full_pdf(uploaded_file, user_prompt):
    """전체 PDF 분석 (기존 방식)"""
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

def verify_page_analysis(page_number, summary, pdf_bytes):
    """특정 페이지의 분석 결과를 검증"""
    try:
        reader = PdfReader(io.BytesIO(pdf_bytes))
        
        # 페이지 번호 유효성 확인
        if page_number < 1 or page_number > len(reader.pages):
            return False, f"페이지 번호 {page_number}가 유효 범위를 벗어남"
        
        # 해당 페이지만 추출
        writer = PdfWriter()
        writer.add_page(reader.pages[page_number - 1])
        
        with tempfile.NamedTemporaryFile(delete=False, suffix=".pdf") as tmp:
            writer.write(tmp)
            tmp_path = tmp.name
        
        try:
            # 단일 페이지 업로드
            single_page_file = upload_pdf_to_gemini(tmp_path)
            
            # 검증 프롬프트
            prompt = f"""
            이 PDF는 단일 페이지입니다.
            
            다음 요약이 이 페이지의 실제 내용과 일치하는지 검증하세요:
            "{summary}"
            
            응답 형식:
            {{
                "match": true/false,
                "reason": "일치하지 않는 이유 (불일치 시)",
                "actual_content": "페이지의 실제 핵심 내용 (20자 이내)"
            }}
            """
            
            model = genai.GenerativeModel('gemini-2.0-flash')
            response = model.generate_content([single_page_file, prompt])
            
            # 검증 결과 파싱
            result_text = response.text.strip()
            if "{" in result_text and "}" in result_text:
                start = result_text.find("{")
                end = result_text.rfind("}") + 1
                json_str = result_text[start:end]
                result = json.loads(json_str)
                
                if not result.get('match', False):
                    return False, result.get('reason', '내용 불일치')
                return True, None
            
        finally:
            if os.path.exists(tmp_path):
                os.unlink(tmp_path)
                
    except Exception as e:
        return False, f"검증 중 오류: {str(e)}"
    
    return True, None

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