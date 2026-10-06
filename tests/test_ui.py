import sys,unittest,copy
from pathlib import Path
from uuid import uuid4
from datetime import datetime,timezone
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from streamlit.testing.v1 import AppTest
from test_core import guide,question

class FakeRepo:
    user_id='test-user'
    def __init__(self):
        self.rows=[{'id':'edict','kind':'edital','created_at':'2026-10-06T12:00:00Z','payload':{'name':'teste.pdf','cargo':'','data':{'guia':guide(),'exam_date':'','essay_criteria':[]}}},{'id':'q1','kind':'question','created_at':'2026-10-06T12:00:00Z','payload':{'edict_id':'edict','question':question()}}]
    def check(self):pass
    def list(self,kind):return [r for r in self.rows if r['kind']==kind]
    def put(self,kind,payload,record_id=None):
        rid=record_id or str(uuid4());previous=next((x for x in self.rows if x['id']==rid),None)
        row={'id':rid,'kind':kind,'created_at':previous['created_at'] if previous else datetime.now(timezone.utc).isoformat(),'payload':copy.deepcopy(payload)}
        self.rows=[r for r in self.rows if r['id']!=rid]+[row];return row
    def logout(self):pass

class UI(unittest.TestCase):
    def app(self):
        app=AppTest.from_file(str(ROOT/'app.py'),default_timeout=20)
        app.secrets={'SUPABASE_URL':'https://example.supabase.co','SUPABASE_KEY':'fake'}
        app.session_state['repo']=FakeRepo();return app.run()

    def test_unconfigured_app_does_not_bypass_login(self):
        app=AppTest.from_file(str(ROOT/'app.py')).run()
        self.assertEqual(len(app.exception),0)
        self.assertTrue(any('Configure' in x.value for x in app.info))

    def test_all_ten_modules_render(self):
        app=self.app()
        nav=next(x for x in app.radio if x.label=='Navegação')
        options=list(nav.options);self.assertEqual(len(options),10)
        for name in options:
            next(x for x in app.radio if x.label=='Navegação').set_value(name).run()
            self.assertEqual(len(app.exception),0,name)
            self.assertFalse(any('Não foi possível carregar' in x.value for x in app.error),name)

    def test_simulation_snapshot_is_persisted_and_startable(self):
        app=self.app();next(x for x in app.radio if x.label=='Navegação').set_value('Simulados').run()
        next(x for x in app.button if x.label=='Gerar novo simulado').click().run()
        self.assertEqual(len(app.exception),0)
        repo=app.session_state['repo'];sim=repo.list('simulation')[0]
        self.assertEqual(len(sim['payload']['questions']),10)
        self.assertTrue(sim['payload']['reused'])
        next(x for x in app.button if x.label=='Iniciar no aplicativo').click().run()
        self.assertEqual(repo.list('simulation')[0]['payload']['status'],'running')
        self.assertEqual(len(app.exception),0)
        next(x for x in app.button if x.label=='Finalizar simulado').click().run()
        self.assertEqual(repo.list('simulation')[0]['payload']['result']['blank'],10)

if __name__=='__main__':unittest.main()
