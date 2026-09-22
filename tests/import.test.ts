import {it,expect} from 'vitest';
import {mkdtempSync,writeFileSync,readFileSync} from 'node:fs';
import {tmpdir} from 'node:os';
import {join} from 'node:path';
import {execFileSync} from 'node:child_process';
it('importa somente a UF escolhida e empresas ativas, escapando apóstrofos',()=>{
 const folder=mkdtempSync(join(tmpdir(),'nexus-import-'));const input=join(folder,'input.jsonl'),output=join(folder,'output.sql');
 const c={cnpj:'12345678000100',name:"Empresa D'Água",cnae:'4321500',sector:'Instalações elétricas',city:'Parauapebas',state:'PA',address:'Rua Exemplo',phone:'',email:'',opened:'2025-01-01',lat:-6,lng:-49,cityLat:-6,cityLng:-49,active:true};
 writeFileSync(input,[c,{...c,active:false},{...c,state:'SP'}].map(x=>JSON.stringify(x)).join('\n'));
 execFileSync(process.execPath,['scripts/import-catalog.mjs',input,output,'PA']);const sql=readFileSync(output,'utf8');expect(sql.match(/INSERT OR REPLACE INTO companies/g)).toHaveLength(1);expect(sql).toContain("Empresa D''Água");expect(sql).toContain('instalacoes eletricas');
 expect(()=>execFileSync(process.execPath,['scripts/import-catalog.mjs',input,output,'PA'],{stdio:'pipe'})).toThrow();
});
