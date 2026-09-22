// Streams normalized JSONL to SQL. Raw Receita archives must be joined/enriched upstream.
import {createReadStream,createWriteStream} from 'node:fs';
import {createInterface} from 'node:readline';
import {once} from 'node:events';
import {resolve} from 'node:path';
const [input,output,uf]=process.argv.slice(2);
if(!input||!output||!/^[A-Z]{2}$/.test(uf||''))throw Error('Uso: node scripts/import-catalog.mjs entrada.jsonl saida.sql PA');
if(resolve(input).toLowerCase()===resolve(output).toLowerCase())throw Error('Entrada e saída devem ser diferentes');
const out=createWriteStream(output,{flags:'wx'});await once(out,'open');
const norm=s=>s.normalize('NFD').replace(/[\u0300-\u036f]/g,'').toLowerCase();
const quote=v=>typeof v==='number'?String(v):"'"+String(v).replace(/'/g,"''")+"'";
const write=async s=>{if(!out.write(s+'\n'))await once(out,'drain')};
let count=0,line=0;
try{for await(const raw of createInterface({input:createReadStream(input),crlfDelay:Infinity})){
 line++;if(!raw.trim())continue;const c=JSON.parse(raw);if(c.state!==uf||c.active!==true)continue;
 const fields=['cnpj','name','cnae','sector','city','state','address','phone','email','opened','lat','lng'];
 if(!/^[0-9A-Z]{12}[0-9]{2}$/.test(c.cnpj)||!/^\d{7}$/.test(c.cnae)||fields.slice(0,10).some(k=>typeof c[k]!=='string')||!Number.isFinite(c.lat)||!Number.isFinite(c.lng)||Math.abs(c.lat)>90||Math.abs(c.lng)>180||!Number.isFinite(c.cityLat)||!Number.isFinite(c.cityLng)||Math.abs(c.cityLat)>90||Math.abs(c.cityLng)>180||!/^\d{4}-\d{2}-\d{2}$/.test(c.opened))throw Error('Registro inválido na linha '+line);
 await write(`INSERT OR REPLACE INTO cities (normalized,name,state,lat,lng) VALUES (${[norm(c.city),c.city,c.state,c.cityLat,c.cityLng].map(quote).join(',')});`);
 await write(`INSERT OR REPLACE INTO companies (${fields.join(',')},search) VALUES (${[...fields.map(k=>c[k]),norm(c.name+' '+c.cnae+' '+c.sector+' '+(c.secondaryCnaes||[]).join(' '))].map(quote).join(',')});`);count++;
}out.end();await once(out,'finish');console.log(`${count} empresas ativas exportadas. Arquivo contém dados de contato; não versionar.`)}catch(e){out.destroy();throw e}
