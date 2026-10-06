import json
import streamlit as st
from services.extraction import extract_pdf
from services.guide_pdf import render_pdf
from core.guide_schema import Guia
from ui.common import target,ai_action

def upload_view(ctx):
    st.header('Edital alvo')
    file=st.file_uploader('Edital original em PDF',type=['pdf'])
    cargo=st.text_input('Cargo de interesse (opcional)',max_chars=300)
    authorized=st.checkbox('Autorizo enviar o texto deste edital público ao Google Gemini.')
    st.caption('PDF textual de até 20 MB; sem OCR. Na faixa gratuita do Google, dados podem ser usados para melhorar seus produtos.')
    if st.button('Analisar e salvar edital',disabled=not file or not authorized,type='primary'):
        def process():
            document=extract_pdf(file.getvalue())
            if document.pages_without_text:raise ValueError('Há páginas sem texto extraível. Faça OCR ou remova páginas realmente vazias antes de analisar.')
            data=ctx['ai'].edital(document.text,cargo)
            return ctx['repo'].put('edital',{'name':file.name,'cargo':cargo,'data':data})
        if ai_action(process):st.success('Edital salvo. Selecione-o no menu lateral.');st.rerun()
    if ctx.get('edict'):
        st.subheader('Edital selecionado')
        st.json(ctx['edict']['payload']['data'])

def guide_view(ctx):
    st.header('Guia resumido do edital')
    edict=target(ctx)
    if not edict:return
    guide=Guia.model_validate(edict['payload']['data']['guia'])
    st.write(guide.orgao);st.caption('Resumo de apoio: confira o edital oficial e suas retificações.')
    if st.button('Preparar PDF visual',type='primary'):
        pdf=ai_action(lambda:render_pdf(guide))
        if pdf:st.session_state['guide_pdf']=(edict['id'],pdf)
    saved=st.session_state.get('guide_pdf')
    if saved and saved[0]==edict['id']:st.download_button('Baixar guia em PDF',saved[1],'guia-edital.pdf','application/pdf')
    st.download_button('Baixar JSON',json.dumps(guide.model_dump(),ensure_ascii=False,indent=2),'guia.json','application/json')
