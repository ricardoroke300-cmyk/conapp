import unittest
import sys,json,random
from pathlib import Path
from datetime import date
from io import BytesIO
from unittest.mock import MagicMock,patch
from types import SimpleNamespace
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from core.models import Edict,Question,EssayGrade
from core.study import *
from services.documents import exam_pdf,booklet_pdf
from services.guide_pdf import render_pdf
from core.guide_schema import Guia
from services.ai import AI,AIError,prepare_image
from services.database import Repository,AccessError
from pypdf import PdfReader
from PIL import Image

def guide():
    return {'titulo':'Guia de teste','orgao':'Órgão de teste','banca':'Banca de teste','vagas':'10','remuneracao':'R$ 2.000','escolaridade':'Médio','carga_horaria':'40h','cronograma':[{'evento':'Prova','data':'01/12/2026'}],'fases':[{'fase':'1','nome':'Objetiva','tipo':'Eliminatória','detalhe':'10 questões'}],'materias':[{'nome':'Português','peso':'Peso 1','questoes':'10 questões','topicos':'Interpretação e concordância'}]}

def question():
    return {'subject':'Português','topic':'Concordância','level':'Fácil','statement':'Qual é a frase correta?','alternatives':['Os alunos estudam.','Os alunos estuda.','Os alunos estudou.','Os alunos estudar.'],'answer':0,'explanation':'O verbo concorda com o sujeito plural.'}

