import {
  DEVICE_FAMILY_DEFINITIONS,
  getDeviceFamilyLabel,
  normalizeDeviceFamilyText,
  resolveDeviceFamily,
} from './deviceFamily';

describe('device family classification contracts', () => {
  test('exposes stable family metadata and fallback label', () => {
    expect(DEVICE_FAMILY_DEFINITIONS).toEqual([
      { key: 'itest_psu', label: 'iTest PSU' },
      { key: 'netio', label: 'NETIO PDU' },
      { key: 'camera', label: 'Cameras' },
      { key: 'motor', label: 'Motors' },
      { key: 'generic', label: 'Generic Tango' },
    ]);
    expect(getDeviceFamilyLabel('netio')).toBe('NETIO PDU');
    expect(getDeviceFamilyLabel('unknown')).toBe('Generic Tango');
  });

  test('normalizes values and classifies string names and class metadata', () => {
    expect(normalizeDeviceFamilyText('  BASLER-CAMERA ')).toBe('  basler-camera ');
    expect(resolveDeviceFamily('iTest PSU controller')).toBe('itest_psu');
    expect(resolveDeviceFamily('pdu-main')).toBe('netio');
    expect(resolveDeviceFamily('basler acA')).toBe('camera');
    expect(resolveDeviceFamily('standa stage')).toBe('motor');
    expect(resolveDeviceFamily('custom/tango/device')).toBe('generic');
    expect(resolveDeviceFamily('device-1', 'CameraDevice')).toBe('camera');
  });

  test('supports object metadata and gives iTest precedence over other matches', () => {
    expect(
      resolveDeviceFamily({ name: 'power-1', class: 'Generic', server: 'PSU-Server' })
    ).toBe('itest_psu');
    expect(resolveDeviceFamily({ name: 'pdu-1', class: 'NetioDevice' })).toBe('netio');
    expect(resolveDeviceFamily({ name: 'axis', class: 'MotorController' })).toBe('motor');
    expect(resolveDeviceFamily(null)).toBe('generic');
  });
});
