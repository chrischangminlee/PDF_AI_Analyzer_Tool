import streamlit as st
import google.generativeai as genai
from dotenv import load_dotenv
import os
import io
from pdf2image import convert_from_bytes
from PIL import Image
import base64
import time
import tempfile

# 환경변수 로드
load_dotenv()

# 페이지 설정
st.set_page_config(page_title="이창민의 PDF AI 세부 분석 Tool", layout="wide")

def get_api_key():
    """Get API key from environment variable or Streamlit secrets"""
    # Try to get from Streamlit secrets first (for production)
    if 'gemini_api_key' in st.secrets:
        return st.secrets['gemini_api_key']
    # Fallback to environment variable (for local development)
    return os.getenv('GEMINI_API_KEY')

# API 키 설정
api_key = get_api_key()
if not api_key:
    st.error('Gemini API 키가 설정되지 않았습니다. .env 파일이나 Streamlit secrets에 API 키를 설정해주세요.')
    st.stop()

genai.configure(api_key=api_key)

# 왼쪽 사이드바 내용
st.sidebar.title("소개")
st.sidebar.markdown("""
본 서비스는 AI를 활용하여 다양한 종류의 PDF를 세부분석 할 수 있게 도와주는 AI 도구 입니다.
유용한 기능들이 지속적으로 개발 중이며, 보다 향상된 서비스를 제공하기 위해 개선을 이어가고 있습니다.
* Gemini 1.5 flash model을 사용하여 PDF를 분석하고 있어 답변 생성 속도가 느립니다.
""")
st.sidebar.markdown('<p style="color: red; font-size: 0.8em;">(주의) 본 AI가 제공하는 답변은 참고용이며, 정확성을 보장할 수 없습니다. 보안을 위해 회사 기밀, 개인정보등은 제공하지 않기를 권장드리며, 반드시 실제 업무에 적용하기 전에 검토하시길 바랍니다.</p>', unsafe_allow_html=True)

st.sidebar.markdown("### 타 Link")
st.sidebar.markdown("[개발자 링크드인](https://www.linkedin.com/in/chrislee9407/)")
st.sidebar.markdown("[K-계리 AI 플랫폼](https://chrischangminlee.github.io/K_Actuary_AI_Agent_Platform/)")
st.sidebar.markdown("[K-Actuary AI Doc Analyzer (Old Ver.)](https://kactuarypdf.streamlit.app/)")

# 메인 제목
st.title("이창민의 PDF AI 세부 분석 Tool")
st.write(
    "안녕하세요, 본 서비스는 AI 를 통한 PDF 세부분석 Tool 입니다. PDF 분석 Process는 다음과 같습니다.\n"
    "- PDF 업로드와 함께 희망 분석 내용 프롬프트 전달\n"
    "- PDF AI 분석을 통해 관련성 높은 문서 페이지 도출 \n"
    "- 도출된 페이지 확인 후 최종 분석 희망하는 페이지들 선택 \n"
    "- 확인\n"
)

# 세션 상태 초기화
if 'pdf_pages' not in st.session_state:
    st.session_state.pdf_pages = []
if 'relevant_pages' not in st.session_state:
    st.session_state.relevant_pages = []
if 'selected_pages' not in st.session_state:
    st.session_state.selected_pages = []
if 'uploaded_file' not in st.session_state:
    st.session_state.uploaded_file = None
if 'step' not in st.session_state:
    st.session_state.step = 1

def upload_pdf_to_gemini(pdf_file):
    """PDF 파일을 Gemini에 업로드"""
    try:
        # 임시 파일로 저장
        with tempfile.NamedTemporaryFile(delete=False, suffix='.pdf') as tmp_file:
            tmp_file.write(pdf_file.getvalue())
            tmp_file_path = tmp_file.name
        
        # Gemini API를 사용하여 파일 업로드
        uploaded_file = genai.upload_file(tmp_file_path, mime_type='application/pdf')
        
        # 임시 파일 삭제
        os.unlink(tmp_file_path)
        
        return uploaded_file
        
    except Exception as e:
        st.error(f"PDF 파일을 Gemini에 업로드하는 중 오류가 발생했습니다: {str(e)}")
        return None

def convert_pdf_to_images(pdf_file):
    """PDF를 이미지로 변환"""
    try:
        # PDF 파일을 바이트로 읽기
        pdf_bytes = pdf_file.read()
        # 이미지로 변환 (DPI를 낮춰서 처리 속도 향상)
        images = convert_from_bytes(pdf_bytes, dpi=100, fmt='jpeg')
        return images
    except Exception as e:
        st.warning(f"PDF를 이미지로 변환하는 중 오류가 발생했습니다: {str(e)}")
        st.info("페이지 미리보기를 건너뛰고 분석을 계속합니다. AI가 PDF를 직접 분석하므로 기능에는 문제가 없습니다.")
        # 빈 리스트를 반환하여 프로세스가 계속 진행되도록 함
        return []

