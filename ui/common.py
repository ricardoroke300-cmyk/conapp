import streamlit as st

def target(ctx):
    row=ctx.get('edict')
    if not row:
        st.info('Envie e selecione um edital na aba Edital alvo para começar.')
        return None
    return row

def scoped(ctx,kind):
    edict=target(ctx)
    return [r for r in ctx['repo'].list(kind) if r['payload'].get('edict_id')==edict['id']] if edict else []

def save(ctx,kind,payload,record_id=None):
    ctx['repo'].check()
    return ctx['repo'].put(kind,{'edict_id':ctx['edict']['id'],**payload},record_id)

def subjects(ctx):
    return [m['nome'] for m in ctx['edict']['payload']['data']['guia']['materias']]

def ai_action(fn):
    try:
        with st.spinner('Processando…'):return fn()
    except Exception as exc:
        from services.ai import AIError
        from services.database import AccessError
        st.error(str(exc) if isinstance(exc,(AIError,AccessError,ValueError)) else 'Não foi possível concluir. Confira a configuração dos serviços.')
        return None
