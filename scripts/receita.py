"""Importação regional da Receita Federal. Python 3.11+, somente biblioteca padrão.

ZIPs permanecem em data/ para retomada. Nenhum contato é escrito nos logs.
"""
import argparse
import base64
import csv
import hashlib
import io
import json
import math
import re
import sqlite3
import shutil
import subprocess
import time
import unicodedata
import urllib.request
import xml.etree.ElementTree as ET
import zipfile
from pathlib import Path
from urllib.parse import unquote, urlparse
from datetime import date
from concurrent.futures import ThreadPoolExecutor

BASE = 'https://arquivos.receitafederal.gov.br/public.php/webdav/'
# Token de compartilhamento PUBLICO, publicado pela Receita. Não é uma credencial pessoal.
SHARE = 'YggdBLfdninEJX9'
GEO = 'https://raw.githubusercontent.com/kelvins/municipios-brasileiros/main/csv/municipios.csv'
FIELDS = 'cnpj,name,cnae,sector,city,state,address,phone,email,opened,lat,lng,search'

def norm(value):
    return ''.join(c for c in unicodedata.normalize('NFD', value) if not unicodedata.combining(c)).lower().strip()

def km(a, b):
    la, lo, lb, lob = map(math.radians, (*a, *b))
    h = math.sin((lb-la)/2)**2 + math.cos(la)*math.cos(lb)*math.sin((lob-lo)/2)**2
    return 12742 * math.asin(min(1, math.sqrt(h)))

def request(url, method='GET'):
    headers = {'User-Agent': 'NSNexus-Catalog/1.0'}
    if url.startswith(BASE):
        headers['Authorization'] = 'Basic ' + base64.b64encode((SHARE+':').encode()).decode()
    if method == 'PROPFIND':
        headers['Depth'] = '1'
    return urllib.request.urlopen(urllib.request.Request(url, headers=headers, method=method), timeout=60)

def listing(path=''):
    with request(BASE+path, 'PROPFIND') as res:
        root = ET.fromstring(res.read())
    items = {}
    for entry in root.findall('{DAV:}response'):
        href = entry.findtext('{DAV:}href') or ''
        name = unquote(urlparse(href).path.rstrip('/').split('/')[-1])
        size = entry.findtext('.//{DAV:}getcontentlength')
        items[name] = int(size) if size else 0
    return items

