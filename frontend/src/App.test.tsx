import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { cleanup, fireEvent, render, screen, waitFor, within } from '@testing-library/react';
import App from './App';

const options = {
  genres: [{ id: 'lofi', label: 'Lofi', bpm: 80 }, { id: 'trap', label: 'Trap', bpm: 140 }],
  moods: [{ id: 'chill', label: 'Chill' }, { id: 'sad', label: 'Buồn' }],
  instruments: [{ id: 'piano', label: 'Piano' }, { id: 'bass', label: 'Bass' }],
  ambiences: [{ id: 'none', label: 'Không' }, { id: 'rain', label: 'Tiếng mưa' }],
  keys: ['C', 'C#', 'D', 'A'],
};
const recipe = { genre: 'lofi', mood: 'chill', bpm: 80, key: 'C', mode: 'major', duration_s: 30, instruments: ['piano', 'bass'], drums: true, drums_entry: 'start', melody: true, ambience: 'rain' };

function take(i: number) {
  const root = `/api/projects/p1/creator/compositions/m_${i}`;
  return {
    composition_id: `m_${i}`,
    audio_url: `/api/projects/p1/creator/previews/text_music_${i}.wav`,
    peaks: [0.1, 0.5, 1, 0.4],
    midi_url: `${root}/midi`,
    stems_url: `${root}/stems.zip`,
    stems: [{ id: 'drums', label: 'Trống', url: `${root}/stems/drums` }],
    metadata: { label: `Phương án ${i + 1} · Dm7 – G7`, key: 'C major', bpm: 80, duration_s: 30, progression: ['Dm7', 'G7', 'Cmaj7', 'Am7'], sections: [{ label: 'intro', name: 'Intro', start_bar: 0, bars: 2, energy: .3, chords: ['Cmaj7'] }, { label: 'chorus', name: 'Chorus', start_bar: 2, bars: 6, energy: 1, chords: ['Dm7'] }], parts: [{ part: 'chords', instrument: 'piano', stem: 'harmony' }], warning: 'Sáng tác bằng engine nhạc local, chưa phải mô hình sinh nhạc AI.' },
  };
}

type Caps = Record<string, { enabled: boolean; reason?: string; provider_enabled?: boolean; provider_reason?: string }>;

function mockApi(modes: Caps = { text_music: { enabled: true, provider_enabled: false, provider_reason: 'Cấu hình ELEVENLABS_API_KEY.' } }) {
  const fetchMock = vi.fn((url: string, init?: RequestInit) => {
    const ok = (body: unknown) => Promise.resolve({ ok: true, json: () => Promise.resolve(body) });
    if (url === '/api/creator/capabilities') return ok({ modes });
    if (url === '/api/health') return ok({ ok: true });
    if (url === '/api/creator/music-options') return ok(options);
    if (url === '/api/creator/recipe') {
      const prompt = JSON.parse(String(init?.body)).prompt as string;
      const detected = prompt.includes('mưa')
        ? [{ kind: 'genre', label: 'Lofi', source: 'lofi' }, { kind: 'ambience', label: 'Tiếng mưa', source: 'mưa' }]
        : [{ kind: 'genre', label: 'Lofi', source: 'mặc định' }];
      return ok({ recipe, detected, notes: [] });
    }
    if (url === '/api/projects') return ok({ id: 'p1' });
    if (url === '/api/projects/p1/creator/text-music') return ok({ takes: [take(0), take(1), take(2)] });
    return Promise.resolve({ ok: false, json: () => Promise.resolve({ detail: 'not mocked' }) });
  });
  vi.stubGlobal('fetch', fetchMock);
  return fetchMock;
}

beforeEach(() => { localStorage.clear(); window.location.hash = ''; });
afterEach(() => { cleanup(); vi.unstubAllGlobals(); });

