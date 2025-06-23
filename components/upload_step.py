import streamlit as st
import tempfile, os
from services.pdf_service import annotate_pdf_with_page_numbers, upload_pdf_to_gemini, convert_pdf_to_images
from services.gemini_service import find_relevant_pages_with_gemini, parse_page_info

# === 1단계 UI & 로직 (원본 섹션 4) 전체 붙여넣기 ===
def run_upload_step():
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

    # 예시 PDF 불러오기 / 제거 버튼 (form 밖에서 처리)
    st.write("예시 PDF를 활용하거나, PDF를 불러오세요")

    col1, col2 = st.columns(2)
    with col1:
        if st.session_state.get('example_pdf_loaded', False):
            # 예시 PDF가 로드된 경우: 제거 버튼만 표시
            if st.button("🗑️ 예시 PDF 제거", type="secondary"):
                st.session_state['example_pdf_loaded'] = False
                if 'example_pdf_bytes' in st.session_state:
                    del st.session_state['example_pdf_bytes']
                st.rerun()
        else:
            # 예시 PDF가 로드되지 않은 경우: 불러오기 버튼만 표시
            if st.button("📄 예시 PDF (K-ICS 해설서) 불러오기", type="secondary"):
                example_pdf_bytes = load_example_pdf()
                if example_pdf_bytes:
                    st.session_state['example_pdf_loaded'] = True
                    st.session_state['example_pdf_bytes'] = example_pdf_bytes
                    st.success("✅ 예시 PDF가 로드되었습니다!")
                    st.rerun()

    with st.form("upload_form"):
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

        # 분석 시작 버튼 (form 안의 유일한 submit button)
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