def find_relevant_pages_with_gemini(uploaded_file, user_prompt):
    """Gemini API를 사용하여 PDF에서 관련 페이지 찾기"""
    try:
        model = genai.GenerativeModel('gemini-1.5-flash')
        
        prompt = f"""
        업로드된 PDF 문서를 분석하여 다음 질문과 관련이 있을 수 있는 페이지 번호들을 찾아주세요.
        
        사용자의 질문: {user_prompt}
        
        지시사항:
        1. PDF 문서 전체를 꼼꼼히 분석해주세요
        2. 질문과 직접적으로 관련된 페이지뿐만 아니라 간접적으로 관련될 수 있는 페이지도 포함해주세요
        3. 답변은 페이지 번호만 쉼표로 구분하여 제공하고, 다른 설명은 하지 마세요
        4. 페이지 번호는 1부터 시작합니다
        
        예시 답변 형식: 3, 111, 253, 299
        """
        
        response = model.generate_content([uploaded_file, prompt])
        return response.text.strip()
    
    except Exception as e:
        st.error(f"Gemini API 호출 중 오류가 발생했습니다: {str(e)}")
        return ""

def generate_final_answer(uploaded_file, selected_pages, user_prompt):
    """선택된 페이지들을 기반으로 최종 답변 생성"""
    try:
        model = genai.GenerativeModel('gemini-1.5-flash')
        
        pages_text = ", ".join(map(str, selected_pages))
        
        prompt = f"""
        업로드된 PDF 문서에서 특정 페이지들({pages_text})을 중심으로 사용자의 질문에 답변해주세요.
        
        사용자의 질문: {user_prompt}
        
        분석 대상 페이지: {pages_text}
        
        지시사항:
        1. 지정된 페이지들을 중심으로 분석하되, 필요하다면 다른 페이지의 관련 정보도 참조하세요
        2. 상세하고 정확한 답변을 제공해주세요
        3. 가능한 한 구체적인 정보와 페이지 참조를 포함하여 답변해주세요
        4. 답변 구조를 명확하게 정리해주세요
        """
        
        response = model.generate_content([uploaded_file, prompt])
        return response.text
    
    except Exception as e:
        st.error(f"최종 답변 생성 중 오류가 발생했습니다: {str(e)}")
        return ""

# 1단계: PDF 파일 업로드 및 프롬프트 입력
st.header("1단계: PDF 업로드 및 분석 요청")

with st.form("pdf_analysis_form"):
    col1, col2 = st.columns(2)
    
    with col1:
        pdf_file = st.file_uploader("분석 희망하는 PDF 파일을 업로드하세요", type=["pdf"])
    
    with col2:
        user_prompt = st.text_input("PDF에서 분석하고자하는 내용을 포함한 프롬프트를 입력하세요 (입력 후 엔터 또는 분석 버튼 클릭)", 
                                  placeholder="예: 요구자본의 정의를 알려줘")
    
    # 폼 제출 버튼 (엔터키로도 작동)
    submitted = st.form_submit_button("🚀 PDF 분석 시작", type="primary", use_container_width=True)

if submitted and pdf_file and user_prompt:
    with st.spinner("PDF를 분석하고 관련 페이지를 찾는 중..."):
        # 진행률 표시
        progress_bar = st.progress(0)
        status_text = st.empty()
        
        # PDF를 Gemini에 업로드
        status_text.text("PDF를 Gemini AI에 업로드하는 중...")
        progress_bar.progress(25)
        uploaded_file = upload_pdf_to_gemini(pdf_file)
        if not uploaded_file:
            st.error("PDF 업로드에 실패했습니다. 다시 시도해주세요.")
            progress_bar.empty()
            status_text.empty()
            st.stop()
        
        st.session_state.uploaded_file = uploaded_file
        
        # PDF 이미지 변환 (미리보기용)
        status_text.text("PDF 미리보기를 위해 이미지로 변환하는 중...")
        progress_bar.progress(50)
        pdf_file.seek(0)  # 파일 포인터 리셋
        pdf_images = convert_pdf_to_images(pdf_file)
        st.session_state.pdf_images = pdf_images
        
        # Gemini AI가 직접 PDF를 분석하여 관련 페이지 찾기
        status_text.text("Gemini AI가 PDF를 분석하여 관련 페이지를 찾는 중...")
        progress_bar.progress(75)
        relevant_pages_text = find_relevant_pages_with_gemini(uploaded_file, user_prompt)
        
        # 페이지 번호 파싱
        try:
            page_numbers = [int(p.strip()) for p in relevant_pages_text.split(',') if p.strip().isdigit()]
            # 유효한 페이지 번호만 필터링 (1-based index)
            valid_pages = [p for p in page_numbers if 1 <= p <= len(pdf_images)]
            st.session_state.relevant_pages = valid_pages
        except:
            st.session_state.relevant_pages = []
        
        progress_bar.progress(100)
        status_text.text("분석 완료!")
        st.session_state.step = 2
        time.sleep(1)
        progress_bar.empty()
        status_text.empty()

