# gemini_service.py - 배치 분석 및 검증 기능 추가

import io, os, tempfile, json, time
import streamlit as st
from PyPDF2 import PdfReader, PdfWriter
import google.generativeai as genai
from .pdf_service import upload_pdf_to_gemini

def call_gemini_with_retry(model, content, max_retries=3, base_delay=2):
    """Gemini API 호출을 재시도 로직과 함께 실행"""
    for attempt in range(max_retries):
        try:
            # API 호출 전 대기 (rate limiting)
            if attempt > 0:
                delay = base_delay * (2 ** attempt)  # 지수 백오프
                st.info(f"⏳ API 호출 대기 중... ({delay}초)")
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
                            st.warning(f"⚠️ API 할당량 초과. {delay}초 대기 후 재시도... ({attempt + 1}/{max_retries})")
                            time.sleep(delay)
                        except:
                            st.warning(f"⚠️ API 할당량 초과. 60초 대기 후 재시도... ({attempt + 1}/{max_retries})")
                            time.sleep(60)
                    else:
                        st.warning(f"⚠️ API 할당량 초과. 30초 대기 후 재시도... ({attempt + 1}/{max_retries})")
                        time.sleep(30)
                else:
                    st.error("❌ API 할당량이 완전히 소진되었습니다. 나중에 다시 시도해주세요.")
                    raise Exception("QUOTA_EXHAUSTED")
            else:
                # 다른 오류
                if attempt < max_retries - 1:
                    st.warning(f"⚠️ API 호출 실패. 5초 대기 후 재시도... ({attempt + 1}/{max_retries})")
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

def analyze_pdf_batch(batch_file, user_prompt, batch_info):
    """단일 배치 PDF 분석"""
    try:
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
        return call_gemini_with_retry(model, [batch_file, prompt])
    except Exception as e:
        return f"배치 분석 오류: {e}"

def find_relevant_pages_with_gemini(uploaded_file, user_prompt, pdf_bytes=None):
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
                # 배치 파일 업로드
                batch_file = upload_pdf_to_gemini(batch['path'])
                
                # 배치간 대기 시간 추가 (rate limiting)
                if idx > 0:
                    st.info(f"⏳ 다음 배치 처리를 위해 3초 대기...")
                    time.sleep(3)
                
                # 배치 분석
                batch_response = analyze_pdf_batch(batch_file, user_prompt, batch)
                
                # 결과 파싱
                pages, page_info = parse_page_info(batch_response)
                
                # 전체 결과에 병합
                all_pages.extend(pages)
                all_page_info.update(page_info)
                
            except Exception as e:
                # API 할당량 소진 시 즉시 중단
                if "QUOTA_EXHAUSTED" in str(e):
                    st.error("❌ API 할당량 소진으로 배치 처리를 중단합니다.")
                    progress_bar.empty()
                    # 지금까지 처리된 결과라도 반환
                    break
                else:
                    st.warning(f"⚠️ 배치 {idx + 1} 처리 실패: {e}")
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
        # 기존 방식 (전체 PDF 한 번에 분석)
        response = analyze_full_pdf(uploaded_file, user_prompt)
        pages, page_info = parse_page_info(response)
        return pages[:10], page_info

def analyze_full_pdf(uploaded_file, user_prompt):
    """전체 PDF 분석 (기존 방식)"""
    try:
        prompt = f"""
        당신은 PDF 문서 분석 전문가입니다. 사용자 질문과 **정말로 관련이 높은** 페이지만을 찾아야 합니다.

        ## 사용자 질문
        {user_prompt}

        ## 극도로 엄격한 관련성 판단 기준
        
        **상 (직접 관련) - 반드시 포함해야 할 페이지**:
        - 사용자 질문의 **핵심 키워드**가 페이지 제목이나 본문에 명확히 언급됨
        - 질문에 대한 **직접적인 답변, 정의, 설명**이 포함됨
        - 질문 주제를 **주요 내용**으로 다루는 페이지
        
        **중 (간접 관련) - 신중하게 판단**:
        - 질문 주제의 **직접적인 배경 정보**나 **전제 조건** 설명
        - 질문과 관련된 **상위/하위 개념**의 상세한 설명
        - 질문 해결에 **필수적인** 관련 정보 포함
        
        **하 (관련 없음) - 절대 포함하지 말 것**:
        - 질문 키워드가 **단순 언급**만 되고 주요 내용이 아닌 경우
        - **목차, 서문, 부록, 참고문헌** 등의 형식적 내용
        - 질문과 **다른 주제**를 다루는 페이지
        - **확신이 없는** 모든 페이지

        ## 분석 지시사항
        1. **매우 엄격하게** 관련성을 판단하세요
        2. **확신이 없으면 제외**하세요 (빠뜨리는 것이 잘못 포함하는 것보다 낫습니다)
        3. 각 페이지의 좌측 상단 번호를 정확히 확인하세요
        4. **관련성이 '상' 또는 '중'인 페이지만** 응답에 포함하세요

        ## 응답 형식
        **진짜 관련있는 페이지만** JSON으로 응답하세요 (없으면 빈 배열):
        
        ```json
        {{
            "pages": [
                {{
                    "page_number": [페이지 좌측 상단의 물리적 번호],
                    "summary": "[해당 페이지의 핵심 내용 15자 이내]",
                    "relevance": "[상/중]"
                }}
            ]
        }}
        ```

        ⚠️ **중요**: 관련성이 낮거나 확실하지 않은 페이지는 절대 포함하지 마세요!
        """
        
        model = genai.GenerativeModel('gemini-2.0-flash')
        return call_gemini_with_retry(model, [uploaded_file, prompt])
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
    return call_gemini_with_retry(model, [uploaded_sel, prompt])