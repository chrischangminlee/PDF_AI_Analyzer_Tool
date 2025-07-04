import streamlit as st
import pandas as pd
import base64
from services.pdf_service import annotate_pdf_with_page_numbers, convert_pdf_to_images, extract_single_page_pdf
from services.gemini_service import find_relevant_pages_with_gemini

def run_upload_step():
    st.header("PDF 업로드 및 질문 입력")

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
        
        try:
            # 세션 초기화
            st.session_state.analysis_results = []
            st.session_state.user_prompt = user_prompt_input

            # 1단계: PDF 페이지 번호 삽입
            step1_placeholder.info("📝 **1/3단계:** PDF에 페이지 번호 삽입 중...")
            numbered_bytes = annotate_pdf_with_page_numbers(pdf_bytes_to_process)
            st.session_state.original_pdf_bytes = numbered_bytes
            step1_placeholder.success("📝 **1/3단계:** PDF에 페이지 번호 삽입 완료 ✅")

            # 2단계: PDF를 이미지로 변환
            step2_placeholder.info("🖼️ **2/3단계:** PDF를 이미지로 변환 중...")
            st.session_state.pdf_images = convert_pdf_to_images(numbered_bytes)
            
            if not st.session_state.pdf_images:
                step2_placeholder.warning("🖼️ **2/3단계:** PDF 이미지 변환 실패 ⚠️ (분석은 계속 진행)")
            else:
                step2_placeholder.success("🖼️ **2/3단계:** PDF를 이미지로 변환 완료 ✅")

            # 3단계: AI 분석 실행
            step3_placeholder.info("🤖 **3/3단계:** AI가 관련 페이지 분석 중... (시간이 다소 걸릴 수 있습니다)")
            
            # 상태 업데이트용 placeholder 생성
            status_placeholder = st.empty()
            
            # 배치 분석 방식으로 실행
            pages, page_info = find_relevant_pages_with_gemini(
                user_prompt_input, 
                pdf_bytes=numbered_bytes, 
                status_placeholder=status_placeholder
            )
            
            # 분석 완료 후 상태 메시지 정리
            status_placeholder.empty()
            
            if not pages:
                # 모든 진행 단계 블록 제거
                step1_placeholder.empty()
                step2_placeholder.empty()
                step3_placeholder.empty()
                
                st.error("❌ AI 분석 결과가 비어있습니다. 다시 시도해주세요.")
                return
            
            # 결과를 세션에 저장
            st.session_state.relevant_pages = pages
            st.session_state.page_info = page_info
            
            step3_placeholder.success("🤖 **3/3단계:** AI 관련 페이지 분석 완료 ✅")

            # 모든 진행 단계 블록 제거
            step1_placeholder.empty()
            step2_placeholder.empty()
            step3_placeholder.empty()
            
            # 분석 완료 표시
            st.success(f"✅ **분석 완료!** AI가 {len(pages)}개의 관련 페이지를 찾았습니다!")
            
            # 결과 표시
            display_analysis_results()

        except Exception as e:
            import traceback
            # 모든 진행 단계 블록 제거
            step1_placeholder.empty()
            step2_placeholder.empty()
            step3_placeholder.empty()
            
            st.error(f"❌ **오류 발생:** {str(e)}")
            
            # 디버깅을 위한 상세 오류 정보
            st.error("상세 오류 정보:")
            st.code(traceback.format_exc())
            st.error("위 오류가 지속되면 페이지를 새로고침하고 다시 시도해주세요.")
    
    # 이전 분석 결과가 있으면 표시
    elif hasattr(st.session_state, 'relevant_pages') and st.session_state.relevant_pages:
        display_analysis_results()


def display_analysis_results():
    """분석 결과를 테이블 형태로 표시"""
    st.header("📊 분석 결과")
    st.write(f"**질문:** {st.session_state.user_prompt}")
    
    # 결과 데이터 준비
    table_data = []
    for page_num in st.session_state.relevant_pages:
        if page_num in st.session_state.page_info:
            info = st.session_state.page_info[page_num]
            if info['relevance'] in ['상', '중']:  # 관련도 중~상만 표시
                table_data.append({
                    '페이지': page_num,
                    '답변': info['page_response'],
                    '관련도': info['relevance'],
                    '상세보기': "📄 보기"
                })
    
    if table_data:
        # DataFrame 생성
        df = pd.DataFrame(table_data)
        
        # 테이블 표시 (인덱스 숨김)        
        st.dataframe(
            df,
            use_container_width=True,
            hide_index=True,
            column_config={
                "페이지": st.column_config.NumberColumn(
                    "페이지",
                    help="PDF 페이지 번호",
                    format="%d",
                    width="small"
                ),
                "답변": st.column_config.TextColumn(
                    "답변",
                    help="사용자 질문에 대한 답변",
                    width="large"
                ),
                "관련도": st.column_config.TextColumn(
                    "관련도",
                    help="질문과의 관련성",
                    width="small"
                ),
                "상세보기": st.column_config.TextColumn(
                    "상세보기",
                    help="페이지 상세 내용 보기",
                    width="small"
                )
            }
        )
        
        # 페이지별 상세보기 버튼
        st.markdown("---")
        st.subheader("📄 페이지 상세보기")
        
        cols = st.columns(min(4, len(table_data)))
        for idx, row in enumerate(table_data):
            page_num = row['페이지']
            with cols[idx % 4]:
                if st.button(f"페이지 {page_num} 보기", key=f"view_page_{page_num}"):
                    single_page_pdf = extract_single_page_pdf(
                        st.session_state.original_pdf_bytes, 
                        page_num
                    )
                    if single_page_pdf:
                        # Base64 인코딩
                        b64 = base64.b64encode(single_page_pdf).decode()
                        # JavaScript로 새 탭 열기
                        href = f'<a href="data:application/pdf;base64,{b64}" target="_blank">페이지 {page_num} 새 탭에서 열기</a>'
                        st.markdown(href, unsafe_allow_html=True)
    
    else:
        st.warning("⚠️ 관련도가 '중' 이상인 페이지가 없습니다.")
    
    # 새로운 분석 시작 버튼
    if st.button("🔄 새로운 분석 시작", type="primary"):
        # 세션 상태 초기화
        for key in ['relevant_pages', 'page_info', 'user_prompt', 'original_pdf_bytes', 
                    'pdf_images', 'example_pdf_loaded', 'example_pdf_bytes']:
            if key in st.session_state:
                del st.session_state[key]
        st.rerun()