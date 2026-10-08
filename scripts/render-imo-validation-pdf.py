from pathlib import Path
from html import escape
from docx import Document
from docx.text.paragraph import Paragraph as DP
from docx.table import Table as DT
from reportlab.platypus import SimpleDocTemplate,Paragraph,Table,TableStyle,Spacer,PageBreak
from reportlab.lib.styles import getSampleStyleSheet,ParagraphStyle
from reportlab.lib import colors
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
import pypdfium2 as pdfium

ROOT=Path(__file__).resolve().parents[1];OUT=ROOT/'outputs/imo-validation';QA=ROOT/'tmp/imo-validation'
pdfmetrics.registerFont(TTFont('Arial','C:/Windows/Fonts/arial.ttf'));pdfmetrics.registerFont(TTFont('Arial-Bold','C:/Windows/Fonts/arialbd.ttf'))
styles=getSampleStyleSheet()
for name in styles.byName:styles[name].fontName='Arial';styles[name].textColor=colors.black
styles['Normal'].fontSize=10;styles['Normal'].leading=13;styles['Normal'].spaceAfter=7
styles['Title'].fontName='Arial-Bold';styles['Title'].fontSize=22;styles['Title'].leading=26;styles['Title'].alignment=0;styles['Title'].spaceAfter=14
styles['Heading1'].fontName='Arial-Bold';styles['Heading1'].fontSize=16;styles['Heading1'].leading=20;styles['Heading1'].spaceBefore=5;styles['Heading1'].spaceAfter=10
styles['Heading2'].fontName='Arial-Bold';styles['Heading2'].fontSize=11;styles['Heading2'].leading=14;styles['Heading2'].spaceBefore=6;styles['Heading2'].spaceAfter=4
styles.add(ParagraphStyle('Cell',fontName='Arial',fontSize=9,leading=11,spaceAfter=0))
styles.add(ParagraphStyle('CellHead',parent=styles['Cell'],fontName='Arial-Bold'))
def plain(t):return escape(t).replace('\n','<br/>')
def footer(canvas,doc):
    canvas.setFont('Arial',8);canvas.drawString(50,26,'IMO recruiting validation | Evidence checked October 8, 2026');canvas.drawRightString(562,26,str(doc.page))
for stem in ['IMO_Recruiting_Analysis','Reviewer_Checklist']:
    doc=Document(OUT/(stem+'.docx'));flow=[]
    for el in doc.element.body.iterchildren():
        if el.tag.endswith('}p'):
            p=DP(el,doc)
            if el.xpath('.//w:br[@w:type="page"]'):flow.append(PageBreak())
            if p.text:
                style_name=p.style.name.replace(' ','')
                style=styles[style_name] if style_name in styles.byName else styles['Normal']
                content=''.join(('<b>'+plain(run.text)+'</b>')if run.bold else plain(run.text)for run in p.runs)
                flow.append(Paragraph(content or plain(p.text),style))
        elif el.tag.endswith('}tbl'):
            t=DT(el,doc);rows=[[Paragraph(plain(c.text),styles['CellHead']if i==0 else styles['Cell'])for c in row.cells]for i,row in enumerate(t.rows)]
            widths=[c.width/914400*72 if c.width else 504/len(t.rows[0].cells) for c in t.rows[0].cells]
            widths=[w*504/sum(widths)for w in widths]
            rt=Table(rows,colWidths=widths,repeatRows=1,hAlign='LEFT')
            rt.setStyle(TableStyle([('GRID',(0,0),(-1,-1),.45,colors.HexColor('#D9D9D9')),('BACKGROUND',(0,0),(-1,0),colors.HexColor('#E8EDF3')),('VALIGN',(0,0),(-1,-1),'MIDDLE'),('LEFTPADDING',(0,0),(-1,-1),7),('RIGHTPADDING',(0,0),(-1,-1),7),('TOPPADDING',(0,0),(-1,-1),5),('BOTTOMPADDING',(0,0),(-1,-1),5)]))
            flow.extend([rt,Spacer(1,8)])
    path=OUT/(stem+'.pdf')
    SimpleDocTemplate(str(path),pagesize=(612,792),leftMargin=50,rightMargin=58,topMargin=45,bottomMargin=45,title=stem.replace('_',' '),author='IMO recruiting validation').build(flow,onFirstPage=footer,onLaterPages=footer)
    pdf=pdfium.PdfDocument(str(path));dest=QA/(stem+'-pages');dest.mkdir(exist_ok=True)
    for i in range(len(pdf)):pdf[i].render(scale=1.5).to_pil().save(dest/f'page-{i+1}.png')
    print(stem,len(pdf),'pages')
