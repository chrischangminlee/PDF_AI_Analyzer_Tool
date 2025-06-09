import streamlit as st
import google.generativeai as genai
from dotenv import load_dotenv
import os, io, tempfile
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
    'page_info': {},
    'selected_pages': [],
    'user_prompt': "", # ★ 추가: 사용자 질문 저장
    'original_pdf_bytes': None,
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

# ★★★★★ 수정된 핵심 함수 ★★★★★
def parse_page_info(gemini_response):
    """Gemini 응답을 파싱하여 페이지 정보 추출"""
    pages = []
    page_info = {}
    
    for line in gemini_response.strip().split('\n'):
        if '|' in line:
            try:
                parts = line.strip().split('|')
                if len(parts) == 4:
                    physical_page = int(parts[0].strip())
                    logical_page = parts[1].strip()
                    keywords = parts[2].strip()
                    relevance = parts[3].strip()
                    
                    pages.append(physical_page)
                    page_info[physical_page] = {
                        'logical_page': logical_page,
                        'keywords': keywords,
                        'relevance': relevance
                    }
            except (ValueError, IndexError) as e:
                st.warning(f"응답 라인 파싱 실패: '{line}', 오류: {e}")
                continue
    
    return pages, page_info

def find_relevant_pages_with_gemini(uploaded_file, user_prompt):
    try:
        prompt = f"""
        업로드된 PDF 문서를 분석하여 다음 질문과 관련이 있을 수 있는 페이지들을 찾아주세요.
        사용자의 질문: {user_prompt}
        지시사항:
        1. PDF 문서 전체를 꼼꼼히 분석해주세요.
        2. 각 페이지를 분석할 때는 다른 페이지의 내용은 절대 고려하지 말고, 해당 페이지의 정보에만 집중해주세요.
        3. 질문의 핵심 키워드들이 포함된 페이지만을 포함해주세요.
        4. **PDF 실제 페이지 번호**는 1부터 시작합니다.
        5. **문서에 인쇄된 페이지 번호**가 페이지의 상단이나 하단에 있다면, 그 번호도 함께 찾아주세요. 없다면 '없음'으로 표기합니다.
        6. 각 페이지에 대해 다음 정보를 제공해주세요:
           - PDF 실제 페이지 번호 (1부터 시작)
           - 문서에 인쇄된 페이지 번호 (없으면 '없음')
           - 해당 페이지의 핵심 키워드 3개 (콤마로 구분)
           - 질문과의 관련도 (상/중/하 중 하나)
        7. 관련도가 높은 순서대로 최대 10개 페이지까지 추천해주세요.
        응답 형식 (각 줄마다 하나의 페이지 정보, 파이프(|)로 구분):
        PDF실제페이지|문서상페이지|키워드1,키워드2,키워드3|관련도
        예시:
        3|없음|목차,서문,개요|하
        13|7|요구자본,리스크,자본충족률|상
        25|19|보험료,계리,위험률|중
        """
        model = genai.GenerativeModel('gemini-1.5-flash')
        resp = model.generate_content([uploaded_file, prompt])
        return resp.text.strip()
    except Exception as e:
        st.error(f"Gemini 호출 오류: {e}")
        return ""

