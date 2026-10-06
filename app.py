import sys, os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from services.database import Repository, AccessError

"""Ponto de entrada: configuração → autenticação → contexto → módulo."""
import streamlit as st
from services.database import Repository,AccessError
from services.ai import AI
from ui import edital,plan,materials,simulations,board,questions,performance,essays

st.set_page_config(page_title='Concurso IA',page_icon='📘',layout='wide')

def settings():
    try:return dict(st.secrets)
    except (FileNotFoundError,st.errors.StreamlitSecretNotFoundError):return {}

def clear_session():
    for key in list(st.session_state):del st.session_state[key]

def login(config):
    st.title('Concurso IA');st.caption('Estude a partir do seu edital.')
    with st.form('login'):
        email=st.text_input('E-mail');password=st.text_input('Senha',type='password')
        license_key=st.text_input('Chave de licença',type='password')
        submit=st.form_submit_button('Entrar',type='primary')
    if submit:
        try:
            repo=Repository(config['SUPABASE_URL'],config['SUPABASE_KEY'])
            repo.login(email,password,license_key)
            clear_session();st.session_state['repo']=repo;st.rerun()
        except AccessError as exc:st.error(str(exc))
        except Exception:st.error('Não foi possível acessar o Supabase. Confira a configuração.')
    st.info('Nesta base, contas e licenças são criadas pelo administrador no Supabase. Não há checkout ou cadastro aberto.')

def main():
    config=settings()
    if not config.get('SUPABASE_URL') or not config.get('SUPABASE_KEY'):
        st.title('Concurso IA • Configuração inicial')
        st.info('Configure SUPABASE_URL e SUPABASE_KEY nos Secrets. Execute o SQL e crie uma conta/licença antes do primeiro login.')
        st.code('python -m streamlit run app.py',language='bash')
        st.stop()
    repo=st.session_state.get('repo')
    if not repo:login(config);return
    try:repo.check()
    except AccessError as exc:
        clear_session();st.error(str(exc));st.stop()

    # No global cached Supabase client: each Streamlit session owns its JWT.
    @st.fragment(run_every='30s')
    def heartbeat():
        try:repo.check();st.caption('Licença ativa • sessão autorizada')
        except AccessError:
            clear_session();st.rerun()
    with st.sidebar:
        st.title('Concurso IA');heartbeat()
        if st.button('Sair'):
            try:repo.logout()
            except Exception:pass
            clear_session();st.rerun()
        rows=repo.list('edital')
        current=st.selectbox('Edital ativo',rows,index=len(rows)-1 if rows else None,format_func=lambda r:r['payload']['name']+' • '+(r['payload'].get('cargo') or 'todos os cargos')) if rows else None
        chosen=st.radio('Navegação',list(PAGES))
    ctx={'repo':repo,'ai':AI(config.get('GEMINI_API_KEY',''),config.get('GEMINI_MODEL','gemini-3.5-flash-lite'),repo),'edict':current}
    if current:st.caption('Edital ativo: '+current['payload']['name'])
    try:PAGES[chosen](ctx)
    except AccessError:
        clear_session();st.error('Acesso encerrado. Entre novamente.')
    except Exception:st.error('Não foi possível carregar este módulo. Confira conexão, configuração SQL e dados do edital.')

def account(ctx):
    st.header('Conta e licença')
    st.write('Usuário: '+ctx['repo'].user_id)
    st.write('Licença validada no Supabase. Outra autenticação fica bloqueada enquanto esta sessão mantém sua reserva ativa.')
    st.caption('Licenciamento reduz compartilhamento; não impede toda cópia. Uma sessão abandonada é liberada após dois minutos sem renovação.')

PAGES={
    'Conta e licença':account,
    'Edital alvo':edital.upload_view,
    'Guia resumido do edital':edital.guide_view,
    'Plano de estudos':plan.render,
    'Apostilas ilustradas':materials.render,
    'Simulados':simulations.render,
    'Perfil da banca':board.render,
    'Banco de questões':questions.render,
    'Desempenho':performance.render,
    'Redação':essays.render,
}

if __name__=='__main__':main()
