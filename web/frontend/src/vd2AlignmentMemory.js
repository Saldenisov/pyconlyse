import {useCallback,useEffect,useMemo,useRef,useState} from 'react';

export const ALIGNMENT_REGION_KEY='pyconlyse.vd2.alignment.region.v1';
export const DEFAULT_ALIGNMENT_REGION={wavelengthMin:500,wavelengthMax:700,topPercent:0,bottomPercent:20};
const finite=values=>values.every(Number.isFinite);

export function validAlignmentRegion(region) {
  return Boolean(region&&finite([region.wavelengthMin,region.wavelengthMax,region.topPercent,region.bottomPercent])
    &&region.wavelengthMin>=0&&region.wavelengthMin<region.wavelengthMax
    &&region.topPercent>=0&&region.topPercent<region.bottomPercent&&region.bottomPercent<=100);
}

export function alignmentTimeMemoryKey(unit,min,max) {
  if(!unit||!finite([min,max])||min>=max)return null;
  return `pyconlyse.vd2.alignment.windows.v1:${unit}:${min.toPrecision(10)}:${max.toPrecision(10)}`;
}

export function validAlignmentWindows(windows,min,max) {
  return Boolean(windows&&Array.isArray(windows.baseline)&&Array.isArray(windows.signal)
    &&windows.baseline.length===2&&windows.signal.length===2&&finite([...windows.baseline,...windows.signal])
    &&windows.baseline[0]>=min&&windows.baseline[0]<windows.baseline[1]
    &&windows.baseline[1]<windows.signal[0]&&windows.signal[0]<windows.signal[1]&&windows.signal[1]<=max);
}

export function validAcquisitionRois(rois) {
  return Array.isArray(rois)&&rois.every(roi=>roi&&/^roi-\d{1,10}$/.test(roi.id)
    &&['vertical','horizontal','rectangle'].includes(roi.type)
    &&[roi.x0,roi.x1,roi.y0,roi.y1].every(value=>Number.isInteger(value)&&value>=0&&value<=1000000))
    &&new Set(rois.map(roi=>roi.id)).size===rois.length;
}

function read(key,fallback,validate,perWindow) {
  const value=typeof fallback==='function'?fallback():fallback;
  if(!key)return {value,error:''};
  try {
    const raw=(perWindow?window.sessionStorage.getItem(key):null) ?? window.localStorage.getItem(key);
    if(raw===null)return {value,error:''};
    const saved=JSON.parse(raw);
    if(saved?.version!==1||!validate(saved.value))throw new Error('Invalid stored geometry');
    return {value:saved.value,error:''};
  } catch(_error) {
    return {value,error:'Saved regions could not be read in this browser. Default positions are shown.'};
  }
}

// Geometry only: mounting/restoring this hook never sends device commands.
// An unavailable image has key=null, so it cannot overwrite saved positions.
export function useVd2Memory(key,fallback,validate,perWindow=false) {
  const fallbackRef=useRef(fallback);fallbackRef.current=fallback;
  const loaded=useMemo(()=>read(key,fallbackRef.current,validate,perWindow),[key,validate,perWindow]);
  const [record,setRecord]=useState(()=>({key,value:loaded.value,dirty:false}));
  const [error,setError]=useState(loaded.error);
  const value=record.key===key?record.value:loaded.value;
  useEffect(()=>{
    if(record.key!==key){setRecord({key,value:loaded.value,dirty:false});setError(loaded.error);}
  },[key,loaded,record.key]);
  const setValue=useCallback(update=>setRecord(previous=>{
    const current=previous.key===key?previous.value:loaded.value;
    return {key,value:typeof update==='function'?update(current):update,dirty:true};
  }),[key,loaded]);
  useEffect(()=>{
    if(!key||record.key!==key||!validate(record.value)||(loaded.error&&!record.dirty))return;
    try {
      (perWindow?window.sessionStorage:window.localStorage).setItem(key,JSON.stringify({version:1,value:record.value}));setError('');
    } catch(_error) {
      setError('Region positions are kept for this session only: browser storage is unavailable.');
    }
  },[key,record,loaded.error,validate,perWindow]);
  return [value,setValue,error];
}
