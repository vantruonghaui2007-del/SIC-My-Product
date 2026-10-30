import { useEffect, useState } from 'react';
import { createProject, errorText, getJSON, postJSON, upload } from '../api';
import { addToLibrary } from '../library';
import type { ModeCapability, Project, Source, StudioClip, StudioVersion } from '../types';
import Icon from '../ui/Icon';
import WaveformPlayer from '../ui/WaveformPlayer';
import { Card, DownloadLinks, Dropzone, Field, Notice, Spinner, Toggle } from '../ui/controls';

const EXAMPLES = ['Thêm beat lofi', 'Thêm beat house 124 BPM', 'Đổi tempo sang 100 BPM', 'Thêm tiếng mưa', 'Thêm vinyl crackle', 'Giảm âm lượng beat 3 dB'];

const bpm = (value: number) => Math.round(value * 10) / 10;

function clipName(clip: StudioClip) {
  if (clip.kind === 'beat') return `Beat ${clip.style}`;
  if (clip.kind === 'ambience') return `Nền ${clip.ambience}`;
  return clip.lane;
}

export default function Studio({ mode, capability }: { mode: 'remix' | 'mashup'; capability?: ModeCapability }) {
  const slots = mode === 'mashup' ? ['A', 'B'] : ['A'];
  const [pid, setPid] = useState('');
  const [files, setFiles] = useState<Record<string, File | null>>({});
  const [sources, setSources] = useState<Source[]>([]);
  const [rights, setRights] = useState(false);
  const [versions, setVersions] = useState<StudioVersion[]>([]);
  const [current, setCurrent] = useState<StudioVersion | null>(null);
  const [prompt, setPrompt] = useState('');
  const [busy, setBusy] = useState('');
  const [error, setError] = useState('');
  const [gains, setGains] = useState<Record<string, number>>({});

  useEffect(() => {
    setGains(Object.fromEntries((current?.script.clips || []).map(c => [c.id, c.gain_db])));
  }, [current]);

  const ready = sources.length === slots.length;

  function adopt(version: StudioVersion) {
    setVersions(list => [...list.filter(v => v.id !== version.id), version]);
    setCurrent(version);
    if (version.render_file) {
      addToLibrary({ kind: 'studio', title: `${mode === 'remix' ? 'Remix' : 'Mashup'} · ${version.prompt || 'Bản gốc'}`, subtitle: version.cards.map(c => c.title).join(' · ') || `${bpm(version.script.bpm)} BPM`, audioUrl: audioUrl(pid, version.id), peaks: version.peaks, downloads: exportLinks(pid, version.id) });
    }
  }

  function audioUrl(project: string, vid: string) {
    return `/api/projects/${project}/studio/versions/${vid}/audio`;
  }

  async function uploadSources() {
    setBusy('upload'); setError('');
    try {
      const project = pid || await createProject(mode);
      setPid(project);
      const uploaded: Source[] = [...sources];
      for (const slot of slots.slice(sources.length)) {
        const file = files[slot];
        if (!file) throw new Error(`Chọn tệp cho nguồn ${slot}.`);
        const form = new FormData();
        form.set('file', file); form.set('rights_confirmed', 'true');
        uploaded.push(await upload<Source>(`/api/projects/${project}/sources/upload`, form, `Không tải được nguồn ${slot}.`));
        setSources([...uploaded]);
      }
      const state = await getJSON<Project>(`/api/projects/${project}`);
      const base = state.versions.find(v => v.id === state.head);
      const original = await postJSON<StudioVersion>(`/api/projects/${project}/studio/patch`, { mode: 'tempo', bpm: base?.script.bpm || 120, prompt: mode === 'remix' ? 'Bản gốc' : 'Ghép thô A + B' }, 'Không dựng được bản gốc.');
      setVersions([original]); setCurrent(original);
    } catch (e) {
      setError(errorText(e));
    } finally {
      setBusy('');
    }
  }

  async function applyPrompt(text = prompt) {
    if (!text.trim()) return;
    setBusy('prompt'); setError('');
    try {
      adopt(await postJSON<StudioVersion>(`/api/projects/${pid}/prompts`, { text }, 'Không áp dụng được câu lệnh.'));
      setPrompt('');
    } catch (e) {
      setError(errorText(e));
    } finally {
      setBusy('');
    }
  }

  async function editClip(clip: StudioClip, patch: { gain_db?: number; muted?: boolean }) {
    setBusy('edit'); setError('');
    try {
      adopt(await postJSON<StudioVersion>(`/api/projects/${pid}/studio/edits`, { clip_id: clip.id, ...patch }, 'Không chỉnh được clip.'));
    } catch (e) {
      setError(errorText(e));
    } finally {
      setBusy('');
    }
  }

  async function undo() {
    setBusy('undo'); setError('');
    try {
      const state = await postJSON<Project>(`/api/projects/${pid}/undo`, {}, 'Không hoàn tác được.');
      const head = state.versions.find(v => v.id === state.head);
      if (head?.render_file) setCurrent(head);
    } catch (e) {
      setError(errorText(e));
    } finally {
      setBusy('');
    }
  }

  return (
    <div className="split">
      <div className="column">
        <Card title={mode === 'remix' ? 'Bài hát nguồn' : 'Hai bài hát nguồn'} step="01">
          {slots.map((slot, i) => {
            const source = sources[i];
            return source ? (
              <div key={slot} className="source">
                <span className="source-badge">{slot}</span>
                <div><b>{source.name}</b><small className="mono">{source.analysis?.bpm ? `${Math.round(source.analysis.bpm)} BPM` : 'BPM chưa rõ'} · {Math.round(source.analysis?.duration_s || 0)}s</small></div>
                <Icon name="check" className="ok" />
              </div>
            ) : (
              <Field key={slot} label={mode === 'mashup' ? `Nguồn ${slot}${slot === 'A' ? ' — giọng chính' : ' — nền'}` : 'Tệp bài hát'}>
                <Dropzone file={files[slot] || null} onFile={file => setFiles(f => ({ ...f, [slot]: file }))} hint="Bài hát 8 giây – 6 phút mà bạn có quyền sử dụng" />
              </Field>
            );
          })}
          {!ready && (
            <>
              <Toggle checked={rights} onChange={setRights} label="Tôi có quyền sử dụng các tệp này" />
              <button type="button" className="button secondary" disabled={!rights || busy !== '' || slots.some((s, i) => !sources[i] && !files[s])} onClick={() => void uploadSources()}>
                {busy === 'upload' ? <><Spinner /> Đang phân tích & khớp tempo…</> : <><Icon name="upload" size={16} /> Tải lên & phân tích</>}
              </button>
            </>
          )}
          {capability?.reason && <p className="hint">{capability.reason}</p>}
        </Card>

        <Card title="Chỉnh bằng câu lệnh" step="02">
          <Field label="Câu lệnh" htmlFor="studio-prompt" hint={`${prompt.length} / 500`}>
            <textarea id="studio-prompt" value={prompt} maxLength={500} onChange={e => setPrompt(e.target.value)} placeholder="Ví dụ: Thêm beat lofi, đổi tempo sang 90 BPM…" disabled={!ready} />
          </Field>
          <div className="examples">{EXAMPLES.map(example => <button type="button" key={example} className="example" disabled={!ready || busy !== ''} onClick={() => void applyPrompt(example)}>{example}</button>)}</div>
          <button type="button" className="button primary large" disabled={!ready || !prompt.trim() || busy !== ''} onClick={() => void applyPrompt()}>
            {busy === 'prompt' ? <><Spinner /> Đang dựng bản phối…</> : <><Icon name="sparkle" /> Áp dụng câu lệnh</>}
          </button>
          <p className="hint">Câu lệnh được hiểu bằng quy tắc (tempo, beat house/lofi/trap/edm/pop, mưa/vinyl/biển, âm lượng). Đổi tempo sẽ time-stretch bài gốc.</p>
        </Card>

        {current && current.script.clips.length > 0 && (
          <Card title="Bàn mix" step="03" actions={<span className="badge">{bpm(current.script.bpm)} BPM</span>}>
            <div className="mixer">
              {current.script.clips.map(clip => (
                <div key={clip.id} className={`channel${clip.muted ? ' muted' : ''}`}>
                  <button type="button" className={`mute${clip.muted ? ' on' : ''}`} aria-pressed={clip.muted} disabled={busy !== ''} onClick={() => void editClip(clip, { muted: !clip.muted })}>M</button>
                  <span className="channel-name">{clipName(clip)}</span>
                  <input
                    type="range" min={-24} max={6} step={1} aria-label={`Âm lượng ${clipName(clip)}`}
                    value={gains[clip.id] ?? clip.gain_db}
                    disabled={busy !== ''}
                    onChange={e => setGains(g => ({ ...g, [clip.id]: Number(e.target.value) }))}
                    onPointerUp={() => gains[clip.id] !== clip.gain_db && void editClip(clip, { gain_db: gains[clip.id] })}
                    onKeyUp={() => gains[clip.id] !== clip.gain_db && void editClip(clip, { gain_db: gains[clip.id] })}
                  />
                  <span className="mono gain">{(gains[clip.id] ?? clip.gain_db) > 0 ? '+' : ''}{gains[clip.id] ?? clip.gain_db} dB</span>
                </div>
              ))}
            </div>
          </Card>
        )}
      </div>

      <div className="column results">
        <Card title="Bản phối" actions={current && current.parent && <button type="button" className="button ghost small" disabled={busy !== ''} onClick={() => void undo()}><Icon name="undo" size={14} /> Hoàn tác</button>}>
          {error && <Notice tone="error">{error}</Notice>}
          {busy === 'edit' && <Notice>Đang render lại bản phối…</Notice>}
          {current?.render_file ? (
            <>
              <WaveformPlayer key={current.id} src={audioUrl(pid, current.id)} peaks={current.peaks} title={current.prompt || 'Bản gốc'} />
              {current.cards.length > 0 && <div className="changes">{current.cards.map(card => <span key={card.title} className="tag"><small>{card.kind}</small>{card.title}</span>)}</div>}
              <DownloadLinks links={exportLinks(pid, current.id)} />
            </>
          ) : !error && <div className="empty"><b>Bản phối sẽ xuất hiện ở đây</b><p>{mode === 'remix' ? 'Tải bài hát lên, rồi thêm beat, đổi tempo hay thêm âm nền bằng câu lệnh.' : 'Tải hai bài hát; MIXVERSE khớp tempo rồi chồng hai bài lên nhau.'}</p></div>}
        </Card>
        {versions.length > 1 && (
          <Card title="Lịch sử phiên bản">
            <ol className="history">
              {[...versions].reverse().map(v => (
                <li key={v.id}>
                  <button type="button" className={current?.id === v.id ? 'active' : ''} onClick={() => setCurrent(v)}>
                    <b>{v.prompt || 'Bản gốc'}</b>
                    <small>{v.cards.map(c => c.title).join(' · ') || `${bpm(v.script.bpm)} BPM`}</small>
                  </button>
                </li>
              ))}
            </ol>
          </Card>
        )}
      </div>
    </div>
  );
}

function exportLinks(pid: string, vid: string) {
  return [{ label: 'Xuất WAV', href: `/api/projects/${pid}/studio/exports/${vid}/wav`, primary: true }, { label: 'Xuất MP3', href: `/api/projects/${pid}/studio/exports/${vid}/mp3` }];
}
