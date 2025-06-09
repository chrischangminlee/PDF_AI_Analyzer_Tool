import streamlit as st
import google.generativeai as genai
from dotenv import load_dotenv
import os, io, time, tempfile, base64
from PyPDF2 import PdfReader, PdfWriter
from pdf2image import convert_from_bytes
from PIL import Image
from concurrent.futures import ThreadPoolExecutor, as_completed

# ───────────────────────────────────────────────
# 0. 환경설정
# ───────────────────────────────────────────────
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


# ───────────────────────────────────────────────
# 1. 사이드바 & 기본 설명
# ───────────────────────────────────────────────
st.sidebar.title("소개")
st.sidebar.markdown("""
본 서비스는 AI를 활용하여 다양한 종류의 PDF를 세부분석 할 수 있게 도와주는 AI 도구 입니다.
* Gemini 1.5 flash model을 사용하고 있어 답변 생성 속도가 느릴 수 있습니다.
""")
st.sidebar.markdown('<p style="color: red; font-size: 0.8em;">(주의)본 AI가 제공하는 답변은 참고용이며, 정확성을 보장할 수 없습니다. 보안을 위해 회사 기밀, 개인정보등은 제공하지 않기를 권장드리며, 반드시 실제 업무에 적용하기 전에 검토하시길 바랍니다.</p>', unsafe_allow_html=True)
st.sidebar.markdown("### 타 Link")
st.sidebar.markdown("[개발자 링크드인](https://www.linkedin.com/in/chrislee9407/)")
st.sidebar.markdown("[K-계리 AI 플랫폼](https://chrischangminlee.github.io/K_Actuary_AI_Agent_Platform/)")
st.sidebar.markdown("[K-Actuary AI Doc Analyzer (Old Ver.)](https://kactuarypdf.streamlit.app/)")

st.title("이창민의 PDF AI 세부 분석 Tool")
st.write(
    "- **1단계** PDF 업로드 + 질문 입력  \n"
    "- **2단계** 관련 페이지 AI 추천 & 직접 선택  \n"
    "- **3단계** 선택한 페이지만으로 최종 분석"
)

# ───────────────────────────────────────────────
# 2. 세션 상태 초기화
# ───────────────────────────────────────────────
for k, v in {
    'relevant_pages': [],
    'page_info': {},              # ★ 추가: 페이지별 키워드/관련도 정보
    'selected_pages': [],
    'original_pdf_bytes': None,   # ★ 변경: 원본 바이트 저장
    'pdf_images': [],
    'step': 1,
}.items():
    if k not in st.session_state:
        st.session_state[k] = v


# ───────────────────────────────────────────────
# 3. 유틸 함수
# ───────────────────────────────────────────────
def upload_pdf_to_gemini(pdf_path):
    """파일 경로를 받아 Gemini 파일 객체로 업로드"""
    return genai.upload_file(pdf_path, mime_type="application/pdf")

def convert_pdf_to_images(pdf_bytes):
    """PDF bytes → JPEG 이미지 리스트"""
    try:
        return convert_from_bytes(pdf_bytes, dpi=100, fmt='jpeg')
    except Exception as e:
        st.warning(f"이미지 변환 오류: {e}")
        return []

def split_pdf_to_pages(pdf_bytes):
    """PDF를 페이지별로 분리하여 임시 파일로 저장"""
    reader = PdfReader(io.BytesIO(pdf_bytes))
    page_files = []
    
    for i, page in enumerate(reader.pages):
        writer = PdfWriter()
        writer.add_page(page)
        
        # 임시 파일로 저장
        with tempfile.NamedTemporaryFile(delete=False, suffix=f"_page_{i+1}.pdf") as tmp_file:
            writer.write(tmp_file)
            page_files.append({
                'page_num': i + 1,
                'file_path': tmp_file.name
            })
    
    return page_files

