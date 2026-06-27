import React from 'react';
import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';

vi.stubEnv('VITE_GOOGLE_CLIENT_ID', 'test-google-id');

const { OAuthButtons } = await import('@features/auth/components/OAuthButtons');

// Capture window.location.href assignments
const locationHrefSpy = vi.fn();
Object.defineProperty(window, 'location', {
  writable: true,
  value: {
    ...window.location,
    href: '',
    pathname: '/login',
    search: '',
    set href(url: string) {
      locationHrefSpy(url);
    },
    get href() {
      return '';
    },
  },
});

describe('OAuthButtons', () => {
  const user = userEvent.setup({ delay: null });

  beforeEach(() => {
    locationHrefSpy.mockReset();
  });

  it('renders the Google sign-in button', () => {
    render(<OAuthButtons />);
    expect(screen.getByText('Continue with Google')).toBeInTheDocument();
  });

  it('renders a button element (not a link)', () => {
    render(<OAuthButtons />);
    const btn = screen.getByText('Continue with Google');
    expect(btn.closest('button')).toBeInTheDocument();
  });

  it('redirects to backend OAuth endpoint on click', async () => {
    render(<OAuthButtons next="/dashboard" />);
    await user.click(screen.getByText('Continue with Google'));

    expect(locationHrefSpy).toHaveBeenCalledTimes(1);
    const url = locationHrefSpy.mock.calls[0][0];
    expect(url).toContain('/api/v1/auth/oauth/google');
    expect(url).toContain('next=');
    expect(url).toContain(encodeURIComponent('/dashboard'));
  });

  it('uses current path as next when next prop is not provided', async () => {
    render(<OAuthButtons />);
    await user.click(screen.getByText('Continue with Google'));

    expect(locationHrefSpy).toHaveBeenCalledTimes(1);
    const url = locationHrefSpy.mock.calls[0][0];
    expect(url).toContain('next=');
  });

  it('renders the divider label', () => {
    render(<OAuthButtons dividerLabel="or continue with" />);
    expect(screen.getByText('or continue with')).toBeInTheDocument();
  });

  it('hides divider when dividerLabel is empty', () => {
    render(<OAuthButtons dividerLabel="" />);
    expect(screen.queryByText('or')).not.toBeInTheDocument();
  });

  it('accepts custom className', () => {
    const { container } = render(<OAuthButtons className="custom-class" />);
    expect(container.firstChild).toHaveClass('custom-class');
  });
});
