import {fireEvent,render,screen} from '@testing-library/react';
import {ALIGNMENT_REGION_KEY,DEFAULT_ALIGNMENT_REGION,alignmentTimeMemoryKey,useVd2Memory,validAcquisitionRois,validAlignmentRegion} from './vd2AlignmentMemory';

function RegionMemory() {
  const [region,setRegion,error]=useVd2Memory(ALIGNMENT_REGION_KEY,DEFAULT_ALIGNMENT_REGION,validAlignmentRegion);
  return <><input aria-label="From" type="number" value={region.wavelengthMin} onChange={event=>setRegion(old=>({...old,wavelengthMin:Number(event.target.value)}))} />
    <output>{region.wavelengthMax}</output>{error&&<p role="alert">{error}</p>}</>;
}
const roi={id:'roi-1',type:'rectangle',x0:3,x1:9,y0:4,y1:10};
function RoiMemory({size}) {
  const [rois,setRois]=useVd2Memory(size?`roi-test:${size}`:null,[],validAcquisitionRois);
  return <><output aria-label="ROIs">{JSON.stringify(rois)}</output>
    <button onClick={()=>setRois([roi])}>Draw</button><button onClick={()=>setRois([])}>Clear</button></>;
}
beforeEach(()=>window.localStorage.clear());

test('browser reload/remount restores exact physical ROI coordinates',()=>{
  const view=render(<RegionMemory />);
  fireEvent.change(screen.getByRole('spinbutton',{name:'From'}),{target:{value:'553.25'}});
  view.unmount();render(<RegionMemory />);
  expect(screen.getByRole('spinbutton',{name:'From'})).toHaveValue(553.25);
  expect(screen.getByText('700')).toBeInTheDocument();
});

test('temporarily invalid edits never destroy the last valid saved geometry',()=>{
  const view=render(<RegionMemory />);
  fireEvent.change(screen.getByRole('spinbutton',{name:'From'}),{target:{value:'550'}});
  fireEvent.change(screen.getByRole('spinbutton',{name:'From'}),{target:{value:'900'}});
  expect(screen.getByRole('spinbutton',{name:'From'})).toHaveValue(900);
  view.unmount();render(<RegionMemory />);
  expect(screen.getByRole('spinbutton',{name:'From'})).toHaveValue(550);
});

test('missing frames and changes in image dimensions cannot erase another geometry context',()=>{
  const view=render(<RoiMemory size="512x512" />);
  fireEvent.click(screen.getByText('Draw'));
  view.rerender(<RoiMemory size={null} />);expect(screen.getByLabelText('ROIs')).toHaveTextContent('[]');
  view.rerender(<RoiMemory size="1024x512" />);expect(screen.getByLabelText('ROIs')).toHaveTextContent('[]');
  view.rerender(<RoiMemory size="512x512" />);expect(screen.getByLabelText('ROIs')).toHaveTextContent(JSON.stringify([roi]));
  fireEvent.click(screen.getByText('Clear'));view.unmount();render(<RoiMemory size="512x512" />);
  expect(screen.getByLabelText('ROIs')).toHaveTextContent('[]');
});

test.each(['broken JSON',JSON.stringify({version:99,value:DEFAULT_ALIGNMENT_REGION}),JSON.stringify({version:1,value:{...DEFAULT_ALIGNMENT_REGION,topPercent:120}})])('corrupt or unsupported saved data is reported and not silently overwritten: %s',raw=>{
  window.localStorage.setItem(ALIGNMENT_REGION_KEY,raw);
  render(<RegionMemory />);
  expect(screen.getByRole('spinbutton',{name:'From'})).toHaveValue(500);
  expect(screen.getByRole('alert')).toHaveTextContent('could not be read');
  expect(window.localStorage.getItem(ALIGNMENT_REGION_KEY)).toBe(raw);
  fireEvent.change(screen.getByRole('spinbutton',{name:'From'}),{target:{value:'550'}});
  expect(screen.queryByRole('alert')).not.toBeInTheDocument();
});

test('unavailable browser storage preserves usable session geometry and exposes the limitation',()=>{
  const get=jest.spyOn(Storage.prototype,'getItem').mockImplementation(()=>{throw new Error('disabled');});
  const set=jest.spyOn(Storage.prototype,'setItem').mockImplementation(()=>{throw new Error('full');});
  const view=render(<RegionMemory />);
  try {
    fireEvent.change(screen.getByRole('spinbutton',{name:'From'}),{target:{value:'550'}});
    expect(screen.getByRole('spinbutton',{name:'From'})).toHaveValue(550);
    expect(screen.getByRole('alert')).toHaveTextContent('session only');
  } finally {view.unmount();get.mockRestore();set.mockRestore();}
});

test('time-window keys distinguish physical units and ranges without depending on sample count',()=>{
  expect(alignmentTimeMemoryKey('us',0,1)).not.toBe(alignmentTimeMemoryKey('ms',0,1));
  expect(alignmentTimeMemoryKey('us',0,1)).not.toBe(alignmentTimeMemoryKey('us',0,2));
  expect(alignmentTimeMemoryKey('us',Infinity,-Infinity)).toBeNull();
});
