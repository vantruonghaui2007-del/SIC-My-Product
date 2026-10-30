import { afterEach, expect, it, vi } from 'vitest';
import { cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react';
import TextSong from './views/TextSong';
import TextMusic from './views/TextMusic';

afterEach(() => { cleanup(); localStorage.clear(); vi.unstubAllGlobals(); });

const google = { enabled: true, provider_enabled: true, provider: 'google', provider_label: 'Google AI · Lyria', provider_access_required: true };
const recipe = { genre: 'lofi', mood: 'chill', bpm: 80, key: 'C', mode: 'major', duration_s: 30, instruments: ['piano'], drums: true, drums_entry: 'start', melody: true, ambience: 'none' };

function mockApi() {
  const calls: { url: string; body: Record<string, unknown> }[] = [];
  vi.stubGlobal('fetch', vi.fn(async (url: string, init?: RequestInit) => {
    const body = init?.body ? JSON.parse(String(init.body)) : {};
    if (url.endsWith('/text-music')) calls.push({ url, body });
    const result = url === '/api/creator/recipe' ? { recipe, detected: [], notes: [] }
      : url === '/api/creator/music-options' ? { genres: [], moods: [], instruments: [], ambiences: [], keys: ['C'] }
      : { audio_url: '/api/result.wav', metadata: { provider: 'google', duration_s: 30 }, peaks: [.1] };
    return { ok: true, json: async () => result };
  }));
  return calls;
}

it('requires Google song consent and access code, then credits Google in library', async () => {
  const calls = mockApi();
  render(<TextSong capability={google} projectId="p1" onProject={() => {}} onNavigate={() => {}} />);
  fireEvent.change(screen.getByLabelText('Lời của bạn'), { target: { value: 'Xin chào Việt Nam' } });
  fireEvent.click(screen.getByRole('button', { name: 'Duyệt lời' }));
  fireEvent.click(screen.getByRole('checkbox', { name: /đồng ý.*Google/i }));
  expect(screen.getByRole('button', { name: 'Sinh bài hát' })).toBeDisabled();
  fireEvent.change(screen.getByLabelText('Mã truy cập AI'), { target: { value: 'owner-code' } });
  fireEvent.click(screen.getByRole('button', { name: 'Sinh bài hát' }));
  expect(await screen.findByRole('link', { name: 'WAV' })).toHaveAttribute('href', '/api/result.wav/download/wav');
  expect(calls).toHaveLength(1);
  expect(calls[0].body).toMatchObject({ provider_consent: true, provider_access_token: 'owner-code', lyrics: 'Xin chào Việt Nam' });
  const stored = Object.values(localStorage).join('');
  expect(stored).toContain('Google');
  expect(stored).not.toContain('owner-code');
  expect(stored).not.toContain('ElevenLabs');
});

it('uses Google consent and credits for instrumental generation', async () => {
  const calls = mockApi();
  render(<TextMusic capability={google} projectId="p1" onProject={() => {}} />);
  fireEvent.change(screen.getByLabelText('Mô tả bản nhạc'), { target: { value: 'lofi piano' } });
  await waitFor(() => expect(screen.getByRole('button', { name: /Sáng tác bản nhạc/ })).toBeEnabled());
  fireEvent.click(screen.getByRole('radio', { name: /AI Provider/ }));
  fireEvent.click(screen.getByRole('checkbox', { name: /đồng ý.*Google/i }));
  fireEvent.change(screen.getByLabelText('Mã truy cập AI'), { target: { value: 'owner-code' } });
  fireEvent.click(screen.getByRole('button', { name: 'Sinh nhạc bằng AI' }));
  expect(await screen.findByRole('link', { name: 'WAV' })).toBeInTheDocument();
  expect(calls).toHaveLength(1);
  expect(calls[0].body).toMatchObject({ generation_method: 'provider', provider_access_token: 'owner-code', prompt: 'lofi piano' });
  expect(Object.values(localStorage).join('')).toContain('Google');
  expect(Object.values(localStorage).join('')).not.toContain('owner-code');
});
