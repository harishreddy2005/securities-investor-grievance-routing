"""Generate Word/PDF faculty handouts from the canonical Markdown source."""
from pathlib import Path
from xml.sax.saxutils import escape
from docx import Document
from docx.shared import Inches, Pt
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle
from reportlab.platypus import SimpleDocTemplate, Paragraph
from pypdf import PdfReader


def main():
    doc=Document()
    section=doc.sections[0]
    section.top_margin=section.bottom_margin=Inches(.45)
    section.left_margin=section.right_margin=Inches(.55)
    doc.styles['Normal'].font.name='Calibri'
    doc.styles['Normal'].font.size=Pt(9)
    doc.styles['Normal'].paragraph_format.space_after=Pt(3)
    normal=ParagraphStyle('body',fontName='Helvetica',fontSize=9,leading=11,spaceAfter=4)
    heading=ParagraphStyle('heading',parent=normal,fontName='Helvetica-Bold',fontSize=10,leading=12,spaceBefore=5)
    title=ParagraphStyle('title',parent=heading,fontSize=13,leading=15)
    code_style=ParagraphStyle('code',parent=normal,fontName='Courier',fontSize=7,leading=9)
    story=[]; code=False
    for line in Path('docs/FACULTY_SUMMARY.md').read_text(encoding='utf-8').splitlines():
        if line.startswith('```'):
            code=not code
            continue
        if not line.strip(): continue
        if line.startswith('# '):
            text=line[2:]; doc.add_heading(text,0); style=title
        elif line.startswith('## '):
            text=line[3:]; doc.add_heading(text,2); style=heading
        else:
            text=line; paragraph=doc.add_paragraph(text.replace('`',''))
            style=code_style if code else normal
            if code:
                for run in paragraph.runs: run.font.name='Consolas'; run.font.size=Pt(7)
        story.append(Paragraph(escape(text.replace('`','')),style))
    doc.save('docs/FACULTY_SUMMARY.docx')
    SimpleDocTemplate('docs/FACULTY_SUMMARY.pdf',pagesize=A4,leftMargin=36,rightMargin=36,topMargin=26,bottomMargin=26).build(story)
    pages=len(PdfReader('docs/FACULTY_SUMMARY.pdf').pages)
    assert pages==1,f'Faculty PDF must stay one page, got {pages}'
    print('Generated Word handout and verified one-page faculty PDF.')


if __name__=='__main__': main()
