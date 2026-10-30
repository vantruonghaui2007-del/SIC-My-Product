import { useMemo, useState } from 'react';
import { isExpired, useLibrary } from '../library';
import type { LibraryItem, ViewId } from '../types';
import Icon from '../ui/Icon';
import WaveformPlayer from '../ui/WaveformPlayer';
import { Card, Chip, DownloadLinks } from '../ui/controls';

const KIND_LABEL: Record<LibraryItem['kind'], string> = {
  text_music: 'Text to Music', text_song: 'Text to Song', rap_beat: 'Rap to Beat', sound_music: 'Sound to Music', studio: 'Studio',
};

function ago(timestamp: number) {
  const minutes = Math.round((Date.now() - timestamp) / 60000);
  if (minutes < 1) return 'vừa xong';
  if (minutes < 60) return `${minutes} phút trước`;
  const hours = Math.round(minutes / 60);
  return hours < 24 ? `${hours} giờ trước` : `${Math.round(hours / 24)} ngày trước`;
}

export default function Library({ onNavigate }: { onNavigate: (view: ViewId) => void }) {
  const { items, remove, clear } = useLibrary();
  const [filter, setFilter] = useState<LibraryItem['kind'] | 'all'>('all');
  const [query, setQuery] = useState('');
  const kinds = useMemo(() => Array.from(new Set(items.map(item => item.kind))), [items]);
  const shown = items.filter(item => (filter === 'all' || item.kind === filter) && `${item.title} ${item.subtitle}`.toLowerCase().includes(query.toLowerCase()));

  if (!items.length) {
    return (
      <Card>
        <div className="empty large">
          <Icon name="library" size={34} />
          <b>Thư viện đang trống</b>
          <p>Mọi bản nhạc bạn tạo sẽ được lưu ở đây (trên trình duyệt này) để nghe lại và tải xuống.</p>
          <button type="button" className="button primary" onClick={() => onNavigate('text_music')}><Icon name="music" size={16} /> Sáng tác bản đầu tiên</button>
        </div>
      </Card>
    );
  }

  return (
    <Card
      title={`${items.length} bản nhạc`}
      actions={<button type="button" className="button ghost small" onClick={() => { if (window.confirm('Xoá toàn bộ lịch sử trong thư viện?')) clear(); }}><Icon name="trash" size={14} /> Xoá tất cả</button>}
    >
      <div className="library-tools">
        <input type="search" placeholder="Tìm theo tên, thể loại, hợp âm…" value={query} onChange={e => setQuery(e.target.value)} aria-label="Tìm trong thư viện" />
        <div className="chips">
          <Chip active={filter === 'all'} onClick={() => setFilter('all')}>Tất cả</Chip>
          {kinds.map(kind => <Chip key={kind} active={filter === kind} onClick={() => setFilter(kind)}>{KIND_LABEL[kind]}</Chip>)}
        </div>
      </div>
      <p className="hint">Tệp âm thanh trên server tự xoá sau 24 giờ — hãy tải về những bản bạn muốn giữ.</p>
      <ul className="library">
        {shown.map(item => {
          const expired = isExpired(item);
          return (
            <li key={item.id} className={expired ? 'expired' : ''}>
              <div className="library-meta">
                <span className="tag"><small>{KIND_LABEL[item.kind]}</small>{ago(item.createdAt)}</span>
                <b>{item.title}</b>
                {item.subtitle && <small>{item.subtitle}</small>}
              </div>
              {expired ? <p className="hint">Đã hết hạn trên server.</p> : <WaveformPlayer src={item.audioUrl} peaks={item.peaks} bars={120} />}
              <div className="library-actions">
                {!expired && <DownloadLinks links={item.downloads} />}
                <button type="button" className="icon-button" aria-label={`Xoá ${item.title}`} onClick={() => remove(item.id)}><Icon name="trash" size={16} /></button>
              </div>
            </li>
          );
        })}
      </ul>
      {!shown.length && <p className="hint">Không có bản nào khớp bộ lọc.</p>}
    </Card>
  );
}
