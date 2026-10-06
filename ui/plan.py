from datetime import date
from zoneinfo import ZoneInfo
from datetime import datetime
import pandas as pd
import streamlit as st
from core.study import build_plan
from ui.common import target,subjects,scoped,save,ai_action

def render(ctx):
    st.header('Plano de estudos adaptativo')
    edict=target(ctx)
    if not edict:return
    names=subjects(ctx)
    if not names:st.warning('O edital não tem matérias identificadas. Confira a extração.');return
    stored=scoped(ctx,'plan');current=stored[-1] if stored else None
    available=current['payload']['available'] if current else [60]*5+[0,0]
    days=['Segunda','Terça','Quarta','Quinta','Sexta','Sábado','Domingo']
    available=[int(st.number_input(f'{d}: minutos disponíveis',0,720,int(v),step=10)) for d,v in zip(days,available)]
    raw=edict['payload']['data'].get('exam_date','')
    try:exam=date.fromisoformat(raw)
    except ValueError:exam=None
    known=st.checkbox('Definir data da prova',value=exam is not None)
    today=datetime.now(ZoneInfo('America/Sao_Paulo')).date()
    exam=st.date_input('Data da prova',value=exam or today) if known else None
    st.caption('Distribuição determinística por matéria e desempenho. Horizonte de até 90 dias; gere novamente conforme sua evolução. Zero minutos não cria sessões.')
    if st.button('Gerar/atualizar plano',type='primary'):
        attempts=scoped(ctx,'attempt');accuracy={}
        for s in names:
            a=[x['payload'] for x in attempts if x['payload']['subject']==s][-50:]
            if a:accuracy[s]=sum(x['correct'] for x in a)/len(a)
        sessions=build_plan(names,available,exam,accuracy,today)
        saved=ai_action(lambda:save(ctx,'plan',{'available':available,'exam_date':exam.isoformat() if exam else '', 'sessions':sessions},current['id'] if current else None))
        if saved:st.success('Plano salvo.');st.rerun()
    if current:st.dataframe(pd.DataFrame(current['payload']['sessions']),hide_index=True,use_container_width=True)
