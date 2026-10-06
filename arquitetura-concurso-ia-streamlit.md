# Concurso IA — Base modular Streamlit + Supabase + Gemini

Implementação inicial dos dez módulos solicitados. O código integra navegação, edital ativo, dados por aluno, licença, geração estruturada por IA e PDFs. **É uma base de desenvolvimento, não uma versão comercial validada.** Não foram configuradas contas externas nem executadas chamadas reais à IA/Supabase nesta entrega.

## Estrutura

```text
concurso-ia-streamlit/
  app.py                       configuração, login, licença e roteamento
  requirements.txt
  secrets.toml.example
  .streamlit/config.toml
  core/
    models.py                  contratos de IA e validações
    guide_schema.py            contrato do guia
    study.py                   plano, seleção, pontuação e deduplicação
  services/
    database.py                Supabase Auth, RPCs e persistência
    ai.py                      Gemini texto/visão e verificação de questões
    extraction.py              extração textual do PDF
    guide_pdf.py               guia visual com cartões e tabelas
    documents.py               apostilas e simulado em duas colunas
  ui/
    common.py                  contexto do edital e operações comuns
    edital.py                  upload e guia resumido
    plan.py                    disponibilidade e cronograma
    materials.py               apostilas por disciplina
    simulations.py             configuração, cronômetro, PDF e histórico
    board.py                   evidências e hipóteses sobre a banca
    questions.py               geração verificada e prática
    performance.py             gráficos e histórico
    essays.py                  tema, fotos, transcrição e correção
  sql/
    001_schema.sql             tabelas, RLS, licença e cotas atômicas
    002_issue_license_example.sql
  assets/                      fontes DejaVu e licença
  tests/                       testes sem chamadas externas
```

## Arquitetura

Streamlit serve a interface e executa o backend Python. O navegador não recebe a chave Gemini ou service_role. Cada sessão Streamlit possui seu próprio cliente Supabase autenticado; ele não usa cache global. O Supabase Auth gerencia senhas e sessões. O Postgres valida licença e acesso por Row Level Security, usando o ID do aluno e da sessão JWT.

O edital processado alimenta o guia, disciplinas, recomendações de quantidade, plano, contexto da banca e rubrica de redação. Conteúdo gerado é persistido como JSON no Supabase e associado ao edital, evitando misturar históricos de concursos. Os documentos PDF são reconstruídos a partir desse conteúdo. Fotos e arquivos originais não são armazenados nesta base.

### Dados e licença

- `licenses`: hash SHA-256 da chave aleatória, proprietário definido pelo administrador, habilitação, validade opcional, sessão ativa, prazo da reserva e cota diária.
- `ai_usage`: contador diário UTC por aluno. A reserva da chamada é atômica no banco e não pode exceder o limite definido pelo administrador.
- `records`: registros separados por usuário e tipo (edital, plano, apostila, banca, questão, simulado, tentativa e redação). JSON de até 4 MB por registro; consultas paginadas.
- `auth.users`: contas gerenciadas pelo Supabase; senhas não são salvas nas tabelas do aplicativo.

A função `acquire_license` bloqueia a linha da licença antes de conceder acesso, impedindo duas autenticações de adquirir a mesma licença simultaneamente. A licença é vinculada previamente ao usuário; outra conta não pode reivindicá-la. `heartbeat_license` renova por dois minutos, a cada 30 segundos no app e antes das operações. `release_license` libera ao sair. Uma sessão abandonada fica disponível depois do prazo. A RLS exige licença válida e a sessão JWT correspondente mesmo para acessos diretos ao banco.

Isso controla sessões de autenticação distintas, não constitui DRM inviolável. Reutilização do mesmo token roubado não é detectada como um dispositivo diferente. Um PDF já baixado não pode ser revogado. A validação SQL e testes reais de concorrência/isolamento são obrigatórios antes da venda.

## Configuração local

Use Python 3.11 ou 3.12:

```bash
python -m venv .venv
# Windows: .venv\Scripts\activate
# Linux/macOS: source .venv/bin/activate
python -m pip install -r requirements.txt
python -m streamlit run app.py
```

No Windows pode usar `py` no lugar de `python`. Sem Secrets, o aplicativo mostra orientação de configuração e não libera o paywall.

## Supabase

1. Crie um projeto e execute `sql/001_schema.sql` uma vez no SQL Editor. O script cria as tabelas e funções; não é uma migração idempotente para rodar repetidamente.
2. Em Authentication, crie o usuário com e-mail e senha. Configure a confirmação de e-mail conforme seu fluxo. Nesta base não há cadastro aberto, checkout ou recuperação de senha implementados.
3. Em `002_issue_license_example.sql`, substitua **as duas ocorrências** do UUID de exemplo pelo ID do usuário criado. Execute no SQL Editor como administrador. A chave retornada deve ser entregue ao aluno de forma privada; o banco guarda apenas o hash.
4. Copie URL e chave publishable/anon para Secrets. **Não use service_role.** O SQL revoga leitura/escrita direta de licenças e cotas pelo aluno.
5. Para suspender uma licença, o administrador atualiza `enabled=false`. Para definir vencimento/cota, atualiza `expires_at`/`daily_ai_limit` no Supabase. Não há painel administrativo no app nesta etapa.

Exemplo de ação administrativa, com UUID real:

```sql
update public.licenses
set enabled = false
where user_id = 'UUID-DO-USUARIO';
```

## Secrets e Gemini

Localmente, copie `secrets.toml.example` para `.streamlit/secrets.toml` e preencha. Esse arquivo está no `.gitignore`. Na hospedagem, copie os campos para Advanced settings → Secrets.

