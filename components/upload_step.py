# upload_step.py - 간소화된 버전

import streamlit as st
import tempfile, os
from services.pdf_service import annotate_pdf_with_page_numbers, upload_pdf_to_gemini, convert_pdf_to_images
from services.gemini_service import find_relevant_pages_with_gemini, parse_page_info

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

        # 각 단계별 placeholder 생성
        step1_placeholder = st.empty()
        step2_placeholder = st.empty()
        step3_placeholder = st.empty()
        step4_placeholder = st.empty()
        result_placeholder = st.empty()
        
        try:
            # 세션 초기화
            st.session_state.relevant_pages = []
            st.session_state.page_info = {}
            st.session_state.selected_pages = []
            st.session_state.original_pdf_bytes = None
            st.session_state.pdf_images = []
            st.session_state.user_prompt = user_prompt_input

            # 1단계: PDF 페이지 번호 삽입
            step1_placeholder.info("📝 **1/4단계:** PDF에 페이지 번호 삽입 중...")
            numbered_bytes = annotate_pdf_with_page_numbers(pdf_bytes_to_process)
            st.session_state.original_pdf_bytes = numbered_bytes
            step1_placeholder.success("📝 **1/4단계:** PDF에 페이지 번호 삽입 완료 ✅")

            # 2단계: Gemini에 PDF 업로드
            step2_placeholder.info("☁️ **2/4단계:** Gemini AI에 PDF 업로드 중...")
            with tempfile.NamedTemporaryFile(delete=False, suffix=".pdf") as tmp:
                tmp.write(numbered_bytes)
                tmp_path = tmp.name
            try:
                uploaded_file = upload_pdf_to_gemini(tmp_path)
            finally:
                os.unlink(tmp_path)
            step2_placeholder.success("☁️ **2/4단계:** Gemini AI에 PDF 업로드 완료 ✅")

            # 3단계: PDF를 이미지로 변환
            step3_placeholder.info("🖼️ **3/4단계:** PDF를 이미지로 변환 중...")
            st.session_state.pdf_images = convert_pdf_to_images(numbered_bytes)
            
            if not st.session_state.pdf_images:
                step3_placeholder.warning("🖼️ **3/4단계:** PDF 이미지 변환 실패 ⚠️ (분석은 계속 진행)")
            else:
                step3_placeholder.success("🖼️ **3/4단계:** PDF를 이미지로 변환 완료 ✅")

            # 4단계: AI 분석 실행
            step4_placeholder.info("🤖 **4/4단계:** AI가 관련 페이지 분석 중... (시간이 다소 걸릴 수 있습니다)")
            
            # 배치 분석 방식으로 변경
            pages, page_info = find_relevant_pages_with_gemini(uploaded_file, user_prompt_input, pdf_bytes=numbered_bytes)
            
            if not pages:
                # 모든 진행 단계 블록 제거
                step1_placeholder.empty()
                step2_placeholder.empty()
                step3_placeholder.empty()
                step4_placeholder.empty()
                
                result_placeholder.error("❌ AI 분석 결과가 비어있습니다. 다시 시도해주세요.")
                return
            
            total_pages = len(st.session_state.pdf_images) if st.session_state.pdf_images else 1
            
            # 페이지 번호 유효성 확인
            valid_pages = [p for p in pages if 1 <= p <= total_pages]
            st.session_state.relevant_pages = valid_pages
            st.session_state.page_info = page_info

            step4_placeholder.success("🤖 **4/4단계:** AI 관련 페이지 분석 완료 ✅")

            # 모든 진행 단계 블록 제거
            step1_placeholder.empty()
            step2_placeholder.empty()
            step3_placeholder.empty()
            step4_placeholder.empty()
            
            if st.session_state.relevant_pages:
                st.session_state.step = 2
                result_placeholder.success(f"✅ **분석 완료!** AI가 {len(st.session_state.relevant_pages)}개의 관련 페이지를 찾았습니다!")
                st.rerun()
            else:
                result_placeholder.warning("⚠️ 질문과 관련된 페이지를 찾지 못했습니다. 다른 질문으로 시도해보세요.")

        except Exception as e:
            import traceback
            # 모든 진행 단계 블록 제거
            step1_placeholder.empty()
            step2_placeholder.empty()
            step3_placeholder.empty()
            step4_placeholder.empty()
            
            result_placeholder.error(f"❌ **오류 발생:** {str(e)}")
            
            # 디버깅을 위한 상세 오류 정보
            st.error("상세 오류 정보:")
            st.code(traceback.format_exc())
            st.error("위 오류가 지속되면 페이지를 새로고침하고 다시 시도해주세요.")