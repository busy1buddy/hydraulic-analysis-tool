"""
EPANET Report Generation
=========================
Generates professional DOCX and PDF reports from hydraulic analysis results.
"""

from .docx_report import generate_docx_report
from .pdf_report import generate_pdf_report

__all__ = ['generate_docx_report', 'generate_pdf_report']
