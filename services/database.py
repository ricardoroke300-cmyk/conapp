"""Login por e-mail + licença e RPCs autorizadas por token opaco. Sem Auth."""
import re
from uuid import uuid4
from supabase import create_client

class AccessError(RuntimeError):pass

class Repository:
    def __init__(self,url,key):
        self.client=create_client(url,key)
        self.user_id=None
        self.email=None
        self._token=None

    def login(self,email,license_key):
        email=email.strip().lower()
        if len(email)>254 or not re.fullmatch(r'[^\s@]+@[^\s@]+\.[^\s@]+',email) or not 16<=len(license_key.strip())<=200:
            raise AccessError('Informe um e-mail válido e a chave de licença recebida.')
        try:
            result=self.client.rpc('license_login',{'p_email':email,'p_key':license_key.strip()}).execute().data
            if not isinstance(result,dict) or not result.get('token') or not result.get('user_id'):
                raise AccessError('Resposta de licença inválida.')
            self._token=result['token'];self.user_id=result['user_id'];self.email=email
        except Exception as exc:
            self._token=None;self.user_id=None;self.email=None
            raise AccessError('E-mail ou licença não autorizado. Se houver outra sessão ativa, encerre-a ou aguarde dois minutos.') from exc

    def _rpc(self,name,parameters=None):
        if not self._token:raise AccessError('Entre novamente.')
        try:
            return self.client.rpc(name,{'p_token':self._token,**(parameters or {})}).execute().data
        except Exception as exc:
            raise AccessError('A operação não foi autorizada. Confira a sessão, licença, conexão e limite diário.') from exc

    def check(self):
        self._rpc('license_heartbeat')

    def logout(self):
        try:
            if self._token:self._rpc('license_logout')
        finally:
            self._token=None;self.user_id=None;self.email=None

    def list(self,kind):
        self.check();rows=[];offset=0
        while True:
            batch=self._rpc('license_records_list',{'p_kind':kind,'p_offset':offset,'p_limit':500}) or []
            rows.extend(batch)
            if len(batch)<500:return rows
            offset+=500

    def put(self,kind,payload,record_id=None):
        self.check()
        return self._rpc('license_record_put',{'p_kind':kind,'p_payload':payload,'p_id':record_id or str(uuid4())})

    def reserve_ai(self):
        self.check();self._rpc('license_reserve_ai')
