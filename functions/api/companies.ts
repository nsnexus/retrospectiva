import {createRemoteJWKSet,jwtVerify} from 'jose';
import {distance,normalize,type Company} from '../../src/domain';
interface Statement {bind(...values:(number|string)[]):Statement;first<T>():Promise<T|null>;all<T>():Promise<{results:T[]}>}
interface Env {DB:{prepare(sql:string):Statement}; FIREBASE_PROJECT_ID:string}
const keys=createRemoteJWKSet(new URL('https://www.googleapis.com/service_accounts/v1/jwk/securetoken@system.gserviceaccount.com'));
const response=(data:unknown,status=200)=>Response.json(data,{status,headers:{'Cache-Control':'no-store'}});
export const onRequestGet=async({request,env}:{request:Request;env:Env})=>{
 if(!env.DB||!env.FIREBASE_PROJECT_ID)return response({error:'Catálogo não configurado. Consulte o administrador.'},503);
 try{const token=request.headers.get('Authorization')?.replace(/^Bearer /,'');if(!token)return response({error:'Login necessário.'},401);const {payload}=await jwtVerify(token,keys,{issuer:`https://securetoken.google.com/${env.FIREBASE_PROJECT_ID}`,audience:env.FIREBASE_PROJECT_ID,algorithms:['RS256']});if(!payload.sub)return response({error:'Token inválido.'},401);}catch{return response({error:'Sessão inválida. Entre novamente.'},401)}
 const p=new URL(request.url).searchParams;const city=normalize((p.get('city')||'').trim()),state=(p.get('state')||'').toUpperCase(),radius=Number(p.get('radius'));const q=normalize((p.get('q')||'').trim());const from=p.get('from')||'',to=p.get('to')||'';
 const validDate=(s:string)=>!s||(/^\d{4}-\d{2}-\d{2}$/.test(s)&&!Number.isNaN(Date.parse(s))&&new Date(s).toISOString().slice(0,10)===s);
 if(!city||city.length>150||!/^[A-Z]{2}$/.test(state)||!Number.isFinite(radius)||radius<1||radius>500||q.length>100||!validDate(from)||!validDate(to)||(from&&to&&from>to))return response({error:'Confira cidade, UF, raio (1–500 km) e período.'},400);
 try{
 const origin=await env.DB.prepare('SELECT lat,lng FROM cities WHERE normalized = ? AND state = ?').bind(city,state).first<{lat:number;lng:number}>();
 if(!origin)return response({error:'Cidade não cadastrada no catálogo regional.'},404);
 const latDelta=radius/111.195,lngDelta=radius/(111.195*Math.max(.01,Math.cos((Math.abs(origin.lat)+latDelta)*Math.PI/180)));
 const where=['lat BETWEEN ? AND ?','lng BETWEEN ? AND ?'];const args:(number|string)[]=[origin.lat-latDelta,origin.lat+latDelta,origin.lng-lngDelta,origin.lng+lngDelta];
 if(q){where.push("search LIKE ? ESCAPE '\\'");args.push('%'+q.replace(/[\\%_]/g,'\\$&')+'%')}
 if(from){where.push('opened >= ?');args.push(from)}if(to){where.push('opened <= ?');args.push(to)}
 // Keyset scan: no false empty result caused by a bounding-box LIMIT before exact distance.
 const matches:Company[]=[];let cursor='';let scanned=0;
 while(matches.length<101){const batch=await env.DB.prepare(`SELECT cnpj,name,cnae,sector,city,state,address,phone,email,opened,lat,lng FROM companies WHERE ${where.join(' AND ')} AND cnpj > ? ORDER BY cnpj LIMIT 500`).bind(...args,cursor).all<Company>();for(const c of batch.results){if(distance(origin.lat,origin.lng,c.lat,c.lng)<=radius)matches.push(c);if(matches.length===101)break}scanned+=batch.results.length;if(batch.results.length<500||matches.length===101)break;if(scanned>=10000)return response({error:'Região muito ampla. Reduza o raio ou selecione um CNAE.'},422);cursor=batch.results.at(-1)!.cnpj;}
 return response({companies:matches.slice(0,100),hasMore:matches.length>100});
 }catch{return response({error:'Não foi possível consultar o catálogo. Tente novamente.'},503)}
};