def analyze_single_page(page_info, user_prompt):
    """단일 페이지 PDF 파일을 분석하여 키워드와 관련도 추출"""
    try:
        page_num = page_info['page_num']
        file_path = page_info['file_path']
        
        # Gemini에 업로드
        uploaded_file = upload_pdf_to_gemini(file_path)
        
        prompt = f"""
        이 1페이지 PDF를 분석하여 다음 질문과의 관련성을 평가해주세요.
        
        질문: {user_prompt}
        
        지시사항:
        1. 이 페이지만의 내용을 기반으로 분석하세요 (다른 페이지 맥락 고려 안함)
        2. 이 페이지의 핵심 키워드 3개를 찾아주세요
        3. 질문과의 관련도를 상/중/하로 평가해주세요
        
        응답 형식:
        키워드1,키워드2,키워드3|관련도
        
        예시:
        요구자본,리스크,자본충족률|상
        """
        
        model = genai.GenerativeModel('gemini-1.5-flash')
        response = model.generate_content([uploaded_file, prompt])
        
        # 임시 파일 삭제
        os.unlink(file_path)
        
        # 응답 파싱
        result = response.text.strip()
        if '|' in result:
            parts = result.split('|')
            if len(parts) >= 2:
                keywords = parts[0].strip()
                relevance = parts[1].strip()
                return {
                    'page_num': page_num,
                    'keywords': keywords, 
                    'relevance': relevance
                }
        
        return {
            'page_num': page_num,
            'keywords': '키워드,추출,실패',
            'relevance': '하'
        }
        
    except Exception as e:
        # 임시 파일 정리
        if 'file_path' in page_info and os.path.exists(page_info['file_path']):
            os.unlink(page_info['file_path'])
        return {
            'page_num': page_info['page_num'],
            'keywords': f'오류,발생,{str(e)[:10]}',
            'relevance': '하'
        }

def parse_page_info(gemini_response):
    """Gemini 응답을 파싱하여 페이지 정보 추출 (기존 방식용 백업)"""
    pages = []
    page_info = {}
    
    for line in gemini_response.strip().split('\n'):
        if '|' in line:
            try:
                parts = line.strip().split('|')
                if len(parts) >= 3:
                    page_num = int(parts[0].strip())
                    keywords = parts[1].strip()
                    relevance = parts[2].strip()
                    
                    pages.append(page_num)
                    page_info[page_num] = {
                        'keywords': keywords,
                        'relevance': relevance
                    }
            except (ValueError, IndexError):
                continue
    
    return pages, page_info

def find_relevant_pages_with_gemini(pdf_bytes, user_prompt):
    """새로운 방식: 페이지별로 분리하여 개별 분석"""
    try:
        # 1단계: PDF를 페이지별로 분리
        st.info("📄 PDF를 페이지별로 분리하는 중...")
        page_files = split_pdf_to_pages(pdf_bytes)
        total_pages = len(page_files)
        
        if total_pages == 0:
            return []
        
        st.info(f"📊 총 {total_pages}개 페이지를 개별 분석 중...")
        
        # 2단계: 각 페이지를 병렬로 분석
        results = []
        
        # 진행률 표시
        progress_bar = st.progress(0)
        status_text = st.empty()
        
        # 병렬 처리로 각 페이지 분석
        with ThreadPoolExecutor(max_workers=3) as executor:  # 동시 처리 수 제한
            # 작업 제출
            future_to_page = {
                executor.submit(analyze_single_page, page_info, user_prompt): page_info['page_num'] 
                for page_info in page_files
            }
            
            completed = 0
            for future in as_completed(future_to_page):
                try:
                    result = future.result()
                    results.append(result)
                    completed += 1
                    
                    # 진행률 업데이트
                    progress = completed / total_pages
                    progress_bar.progress(progress)
                    status_text.text(f"페이지 {completed}/{total_pages} 분석 완료...")
                    
                except Exception as e:
                    page_num = future_to_page[future]
                    st.warning(f"페이지 {page_num} 분석 중 오류: {e}")
                    results.append({
                        'page_num': page_num,
                        'keywords': '분석,실패,오류',
                        'relevance': '하'
                    })
                    completed += 1
                    progress_bar.progress(completed / total_pages)
        
        progress_bar.empty()
        status_text.empty()
        
        # 3단계: 관련도 순으로 정렬 및 필터링
        relevance_order = {'상': 3, '중': 2, '하': 1}
        
        # 관련도가 '하'가 아닌 것들만 선택하고 정렬
        filtered_results = [r for r in results if r['relevance'] != '하']
        if not filtered_results:
            # 모든 페이지가 '하'인 경우, 상위 10개 선택
            filtered_results = sorted(results, key=lambda x: x['page_num'])[:10]
        
        # 관련도 순으로 정렬 (상 > 중 > 하 순)
        sorted_results = sorted(filtered_results, 
                              key=lambda x: (relevance_order.get(x['relevance'], 0), -x['page_num']), 
                              reverse=True)
        
        # 최대 10개까지만 반환
        final_results = sorted_results[:10]
        
        st.success(f"✅ {len(final_results)}개 관련 페이지 분석 완료!")
        
        return final_results
        
    except Exception as e:
        st.error(f"페이지별 분석 중 오류: {e}")
        # 오류 발생시 임시 파일들 정리
        try:
            if 'page_files' in locals():
                for page_info in page_files:
                    if os.path.exists(page_info['file_path']):
                        os.unlink(page_info['file_path'])
        except:
            pass
        return []

