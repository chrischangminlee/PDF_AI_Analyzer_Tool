# gemini_service.py - 배치 분석 및 검증 기능 추가

import io, os, tempfile, json, time
import streamlit as st
from PyPDF2 import PdfReader, PdfWriter
import google.generativeai as genai

def call_gemini_with_retry(model, content, max_retries=3, base_delay=2, status_placeholder=None):
    """Gemini API 호출을 재시도 로직과 함께 실행"""
    for attempt in range(max_retries):
        try:
            # API 호출 전 대기 (rate limiting)
            if attempt > 0:
                delay = base_delay * (2 ** attempt)  # 지수 백오프
                if status_placeholder:
                    status_placeholder.info(f"⏳ API 호출 대기 중... ({delay}초)")
                time.sleep(delay)
            
            response = model.generate_content(content)
            return response.text.strip()
            
        except Exception as e:
            error_msg = str(e)
            
            if "429" in error_msg or "quota" in error_msg.lower():
                # 할당량 초과 시
                if attempt < max_retries - 1:
                    if "retry_delay" in error_msg:
                        # 서버에서 권장하는 대기 시간 추출
                        try:
                            delay = 45  # 기본 45초
                            if status_placeholder:
                                status_placeholder.warning(f"⚠️ API 할당량 초과. {delay}초 대기 후 재시도... ({attempt + 1}/{max_retries})")
                            time.sleep(delay)
                        except:
                            if status_placeholder:
                                status_placeholder.warning(f"⚠️ API 할당량 초과. 60초 대기 후 재시도... ({attempt + 1}/{max_retries})")
                            time.sleep(60)
                    else:
                        if status_placeholder:
                            status_placeholder.warning(f"⚠️ API 할당량 초과. 30초 대기 후 재시도... ({attempt + 1}/{max_retries})")
                        time.sleep(30)
                else:
                    if status_placeholder:
                        status_placeholder.error("❌ API 할당량이 완전히 소진되었습니다. 나중에 다시 시도해주세요.")
                    raise Exception("QUOTA_EXHAUSTED")
            else:
                # 다른 오류
                if attempt < max_retries - 1:
                    if status_placeholder:
                        status_placeholder.warning(f"⚠️ API 호출 실패. 5초 대기 후 재시도... ({attempt + 1}/{max_retries})")
                    time.sleep(5)
                else:
                    raise e
    
    raise Exception("최대 재시도 횟수 초과")

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
                # page_num이 list인 경우 첫 번째 값만 사용
                if isinstance(page_num, list):
                    page_num = page_num[0] if page_num else None
                if page_num and isinstance(page_num, (int, str)):
                    try:
                        page_num = int(page_num)
                        pages.append(page_num)
                        page_info[page_num] = {
                            'page_response': item.get('summary', ''),
                            'relevance': item.get('relevance', '하')
                        }
                    except (ValueError, TypeError):
                        continue
                
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

def split_pdf_for_batch_analysis(pdf_bytes, batch_size=10):
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

