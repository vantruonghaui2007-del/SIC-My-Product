import { useEffect, useState } from 'react';
import { getJSON } from './api';
import { useLibrary } from './library';
import type { Capabilities, ViewId } from './types';
import Icon from './ui/Icon';
import Library from './views/Library';
import RapBeat from './views/RapBeat';
import SoundMusic from './views/SoundMusic';
import Studio from './views/Studio';
import TextMusic from './views/TextMusic';
import TextSong from './views/TextSong';

type NavItem = { id: ViewId; label: string; icon: Parameters<typeof Icon>[0]['name']; title: string; description: string };
const NAV: { group: string; items: NavItem[] }[] = [
  {
    group: 'Sáng tác',
    items: [
      { id: 'text_music', label: 'Text to Music', icon: 'music', title: 'Mô tả ý tưởng, nhận bản nhạc hoàn chỉnh', description: 'Engine nhạc local tự viết hợp âm, giai điệu, bass, trống và phối thành bài có intro – verse – chorus. Xuất WAV, MP3, stems và MIDI.' },
      { id: 'text_song', label: 'Text to Song', icon: 'mic', title: 'Lời của bạn thành ca khúc', description: 'Gửi lời đã duyệt đến nhà cung cấp AI để hát thành bài hoàn chỉnh.' },
    ],
  },
  {
    group: 'Từ âm thanh',
    items: [
      { id: 'rap_beat', label: 'Rap to Beat', icon: 'wave', title: 'Dựng beat theo flow của bạn', description: 'Tải vocal rap, dò tempo từ chính giọng của bạn, rồi nhận ba beat — giọng gốc giữ nguyên thời gian.' },
      { id: 'sound_music', label: 'Sound to Music', icon: 'sparkle', title: 'Biến âm thanh thành nhạc cụ', description: 'Dùng tiếng động, tiếng gõ hay sample của bạn làm percussion hoặc lớp nền.' },
    ],
  },
  {
    group: 'Studio',
    items: [
      { id: 'remix', label: 'Remix', icon: 'remix', title: 'Remix bằng câu lệnh', description: 'Thêm beat, âm nền, đổi tempo (có time-stretch) và chỉnh từng lớp trên bàn mix.' },
      { id: 'mashup', label: 'Mashup', icon: 'mashup', title: 'Ghép hai bài hát', description: 'Khớp tempo hai nguồn, chồng lên nhau rồi chỉnh tiếp bằng câu lệnh.' },
    ],
  },
  { group: 'Của bạn', items: [{ id: 'library', label: 'Thư viện', icon: 'library', title: 'Thư viện', description: 'Các bản đã tạo trên trình duyệt này.' }] },
];
const ALL = NAV.flatMap(group => group.items);

function viewFromHash(): ViewId {
  const id = window.location.hash.replace('#', '');
  return (ALL.find(item => item.id === id)?.id) || 'text_music';
}

export default function App() {
  const [view, setView] = useState<ViewId>(viewFromHash);
  const [caps, setCaps] = useState<Capabilities>({});
  const [health, setHealth] = useState<'checking' | 'ok' | 'down'>('checking');
  const [projectId, setProjectId] = useState('');
  const { items } = useLibrary();

  useEffect(() => {
    getJSON<Capabilities>('/api/creator/capabilities').then(setCaps).catch(() => undefined);
    getJSON<{ ok: boolean }>('/api/health').then(x => setHealth(x.ok ? 'ok' : 'down')).catch(() => setHealth('down'));
  }, []);

  useEffect(() => {
    const sync = () => setView(viewFromHash());
    window.addEventListener('hashchange', sync);
    return () => window.removeEventListener('hashchange', sync);
  }, []);

  function navigate(next: ViewId) {
    setView(next);
    if (window.location.hash !== `#${next}`) window.history.replaceState(null, '', `#${next}`);
    window.scrollTo?.({ top: 0 });
  }

  const item = ALL.find(i => i.id === view)!;
  const cap = caps.modes?.[view];
  const pill = view === 'library' ? null
    : view === 'text_song' ? (cap?.enabled ? { tone: 'ready', text: 'AI PROVIDER' } : { tone: 'warn', text: 'CẦN CẤU HÌNH PROVIDER' })
    : view === 'remix' || view === 'mashup' ? { tone: 'ready', text: 'STUDIO · LOCAL' }
    : { tone: 'ready', text: 'LOCAL · OFFLINE · MIỄN PHÍ' };

  return (
    <div className="app">
      <aside className="sidebar">
        <a className="brand" href="#text_music" onClick={e => { e.preventDefault(); navigate('text_music'); }}>
          <span className="brand-mark" aria-hidden="true"><Icon name="wave" size={18} /></span>
          <span>MIXVERSE<small>Creator Studio</small></span>
        </a>
        <nav aria-label="Chức năng">
          {NAV.map(group => (
            <div key={group.group} className="nav-group">
              <span className="nav-label">{group.group}</span>
              {group.items.map(entry => {
                const disabled = entry.id !== 'library' && caps.modes?.[entry.id]?.enabled === false;
                return (
                  <button key={entry.id} type="button" className={`nav-item${view === entry.id ? ' active' : ''}`} aria-current={view === entry.id ? 'page' : undefined} onClick={() => navigate(entry.id)}>
                    <Icon name={entry.icon} size={17} />
                    <span>{entry.label}</span>
                    {entry.id === 'library' && items.length > 0 && <span className="count">{items.length}</span>}
                    {disabled && <span className="dot-warn" title="Cần cấu hình" />}
                  </button>
                );
              })}
            </div>
          ))}
        </nav>
        <div className="sidebar-foot">
          <div className={`health ${health}`}><i /> {health === 'ok' ? 'Backend sẵn sàng' : health === 'down' ? 'Backend chưa kết nối' : 'Đang kết nối…'}</div>
          <p>File trên server tự xoá sau 24 giờ. Prompt chỉ gửi ra ngoài khi bạn chọn AI Provider và đồng ý.</p>
        </div>
      </aside>

      <main className="main">
        <header className="page-head">
          <div>
            <span className="kicker">{NAV.find(g => g.items.includes(item))?.group}</span>
            <h1>{item.title}</h1>
            <p>{item.description}</p>
          </div>
          {pill && <span className={`pill ${pill.tone}`}>{pill.text}</span>}
        </header>
        {health === 'down' && <div className="banner">Không kết nối được backend. Hãy chạy <code>uvicorn mixverse.api:create_app_from_env --factory --port 8002</code> trong thư mục <code>backend</code>.</div>}
        {view === 'text_music' && <TextMusic capability={cap} projectId={projectId} onProject={setProjectId} />}
        {view === 'text_song' && <TextSong capability={cap} projectId={projectId} onProject={setProjectId} onNavigate={navigate} />}
        {view === 'rap_beat' && <RapBeat capability={cap} projectId={projectId} onProject={setProjectId} />}
        {view === 'sound_music' && <SoundMusic capability={cap} projectId={projectId} onProject={setProjectId} />}
        {(view === 'remix' || view === 'mashup') && <Studio key={view} mode={view} capability={cap} />}
        {view === 'library' && <Library onNavigate={navigate} />}
        <footer className="foot"><span>© 2026 MIXVERSE</span><span>Bản local không phải AI — luôn ghi rõ nguồn gốc bản nhạc.</span></footer>
      </main>
    </div>
  );
}
