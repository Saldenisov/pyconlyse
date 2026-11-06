import { cleanServerPath, manifestTreatmentUrl, serverPathParent } from './serverPaths';

test('Explorer quotes are removed without changing spaces, apostrophes or path identity',()=>{
  expect(cleanServerPath('  "E:\\DATA_VD2\\20261103\\vd2-manifest.json"  ')).toBe('E:\\DATA_VD2\\20261103\\vd2-manifest.json');
  expect(cleanServerPath('"E:\\DATA_VD2\\O\'Brien\\vd2-manifest.json"')).toBe('E:\\DATA_VD2\\O\'Brien\\vd2-manifest.json');
  expect(serverPathParent('"E:\\DATA_VD2\\20261103\\vd2-manifest.json"')).toBe('E:\\DATA_VD2\\20261103');
  expect(serverPathParent('E:\\file.json')).toBe('E:\\');
});

test('new-window manifest links preserve sample and path through URL encoding',()=>{
  const url=manifestTreatmentUrl('"E:\\DATA_VD2\\test & water\\vd2-manifest.json"','water sample');
  const query=new URL(url,'http://localhost').searchParams;
  expect(query.get('manifest')).toBe('E:\\DATA_VD2\\test & water\\vd2-manifest.json');
  expect(query.get('sample')).toBe('water sample');
});
