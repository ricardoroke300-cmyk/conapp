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
    database.py                licenças por e-mail, RPCs e persistência
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
    003_migrate_email_license.sql migração do banco anterior
  assets/                      fontes DejaVu e licença
  tests/                       testes sem chamadas externas
```

## Arquitetura

Streamlit serve a interface e executa o backend Python. O navegador não recebe a chave Gemini ou service_role. O login pede somente E-mail e Chave de Licença. Não há chamada ao Supabase Auth nem criação de senha. Cada sessão Streamlit guarda seu cliente e um token opaco de licença, sem cache global. O banco valida e-mail, hash da chave, validade e reserva de sessão. As tabelas têm RLS e nenhum acesso direto é concedido às roles anon/authenticated; operações usam somente RPCs com validação do token e separação por proprietário.

O edital processado alimenta o guia, disciplinas, recomendações de quantidade, plano, contexto da banca e rubrica de redação. Conteúdo gerado é persistido como JSON no Supabase e associado ao edital, evitando misturar históricos de concursos. Os documentos PDF são reconstruídos a partir desse conteúdo. Fotos e arquivos originais não são armazenados nesta base.

### Dados e licença

- `licenses`: hash SHA-256 da chave aleatória, proprietário definido pelo administrador, habilitação, validade opcional, sessão ativa, prazo da reserva e cota diária.
- `ai_usage`: contador diário UTC por aluno. A reserva da chamada é atômica no banco e não pode exceder o limite definido pelo administrador.
- `records`: registros separados por usuário e tipo (edital, plano, apostila, banca, questão, simulado, tentativa e redação). JSON de até 4 MB por registro; consultas paginadas.
- O identificador do aluno é um UUID interno da licença. Não depende de auth.users. E-mail e chave são os únicos dados de entrada do login; a chave funciona como credencial secreta.

A função `license_login` bloqueia a linha da licença antes de emitir um token aleatório de 256 bits. O banco guarda somente o hash desse token. O e-mail deve corresponder à licença emitida pelo administrador. A reserva é renovada por dois minutos a cada 30 segundos e antes das operações; outro login é bloqueado enquanto ela estiver ativa. O token tem prazo máximo de oito horas. Ao sair, o hash é invalidado; ao adquirir uma nova sessão após abandono, o token anterior perde autorização.

As RPCs de listagem e escrita recebem o token, resolvem o proprietário no servidor e não aceitam um user_id informado pelo cliente. A escrita não pode sobrescrever registros de outro aluno. A cota continua atômica e controlada pelo administrador. O helper de validação fica em schema privado sem permissão para clientes. Não é necessário service_role no aplicativo.

A chave da licença passa a ser a credencial principal: mantenha-a privada. O fluxo não verifica posse da caixa de e-mail. Reutilização de um token roubado não é detectada como dispositivo diferente. Não é DRM inviolável e um PDF baixado não pode ser revogado. A mudança SQL não foi aplicada a um banco externo nesta entrega; testes reais de isolamento e concorrência continuam necessários.

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

1. **Banco novo:** execute `sql/001_schema.sql` uma vez no SQL Editor. Não execute a migração 003.
2. **Banco já criado pela versão anterior com Supabase Auth:** execute somente `sql/003_migrate_email_license.sql` uma vez, antes de usar o novo código. Ele copia os e-mails dos antigos proprietários, preserva IDs, registros, validade, cotas e hashes das chaves e invalida sessões antigas. Não apaga usuários do Auth. Se algum proprietário não tiver e-mail válido, a transação é revertida para correção pelo administrador.
3. Para emitir uma nova licença, troque `aluno@example.com` pelo e-mail real em `002_issue_license_example.sql`. Execute como administrador e entregue a chave retornada de forma privada. Não é preciso criar usuário em Authentication. Não execute o exemplo sem substituir o e-mail.
4. Copie URL e chave publishable/anon para Secrets. **Não use service_role.** O aluno não tem acesso direto às tabelas.
5. Para suspender uma licença ou mudar cota/validade, o administrador altera `enabled`, `daily_ai_limit` ou `expires_at`. Não há painel administrativo nesta etapa.

Não basta trocar apenas app.py: o novo services/database.py e o SQL correspondente precisam acompanhar o login sem senha. Reinicie o Streamlit após atualizar para encerrar objetos de sessão da versão antiga.

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

1. **Conta/licença:** login e-mail/chave, sem senha ou Supabase Auth; RPC atômico, renovação e saída. Licenças são vinculadas ao e-mail pelo administrador.
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

Os 17 testes locais da versão sem senha passaram: regras, contratos, seleção/snapshot, PDF, notas, autenticação simulada, renovação/paginação e navegação com repositório simulado. O SQL recebe verificação sintática, mas não foi executado em um projeto Supabase real. A qualidade da IA e o acesso externo não foram testados com credenciais reais.

Antes do piloto, execute testes de dois alunos isolados, dois logins simultâneos, token antigo após nova sessão, expiração/revogação, falha de rede, cota concorrente e recuperação de simulados. Confira editais reais com vários cargos, apostilas, gabaritos e manuscritos. Corrija eventuais incompatibilidades do fornecedor/modelo antes de disponibilizar para alunos.

Limitações adicionais: sem checkout, e-mail de recuperação completo, painel admin, exclusão/exportação integral da conta, backup/restauração configurados, versões de retificações, OCR, prova certo/errado, penalidade por erro, pesos oficiais na pontuação ou revisão pedagógica humana. Dados JSON guardados pelo próprio aluno podem ser alterados por ele: este não é um ambiente de avaliação certificada. Novas questões são geradas a pedido; banco autônomo em worker/filas permanece etapa futura. Grandes simulados podem ultrapassar memória/limite JSON e precisam de paginação e tabelas normalizadas. O cronômetro é apoio de treino, não fiscalização de prova.

## Referências oficiais

- https://supabase.com/docs/reference/python/rpc
- https://supabase.com/docs/guides/database/postgres/row-level-security
- https://ai.google.dev/gemini-api/docs/libraries
- https://ai.google.dev/gemini-api/docs/structured-output
- https://ai.google.dev/gemini-api/docs/pricing
- https://ai.google.dev/gemini-api/docs/changelog
- https://docs.streamlit.io/deploy/streamlit-community-cloud/deploy-your-app/secrets-management
