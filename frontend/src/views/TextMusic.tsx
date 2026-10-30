import { useEffect, useRef, useState } from 'react';
import { createProject, errorText, getJSON, postJSON } from '../api';
import { addToLibrary } from '../library';
import type { ModeCapability, MusicOptions, MusicTake, ParsedPrompt, Recipe } from '../types';
import Icon from '../ui/Icon';
import WaveformPlayer from '../ui/WaveformPlayer';
import { Card, Chip, DownloadLinks, Field, Notice, Segmented, Spinner, Toggle } from '../ui/controls';

const EXAMPLES = [
  'Lofi đêm mưa, piano nhẹ nhàng, trống xuất hiện ở đoạn giữa',
  'Trap u tối 140 BPM với bell và 808',
  'Ballad buồn, piano và violin, A minor',
  'EDM sôi động 60 giây cho video tập gym',
  'Ambient mơ màng 2 phút để thiền, có tiếng sóng biển',
  'Pop vui tươi với guitar, đô trưởng',
];
const KIND_LABEL: Record<string, string> = {
  genre: 'Thể loại', mood: 'Cảm xúc', tempo: 'Tempo', key: 'Giọng', instrument: 'Nhạc cụ', ambience: 'Âm nền', structure: 'Cấu trúc', duration: 'Thời lượng',
};
const DURATIONS = [15, 30, 60, 90, 120];
const PART_LABEL: Record<string, string> = { chords: 'Hoà âm', pad: 'Lớp nền', melody: 'Giai điệu', arp: 'Arp', bass: 'Bass' };
const INSTRUMENT_LABEL: Record<string, string> = {
  piano: 'Piano', epiano: 'Electric piano', guitar: 'Guitar', pad: 'Synth pad', strings: 'Dàn dây', bass: 'Bass', bass808: '808',
  bell: 'Bell', pluck: 'Pluck', lead: 'Synth lead', flute: 'Sáo',
};
const BUILD_STEPS = ['Viết vòng hợp âm', 'Sáng tác giai điệu', 'Phối bass & trống', 'Mix & master'];

