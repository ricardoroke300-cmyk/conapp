"""Cliente isolado por sessão: chave pública e JWT do aluno; nunca service_role."""
from uuid import uuid4
import time
from supabase import create_client

class AccessError(RuntimeError):pass

class Repository:
    def __init__(self,url,key):
        self.client=create_client(url,key)
        self.user_id=None

    def login(self,email,password,license_key):
        try:
            result=self.client.auth.sign_in_with_password({"email":email,"password":password})
            if not result.user or not result.session:raise AccessError("Login não autorizado.")
            self.user_id=result.user.id
            self.client.rpc("acquire_license",{"p_key":license_key.strip()}).execute()
        except Exception as exc:
            try:self.client.auth.sign_out({"scope":"local"})
            except Exception:pass
            self.user_id=None
            raise AccessError("Login ou licença não autorizado. Confira suas credenciais; se houver outra sessão ativa, encerre-a ou aguarde dois minutos.") from exc

    def check(self):
        if not self.user_id:raise AccessError("Entre novamente.")
        try:
            session=self.client.auth.get_session()
            if not session:raise AccessError("Sessão encerrada.")
            if session.expires_at is not None and session.expires_at<time.time()+60:self.client.auth.refresh_session()
            self.client.rpc("heartbeat_license").execute()
        except Exception as exc:raise AccessError("Sua sessão ou licença perdeu a autorização. Entre novamente.") from exc

    def logout(self):
        try:self.client.rpc("release_license").execute()
        finally:
            self.client.auth.sign_out({"scope":"local"});self.user_id=None

    def list(self,kind):
        self.check()
        # Pagination: no silent 1,000-row PostgREST truncation.
        rows=[];offset=0
        while True:
            batch=self.client.table("records").select("*").eq("kind",kind).order("created_at").range(offset,offset+499).execute().data
            rows.extend(batch)
            if len(batch)<500:return rows
            offset+=500

    def put(self,kind,payload,record_id=None):
        self.check()
        row={"id":record_id or str(uuid4()),"user_id":self.user_id,"kind":kind,"payload":payload}
        return self.client.table("records").upsert(row,on_conflict="id").execute().data[0]

    def reserve_ai(self):
        self.check()
        # Limit is set by SQL/admin; the client parameter cannot elevate it.
        self.client.rpc("reserve_ai_call").execute()
