import { render, screen } from '@testing-library/react';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { MemoryRouter, Route, Routes } from 'react-router';
import { describe, expect, it } from 'vitest';
import { NotFound } from './NotFound';

describe('NotFound', () => {
  it('names the path, offers three places to go and the finder', () => {
    render(
      <QueryClientProvider client={new QueryClient()}>
        <MemoryRouter initialEntries={['/sessionz/42']}>
          <Routes><Route path="*" element={<NotFound />} /></Routes>
        </MemoryRouter>
      </QueryClientProvider>,
    );
    expect(screen.getByText('404 · no such page')).toBeInTheDocument();
    expect(screen.getByText('/sessionz/42')).toBeInTheDocument();
    const nav = screen.getByRole('navigation', { name: 'Where to go instead' });
    expect(nav.querySelectorAll('a')).toHaveLength(3);
    expect(screen.getByLabelText('Find a player')).toBeInTheDocument();
  });
});