O pedido original citou Gemini 1.5 Flash, desligado em 29/09/2025. Usamos o SDK atual `google-genai` e modelo configurável, padrão `gemini-3.5-flash-lite`, listado com faixa gratuita na consulta feita para este projeto. Confirme disponibilidade, contexto, visão e saída estruturada no projeto ao configurar sua chave. Não existe fallback para outro modelo.

Gratuidade depende das cotas e condições dos provedores. Use projeto sem faturamento se desejar permanecer na faixa gratuita. O aplicativo não detecta se o projeto está com cobrança habilitada. A cota `daily_ai_limit` é de operações, não de dinheiro: uma chamada reservada inclui contagem de contexto e tentativa de geração; falhas consomem a reserva. A autoridade para alterar a cota é o administrador da licença no SQL.

Gerações são síncronas, sem repetição automática. Documentos acima do contexto ou respostas truncadas são rejeitados. Saída estruturada usa JSON schema e Pydantic; isso não garante verdade factual. Dados da faixa gratuita do Google podem ser usados para melhoria dos produtos. Use apenas documentos públicos e obtenha autorização para redações/fotos.

## Fluxos implementados

1. **Conta/licença:** login e-mail/senha/chave, RPC atômico, renovação e saída. Usuários e licenças são provisionados pelo administrador.
2. **Edital:** upload textual de até 20 MB/600 páginas/900 mil caracteres, filtro opcional de cargo, extração Gemini e persistência estruturada. Sem OCR; páginas sem texto interrompem análise.
3. **Guia:** PDF pesquisável com cartões, cronograma, fases e matérias. Paginação automática; não força duas páginas nem omite disciplinas para caber.
4. **Plano:** minutos por dia da semana, data de prova opcional, distribuição de blocos de até 50 minutos, adaptação ao histórico de exercícios e horizonte de até 90 dias. Não cria sessões com disponibilidade zero.
5. **Apostilas:** geração por matéria, teoria/exemplo/alerta e diagramas vetoriais ilustrativos. Não gera imagens artísticas. Conteúdo jurídico exige conferência externa e atualização.
6. **Simulados:** seleção por dificuldade, recomendação de contagem somente quando inequívoca no edital, quantidades editáveis e sem limite comercial de gerações. Banco insuficiente reutiliza questões com aviso. Snapshot fixa perguntas e ordem, respostas persistem, cronômetro usa prazo UTC e finalização salva resultado. PDF em duas colunas + gabarito comentado separado.
7. **Banca:** até cinco provas opcionais em PDF; relatório separa evidência e hipótese. Sem provas, análise preliminar baseada no edital. Não realiza busca na internet.
8. **Questões:** lotes de até dez, quatro alternativas, deduplicação e segunda resolução independente. Salva somente gabaritos confirmados. Treino por matéria/assunto/nível e explicação; conteúdo identificado como IA.
9. **Desempenho:** gráficos por matéria, histórico de simulados e tabela de notas de redação. Sem dados, não inventa estatísticas.
10. **Redação:** tema gerado ou informado pelo aluno, até cinco fotos, transcrição preservando erros, conferência manual, rubrica numérica extraída do edital ou genérica explicitamente identificada. Nota validada contra máximos e correção salva; fotos não são persistidas.

## Publicar no Streamlit Community Cloud

Envie todos os arquivos ao GitHub, sem Secrets. Em https://share.streamlit.io/ escolha o repositório/branch e `app.py` como entrada (ou `concurso-ia-streamlit/app.py` se manteve essa pasta). Selecione Python 3.11/3.12, adicione os Secrets e publique. Supabase e Gemini devem estar configurados primeiro.

Não houve deploy nesta entrega. Hospedagem gratuita não fornece capacidade infinita, worker permanente ou armazenamento local durável.

## Testes e próximos passos obrigatórios

```bash
python -m pip install -r requirements-dev.txt
python -m unittest discover -s tests -v
```

Foram executados 15 testes locais com sucesso: regras, contratos, seleção/snapshot, PDF, notas, autenticação simulada, renovação/paginação e navegação com repositório simulado. O SQL recebe verificação sintática, mas não foi executado em um projeto Supabase real. A qualidade da IA e o acesso externo não foram testados com credenciais reais.

Antes do piloto, execute testes de duas contas isoladas, duas autenticações simultâneas, expiração/revogação, refresh JWT, falha de rede, cota concorrente e recuperação de simulados. Confira editais reais com vários cargos, apostilas, gabaritos e manuscritos. Corrija eventuais incompatibilidades do fornecedor/modelo antes de disponibilizar para alunos.

Limitações adicionais: sem checkout, e-mail de recuperação completo, painel admin, exclusão/exportação integral da conta, backup/restauração configurados, versões de retificações, OCR, prova certo/errado, penalidade por erro, pesos oficiais na pontuação ou revisão pedagógica humana. Dados JSON guardados pelo próprio aluno podem ser alterados por ele: este não é um ambiente de avaliação certificada. Novas questões são geradas a pedido; banco autônomo em worker/filas permanece etapa futura. Grandes simulados podem ultrapassar memória/limite JSON e precisam de paginação e tabelas normalizadas. O cronômetro é apoio de treino, não fiscalização de prova.

## Referências oficiais

- https://supabase.com/docs/reference/python/auth-signinwithpassword
- https://supabase.com/docs/guides/database/postgres/row-level-security
- https://ai.google.dev/gemini-api/docs/libraries
- https://ai.google.dev/gemini-api/docs/structured-output
- https://ai.google.dev/gemini-api/docs/pricing
- https://ai.google.dev/gemini-api/docs/changelog
- https://docs.streamlit.io/deploy/streamlit-community-cloud/deploy-your-app/secrets-management
