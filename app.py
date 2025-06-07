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
st.sidebar.markdown('<p style="color: red; font-size: 0.8em;">(주의) 본 AI가 제공하는 답변은 참고용입니다.</p>', unsafe_allow_html=True)
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
    'selected_pages': [],
    'uploaded_file': None,
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

def find_relevant_pages_with_gemini(uploaded_file, user_prompt):
    try:
        prompt = f"""
        업로드된 PDF 문서를 분석하여 다음 질문과 관련이 있을 수 있는 페이지 번호들을 찾아주세요.
        
        사용자의 질문: {user_prompt}
        
        지시사항:
        1. PDF 문서 전체를 꼼꼼히 분석해주세요
        2. 질문과 직접적으로 관련된 페이지뿐만 아니라 간접적으로 관련될 수 있는 페이지도 포함해주세요
        3. 답변은 페이지 번호만 쉼표로 구분하여 제공하고, 다른 설명은 하지 마세요
        4. 페이지 번호는 1부터 시작합니다
        
        예시 답변 형식: 3, 111, 253, 299
        """
        model = genai.GenerativeModel('gemini-1.5-flash')
        resp = model.generate_content([uploaded_file, prompt])
        return resp.text.strip()
    except Exception as e:
        st.error(f"Gemini 호출 오류: {e}")
        return ""

# ★ 변경: 선택 페이지만 새 PDF로 작성 후 Gemini 호출
def generate_final_answer_from_selected_pages(selected_pages, user_prompt):
    if not selected_pages:
        return "선택된 페이지가 없습니다."

    # 1) 원본 PDF 바이트 → Reader
    reader = PdfReader(io.BytesIO(st.session_state.original_pdf_bytes))

    # 2) Writer에 선택 페이지 추가 (1-based → 0-based)
    writer = PdfWriter()
    for p in selected_pages:
        if 1 <= p <= len(reader.pages):
            writer.add_page(reader.pages[p-1])

    # 3) 임시 파일로 저장 후 업로드
    with tempfile.NamedTemporaryFile(delete=False, suffix=".pdf") as tmp:
        writer.write(tmp)
        tmp_path = tmp.name
    uploaded_sel = upload_pdf_to_gemini(tmp_path)
    os.unlink(tmp_path)           # 임시 파일 삭제

    # 4) Gemini 프롬프트 & 호출
    pages_txt = ", ".join(map(str, selected_pages))
    prompt = f"""
    다음 PDF는 사용자가 선택한 페이지({pages_txt})만 포함합니다.

    질문: {user_prompt}

    지시사항:
    1. PDF 범위 안에서만 답변하세요.
    2. 가능하면 페이지 번호 근거를 명시하세요.
    3. 항목·소제목으로 구조화해 주세요.
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
    with st.spinner("PDF 업로드 및 AI 분석 중..."):
        # ① 원본 바이트 저장
        pdf_bytes = pdf_file.read()
        st.session_state.original_pdf_bytes = pdf_bytes   # ★ 변경
        pdf_file.seek(0)                                  # 포인터 리셋
        
        # ② Gemini에 원본 PDF 업로드
        with tempfile.NamedTemporaryFile(delete=False, suffix=".pdf") as tmp:
            tmp.write(pdf_bytes)
            tmp_path = tmp.name
        uploaded_file = upload_pdf_to_gemini(tmp_path)
        os.unlink(tmp_path)
        st.session_state.uploaded_file = uploaded_file

        # ③ 썸네일용 이미지 변환
        st.session_state.pdf_images = convert_pdf_to_images(pdf_bytes)

        # ④ 관련 페이지 추출
        pages_str = find_relevant_pages_with_gemini(uploaded_file, user_prompt)
        try:
            nums = [int(x.strip()) for x in pages_str.split(',') if x.strip().isdigit()]
            st.session_state.relevant_pages = [p for p in nums if 1 <= p <= len(st.session_state.pdf_images)]
        except:
            st.session_state.relevant_pages = []

        st.session_state.step = 2
        st.success("AI가 관련 페이지를 찾았습니다!")

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
                cb_col, txt_col = st.columns([1, 5])
                with cb_col:
                    if st.checkbox("", key=f"cb_{p}", label_visibility="collapsed"):
                        selected_pages.append(p)
                with txt_col:
                    st.markdown(f"**📄 페이지 {p}**")
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
        for k in ['relevant_pages', 'selected_pages', 'uploaded_file',
                  'original_pdf_bytes', 'pdf_images', 'step']:
            st.session_state.pop(k, None)
        st.rerun()