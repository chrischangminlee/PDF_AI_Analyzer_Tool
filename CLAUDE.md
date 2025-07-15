# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

This is a PDF AI Analysis Tool that minimizes hallucination effects through a multi-step approach to document analysis. The application uses Google Gemini API to intelligently search through PDF documents and provide accurate, relevant answers to user queries.

## Environment Setup

### Required Environment Variables
- `GEMINI_API_KEY`: Google Gemini API key (get from Google AI Studio)
- Can be set in `.env` file or Streamlit secrets

### Installation & Running
```bash
# Install dependencies
pip install -r requirements.txt

# Run the application
streamlit run app.py

# Access at http://localhost:8501
```

## Architecture Overview

### 4-Step Analysis Process

1. **Question Refinement** 📝
   - AI enhances user's input question to be more specific and search-friendly
   - Helps find more accurate results by clarifying ambiguous queries

2. **Batch Processing** 📚
   - Splits large PDFs into 10-page batches
   - Prevents information loss due to AI hallucination
   - Enables efficient processing of large documents

3. **Answer Validation** ✅
   - Verifies each found answer actually addresses the refined question
   - Filters out false positives and irrelevant information
   - Ensures high-quality, relevant results

4. **Summary Generation** 📋
   - Combines validated answers into coherent final response
   - Provides comprehensive answer based on all relevant pages
   - Maintains consistency across multiple page references

### Key Components

**Main Application**
- `app.py`: Entry point, initializes UI and coordinates components
- `config.py`: Manages API keys and environment configuration

**Services Layer**
- `services/gemini_service.py`: Core AI logic
  - `enhance_user_prompt()`: Improves user queries
  - `analyze_pdf_batch()`: Processes 10-page batches
  - `validate_answers_with_prompt()`: Verifies answer relevance
  - `generate_final_summary()`: Creates comprehensive summary
- `services/pdf_service.py`: PDF manipulation
  - `annotate_pdf_with_page_numbers()`: Adds page numbers overlay
  - `convert_pdf_to_images()`: Creates page previews
  - `extract_single_page_pdf()`: Extracts individual pages

**UI Components**
- `components/upload_step.py`: Main UI workflow
  - PDF upload interface
  - 3-step processing visualization
  - Results table with preview functionality
  - CSV export with Korean support (UTF-8 BOM)
- `components/sidebar.py`: App information and warnings

**State Management**
- `utils/session_state.py`: Streamlit session state initialization
- Key states: `relevant_pages`, `page_info`, `refined_prompt`, `final_summary`

### Technical Details

**PDF Processing Pipeline**:
1. Add page numbers to PDF (top-left corner)
2. Convert pages to images (100 DPI JPEG)
3. Split into 10-page batches
4. Process each batch through Gemini API
5. Parse and validate responses
6. Display results in sortable table

**Gemini Integration**:
- Model: `gemini-2.0-flash-latest`
- Batch size: 10 pages per API call
- Response format: JSON for reliable parsing
- Retry logic: Exponential backoff for rate limits
- Relevance levels:
  - 상 (High): Direct answers to the question
  - 중 (Medium): Related but indirect information
  - 하 (Low): Not relevant (excluded from results)

**Results Display**:
- Excel-style table with 3 columns: Page, Answer, Preview
- Page preview: Click button to view page image below table
- CSV export: UTF-8 BOM encoding for Korean text support
- Final summary: Comprehensive answer combining all validated results

## Important Coding Guidelines

1. **Error Handling**: Always include try-catch blocks for API calls and file operations
2. **Status Updates**: Use `status_placeholder` for real-time progress updates
3. **Korean Support**: Ensure all text operations support Korean (UTF-8)
4. **Session State**: Use centralized initialization in `utils/session_state.py`
5. **API Rate Limiting**: Implement retry logic with exponential backoff
6. **Memory Management**: Clear temporary files after batch processing

## Common Tasks

### Adding New Features
1. Update relevant service in `services/`
2. Modify UI in `components/upload_step.py`
3. Update `Project_Context.txt` with changes
4. Test with both example PDF and custom uploads

### Debugging API Issues
- Check API key in environment/secrets
- Monitor rate limit errors in console
- Use `status_placeholder` for detailed progress tracking
- Review JSON parsing in `parse_page_info()`

### Modifying Analysis Logic
- Main analysis: `services/gemini_service.py:analyze_pdf_batch()`
- Validation: `services/gemini_service.py:validate_answers_with_prompt()`
- Summary: `services/gemini_service.py:generate_final_summary()`

## Example PDF
- Location: `Filereference/changminlee_intro.pdf`
- Purpose: Demonstration of analysis capabilities
- Content: Developer's introduction/resume

## Deployment Notes
- Platform: Streamlit Community Cloud
- Secrets: Add `GEMINI_API_KEY` in Streamlit secrets
- System dependency: `poppler-utils` (in `packages.txt`)

## Security Warnings
- Never commit API keys to repository
- Warn users about uploading sensitive documents
- All analysis results are for reference only
- Implement proper input validation for file uploads