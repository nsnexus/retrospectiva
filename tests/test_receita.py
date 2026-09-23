import csv
import importlib.util
import io
import json
import sqlite3
import tempfile
import unittest
import types
import zipfile
from argparse import Namespace
from pathlib import Path
from unittest.mock import patch

spec=importlib.util.spec_from_file_location('receita',Path(__file__).parents[1]/'scripts/receita.py')
r=importlib.util.module_from_spec(spec)
spec.loader.exec_module(r)
pubspec=importlib.util.spec_from_file_location('publisher',Path(__file__).parents[1]/'scripts/publish-catalog.py')
pub=importlib.util.module_from_spec(pubspec)
pubspec.loader.exec_module(pub)

def archive(path,records):
    stream=io.StringIO(newline='')
    csv.writer(stream,delimiter=';',quoting=csv.QUOTE_ALL).writerows(records)
    with zipfile.ZipFile(path,'w') as z: z.writestr('data.csv',stream.getvalue().encode('latin-1'))

def record(status='02',uf='PA',city='0595'):
    row=['']*30
    for idx,value in {0:'00123456',1:'0001',2:'00',5:status,10:'20250115',11:'9602501',12:'4321500',13:'RUA',14:"D'ÁGUA",15:'10',19:uf,20:city,21:'94',22:'999991234',27:'contato@example.test'}.items(): row[idx]=value
    return row

class ReceitaTest(unittest.TestCase):
    def test_filter_and_fields(self):
        cities={'0595':{'name':'PARAUAPEBAS','lat':-6.,'lng':-49.}}
        cnaes={'9602501':'Cabeleireiros','4321500':'Instalações elétricas'}
        row=r.establishment(record(),cities,cnaes,'PA')
        self.assertEqual(row[0],'00123456000100')
        self.assertEqual(row[7],'94999991234')
        self.assertEqual(row[9],'2025-01-15')
        self.assertIn('instalacoes eletricas',row[12])
        self.assertIsNone(r.establishment(record('08'),cities,cnaes,'PA'))
        self.assertIsNone(r.establishment(record(uf='SP'),cities,cnaes,'PA'))
        self.assertEqual(r.opened('20250230'),'')
        with self.assertRaises(ValueError):r.establishment(['short'],cities,cnaes,'PA')

    def test_full_pipeline_and_restart(self):
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory);cache=root/'2026-09';cache.mkdir()
            (root/'municipios.csv').write_text('codigo_ibge,nome,latitude,longitude,codigo_uf,siafi_id\n1505536,Parauapebas,-6.06781,-49.9037,15,0595\n',encoding='utf-8')
            archive(cache/'Municipios.zip',[['0595','PARAUAPEBAS']])
            archive(cache/'Cnaes.zip',[['9602501','Cabeleireiros'],['4321500','Instalações elétricas']])
            for i in range(10):
                archive(cache/f'Estabelecimentos{i}.zip',[record(),record('08')] if i==0 else [])
                archive(cache/f'Empresas{i}.zip',[['00123456',"EMPRESA D'ÁGUA",'','','','','']] if i==9 else [])
            files={p.name:p.stat().st_size for p in cache.iterdir()}
            args=Namespace(month='2026-09',uf='PA',city='Parauapebas',radius=100,workdir=directory)
            with patch.object(r,'listing',return_value=files),patch.object(r,'download'):
                r.run(args);r.run(args)
            out=next(root.glob('catalog-*'))
            manifest=json.loads((out/'manifest.json').read_text(encoding='utf-8'))
            self.assertEqual(manifest['count'],1)
            db=sqlite3.connect(':memory:')
            db.executescript((Path(__file__).parents[1]/'migrations/0001_catalog.sql').read_text())
            for name in sorted(manifest['files']):db.executescript((out/name).read_text(encoding='utf-8'))
            self.assertEqual(db.execute('SELECT name FROM companies_import').fetchone()[0],"EMPRESA D'ÁGUA")
            self.assertEqual(db.execute('SELECT count(*) FROM companies').fetchone()[0],0)
            def fake_wrangler(cmd,**kwargs):
                if '--file' in cmd:
                    db.executescript(Path(cmd[cmd.index('--file')+1]).read_text(encoding='utf-8'))
                    result=[]
                else:
                    cur=db.execute(cmd[cmd.index('--command')+1])
                    result=[dict(zip([d[0] for d in cur.description],row)) for row in cur]
                return types.SimpleNamespace(returncode=0,stdout=json.dumps([{'results':result}]),stderr='')
            with patch.object(pub.shutil,'which',return_value='npx'),patch.object(pub.subprocess,'run',side_effect=fake_wrangler):
                pub.publish(out,True)
                pub.publish(out,True)
            self.assertEqual(db.execute('SELECT count(*) FROM companies').fetchone()[0],1)
            self.assertEqual(db.execute('SELECT count(*) FROM companies_previous').fetchone()[0],1)
            db.close()

if __name__=='__main__':unittest.main()