export default function TextMusic({ capability, projectId, onProject }: { capability?: ModeCapability; projectId: string; onProject: (id: string) => void }) {
  const [prompt, setPrompt] = useState('');
  const [parsed, setParsed] = useState<ParsedPrompt | null>(null);
  const [recipe, setRecipe] = useState<Recipe | null>(null);
  const [manual, setManual] = useState(false);
  const [options, setOptions] = useState<MusicOptions | null>(null);
  const [method, setMethod] = useState<'local' | 'provider'>('local');
  const [consent, setConsent] = useState(false);
  const [takeCount, setTakeCount] = useState(3);
  const [busy, setBusy] = useState(false);
  const [buildStep, setBuildStep] = useState(0);
  const [error, setError] = useState('');
  const [takes, setTakes] = useState<MusicTake[]>([]);
  const [selected, setSelected] = useState(0);
  const manualRef = useRef(manual);
  manualRef.current = manual;

  useEffect(() => {
    getJSON<MusicOptions>('/api/creator/music-options').then(setOptions).catch(() => undefined);
  }, []);

  useEffect(() => {
    const timer = window.setTimeout(() => {
      postJSON<ParsedPrompt>('/api/creator/recipe', { prompt })
        .then(result => {
          setParsed(result);
          if (!manualRef.current) setRecipe(result.recipe);
        })
        .catch(() => undefined);
    }, 320);
    return () => window.clearTimeout(timer);
  }, [prompt]);

  useEffect(() => {
    if (!busy) return;
    setBuildStep(0);
    const timer = window.setInterval(() => setBuildStep(step => Math.min(step + 1, BUILD_STEPS.length - 1)), 900);
    return () => window.clearInterval(timer);
  }, [busy]);

  function edit(patch: Partial<Recipe>) {
    if (!recipe) return;
    setManual(true);
    setRecipe({ ...recipe, ...patch });
  }

  function resync() {
    setManual(false);
    if (parsed) setRecipe(parsed.recipe);
  }

  const providerReady = Boolean(capability?.provider_enabled);
  const canCreate = Boolean(capability?.enabled) && !busy && (method === 'local' ? Boolean(recipe) : providerReady && consent && Boolean(prompt.trim()));

  async function create() {
    if (!recipe) return;
    setBusy(true); setError(''); setTakes([]); setSelected(0);
    try {
      const pid = projectId || await createProject('create');
      if (!projectId) onProject(pid);
      const url = `/api/projects/${pid}/creator/text-music`;
      if (method === 'provider') {
        const data = await postJSON<MusicTake>(url, { prompt, duration_s: recipe.duration_s, generation_method: 'provider', provider_consent: consent }, 'Không sinh được nhạc từ provider.');
        const take = { ...data, metadata: { ...data.metadata, label: `AI Provider · ${data.metadata.provider || ''}` } };
        setTakes([take]);
        addToLibrary({ kind: 'text_music', title: prompt.slice(0, 60) || 'AI Provider', subtitle: 'ElevenLabs', audioUrl: take.audio_url, peaks: take.peaks, downloads: [{ label: 'WAV', href: `${take.audio_url}/download/wav` }, { label: 'MP3', href: `${take.audio_url}/download/mp3` }] });
      } else {
        const data = await postJSON<{ takes: MusicTake[] }>(url, { prompt, generation_method: 'loops', recipe, takes: takeCount }, 'Không tạo được bản nhạc.');
        setTakes(data.takes);
        const genre = options?.genres.find(g => g.id === recipe.genre)?.label || recipe.genre;
        [...data.takes].reverse().forEach(take => addToLibrary({
          kind: 'text_music',
          title: `${genre} · ${take.metadata.key} · ${take.metadata.bpm} BPM`,
          subtitle: take.metadata.label || '',
          audioUrl: take.audio_url,
          peaks: take.peaks,
          downloads: takeLinks(take),
        }));
      }
    } catch (e) {
      setError(errorText(e));
    } finally {
      setBusy(false);
    }
  }

  const take = takes[selected];
  return (
    <div className="split">
      <div className="column">
        <Card title="Ý tưởng của bạn" step="01">
          <Field label="Mô tả bản nhạc" htmlFor="idea" hint={`${prompt.length} / 2.000`}>
            <textarea id="idea" value={prompt} maxLength={2000} onChange={e => setPrompt(e.target.value)} placeholder="Ví dụ: Một bản lofi ấm áp cho đêm mưa, piano nhẹ và nhịp trống thư giãn…" />
          </Field>
          <div className="examples" aria-label="Prompt mẫu">
            {EXAMPLES.map(example => <button type="button" key={example} className="example" onClick={() => setPrompt(example)}>{example}</button>)}
          </div>
          {parsed && (
            <div className="understood">
              <div className="understood-head"><Icon name="sparkle" size={15} /> MIXVERSE hiểu là</div>
              <div className="detected">
                {parsed.detected.map((d, i) => (
                  <span key={`${d.kind}-${d.label}-${i}`} className={`tag ${d.source === 'mặc định' ? 'muted' : ''}`} title={d.source === 'mặc định' ? 'Mặc định theo thể loại' : `Từ: “${d.source}”`}>
                    <small>{KIND_LABEL[d.kind] || d.kind}</small>{d.label}
                  </span>
                ))}
              </div>
              {parsed.notes.map(note => <p key={note} className="hint">{note}</p>)}
            </div>
          )}
        </Card>

        {recipe && options && (
          <Card
            title="Công thức nhạc"
            step="02"
            actions={manual ? <button type="button" className="button ghost small" onClick={resync}><Icon name="undo" size={14} /> Theo lại prompt</button> : <span className="badge">Tự động theo prompt</span>}
          >
            <RecipeEditor recipe={recipe} options={options} onChange={edit} />
          </Card>
        )}

        <Card title="Tạo bản nhạc" step="03">
          <Segmented
            label="Cách tạo"
            value={method}
            onChange={setMethod}
            options={[
              { value: 'local', label: <><Icon name="piano" size={15} /> Engine local · miễn phí</> },
              { value: 'provider', label: <><Icon name="sparkle" size={15} /> AI Provider{providerReady ? '' : ' (chưa cấu hình)'}</>, disabled: !providerReady, title: capability?.provider_reason || '' },
            ]}
          />
          {method === 'local' ? (
            <>
              <Field label="Số phương án">
                <Segmented label="Số phương án" value={takeCount} onChange={setTakeCount} options={[{ value: 1, label: '1 bản' }, { value: 3, label: '3 bản để chọn' }]} />
              </Field>
              <p className="hint">Engine local tự viết hợp âm, giai điệu, bass và trống bằng lý thuyết âm nhạc — không phải AI, chạy offline, không tốn phí. Mỗi phương án dùng vòng hợp âm khác nhau.</p>
            </>
          ) : (
            <>
              <Toggle checked={consent} onChange={setConsent} label="Tôi đồng ý gửi prompt đến ElevenLabs" hint="Có thể phát sinh phí; không tự thử lại nếu lỗi." />
            </>
          )}
          {!providerReady && capability?.provider_reason && <p className="hint">AI Provider: {capability.provider_reason}</p>}
          {capability && !capability.enabled && capability.reason && <Notice tone="warn">{capability.reason}</Notice>}
          <button type="button" className="button primary large" disabled={!canCreate} onClick={() => void create()}>
            {busy ? <><Spinner /> Đang sáng tác…</> : method === 'provider' ? <><Icon name="sparkle" /> Sinh nhạc bằng AI</> : <><Icon name="music" /> Sáng tác bản nhạc</>}
          </button>
        </Card>
      </div>

      <div className="column results">
        <Card title="Kết quả" actions={takes.length > 0 && <span className="badge">{takes.length} phương án</span>}>
          {error && <Notice tone="error">{error}</Notice>}
          {busy && (
            <div className="building" aria-live="polite">
              <div className="eq" aria-hidden="true">{Array.from({ length: 24 }, (_, i) => <span key={i} style={{ animationDelay: `${(i % 6) * .12}s` }} />)}</div>
              <ol>{BUILD_STEPS.map((step, i) => <li key={step} className={i < buildStep ? 'done' : i === buildStep ? 'now' : ''}>{step}</li>)}</ol>
            </div>
          )}
          {!busy && !takes.length && !error && (
            <div className="empty">
              <div className="empty-art" aria-hidden="true">{Array.from({ length: 32 }, (_, i) => <span key={i} style={{ height: `${18 + 60 * Math.abs(Math.sin(i * .5)) * Math.abs(Math.cos(i * .13))}%` }} />)}</div>
              <b>Bản nhạc của bạn sẽ xuất hiện ở đây</b>
              <p>Viết ý tưởng, chỉnh công thức nếu muốn, rồi bấm <em>Sáng tác bản nhạc</em>.</p>
            </div>
          )}
          {takes.length > 1 && (
            <div className="takes" role="tablist" aria-label="Phương án">
              {takes.map((t, i) => (
                <button key={t.audio_url} type="button" role="tab" aria-selected={selected === i} className={`take${selected === i ? ' selected' : ''}`} onClick={() => setSelected(i)}>
                  <b>Phương án {i + 1}</b>
                  <small>{t.metadata.progression?.join(' – ')}</small>
                </button>
              ))}
            </div>
          )}
          {take && <TakeResult key={take.audio_url} take={take} />}
        </Card>
      </div>
    </div>
  );
}

