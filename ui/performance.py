import pandas as pd
import altair as alt
import streamlit as st
from ui.common import target,scoped

def render(ctx):
    st.header('Dashboard de desempenho')
    if not target(ctx):return
    attempts=[r['payload'] for r in scoped(ctx,'attempt')]
    simulations=[r for r in scoped(ctx,'simulation') if r['payload']['status']=='finished']
    samples=[{'Matéria':a['subject'],'Acerto':int(a['correct']),'Origem':'Questões'} for a in attempts]
    for row in simulations:
        p=row['payload']
        samples.extend({'Matéria':q['subject'],'Acerto':int(a==q['answer']) if a is not None else 0,'Origem':'Simulados'} for q,a in zip(p['questions'],p['answers']))
    cols=st.columns(3)
    cols[0].metric('Exercícios respondidos',len(attempts));cols[1].metric('Simulados finalizados',len(simulations));cols[2].metric('Acertos nos exercícios',sum(a['correct'] for a in attempts))
    st.caption('Simulados incluem questões em branco no denominador. Questões e simulados são atividades separadas; a mesma questão pode ser resolvida mais de uma vez.')
    if samples:
        frame=pd.DataFrame(samples);group=frame.groupby('Matéria').agg(Respostas=('Acerto','size'),Acertos=('Acerto','sum')).reset_index();group['% de acertos']=100*group['Acertos']/group['Respostas']
        st.altair_chart(alt.Chart(group).mark_bar(color='#087F8C').encode(x=alt.X('% de acertos:Q',scale=alt.Scale(domain=[0,100])),y=alt.Y('Matéria:N',sort='-x'),tooltip=['Matéria','Respostas','Acertos','% de acertos']),use_container_width=True)
        st.dataframe(group,hide_index=True)
        st.write('Prioridade de revisão: '+', '.join(group.sort_values('% de acertos').head(3)['Matéria']))
    else:st.info('Sem respostas suficientes para apresentar pontos fortes ou fracos.')
    history=[{'Data':r['created_at'],'Simulado':r['id'],**r['payload']['result']} for r in simulations]
    if history:st.subheader('Histórico de simulados');st.dataframe(pd.DataFrame(history),hide_index=True)
    essays=[r for r in scoped(ctx,'essay')]
    if essays:
        rows=[{'Data':r['created_at'],'Nota':r['payload']['grade']['total'],'Máximo':r['payload']['grade']['maximum']} for r in essays]
        st.subheader('Redações: notas estimadas');st.dataframe(pd.DataFrame(rows),hide_index=True)
        st.caption('Rubricas diferentes não produzem notas diretamente comparáveis.')
