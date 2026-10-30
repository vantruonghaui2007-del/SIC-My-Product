export type ModeCapability = {
  enabled: boolean;
  reason?: string | null;
  method?: string;
  provider_enabled?: boolean;
  provider?: string | null;
  provider_reason?: string | null;
};
export type Capabilities = { modes?: Record<string, ModeCapability> };

export type ViewId = 'text_music' | 'text_song' | 'rap_beat' | 'sound_music' | 'remix' | 'mashup' | 'library';

export type Recipe = {
  genre: string;
  mood: string;
  bpm: number;
  key: string;
  mode: 'major' | 'minor';
  duration_s: number;
  instruments: string[];
  drums: boolean;
  drums_entry: 'start' | 'middle';
  melody: boolean;
  ambience: string;
};

export type Detected = { kind: string; label: string; source: string };
export type ParsedPrompt = { recipe: Recipe; detected: Detected[]; notes: string[] };

export type Option = { id: string; label: string; bpm?: number };
export type MusicOptions = {
  genres: Option[];
  moods: Option[];
  instruments: Option[];
  ambiences: Option[];
  keys: string[];
};

export type SectionInfo = { label: string; name: string; start_bar: number; bars: number; energy: number; chords: string[] };
export type Stem = { id: string; label: string; url: string };

export type MusicTake = {
  composition_id?: string;
  audio_url: string;
  peaks?: number[];
  midi_url?: string;
  stems_url?: string;
  stems?: Stem[];
  metadata: {
    label?: string;
    key?: string;
    bpm?: number;
    duration_s?: number;
    progression?: string[];
    sections?: SectionInfo[];
    parts?: { part: string; instrument: string; stem: string }[];
    warning?: string;
    warnings?: string[];
    style?: string;
    provider?: string;
  };
};

export type StudioClip = { kind: string; id: string; lane: string; gain_db: number; muted: boolean; style?: string; ambience?: string; source_id?: string };
export type StudioVersion = {
  id: string;
  parent: string | null;
  prompt: string;
  provider: string;
  cards: { kind: string; title: string; detail: string }[];
  script: { bpm: number; clips: StudioClip[] };
  render: string;
  render_file?: string | null;
  peaks?: number[];
};
export type Source = { id: string; name: string; analysis?: { bpm: number; duration_s: number; n_bars: number; warnings: string[] } };
export type Project = { id: string; mode: string; head: string; versions: StudioVersion[]; sources: Source[] };

export type LibraryItem = {
  id: string;
  kind: 'text_music' | 'text_song' | 'rap_beat' | 'sound_music' | 'studio';
  title: string;
  subtitle: string;
  createdAt: number;
  audioUrl: string;
  peaks?: number[];
  downloads: { label: string; href: string }[];
};