function takeLinks(take: MusicTake) {
  const links = [{ label: 'WAV', href: `${take.audio_url}/download/wav`, primary: true }, { label: 'MP3', href: `${take.audio_url}/download/mp3` }];
  if (take.midi_url) links.push({ label: 'MIDI', href: take.midi_url });
  if (take.stems_url) links.push({ label: 'Stems (.zip)', href: take.stems_url });
  return links;
}

function RecipeEditor({ recipe, options, onChange }: { recipe: Recipe; options: MusicOptions; onChange: (patch: Partial<Recipe>) => void }) {
  const toggleInstrument = (id: string) => {
    const has = recipe.instruments.includes(id);
    if (has && recipe.instruments.length === 1) return;
    onChange({ instruments: has ? recipe.instruments.filter(i => i !== id) : [...recipe.instruments, id] });
  };
  return (
    <div className="recipe">
      <Field label="Thể loại">
        <div className="chips">{options.genres.map(g => <Chip key={g.id} active={recipe.genre === g.id} onClick={() => onChange({ genre: g.id, bpm: g.bpm ?? recipe.bpm })}>{g.label}</Chip>)}</div>
      </Field>
      <Field label="Cảm xúc">
        <div className="chips">{options.moods.map(m => <Chip key={m.id} active={recipe.mood === m.id} onClick={() => onChange({ mood: m.id })}>{m.label}</Chip>)}</div>
      </Field>
      <div className="grid-2">
        <Field label="Tempo" htmlFor="bpm" hint={<b className="mono">{recipe.bpm} BPM</b>}>
          <input id="bpm" type="range" min={60} max={180} value={recipe.bpm} onChange={e => onChange({ bpm: Number(e.target.value) })} />
        </Field>
        <Field label="Giọng (key)" htmlFor="key">
          <div className="inline">
            <select id="key" value={recipe.key} onChange={e => onChange({ key: e.target.value })}>{options.keys.map(k => <option key={k} value={k}>{k}</option>)}</select>
            <Segmented label="Điệu thức" value={recipe.mode} onChange={mode => onChange({ mode })} options={[{ value: 'major', label: 'Major' }, { value: 'minor', label: 'Minor' }]} />
          </div>
        </Field>
      </div>
      <Field label="Thời lượng">
        <Segmented label="Thời lượng" value={recipe.duration_s} onChange={duration_s => onChange({ duration_s })} options={DURATIONS.map(d => ({ value: d, label: d % 60 === 0 ? `${d / 60} phút` : `${d}s` }))} />
      </Field>
      <Field label="Nhạc cụ" hint="Chọn một hoặc nhiều">
        <div className="chips">{options.instruments.map(i => <Chip key={i.id} active={recipe.instruments.includes(i.id)} onClick={() => toggleInstrument(i.id)}>{i.label}</Chip>)}</div>
      </Field>
      <Field label="Âm nền">
        <div className="chips">{options.ambiences.map(a => <Chip key={a.id} active={recipe.ambience === a.id} onClick={() => onChange({ ambience: a.id })}>{a.label}</Chip>)}</div>
      </Field>
      <div className="grid-2">
        <Toggle checked={recipe.drums} onChange={drums => onChange({ drums })} label="Trống" hint={recipe.drums ? (recipe.drums_entry === 'middle' ? 'Vào ở giữa bài' : 'Ngay từ đầu') : 'Tắt'} />
        <Toggle checked={recipe.melody} onChange={melody => onChange({ melody })} label="Giai điệu chính" hint={recipe.melody ? 'Có melody' : 'Chỉ hoà âm'} />
      </div>
      {recipe.drums && <Segmented label="Trống vào" value={recipe.drums_entry} onChange={drums_entry => onChange({ drums_entry })} options={[{ value: 'start', label: 'Trống từ đầu' }, { value: 'middle', label: 'Trống vào giữa bài' }]} />}
    </div>
  );
}