class CoreTests(unittest.TestCase):
    def test_counts_unambiguous_only(self):
        self.assertEqual(recommend_count('15 Questões'),15)
        self.assertIsNone(recommend_count('10 para cargo A e 15 para B'))
        self.assertIsNone(recommend_count('Não informado no edital'))

    def test_plan_exact_time_and_exam_boundary(self):
        start=date(2026,10,5);p=build_plan(['A','B'],[61,0,10,0,0,0,0],start+timedelta(days=2),start=start)
        self.assertEqual(sum(x['minutes'] for x in p),71)
        self.assertTrue(all(x['minutes']<=50 for x in p))
        self.assertEqual(build_plan(['A'],[0]*7,start=start),[])

    def test_simulation_reuses_and_snapshots(self):
        original=question();q,reused=select_simulation([original],{'Português':15},'Fácil',random.Random(1))
        self.assertTrue(reused);self.assertEqual(len(q),15)
        original['statement']='changed';self.assertNotEqual(q[0]['statement'],'changed')
        self.assertEqual(score_simulation(q,[0]*10+[1]*3+[None]*2),{'correct':10,'wrong':3,'blank':2,'total':15,'percentage':66.67})
        with self.assertRaises(ValueError):select_simulation([] ,{'A':1},'Fácil')

    def test_dedup_and_rubric(self):
        q=question();self.assertEqual(distinct_questions([q],[q]),[])
        rubric=[{'name':'Tema','maximum':20.0}]
        g={'criteria':[{'name':'Tema','score':15.0,'maximum':20.0}]}
        self.assertEqual(validate_grade(g,rubric),(15,20))
        g['criteria'][0]['score']=21
        with self.assertRaises(ValueError):validate_grade(g,rubric)

    def test_two_column_pdf_same_questions_key(self):
        q=question();sim={'id':'abc','questions':[q]*12,'minutes':60,'level':'Fácil'}
        r=PdfReader(BytesIO(exam_pdf(sim)));text='\n'.join(p.extract_text() for p in r.pages)
        self.assertEqual(text.count(q['statement']),12)
        page=r.pages[0];positions=[]
        page.extract_text(visitor_text=lambda text,cm,tm,font,size:positions.append(tm[4]+cm[4]) if q['statement'] in text else None)
        self.assertTrue(any(x<250 for x in positions));self.assertTrue(any(x>300 for x in positions))
        key='\n'.join(p.extract_text() for p in PdfReader(BytesIO(exam_pdf(sim,True))).pages)
        self.assertIn(q['explanation'],key)

    def test_booklet_vector_and_guide(self):
        b={'title':'Apostila','subject':'Português','sections':[{'title':'Regra','theory':'Teoria & texto <seguro>','example':'Exemplo','pitfall':'Atenção','steps':['Localize o sujeito','Confira o verbo']}],'references':[]}
        r=PdfReader(BytesIO(booklet_pdf(b)));self.assertIn('Localize o sujeito',''.join(p.extract_text() for p in r.pages))
        r=PdfReader(BytesIO(render_pdf(Guia.model_validate(guide()))));self.assertIn('Português',''.join(p.extract_text() for p in r.pages))

    def test_images_reject_and_encode(self):
        with self.assertRaises(ValueError):prepare_image(b'fake')
        b=BytesIO();Image.new('RGB',(50,50),'white').save(b,format='PNG')
        self.assertTrue(prepare_image(b.getvalue()).startswith(b'\xff\xd8'))

    def test_ai_independent_verification(self):
        ai=AI('fake','fake',MagicMock());q=question()
        ai.run=MagicMock(side_effect=[{'questions':[q]},{'items':[{'index':0,'answer':1,'valid':True,'reason':'Divergência'}]}])
        with self.assertRaises(AIError):ai.questions({'guia':guide()},'Português','Fácil',1,{},[])
        ai.run=MagicMock(side_effect=[{'questions':[q]},{'items':[{'index':0,'answer':0,'valid':True,'reason':'Confirmado'}]}])
        self.assertEqual(len(ai.questions({'guia':guide()},'Português','Fácil',1,{},[])),1)
        blind=ai.run.call_args.args[2]['questions'][0];self.assertNotIn('answer',blind);self.assertNotIn('explanation',blind)

    def test_ai_json_and_truncation(self):
        mock=MagicMock();mock.models.get.return_value=SimpleNamespace(input_token_limit=100000)
        mock.models.count_tokens.return_value=SimpleNamespace(total_tokens=100)
        mock.models.generate_content.return_value=SimpleNamespace(candidates=[SimpleNamespace(finish_reason='MAX_TOKENS')],text=json.dumps(question()))
        ai=AI('fake','fake',MagicMock())
        with patch('services.ai.genai.Client',return_value=mock):
            with self.assertRaises(AIError):ai.run(Question,'instruction',{})
        mock.models.generate_content.return_value=SimpleNamespace(candidates=[SimpleNamespace(finish_reason='STOP')],text=json.dumps(question()))
        with patch('services.ai.genai.Client',return_value=mock):self.assertEqual(ai.run(Question,'instruction',{})['answer'],0)

    def test_repo_login_failure_signs_out(self):
        mock=MagicMock();mock.auth.sign_in_with_password.return_value=SimpleNamespace(user=SimpleNamespace(id='u'),session=object())
        mock.rpc.return_value.execute.side_effect=RuntimeError('session_in_use')
        with patch('services.database.create_client',return_value=mock):
            repo=Repository('url','key')
            with self.assertRaises(AccessError):repo.login('email','password','license')
        self.assertIsNone(repo.user_id);mock.auth.sign_out.assert_called_once()

    def test_repo_refresh_and_pagination(self):
        repo=Repository.__new__(Repository);repo.client=MagicMock();repo.user_id='u'
        repo.client.auth.get_session.return_value=SimpleNamespace(expires_at=0)
        repo.check();repo.client.auth.refresh_session.assert_called_once()
        query=repo.client.table.return_value.select.return_value.eq.return_value.order.return_value
        query.range.return_value.execute.side_effect=[SimpleNamespace(data=[{}]*500),SimpleNamespace(data=[{}]*2)]
        self.assertEqual(len(repo.list('question')),502)

    def test_sql_syntax(self):
        try:from pglast import parse_sql
        except ImportError:self.skipTest('Instale requirements-dev.txt para validar SQL')
        for path in (ROOT/'sql').glob('*.sql'):self.assertTrue(parse_sql(path.read_text()))

if __name__=='__main__':unittest.main()
