import { render, screen } from '@testing-library/react';
import DataWindowVD2 from './DataWindowVD2';

jest.mock('./TopSection', () => function MockTopSection() {
  return <div data-testid="preview-controls">Preview controls</div>;
});

jest.mock('./TabsControl', () => function MockTabsControl() {
  return <div data-testid="treatment-inputs">Treatment inputs</div>;
});

describe('DataWindowVD2 layout shell', () => {
  test('keeps preview and treatment inputs as labelled sections in Studio', () => {
    render(<DataWindowVD2 profile="VD2" layoutMode="studio" />);

    expect(screen.getByRole('main')).toHaveClass('treatment-layout-studio');
    expect(screen.getByRole('heading', { name: 'Preview' })).toBeInTheDocument();
    expect(screen.getByRole('region', { name: 'Treatment inputs and processing' }))
      .toBeInTheDocument();
    expect(screen.getByTestId('preview-controls')).toBeInTheDocument();
    expect(screen.getByTestId('treatment-inputs')).toBeInTheDocument();
  });

  test('uses the classic shell unless Studio is selected', () => {
    render(<DataWindowVD2 profile="VD2" />);

    expect(screen.getByRole('main')).toHaveClass('treatment-layout-classic');
  });
});