# ★ 변경: 선택 페이지만 새 PDF로 작성 후 Gemini 호출
def generate_final_answer_from_selected_pages(selected_pages, user_prompt):
    if not selected_pages:
        return "선택된 페이지가 없습니다."

    # 1) 원본 PDF 바이트 → Reader
    reader = PdfReader(io.BytesIO(st.session_state.original_pdf_bytes))

    # 2) Writer에 선택 페이지 추가 (1-based → 0-based)
    writer = PdfWriter()
    # 선택된 페이지를 정렬하여 순서를 보장합니다.
    sorted_pages = sorted(selected_pages)
    for p in sorted_pages:
        if 1 <= p <= len(reader.pages):
            writer.add_page(reader.pages[p - 1])

    # 3) 임시 파일로 저장 후 업로드
    with tempfile.NamedTemporaryFile(delete=False, suffix=".pdf") as tmp:
        writer.write(tmp)
        tmp_path = tmp.name
    uploaded_sel = upload_pdf_to_gemini(tmp_path)
    os.unlink(tmp_path)  # 임시 파일 삭제

    # 4) Gemini 프롬프트 & 호출 (★ 이 부분이 핵심 수정사항입니다)
    
    # 페이지 매핑 정보 생성 (예: "임시 PDF 1페이지 -> 원본 PDF 13페이지, ...")
    mapping_info = ", ".join(
        [f"임시 PDF의 {i+1}페이지는 원본 PDF의 {p}페이지에 해당합니다" for i, p in enumerate(sorted_pages)]
    )

    prompt = f"""
    당신은 PDF 문서 분석 전문가입니다.
    주어진 PDF 파일은 사용자가 원본 문서에서 특정 페이지만을 추출하여 만든 임시 파일입니다.
    답변 시에는 반드시 '원본 PDF의 페이지 번호'를 기준으로 설명해야 합니다.

    ## 페이지 매핑 정보
    {mapping_info}

    ## 사용자 질문
    {user_prompt}

    ## 지시사항
    1. 제공된 PDF 내용만을 기반으로, 사용자 질문에 대해 상세하고 구조적으로 답변하세요.
    2. 답변 내용의 근거를 제시할 때는, 위 '페이지 매핑 정보'를 참고하여 **반드시 원본 PDF의 페이지 번호를 언급**해주세요. (예: "원본 PDF 13페이지에 따르면...")
    3. 다른 페이지의 내용과 연관지어 설명하지 말고, 주어진 PDF 범위 안에서만 답변을 생성하세요.
    """
    model = genai.GenerativeModel("gemini-1.5-flash")
    resp = model.generate_content([uploaded_sel, prompt])
    return resp.text


# ───────────────────────────────────────────────
# 4. 1단계: 업로드 & 질문 입력
# ───────────────────────────────────────────────
st.header("1단계: PDF 업로드 및 질문 입력")
with st.form("upload_form"):
    col1, col2 = st.columns(2)
    with col1:
        pdf_file = st.file_uploader("PDF 파일을 선택하세요", type=['pdf'])
    with col2:
        user_prompt = st.text_input("분석할 질문 입력", placeholder="예: 요구자본의 정의 알려줘")
    submitted = st.form_submit_button("PDF 분석 시작", type="primary")

if submitted and pdf_file and user_prompt:
    with st.spinner("PDF 분석 준비 중..."):
        # ① 원본 바이트 저장
        pdf_bytes = pdf_file.read()
        st.session_state.original_pdf_bytes = pdf_bytes   # ★ 변경
        pdf_file.seek(0)                                  # 포인터 리셋
        
        # ② 썸네일용 이미지 변환
        st.session_state.pdf_images = convert_pdf_to_images(pdf_bytes)

        # ④ 관련 페이지 추출 (새로운 방식: 페이지별 개별 분석)
        analysis_results = find_relevant_pages_with_gemini(pdf_bytes, user_prompt)
        
        if analysis_results:
            # 결과를 세션 상태에 저장
            st.session_state.relevant_pages = [r['page_num'] for r in analysis_results]
            st.session_state.page_info = {
                r['page_num']: {
                    'keywords': r['keywords'],
                    'relevance': r['relevance']
                } for r in analysis_results
            }
        else:
            st.warning("관련 페이지를 찾지 못했습니다.")
            st.session_state.relevant_pages = []
            st.session_state.page_info = {}

        st.session_state.step = 2

