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
PDF 분석 시 발생하는 환각(할루시네이션) 효과를 최소화 하기위해 PDF 문서를 단계적 접근으로 분석합니다.  

**단계적 접근:**  
1️⃣ **질문 명확화**: Input 질문을 AI가 구체적이고 정확한 질문으로 개선  
2️⃣ **배치 분할 분석**: 대용량 PDF를 10페이지씩 나누어 페이지별 답변 보유여부를 분석하여 환각으로 인한 정보 누락 방지  
3️⃣ **페이지별 검증**: 각 페이지에서 찾은 답변이 실제로 질문에 답하는지 개별적으로 검증하여 잘못된 정보 제거  
4️⃣ **답변 종합**: 검증된 페이지별 답변들을 통합하여 완전하고 일관성 있는 최종 답변 생성  

페이지별 분석 결과는 테이블 형태로 제공되며, 엑셀로 복사할 수 있습니다.
""")

# PDF 업로드 및 분석 실행
run_upload_step()