describe('MIXVERSE studio shell', () => {
  it('lists every workflow and labels the local engine honestly', async () => {
    mockApi();
    render(<App />);
    const nav = screen.getByRole('navigation', { name: 'Chức năng' });
    for (const name of ['Text to Music', 'Text to Song', 'Rap to Beat', 'Sound to Music', 'Remix', 'Mashup', 'Thư viện']) {
      expect(within(nav).getByRole('button', { name: new RegExp(name) })).toBeInTheDocument();
    }
    expect(await screen.findByText(/Backend sẵn sàng/)).toBeInTheDocument();
    expect(screen.getByText(/không phải AI, chạy offline/)).toBeInTheDocument();
  });

  it('keeps paid provider generation disabled without provider config', async () => {
    mockApi();
    render(<App />);
    const provider = await screen.findByRole('radio', { name: /AI Provider.*chưa cấu hình/ });
    expect(provider).toBeDisabled();
    expect(screen.getByText(/Cấu hình ELEVENLABS_API_KEY/)).toBeInTheDocument();
  });

  it('shows what the prompt was understood as', async () => {
    mockApi();
    render(<App />);
    fireEvent.change(screen.getByLabelText('Mô tả bản nhạc'), { target: { value: 'lofi đêm mưa' } });
    expect(await screen.findByText('Tiếng mưa', { selector: '.tag' }, { timeout: 2000 })).toBeInTheDocument();
    expect(screen.getByText(/MIXVERSE hiểu là/)).toBeInTheDocument();
  });

  it('explains and blocks generation when the mode is unavailable', async () => {
    mockApi({ text_music: { enabled: false, reason: 'Engine tạm tắt để bảo trì.' } });
    render(<App />);
    expect(await screen.findByText('Engine tạm tắt để bảo trì.')).toBeInTheDocument();
    expect(screen.getByRole('button', { name: /Sáng tác bản nhạc/ })).toBeDisabled();
  });

  it('creates three takes with stems/MIDI downloads and saves them to the library', async () => {
    const fetchMock = mockApi();
    render(<App />);
    const create = screen.getByRole('button', { name: /Sáng tác bản nhạc/ });
    await waitFor(() => expect(create).toBeEnabled());
    fireEvent.click(create);
    expect(await screen.findByRole('tab', { name: /Phương án 2/ })).toBeInTheDocument();
    const body = JSON.parse(String(fetchMock.mock.calls.find(([url]) => url === '/api/projects/p1/creator/text-music')![1]!.body));
    expect(body).toMatchObject({ generation_method: 'loops', takes: 3, recipe: { genre: 'lofi' } });
    expect(screen.getByRole('link', { name: /MIDI/ })).toHaveAttribute('href', '/api/projects/p1/creator/compositions/m_0/midi');
    expect(screen.getByRole('link', { name: /Stems/ })).toHaveAttribute('href', '/api/projects/p1/creator/compositions/m_0/stems.zip');
    expect(screen.getByText('Chorus')).toBeInTheDocument();

    fireEvent.click(screen.getByRole('button', { name: /Thư viện/ }));
    expect(await screen.findByText('3 bản nhạc')).toBeInTheDocument();
    expect(screen.getAllByText(/Lofi · C major · 80 BPM/)).toHaveLength(3);
  });

  it('guides Text to Song users to the free local engine when no provider is set', async () => {
    mockApi({ text_music: { enabled: true }, text_song: { enabled: false, reason: 'Chưa cấu hình provider.' } });
    window.location.hash = '#text_song';
    render(<App />);
    expect(await screen.findByText(/Text to Song cần nhà cung cấp AI/)).toBeInTheDocument();
    expect(screen.getByRole('button', { name: /Sinh bài hát/ })).toBeDisabled();
    fireEvent.click(screen.getByRole('button', { name: /tạo nhạc nền miễn phí/ }));
    expect(await screen.findByLabelText('Mô tả bản nhạc')).toBeInTheDocument();
  });
});
