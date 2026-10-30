import { useEffect, useId, useMemo, useRef, useState, type KeyboardEvent, type MouseEvent } from 'react';
import Icon from './Icon';

const PLAY_EVENT = 'mixverse:play';
const PLACEHOLDER = Array.from({ length: 120 }, (_, i) => .18 + .12 * Math.abs(Math.sin(i * .35)));

function format(seconds: number) {
  if (!Number.isFinite(seconds) || seconds < 0) return '0:00';
  const m = Math.floor(seconds / 60);
  return `${m}:${String(Math.floor(seconds % 60)).padStart(2, '0')}`;
}

function downsample(peaks: number[], bars: number) {
  if (peaks.length <= bars) return peaks;
  const size = peaks.length / bars;
  return Array.from({ length: bars }, (_, i) => Math.max(...peaks.slice(Math.floor(i * size), Math.max(Math.floor((i + 1) * size), Math.floor(i * size) + 1))));
}

async function decodePeaks(src: string, signal: AbortSignal): Promise<number[] | null> {
  const Context = window.AudioContext || (window as unknown as { webkitAudioContext?: typeof AudioContext }).webkitAudioContext;
  if (!Context) return null;
  const response = await fetch(src, { signal });
  if (!response.ok) return null;
  const context = new Context();
  try {
    const audio = await context.decodeAudioData(await response.arrayBuffer());
    const data = audio.getChannelData(0);
    const size = Math.max(1, Math.floor(data.length / 200));
    const peaks = Array.from({ length: Math.ceil(data.length / size) }, (_, i) => {
      let top = 0;
      for (let j = i * size; j < Math.min(data.length, (i + 1) * size); j += 8) top = Math.max(top, Math.abs(data[j]));
      return top;
    });
    const max = Math.max(...peaks, 1e-6);
    return peaks.map(p => p / max);
  } finally {
    void context.close();
  }
}

export default function WaveformPlayer({ src, peaks, title, compact = false, bars = 160 }: { src: string; peaks?: number[]; title?: string; compact?: boolean; bars?: number }) {
  const id = useId();
  const audio = useRef<HTMLAudioElement>(null);
  const [playing, setPlaying] = useState(false);
  const [time, setTime] = useState(0);
  const [duration, setDuration] = useState(0);
  const [decoded, setDecoded] = useState<number[] | null>(null);
  const [failed, setFailed] = useState(false);

  useEffect(() => {
    setPlaying(false); setTime(0); setDuration(0); setDecoded(null); setFailed(false);
    if (peaks?.length || compact) return;
    const controller = new AbortController();
    decodePeaks(src, controller.signal).then(setDecoded).catch(() => undefined);
    return () => controller.abort();
  }, [src, peaks, compact]);

  useEffect(() => {
    const pauseOthers = (event: Event) => {
      if ((event as CustomEvent<string>).detail !== id) audio.current?.pause();
    };
    window.addEventListener(PLAY_EVENT, pauseOthers);
    return () => window.removeEventListener(PLAY_EVENT, pauseOthers);
  }, [id]);

  // Compact players without peaks show a plain progress track rather than a fake waveform.
  const shape = useMemo(() => {
    const source = peaks?.length ? peaks : decoded || (compact ? null : PLACEHOLDER);
    return source ? downsample(source, compact ? 60 : bars) : null;
  }, [peaks, decoded, compact, bars]);
  const progress = duration ? time / duration : 0;

  async function toggle() {
    const element = audio.current;
    if (!element) return;
    if (!element.paused) { element.pause(); return; }
    window.dispatchEvent(new CustomEvent(PLAY_EVENT, { detail: id }));
    try { await element.play(); } catch { setFailed(true); }
  }

  function seekTo(fraction: number) {
    const element = audio.current;
    if (!element || !duration) return;
    element.currentTime = Math.min(Math.max(fraction, 0), 1) * duration;
    setTime(element.currentTime);
  }

  function onClick(event: MouseEvent<HTMLDivElement>) {
    const rect = event.currentTarget.getBoundingClientRect();
    seekTo((event.clientX - rect.left) / rect.width);
  }

  function onKey(event: KeyboardEvent<HTMLDivElement>) {
    if (event.key === 'ArrowRight') seekTo(progress + .05);
    else if (event.key === 'ArrowLeft') seekTo(progress - .05);
    else if (event.key === ' ' || event.key === 'Enter') { event.preventDefault(); void toggle(); }
  }

  return (
    <div className={`player${compact ? ' compact' : ''}${playing ? ' is-playing' : ''}`}>
      <audio
        ref={audio}
        src={src}
        preload="metadata"
        onLoadedMetadata={e => setDuration(e.currentTarget.duration)}
        onTimeUpdate={e => setTime(e.currentTarget.currentTime)}
        onPlay={() => setPlaying(true)}
        onPause={() => setPlaying(false)}
        onEnded={() => setPlaying(false)}
        onError={() => setFailed(true)}
      />
      <button type="button" className="play-button" onClick={() => void toggle()} aria-label={playing ? `Tạm dừng ${title || ''}` : `Phát ${title || ''}`} disabled={failed}>
        <Icon name={playing ? 'pause' : 'play'} size={compact ? 14 : 20} />
      </button>
      <div className="player-body">
        {title && !compact && <div className="player-title">{title}</div>}
        <div className={shape ? 'wave' : 'track'} role="slider" tabIndex={0} aria-label="Vị trí phát" aria-valuemin={0} aria-valuemax={Math.round(duration)} aria-valuenow={Math.round(time)} onClick={onClick} onKeyDown={onKey}>
          {shape ? (
            <svg viewBox={`0 0 ${shape.length} 100`} preserveAspectRatio="none" aria-hidden="true">
              {shape.map((peak, i) => {
                const h = Math.max(4, peak * 96);
                return <rect key={i} x={i + .18} width={.64} y={50 - h / 2} height={h} rx={.3} className={i / shape.length < progress ? 'played' : ''} />;
              })}
            </svg>
          ) : <span style={{ width: `${progress * 100}%` }} />}
        </div>
        {!compact && <div className="player-time"><span>{format(time)}</span><span>{failed ? 'Không phát được (tệp có thể đã hết hạn)' : format(duration)}</span></div>}
      </div>
    </div>
  );
}
