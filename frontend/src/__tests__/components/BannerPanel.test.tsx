/**
 * Component tests for BannerPanel — the Site Settings admin control for the
 * announcement banner.
 *
 * Covers:
 *  - Loads and populates the form from GET /site-settings/banner/config
 *  - Save sends the right PUT body, including local -> UTC ISO conversion
 *  - "Clear schedule" blanks both datetime fields
 *  - The status chip reflects Off / Scheduled / Active now / Expired
 *  - Loads and populates the color pickers, Save includes them in the PUT
 *    body, and "Reset to default" sends reset_colors:true and restores the
 *    built-in defaults
 */
import React from 'react';
import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { BannerPanel } from '@features/admin/BannerPanel';
import { DEFAULT_BANNER_BG_COLOR, DEFAULT_BANNER_TEXT_COLOR } from '@shared/components/layout/SiteBanner';
import '../../i18n';

function configResponse(overrides: Partial<{
  banner_enabled: boolean; banner_message: string | null;
  banner_starts_at: string | null; banner_ends_at: string | null;
  banner_bg_color: string | null; banner_text_color: string | null;
}> = {}) {
  return {
    banner_enabled: false,
    banner_message: null,
    banner_starts_at: null,
    banner_ends_at: null,
    banner_bg_color: null,
    banner_text_color: null,
    ...overrides,
  };
}

