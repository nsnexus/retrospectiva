"""Publica um catálogo validado no D1, mantendo a base anterior até a promoção.
Uso: python scripts/publish-catalog.py data/receita/catalog-ID [--local]
Exige npx/wrangler autenticado. Não executa SQL arbitrário fora do manifesto.
"""
import argparse
import hashlib
import json
import os
import shutil
import subprocess
from pathlib import Path

def publish(folder, local=False):
    root=Path(folder).resolve()
    manifest=json.loads((root/'manifest.json').read_text(encoding='utf-8'))
    if not isinstance(manifest['count'],int) or manifest['count']<=0:
        raise ValueError('Catálogo vazio')
    for name,digest in manifest['files'].items():
        if Path(name).name!=name or not name.endswith('.sql'):
            raise ValueError('Nome de arquivo inválido')
        if hashlib.sha256((root/name).read_bytes()).hexdigest()!=digest:
            raise ValueError('Arquivo alterado: '+name)
    npx=shutil.which('npx')
    if not npx: raise RuntimeError('Instale Node.js e npm')
    def execute(*args):
        cmd=[npx,'wrangler','d1','execute','prospeccao-catalogo','--local' if local else '--remote','--yes','--json',*args]
        result=subprocess.run(cmd,capture_output=True,text=True,encoding='utf-8',env={**os.environ,'WRANGLER_SEND_METRICS':'false'})
        if result.returncode:
            raise RuntimeError(result.stderr or 'Falha no Wrangler; catálogo não promovido')
        return json.loads(result.stdout)
    execute('--file','migrations/0001_catalog.sql')
    for name in sorted(manifest['files']):
        print('Publicando '+name,flush=True)
        execute('--file',str(root/name))
    stats=execute('--command','SELECT COUNT(*) AS count, COUNT(DISTINCT cnpj) AS unique_count FROM companies_import;')[0]['results'][0]
    if stats['count']!=manifest['count'] or stats['unique_count']!=manifest['count']:
        raise ValueError('Contagem no D1 diverge do manifesto; base anterior preservada')
    stats=execute('--command','SELECT COUNT(*) AS count FROM cities_import;')[0]['results'][0]
    if stats['count']!=manifest['cities']:
        raise ValueError('Contagem de cidades diverge; base anterior preservada')
    # Backups are retained. A subsequent run deliberately replaces only these backup tables.
    promotion=root/'promote.sql'
    promotion.write_text('''DROP TABLE IF EXISTS companies_previous;
DROP TABLE IF EXISTS cities_previous;
ALTER TABLE companies RENAME TO companies_previous;
ALTER TABLE cities RENAME TO cities_previous;
ALTER TABLE companies_import RENAME TO companies;
ALTER TABLE cities_import RENAME TO cities;
DROP INDEX IF EXISTS companies_geo;
DROP INDEX IF EXISTS companies_cnae;
DROP INDEX IF EXISTS companies_opened;
DROP INDEX IF EXISTS companies_cnpj;
DROP INDEX IF EXISTS cities_key;
CREATE UNIQUE INDEX companies_cnpj ON companies(cnpj);
CREATE INDEX companies_geo ON companies(lat,lng);
CREATE INDEX companies_cnae ON companies(cnae);
CREATE INDEX companies_opened ON companies(opened);
CREATE UNIQUE INDEX cities_key ON cities(normalized,state);
''',encoding='utf-8')
    execute('--file',str(promotion))
    results=execute('--command','SELECT COUNT(*) AS count FROM companies;')[0]['results'][0]
    if results['count']!=manifest['count']: raise RuntimeError('Verificação após publicação falhou')
    print(f"Publicado e verificado: {manifest['count']} empresas, {manifest['cities']} cidades, competência {manifest['month']}.")

if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('folder')
    parser.add_argument('--local',action='store_true')
    args=parser.parse_args()
    publish(args.folder,args.local)
