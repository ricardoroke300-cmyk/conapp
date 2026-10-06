from datetime import datetime,timedelta,timezone
from uuid import uuid4
import streamlit as st
from core.study import recommend_count,select_simulation,score_simulation
from services.documents import exam_pdf
from ui.common import target,scoped,save,ai_action
from ui.questions import bank,generate,LEVELS

def finish(ctx,row):
    p=row['payload'];p={**p,'status':'finished','finished_at':datetime.now(timezone.utc).isoformat(),'result':score_simulation(p['questions'],p['answers'])}
    return save(ctx,'simulation',p,row['id'])

def render(ctx):
    st.header('Gerador de simulados')
    if not target(ctx):return
    data=ctx['edict']['payload']['data'];matters=data['guia']['materias']
    if not matters:st.info('Não há matérias identificadas.');return
    st.caption('Sem limite comercial de número de simulados. Use o banco salvo quantas vezes desejar; novas questões por IA têm cota. Pontuação nesta base: um ponto por acerto, sem penalidade.')
    level=st.selectbox('Dificuldade',LEVELS,key='sim-level');minutes=int(st.number_input('Duração em minutos',1,1440,60))
    distribution={}
    for m in matters:
        recommended=recommend_count(m['questoes'])
        st.caption(f"{m['nome']}: recomendação do edital = {recommended if recommended is not None else 'não informada/ambígua'}; {m['peso']}")
        distribution[m['nome']]=int(st.number_input('Questões de '+m['nome'],min_value=0,value=recommended if recommended is not None else 5,step=1,key='count-'+m['nome']))
    st.caption('Quantidades editáveis. Caso excedam o banco do filtro, haverá reutilização identificada. Volumes muito grandes dependem da memória e do tempo de processamento.')
    if st.button('Gerar novo simulado',type='primary'):
        def create():
            questions,reused=select_simulation(bank(ctx),distribution,level)
            sid=str(uuid4())
            return save(ctx,'simulation',{'id':sid,'questions':questions,'answers':[None]*len(questions),'minutes':minutes,'level':level,'status':'draft','reused':reused},sid)
        if ai_action(create):st.success('Simulado salvo com ordem e questões fixas.');st.rerun()
    st.info('Se faltar banco em alguma matéria/nível, use Banco de questões para criar um lote verificado antes de montar o simulado.')
    rows=scoped(ctx,'simulation')
    if not rows:return
    row=st.selectbox('Simulados salvos',list(reversed(rows)),format_func=lambda r:f"{r['created_at'][:16]} • {len(r['payload']['questions'])} questões • {r['payload']['status']}")
    p=row['payload']
    if p['reused']:st.warning('Este simulado reutiliza questões para atender à quantidade escolhida.')
    if st.button('Preparar caderno e gabarito em PDF'):
        def pdfs():return exam_pdf(p),exam_pdf(p,True)
        result=ai_action(pdfs)
        if result:st.session_state['sim-pdf']=(row['id'],*result)
    pdfs=st.session_state.get('sim-pdf')
    if pdfs and pdfs[0]==row['id']:
        st.download_button('Caderno em duas colunas',pdfs[1],'simulado.pdf','application/pdf')
        st.download_button('Gabarito comentado separado',pdfs[2],'gabarito.pdf','application/pdf')
    if p['status']=='draft':
        if st.button('Iniciar no aplicativo'):
            if any(r['payload']['status']=='running' for r in rows):st.error('Finalize o simulado em andamento primeiro.');return
            now=datetime.now(timezone.utc)
            if ai_action(lambda:save(ctx,'simulation',{**p,'status':'running','started_at':now.isoformat(),'deadline':(now+timedelta(minutes=p['minutes'])).isoformat()},row['id'])):st.rerun()
    elif p['status']=='running':
        deadline=datetime.fromisoformat(p['deadline'])
        if datetime.now(timezone.utc)>=deadline:
            if ai_action(lambda:finish(ctx,row)):st.rerun()
            return
        @st.fragment(run_every='1s')
        def timer():
            remaining=max(0,int((deadline-datetime.now(timezone.utc)).total_seconds()))
            st.metric('Tempo restante',f'{remaining//60:02d}:{remaining%60:02d}')
            if remaining==0:
                try:finish(ctx,row);st.rerun()
                except Exception:st.error('Não foi possível salvar o encerramento. Verifique sua sessão.')
        timer()
        for i,q in enumerate(p['questions']):
            st.subheader(f'{i+1}. {q["subject"]}');st.write(q['statement'])
            key=f'sim-{row["id"]}-{i}'
            def changed(index=i,widget=key):
                if datetime.now(timezone.utc)>=deadline:return
                p['answers'][index]=st.session_state[widget]
                save(ctx,'simulation',p,row['id'])
            st.radio('Alternativa',range(4),format_func=lambda a,q=q:f'{chr(65+a)}) {q["alternatives"][a]}',index=p['answers'][i],key=key,on_change=changed)
        if st.button('Finalizar simulado'):
            try:finish(ctx,row);st.rerun()
            except Exception:st.error('Não foi possível salvar. Verifique sua sessão antes de tentar novamente.')
    else:
        st.json(p['result'])
        for i,(q,a) in enumerate(zip(p['questions'],p['answers']),1):
            with st.expander(f'{i}. {q["subject"]} • {"em branco" if a is None else "acerto" if a==q["answer"] else "erro"}'):
                st.write(q['statement']);st.write(f'Gabarito: {chr(65+q["answer"])}');st.write(q['explanation'])
