# Carga pública regional

## Executar

Requer Python 3.11+, curl, Node e Wrangler autenticado. Não depende de API paga.

```sh
python scripts/receita.py --uf PA --city Parauapebas --radius 100
python scripts/publish-catalog.py data/receita/catalog-ID
```

Para executar a carga inteira e publicar somente após a validação: `python scripts/receita.py --uf PA --city Parauapebas --radius 100 --publish`. O computador deve permanecer ligado até terminar. A execução para se ocorrer erro; reexecute o mesmo comando para retomar. O modo de publicação usa a autenticação local do Wrangler, sem guardar tokens no projeto.

O primeiro comando informa o caminho `CATALOG_READY` ao terminar. Use esse caminho no segundo. Para validar publicação sem produção, acrescente `--local` ao segundo comando. Rode a partir da raiz do repositório. Não execute duas publicações ao mesmo tempo.

O coletor descobre a última competência no compartilhamento público da Receita, verifica a presença de todos os dez ZIPs de Estabelecimentos e dez de Empresas, baixa e cruza Municípios/CNAEs. `--month YYYY-MM` fixa a competência. Setembro de 2026 tem aproximadamente 6,76 GB compactados para esses arquivos. Tempo de download depende da Receita e da conexão; mantenha espaço em disco para os ZIPs e o recorte SQLite.

Downloads usam curl com retomada e checagem de tamanho. Reexecutar o mesmo comando retoma os arquivos e pula as partes já processadas. Uma parte só é marcada concluída depois que a leitura de seu ZIP e a transação local terminam. CSVs são processados em fluxo, no formato Latin-1 com separador ponto e vírgula. CNPJ permanece texto, incluindo zeros iniciais. CNPJs com letras são aceitos pelo validador; qualquer mudança de quantidade de colunas interrompe a carga.

Somente estabelecimentos ativos da UF e das cidades selecionadas entram no SQLite regional. A junção com Empresas preserva nome fantasia quando disponível e usa razão social caso contrário. Telefones ausentes permanecem vazios. Não são coletados sócios nem CPFs. Os contatos não aparecem nos logs e `data/` não é versionado.

## Precisão geográfica e cobertura

A Receita não fornece latitude/longitude por estabelecimento. Esta carga usa a localização da **sede municipal** para selecionar municípios no raio, dentro da UF escolhida. Não é distância do endereço da empresa nem distância rodoviária. A interface informa essa aproximação. Empresas da zona rural podem estar mais perto ou mais longe do que a sede sugere. Geocodificação individual ainda é necessária para raio preciso por endereço.

Coordenadas municipais: [Municípios Brasileiros, licença MIT](https://github.com/kelvins/municipios-brasileiros). O vínculo com a Receita usa código SIAFI, evitando divergências de grafia. O manifesto registra URL e hash do arquivo geográfico. A carga inicial de 100 km de Parauapebas cobre quatro cidades: Parauapebas, Canaã dos Carajás, Curionópolis e Eldorado dos Carajás. Consultas fora desse recorte não encontram uma base nacional: amplie a carga explicitamente conforme necessário.

## Publicação e atualização

O exportador produz SQL em lotes de mil empresas e um manifesto com competência, cobertura, contagens e hashes. O publicador valida os arquivos, carrega tabelas temporárias e confere as contagens no D1 antes de promover os dados. A versão anterior permanece nas tabelas `companies_previous` e `cities_previous`. A publicação seguinte substitui esse backup. Uma falha durante o carregamento temporário mantém a base ativa intacta. A promoção é um único arquivo SQL enviado ao importador do D1; confirme a mensagem de verificação final antes de considerar a carga concluída.

Cada publicação substitui **todo o catálogo regional**, removendo do catálogo as empresas que não constam no novo recorte ou deixaram de estar ativas. Os leads no Firestore são preservados. Para atualizar, execute os dois comandos novamente com uma nova competência. Nenhuma atualização periódica é ativada automaticamente.

Fontes: [compartilhamento público da Receita](https://arquivos.receitafederal.gov.br/index.php/s/YggdBLfdninEJX9), [layout oficial](https://www.gov.br/receitafederal/dados/cnpj-metadados.pdf/@@download/file), [importação D1](https://developers.cloudflare.com/d1/best-practices/import-export-data/).

Testes do coletor: `python -m unittest discover -s tests -p "test_*.py"`.
