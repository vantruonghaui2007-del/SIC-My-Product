import { useState } from 'react';
import { createProject, errorText, patchJSON, postJSON, upload } from '../api';
import { addToLibrary } from '../library';
import type { ModeCapability, MusicTake } from '../types';
import Icon from '../ui/Icon';
import WaveformPlayer from '../ui/WaveformPlayer';
import { Card, Chip, DownloadLinks, Dropzone, Field, Notice, Spinner, Toggle } from '../ui/controls';

type Analysis = { tempo_candidates: { bpm: number; score: number; first_downbeat_s: number }[]; active_regions_s: number[][]; warnings: string[] };
type Asset = { id: string; duration_s: number; original_name: string };
const STYLES = ['trap', 'lofi', 'house', 'edm', 'pop'];

export default function RapBeat({ capability, projectId, onProject }: { capability?: ModeCapability; projectId: string; onProject: (id: string) => void }) {
  const [file, setFile] = useState<File | null>(null);
  const [rights, setRights] = useState(false);
  const [asset, setAsset] = useState<Asset | null>(null);
  const [analysis, setAnalysis] = useState<Analysis | null>(null);
  const [bpm, setBpm] = useState(90);
  const [anchor, setAnchor] = useState(0);
  const [style, setStyle] = useState('trap');
  const [busy, setBusy] = useState<'' | 'analyze' | 'beat'>('');
  const [error, setError] = useState('');
  const [takes, setTakes] = useState<MusicTake[]>([]);
  const [selected, setSelected] = useState(0);
  const [pid, setPid] = useState(projectId);

  function choose(next: File | null) {
    setFile(next); setAsset(null); setAnalysis(null); setTakes([]); setError('');
  }

  async function analyze() {
    if (!file) return;
    setBusy('analyze'); setError('');
    try {
      const project = pid || await createProject('create');
      if (!pid) { setPid(project); onProject(project); }
      const form = new FormData();
      form.set('file', file); form.set('kind', 'vocal'); form.set('rights_confirmed', 'true');
      const uploaded = await upload<Asset>(`/api/projects/${project}/creator/assets`, form, 'Không tải được vocal.');
      setAsset(uploaded);
      const result = await postJSON<Analysis>(`/api/projects/${project}/creator/assets/${uploaded.id}/analyze`, {}, 'Không phân tích được vocal.');
      setAnalysis(result);
      const best = result.tempo_candidates[0];
      if (best) { setBpm(best.bpm); setAnchor(Number(best.first_downbeat_s.toFixed(2))); }
    } catch (e) {
      setError(errorText(e));
    } finally {
      setBusy('');
    }
  }

  async function build() {
    if (!asset) return;
    setBusy('beat'); setError(''); setTakes([]);
    try {
      await patchJSON(`/api/projects/${pid}/creator/assets/${asset.id}/grid`, { bpm, first_downbeat_s: anchor }, 'Không xác nhận được nhịp.');
      const data = await postJSON<{ takes: MusicTake[] }>(`/api/projects/${pid}/creator/rap/${asset.id}/takes`, { bpm, style, first_downbeat_s: anchor }, 'Không dựng được beat.');
      setTakes(data.takes); setSelected(0);
      [...data.takes].reverse().forEach(take => addToLibrary({ kind: 'rap_beat', title: `${asset.original_name} · ${style} ${bpm} BPM`, subtitle: take.metadata.label || '', audioUrl: take.audio_url, peaks: take.peaks, downloads: links(take) }));
    } catch (e) {
      setError(errorText(e));
    } finally {
      setBusy('');
    }
  }

  const take = takes[selected];
  return (
    <div className="split">
      <div className="column">
        <Card title="Vocal của bạn" step="01">
          <Dropzone file={file} onFile={choose} hint="Vocal rap 10–60 giây (WAV, MP3, M4A…)" />
          <Toggle checked={rights} onChange={setRights} label="Tôi có quyền sử dụng bản thu này" />
          <button type="button" className="button secondary" disabled={!file || !rights || busy !== ''} onClick={() => void analyze()}>
            {busy === 'analyze' ? <><Spinner /> Đang phân tích…</> : <><Icon name="wave" size={16} /> Tải lên & dò tempo</>}
          </button>
        </Card>
        <Card title="Nhịp & phong cách" step="02">
          {analysis && (
            <Field label="Tempo gợi ý từ vocal" hint="Heuristic — hãy chọn và nghe thử">
              <div className="chips">
                {analysis.tempo_candidates.map(c => (
                  <Chip key={c.bpm} active={bpm === c.bpm} onClick={() => setBpm(c.bpm)}>
                    {c.bpm} BPM <small className="mono">{Math.round(c.score * 100)}%</small>
                  </Chip>
                ))}
              </div>
            </Field>
          )}
          <div className="grid-2">
            <Field label="Tempo" htmlFor="rap-bpm" hint={<b className="mono">{bpm} BPM</b>}>
              <input id="rap-bpm" type="range" min={60} max={180} value={bpm} onChange={e => setBpm(Number(e.target.value))} />
            </Field>
            <Field label="Mốc phách mạnh (giây)" htmlFor="anchor">
              <input id="anchor" type="number" min={0} step={0.01} value={anchor} onChange={e => setAnchor(Number(e.target.value))} />
            </Field>
          </div>
          <Field label="Phong cách beat">
            <div className="chips">{STYLES.map(s => <Chip key={s} active={style === s} onClick={() => setStyle(s)}>{s.toUpperCase()}</Chip>)}</div>
          </Field>
          {capability?.reason && <p className="hint">{capability.reason}</p>}
          <button type="button" className="button primary large" disabled={!asset || busy !== '' || !capability?.enabled} onClick={() => void build()}>
            {busy === 'beat' ? <><Spinner /> Đang dựng beat…</> : <><Icon name="music" /> Dựng 3 beat theo vocal</>}
          </button>
          {!asset && <p className="hint">Tải vocal lên ở bước 01 trước.</p>}
        </Card>
      </div>
      <div className="column results">
        <Card title="Kết quả">
          {error && <Notice tone="error">{error}</Notice>}
          {asset && !takes.length && !error && <Notice tone="success">Đã nhận {asset.original_name} · {asset.duration_s.toFixed(1)} giây. Vocal được giữ nguyên thời gian.</Notice>}
          {takes.length > 0 && (
            <div className="takes" role="tablist" aria-label="Beat">
              {takes.map((t, i) => (
                <button key={t.audio_url} type="button" role="tab" aria-selected={selected === i} className={`take${selected === i ? ' selected' : ''}`} onClick={() => setSelected(i)}>
                  <b>{t.metadata.label}</b><small>Phương án {i + 1}</small>
                </button>
              ))}
            </div>
          )}
          {take ? (
            <>
              <WaveformPlayer key={take.audio_url} src={take.audio_url} peaks={take.peaks} title={`${style.toUpperCase()} · ${bpm} BPM`} />
              <DownloadLinks links={links(take)} />
            </>
          ) : !error && !asset && <div className="empty"><b>Beat sẽ xuất hiện ở đây</b><p>Tải vocal, chọn tempo rồi dựng beat — giọng gốc giữ nguyên.</p></div>}
        </Card>
      </div>
    </div>
  );
}

function links(take: MusicTake) {
  return [{ label: 'WAV', href: `${take.audio_url}/download/wav`, primary: true }, { label: 'MP3', href: `${take.audio_url}/download/mp3` }];
}
