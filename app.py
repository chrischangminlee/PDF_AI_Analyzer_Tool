import streamlit as st
import google.generativeai as genai
from dotenv import load_dotenv
import os, io, tempfile
from PyPDF2 import PdfReader, PdfWriter
from pdf2image import convert_from_bytes
from PIL import Image

# ★★★ 페이지 번호 오버레이용
from reportlab.pdfgen import canvas          # ★★★
from reportlab.lib.units import mm           # ★★★

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
* 무료 Gemini model (Gemini 2.0 flash) 을 사용하고 있어 답변 생성 속도가 느릴 수 있습니다.
""")
st.sidebar.markdown('<p style="color: red; font-size: 0.8em;">(주의)본 AI가 제공하는 답변은 참고용이며, 정확성을 보장할 수 없습니다. 보안을 위해 회사 기밀, 개인정보등은 제공하지 않기를 권장드리며, 반드시 실제 업무에 적용하기 전에 검토하시길 바랍니다.</p>', unsafe_allow_html=True)
st.sidebar.markdown("### 타 Link")
st.sidebar.markdown("[개발자 링크드인](https://www.linkedin.com/in/chrislee9407/)")
st.sidebar.markdown("[K-계리 AI 플랫폼](https://chrischangminlee.github.io/K_Actuary_AI_Agent_Platform/)")
st.sidebar.markdown("[K-Actuary AI Doc Analyzer (Old Ver.)](https://kactuarypdf.streamlit.app/)")

# ───────────────────────────────────────────────
# PDF 텍스트 분석 도구 (임시 디버깅용)
# ───────────────────────────────────────────────
st.sidebar.markdown("---")
st.sidebar.markdown("### 🔧 PDF 텍스트 분석 도구")
st.sidebar.markdown("<small>페이지별 텍스트 추출 상태 확인용 (임시)</small>", unsafe_allow_html=True)

st.title("이창민의 PDF AI 세부 분석 Tool")
st.write(
    "본 PDF AI 세부 분석 Tool은 단계적 AI활용과 Human Input을 통해 AI 환각효과를 최소화 하고자 합니다.  \n"
    "- **1단계 (AI분석):** PDF 업로드 + 분석 요청사항 입력  \n"
    "- **2단계 (Human Input):** 관련 페이지 AI 추천 & 페이지 별 답변 참고하여 최종분석 대상 페이지 직접 선택 \n"
    "- **3단계 (AI최종분석):** 선택된 페이지들 종합하여 최종 분석"
)

# ───────────────────────────────────────────────
# 2. 세션 상태 초기화
# ───────────────────────────────────────────────
for k, v in {
    'relevant_pages': [],
    'page_info': {},
    'selected_pages': [],
    'user_prompt': "",
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
    return genai.upload_file(pdf_path, mime_type="application/pdf")

def convert_pdf_to_images(pdf_bytes):
    try:
        return convert_from_bytes(pdf_bytes, dpi=100, fmt='jpeg')
    except Exception as e:
        st.warning(f"이미지 변환 오류: {e}")
        return []

# ★★★ 페이지 번호 삽입 함수
def annotate_pdf_with_page_numbers(pdf_bytes):
    reader = PdfReader(io.BytesIO(pdf_bytes))
    writer = PdfWriter()

    for idx, page in enumerate(reader.pages):
        # 각 페이지 크기와 동일한 오버레이 PDF 생성
        width = float(page.mediabox.width)
        height = float(page.mediabox.height)

        packet = io.BytesIO()
        c = canvas.Canvas(packet, pagesize=(width, height))
        c.setFont("Helvetica", 9)
        # 좌측 상단(여백 10mm) 위치에 페이지 번호 작성
        c.drawString(10 * mm, height - 15 * mm, str(idx + 1))
        c.save()

        packet.seek(0)
        overlay_pdf = PdfReader(packet)
        page.merge_page(overlay_pdf.pages[0])
        writer.add_page(page)

    output_stream = io.BytesIO()
    writer.write(output_stream)
    return output_stream.getvalue()
# ★★★ 끝

def parse_page_info(gemini_response):
    pages, page_info = [], {}
    for line in gemini_response.strip().split('\n'):
        if '|' in line:
            try:
                parts = line.strip().split('|')
                if len(parts) == 3:
                    physical_page, page_response, relevance = int(parts[0].strip()), parts[1].strip(), parts[2].strip()
                    pages.append(physical_page)
                    page_info[physical_page] = {'page_response': page_response, 'relevance': relevance}
            except (ValueError, IndexError):
                continue
    return pages, page_info

def find_relevant_pages_with_gemini(uploaded_file, user_prompt):
    try:
        prompt = f"""
        당신은 PDF의 각 페이지를 개별적으로 분석하는 고도로 전문화된 '페이지 단위 분석 엔진'입니다. 
        당신의 유일한 임무는 지시에 따라 **물리적 페이지(좌측 상단 번호 기준)**를 하나씩, 완전히 독립적으로 처리하는 것입니다.

        ## 사용자 질문
        {user_prompt}

        ## 처리 절차
        1. **페이지 격리**  
        - 현재 분석할 물리적 페이지 N만을 인식합니다.  
        - 다른 모든 페이지 정보는 **완벽히 무시**합니다.

        2. **독립적 내용 분석**  
        - N페이지 내부의 텍스트·표·이미지 **전용**으로, 사용자 질문과의 **관련도**를 평가합니다.  
        - 관련도 등급  
            • **상** : 질문에 대한 해답을 제공  
            • **중** : 질문의 핵심 키워드를 포함함 
            • **하** : 키워드가 희박하거나 문맥이 사실상 무관

        3. **페이지별 답변 추출**  
        - **오직 N페이지 내용에서만** 질문과 가장 밀접한 정보를 요약‧추출합니다.  
        - 외부 지식·다른 페이지 내용은 절대 사용하지 않습니다.

        4. **결과 생성**  
        - 아래 **“응답 형식”**으로 N페이지 결과 1줄을 작성합니다.  
        - 관련도 **‘하’이거나 무관**할 경우, **출력하지 않습니다**.

        5. **메모리 리셋**  
        - N페이지 작업 종료 즉시, 그 내용과 메타데이터를 **완전 삭제**하고 다음 페이지로 이동합니다.

        ## 추가 지시사항
        - 최대 **10행**만 출력합니다.  
        - **응답 형식**에서 파이프(`|`)는 정확히 **두 개**여야 하며, 그 이외 문자는 금지입니다. 형식 오류가 있으면 결과 전체를 무효로 간주합니다.
        - 최종 결과는 질문과의 관련도가 '상' 또는 '중'인 페이지들만, 최대 10개까지 보여주세요.

        ## 응답 형식 (각 줄마다 하나의 페이지 정보, 파이프(|)로 구분)
        물리적페이지번호|페이지별답변(요약)|관련도

        ## 예시
        10|요구자본 정의 요약|상
        """
        model = genai.GenerativeModel('gemini-2.0-flash')
        resp = model.generate_content([uploaded_file, prompt])
        return resp.text.strip()
    except Exception as e:
        st.error(f"Gemini 호출 오류: {e}")
        return ""

# ★★★★★ 프롬프트가 강화된 함수 ★★★★★
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

    prompt = f"""
    당신은 사용자의 질문에 답변하는 매우 유능하고 친절한 문서 분석 전문가입니다.
    주어진 PDF는 사용자가 원본 문서에서 일부 페이지만을 선택하여 생성한 것입니다.

