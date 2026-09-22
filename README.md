# NSNexus • Prospecção empresarial

Aplicação React/Vite + TypeScript, Firebase Auth/Firestore e Cloudflare Pages Functions/D1. O repositório remoto estava vazio na inspeção inicial.

## Executar

Requer Node.js 22.12+ e npm. Execute `npm ci`, copie `.env.example` para `.env.local` e rode `npm run dev`. A demonstração usa empresas **fictícias**, sem telefones reais, e salva leads no navegador. Procure por construção, instalações elétricas ou CNAE 4321500 em Parauapebas/PA, raio 100 km. Não use o modo demo para guardar dados reais.

`npm run build` verifica TypeScript e gera `dist`. `npm test` executa os testes. `npm run preview` serve apenas o frontend compilado; a API requer o ambiente Pages.

## Funcionalidades

- Busca por ramo textual/CNAE, cidade + UF, raio de 1 a 500 km e período de abertura.
- Catálogo importado somente com empresas ativas e coordenadas. Distância em linha reta a partir do centro do município, não percurso rodoviário.
- Até 100 resultados por consulta, com aviso para refinar filtros quando houver mais.
- Ficha com CNPJ, endereço, contato e abertura. Salvar ficha cadastra lead; CNPJ é a chave para evitar duplicatas.
- Status comercial, observações, último contato e próxima tentativa; indicadores de pendências.
- Link de WhatsApp para telefone com formato brasileiro válido. O cadastro não comprova que o número possui WhatsApp.
- Exportação CSV da carteira filtrada, com proteção contra fórmulas de planilha.
- Login e recuperação de senha. Cada usuário possui sua própria carteira; não há compartilhamento de equipe nesta versão.

## Firebase

1. Crie um projeto, registre um aplicativo Web e habilite Authentication → E-mail/senha.
2. Crie as contas autorizadas pelo console Authentication. A aplicação não oferece cadastro público.
3. Crie o Firestore em modo produção e escolha a região conforme sua operação.
4. Configure `VITE_FIREBASE_API_KEY`, `VITE_FIREBASE_AUTH_DOMAIN`, `VITE_FIREBASE_PROJECT_ID`, `VITE_FIREBASE_APP_ID`; defina `VITE_DEMO_MODE=false`.
5. Instale a CLI Firebase e execute `firebase login`, depois `firebase deploy --only firestore --project SEU_PROJECT_ID`.
6. Em Authentication → Settings → Authorized domains, adicione seu domínio Cloudflare e domínio próprio. Configure o e-mail de recuperação.

As regras permitem apenas ao usuário autenticado ler/gravar em `users/{uid}/leads/{cnpj}`, validam campos e negam todos os outros caminhos. Chaves públicas de configuração Firebase ficam no frontend; credenciais de serviço nunca devem usar prefixo `VITE_`. Dados dos leads não são sincronizados antes do login. As regras devem ser publicadas antes de liberar acesso.

## Cloudflare Pages

O `wrangler.toml` já contém a configuração pública Web do Firebase `leeds-316cc` nas variáveis `VITE_*`, com demonstração desativada. Esses identificadores são incorporados ao frontend e não são credenciais administrativas. Para este projeto, mantenha esses valores no deploy; ao usar outro Firebase, atualize todas as variáveis correspondentes. Os arquivos `.env.local` e `.dev.vars` continuam fora do Git.

1. Crie D1 com `npx wrangler d1 create prospeccao-catalogo` e coloque o ID retornado em `wrangler.toml`.
2. Substitua `FIREBASE_PROJECT_ID` no mesmo arquivo. A API valida assinatura, validade, emissor e audiência do token Firebase.
3. Aplique `npx wrangler d1 migrations apply prospeccao-catalogo --remote`.
4. Importe o catálogo regional conforme a seção seguinte.
5. Conecte o repositório ao Cloudflare Pages: comando `npm run build`, saída `dist`, raiz do projeto `/`, Node 22.12+.
6. Cadastre as variáveis `VITE_*` no ambiente de build com demo **false**. Verifique binding D1 `DB` e variável `FIREBASE_PROJECT_ID` para Functions em produção e preview.
7. Para publicar pela CLI: `npm run build` e `npx wrangler pages deploy dist`. Para execução local completa: configure `.dev.vars` com `FIREBASE_PROJECT_ID=...`, aplique migrations e importação com `--local`, compile e rode `npx wrangler pages dev dist`.

