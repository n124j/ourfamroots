/**
 * Component tests for UserAvatar.
 */
import React from 'react';
import { render, screen } from '@testing-library/react';
import { UserAvatar } from '@shared/components/UserAvatar';

describe('UserAvatar', () => {
  it('renders initials when no avatar URL is provided', () => {
    render(<UserAvatar displayName="Alice Smith" />);
    expect(screen.getByText('AS')).toBeInTheDocument();
  });

  it('renders single initial for single-word name', () => {
    render(<UserAvatar displayName="Alice" />);
    expect(screen.getByText('A')).toBeInTheDocument();
  });

  it('falls back to email initial when no displayName', () => {
    render(<UserAvatar email="bob@example.com" />);
    expect(screen.getByText('B')).toBeInTheDocument();
  });

  it('falls back to ? when neither displayName nor email', () => {
    render(<UserAvatar />);
    expect(screen.getByText('?')).toBeInTheDocument();
  });

  it('renders an img when avatarUrl is provided', () => {
    render(<UserAvatar avatarUrl="https://example.com/pic.jpg" displayName="Alice" />);
    const img = screen.getByRole('presentation');
    expect(img).toHaveAttribute('src', 'https://example.com/pic.jpg');
    expect(img).toHaveAttribute('referrerPolicy', 'no-referrer');
  });

  it('does not render img when avatarUrl is null', () => {
    render(<UserAvatar avatarUrl={null} displayName="Alice" />);
    expect(screen.queryByRole('img')).not.toBeInTheDocument();
    expect(screen.getByText('A')).toBeInTheDocument();
  });

  it('applies sm size classes', () => {
    const { container } = render(<UserAvatar displayName="A" size="sm" />);
    const wrapper = container.firstChild as HTMLElement;
    expect(wrapper.className).toContain('w-8');
    expect(wrapper.className).toContain('h-8');
  });

  it('applies md size classes by default', () => {
    const { container } = render(<UserAvatar displayName="A" />);
    const wrapper = container.firstChild as HTMLElement;
    expect(wrapper.className).toContain('w-10');
    expect(wrapper.className).toContain('h-10');
  });

  it('applies lg size classes', () => {
    const { container } = render(<UserAvatar displayName="A" size="lg" />);
    const wrapper = container.firstChild as HTMLElement;
    expect(wrapper.className).toContain('w-16');
    expect(wrapper.className).toContain('h-16');
  });

  it('truncates initials to 2 characters', () => {
    render(<UserAvatar displayName="Alice Bob Charlie" />);
    expect(screen.getByText('AB')).toBeInTheDocument();
  });
});
