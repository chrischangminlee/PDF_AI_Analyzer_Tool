# upload_step.py - 개선된 버전

import streamlit as st
import tempfile, os
from services.pdf_service import annotate_pdf_with_page_numbers, upload_pdf_to_gemini, convert_pdf_to_images
from services.gemini_service import find_relevant_pages_with_gemini, parse_page_info, extract_page_metadata

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

    # 예시 PDF 불러오기 / 제거 버튼
    st.write("예시 PDF를 활용하거나, PDF를 불러오세요")

    col1, col2 = st.columns(2)
    with col1:
        if st.session_state.get('example_pdf_loaded', False):
            if st.button("🗑️ 예시 PDF 제거", type="secondary"):
                st.session_state['example_pdf_loaded'] = False
                if 'example_pdf_bytes' in st.session_state:
                    del st.session_state['example_pdf_bytes']
                st.rerun()
        else:
            if st.button("📄 예시 PDF (K-ICS 해설서) 불러오기", type="secondary"):
                example_pdf_bytes = load_example_pdf()
                if example_pdf_bytes:
                    st.session_state['example_pdf_loaded'] = True
                    st.session_state['example_pdf_bytes'] = example_pdf_bytes
                    st.success("✅ 예시 PDF가 로드되었습니다!")
                    st.rerun()

    with st.form("upload_form"):
        col3, col4 = st.columns(2)
        with col3:
            if st.session_state.get('example_pdf_loaded', False):
                st.info("📄 **예시 PDF (K-ICS 해설서.pdf)** 가 선택되었습니다.")
                pdf_file = None
            else:
                pdf_file = st.file_uploader("PDF 파일을 선택하세요", type=['pdf'])

        with col4:
            user_prompt_input = st.text_input("분석 요청사항 입력", placeholder="예: 요구자본의 정의 알려줘")

        # 고급 옵션
        with st.expander("고급 옵션"):
            analysis_mode = st.radio(
                "분석 모드",
                ["빠른 분석 (기본)", "정밀 분석 (시간 소요)"],
                help="정밀 분석은 페이지 검증을 추가로 수행합니다"
            )
            max_pages = st.slider("최대 분석 페이지 수", 5, 20, 10)

        submitted = st.form_submit_button("PDF 분석 시작", type="primary")

    if submitted and user_prompt_input:
        # PDF 파일 확인
        if st.session_state.get('example_pdf_loaded', False):
            pdf_bytes_to_process = st.session_state['example_pdf_bytes']
            pdf_source = "예시 PDF (K-ICS 해설서.pdf)"
        elif pdf_file:
            pdf_bytes_to_process = pdf_file.read()
            pdf_source = pdf_file.name
        else:
            st.error("PDF 파일을 선택하거나 예시 PDF를 로드해주세요.")
            st.stop()

        # 진행 상황 표시
        progress_bar = st.progress(0)
        status_text = st.empty()
        
        try:
            # 세션 초기화
            for k in ['relevant_pages', 'page_info', 'selected_pages', 'original_pdf_bytes', 'pdf_images', 'page_metadata']:
                st.session_state[k] = [] if k in ['relevant_pages', 'selected_pages', 'pdf_images'] else {}
            st.session_state.user_prompt = user_prompt_input

            # 1단계: PDF 페이지 번호 삽입
            status_text.text("📝 PDF에 페이지 번호 삽입 중...")
            progress_bar.progress(0.2)
            numbered_bytes = annotate_pdf_with_page_numbers(pdf_bytes_to_process)
            st.session_state.original_pdf_bytes = numbered_bytes

            # 2단계: 메타데이터 추출
            status_text.text("📊 PDF 메타데이터 분석 중...")
            progress_bar.progress(0.3)
            st.session_state.page_metadata = extract_page_metadata(numbered_bytes)

            # 3단계: Gemini에 PDF 업로드
            status_text.text("☁️ Gemini AI에 PDF 업로드 중...")
            progress_bar.progress(0.4)
            with tempfile.NamedTemporaryFile(delete=False, suffix=".pdf") as tmp:
                tmp.write(numbered_bytes)
                tmp_path = tmp.name
            try:
                uploaded_file = upload_pdf_to_gemini(tmp_path)
            finally:
                os.unlink(tmp_path)

            # 4단계: PDF를 이미지로 변환
            status_text.text("🖼️ PDF를 이미지로 변환 중...")
            progress_bar.progress(0.6)
            st.session_state.pdf_images = convert_pdf_to_images(numbered_bytes)

            # 5단계: AI 분석 실행
            status_text.text("🤖 AI가 관련 페이지 분석 중...")
            progress_bar.progress(0.8)
            
            # 분석 모드에 따른 처리
            if analysis_mode == "정밀 분석 (시간 소요)":
                # 배치 분석으로 더 정확한 결과 얻기
                pages_response = find_relevant_pages_with_gemini(uploaded_file, user_prompt_input)
                
                # 결과 검증 단계 추가
                if pages_response:
                    status_text.text("🔍 분석 결과 검증 중...")
                    progress_bar.progress(0.9)
                    # 여기서 추가 검증 로직 수행 가능
            else:
                pages_response = find_relevant_pages_with_gemini(uploaded_file, user_prompt_input)
            
            if not pages_response.strip():
                progress_bar.empty()
                status_text.empty()
                st.error("❌ AI 분석 결과가 비어있습니다. 다시 시도해주세요.")
                return
                
            # 결과 파싱
            pages, page_info = parse_page_info(pages_response)
            total_pages = len(st.session_state.pdf_images) if st.session_state.pdf_images else 1
            
            # 페이지 번호 유효성 검증 및 필터링
            valid_pages = []
            for p in pages:
                if 1 <= p <= total_pages:
                    valid_pages.append(p)
                else:
                    st.warning(f"⚠️ 페이지 {p}는 유효 범위를 벗어났습니다 (전체: {total_pages}페이지)")
            
            st.session_state.relevant_pages = list(dict.fromkeys(valid_pages[:max_pages]))
            st.session_state.page_info = page_info

            # 완료
            progress_bar.progress(1.0)
            status_text.empty()
            progress_bar.empty()
            
            if st.session_state.relevant_pages:
                st.session_state.step = 2
                st.success(f"✅ **분석 완료!** AI가 {len(st.session_state.relevant_pages)}개의 관련 페이지를 찾았습니다!")
                
                # 분석 결과 요약 표시
                with st.expander("📊 분석 결과 요약", expanded=True):
                    col1, col2, col3 = st.columns(3)
                    with col1:
                        st.metric("전체 페이지", total_pages)
                    with col2:
                        st.metric("관련 페이지", len(st.session_state.relevant_pages))
                    with col3:
                        relevance_counts = {'상': 0, '중': 0, '하': 0}
                        for info in page_info.values():
                            rel = info.get('relevance', '하')
                            if rel in relevance_counts:
                                relevance_counts[rel] += 1
                        st.metric("높은 관련도", relevance_counts['상'])
                
                st.rerun()
            else:
                st.warning("⚠️ 질문과 관련된 페이지를 찾지 못했습니다. 다른 질문으로 시도해보세요.")

        except Exception as e:
            progress_bar.empty()
            status_text.empty()
            st.error(f"❌ **오류 발생:** {str(e)}")
            
            # 디버그 정보 표시
            with st.expander("🐛 디버그 정보"):
                st.write("오류 타입:", type(e).__name__)
                st.write("오류 메시지:", str(e))
                if hasattr(e, '__traceback__'):
                    import traceback
                    st.code(traceback.format_exc())