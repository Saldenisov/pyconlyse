export const DEVICE_FAMILY_DEFINITIONS = [
  { key: 'itest_psu', label: 'iTest PSU' },
  { key: 'netio', label: 'NETIO PDU' },
  { key: 'camera', label: 'Cameras' },
  { key: 'motor', label: 'Motors' },
  { key: 'generic', label: 'Generic Tango' },
];

const DEVICE_FAMILY_LABELS = Object.fromEntries(
  DEVICE_FAMILY_DEFINITIONS.map((family) => [family.key, family.label])
);

export const normalizeDeviceFamilyText = (value) => String(value || '').toLowerCase();

export function resolveDeviceFamily(deviceOrName, deviceClass = '') {
  let name = '';
  let familyClass = '';
  let server = '';

  if (typeof deviceOrName === 'string') {
    name = normalizeDeviceFamilyText(deviceOrName);
    familyClass = normalizeDeviceFamilyText(deviceClass);
  } else {
    name = normalizeDeviceFamilyText(deviceOrName?.name);
    familyClass = normalizeDeviceFamilyText(deviceOrName?.class);
    server = normalizeDeviceFamilyText(deviceOrName?.server);
  }

  const isItest =
    name.includes('itest') ||
    name.includes('psu') ||
    familyClass.includes('itest') ||
    familyClass.includes('psu') ||
    server.includes('itest') ||
    server.includes('psu');
  if (isItest) {
    return 'itest_psu';
  }
  if (name.includes('netio') || name.includes('pdu') || familyClass.includes('netio')) {
    return 'netio';
  }
  if (
    name.includes('camera') ||
    name.includes('basler') ||
    name.includes('andor') ||
    familyClass.includes('camera')
  ) {
    return 'camera';
  }
  if (
    name.includes('motor') ||
    name.includes('standa') ||
    name.includes('owis') ||
    familyClass.includes('motor')
  ) {
    return 'motor';
  }
  return 'generic';
}

export const getDeviceFamilyLabel = (familyKey) =>
  DEVICE_FAMILY_LABELS[familyKey] || DEVICE_FAMILY_LABELS.generic;