def download(url, target, size=0):
    if target.exists() and (not size or target.stat().st_size == size):
        return
    target.parent.mkdir(parents=True, exist_ok=True)
    part = target.with_suffix(target.suffix+'.part')
    # curl handles resumable multi-GB transfers and Windows DNS more reliably.
    if shutil.which('curl'):
        if size > 64*1024*1024:
            # Bounded HTTP ranges avoid restarting multi-GB downloads when the
            # public server closes a long response. Validate every range before append.
            piece=part.with_suffix('.range')
            headers=part.with_suffix('.headers')
            offset=part.stat().st_size if part.exists() else 0
            while offset<size:
                end=min(size-1,offset+16*1024*1024-1)
                cmd=['curl','--fail','--location','--retry','4','--retry-delay','3','--connect-timeout','30','--max-time','180','--range',f'{offset}-{end}','--dump-header',str(headers),'--output',str(piece),url]
                if url.startswith(BASE): cmd.extend(['--user',SHARE+':'])
                subprocess.run(cmd,check=True,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
                expected=f'content-range: bytes {offset}-{end}/{size}'
                if expected not in headers.read_text().lower() or piece.stat().st_size!=end-offset+1:
                    raise ValueError('Servidor não confirmou o intervalo solicitado')
                with part.open('ab') as output,piece.open('rb') as source:
                    shutil.copyfileobj(source,output)
                offset=end+1
                if offset//(128*1024*1024)!=(offset-piece.stat().st_size)//(128*1024*1024):
                    print(f'{target.name}: {offset/size:.0%}',flush=True)
            piece.unlink(missing_ok=True)
            headers.unlink(missing_ok=True)
            part.replace(target)
            return
        cmd=['curl','--fail','--location','--retry','4','--retry-delay','3','--connect-timeout','30','--speed-time','120','--speed-limit','1024','--continue-at','-','--output',str(part),url]
        if url.startswith(BASE): cmd.extend(['--user',SHARE+':'])
        subprocess.run(cmd,check=True,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
        if size and part.stat().st_size!=size: raise ValueError('Download incompleto: '+target.name)
        part.replace(target)
        return
    for attempt in range(3):
        try:
            with request(url) as res, part.open('wb') as output:
                total = 0
                while chunk := res.read(1024*1024):
                    output.write(chunk)
                    total += len(chunk)
            if size and total != size:
                raise ValueError(f'Tamanho inesperado: {target.name}')
            part.replace(target)
            return
        except Exception:
            if attempt == 2:
                raise
            time.sleep(2**attempt)

def rows(path):
    with zipfile.ZipFile(path) as archive:
        names = [n for n in archive.namelist() if not n.endswith('/')]
        if len(names) != 1:
            raise ValueError(f'ZIP deve conter um CSV: {path}')
        with archive.open(names[0]) as raw:
            yield from csv.reader(io.TextIOWrapper(raw, encoding='latin-1', newline=''), delimiter=';')

def opened(value):
    if not re.fullmatch(r'\d{8}', value):
        return ''
    try:
        return date(int(value[:4]), int(value[4:6]), int(value[6:])).isoformat()
    except ValueError:
        return ''

def establishment(r, cities, cnaes, uf):
    if len(r) != 30:
        raise ValueError(f'Layout de estabelecimentos mudou: {len(r)} colunas, esperado 30')
    if r[5] not in ('02', '2') or r[19] != uf or r[20] not in cities:
        return None
    c = cities[r[20]]
    cnpj = ''.join(r[:3])
    if not re.fullmatch(r'[A-Z0-9]{12}\d{2}', cnpj):
        raise ValueError('CNPJ fora do formato esperado')
    sector = cnaes.get(r[11], '')
    address = ' '.join(filter(None, r[13:18])) + (' CEP '+r[18] if r[18] else '')
    phone = (r[21]+r[22]) if r[22] else ((r[23]+r[24]) if r[24] else '')
    secondary = [cnaes.get(code, '') for code in r[12].split(',')]
    return (cnpj, r[4], r[11], sector, c['name'], uf, address, phone, r[27], opened(r[10]), c['lat'], c['lng'], norm(' '.join([r[4], r[11], sector, r[12], *secondary])))

def sql(value):
    if isinstance(value, (int, float)):
        return str(value)
    return "'" + str(value).replace("'", "''") + "'"

def run(args):
    root = Path(args.workdir)
    root.mkdir(parents=True, exist_ok=True)
    month = args.month
    if not month:
        months = sorted(m for m in listing() if re.fullmatch(r'\d{4}-\d{2}', m))
        if not months:
            raise ValueError('Nenhuma competência disponível na Receita')
        month = months[-1]
    if not re.fullmatch(r'\d{4}-\d{2}', month):
        raise ValueError('Competência deve ser YYYY-MM')
    files = listing(month+'/')
    required = ['Municipios.zip', 'Cnaes.zip'] + [f'{kind}{i}.zip' for kind in ('Estabelecimentos','Empresas') for i in range(10)]
    missing = set(required)-files.keys()
    if missing:
        raise ValueError('Competência incompleta: '+', '.join(sorted(missing)))
    print(f'Competência {month}; arquivos compactados: {sum(files[n] for n in required)/1e9:.2f} GB', flush=True)
    cache = root/month
    pending = {}
    def source(name):
        target = cache/name
        print(f'Obtendo/lendo {name}', flush=True)
        if name in pending:
            pending[name].result()
        else:
            download(BASE+month+'/'+name, target, files[name])
        return target
    geo_path = root/'municipios.csv'
    download(GEO, geo_path)
    with geo_path.open(encoding='utf-8-sig', newline='') as geo_file:
        geo = list(csv.DictReader(geo_file))
    uf_code = {'RO':'11','AC':'12','AM':'13','RR':'14','PA':'15','AP':'16','TO':'17','MA':'21','PI':'22','CE':'23','RN':'24','PB':'25','PE':'26','AL':'27','SE':'28','BA':'29','MG':'31','ES':'32','RJ':'33','SP':'35','PR':'41','SC':'42','RS':'43','MS':'50','MT':'51','GO':'52','DF':'53'}[args.uf]
    local = [g for g in geo if g['codigo_uf'] == uf_code]
    origin = next((g for g in local if norm(g['nome']) == norm(args.city)), None)
    if not origin:
        raise ValueError('Cidade de referência não encontrada')
    center = (float(origin['latitude']), float(origin['longitude']))
    selected = {str(g['siafi_id']).zfill(4): g for g in local if km(center,(float(g['latitude']),float(g['longitude']))) <= args.radius}
    cities = {}
    for code, name in rows(source('Municipios.zip')):
        if code.zfill(4) in selected:
            g = selected[code.zfill(4)]
            cities[code] = {'name':name,'lat':float(g['latitude']),'lng':float(g['longitude'])}
    if len(cities) != len(selected):
        raise ValueError('Municípios sem correspondência; conferir nomes antes de importar')
    print(f'Recorte {args.uf}: {len(cities)} cidades; raio aproximado entre sedes municipais.', flush=True)
    cnaes = dict(rows(source('Cnaes.zip')))
    scope = hashlib.sha256(f'{month}:{args.uf}:{norm(args.city)}:{args.radius}'.encode()).hexdigest()[:12]
    db = sqlite3.connect(root/f'regional-{scope}.sqlite')
    db.executescript('CREATE TABLE IF NOT EXISTS companies (cnpj TEXT PRIMARY KEY,name TEXT,cnae TEXT,sector TEXT,city TEXT,state TEXT,address TEXT,phone TEXT,email TEXT,opened TEXT,lat REAL,lng REAL,search TEXT); CREATE TABLE IF NOT EXISTS done (name TEXT PRIMARY KEY); CREATE TABLE IF NOT EXISTS names (base TEXT PRIMARY KEY, name TEXT);')
    # Three independent transfers, bounded to avoid overwhelming the public host.
    transfers=ThreadPoolExecutor(max_workers=3)
    for name in required[2:]:
        if not db.execute('SELECT 1 FROM done WHERE name=?',(name,)).fetchone():
            pending[name]=transfers.submit(download,BASE+month+'/'+name,cache/name,files[name])
    for i in range(10):
        name = f'Estabelecimentos{i}.zip'
        if db.execute('SELECT 1 FROM done WHERE name=?',(name,)).fetchone():
            continue
        path = source(name)
        with db:
            for r in rows(path):
                record = establishment(r,cities,cnaes,args.uf)
                if record:
                    db.execute('INSERT OR REPLACE INTO companies VALUES ('+','.join('?'*13)+')',record)
            db.execute('INSERT INTO done VALUES (?)',(name,))
        print(f'{name} concluído; {db.execute("SELECT count(*) FROM companies").fetchone()[0]} estabelecimentos no recorte',flush=True)
    bases = {r[0][:8] for r in db.execute('SELECT cnpj FROM companies')}
    if not bases:
        raise ValueError('Nenhuma empresa encontrada; publicação recusada')
    for i in range(10):
        name = f'Empresas{i}.zip'
        if db.execute('SELECT 1 FROM done WHERE name=?',(name,)).fetchone():
            continue
        with db:
            for r in rows(source(name)):
                if len(r) != 7:
                    raise ValueError('Layout de empresas inesperado')
                if r[0] in bases:
                    db.execute('INSERT OR REPLACE INTO names VALUES (?,?)',(r[0],r[1]))
            db.execute('INSERT INTO done VALUES (?)',(name,))
    missing = db.execute('SELECT count(*) FROM companies c LEFT JOIN names n ON substr(c.cnpj,1,8)=n.base WHERE n.base IS NULL').fetchone()[0]
    if missing:
        raise ValueError(f'{missing} estabelecimentos sem razão social; exportação recusada')
    out = root/f'catalog-{scope}'
    out.mkdir(exist_ok=True)
    # Separate staging tables: failed upload never changes the active catalogue.
    with (out/'0000-schema.sql').open('w',encoding='utf-8') as f:
        f.write('DROP TABLE IF EXISTS companies_import;\nCREATE TABLE companies_import AS SELECT * FROM companies WHERE 0;\nDROP TABLE IF EXISTS cities_import;\nCREATE TABLE cities_import AS SELECT * FROM cities WHERE 0;\n')
        for c in cities.values():
            f.write('INSERT INTO cities_import VALUES ('+','.join(map(sql,[norm(c['name']),c['name'],args.uf,c['lat'],c['lng']]))+');\n')
    count=0
    chunk=None
    query='SELECT c.*,n.name FROM companies c JOIN names n ON substr(c.cnpj,1,8)=n.base ORDER BY c.cnpj'
    for row in db.execute(query):
        values=list(row[:13])
        values[1]=row[1] or row[13]
        values[12]=row[12]+' '+norm(row[13])
        if count%1000==0:
            if chunk: chunk.close()
            chunk=(out/f'{count//1000+1:04d}-companies.sql').open('w',encoding='utf-8')
        chunk.write('INSERT INTO companies_import ('+FIELDS+') VALUES ('+','.join(map(sql,values))+');\n')
        count+=1
    if chunk: chunk.close()
    manifest={'month':month,'count':count,'cities':len(cities),'uf':args.uf,'center':args.city,'radiusKm':args.radius,'locationPrecision':'municipality','source':BASE+month+'/','geoSource':GEO,'geoSha256':hashlib.sha256(geo_path.read_bytes()).hexdigest()}
    manifest['files']={p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in sorted(out.glob('*.sql'))}
    (out/'manifest.json').write_text(json.dumps(manifest,ensure_ascii=False,indent=2),encoding='utf-8')
    db.close()
    transfers.shutdown()
    print(f'CATALOG_READY={out.resolve()}\n{count} empresas preparadas; ainda não publicadas no D1.',flush=True)
    return out

if __name__ == '__main__':
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--month',help='YYYY-MM; padrão: última competência publicada')
    p.add_argument('--uf',default='PA')
    p.add_argument('--city',default='Parauapebas')
    p.add_argument('--radius',type=float,default=100)
    p.add_argument('--workdir',default='data/receita')
    p.add_argument('--publish',action='store_true',help='Publica no D1 após validar a carga inteira; requer Wrangler autenticado')
    args=p.parse_args()
    if not 1<=args.radius<=500: p.error('Raio deve estar entre 1 e 500 km')
    output=run(args)
    if args.publish:
        import sys
        subprocess.run([sys.executable,str(Path(__file__).with_name('publish-catalog.py')),str(output)],check=True)
