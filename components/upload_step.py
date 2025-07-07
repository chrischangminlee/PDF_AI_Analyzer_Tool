import streamlit as st
import pandas as pd
import io
from services.pdf_service import annotate_pdf_with_page_numbers, convert_pdf_to_images
from services.gemini_service import find_relevant_pages_with_gemini, generate_final_summary, validate_answers_with_prompt

def run_upload_step():
    st.header("PDF 업로드 및 질문 입력")

    # 예시 PDF 로드 기능
    def load_example_pdf():
        """예시 PDF 파일을 로드하여 세션 상태에 저장"""
        try:
            example_pdf_path = "Filereference/changminlee_intro.pdf"
            with open(example_pdf_path, "rb") as f:
                return f.read()
        except Exception as e:
            st.error(f"예시 PDF 로드 실패: {e}")
            return None

    # 예시 PDF 불러오기 / 제거 버튼
    st.write("예시 PDF를 활용하거나, PDF를 불러오세요")

    col1, _ = st.columns(2)
    with col1:
        if st.session_state.get('example_pdf_loaded', False):
            if st.button("🗑️ 예시 PDF 제거", type="secondary"):
                st.session_state['example_pdf_loaded'] = False
                if 'example_pdf_bytes' in st.session_state:
                    del st.session_state['example_pdf_bytes']
                st.rerun()
        else:
            if st.button("📄 예시 PDF (개발자 이창민 Intro) 불러오기", type="secondary"):
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
                st.info("📄 **예시 PDF (changminlee_intro.pdf)** 가 선택되었습니다.")
                pdf_file = None
            else:
                pdf_file = st.file_uploader("PDF 파일을 선택하세요", type=['pdf'])

        with col4:
            user_prompt_input = st.text_input("분석 요청사항 입력", placeholder="예:이창민의 경력")

        submitted = st.form_submit_button("PDF 분석 시작", type="primary")

    if submitted and user_prompt_input:
        # PDF 파일 확인
        if st.session_state.get('example_pdf_loaded', False):
            pdf_bytes_to_process = st.session_state['example_pdf_bytes']
            # pdf_source = "예시 PDF (changminlee_intro.pdf)"
        elif pdf_file:
            pdf_bytes_to_process = pdf_file.read()
            # pdf_source = pdf_file.name
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
            
            # 결과를 세션에 저장
            st.session_state.relevant_pages = pages
            st.session_state.page_info = page_info
            
            step3_placeholder.success("🤖 **3/3단계:** AI 관련 페이지 분석 완료 ✅")

            # 모든 진행 단계 블록 제거
            step1_placeholder.empty()
            step2_placeholder.empty()
            step3_placeholder.empty()
            
            # 분석 완료 표시
            if not pages:
                st.error("❌ 관련 페이지를 찾을 수 없습니다. 다시 시도해주세요.")
                return
            else:
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
    st.write(f"**원본 질문:** {st.session_state.user_prompt}")
    
    # 개선된 프롬프트가 있으면 표시
    if hasattr(st.session_state, 'refined_prompt') and st.session_state.refined_prompt != st.session_state.user_prompt:
        st.write(f"**분석에 사용된 질문:** {st.session_state.refined_prompt}")
    
    # 최종 요약은 아래에서 테이블 생성 후 표시
    
    # 결과 데이터 준비 - 상과 중 모두 포함
    table_data = []
    for page_num in st.session_state.relevant_pages:
        if page_num in st.session_state.page_info:
            info = st.session_state.page_info[page_num]
            # 답변이 비어있는 경우 처리
            answer = info['page_response']
            if not answer or answer.strip() == "":
                answer = "관련 내용이 포함된 페이지"
            
            table_data.append({
                '페이지': page_num,
                '답변': answer,
                '관련도': info['relevance'],
            })
    
    if table_data:
        # 2단계: 답변 검증 (refined_prompt에 실제로 답변하는지 확인)
        if hasattr(st.session_state, 'refined_prompt'):
            validation_placeholder = st.empty()
            validated_data = validate_answers_with_prompt(
                table_data,
                st.session_state.refined_prompt,
                validation_placeholder
            )
            validation_placeholder.empty()
            
            # 검증된 데이터로 업데이트
            table_data = validated_data
        
        # 3단계: 최종 요약 생성 (검증된 답변들로만)
        if table_data and hasattr(st.session_state, 'refined_prompt'):
            summary_placeholder = st.empty()
            final_summary = generate_final_summary(
                table_data,
                st.session_state.refined_prompt,
                summary_placeholder
            )
            summary_placeholder.empty()
            st.session_state.final_summary = final_summary
            
        # 최종 요약 표시
        if hasattr(st.session_state, 'final_summary') and st.session_state.final_summary:
            st.markdown("### 📋 최종 답변")
            st.info(st.session_state.final_summary)
            st.divider()
    
    if table_data:
        # DataFrame 생성
        df = pd.DataFrame(table_data)
        
        # 테이블 표시
        st.markdown("### 📊 분석 결과 테이블")
        
        # 테이블과 버튼을 함께 표시
        col_headers = st.columns([1, 7, 2])
        with col_headers[0]:
            st.markdown("**페이지**")
        with col_headers[1]:
            st.markdown("**답변**")
        with col_headers[2]:
            st.markdown("**상세보기 (하단에 표기됩니다)**")
        
        # 구분선
        st.markdown("---")
        
        # 각 행 표시
        for _, row in df.iterrows():
            cols = st.columns([1, 7, 2])
            
            with cols[0]:
                st.write(f"{row['페이지']}")
            
            with cols[1]:
                st.write(row['답변'])
            
            with cols[2]:
                # 미리보기 버튼
                if st.button("🔍 미리보기", key=f"preview_{row['페이지']}"):
                    st.session_state.preview_page = row['페이지']
                    st.session_state.preview_data = row
        
        st.markdown("---")
        
        # CSV 다운로드 버튼 추가
        csv_buffer = io.StringIO()
        # 관련도 컬럼 제외하고 CSV 생성
        df_csv = df[['페이지', '답변']]
        df_csv.to_csv(csv_buffer, index=False, encoding='utf-8')
        csv_data = csv_buffer.getvalue().encode('utf-8-sig')
        
        st.download_button(
            label="📥 페이지 별 결과 CSV 형태로 다운받기",
            data=csv_data,
            file_name=f"분석결과_{pd.Timestamp.now().strftime('%Y%m%d_%H%M%S')}.csv",
            mime="text/csv;charset=utf-8-sig",
            type="primary"
        )

        st.markdown("---")
        
        # 미리보기 표시
        if hasattr(st.session_state, 'preview_page') and st.session_state.preview_page:
            st.markdown("---")
            
            # 미리보기 섹션
            st.markdown("### 📄 페이지 {} 미리보기".format(st.session_state.preview_page))
            
            page_num = st.session_state.preview_page
            page_data = st.session_state.preview_data
            
            # 닫기 버튼과 정보를 한 줄에 표시
            col1, col2, col3 = st.columns([4, 4, 1])
            with col1:
                st.write(f"**관련도:** {'🔴 상' if page_data['관련도'] == '상' else '🟡 중'}")
            with col2:
                st.write(f"**답변:** {page_data['답변']}")
            with col3:
                if st.button("❌ 닫기", key="close_preview"):
                    del st.session_state.preview_page
                    del st.session_state.preview_data
                    st.rerun()
            
            # 이미지 표시
            if hasattr(st.session_state, 'pdf_images') and st.session_state.pdf_images:
                page_idx = page_num - 1
                if 0 <= page_idx < len(st.session_state.pdf_images):
                    st.image(
                        st.session_state.pdf_images[page_idx], 
                        caption=f"페이지 {page_num}", 
                        use_column_width=True
                    )
            
        
        
        # 사용 팁
        st.info("💡 **팁:** '👁️ 보기' 버튼을 클릭하면 해당 페이지를 미리볼 수 있습니다.")
    
    else:
        st.warning("⚠️ 직접적인 답변이 포함된 페이지가 없습니다. (관련도 '상' 페이지가 없음)")
    
    # 새로운 분석 시작 버튼
    if st.button("🔄 새로운 분석 시작", type="primary"):
        # 세션 상태 초기화
        for key in ['relevant_pages', 'page_info', 'user_prompt', 'refined_prompt', 'final_summary',
                    'original_pdf_bytes', 'pdf_images', 'example_pdf_loaded', 'example_pdf_bytes']:
            if key in st.session_state:
                del st.session_state[key]
        st.rerun()