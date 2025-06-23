import streamlit as st

def render_sidebar():
    st.sidebar.title("소개")
    st.sidebar.markdown("""
본 서비스는 AI를 활용하여 다양한 종류의 PDF를 세부분석 할 수 있게 도와주는 AI 도구 입니다.
* 무료 Gemini model (Gemini 2.0 flash) 을 사용하고 있어 답변 생성 속도가 느릴 수 있습니다.
""")
    st.sidebar.markdown('<p style="color: red; font-size: 0.8em;">(주의)본 AI가 제공하는 답변은 참고용이며 ...</p>', unsafe_allow_html=True)
    st.sidebar.markdown("### 타 Link")
    st.sidebar.markdown("[개발자 링크드인](https://www.linkedin.com/in/chrislee9407/)")
    st.sidebar.markdown("[K-계리 AI 플랫폼](https://chrischangminlee.github.io/K_Actuary_AI_Agent_Platform/)")
    st.sidebar.markdown("[K-Actuary AI Doc Analyzer (Old Ver.)](https://kactuarypdf.streamlit.app/)")
    # 임시 디버그 툴도 그대로
    st.sidebar.markdown("---")
    st.sidebar.markdown("### 🔧 PDF 텍스트 분석 도구")
    st.sidebar.markdown("<small>페이지별 텍스트 추출 상태 확인용 (임시)</small>", unsafe_allow_html=True)
