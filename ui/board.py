import streamlit as st
from services.extraction import extract_pdf
from ui.common import target,scoped,save,ai_action

def render(ctx):
    st.header('Perfil da banca')
    if not target(ctx):return
    proofs=st.file_uploader('Provas anteriores (opcional, até 5 PDFs)',type=['pdf'],accept_multiple_files=True)
    consent=st.checkbox('Autorizo enviar os textos das provas ao Google.')
    st.caption('Sem provas anteriores, o resultado é preliminar e baseado nas regras do edital. Não há pesquisa automática na internet nesta base.')
    if st.button('Analisar perfil',disabled=bool(proofs) and not consent,type='primary'):
        def process():
            if len(proofs)>5:raise ValueError('Envie até cinco provas.')
            sources=[]
            for file in proofs:
                doc=extract_pdf(file.getvalue())
                if doc.pages_without_text:raise ValueError('Há páginas de prova sem texto. Faça OCR antes de importar.')
                sources.append({'arquivo':file.name,'texto':doc.text})
            data=ctx['ai'].board(ctx['edict']['payload']['data'],sources)
            return save(ctx,'board',{'data':data,'sources':[x['arquivo'] for x in sources]})
        if ai_action(process):st.success('Perfil salvo.');st.rerun()
    rows=scoped(ctx,'board')
    if rows:
        data=rows[-1]['payload']['data'];st.write(data['scope'])
        for key,title in [('evidence','Evidências'),('style','Estilo'),('pitfalls','Pegadinhas e hipóteses'),('priorities','Prioridades')]:
            st.subheader(title)
            for item in data[key]:st.write('• '+item)
        st.warning(data['limitations'])