def analyze_pdf_batch(batch_path, user_prompt, batch_info, status_placeholder=None):
    """단일 배치 PDF 분석"""
    # 배치 파일을 Gemini에 업로드
    batch_file = genai.upload_file(batch_path)
    
    prompt = f"""
    이 PDF는 전체 문서의 {batch_info['start_page']}페이지부터 {batch_info['end_page']}페이지까지만 포함합니다.
    
    중요: 각 페이지의 좌측 상단에 표시된 번호를 반드시 확인하고 사용하세요.
    
    ## 사용자 질문
    {user_prompt}
    
    ## 엄격한 관련성 판단 기준
    ⚠️ **매우 중요**: 다음 기준을 엄격히 적용하세요
    
    **상 (직접 관련)**: 
    - 사용자 질문의 핵심 키워드가 페이지에 명시적으로 언급됨
    - 질문에 대한 직접적인 답변이나 정의가 포함됨
    - 질문과 정확히 일치하는 주제를 다룸
    
    **중 (간접 관련)**:
    - 질문과 관련된 배경 정보나 맥락이 포함됨
    - 질문 주제의 상위/하위 개념을 다룸
    - 질문 해결에 도움이 되는 관련 정보 포함
    
    **하 (관련 없음) - 결과에서 제외**:
    - 질문과 전혀 관련 없는 내용
    - 단순히 문서의 목차, 서문, 부록 등
    - 질문 키워드가 우연히 언급되었지만 맥락상 무관한 경우
    
    ## 분석 지시사항
    1. 각 페이지를 독립적으로 분석
    2. 페이지 좌측 상단 번호 확인
    3. **관련성이 '상' 또는 '중'인 페이지만** 보고
    4. 확신이 없으면 제외하세요 (false positive 방지)
    
    ## 응답 형식
    관련성이 높은 페이지만 JSON으로 응답하세요:
    ```json
    {{
        "pages": [
            {{
                "page_number": [좌측 상단의 실제 페이지 번호],
                "summary": "[해당 페이지의 핵심 내용 15자 이내]",
                "relevance": "[상/중]"
            }}
        ]
    }}
    ```
    
    ⚠️ 관련성이 낮은 페이지는 절대 포함하지 마세요!
    """
    
    model = genai.GenerativeModel('gemini-2.0-flash')
    # 예외를 그대로 전파하도록 try-catch 제거
    return call_gemini_with_retry(model, [batch_file, prompt], status_placeholder=status_placeholder)

def find_relevant_pages_with_gemini(user_prompt, pdf_bytes=None, status_placeholder=None):
    """배치 단위로 PDF 분석"""
    all_pages = []
    all_page_info = {}
    
    if pdf_bytes:
        # PDF를 배치로 나누어 분석
        batches = split_pdf_for_batch_analysis(pdf_bytes, batch_size=10)
        
        progress_bar = st.progress(0)
        for idx, batch in enumerate(batches):
            progress_bar.progress((idx + 1) / len(batches))
            
            try:
                # 배치간 대기 시간 추가 (rate limiting) - 업로드 전에 실행
                if idx > 0:
                    if status_placeholder:
                        status_placeholder.info(f"⏳ 배치 {idx + 1}/{len(batches)} 처리를 위해 3초 대기...")
                    time.sleep(3)
                
                # 현재 배치 진행상황 표시
                if status_placeholder:
                    status_placeholder.info(f"🤖 배치 {idx + 1}/{len(batches)} 분석 중... (페이지 {batch['start_page']}-{batch['end_page']})")
                
                # 배치 분석 (내부에서 업로드 처리)
                batch_response = analyze_pdf_batch(batch['path'], user_prompt, batch, status_placeholder)
                
                # 결과 파싱
                pages, page_info = parse_page_info(batch_response)
                
                # 전체 결과에 병합
                all_pages.extend(pages)
                all_page_info.update(page_info)
                
            except Exception as e:
                # API 할당량 소진 시 즉시 중단
                if "QUOTA_EXHAUSTED" in str(e):
                    if status_placeholder:
                        status_placeholder.error("❌ API 할당량 소진으로 배치 처리를 중단합니다.")
                    progress_bar.empty()
                    # 지금까지 처리된 결과라도 반환
                    break
                else:
                    if status_placeholder:
                        status_placeholder.warning(f"⚠️ 배치 {idx + 1} 처리 실패: {e}")
                    continue
            finally:
                # 임시 파일 삭제
                if os.path.exists(batch['path']):
                    os.unlink(batch['path'])
        
        progress_bar.empty()
        
        # 중복 제거 및 정렬
        unique_pages = list(dict.fromkeys(all_pages))
        return unique_pages[:10], all_page_info
    
    else:
        # pdf_bytes가 없는 경우 빈 결과 반환
        return [], {}



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
        uploaded_sel = genai.upload_file(tmp_path)
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
    return call_gemini_with_retry(model, [uploaded_sel, prompt])