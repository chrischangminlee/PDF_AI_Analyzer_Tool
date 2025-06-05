import streamlit as st
import google.generativeai as genai
from dotenv import load_dotenv
import os
from pypdf import PdfReader
import io
from pdf2image import convert_from_bytes
from PIL import Image
import base64
import time

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
st.sidebar.markdown("[K Actuary AI PDF Analyzer](https://kactuarypdf.streamlit.app/)")

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
if 'pdf_text' not in st.session_state:
    st.session_state.pdf_text = ""
if 'step' not in st.session_state:
    st.session_state.step = 1

def extract_text_from_pdf(pdf_file):
    """PDF에서 텍스트 추출"""
    pdf_reader = PdfReader(pdf_file)
    text = ""
    page_texts = []
    
    for page_num, page in enumerate(pdf_reader.pages):
        page_text = page.extract_text()
        page_texts.append(page_text)
        text += f"[페이지 {page_num + 1}]\n{page_text}\n\n"
    
    return text, page_texts

def convert_pdf_to_images(pdf_file):
    """PDF를 이미지로 변환"""
    try:
        # PDF 파일을 바이트로 읽기
        pdf_bytes = pdf_file.read()
        # 이미지로 변환
        images = convert_from_bytes(pdf_bytes, dpi=150)
        return images
    except Exception as e:
        st.error(f"PDF를 이미지로 변환하는 중 오류가 발생했습니다: {str(e)}")
        return []

def find_relevant_pages_with_gemini(pdf_text, user_prompt):
    """Gemini API를 사용하여 관련 페이지 찾기"""
    try:
        model = genai.GenerativeModel('gemini-1.5-flash')
        
        prompt = f"""
        다음은 PDF 문서의 전체 내용입니다:
        
        {pdf_text}
        
        사용자의 질문: {user_prompt}
        
        이 질문과 관련이 있을 수 있는 페이지 번호들을 모두 찾아서 쉼표로 구분하여 나열해주세요.
        답변은 페이지 번호만 제공하고, 다른 설명은 하지 마세요.
        예시: 3, 111, 253, 299
        """
        
        response = model.generate_content(prompt)
        return response.text.strip()
    
    except Exception as e:
        st.error(f"Gemini API 호출 중 오류가 발생했습니다: {str(e)}")
        return ""

def generate_final_answer(selected_page_texts, user_prompt):
    """선택된 페이지들로 최종 답변 생성"""
    try:
        model = genai.GenerativeModel('gemini-1.5-flash')
        
        combined_text = "\n\n".join([f"[페이지 {i+1}]\n{text}" for i, text in enumerate(selected_page_texts)])
        
        prompt = f"""
        다음은 선택된 PDF 페이지들의 내용입니다:
        
        {combined_text}
        
        사용자의 질문: {user_prompt}
        
        위 내용을 바탕으로 사용자의 질문에 대해 상세하고 정확한 답변을 제공해주세요.
        가능한 한 구체적인 정보와 페이지 참조를 포함하여 답변해주세요.
        """
        
        response = model.generate_content(prompt)
        return response.text
    
    except Exception as e:
        st.error(f"최종 답변 생성 중 오류가 발생했습니다: {str(e)}")
        return ""

# 1단계: PDF 파일 업로드 및 프롬프트 입력
st.header("1단계: PDF 업로드 및 분석 요청")

col1, col2 = st.columns(2)

with col1:
    pdf_file = st.file_uploader("분석 희망하는 PDF 파일을 업로드하세요", type=["pdf"])

with col2:
    user_prompt = st.text_input("프롬프트를 입력하세요", placeholder="예: 보험약관에서 담보별 지급금액을 알려줘")

if pdf_file and user_prompt and st.button("PDF 분석 시작", type="primary"):
    with st.spinner("PDF를 분석하고 관련 페이지를 찾는 중..."):
        # 진행률 표시
        progress_bar = st.progress(0)
        status_text = st.empty()
        
        # PDF 텍스트 추출
        status_text.text("PDF에서 텍스트를 추출하는 중...")
        progress_bar.progress(25)
        pdf_text, page_texts = extract_text_from_pdf(pdf_file)
        st.session_state.pdf_text = pdf_text
        st.session_state.page_texts = page_texts
        
        # PDF 이미지 변환
        status_text.text("PDF를 이미지로 변환하는 중...")
        progress_bar.progress(50)
        pdf_file.seek(0)  # 파일 포인터 리셋
        pdf_images = convert_pdf_to_images(pdf_file)
        st.session_state.pdf_images = pdf_images
        
        # Gemini API로 관련 페이지 찾기
        status_text.text("AI가 관련 페이지를 분석하는 중...")
        progress_bar.progress(75)
        relevant_pages_text = find_relevant_pages_with_gemini(pdf_text, user_prompt)
        
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
    
    # 관련 페이지들을 3열로 표시
    cols = st.columns(3)
    
    for i, page_num in enumerate(st.session_state.relevant_pages):
        col_idx = i % 3
        with cols[col_idx]:
            # 페이지 이미지 표시 (0-based index로 변환)
            if page_num - 1 < len(st.session_state.pdf_images):
                st.image(st.session_state.pdf_images[page_num - 1], 
                        caption=f"페이지 {page_num}", 
                        use_column_width=True)
                
                # 선택 체크박스
                if st.checkbox(f"페이지 {page_num} 선택", key=f"page_{page_num}"):
                    selected_pages.append(page_num)
    
    # 선택된 페이지들 저장
    st.session_state.selected_pages = selected_pages
    
    if selected_pages:
        st.success(f"선택된 페이지: {', '.join(map(str, selected_pages))}")
        
        if st.button("선택된 페이지로 최종 분석 실행", type="primary"):
            st.session_state.step = 3

# 3단계: 최종 답변 생성
if st.session_state.step >= 3 and st.session_state.selected_pages:
    st.header("3단계: 최종 분석 결과")
    
    with st.spinner("선택된 페이지들을 분석하여 답변을 생성하는 중..."):
        # 선택된 페이지들의 텍스트 추출
        selected_page_texts = []
        for page_num in st.session_state.selected_pages:
            if page_num - 1 < len(st.session_state.page_texts):
                selected_page_texts.append(st.session_state.page_texts[page_num - 1])
        
        # 최종 답변 생성
        final_answer = generate_final_answer(selected_page_texts, user_prompt)
    
    if final_answer:
        st.subheader("📋 분석 결과")
        st.write(f"**질문:** {user_prompt}")
        st.write(f"**분석된 페이지:** {', '.join(map(str, st.session_state.selected_pages))}")
        st.write("**답변:**")
        st.write(final_answer)
        
        # 다시 분석하기 버튼
        if st.button("새로운 분석 시작"):
            # 세션 상태 초기화
            for key in ['pdf_pages', 'relevant_pages', 'selected_pages', 'pdf_text', 'step', 'pdf_images', 'page_texts']:
                if key in st.session_state:
                    del st.session_state[key]
            st.rerun()

# 하단 정보
st.markdown("---")
st.markdown("💡 **사용 팁:** 더 정확한 분석을 위해 구체적이고 명확한 질문을 작성해주세요.")
st.markdown("🔄 **업데이트:** 지속적으로 기능을 개선하고 있습니다.") 