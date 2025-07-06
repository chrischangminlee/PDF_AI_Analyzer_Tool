# gemini_service.py - 배치 분석 및 검증 기능

import io, os, tempfile, json, time
import streamlit as st
from PyPDF2 import PdfReader, PdfWriter
import google.generativeai as genai

# 모델 상수
GEMINI_MODEL = "gemini-2.5-flash"

def call_gemini_with_retry(model, content, max_retries=3, base_delay=1, status_placeholder=None):
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
        # 디버깅을 위한 로그
        if not gemini_response or not gemini_response.strip():
            st.warning("⚠️ Gemini 응답이 비어있습니다.")
            return pages, page_info
            
        if "```json" in gemini_response:
            json_str = gemini_response.split("```json")[1].split("```")[0].strip()
        elif "{" in gemini_response and "}" in gemini_response:
            start = gemini_response.find("{")
            end = gemini_response.rfind("}") + 1
            json_str = gemini_response[start:end]
        else:
            st.warning("⚠️ JSON 형식을 찾을 수 없어 기존 파싱 방식을 시도합니다.")
            return parse_page_info_legacy(gemini_response)
        
        data = json.loads(json_str)
        
        # 페이지가 없는 경우 확인
        if not data.get("pages"):
            st.info("ℹ️ 관련 페이지를 찾을 수 없습니다.")
            return pages, page_info
            
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
                            'page_response': item.get('answer', ''),
                            'relevance': item.get('relevance', '하')
                        }
                    except (ValueError, TypeError):
                        continue
                
    except (json.JSONDecodeError, KeyError) as e:
        st.warning(f"⚠️ JSON 파싱 오류: {str(e)}")
        st.text("Gemini 응답:")
        st.code(gemini_response[:500] + "..." if len(gemini_response) > 500 else gemini_response)
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

def analyze_pdf_batch(batch_path, refined_prompt, batch_info, status_placeholder=None):
    """단일 배치 PDF 분석"""
    # 배치 파일을 Gemini에 업로드
    batch_file = genai.upload_file(batch_path)
    
    prompt = f"""
    이 PDF는 전체 문서의 {batch_info['start_page']}페이지부터 {batch_info['end_page']}페이지까지만 포함합니다.

    중요: 각 페이지의 좌측 상단에 표시된 번호를 반드시 확인하고 사용하세요.

    ## 사용자 질문
    {refined_prompt}

    ## 엄격한 관련성 판단 기준
    ⚠️ **매우 중요**: 다음 기준을 엄격히 적용하세요.

    **상 (직접 답변)**  
    - 페이지 안에 **사용자 질문에 대한 명시적·직접적 답변 문장**이 존재함  
    - 질문 핵심 키워드뿐 아니라 **답변 내용 자체**가 포함되어 있음  
    - ‘answer’ 필드에 해당 문장(또는 핵심 요약)을 **30자 이내**로 입력  
    - 위 조건을 모두 충족하지 못하면 ‘상’으로 분류하지 말 것

    **중 (간접 관련)**  
    - 질문과 밀접한 배경·맥락·상위/하위 개념을 다룸  
    - 직접적인 답은 없지만 문제 해결에 실질적으로 도움이 되는 정보 포함  
    - ‘answer’ 필드는 **빈 문자열("")**로 두거나 생략

    **하 (관련 없음)** – 결과에서 **제외**  
    - 질문과 전혀 무관하거나 키워드가 우연히 등장하는 수준  
    - 목차, 서문, 부록 등

    ## 분석 지시사항
    1. 각 페이지를 **독립적으로** 분석  
    2. 페이지 좌측 상단 번호 확인  
    3. **질문에 대한 직접 답변 문장이 있으면** 30자 이내로 발췌·요약하여 `answer`에 입력  
    4. **‘상’ 또는 ‘중’**에 해당하는 페이지만 결과에 포함  
    - **‘상’**: ③의 답변이 존재하며 조건 충족  
    - **‘중’**: 답변은 없지만 유의미한 간접 정보 포함  
    5. 확신이 없으면 제외(오탐 방지)

    ## 응답 형식
    관련성이 높은 페이지만 JSON으로 응답하세요:

    ```json
    {{
        "pages": [
            {{
                "page_number": [좌측 상단의 실제 페이지 번호],
                "answer": "[사용자 질문에 대한 직접 답변 (30자 이내) 또는 빈 문자열]",
                "relevance": "[상/중]"
            }}
        ]
    }}
    ```
    
    ⚠️ 관련성이 낮은 페이지는 절대 포함하지 마세요!
    """
    
    model = genai.GenerativeModel(GEMINI_MODEL)
    return call_gemini_with_retry(model, [batch_file, prompt], status_placeholder=status_placeholder)

