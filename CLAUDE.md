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
- `pandas` - Data manipulation for tables
- `python-dotenv` - Environment variables

## Architecture Overview

This is a simplified PDF analysis application that finds relevant pages and presents results in a table format.

### Core Flow
1. **Upload PDF**: User uploads PDF file or uses example PDF
2. **Enter Question**: User inputs their analysis query
3. **AI Analysis**: Gemini analyzes PDF in 10-page batches
4. **Table Results**: Display results as a table with page number, answer, and relevance
5. **Export to Excel**: Users can copy results to Excel

### Key Components

**Main Application**
- `app.py`: Main entry point
- `config.py`: Environment setup and Gemini API configuration

**Services Layer**
- `services/gemini_service.py`: Gemini API interactions, batch processing
- `services/pdf_service.py`: PDF processing, page extraction

**UI Components**
- `components/upload_step.py`: Handles PDF upload, analysis, and results display
- `components/sidebar.py`: Application info and instructions

**State Management**
- `utils/session_state.py`: Centralized session state initialization
- Key states: `relevant_pages`, `page_info`, `user_prompt`, `original_pdf_bytes`, `pdf_images`

### Technical Details

**PDF Processing Pipeline**:
1. Annotate PDF with page numbers (top-left overlay)
2. Convert to images for preview
3. Split into 10-page batches for analysis
4. Upload each batch to Gemini API
5. Parse responses for relevant pages (중/상 relevance only)
6. Display results in table format

**Gemini Integration**:
- Uses `gemini-2.0-flash-latest` model
- Batch processing (10 pages per API call)
- JSON response format for better parsing
- Filters only 중(medium) and 상(high) relevance pages

**Results Display**:
- Pandas DataFrame for table display
- Page-by-page view buttons (opens in new tab)
- TSV format for Excel copying
- Clear instructions for data export

## Example PDF
Includes example PDF (`Filereference/K-ICS 해설서.pdf`) for demonstration purposes.

## Deployment
Configured for Streamlit Community Cloud deployment with API key in secrets.