import streamlit as st
import config
from utils.session_state import init_session_state
from components.sidebar import render_sidebar
from components.upload_step import run_upload_step

# 세션 초기화
init_session_state()

# 사이드바
render_sidebar()

# 메인 타이틀
st.title("PDF AI 분석 도구")
st.markdown("""
PDF 문서를 업로드하고 질문을 입력하면, AI가 관련 페이지를 찾아 분석해드립니다.  
분석 결과는 테이블 형태로 제공되며, 엑셀로 복사할 수 있습니다.
""")

# PDF 업로드 및 분석 실행
run_upload_step()
