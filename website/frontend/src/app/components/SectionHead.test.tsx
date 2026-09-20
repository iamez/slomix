import { render, screen } from '@testing-library/react';
import { describe, expect, it } from 'vitest';
import { SectionHead } from './ui';

describe('SectionHead', () => {
  it('is a level-2 heading, so every panel is a stop in the page outline', () => {
    render(<SectionHead label="players" aside={<span>22 columns</span>} parity="x.y" />);
    expect(screen.getByRole('heading', { level: 2, name: 'players' })).toBeInTheDocument();
    expect(screen.getByText('22 columns')).toBeInTheDocument();
  });
});