# ───────────────────────────────────────────────
# 5. 2단계: 페이지 선택
# ───────────────────────────────────────────────
if st.session_state.step >= 2 and st.session_state.relevant_pages:
    st.header("2단계: 관련 페이지 확인 & 선택")
    st.write(f"**AI 추천 페이지:** {', '.join(map(str, st.session_state.relevant_pages))}")

    # 위쪽 버튼 자리
    top_msg = st.empty()
    top_btn = st.empty()

    # 체크박스 UI
    selected_pages = []
    cols = st.columns(3)
    for i, p in enumerate(st.session_state.relevant_pages):
        with cols[i % 3]:
            with st.container(border=True):
                # 체크박스와 페이지 번호
                cb_col, txt_col = st.columns([1, 5])
                with cb_col:
                    if st.checkbox("", key=f"cb_{p}", label_visibility="collapsed"):
                        selected_pages.append(p)
                with txt_col:
                    st.markdown(f"**📄 페이지 {p}**")
                
                # 키워드와 관련도 표시
                if p in st.session_state.page_info:
                    info = st.session_state.page_info[p]
                    keywords = info.get('keywords', '')
                    relevance = info.get('relevance', '')
                    
                    # 관련도에 따른 색상 설정
                    if relevance == '상':
                        color = "🔴"
                        bg_color = "#ffe6e6"
                    elif relevance == '중':
                        color = "🟡"
                        bg_color = "#fff9e6"
                    else:
                        color = "⚪"
                        bg_color = "#f0f0f0"
                    
                    # 키워드와 관련도 박스
                    st.markdown(f"""
                    <div style="background-color: {bg_color}; padding: 8px; border-radius: 5px; margin: 5px 0;">
                        <div style="font-size: 0.8em; font-weight: bold;">
                            {color} 관련도: {relevance}
                        </div>
                        <div style="font-size: 0.75em; color: #666;">
                            🔑 {keywords}
                        </div>
                    </div>
                    """, unsafe_allow_html=True)
                
                # 페이지 이미지
                if p-1 < len(st.session_state.pdf_images):
                    st.image(st.session_state.pdf_images[p-1], use_column_width=True)

    st.session_state.selected_pages = selected_pages

    # 위쪽 버튼 활성화
    if selected_pages:
        top_msg.success(f"선택된 페이지: {', '.join(map(str, selected_pages))}")
        if top_btn.button("선택된 페이지만으로 최종 분석 실행", type="primary", key="run_top"):
            st.session_state.step = 3
    else:
        top_msg.info("페이지를 선택해주세요.")

    st.markdown("---")
    # 아래쪽도 동일 버튼
    if selected_pages:
        st.success(f"선택된 페이지: {', '.join(map(str, selected_pages))}")
        if st.button("선택된 페이지만으로 최종 분석 실행", type="primary", key="run_bottom"):
            st.session_state.step = 3
    else:
        st.info("페이지를 선택해야 버튼이 활성화됩니다.")


# ───────────────────────────────────────────────
# 6. 3단계: 최종 분석
# ───────────────────────────────────────────────
if st.session_state.step >= 3 and st.session_state.selected_pages:
    st.header("3단계: 최종 분석 결과")
    with st.spinner("선택한 페이지만으로 AI가 답변 생성 중..."):
        answer = generate_final_answer_from_selected_pages(
            st.session_state.selected_pages,
            user_prompt
        )

    st.subheader("📋 분석 결과")
    st.write(f"**질문:** {user_prompt}")
    st.write(f"**분석한 페이지:** {', '.join(map(str, st.session_state.selected_pages))}")
    st.write(answer)

    if st.button("새로운 분석 시작"):
        for k in ['relevant_pages', 'page_info', 'selected_pages',
                  'original_pdf_bytes', 'pdf_images', 'step']:
            st.session_state.pop(k, None)
        st.rerun()