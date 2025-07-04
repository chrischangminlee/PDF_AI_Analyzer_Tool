# PDF AI 분석 도구

Google Gemini AI를 활용한 PDF 문서 분석 웹 애플리케이션입니다.

## 주요 기능

- **PDF 업로드 및 분석**: PDF 파일을 업로드하고 질문을 입력하면 AI가 관련 페이지를 찾아 분석
- **배치 처리**: 10페이지씩 나누어 효율적으로 분석
- **테이블 형태 결과**: 페이지번호, 답변, 관련도를 표로 제공
- **페이지별 보기**: 각 페이지를 새 탭에서 확인 가능
- **엑셀 복사 기능**: 분석 결과를 엑셀로 쉽게 복사

## 설치 및 실행

### 1. 필수 요구사항

- Python 3.8 이상
- Google Gemini API 키

### 2. 의존성 설치

```bash
pip install -r requirements.txt
```

### 3. 환경 설정

프로젝트 루트 디렉토리에 `.env` 파일을 생성하고 다음 내용을 추가:

```
GEMINI_API_KEY=your-gemini-api-key-here
```

Google Gemini API 키는 [Google AI Studio](https://makersuite.google.com/app/apikey)에서 발급받을 수 있습니다.

### 4. 애플리케이션 실행

```bash
streamlit run app.py
```

브라우저에서 http://localhost:8501 으로 접속하여 사용할 수 있습니다.

## 사용법

1. **PDF 업로드**: PDF 파일을 선택하거나 예시 PDF 사용
2. **질문 입력**: 찾고자 하는 정보를 구체적으로 입력
   - 예: "요구자본의 정의 알려줘"
   - 예: "제품 사양서에서 기술적 요구사항을 찾아줘"
3. **분석 시작**: "PDF 분석 시작" 버튼 클릭
4. **결과 확인**: 테이블 형태로 관련 페이지와 답변 확인
5. **페이지 보기**: 각 페이지의 "보기" 버튼으로 상세 내용 확인
6. **엑셀 복사**: 제공된 방법으로 결과를 엑셀에 복사

## 기술 스택

- **Frontend**: Streamlit
- **AI Model**: Google Gemini 2.0 Flash Latest
- **PDF Processing**: PyPDF2, pdf2image
- **Data Processing**: Pandas
- **Environment Management**: python-dotenv

## 프로젝트 구조

```
pdf-analyzer/
├── app.py                    # 메인 애플리케이션
├── config.py                 # 환경 설정
├── requirements.txt          # 의존성
├── packages.txt             # 시스템 패키지
├── components/              # UI 컴포넌트
│   ├── sidebar.py          # 사이드바
│   └── upload_step.py      # PDF 업로드 및 분석
├── services/               # 서비스 레이어
│   ├── pdf_service.py      # PDF 처리
│   └── gemini_service.py   # Gemini API
└── utils/                  # 유틸리티
    └── session_state.py    # 세션 상태 관리
```

## 주의사항

- 본 AI가 제공하는 답변은 참고용이며, 정확성을 보장할 수 없습니다
- 보안을 위해 회사 기밀이나 개인정보는 업로드하지 않기를 권장합니다
- 실제 업무에 적용하기 전에 반드시 검토하시기 바랍니다

## 배포

### Streamlit Community Cloud

1. GitHub에 코드를 푸시
2. [Streamlit Community Cloud](https://share.streamlit.io)에서 앱 배포
3. Secrets 설정에서 `gemini_api_key` 추가

## 개발자 정보

- **개발자**: 이창민
- **LinkedIn**: [chrislee9407](https://www.linkedin.com/in/chrislee9407/)

## 라이선스

이 프로젝트는 개인 프로젝트입니다.