## 사용자 질문
{user_prompt}

## 상세 지시사항
1. 제공된 PDF 내용만을 기반으로 사용자 질문에 대해 상세하고 구조적으로 답변하세요.
    """
    model = genai.GenerativeModel("gemini-2.0-flash")
    resp = model.generate_content([uploaded_sel, prompt])
    return resp.text


# ───────────────────────────────────────────────
# 4. 1단계: 업로드 & 질문 입력
# ───────────────────────────────────────────────
st.header("1단계: PDF 업로드 및 질문 입력")

# 예시 PDF 로드 기능
def load_example_pdf():
    """예시 PDF 파일을 로드하여 세션 상태에 저장"""
    try:
        example_pdf_path = "Filereference/K-ICS 해설서.pdf"
        with open(example_pdf_path, "rb") as f:
            return f.read()
    except Exception as e:
        st.error(f"예시 PDF 로드 실패: {e}")
        return None

with st.form("upload_form"):
    st.write("예시 PDF를 활용하거나, PDF를 불러오세요")

    # 예시 PDF 불러오기 / 제거 버튼
    if st.session_state.get('example_pdf_loaded', False):
        # 예시 PDF가 로드된 경우: 제거 버튼만 표시
        clear_clicked = st._button("🗑️ 예시 PDF 제거", type="secondary")
        load_clicked = False  # 로드 버튼은 클릭되지 않음
    else:
        # 예시 PDF가 로드되지 않은 경우: 불러오기 버튼만 표시
        load_clicked = st._button("📄 예시 PDF (K-ICS 해설서) 불러오기", type="secondary")
        clear_clicked = False  # 제거 버튼은 클릭되지 않음

    # 버튼 처리 로직
    if load_clicked:
        example_pdf_bytes = load_example_pdf()
        if example_pdf_bytes:
            st.session_state['example_pdf_loaded'] = True
            st.session_state['example_pdf_bytes'] = example_pdf_bytes
            st.success("✅ 예시 PDF가 로드되었습니다!")
            st.rerun()

    if clear_clicked:
        st.session_state['example_pdf_loaded'] = False
        if 'example_pdf_bytes' in st.session_state:
            del st.session_state['example_pdf_bytes']
        st.rerun()

    # PDF 업로드 및 질문 입력
    col3, col4 = st.columns(2)
    with col3:
        if st.session_state.get('example_pdf_loaded', False):
            st.info("📄 **예시 PDF (K-ICS 해설서.pdf)** 가 선택되었습니다.")
            pdf_file = None
        else:
            pdf_file = st.file_uploader("PDF 파일을 선택하세요", type=['pdf'])

    with col4:
        user_prompt_input = st.text_input("분석 요청사항 입력", placeholder="예: 요구자본의 정의 알려줘")

    # 분석 시작 버튼
    submitted = st.form_submit_button("PDF 분석 시작", type="primary")


if submitted and user_prompt_input:
    # PDF 파일 확인 (업로드된 파일 또는 예시 PDF)
    if st.session_state.get('example_pdf_loaded', False):
        pdf_bytes_to_process = st.session_state['example_pdf_bytes']
        pdf_source = "예시 PDF (K-ICS 해설서.pdf)"
    elif pdf_file:
        pdf_bytes_to_process = pdf_file.read()
        pdf_source = pdf_file.name
    else:
        st.error("PDF 파일을 선택하거나 예시 PDF를 로드해주세요.")
        st.stop()

    with st.spinner(f"PDF 업로드 및 AI 분석 중... ({pdf_source})"):
        # 세션 초기화
        for k in ['relevant_pages', 'page_info', 'selected_pages', 'original_pdf_bytes', 'pdf_images']:
            st.session_state[k] = [] if isinstance(st.session_state.get(k), list) else {} if isinstance(st.session_state.get(k), dict) else None

        # 원본 PDF → 페이지 번호 삽입 → 세션 저장
        numbered_bytes = annotate_pdf_with_page_numbers(pdf_bytes_to_process)   # ★★★
        st.session_state.original_pdf_bytes = numbered_bytes             # ★★★
        st.session_state.user_prompt = user_prompt_input

        # Gemini 업로드
        with tempfile.NamedTemporaryFile(delete=False, suffix=".pdf") as tmp:
            tmp.write(numbered_bytes)                                    # ★★★
            tmp_path = tmp.name
        try:
            uploaded_file = upload_pdf_to_gemini(tmp_path)
        finally:
            os.unlink(tmp_path)

        # 이미지 변환 (페이지 번호가 찍힌 상태)
        st.session_state.pdf_images = convert_pdf_to_images(numbered_bytes)   # ★★★

        # 관련 페이지 탐색
        pages_response = find_relevant_pages_with_gemini(uploaded_file, user_prompt_input)
        pages, page_info = parse_page_info(pages_response)
        total_pages = len(st.session_state.pdf_images)
        st.session_state.relevant_pages = list(dict.fromkeys([p for p in pages if 1 <= p <= total_pages]))
        st.session_state.page_info = page_info

        st.session_state.step = 2
        st.success("AI가 관련 페이지를 찾았습니다!")
        st.rerun()


# ───────────────────────────────────────────────
# 5. 2단계: 페이지 선택
# ───────────────────────────────────────────────
if st.session_state.step >= 2 and st.session_state.relevant_pages:
    st.header("2단계: 관련 페이지 확인 & 선택")
    st.write(f"**AI 추천 페이지 수:** {len(st.session_state.relevant_pages)}개")
    st.write("선별된 페이지위에 마우스를 올리면 나타나는 확대 버튼으로 내용을 확인할 수 있어요.")

    top_msg, top_btn = st.empty(), st.empty()
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
                    st.markdown(f"**📄 관련 페이지**")

                if p in st.session_state.page_info:
                    info = st.session_state.page_info[p]
                    page_response, relevance = info.get('page_response', ''), info.get('relevance', '')

                    if relevance == '상':
                        color, bg_color = "🔴", "#ffe6e6"
                    elif relevance == '중':
                        color, bg_color = "🟡", "#fff9e6"
                    else:
                        color, bg_color = "⚪", "#f0f0f0"

                    st.markdown(f"""
                    <div style="background-color: {bg_color}; padding: 8px; border-radius: 5px; margin: 5px 0;">
                        <div style="font-size: 0.8em; font-weight: bold;">{color} 관련도: {relevance}</div>
                        <div style="font-size: 0.75em; color: #666;">🔑 {page_response}</div>
                    </div>""", unsafe_allow_html=True)

                if p - 1 < len(st.session_state.pdf_images):
                    st.image(st.session_state.pdf_images[p - 1], use_column_width=True)

    st.session_state.selected_pages = selected_pages

    if selected_pages:
        top_msg.success(f"선택된 페이지: {len(selected_pages)}개")
        if top_btn.button("선택된 페이지만으로 최종 분석 실행", type="primary", key="run_top"):
            st.session_state.step = 3
            st.rerun()
    else:
        top_msg.info("분석할 페이지를 선택해주세요.")

    st.markdown("---")
    if selected_pages:
        if st.button("선택된 페이지만으로 최종 분석 실행", type="primary", key="run_bottom"):
            st.session_state.step = 3
            st.rerun()

# ───────────────────────────────────────────────
# 6. 3단계: 최종 분석
# ───────────────────────────────────────────────
if st.session_state.step >= 3 and st.session_state.selected_pages:
    st.header("3단계: 최종 분석 결과")
    with st.spinner("선별된 페이지로 PDF 최종 AI 분석 중..."):
        answer = generate_final_answer_from_selected_pages(
            st.session_state.selected_pages,
            st.session_state.user_prompt
        )

    st.subheader("📋 분석 결과")
    st.write(f"**질문:** {st.session_state.user_prompt}")
    st.write(f"**분석에 사용된 페이지 수:** {len(st.session_state.selected_pages)}개")
    st.markdown(answer)

    if st.button("새로운 분석 시작"):
        for key in list(st.session_state.keys()):
            del st.session_state[key]
        st.rerun()
