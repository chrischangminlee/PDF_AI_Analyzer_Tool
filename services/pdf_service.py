import io
from PyPDF2 import PdfReader, PdfWriter
from pdf2image import convert_from_bytes
from reportlab.pdfgen import canvas
from reportlab.lib.units import mm
import streamlit as st

def convert_pdf_to_images(pdf_bytes):
    """PDF를 이미지로 변환"""
    try:
        return convert_from_bytes(pdf_bytes, dpi=100, fmt='jpeg')
    except Exception as e:
        st.warning(f"이미지 변환 오류: {e}")
        return []

def annotate_pdf_with_page_numbers(pdf_bytes):
    """PDF에 페이지 번호 오버레이 추가"""
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

def extract_single_page_pdf(pdf_bytes, page_num):
    """PDF에서 특정 페이지만 추출"""
    try:
        reader = PdfReader(io.BytesIO(pdf_bytes))
        if 1 <= page_num <= len(reader.pages):
            writer = PdfWriter()
            writer.add_page(reader.pages[page_num - 1])
            
            output_stream = io.BytesIO()
            writer.write(output_stream)
            return output_stream.getvalue()
        else:
            return None
    except Exception as e:
        st.error(f"페이지 추출 오류: {e}")
        return None