Vite sozinho não executa `/api/companies`. A ausência de Firebase ou catálogo gera erro explícito; produção nunca muda automaticamente para dados fictícios. Configure limites de requisições no Cloudflare conforme o volume e acompanhe custos de D1/Firestore.

Referências: [Cloudflare: configuração de build](https://developers.cloudflare.com/pages/configuration/build-configuration/) e [Firebase: regras por usuário](https://firebase.google.com/docs/rules/rules-and-auth).

## Catálogo de CNPJ: separado do Firestore

```text
Arquivos públicos → armazenamento bruto externo → ETL/junções + geocodificação
   → recorte regional normalizado → D1 → Pages API autenticada → busca
   → somente empresas selecionadas → Firestore (carteira de cada usuário)
```

A base nacional **não** vai para Firestore nem para o bundle frontend. D1 é adequado ao recorte regional inicial, não se propõe armazenar toda a base nacional. Para expansão, substitua a consulta da Function por um serviço PostgreSQL/PostGIS e mantenha o contrato `GET /api/companies`. Use armazenamento de objetos para arquivos brutos e processamento em lotes fora das Functions.

O importador incluído recebe **JSONL normalizado**, não ZIP/CSV bruto da Receita. A etapa de baixar, unir estabelecimentos/empresas/CNAEs/municípios e geocodificar endereços ainda precisa ser conectada a uma fonte de dados. Não invente coordenadas: mantenha registros sem geocodificação em quarentena; coordenadas de centroides para empresas reduzem a precisão do raio. Registre fonte, competência e precisão no processo externo. O ramo é busca textual na descrição oficial; não há conversão automática por IA de sinônimos para CNAEs.

Cada linha deve conter:

```json
{"cnpj":"12345678000100","name":"EMPRESA EXEMPLO","cnae":"4321500","sector":"Instalações elétricas","secondaryCnaes":[],"city":"Parauapebas","state":"PA","address":"Endereço normalizado","phone":"","email":"","opened":"2025-01-15","lat":-6.0675,"lng":-49.9022,"cityLat":-6.0675,"cityLng":-49.9022,"active":true}
```

Esse registro é apenas exemplo de formato. Preserve CNPJ como texto, inclusive zeros iniciais e formato alfanumérico. Telefone/e-mail podem ser vazios. `cityLat/cityLng` são o centro municipal consistente entre registros; `lat/lng` são as coordenadas do estabelecimento.

Execute `node scripts/import-catalog.mjs data/catalogo.jsonl data/catalogo.sql PA`, depois `npx wrangler d1 execute prospeccao-catalogo --remote --file=data/catalogo.sql`. O importador filtra UF e empresas ativas, valida campos e escreve em fluxo, sem carregar o arquivo inteiro na memória. Divida grandes saídas conforme os limites do provedor. Em caso de erro descarte a saída parcial, corrija a entrada e gere outro arquivo. Não versione catálogos ou contatos reais.

Para atualização de competência, carregue uma **nova base regional** e troque o binding após validar contagens e amostras. O upsert não remove empresas que encerraram atividades: não trate importações incrementais como substituição completa. Os leads existentes preservam a ficha capturada; não são sobrescritos pela importação.

## Validação antes de produção

Execute build/testes, publique regras e valide com duas contas: uma não deve acessar a carteira da outra. Confira login, recuperação, salvar/reabrir lead, exportação e busca com catálogo real. Teste raio e período com coordenadas conhecidas. Sem credenciais e importação, a demonstração funciona, mas não há consulta de empresas reais.
