import streamlit as st
from ui.common import target,subjects,scoped,save,ai_action
LEVELS=['Fácil','Médio','Difícil']

def bank(ctx):
    return [{**r['payload']['question'],'id':r['id']} for r in scoped(ctx,'question')]

def generate(ctx,subject,level,count):
    existing=bank(ctx);profiles=scoped(ctx,'board')
    profile=profiles[-1]['payload']['data'] if profiles else {}
    questions=ctx['ai'].questions(ctx['edict']['payload']['data'],subject,level,count,profile,existing)
    saved=[]
    for q in questions:saved.append(save(ctx,'question',{'question':q,'source':'ai','review':'automated'}))
    return saved

def render(ctx):
    st.header('Banco de questões')
    if not target(ctx):return
    names=subjects(ctx)
    if not names:st.info('Não há matérias identificadas.');return
    subject=st.selectbox('Matéria',names);level=st.selectbox('Dificuldade',LEVELS)
    count=int(st.number_input('Questões novas neste lote',1,10,5))
    if st.button('Criar e verificar lote de questões'):
        saved=ai_action(lambda:generate(ctx,subject,level,count))
        if saved:st.success(f'{len(saved)} questões salvas. Conferência automática não substitui revisão humana.');st.rerun()
    pool=[q for q in bank(ctx) if q['subject']==subject and q['level']==level]
    if not pool:st.info('Gere um lote para começar.');return
    topics=sorted({q['topic'] for q in pool});topic=st.selectbox('Assunto',['Todos']+topics)
    pool=[q for q in pool if topic=='Todos' or q['topic']==topic]
    q=st.selectbox('Questão',pool,format_func=lambda q:q['statement'][:90])
    st.write(q['statement']);st.caption('Questão própria gerada por IA; gabarito conferido automaticamente.')
    choice=st.radio('Sua resposta',range(4),format_func=lambda i:f'{chr(65+i)}) {q["alternatives"][i]}',index=None,key='answer-'+q['id'])
    if st.button('Conferir resposta',disabled=choice is None):
        payload={'question_id':q['id'],'subject':subject,'topic':q['topic'],'answer':choice,'correct':choice==q['answer'],'question':q}
        result=ai_action(lambda:save(ctx,'attempt',payload))
        if result:
            st.success('Correto!') if payload['correct'] else st.error(f"Gabarito: {chr(65+q['answer'])}")
            st.write(q['explanation'])
