export const spectralSum = 'matched_spectral_sum';
export const spectralIndividual = 'matched_spectral_individual';

export const vd2OdLabels = {
  [spectralSum]: 'Matched BASE + spectral correction · OD of sums',
  [spectralIndividual]: 'Matched BASE + spectral correction · Mean individual OD',
  averaged: 'Classic · OD of averages',
  individual: 'Classic · Mean individual OD',
};

export const vd2OdModes = (expType, supported, current) => {
  const modes = expType === 'HIS' ? ['averaged', 'individual'] : [spectralSum, spectralIndividual, 'averaged'];
  if (expType === 'HIS+NOISE' && current === 'individual') modes.push(current);
  return modes.filter(mode => supported.includes(mode));
};