function TakeResult({ take }: { take: MusicTake }) {
  const m = take.metadata;
  const totalBars = m.sections?.reduce((sum, s) => sum + s.bars, 0) || 1;
  return (
    <div className="take-result">
      <WaveformPlayer src={take.audio_url} peaks={take.peaks} title={m.label} />
      <div className="facts">
        {m.key && <span><small>Giọng</small>{m.key}</span>}
        {m.bpm && <span><small>Tempo</small>{m.bpm} BPM</span>}
        {m.duration_s && <span><small>Độ dài</small>{Math.round(m.duration_s)}s</span>}
        {m.progression && <span className="wide"><small>Vòng hợp âm</small>{m.progression.join(' – ')}</span>}
      </div>
      {m.sections && (
        <div className="structure" aria-label="Cấu trúc bài">
          {m.sections.map(s => (
            <div key={s.start_bar} className={`section ${s.label}`} style={{ flexGrow: s.bars }} title={`${s.name}: ô ${s.start_bar + 1}–${s.start_bar + s.bars} · ${s.chords.join(' ')}`}>
              <b>{s.name}</b>
              <small>{s.bars} ô</small>
            </div>
          ))}
        </div>
      )}
      {m.parts && (
        <div className="parts">
          <span className="hint mono">{totalBars} ô nhịp</span>
          {m.parts.map(p => <span key={p.part} className="tag"><small>{PART_LABEL[p.part] || p.part}</small>{INSTRUMENT_LABEL[p.instrument] || p.instrument}</span>)}
        </div>
      )}
      {take.stems && take.stems.length > 0 && (
        <div className="stems">
          <div className="subhead"><Icon name="layers" size={15} /> Stems — tải riêng từng lớp để mix trong DAW</div>
          {take.stems.map(stem => (
            <div key={stem.id} className={`stem ${stem.id}`}>
              <span className="stem-name">{stem.label}</span>
              <WaveformPlayer src={stem.url} compact title={stem.label} />
              <a className="icon-button" href={stem.url} download aria-label={`Tải stem ${stem.label}`}><Icon name="download" size={16} /></a>
            </div>
          ))}
        </div>
      )}
      <DownloadLinks links={takeLinks(take)} />
      {m.warning && <p className="hint">{m.warning}</p>}
    </div>
  );
}
