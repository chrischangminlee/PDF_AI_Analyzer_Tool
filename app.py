import streamlit as st
import config                    # 환경 설정 (page_config, genai 설정)
from utils.session_state import init_session_state
from components.sidebar import render_sidebar
from components.upload_step import run_upload_step
from components.page_selection_step import run_page_selection_step
from components.final_analysis_step import run_final_analysis_step

# 세션 초기화
init_session_state()

# 사이드바
render_sidebar()

# 메인 타이틀
st.title("이창민의 PDF AI 세부 분석 Tool")
st.write("""
PDF분석, 시간이 오래걸리더라도 퀄리티있는 답변을 추출하고자 만들어 보았습니다.
         
본 PDF AI 세부 분석 Tool은 단계적 AI활용과 Human Input을 통해 AI 환각효과를 최소화 하고자 합니다.

현재 무료버전을 사용하고 있어 일일 API 사용량이 제한되어 당일 사용이 불가능할 수도 있습니다.
**PDF 분석 기간이 몇분 소요되니, 참고바랍니다.**
- **1단계 (AI분석):** PDF 업로드 + 분석 요청사항 입력
- **2단계 (Human Input):** 관련 페이지 AI 추천 & 페이지 별 답변 참고하여 최종분석 대상 페이지 직접 선택
- **3단계 (AI최종분석):** 선택된 페이지들 종합하여 최종 분석
""")

# 단계별 실행
run_upload_step()
run_page_selection_step()
run_final_analysis_step()
