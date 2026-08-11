/**
 * Component tests for SiteBanner — the site-wide announcement banner shown
 * to every visitor (see banner.store.ts for the underlying state).
 *
 * Covers:
 *  - Renders nothing when inactive, or active with no message
 *  - Renders the message when active
 *  - Sets/clears the --site-banner-height CSS variable used by full-bleed
 *    pages (FamilyTreePage/DiscoverTreePage) to offset themselves
 *  - Dismiss hides the banner for the current message, but is deliberately
 *    NOT persisted anywhere (no sessionStorage/localStorage) — it's a
 *    "not right now" for this page load, not "never again": a fresh
 *    mount (reload/next visit) always shows an active banner again, and a
 *    changed message reappears immediately even without a reload
 *  - Uses custom bg/text colors when set, falls back to the built-in
 *    defaults when null
 */
import React from 'react';
import { render, screen, waitFor, act } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { SiteBanner, DEFAULT_BANNER_BG_COLOR, DEFAULT_BANNER_TEXT_COLOR } from '@shared/components/layout/SiteBanner';
import { useBannerStore } from '@store/banner.store';
import '../../i18n';

vi.mock('@store/banner.store', async () => {
  const actual = await vi.importActual<typeof import('@store/banner.store')>('@store/banner.store');
  return { ...actual, checkBannerStatus: vi.fn() };
});

// jsdom does not implement ResizeObserver.
class MockResizeObserver {
  observe() {}
  unobserve() {}
  disconnect() {}
}
(global as any).ResizeObserver = MockResizeObserver;

beforeEach(() => {
  useBannerStore.setState({ active: false, message: '', bgColor: null, textColor: null, isLoaded: true });
  document.documentElement.style.removeProperty('--site-banner-height');
});

describe('SiteBanner', () => {
  it('renders nothing when inactive', () => {
    useBannerStore.setState({ active: false, message: 'Ignored while inactive' });
    const { container } = render(<SiteBanner />);
    expect(container).toBeEmptyDOMElement();
  });

  it('renders nothing when active but the message is empty', () => {
    useBannerStore.setState({ active: true, message: '' });
    const { container } = render(<SiteBanner />);
    expect(container).toBeEmptyDOMElement();
  });

  it('renders the message when active with a message', () => {
    useBannerStore.setState({ active: true, message: 'We will be down soon' });
    render(<SiteBanner />);
    expect(screen.getByText('We will be down soon')).toBeInTheDocument();
  });

  it('sets --site-banner-height to 0px when inactive', () => {
    useBannerStore.setState({ active: false, message: '' });
    render(<SiteBanner />);
    expect(document.documentElement.style.getPropertyValue('--site-banner-height')).toBe('0px');
  });

  it('sets a non-zero --site-banner-height when visible', async () => {
    useBannerStore.setState({ active: true, message: 'Hello' });
    render(<SiteBanner />);
    await waitFor(() => {
      expect(document.documentElement.style.getPropertyValue('--site-banner-height')).not.toBe('');
    });
  });

  it('dismiss hides the banner for the current message', async () => {
    const user = userEvent.setup();
    useBannerStore.setState({ active: true, message: 'Same message' });
    render(<SiteBanner />);

    await user.click(screen.getByRole('button', { name: /dismiss/i }));
    expect(screen.queryByText('Same message')).not.toBeInTheDocument();
  });

  it('dismiss persists across re-renders of the same mounted instance (e.g. SPA navigation)', async () => {
    const user = userEvent.setup();
    useBannerStore.setState({ active: true, message: 'Same message' });
    const { rerender } = render(<SiteBanner />);
    await user.click(screen.getByRole('button', { name: /dismiss/i }));

    rerender(<SiteBanner />);
    expect(screen.queryByText('Same message')).not.toBeInTheDocument();
  });

  it('a dismissed banner reappears on the next mount (reload/next visit) — dismissal is not persisted', async () => {
    const user = userEvent.setup();
    useBannerStore.setState({ active: true, message: 'Same message' });
    const { unmount } = render(<SiteBanner />);
    await user.click(screen.getByRole('button', { name: /dismiss/i }));
    unmount();

    render(<SiteBanner />);
    expect(screen.getByText('Same message')).toBeInTheDocument();
  });

  it('a changed message reappears immediately even without remounting', async () => {
    const user = userEvent.setup();
    useBannerStore.setState({ active: true, message: 'First message' });
    render(<SiteBanner />);
    await user.click(screen.getByRole('button', { name: /dismiss/i }));
    expect(screen.queryByText('First message')).not.toBeInTheDocument();

    act(() => {
      useBannerStore.setState({ active: true, message: 'Second message' });
    });
    expect(await screen.findByText('Second message')).toBeInTheDocument();
  });

  it('uses the built-in default colors when none are configured', () => {
    useBannerStore.setState({ active: true, message: 'Hello', bgColor: null, textColor: null });
    render(<SiteBanner />);
    const banner = screen.getByText('Hello').parentElement as HTMLElement;
    expect(banner).toHaveStyle({ background: DEFAULT_BANNER_BG_COLOR, color: DEFAULT_BANNER_TEXT_COLOR });
  });

  it('uses the configured custom colors when set', () => {
    useBannerStore.setState({ active: true, message: 'Hello', bgColor: '#112233', textColor: '#eeeeee' });
    render(<SiteBanner />);
    const banner = screen.getByText('Hello').parentElement as HTMLElement;
    expect(banner).toHaveStyle({ background: '#112233', color: '#eeeeee' });
  });
});
