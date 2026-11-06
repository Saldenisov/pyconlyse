import {captureAlignmentSnapshot,getAlignmentSnapshots} from './vd2AlignmentPresets';
import {fetchWithCsrfToken} from './csrfRequest';
import {ALIGNMENT_CHANNELS} from '../vd2AlignmentSearch';

jest.mock('./csrfRequest',()=>({fetchWithCsrfToken:jest.fn()}));
const channels=ALIGNMENT_CHANNELS.map((name,index)=>({id:index+1,name,value:0.1}));
const reply=data=>({ok:true,json:async()=>data});
const originalCrypto=Object.getOwnPropertyDescriptor(window,'crypto');
beforeEach(()=>{
  fetchWithCsrfToken.mockReset();
  Object.defineProperty(window,'crypto',{configurable:true,value:{getRandomValues:array=>{array.fill(123);return array;}}});
});
afterEach(()=>{if(originalCrypto)Object.defineProperty(window,'crypto',originalCrypto);else delete window.crypto;});

test('GET reads saved DB settings without hardware authorization or mutation',async()=>{
  fetchWithCsrfToken.mockResolvedValue(reply({success:true,recommended:null}));
  expect(await getAlignmentSnapshots('ELYSE/pdu/iTest')).toEqual({success:true,recommended:null});
  expect(fetchWithCsrfToken.mock.calls[0][0]).toBe('/api/pump-probe-vd2/alignment/snapshots?device=ELYSE%2Fpdu%2FiTest');
  expect(fetchWithCsrfToken.mock.calls[0][1].method).toBeUndefined();
});

test('old Web missing the new DB route reports unavailable; POST cannot claim a saved return point',async()=>{
  fetchWithCsrfToken.mockResolvedValue({ok:false,status:404,json:async()=>{throw new Error('HTML response');}});
  expect(await getAlignmentSnapshots('ELYSE/pdu/iTest')).toMatchObject({available:false,recommended:null});
  await expect(captureAlignmentSnapshot({device:'ELYSE/pdu/iTest',kind:'before_search',channels})).rejects.toThrow('No return point was saved');
});

test('POST records an idempotency UUID and exact reviewed currents using normal CSRF',async()=>{
  fetchWithCsrfToken.mockResolvedValue(reply({success:true,snapshot:{id:'saved',device:'ELYSE/pdu/iTest',kind:'before_search',channels}}));
  await captureAlignmentSnapshot({device:'ELYSE/pdu/iTest',kind:'before_search',channels});
  const [url,options]=fetchWithCsrfToken.mock.calls[0],body=JSON.parse(options.body);
  expect(url).toBe('/api/pump-probe-vd2/alignment/snapshots');
  expect(options.method).toBe('POST');expect(body.expected).toEqual(channels);
  expect(body.operation_id).toMatch(/^[0-9a-f]{8}-[0-9a-f]{4}-4[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/);
});

test.each(['database','identity','currents'])('%s failure is never interpreted as a durable return point',async failure=>{
  const snapshot={id:'saved',device:'ELYSE/pdu/iTest',kind:'before_search',channels:channels.map(channel=>({...channel}))};
  if(failure==='identity')snapshot.channels[7].id=100;
  if(failure==='currents')snapshot.channels[7].value=1;
  fetchWithCsrfToken.mockResolvedValue(failure==='database'?{ok:false,status:503,json:async()=>({success:false,error:'Database full'})}:reply({success:true,snapshot}));
  await expect(captureAlignmentSnapshot({device:'ELYSE/pdu/iTest',kind:'before_search',channels})).rejects.toThrow(failure==='database'?'Database full':/Database did not confirm/);
});
