import streamlit as st

def render_sidebar():
    st.sidebar.title("소개")
    st.sidebar.markdown("""
본 서비스는 AI를 활용하여 PDF 문서를 분석하고 관련 페이지를 찾아주는 도구입니다.
* 현재 Gemini model (gemini 2.5 flash) 을 사용하고 있습니다.
* 10페이지씩 배치로 분석하여 효율적으로 처리합니다.
""")
    st.sidebar.markdown('<p style="color: red; font-size: 0.8em;">(주의)본 AI가 제공하는 답변은 참고용이며, 정확성을 보장할 수 없습니다. 보안을 위해 회사 기밀, 개인정보등은 제공하지 않기를 권장드리며, 반드시 실제 업무에 적용하기 전에 검토하시길 바랍니다.</p>', unsafe_allow_html=True)
    
    st.sidebar.markdown("---")
    st.sidebar.markdown("### 사용 방법")
    st.sidebar.markdown("""
    1. PDF 파일을 업로드하거나 예시 PDF를 사용
    2. 분석하고자 하는 질문 입력
    3. PDF 분석 시작 버튼 클릭
    4. 페이지별 분석 결과를 엑셀로 복사 가능
    """)
    st.sidebar.markdown('<p style="color: red; font-size: 0.8em;">(주의)본 AI가 제공하는 답변은 참고용이며, 정확성을 보장할 수 없습니다. 보안을 위해 회사 기밀, 개인정보등은 제공하지 않기를 권장드리며, 반드시 실제 업무에 적용하기 전에 검토하시길 바랍니다.</p>', unsafe_allow_html=True)
    st.sidebar.markdown("### 타 Link")
    st.sidebar.markdown("[기업 AI 인사이트 플랫폼](https://chrischangminlee.github.io/Enterprise-AI-Platform/)")
    st.sidebar.markdown("[기업 AI 연구소 유튜브](https://www.youtube.com/@EnterpriseAILab)")
    st.sidebar.markdown("[기업 AI 정보 오픈카톡방](https://open.kakao.com/o/gbr6iuGh)")
    st.sidebar.markdown("[개발자 링크드인](https://www.linkedin.com/in/chrislee9407/)")