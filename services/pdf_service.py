import io, tempfile, os
import streamlit as st
from PyPDF2 import PdfReader, PdfWriter
from pdf2image import convert_from_bytes
from reportlab.pdfgen import canvas
from reportlab.lib.units import mm
from google.generativeai import GenerativeModel
import google.generativeai as genai  # 필요 시

# PDF → 이미지
def convert_pdf_to_images(pdf_bytes):
    try:
        return convert_from_bytes(pdf_bytes, dpi=100, fmt='jpeg')
    except Exception as e:
        st.warning(f"이미지 변환 오류: {e}")
        return []

# 페이지 번호 오버레이
def annotate_pdf_with_page_numbers(pdf_bytes):
    reader = PdfReader(io.BytesIO(pdf_bytes))
    writer = PdfWriter()

    for idx, page in enumerate(reader.pages):
        width = float(page.mediabox.width)
        height = float(page.mediabox.height)

        packet = io.BytesIO()
        c = canvas.Canvas(packet, pagesize=(width, height))
        c.setFont("Helvetica", 9)
        c.drawString(10 * mm, height - 15 * mm, str(idx + 1))
        c.save()

        packet.seek(0)
        overlay_pdf = PdfReader(packet)
        page.merge_page(overlay_pdf.pages[0])
        writer.add_page(page)

    output_stream = io.BytesIO()
    writer.write(output_stream)
    return output_stream.getvalue()

# Gemini 파일 업로드
def upload_pdf_to_gemini(pdf_path):
    return genai.upload_file(pdf_path, mime_type="application/pdf")
