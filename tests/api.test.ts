import {it,expect,vi} from 'vitest';
vi.mock('jose',()=>({createRemoteJWKSet:()=>null,jwtVerify:vi.fn(async(token:string)=>{if(token!=='valid')throw Error('invalid');return {payload:{sub:'user-a'}}})}));
import {onRequestGet} from '../functions/api/companies';
async function call(query:string,token='valid',db:unknown={}){return onRequestGet({request:new Request('https://example.test/api/companies?'+query,{headers:token?{Authorization:'Bearer '+token}:{}}),env:{DB:db,FIREBASE_PROJECT_ID:'test'}} as never)}
it('rejeita chamadas sem autenticação',async()=>{expect((await call('', '')).status).toBe(401);expect((await call('','invalid')).status).toBe(401)});
it('valida raio e intervalo antes de consultar o banco',async()=>{expect((await call('city=X&state=PA&radius=-1')).status).toBe(400);expect((await call('city=X&state=PA&radius=100&from=2026-02-30')).status).toBe(400);expect((await call('city=X&state=PA&radius=100&from=2026-03-01&to=2025-01-01')).status).toBe(400)});
it('exclui pontos fora do círculo mesmo quando estão no retângulo',async()=>{const db={prepare:vi.fn(()=>({bind:()=>({first:async()=>({lat:0,lng:0}),all:async()=>({results:[{cnpj:'1',lat:.8,lng:.8},{cnpj:'2',lat:.2,lng:.2}]})})}))};const r=await call('city=X&state=PA&radius=100','valid',db);expect(r.status).toBe(200);expect((await r.json() as {companies:{cnpj:string}[]}).companies.map(c=>c.cnpj)).toEqual(['2'])});