def enhance_user_prompt(user_prompt, status_placeholder=None):
    """사용자의 초기 프롬프트를 더 명확하고 구체적으로 개선"""
    try:
        if status_placeholder:
            status_placeholder.info("🔍 질문 분석 중...")
        
        prompt = f"""
당신은 PDF 문서 분석을 위한 프롬프트 개선 전문가입니다.
사용자의 질문을 분석하여, PDF에서 정확한 정보를 찾을 수 있도록 더 명확하고 구체적인 질문으로 개선해주세요.

원본 질문: {user_prompt}

다음 지침에 따라 질문을 개선하세요:
1. 모호한 표현을 구체적으로 변경
2. 관련 용어나 동의어 추가
3. 찾고자 하는 정보의 유형 명확화 (정의, 절차, 조건, 금액 등)
4. 불필요한 정중한 표현 제거 ("알려줘", "부탁해" 등)

개선된 질문만 출력하세요. 추가 설명은 하지 마세요.
"""
        
        model = genai.GenerativeModel(GEMINI_MODEL)
        enhanced_prompt = call_gemini_with_retry(model, prompt, max_retries=2, base_delay=1)
        
        if status_placeholder:
            status_placeholder.success(f"✅ 질문 분석 완료: {enhanced_prompt}")
        
        return enhanced_prompt.strip()
        
    except Exception as e:
        if status_placeholder:
            status_placeholder.warning("⚠️ 질문 개선 실패, 원본 질문으로 진행합니다.")
        return user_prompt

def find_relevant_pages_with_gemini(user_prompt, pdf_bytes=None, status_placeholder=None):
    """배치 단위로 PDF 분석"""
    all_pages = []
    all_page_info = {}
    
    if pdf_bytes:
        # 프롬프트 개선
        refined_prompt = enhance_user_prompt(user_prompt, status_placeholder)
        
        # 개선된 프롬프트를 세션에 저장
        st.session_state.refined_prompt = refined_prompt
        
        # PDF를 배치로 나누어 분석
        batches = split_pdf_for_batch_analysis(pdf_bytes, batch_size=10)
        
        progress_bar = st.progress(0)
        for idx, batch in enumerate(batches):
            progress_bar.progress((idx + 1) / len(batches))
            
            try:
                # 배치간 대기 시간 제거 (Paid API 사용)
                
                # 현재 배치 진행상황 표시
                if status_placeholder:
                    status_placeholder.info(f"🤖 배치 {idx + 1}/{len(batches)} 분석 중... (페이지 {batch['start_page']}-{batch['end_page']})")
                
                # 배치 분석 (내부에서 업로드 처리)
                batch_response = analyze_pdf_batch(batch['path'], refined_prompt, batch, status_placeholder)
                
                # 결과 파싱
                pages, page_info = parse_page_info(batch_response)
                
                # 전체 결과에 병합
                all_pages.extend(pages)
                all_page_info.update(page_info)
                
            except Exception as e:
                # API 할당량 소진 시 즉시 중단
                if "QUOTA_EXHAUSTED" in str(e):
                    if status_placeholder:
                        status_placeholder.error("❌ API 할당량이 소진되어 분석을 완료할 수 없습니다.")
                    progress_bar.empty()
                    # 할당량 소진 시 빈 결과 반환 (부분 결과 X)
                    return [], {}
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
        return sorted(unique_pages), all_page_info
    
    else:
        # pdf_bytes가 없는 경우 빈 결과 반환
        return [], {}