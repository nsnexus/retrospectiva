import {it,expect} from 'vitest';
import {sectorTerms} from '../src/sectors';
it('relaciona ramo popular a CNAE e normaliza código formatado',()=>{
 expect(sectorTerms('Barbearia')).toEqual(['9602501']);
 expect(sectorTerms('96.02-5/01')).toEqual(['9602501']);
 expect(sectorTerms('Construção de edifícios')).toEqual(['construcao de edificios']);
});
