import streamlit as st
import google.generativeai as genai
from dotenv import load_dotenv
import os, io, time, tempfile, base64
from PyPDF2 import PdfReader, PdfWriter
from pdf2image import convert_from_bytes
from PIL import Image

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
    "본 PDF AI 세부 분석 Tool은 단계적 AI활용과 Human Input을 통해 AI 환각효과를 최소화 하고자 합니다.  \n"
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

def parse_page_info(gemini_response):
    """Gemini 응답을 파싱하여 페이지 정보 추출"""
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

def find_relevant_pages_gemini_batch(pdf_bytes, user_prompt):
    """
    단일 API 호출로 PDF의 모든 페이지를 분석하여 관련 페이지를 찾습니다.
    """
    try:
        # 1. 원본 PDF 바이트를 임시 파일에 저장 후 Gemini에 한 번만 업로드
        with tempfile.NamedTemporaryFile(delete=False, suffix=".pdf") as tmp:
            tmp.write(pdf_bytes)
            tmp_path = tmp.name
        
        st.info("📄 PDF 전체를 Gemini에 업로드하는 중...")
        uploaded_file = upload_pdf_to_gemini(tmp_path)
        os.unlink(tmp_path) # 업로드 후 임시 파일 즉시 삭제

        # 2. 모든 페이지를 한 번에 분석하도록 요청하는 프롬프트
        st.info("📊 AI가 전체 페이지를 분석 중입니다. 잠시만 기다려주세요...")
        
        prompt = f"""
        당신은 문서를 정밀하게 분석하는 AI 전문가입니다.
        주어진 PDF 파일 전체를 페이지별로 분석하여 아래 사용자 질문과 각 페이지의 관련성을 평가해주세요.

        ## 사용자 질문:
        {user_prompt}

        ## 분석 지시사항:
        1. PDF의 **모든 페이지**를 처음부터 끝까지 순서대로 검토하세요.
        2. 각 페이지를 분석할 때는 다른 페이지의 내용은 고려하지 말고, 해당 페이지의 정보에만 집중해주세요.
        3. 각 페이지별로 사용자 질문과의 관련도를 '상', '중', '하'로 평가해주세요.
        4. 각 페이지의 핵심 내용을 나타내는 키워드를 3개 추출해주세요.
        5. 아래 '응답 형식'을 반드시 정확하게 지켜서, 모든 페이지에 대한 결과를 한 줄씩 출력해주세요.

        ## 응답 형식 (페이지 번호 | 키워드1,키워드2,키워드3 | 관련도):
        1|요약,소개,목차|하
        2|요구자본,리스크,정의|상
        3|시장위험,신용위험,상관계수|중
        ...
        (이하 모든 페이지에 대해 반복)
        """

        model = genai.GenerativeModel('gemini-1.5-flash')
        response = model.generate_content([uploaded_file, prompt])
        
        # 3. Gemini 응답 파싱 (기존 함수 재활용)
        # 이 함수는 "페이지번호|키워드|관련도" 형식의 텍스트를 파싱하는 역할을 합니다.
        all_pages, page_info_dict = parse_page_info(response.text)

        if not all_pages:
            st.warning("관련 페이지 정보를 추출하지 못했습니다. AI 응답 형식을 확인해보세요.")
            return []

        # 4. 결과 필터링 및 정렬 (기존 로직과 동일)
        results = [
            {'page_num': p, **page_info_dict[p]} for p in all_pages if p in page_info_dict
        ]
        
        relevance_order = {'상': 3, '중': 2, '하': 1}
        
        # 관련도가 '하'가 아닌 것만 선택
        filtered_results = [r for r in results if r.get('relevance') != '하']
        
        # 만약 모든 페이지의 관련도가 '하'라면, 그냥 페이지 순서대로 상위 10개 표시
        if not filtered_results:
            st.info("모든 페이지의 관련도가 '하'로 평가되어, 문서의 첫 10페이지를 추천합니다.")
            filtered_results = sorted(results, key=lambda x: x['page_num'])[:10]

        # 관련도 높은 순 -> 페이지 번호 높은 순 (내림차순 정렬)
        sorted_results = sorted(filtered_results,
                                key=lambda x: (relevance_order.get(x.get('relevance'), 0), x['page_num']),
                                reverse=True)
        
        final_results = sorted_results[:10] # 최대 10개 까지만 반환
        
        st.success(f"✅ {len(final_results)}개 관련 페이지 분석 완료!")
        return final_results

    except Exception as e:
        st.error(f"페이지 일괄 분석 중 오류 발생: {e}")
        # 오류 발생 시 생성되었을 수 있는 임시 파일 정리
        if 'tmp_path' in locals() and os.path.exists(tmp_path):
            os.unlink(tmp_path)
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

        # ④ 관련 페이지 추출 (개선된 방식: 단일 호출 일괄 분석)
        analysis_results = find_relevant_pages_gemini_batch(pdf_bytes, user_prompt)
        
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