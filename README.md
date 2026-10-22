# Aurora Finanças — versão 0.2.0

App experimental para Android, iPhone e web. Esta etapa adiciona cartões, compras parceladas, faturas e um servidor com login e sincronização manual. Não inclui conexão ao MeuPluggy nem IA externa. O nome Aurora é provisório.

## O que funciona
- Todos os recursos locais anteriores: contas, receitas, despesas, transferências, busca, metas, gráficos e chat local determinístico.
- Nova aba Cartões: cadastro de limite, fechamento e vencimento; compras de 1 a 48 parcelas; faturas e pagamentos parciais.
- API Python + SQLite: cadastro/login, senhas com scrypt e salt, tokens aleatórios com hash no banco e expiração em 24 horas, logout, isolamento por usuário e controle de revisão.
- Ajustes: formulário de servidor e login; botões para baixar e enviar os dados. A sincronização é MANUAL e transfere uma cópia completa. Não é atualização em tempo real ou mesclagem automática.
- Compatibilidade com dados locais v0.1: novas coleções de cartões/compras são opcionais ao abrir registros antigos.

## Testar o app
Node.js compatível com Expo SDK 54 (20.19+); Python 3.10+ para servidor.

```bash
npm ci
npm test
npm run web
```

Na aba Ajustes é possível carregar dados fictícios com confirmação. Os dados reais dos vídeos não estão incluídos.

Para prévia já compilada:

```bash
python3 -m http.server 8080 --directory dist-web
```
Abra http://localhost:8080. A prévia compilada aceita apenas servidor HTTPS. Para desenvolvimento com HTTP use `npm run web`, que inicia o app em modo de desenvolvimento.

## Iniciar o backend local
Em outro terminal, na pasta do projeto:

```bash
python3 server/server.py
```

Endereço padrão: http://localhost:8787. No app web em desenvolvimento, abra Ajustes e informe esse endereço; cadastre email e senha de pelo menos 12 caracteres. O cadastro não verifica email nesta versão.

Para testar em celular na mesma rede:

```bash
AURORA_HOST=0.0.0.0 python3 server/server.py
npm start
```

Use `http://IP-DO-SEU-PC:8787` no celular em modo de desenvolvimento (localhost no celular é o próprio celular). Não exponha essa porta à internet. Políticas de rede do sistema/build podem exigir HTTPS mesmo em testes.

Para sincronizar entre dois dispositivos:
1. No primeiro, cadastre um login no servidor.
2. Clique em “Conferir / baixar dados do servidor” e confirme. Servidor vazio não apaga os registros locais.
3. Envie os dados deste aparelho.
4. No segundo, faça login no mesmo servidor e baixe os dados, confirmando a substituição dos locais.
5. Após editar, envie. Se outro aparelho já enviou mudanças, o servidor rejeita a revisão antiga com HTTP 409. Exporte uma cópia local antes de baixar: nesta versão não há ferramenta para mesclar divergências.

Sessões ficam em memória, não no armazenamento persistente. Fechar o aplicativo exige novo login. Sair não apaga dados locais: em aparelho compartilhado, limpe-os explicitamente. Não publique este servidor de desenvolvimento como serviço de produção.

## Regras financeiras
- Valores em centavos inteiros; parcelas distribuem o resto de centavos nas primeiras parcelas.
- Compra de cartão entra como despesa pelo valor TOTAL na data da compra. Parcelas são calendário de obrigações, não novas despesas.
- Pagamento de fatura reduz saldo da conta e dívida do cartão; não aumenta despesas novamente. Aceita pagamento parcial e rejeita valor acima do restante.
- Limite disponível = limite cadastrado menos todas as parcelas ainda não pagas. Sem limite separado para compras parceladas.
- Fatura identificada pelo mês de fechamento. Compra no dia do fechamento entra na fatura seguinte, uma convenção simplificada que pode divergir do processamento do banco.
- Vencimento no mesmo mês do fechamento se seu dia for maior; no mês seguinte em caso contrário. Dias 1–28 nesta etapa.
- Pagamento de fatura pode ser excluído no histórico; os saldos são recalculados. Compras/cartões ainda não têm edição/exclusão na interface.
- Sem juros, encargos, estornos, renegociação ou ajustes manuais de fatura.
- Saldo total inclui reservas, sem descontar dívida de cartão; não é patrimônio líquido nem valor livre para gastar.
- O chat inclui gastos no cartão nos totais; permanece um assistente local, sem modelo externo.
- Ocultar valores cobre painel e histórico. Cartões e chat avisam que mostram valores.

## API e armazenamento
- `POST /auth/register` e `POST /auth/login`: `{email,password}` → `{token,email}`.
- `POST /auth/logout`: revoga o token enviado em `Authorization: Bearer ...`.
- `GET /state`: retorna `{revision,state}` do usuário autenticado.
- `PUT /state`: recebe `{revision,state}`; exige a última revisão, retorna nova revisão ou 409.
- `GET /health`: estado básico do processo.
- SQLite em server/aurora.sqlite3, criado ao iniciar; não está incluído no pacote.
- Configuração: AURORA_HOST, AURORA_PORT, AURORA_DB, AURORA_ORIGINS (origens web separadas por vírgula). CORS usa lista explícita. Limite de corpo: 2 MB; limite de autenticação: 10 tentativas/minuto/IP em memória.
- A API valida formato e referências básicas. Não é um livro contábil autoritativo: aceita snapshots do usuário, e o cliente aplica regras de negócio.

## Antes de hospedar para uso real
Usar servidor HTTP adequado para produção e HTTPS, persistência/backup e permissões do SQLite, verificação de email, recuperação de senha, limitação de requisições persistente, proteção dos dados locais e monitoramento. O servidor Python padrão desta entrega serve para desenvolvimento. Nenhum servidor foi hospedado e nenhuma conta externa foi criada.

## Android e iPhone
O mesmo código usa Expo SDK 54 / React Native 0.81.5. Em desenvolvimento:

```bash
npm run android
# Requer Android Studio/SDK.
npm run ios
# Requer macOS/Xcode e assinatura adequada.
```

Expo Go precisa ser compatível com SDK 54; caso contrário, usar development build. No Linux, iOS requer build remoto ou um Mac. Não há APK/IPA assinado neste pacote.

## Testes
```bash
npm test
python3 -m unittest discover -s server -p 'test_*.py'
```
Nove testes financeiros e um teste de integração da API com múltiplas verificações: autenticação, isolamento, persistência, conflito de revisão, payload inválido e revogação de sessão. Exportação web/Android/iOS verificada; testes visuais e em dispositivos físicos permanecem pendentes.

## Próximas etapas
- Validar navegação, formulários e conexão em Android/iPhone.
- Importação CSV com prévia e deduplicação; restauração de backup.
- Evoluir sincronização para operações incrementais.
- Validar acesso ao MeuPluggy e implementar adaptador no backend, sem credenciais no app.
- IA externa e agentes após a base de dados e autenticação amadurecerem.