# 2단계: 관련 페이지 표시 및 선택
if st.session_state.step >= 2 and st.session_state.relevant_pages:
    st.header("2단계: AI가 찾은 관련 페이지들")
    st.write(f"**AI가 찾은 관련 페이지:** {', '.join(map(str, st.session_state.relevant_pages))}")
    st.write("아래에서 실제로 분석에 사용할 페이지들을 선택해주세요:")
    
    # 페이지 선택 체크박스
    selected_pages = []
    
    # PDF 이미지가 있는지 확인
    if hasattr(st.session_state, 'pdf_images') and st.session_state.pdf_images:
        # 관련 페이지들을 3열로 표시 (이미지와 함께)
        cols = st.columns(3)
        
        for i, page_num in enumerate(st.session_state.relevant_pages):
            col_idx = i % 3
            with cols[col_idx]:
                # 페이지 컨테이너 박스
                with st.container():
                    # 하나의 통합된 박스 시작
                    st.markdown("""
                    <div style="border: 2px solid #e0e0e0; border-radius: 10px; padding: 15px; margin: 10px 0; background-color: #fafafa;">
                    """, unsafe_allow_html=True)
                    
                    # 상단 행: 체크박스(좌측)와 페이지 번호(우측)
                    header_col1, header_col2 = st.columns([1, 4])
                    with header_col1:
                        is_selected = st.checkbox("", key=f"page_{page_num}", label_visibility="collapsed")
                        if is_selected:
                            selected_pages.append(page_num)
                    with header_col2:
                        st.markdown(f"**📄 페이지 {page_num}**")
                    
                    # 페이지 이미지 표시
                    if page_num - 1 < len(st.session_state.pdf_images):
                        st.image(st.session_state.pdf_images[page_num - 1], 
                                use_column_width=True)
                    else:
                        st.info("이미지를 불러올 수 없습니다")
                    
                    # 박스 종료
                    st.markdown("</div>", unsafe_allow_html=True)
    else:
        # 이미지 변환이 실패한 경우 텍스트로만 페이지 선택 제공
        st.info("📄 페이지 미리보기는 사용할 수 없지만, AI가 PDF를 직접 분석했으므로 정상적으로 분석할 수 있습니다.")
        
        cols = st.columns(4)
        for i, page_num in enumerate(st.session_state.relevant_pages):
            col_idx = i % 4
            with cols[col_idx]:
                # 텍스트 기반 페이지 선택 박스
                with st.container():
                    # 통합된 박스 시작
                    st.markdown("""
                    <div style="border: 2px solid #e0e0e0; border-radius: 10px; padding: 15px; margin: 10px 0; background-color: #fafafa; text-align: center;">
                    """, unsafe_allow_html=True)
                    
                    # 체크박스(좌측)와 페이지 번호(우측)
                    checkbox_col, text_col = st.columns([1, 3])
                    with checkbox_col:
                        is_selected = st.checkbox("", key=f"page_{page_num}", label_visibility="collapsed")
                        if is_selected:
                            selected_pages.append(page_num)
                    with text_col:
                        st.markdown(f"**📄 페이지 {page_num}**")
                    
                    # 박스 종료
                    st.markdown("</div>", unsafe_allow_html=True)
    
    # 선택된 페이지들 저장
    st.session_state.selected_pages = selected_pages
    
    if selected_pages:
        st.success(f"선택된 페이지: {', '.join(map(str, selected_pages))}")
        
        if st.button("선택된 페이지로 최종 분석 실행", type="primary"):
            st.session_state.step = 3

# 3단계: 최종 답변 생성
if st.session_state.step >= 3 and st.session_state.selected_pages:
    st.header("3단계: 최종 분석 결과")
    
    with st.spinner("Gemini AI가 선택된 페이지들을 분석하여 답변을 생성하는 중..."):
        # Gemini AI가 선택된 페이지들을 직접 분석하여 최종 답변 생성
        final_answer = generate_final_answer(st.session_state.uploaded_file, st.session_state.selected_pages, user_prompt)
    
    if final_answer:
        st.subheader("📋 분석 결과")
        st.write(f"**질문:** {user_prompt}")
        st.write(f"**분석된 페이지:** {', '.join(map(str, st.session_state.selected_pages))}")
        st.write("**답변:**")
        st.write(final_answer)
        
        # 다시 분석하기 버튼
        if st.button("새로운 분석 시작"):
            # 세션 상태 초기화
            for key in ['pdf_pages', 'relevant_pages', 'selected_pages', 'uploaded_file', 'step', 'pdf_images']:
                if key in st.session_state:
                    del st.session_state[key]
            st.rerun()

# 하단 정보
st.markdown("---")
st.markdown("💡 **사용 팁:** 더 정확한 분석을 위해 구체적이고 명확한 질문을 작성해주세요.")
st.markdown("🔄 **업데이트:** 지속적으로 기능을 개선하고 있습니다.") 