# 이창민의 PDF AI 세부 분석 Tool

Google Gemini AI를 활용한 PDF 문서 세부 분석 웹 애플리케이션입니다.

## 주요 기능

1. **PDF 업로드**: 분석하고자 하는 PDF 파일을 업로드
2. **프롬프트 입력**: PDF에서 찾고자 하는 정보를 구체적으로 명시
3. **AI 페이지 도출**: Google Gemini API를 통해 관련성 높은 페이지들을 자동 도출
4. **페이지 미리보기**: 도출된 페이지들을 이미지로 확인
5. **페이지 선택**: 실제 분석에 사용할 페이지들을 사용자가 직접 선택
6. **최종 분석**: 선택된 페이지들만을 사용하여 정확한 답변 생성

## 설치 및 실행

### 1. 필수 요구사항

- Python 3.8 이상
- Google Gemini API 키

### 2. 의존성 설치

```bash
pip install -r requirements.txt
```

### 3. 환경 설정

프로젝트 루트 디렉토리에 `.env` 파일을 생성하고 다음 내용을 추가하세요:

```
GEMINI_API_KEY=your-gemini-api-key-here
```

Google Gemini API 키는 [Google AI Studio](https://makersuite.google.com/app/apikey)에서 발급받을 수 있습니다.

### 4. 애플리케이션 실행

```bash
streamlit run app.py
```

브라우저에서 http://localhost:8501 으로 접속하면 애플리케이션을 사용할 수 있습니다.

## 사용법

1. **PDF 업로드**: 왼쪽에서 분석하고 싶은 PDF 파일을 업로드합니다.
2. **질문 입력**: 오른쪽에서 PDF에서 찾고자 하는 정보를 구체적으로 입력합니다.
   - 예: "보험약관에서 담보별 지급금액을 알려줘"
   - 예: "제품 사양서에서 기술적 요구사항을 찾아줘"
3. **분석 시작**: "PDF 분석 시작" 버튼을 클릭합니다.
4. **페이지 확인**: AI가 찾은 관련 페이지들을 이미지로 확인합니다.
5. **페이지 선택**: 실제로 분석에 사용할 페이지들을 체크박스로 선택합니다.
6. **최종 분석**: "선택된 페이지로 최종 분석 실행" 버튼을 클릭하여 결과를 확인합니다.

## 기술 스택

- **Frontend**: Streamlit
- **AI Model**: Google Gemini 1.5 Flash
- **PDF Processing**: PyPDF2, pdf2image
- **Image Processing**: Pillow
- **Environment Management**: python-dotenv

## 주의사항

- 본 AI가 제공하는 답변은 참고용이며, 정확성을 보장할 수 없습니다.
- 보안을 위해 회사 기밀이나 개인정보는 업로드하지 않기를 권장합니다.
- 실제 업무에 적용하기 전에 반드시 검토하시기 바랍니다.

## 배포

### Streamlit Community Cloud

1. GitHub에 코드를 푸시합니다.
2. [Streamlit Community Cloud](https://share.streamlit.io)에서 앱을 배포합니다.
3. Secrets 설정에서 `gemini_api_key`를 추가합니다.

## 개발자 정보

- **개발자**: 이창민
- **LinkedIn**: [chrislee9407](https://www.linkedin.com/in/chrislee9407/)
- **관련 프로젝트**: [K-계리 AI 플랫폼](https://chrischangminlee.github.io/K_Actuary_AI_Agent_Platform/)

## 라이선스

이 프로젝트는 개인 프로젝트입니다. 