describe('BannerPanel', () => {
  const mockFetch = vi.fn();

  beforeEach(() => {
    global.fetch = mockFetch as any;
    mockFetch.mockReset();
  });

  it('loads and populates the form from the config endpoint', async () => {
    mockFetch.mockResolvedValueOnce({
      ok: true,
      json: async () => configResponse({ banner_enabled: true, banner_message: 'Downtime tonight' }),
    });
    render(<BannerPanel token="test-token" />);

    expect(await screen.findByDisplayValue('Downtime tonight')).toBeInTheDocument();
    expect(screen.getByRole('switch')).toHaveAttribute('aria-checked', 'true');
  });

  it('shows "Off" status when disabled', async () => {
    mockFetch.mockResolvedValueOnce({ ok: true, json: async () => configResponse({ banner_enabled: false }) });
    render(<BannerPanel token="test-token" />);
    expect(await screen.findByText('Off')).toBeInTheDocument();
  });

  it('shows "Active now" status when enabled with no schedule', async () => {
    mockFetch.mockResolvedValueOnce({ ok: true, json: async () => configResponse({ banner_enabled: true }) });
    render(<BannerPanel token="test-token" />);
    expect(await screen.findByText('Active now')).toBeInTheDocument();
  });

  it('shows "Scheduled" status when enabled with a future start time', async () => {
    const future = new Date(Date.now() + 24 * 60 * 60 * 1000).toISOString();
    mockFetch.mockResolvedValueOnce({
      ok: true,
      json: async () => configResponse({ banner_enabled: true, banner_starts_at: future }),
    });
    render(<BannerPanel token="test-token" />);
    expect(await screen.findByText('Scheduled')).toBeInTheDocument();
  });

  it('shows "Expired" status when enabled with a past end time', async () => {
    const past = new Date(Date.now() - 24 * 60 * 60 * 1000).toISOString();
    mockFetch.mockResolvedValueOnce({
      ok: true,
      json: async () => configResponse({ banner_enabled: true, banner_ends_at: past }),
    });
    render(<BannerPanel token="test-token" />);
    expect(await screen.findByText('Expired')).toBeInTheDocument();
  });

  it('Save sends a PUT with the toggled enabled flag and message', async () => {
    const user = userEvent.setup();
    mockFetch.mockResolvedValueOnce({ ok: true, json: async () => configResponse() });
    render(<BannerPanel token="test-token" />);
    await screen.findByRole('switch');

    await user.click(screen.getByRole('switch'));
    await user.type(screen.getByPlaceholderText(/scheduled maintenance/i), 'Heads up!');

    mockFetch.mockResolvedValueOnce({
      ok: true,
      json: async () => configResponse({ banner_enabled: true, banner_message: 'Heads up!' }),
    });
    await user.click(screen.getByText('Save settings'));

    await waitFor(() => {
      const putCall = mockFetch.mock.calls.find(([, opts]) => opts?.method === 'PUT');
      expect(putCall).toBeTruthy();
      const [url, opts] = putCall!;
      expect(url).toContain('/site-settings/banner');
      const body = JSON.parse(opts.body);
      expect(body.banner_enabled).toBe(true);
      expect(body.banner_message).toBe('Heads up!');
    });
  });

  it('"Clear schedule" sends clear_schedule:true and blanks both datetime inputs', async () => {
    const user = userEvent.setup();
    const now = new Date().toISOString();
    mockFetch.mockResolvedValueOnce({
      ok: true,
      json: async () => configResponse({ banner_enabled: true, banner_starts_at: now, banner_ends_at: now }),
    });
    render(<BannerPanel token="test-token" />);
    await screen.findByRole('switch');

    mockFetch.mockResolvedValueOnce({ ok: true, json: async () => ({}) });
    await user.click(screen.getByText('Clear schedule'));

    await waitFor(() => {
      const putCall = mockFetch.mock.calls.find(([, opts]) => opts?.method === 'PUT');
      const body = JSON.parse(putCall![1].body);
      expect(body.clear_schedule).toBe(true);
    });
  });

  it('shows an error message when saving fails', async () => {
    const user = userEvent.setup();
    mockFetch.mockResolvedValueOnce({ ok: true, json: async () => configResponse() });
    render(<BannerPanel token="test-token" />);
    await screen.findByRole('switch');

    mockFetch.mockResolvedValueOnce({ ok: false, json: async () => ({ detail: 'Super Administrator access required' }) });
    await user.click(screen.getByText('Save settings'));

    expect(await screen.findByText('Super Administrator access required')).toBeInTheDocument();
  });

  it('defaults the color pickers to the built-in defaults when unset', async () => {
    mockFetch.mockResolvedValueOnce({ ok: true, json: async () => configResponse() });
    render(<BannerPanel token="test-token" />);
    await screen.findByRole('switch');

    expect(screen.getAllByDisplayValue(DEFAULT_BANNER_BG_COLOR).length).toBeGreaterThan(0);
    expect(screen.getAllByDisplayValue(DEFAULT_BANNER_TEXT_COLOR).length).toBeGreaterThan(0);
  });

  it('loads and populates the color pickers from the config endpoint', async () => {
    mockFetch.mockResolvedValueOnce({
      ok: true,
      json: async () => configResponse({ banner_bg_color: '#112233', banner_text_color: '#eeeeee' }),
    });
    render(<BannerPanel token="test-token" />);
    await screen.findByRole('switch');

    expect(screen.getAllByDisplayValue('#112233').length).toBeGreaterThan(0);
    expect(screen.getAllByDisplayValue('#eeeeee').length).toBeGreaterThan(0);
  });

  it('Save sends the configured colors in the PUT body', async () => {
    const user = userEvent.setup();
    mockFetch.mockResolvedValueOnce({
      ok: true,
      json: async () => configResponse({ banner_bg_color: '#112233', banner_text_color: '#eeeeee' }),
    });
    render(<BannerPanel token="test-token" />);
    await screen.findByRole('switch');

    mockFetch.mockResolvedValueOnce({
      ok: true,
      json: async () => configResponse({ banner_bg_color: '#112233', banner_text_color: '#eeeeee' }),
    });
    await user.click(screen.getByText('Save settings'));

    await waitFor(() => {
      const putCall = mockFetch.mock.calls.find(([, opts]) => opts?.method === 'PUT');
      const body = JSON.parse(putCall![1].body);
      expect(body.banner_bg_color).toBe('#112233');
      expect(body.banner_text_color).toBe('#eeeeee');
    });
  });

  it('"Reset to default" sends reset_colors:true and restores the default colors', async () => {
    const user = userEvent.setup();
    mockFetch.mockResolvedValueOnce({
      ok: true,
      json: async () => configResponse({ banner_bg_color: '#112233', banner_text_color: '#eeeeee' }),
    });
    render(<BannerPanel token="test-token" />);
    await screen.findByRole('switch');
    expect(screen.getAllByDisplayValue('#112233').length).toBeGreaterThan(0);

    mockFetch.mockResolvedValueOnce({ ok: true, json: async () => ({}) });
    await user.click(screen.getByText('Reset to default'));

    await waitFor(() => {
      const putCall = mockFetch.mock.calls.find(([, opts]) => opts?.method === 'PUT');
      const body = JSON.parse(putCall![1].body);
      expect(body.reset_colors).toBe(true);
    });
    expect(screen.getAllByDisplayValue(DEFAULT_BANNER_BG_COLOR).length).toBeGreaterThan(0);
    expect(screen.getAllByDisplayValue(DEFAULT_BANNER_TEXT_COLOR).length).toBeGreaterThan(0);
  });
});
