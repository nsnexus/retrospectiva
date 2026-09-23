import {normalize} from './domain';
// Sinônimos comerciais que não constam literalmente na descrição oficial do CNAE.
// A classificação pode incluir outras atividades: sempre exibimos a descrição oficial.
const aliases:Record<string,string[]>={
 barbearia:['9602501'],barbeiro:['9602501'],barbearias:['9602501'],
 cabeleireiro:['9602501'],salao:['9602501'], 'salao de beleza':['9602501'],
 restaurante:['5611201'],restaurantes:['5611201'],
 dentista:['8630504'],odontologia:['8630504'],'clinica odontologica':['8630504'],
 'auto eletrica':['4520003'],eletricista:['4321500'],'instalacoes eletricas':['4321500'],
 construtora:['4120400'],construtoras:['4120400'],
};
export function sectorTerms(query:string):string[]{
 const q=normalize(query.trim());
 const digits=q.replace(/[.\/-]/g,'');
 if(/^\d{7}$/.test(digits))return [digits];
 return aliases[q]||[q];
}
