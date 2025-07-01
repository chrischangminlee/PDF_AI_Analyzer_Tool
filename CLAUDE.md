# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Environment Setup

Required environment variables:
- `GEMINI_API_KEY`: Google Gemini API key (get from Google AI Studio)
- Can be set in `.env` file or Streamlit secrets

## Common Commands

### Development
```bash
# Install dependencies
pip install -r requirements.txt

# Run the application
streamlit run app.py

# Access at http://localhost:8501
```

### Dependencies
The project uses these key packages:
- `streamlit` (1.31.0) - Web framework
- `google-generativeai` (0.7.2) - Google Gemini API
- `pdf2image` - PDF to image conversion
- `PyPDF2` - PDF manipulation
- `python-dotenv` - Environment variables

## Architecture Overview

This is a 3-step PDF analysis application that minimizes AI hallucination through human-in-the-loop design:

### Core Flow
1. **Upload Step** (`components/upload_step.py`): PDF upload + user prompt input
2. **Page Selection Step** (`components/page_selection_step.py`): AI finds relevant pages, user selects which ones to analyze
3. **Final Analysis Step** (`components/final_analysis_step.py`): AI analyzes only selected pages

### Key Components

**Main Application**
- `app.py`: Main entry point with step orchestration
- `config.py`: Environment setup and Gemini API configuration

**Services Layer**
- `services/gemini_service.py`: Gemini API interactions, prompt engineering, response parsing
- `services/pdf_service.py`: PDF processing, image conversion, page numbering overlay

**UI Components**
- `components/upload_step.py`: Handles PDF upload, example PDF loading, and initial AI analysis
- `components/page_selection_step.py`: Shows AI-found pages with previews for user selection
- `components/final_analysis_step.py`: Generates final analysis from selected pages
- `components/sidebar.py`: Application info and developer links

**State Management**
- `utils/session_state.py`: Centralized session state initialization
- Uses Streamlit session state for multi-step workflow persistence

### Technical Details

**PDF Processing Pipeline**:
1. Annotate PDF with physical page numbers (overlay in top-left)
2. Upload to Gemini API for analysis
3. Convert to images for preview display
4. Parse Gemini response for relevant pages
5. Create subset PDF from selected pages for final analysis

**Gemini Integration**:
- Uses `gemini-2.0-flash` model
- Complex prompt engineering for page-by-page analysis
- Response parsing expects format: `page_number|page_response|relevance`
- Handles both initial page finding and final analysis

**State Management Keys**:
- `relevant_pages`: List of AI-identified page numbers
- `page_info`: Dict with page responses and relevance scores  
- `selected_pages`: User-selected pages for final analysis
- `user_prompt`: User's analysis question
- `original_pdf_bytes`: Processed PDF with page numbers
- `pdf_images`: PIL images for preview display
- `step`: Current workflow step (1-3)

## Example PDF
Includes example PDF (`Filereference/K-ICS 해설서.pdf`) for demonstration purposes - Korean insurance regulation document.

## Deployment
Configured for Streamlit Community Cloud deployment with API key in secrets.