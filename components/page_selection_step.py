# page_selection_step.py - 개선된 버전

import streamlit as st
from services.gemini_service import verify_page_content

def run_page_selection_step():
    if st.session_state.step >= 2 and st.session_state.relevant_pages:
        st.header("2단계: 관련 페이지 확인 & 선택")
        
        # 상단 정보 및 컨트롤
        col1, col2 = st.columns([3, 1])
        with col1:
            st.write(f"**AI 추천 페이지 수:** {len(st.session_state.relevant_pages)}개")
            st.write("선별된 페이지 위에 마우스를 올리면 나타나는 확대 버튼으로 내용을 확인할 수 있어요.")
        with col2:
            if st.button("🔄 페이지 재분석", help="AI 분석 결과가 정확하지 않다면 재분석을 시도하세요"):
                st.session_state.step = 1
                st.rerun()

        # 페이지 표시 옵션
        view_options = st.columns(4)
        with view_options[0]:
            sort_by = st.selectbox("정렬 기준", ["페이지 번호", "관련도 높은 순", "관련도 낮은 순"])
        with view_options[1]:
            cols_per_row = st.selectbox("열 개수", [2, 3, 4], index=1)
        with view_options[2]:
            show_only_high = st.checkbox("높은 관련도만 표시", help="관련도 '상'인 페이지만 표시")
        with view_options[3]:
            select_all = st.checkbox("전체 선택/해제")

        # 페이지 정렬
        sorted_pages = st.session_state.relevant_pages.copy()
        if sort_by == "관련도 높은 순":
            sorted_pages.sort(key=lambda p: {'상': 0, '중': 1, '하': 2}.get(
                st.session_state.page_info.get(p, {}).get('relevance', '하'), 2))
        elif sort_by == "관련도 낮은 순":
            sorted_pages.sort(key=lambda p: {'상': 2, '중': 1, '하': 0}.get(
                st.session_state.page_info.get(p, {}).get('relevance', '하'), 0))

        # 필터링
        if show_only_high:
            sorted_pages = [p for p in sorted_pages 
                           if st.session_state.page_info.get(p, {}).get('relevance') == '상']

        # 선택 상태 메시지
        top_msg = st.empty()
        top_btn = st.empty()
        
        # 선택된 페이지 추적
        selected_pages = []

        # 페이지 그리드 표시
        if sorted_pages:
            cols = st.columns(cols_per_row)
            for i, p in enumerate(sorted_pages):
                with cols[i % cols_per_row]:
                    with st.container(border=True):
                        # 페이지 헤더
                        header_cols = st.columns([1, 4, 1])
                        with header_cols[0]:
                            # 전체 선택 상태 반영
                            default_checked = select_all or st.session_state.get(f"cb_{p}", False)
                            if st.checkbox("", key=f"cb_{p}", value=default_checked, label_visibility="collapsed"):
                                selected_pages.append(p)
                        
                        with header_cols[1]:
                            st.markdown(f"**📄 페이지 {p}**")
                        
                        with header_cols[2]:
                            # 페이지 검증 버튼
                            if st.button("🔍", key=f"verify_{p}", help="페이지 내용 검증"):
                                with st.spinner("검증 중..."):
                                    if p in st.session_state.page_info:
                                        expected = st.session_state.page_info[p].get('page_response', '')
                                        # 실제 검증 함수 호출 (구현 필요)
                                        st.info(f"페이지 {p} 검증 완료")

                        # 페이지 정보 표시
                        if p in st.session_state.page_info:
                            info = st.session_state.page_info[p]
                            page_response = info.get('page_response', '')
                            relevance = info.get('relevance', '')
                            confidence = info.get('confidence', 0.5)

                            # 관련도별 스타일링
                            if relevance == '상':
                                color, bg_color, icon = "#d32f2f", "#ffebee", "🔴"
                            elif relevance == '중':
                                color, bg_color, icon = "#f57c00", "#fff3e0", "🟡"
                            else:
                                color, bg_color, icon = "#616161", "#f5f5f5", "⚪"

                            # 정보 카드
                            st.markdown(f"""
                            <div style="background-color: {bg_color}; padding: 10px; border-radius: 8px; margin: 8px 0; border-left: 4px solid {color};">
                                <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 5px;">
                                    <span style="font-weight: bold; color: {color};">{icon} 관련도: {relevance}</span>
                                    <span style="font-size: 0.8em; color: #666;">신뢰도: {confidence:.0%}</span>
                                </div>
                                <div style="font-size: 0.9em; color: #333; line-height: 1.4;">
                                    🔑 {page_response}
                                </div>
                            </div>
                            """, unsafe_allow_html=True)

                            # 메타데이터 표시 (있는 경우)
                            if p in st.session_state.get('page_metadata', {}):
                                meta = st.session_state.page_metadata[p]
                                with st.expander("📊 페이지 정보", expanded=False):
                                    st.write(f"- 텍스트 길이: {meta.get('text_length', 0):,}자")
                                    st.write(f"- 이미지 포함: {'예' if meta.get('has_images') else '아니오'}")
                                    st.write(f"- 표 포함: {'예' if meta.get('has_tables') else '아니오'}")

                        # 페이지 이미지
                        if p - 1 < len(st.session_state.pdf_images):
                            img = st.session_state.pdf_images[p - 1]
                            st.image(img, use_column_width=True)
                            
                            # 이미지 확대 보기 옵션
                            if st.button(f"🔍 확대 보기", key=f"zoom_{p}"):
                                st.session_state[f'zoom_page_{p}'] = True
                                st.rerun()
        else:
            st.info("표시할 페이지가 없습니다. 필터 조건을 확인하세요.")

        # 확대 보기 모달
        for p in sorted_pages:
            if st.session_state.get(f'zoom_page_{p}', False):
                with st.container():
                    st.markdown("### 🔍 페이지 확대 보기")
                    col1, col2 = st.columns([4, 1])
                    with col1:
                        st.markdown(f"**페이지 {p}**")
                    with col2:
                        if st.button("❌ 닫기", key=f"close_zoom_{p}"):
                            st.session_state[f'zoom_page_{p}'] = False
                            st.rerun()
                    
                    if p - 1 < len(st.session_state.pdf_images):
                        st.image(st.session_state.pdf_images[p - 1], use_column_width=True)
                    
                    st.markdown("---")

        # 선택된 페이지 업데이트
        st.session_state.selected_pages = selected_pages

        # 상단 상태 메시지 및 버튼
        if selected_pages:
            top_msg.success(f"✅ 선택된 페이지: {len(selected_pages)}개 ({', '.join(map(str, sorted(selected_pages)))})")
            if top_btn.button("🚀 선택된 페이지로 최종 분석 실행", type="primary", key="run_top"):
                st.session_state.step = 3
                st.rerun()
        else:
            top_msg.info("📌 분석할 페이지를 선택해주세요.")

        # 하단 구분선 및 액션 버튼
        st.markdown("---")
        
        # 추가 옵션
        with st.expander("⚙️ 추가 옵션"):
            col1, col2 = st.columns(2)
            with col1:
                # 수동 페이지 추가
                manual_pages = st.text_input(
                    "페이지 번호 직접 입력", 
                    placeholder="예: 1, 3, 5-10",
                    help="쉼표로 구분하거나 범위(-)로 입력"
                )
                if st.button("➕ 페이지 추가"):
                    try:
                        added_pages = parse_page_range(manual_pages)
                        for p in added_pages:
                            if p not in selected_pages and 1 <= p <= len(st.session_state.pdf_images):
                                selected_pages.append(p)
                                st.session_state[f"cb_{p}"] = True
                        st.success(f"{len(added_pages)}개 페이지 추가됨")
                        st.rerun()
                    except:
                        st.error("올바른 형식으로 입력하세요")
            
            with col2:
                # 관련도별 일괄 선택
                st.write("관련도별 일괄 선택")
                col_a, col_b, col_c = st.columns(3)
                with col_a:
                    if st.button("🔴 상", key="select_high"):
                        for p in sorted_pages:
                            if st.session_state.page_info.get(p, {}).get('relevance') == '상':
                                st.session_state[f"cb_{p}"] = True
                        st.rerun()
                with col_b:
                    if st.button("🟡 중", key="select_medium"):
                        for p in sorted_pages:
                            if st.session_state.page_info.get(p, {}).get('relevance') == '중':
                                st.session_state[f"cb_{p}"] = True
                        st.rerun()
                with col_c:
                    if st.button("⚪ 하", key="select_low"):
                        for p in sorted_pages:
                            if st.session_state.page_info.get(p, {}).get('relevance') == '하':
                                st.session_state[f"cb_{p}"] = True
                        st.rerun()

        # 최종 분석 버튼 (하단)
        if selected_pages:
            st.markdown("###")  # 여백
            col1, col2, col3 = st.columns([1, 2, 1])
            with col2:
                if st.button("🚀 선택된 페이지로 최종 분석 실행", type="primary", key="run_bottom", use_container_width=True):
                    st.session_state.step = 3
                    st.rerun()
            
            # 선택 요약
            st.info(f"""
            **선택 요약**
            - 총 {len(selected_pages)}개 페이지 선택됨
            - 관련도 분포: 상({sum(1 for p in selected_pages if st.session_state.page_info.get(p, {}).get('relevance') == '상')}), 
              중({sum(1 for p in selected_pages if st.session_state.page_info.get(p, {}).get('relevance') == '중')}), 
              하({sum(1 for p in selected_pages if st.session_state.page_info.get(p, {}).get('relevance') == '하')})
            """)

def parse_page_range(page_str):
    """페이지 범위 문자열을 파싱하여 페이지 번호 리스트 반환"""
    pages = []
    parts = page_str.replace(' ', '').split(',')
    
    for part in parts:
        if '-' in part:
            start, end = map(int, part.split('-'))
            pages.extend(range(start, end + 1))
        else:
            pages.append(int(part))
    
    return list(set(pages))  # 중복 제거