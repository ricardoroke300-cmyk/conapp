import streamlit as st
from services.documents import booklet_pdf
from ui.common import target,subjects,scoped,save,ai_action

def render(ctx):
    st.header('Apostilas ilustradas')
    if not target(ctx):return
    names=subjects(ctx)
    if not names:st.info('Nenhuma matéria identificada.');return
    subject=st.selectbox('Matéria',names)
    st.caption('Ilustrações nesta base: diagramas vetoriais de conceitos. Texto gerado por IA precisa de revisão, especialmente leis e normas atualizadas.')
    if st.button('Gerar apostila desta matéria',type='primary'):
        data=ai_action(lambda:ctx['ai'].booklet(ctx['edict']['payload']['data'],subject))
        if data:
            if data['subject']!=subject:st.error('A matéria retornada não corresponde à seleção.');return
            if ai_action(lambda:save(ctx,'booklet',{'subject':subject,'data':data})):st.success('Apostila salva.');st.rerun()
    for row in scoped(ctx,'booklet'):
        if row['payload']['subject']==subject:
            with st.expander(row['payload']['data']['title']):
                pdf=ai_action(lambda:booklet_pdf(row['payload']['data']))
                if pdf:st.download_button('Baixar apostila',pdf,'apostila.pdf','application/pdf',key=row['id'])
                st.json(row['payload']['data'])
