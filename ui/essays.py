import streamlit as st
from services.ai import prepare_image
from ui.common import target,scoped,save,ai_action

GENERIC=[{'name':name,'maximum':20.0,'description':'Critério genérico de treino; não representa a nota oficial da banca.'} for name in ['Adequação ao tema','Estrutura e coerência','Argumentação','Coesão','Domínio da língua']]

def render(ctx):
    st.header('Correção de redação por foto')
    if not target(ctx):return
    eid=ctx['edict']['id'];data=ctx['edict']['payload']['data']
    rubric=data.get('essay_criteria') or GENERIC
    if not data.get('essay_criteria'):st.warning('O edital não informa critérios numéricos suficientes. Será usada rubrica genérica de treino, de 0 a 100.')
    with st.expander('Critérios aplicados'):st.json(rubric)
    if st.button('Gerar tema de treino'):
        theme=ai_action(lambda:ctx['ai'].theme(data))
        if theme:
            st.session_state['theme-'+eid]=theme
            st.session_state['theme-text-'+eid]=theme['title']+'\n'+theme['prompt']+'\n'+theme['instructions']
    generated=st.session_state.get('theme-'+eid,{})
    theme=st.text_area('Tema e proposta (pode informar manualmente)',value=(generated.get('title','')+'\n'+generated.get('prompt','')+'\n'+generated.get('instructions','')).strip(),key='theme-text-'+eid,height=120)
    photos=st.file_uploader('Fotos na ordem das páginas (até 5)',type=['jpg','jpeg','png','webp'],accept_multiple_files=True)
    consent=st.checkbox('Autorizo enviar as fotos e o texto da redação ao Google Gemini.')
    if st.button('Transcrever fotos',disabled=not photos or not consent):
        def process():
            if len(photos)>5:raise ValueError('Envie até cinco fotos.')
            return ctx['ai'].transcribe([prepare_image(f.getvalue()) for f in photos])
        transcription=ai_action(process)
        if transcription:
            if not transcription['readable']:st.error('Fotos ilegíveis. Fotografe novamente.');return
            st.session_state['essay-text-'+eid]=transcription['text']
            st.session_state['essay-confirm-'+eid]=False
            st.session_state['uncertain-'+eid]=transcription['uncertain']
    text=st.text_area('Confira a transcrição; preserve sua escrita original',height=260,key='essay-text-'+eid,max_chars=30000)
    if st.session_state.get('uncertain-'+eid):st.warning('Confira: '+'; '.join(st.session_state['uncertain-'+eid]))
    confirmed=st.checkbox('Confirmei que o texto corresponde à minha redação.',key='essay-confirm-'+eid)
    if st.button('Corrigir e estimar nota',disabled=not confirmed or not consent or not theme.strip(),type='primary'):
        grade=ai_action(lambda:ctx['ai'].grade(text,theme,rubric))
        if grade and ai_action(lambda:save(ctx,'essay',{'theme':theme,'text':text,'rubric':rubric,'grade':grade})):
            st.success('Correção salva no histórico. Nota estimada, não oficial.');st.rerun()
    st.caption('Fotos são processadas em memória; esta base salva somente texto, tema, rubrica e correção no Supabase.')
    for row in reversed(scoped(ctx,'essay')):
        p=row['payload'];g=p['grade']
        with st.expander(f'{row["created_at"][:16]} • {g["total"]:.1f}/{g["maximum"]:.1f}'):
            st.write(p['theme']);st.write(g['feedback']);st.json(g['criteria'])
            for item in g['improvements']:st.write('• '+item)
