"""Layout vetorial A4: cartões, tabelas e disciplinas com paginação automática."""
from html import escape
from io import BytesIO
from pathlib import Path
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.lib import colors
from reportlab.lib.enums import TA_LEFT
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, LongTable, TableStyle, KeepTogether
from core.guide_schema import Guia

NAVY = colors.HexColor("#102B46")
TEAL = colors.HexColor("#087F8C")
INK = colors.HexColor("#22364A")
LIGHT = colors.HexColor("#EEF5F8")
GOLD = colors.HexColor("#EFB548")
WIDTH = A4[0] - 84
ASSETS = Path(__file__).resolve().parents[1] / "assets"
pdfmetrics.registerFont(TTFont("GuiaSans", str(ASSETS / "DejaVuSans.ttf")))
pdfmetrics.registerFont(TTFont("GuiaSansBold", str(ASSETS / "DejaVuSans-Bold.ttf")))
BODY = ParagraphStyle("body", fontName="GuiaSans", fontSize=9, leading=13, textColor=INK, alignment=TA_LEFT, splitLongWords=True)

def p(value, size=9, color=INK, bold=False):
    style = ParagraphStyle("p", parent=BODY, fontName="GuiaSansBold" if bold else "GuiaSans", fontSize=size, leading=size*1.4, textColor=color)
    return Paragraph(escape(str(value)).replace("\n", "<br/>"), style)

def section(number, title):
    t = Table([[p(f"{number:02d}", 11, colors.white, True), p(title, 14, NAVY, True)]], colWidths=[36, WIDTH-36])
    t.setStyle(TableStyle([("BACKGROUND",(0,0),(0,0),TEAL),("VALIGN",(0,0),(-1,-1),"MIDDLE"),("TOPPADDING",(0,0),(-1,-1),8),("BOTTOMPADDING",(0,0),(-1,-1),8),("LEFTPADDING",(1,0),(1,0),12)]))
    return t

def rows_table(headers, rows, widths):
    table = LongTable([[p(x,9,colors.white,True) for x in headers]] + [[p(x) for x in row] for row in rows], colWidths=widths, repeatRows=1, splitInRow=1)
    table.setStyle(TableStyle([("BACKGROUND",(0,0),(-1,0),NAVY),("ROWBACKGROUNDS",(0,1),(-1,-1),[LIGHT,colors.white]),("VALIGN",(0,0),(-1,-1),"TOP"),("LEFTPADDING",(0,0),(-1,-1),10),("RIGHTPADDING",(0,0),(-1,-1),10),("TOPPADDING",(0,0),(-1,-1),9),("BOTTOMPADDING",(0,0),(-1,-1),9),("LINEBELOW",(0,0),(-1,0),2,TEAL),("LINEBELOW",(0,1),(-1,-1),0.4,colors.HexColor("#DCE7ED"))]))
    return table

def page_frame(canvas, doc):
    canvas.saveState()
    w,h = A4
    canvas.setFillColor(NAVY)
    canvas.rect(0,h-22,w,22,fill=1,stroke=0)
    canvas.setFillColor(TEAL)
    canvas.rect(0,h-25,w,3,fill=1,stroke=0)
    canvas.setStrokeColor(colors.HexColor("#DCE7ED"))
    canvas.line(42,39,w-42,39)
    canvas.setFont("GuiaSans",7)
    canvas.setFillColor(INK)
    canvas.drawString(42,26,"Guia de estudo • Confira as regras no edital original e nas retificações.")
    canvas.drawRightString(w-42,26,f"Página {doc.page}")
    canvas.restoreState()

def render_pdf(guide: Guia) -> bytes:
    guide = Guia.model_validate(guide.model_dump())
    output = BytesIO()
    doc = SimpleDocTemplate(output,pagesize=A4,rightMargin=42,leftMargin=42,topMargin=46,bottomMargin=54,title=guide.titulo,author="Guia Visual de Concursos")
    story = [p("SEU CONCURSO, MAIS CLARO",9,TEAL,True),Spacer(1,6),p(guide.titulo,24,NAVY,True),Spacer(1,8),p(guide.orgao,13,NAVY,True),Spacer(1,5),p(f"Banca organizadora: {guide.banca}"),Spacer(1,18)]
    cards = [("VAGAS",guide.vagas),("REMUNERAÇÃO",guide.remuneracao),("ESCOLARIDADE",guide.escolaridade),("CARGA HORÁRIA",guide.carga_horaria)]
    for start in (0,2):
        row = [[p(label,8,TEAL,True),Spacer(1,5),p(value,11,NAVY,True)] for label,value in cards[start:start+2]]
        # Cards can split when multi-cargo text is long; no fixed height or clipping.
        t=Table([row],colWidths=[WIDTH/2,WIDTH/2],splitInRow=1)
        t.setStyle(TableStyle([("BACKGROUND",(0,0),(-1,-1),LIGHT),("BOX",(0,0),(-1,-1),0.6,colors.HexColor("#DCE7ED")),("INNERGRID",(0,0),(-1,-1),5,colors.white),("VALIGN",(0,0),(-1,-1),"TOP"),("LEFTPADDING",(0,0),(-1,-1),14),("RIGHTPADDING",(0,0),(-1,-1),14),("TOPPADDING",(0,0),(-1,-1),12),("BOTTOMPADDING",(0,0),(-1,-1),12)]))
        story.extend([t,Spacer(1,7)])
    story.extend([Spacer(1,13),section(1,"Datas importantes"),Spacer(1,10)])
    story.append(rows_table(["EVENTO","DATA / PERÍODO"],[[x.evento,x.data] for x in guide.cronograma],[WIDTH*.43,WIDTH*.57]) if guide.cronograma else p("Cronograma não informado no edital."))
    story.extend([Spacer(1,18),section(2,"Etapas da seleção"),Spacer(1,10)])
    story.append(rows_table(["FASE","ETAPA","CARÁTER / DETALHE"],[[x.fase,x.nome,f"{x.tipo}\n{x.detalhe}"] for x in guide.fases],[WIDTH*.15,WIDTH*.35,WIDTH*.5]) if guide.fases else p("Fases não informadas no edital."))
    story.extend([Spacer(1,18),section(3,"O que estudar"),Spacer(1,10)])
    if not guide.materias:
        story.append(p("Matérias não informadas no edital."))
    for index,m in enumerate(guide.materias,1):
        heading=Table([[p(f"{index:02d}  {m.nome}",11,colors.white,True)]],colWidths=[WIDTH])
        heading.setStyle(TableStyle([("BACKGROUND",(0,0),(-1,-1),TEAL),("LEFTPADDING",(0,0),(-1,-1),12),("TOPPADDING",(0,0),(-1,-1),8),("BOTTOMPADDING",(0,0),(-1,-1),8)]))
        meta=p(f"{m.peso}  •  {m.questoes}",9,TEAL,True)
        story.extend([KeepTogether([heading,Spacer(1,6),meta,Spacer(1,5)]),p(m.topicos),Spacer(1,15)])
    story.extend([Spacer(1,6),p("ATENÇÃO AO EDITAL ORIGINAL",9,TEAL,True),Spacer(1,4),p("Este guia é um resumo de apoio. Requisitos, exceções, anexos e retificações devem ser conferidos no edital oficial. Campos não informados não foram estimados.",8)])
    doc.build(story,onFirstPage=page_frame,onLaterPages=page_frame)
    return output.getvalue()
