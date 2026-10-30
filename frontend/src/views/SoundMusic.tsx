import { useState } from 'react';
import { createProject, errorText, postJSON, upload } from '../api';
import { addToLibrary } from '../library';
import type { ModeCapability, MusicTake } from '../types';
import Icon from '../ui/Icon';
import WaveformPlayer from '../ui/WaveformPlayer';
import { Card, DownloadLinks, Dropzone, Field, Notice, Segmented, Spinner, Toggle } from '../ui/controls';

export default function SoundMusic({ capability, projectId, onProject }: { capability?: ModeCapability; projectId: string; onProject: (id: string) => void }) {
  const [file, setFile] = useState<File | null>(null);
  const [rights, setRights] = useState(false);
  const [role, setRole] = useState<'percussion' | 'texture'>('percussion');
  const [bpm, setBpm] = useState(100);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');
  const [take, setTake] = useState<MusicTake | null>(null);

  async function create() {
    if (!file) return;
    setBusy(true); setError(''); setTake(null);
    try {
      const pid = projectId || await createProject('create');
      if (!projectId) onProject(pid);
      const form = new FormData();
      form.set('file', file); form.set('kind', 'sound'); form.set('rights_confirmed', 'true');
      const asset = await upload<{ id: string }>(`/api/projects/${pid}/creator/assets`, form, 'Không tải được âm thanh.');
      const data = await postJSON<MusicTake>(`/api/projects/${pid}/creator/sounds/${asset.id}/preview`, { bpm, role }, 'Không tạo được bản nghe thử.');
      setTake(data);
      addToLibrary({ kind: 'sound_music', title: `${file.name} · ${role === 'percussion' ? 'Percussion' : 'Texture'}`, subtitle: `${bpm} BPM`, audioUrl: data.audio_url, peaks: data.peaks, downloads: [{ label: 'WAV', href: `${data.audio_url}/download/wav` }, { label: 'MP3', href: `${data.audio_url}/download/mp3` }] });
    } catch (e) {
      setError(errorText(e));
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="split">
      <div className="column">
        <Card title="Âm thanh gốc" step="01">
          <Dropzone file={file} onFile={next => { setFile(next); setTake(null); }} hint="Tiếng gõ, tiếng động, sample 0,1–30 giây" />
          <Toggle checked={rights} onChange={setRights} label="Tôi có quyền sử dụng tệp này" />
        </Card>
        <Card title="Biến thành nhạc" step="02">
          <Field label="Vai trò của sample">
            <Segmented label="Vai trò" value={role} onChange={setRole} options={[{ value: 'percussion', label: 'Percussion — gõ theo phách' }, { value: 'texture', label: 'Texture — lớp nền lặp' }]} />
          </Field>
          <Field label="Tempo" htmlFor="sound-bpm" hint={<b className="mono">{bpm} BPM</b>}>
            <input id="sound-bpm" type="range" min={60} max={180} value={bpm} onChange={e => setBpm(Number(e.target.value))} />
          </Field>
          {capability?.reason && <p className="hint">{capability.reason}</p>}
          <button type="button" className="button primary large" disabled={!file || !rights || busy || !capability?.enabled} onClick={() => void create()}>
            {busy ? <><Spinner /> Đang dựng…</> : <><Icon name="wave" /> Tạo bản nghe thử</>}
          </button>
        </Card>
      </div>
      <div className="column results">
        <Card title="Kết quả">
          {error && <Notice tone="error">{error}</Notice>}
          {take ? (
            <>
              <WaveformPlayer src={take.audio_url} peaks={take.peaks} title={file?.name} />
              <DownloadLinks links={[{ label: 'WAV', href: `${take.audio_url}/download/wav`, primary: true }, { label: 'MP3', href: `${take.audio_url}/download/mp3` }]} />
              {take.metadata.warnings?.map(w => <p key={w} className="hint">{w}</p>)}
            </>
          ) : !error && <div className="empty"><b>Bản nghe thử sẽ xuất hiện ở đây</b><p>Sample của bạn được dùng trực tiếp, không thay bằng âm thanh khác.</p></div>}
        </Card>
      </div>
    </div>
  );
}
