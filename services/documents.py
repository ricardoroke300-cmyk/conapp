from io import BytesIO
from html import escape
from reportlab.lib.pagesizes import A4
from reportlab.lib import colors
from reportlab.platypus import BaseDocTemplate,PageTemplate,Frame,SimpleDocTemplate,Paragraph,Spacer,Table,TableStyle,Flowable,KeepTogether
from services.guide_pdf import p,page_frame,section,WIDTH,TEAL,NAVY,INK

class Diagram(Flowable):
    """Diagrama vetorial de conceitos; não depende de uma API de imagens."""
    def __init__(self,steps):
        super().__init__();self.steps=steps;self.width=WIDTH;self.height=len(steps)*46
    def draw(self):
        c=self.canv
        for i,text in enumerate(self.steps):
            y=self.height-(i+1)*46+7
            c.setFillColor(colors.HexColor('#EEF5F8'));c.roundRect(0,y,self.width,36,7,fill=1,stroke=0)
            c.setFillColor(TEAL);c.circle(18,y+18,10,fill=1,stroke=0)
            c.setFillColor(colors.white);c.setFont('GuiaSansBold',8);c.drawCentredString(18,y+15,str(i+1))
            para=p(text,8);_,h=para.wrap(self.width-56,28)
            if h>28:
                # A long label becomes normal flowing text elsewhere; no hidden clipping.
                para=p(f'Etapa {i+1}: veja o texto abaixo.',8);_,h=para.wrap(self.width-56,28)
            para.drawOn(c,38,y+(36-h)/2)
            if i<len(self.steps)-1:
                c.setStrokeColor(TEAL);c.line(18,y,18,y-10);c.line(18,y-10,14,y-6);c.line(18,y-10,22,y-6)

def booklet_pdf(data):
    b=BytesIO();doc=SimpleDocTemplate(b,pagesize=A4,leftMargin=42,rightMargin=42,topMargin=46,bottomMargin=54)
    story=[p(data['title'],22,NAVY,True),Spacer(1,8),p(data['subject'],12,TEAL,True),p('Material gerado por IA para treino. Confira referências e atualidade antes de estudar.',8),Spacer(1,15)]
    for i,s in enumerate(data['sections'],1):
        story.extend([section(i,s['title']),Spacer(1,8),p(s['theory']),Spacer(1,8),p('EXEMPLO',9,TEAL,True),p(s['example']),p('ATENÇÃO',9,TEAL,True),p(s['pitfall']),Spacer(1,8),Diagram(s['steps'])])
        for number,text in enumerate(s['steps'],1):
            _,height=p(text,8).wrap(WIDTH-56,28)
            if height>28:story.append(p(f'Etapa {number}: {text}',8))
        story.append(Spacer(1,14))
    story.extend([p('Referências fornecidas',12,NAVY,True)]+([p(x,8) for x in data['references']] or [p('Nenhuma referência verificável foi fornecida no contexto.',8)]))
    doc.build(story,onFirstPage=page_frame,onLaterPages=page_frame);return b.getvalue()

def exam_pdf(simulation,answer_key=False):
    b=BytesIO();questions=simulation['questions']
    if answer_key:
        doc=SimpleDocTemplate(b,pagesize=A4,leftMargin=42,rightMargin=42,topMargin=46,bottomMargin=54)
        story=[p('Gabarito comentado',22,NAVY,True),p(f"Simulado {simulation['id']}",8),Spacer(1,15)]
        for i,q in enumerate(questions,1):story.extend([p(f"{i}. {chr(65+q['answer'])} • {q['subject']}",10,TEAL,True),p(q['explanation']),Spacer(1,9)])
        doc.build(story,onFirstPage=page_frame,onLaterPages=page_frame);return b.getvalue()
    w,h=A4;gap=18;col=(w-84-gap)/2
    def header(c,d):
        page_frame(c,d);c.saveState();c.setFont('GuiaSansBold',9);c.setFillColor(NAVY)
        c.drawString(42,h-40,'SIMULADO • QUESTÕES PRÓPRIAS GERADAS POR IA')
        c.setFont('GuiaSans',7);c.drawString(42,h-53,f"ID: {simulation['id']} • {simulation['minutes']} minutos • {simulation['level']}")
        c.restoreState()
    doc=BaseDocTemplate(b,pagesize=A4)
    frames=[Frame(42,54,col,h-124,id='left',leftPadding=0,rightPadding=0,topPadding=0,bottomPadding=0),Frame(42+col+gap,54,col,h-124,id='right',leftPadding=0,rightPadding=0,topPadding=0,bottomPadding=0)]
    doc.addPageTemplates(PageTemplate(id='two-columns',frames=frames,onPage=header))
    story=[p('Nome: ______________________',8),p('Assinale apenas uma alternativa por questão.',8),Spacer(1,10)]
    for i,q in enumerate(questions,1):
        block=[p(f"{i}. {q['subject']} • {q['topic']}",9,TEAL,True),p(q['statement'],9)]
        block.extend([p(f'{chr(65+j)}) {a}',8) for j,a in enumerate(q['alternatives'])]);block.append(Spacer(1,12))
        story.append(KeepTogether(block))
    story.extend([p('Folha de respostas',12,NAVY,True),Spacer(1,8)])
    for offset in range(0,len(questions),20):
        cells=[[p(f'{i+1:03d}   A ○   B ○   C ○   D ○',8)] for i in range(offset,min(offset+20,len(questions)))]
        t=Table(cells,colWidths=[col]);t.setStyle(TableStyle([('LINEBELOW',(0,0),(-1,-1),.3,colors.lightgrey),('TOPPADDING',(0,0),(-1,-1),5),('BOTTOMPADDING',(0,0),(-1,-1),5)]));story.extend([t,Spacer(1,5)])
    doc.build(story);return b.getvalue()