def generate_final_answer_from_selected_pages(selected_pages, user_prompt):
    if not selected_pages:
        return "선택된 페이지가 없습니다."

    reader = PdfReader(io.BytesIO(st.session_state.original_pdf_bytes))
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

    # 페이지 매핑 정보 생성 (★ 개선: 논리적 페이지 번호도 함께 제공)
    mapping_parts = []
    for i, p in enumerate(sorted_pages):
        logical_page = st.session_state.page_info.get(p, {}).get('logical_page', '없음')
        if logical_page != '없음':
            mapping_parts.append(f"임시 PDF {i+1}페이지는 원본 문서의 '{logical_page}' 페이지(실제 {p}페이지)에 해당합니다")
        else:
            mapping_parts.append(f"임시 PDF {i+1}페이지는 원본 문서의 실제 {p}페이지에 해당합니다")
    mapping_info = "\n".join(mapping_parts)

    prompt = f"""
    당신은 PDF 문서 분석 전문가입니다.
    주어진 PDF 파일은 사용자가 원본 문서에서 특정 페이지만을 추출하여 만든 임시 파일입니다.
    답변 시에는 반드시 사용자가 이해하기 쉽도록 '원본 문서의 페이지 번호'를 기준으로 설명해야 합니다.

    ## 페이지 매핑 정보
    {mapping_info}

    ## 사용자 질문
    {user_prompt}

    ## 지시사항
    1. 제공된 PDF 내용만을 기반으로, 사용자 질문에 대해 상세하고 구조적으로 답변하세요.
    2. 답변 내용의 근거를 제시할 때, 위 '페이지 매핑 정보'를 참고하여 **반드시 원본 문서의 페이지 번호(예: '원본 13페이지')를 언급**해주세요. 문서상 페이지 번호가 없는 경우에만 실제 페이지 번호를 사용하세요.
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
        user_prompt_input = st.text_input("분석할 질문 입력", placeholder="예: 요구자본의 정의 알려줘")
    submitted = st.form_submit_button("PDF 분석 시작", type="primary")

if submitted and pdf_file and user_prompt_input:
    with st.spinner("PDF 업로드 및 AI 분석 중..."):
        # 세션 초기화
        for k in ['relevant_pages', 'page_info', 'selected_pages', 'uploaded_file', 'original_pdf_bytes', 'pdf_images']:
            st.session_state[k] = [] if isinstance(st.session_state.get(k), list) else {} if isinstance(st.session_state.get(k), dict) else None

        pdf_bytes = pdf_file.read()
        st.session_state.original_pdf_bytes = pdf_bytes
        st.session_state.user_prompt = user_prompt_input # ★ 질문 저장
        
        with tempfile.NamedTemporaryFile(delete=False, suffix=".pdf") as tmp:
            tmp.write(pdf_bytes)
            tmp_path = tmp.name
        
        try:
            uploaded_file = upload_pdf_to_gemini(tmp_path)
        finally:
            os.unlink(tmp_path)
        
        st.session_state.pdf_images = convert_pdf_to_images(pdf_bytes)
        
        pages_response = find_relevant_pages_with_gemini(uploaded_file, user_prompt_input)
        
        # ★ 변경: 수정된 파서 사용 및 폴백 로직 제거
        pages, page_info = parse_page_info(pages_response)
        
        total_pages = len(st.session_state.pdf_images)
        valid_pages = [p for p in pages if 1 <= p <= total_pages]
        
        st.session_state.relevant_pages = valid_pages
        st.session_state.page_info = page_info

        st.session_state.step = 2
        st.success("AI가 관련 페이지를 찾았습니다!")
        st.rerun() # ★ 추가: 폼 제출 후 상태를 반영하기 위해 rerun


# ───────────────────────────────────────────────
# 5. 2단계: 페이지 선택
# ───────────────────────────────────────────────
if st.session_state.step >= 2 and st.session_state.relevant_pages:
    st.header("2단계: 관련 페이지 확인 & 선택")
    
    # AI 추천 페이지 번호들을 문자열로 변환 (논리적 페이지 우선)
    recommended_pages_display = []
    for p in st.session_state.relevant_pages:
        info = st.session_state.page_info.get(p, {})
        logical_page = info.get('logical_page', '없음')
        if logical_page != '없음':
            recommended_pages_display.append(logical_page)
        else:
            recommended_pages_display.append(f"실제 {p}")

    st.write(f"**AI 추천 페이지:** {', '.join(recommended_pages_display)}")

    top_msg = st.empty()
    top_btn = st.empty()

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
                    # ★★★★★ UI 수정된 부분 ★★★★★
                    info = st.session_state.page_info.get(p, {})
                    logical_page = info.get('logical_page', '없음')
                    if logical_page != '없음':
                        st.markdown(f"**📄 문서 {logical_page} 페이지** (실제: {p})")
                    else:
                        st.markdown(f"**📄 실제 {p} 페이지**")

                if p in st.session_state.page_info:
                    info = st.session_state.page_info[p]
                    keywords = info.get('keywords', '')
                    relevance = info.get('relevance', '')
                    
                    if relevance == '상': color, bg_color = "🔴", "#ffe6e6"
                    elif relevance == '중': color, bg_color = "🟡", "#fff9e6"
                    else: color, bg_color = "⚪", "#f0f0f0"
                    
                    st.markdown(f"""
                    <div style="background-color: {bg_color}; padding: 8px; border-radius: 5px; margin: 5px 0;">
                        <div style="font-size: 0.8em; font-weight: bold;">{color} 관련도: {relevance}</div>
                        <div style="font-size: 0.75em; color: #666;">🔑 {keywords}</div>
                    </div>
                    """, unsafe_allow_html=True)
                
                if p-1 < len(st.session_state.pdf_images):
                    st.image(st.session_state.pdf_images[p-1], use_column_width=True)

    st.session_state.selected_pages = selected_pages

    if selected_pages:
        display_selected = [st.session_state.page_info.get(p, {}).get('logical_page', str(p)) for p in selected_pages]
        top_msg.success(f"선택된 페이지: {', '.join(display_selected)}")
        if top_btn.button("선택된 페이지만으로 최종 분석 실행", type="primary", key="run_top"):
            st.session_state.step = 3
            st.rerun()
    else:
        top_msg.info("페이지를 선택해주세요.")

    st.markdown("---")
    if selected_pages:
        if st.button("선택된 페이지만으로 최종 분석 실행", type="primary", key="run_bottom"):
            st.session_state.step = 3
            st.rerun()

# ───────────────────────────────────────────────
# 6. 3단계: 최종 분석
# ───────────────────────────────
if st.session_state.step >= 3 and st.session_state.selected_pages:
    st.header("3단계: 최종 분석 결과")
    with st.spinner("선택한 페이지만으로 AI가 답변 생성 중..."):
        answer = generate_final_answer_from_selected_pages(
            st.session_state.selected_pages,
            st.session_state.user_prompt
        )

    st.subheader("📋 분석 결과")
    st.write(f"**질문:** {st.session_state.user_prompt}")
    
    display_selected = []
    for p in sorted(st.session_state.selected_pages):
        logical_page = st.session_state.page_info.get(p, {}).get('logical_page', '없음')
        if logical_page != '없음':
            display_selected.append(logical_page)
        else:
            display_selected.append(f"실제 {p}")

    st.write(f"**분석한 페이지:** {', '.join(display_selected)}")
    st.markdown(answer)

    if st.button("새로운 분석 시작"):
        # 모든 세션 상태 키 초기화
        for key in list(st.session_state.keys()):
            del st.session_state[key]
        st.rerun()