export function cleanServerPath(value) {
  let path=String(value||'').trim();
  while(path.length>=2&&['"',"'"].includes(path[0])&&path.at(-1)===path[0])path=path.slice(1,-1).trim();
  return path;
}

export function serverPathParent(value) {
  const path=cleanServerPath(value).replace(/[\\/]+$/,'');
  const position=Math.max(path.lastIndexOf('\\'),path.lastIndexOf('/'));
  if(position===2&&path[1]===':')return path.slice(0,3);
  return position===0?'/':position>0?path.slice(0,position):'';
}

export function manifestTreatmentUrl(manifest,sample='') {
  const query=new URLSearchParams({profile:'VD2',manifest:cleanServerPath(manifest)});
  if(sample)query.set('sample',sample);
  return `/datatreatment?${query}`;
}
