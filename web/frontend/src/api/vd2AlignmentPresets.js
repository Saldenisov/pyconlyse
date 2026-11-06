import {fetchWithCsrfToken} from './csrfRequest';

const endpoint='/api/pump-probe-vd2/alignment/snapshots';
async function request(url,options,allowMissing=false) {
  const abort=new AbortController(),timer=setTimeout(()=>abort.abort(),15000);
  try {
    const response=await fetchWithCsrfToken(url,{credentials:'include',...options,signal:abort.signal});
    // Older Web processes can keep serving the updated static UI until the
    // operator reloads Web. Missing DB routes must never enable current writes.
    if(response.status===404) {
      if(allowMissing)return {success:true,available:false,best:null,previous:null,recommended:null,history:[]};
      throw new Error('Saved-current presets need Web reload. No return point was saved.');
    }
    return await json(response);
  }
  finally {clearTimeout(timer);}
}
async function json(response) {
  const data=await response.json();
  if(!response.ok||data.success!==true)throw new Error(data.error||`Alignment database request failed (HTTP ${response.status})`);
  return data;
}
export async function getAlignmentSnapshots(device) {
  return request(`${endpoint}?device=${encodeURIComponent(device)}`,undefined,true);
}
export function expectedCurrents(channels) {
  return channels.map(({id,name,value})=>({id,name,value}));
}
export async function captureAlignmentSnapshot({device,kind,channels,context={},parent_id=null,quality=null}) {
  // DB-only POST, protected by normal authentication/CSRF. Hardware writes
  // continue to use the separate, existing iTest authorization route.
  const bytes=window.crypto.getRandomValues(new Uint8Array(16));
  bytes[6]=(bytes[6]&15)|64;bytes[8]=(bytes[8]&63)|128;
  const hex=Array.from(bytes,value=>value.toString(16).padStart(2,'0')).join('');
  const operation_id=[hex.slice(0,8),hex.slice(8,12),hex.slice(12,16),hex.slice(16,20),hex.slice(20)].join('-');
  const data=await request(endpoint,{method:'POST',headers:{'Content-Type':'application/json'},
    body:JSON.stringify({device,kind,expected:expectedCurrents(channels),context,parent_id,quality,operation_id})});
  if(!data.snapshot?.id||data.snapshot.kind!==kind||data.snapshot.device.toLowerCase()!==device.toLowerCase())throw new Error('Database did not confirm this return point. No further action.');
  const actual=data.snapshot.channels;
  if(!Array.isArray(actual)||actual.length!==8||actual.some((channel,index)=>channel.id!==channels[index].id||channel.name!==channels[index].name
    ||!Number.isFinite(channel.value)||Math.abs(channel.value-channels[index].value)>0.0005))throw new Error('Database did not confirm the reviewed currents. No further action.');
  return data.snapshot;
}
