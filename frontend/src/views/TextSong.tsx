import { useState } from 'react';
import { createProject, errorText, postJSON } from '../api';
import { addToLibrary } from '../library';
import type { ModeCapability, MusicTake, ViewId } from '../types';
import Icon from '../ui/Icon';
import WaveformPlayer from '../ui/WaveformPlayer';
import { Card, DownloadLinks, Field, Notice, Segmented, Spinner, Toggle } from '../ui/controls';

const GENRES = ['pop', 'ballad', 'rnb', 'rock', 'edm', 'lofi'];

export default function TextSong({ capability, projectId, onProject, onNavigate }: { capability?: ModeCapability; projectId: string; onProject: (id: string) => void; onNavigate: (view: ViewId) => void }) {
  const [lyrics, setLyrics] = useState('');
  const [genre, setGenre] = useState('pop');
  const [duration, setDuration] = useState(60);
  const [reviewed, setReviewed] = useState(false);
  const [consent, setConsent] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');
  const [take, setTake] = useState<MusicTake | null>(null);
  const enabled = Boolean(capability?.enabled);
  const lines = lyrics.split('\n').filter(line => line.trim()).length;

  async function create() {
    setBusy(true); setError(''); setTake(null);
    try {
      const pid = projectId || await createProject('create');
      if (!projectId) onProject(pid);
      const data = await postJSON<MusicTake>(`/api/projects/${pid}/creator/text-music`, { prompt: '', lyrics, genre, duration_s: duration, generation_method: 'provider', provider_consent: consent }, 'Không sinh được bài hát.');
      setTake(data);
      addToLibrary({ kind: 'text_song', title: lyrics.split('\n')[0].slice(0, 60) || 'Bài hát', subtitle: `${genre} · ElevenLabs`, audioUrl: data.audio_url, peaks: data.peaks, downloads: [{ label: 'WAV', href: `${data.audio_url}/download/wav` }, { label: 'MP3', href: `${data.audio_url}/download/mp3` }] });
    } catch (e) {
      setError(errorText(e));
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="split">
      <div className="column">
        {!enabled && (
          <Card className="callout">
            <h3><Icon name="info" size={18} /> Text to Song cần nhà cung cấp AI</h3>
            <p>Hát lời thành ca khúc cần một mô hình sinh giọng hát (ElevenLabs Music). {capability?.reason}</p>
            <ol className="steps">
              <li>Sao chép <code>backend/.env.example</code> thành <code>backend/.env</code></li>
              <li>Điền <code>MIXVERSE_MUSIC_PROVIDER=elevenlabs</code> và <code>ELEVENLABS_API_KEY</code></li>
              <li>Khởi động lại backend</li>
            </ol>
            <button type="button" className="button secondary" onClick={() => onNavigate('text_music')}>
              <Icon name="piano" size={16} /> Trong lúc chờ: tạo nhạc nền miễn phí bằng engine local <Icon name="arrow" size={16} />
            </button>
          </Card>
        )}
        <Card title="Lời bài hát" step="01">
          <Field label="Lời của bạn" htmlFor="lyrics" hint={`${lines} dòng · ${lyrics.length} / 4.000`}>
            <textarea id="lyrics" className="tall" value={lyrics} maxLength={4000} onChange={e => { setLyrics(e.target.value); setReviewed(false); }} placeholder={'[Verse]\nNhập lời bài hát của bạn…\n\n[Chorus]\n…'} />
          </Field>
          <p className="hint">Mẹo: dùng nhãn [Verse], [Chorus], [Bridge] để chia đoạn rõ ràng.</p>
        </Card>
        <Card title="Phong cách" step="02">
          <Field label="Thể loại">
            <Segmented label="Thể loại" value={genre} onChange={setGenre} options={GENRES.map(g => ({ value: g, label: g.toUpperCase() }))} />
          </Field>
          <Field label="Thời lượng">
            <Segmented label="Thời lượng" value={duration} onChange={setDuration} options={[30, 60, 90, 120].map(d => ({ value: d, label: `${d}s` }))} />
          </Field>
        </Card>
        <Card title="Gửi đến provider" step="03">
          <div className="checklist">
            <button type="button" className={`button ${reviewed ? 'ghost' : 'secondary'}`} disabled={!lyrics.trim()} onClick={() => setReviewed(true)}>
              <Icon name="check" size={16} /> {reviewed ? 'Đã duyệt lời' : 'Duyệt lời'}
            </button>
            <Toggle checked={consent} onChange={setConsent} label="Tôi đồng ý gửi lời này đến nhà cung cấp nhạc bên ngoài" hint="Provider được gọi một lần cho mỗi lần tạo và có thể phát sinh chi phí." />
          </div>
          {!reviewed && lyrics.trim() && <p className="hint">Cần duyệt lời sau lần chỉnh sửa cuối cùng.</p>}
          <button type="button" className="button primary large" disabled={!enabled || busy || !lyrics.trim() || !reviewed || !consent} onClick={() => void create()}>
            {busy ? <><Spinner /> Đang sinh bài hát…</> : <><Icon name="music" /> Sinh bài hát</>}
          </button>
        </Card>
      </div>
      <div className="column results">
        <Card title="Kết quả">
          {error && <Notice tone="error">{error}</Notice>}
          {take ? (
            <>
              <WaveformPlayer src={take.audio_url} peaks={take.peaks} title="Bài hát của bạn" />
              <DownloadLinks links={[{ label: 'WAV', href: `${take.audio_url}/download/wav`, primary: true }, { label: 'MP3', href: `${take.audio_url}/download/mp3` }]} />
              {take.metadata.warning && <p className="hint">{take.metadata.warning}</p>}
            </>
          ) : !error && (
            <div className="empty"><b>Bài hát sẽ xuất hiện ở đây</b><p>Lời được gửi đúng một lần sau khi bạn duyệt và đồng ý.</p></div>
          )}
        </Card>
      </div>
    </div>
  );
}
