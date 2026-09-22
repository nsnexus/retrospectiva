import {describe,it,expect} from 'vitest';
import {distance,csv,whatsapp,normalize,type Lead} from '../src/domain';
import {companies} from '../src/demo';
describe('regras da prospecção',()=>{
 it('calcula raio em linha reta e inclui cidades próximas',()=>{expect(distance(-6.0675,-49.9022,-6.0675,-49.9022)).toBe(0);expect(distance(-6.0675,-49.9022,-6.4966,-49.8776)).toBeCloseTo(47.79,0)});
 it('normaliza pesquisa e telefone brasileiro',()=>{expect(normalize('Construção')).toBe('construcao');expect(whatsapp('(94) 99999-1234')).toBe('https://wa.me/5594999991234');expect(whatsapp('123')).toBeNull()});
 it('exporta com escape e bloqueia fórmulas de planilha',()=>{const l:Lead={company:companies[0],status:'Novo',notes:'=HYPERLINK("bad")\ntexto',nextAttempt:'',lastContact:'',updatedAt:''};expect(csv([l])).toContain('"\'=HYPERLINK(""bad"")\ntexto"');expect(csv([l]).startsWith('\uFEFF')).toBe(true)});
});
