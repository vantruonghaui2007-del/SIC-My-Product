import { useId, useRef, useState, type ReactNode } from 'react';
import Icon from './Icon';

export function Chip({ active, onClick, children, disabled, title }: { active?: boolean; onClick?: () => void; children: ReactNode; disabled?: boolean; title?: string }) {
  return (
    <button type="button" className={`chip${active ? ' active' : ''}`} aria-pressed={active} onClick={onClick} disabled={disabled} title={title}>
      {children}
    </button>
  );
}

export function Segmented<T extends string | number>({ value, options, onChange, label }: { value: T; options: { value: T; label: ReactNode; disabled?: boolean; title?: string }[]; onChange: (value: T) => void; label: string }) {
  return (
    <div className="segmented" role="radiogroup" aria-label={label}>
      {options.map(option => (
        <button key={String(option.value)} type="button" role="radio" aria-checked={value === option.value} className={value === option.value ? 'on' : ''} disabled={option.disabled} title={option.title} onClick={() => onChange(option.value)}>
          {option.label}
        </button>
      ))}
    </div>
  );
}

export function Toggle({ checked, onChange, label, hint }: { checked: boolean; onChange: (value: boolean) => void; label: ReactNode; hint?: ReactNode }) {
  return (
    <label className="toggle">
      <input type="checkbox" checked={checked} onChange={e => onChange(e.target.checked)} />
      <span className="toggle-track" aria-hidden="true"><span /></span>
      <span className="toggle-copy">{label}{hint && <small>{hint}</small>}</span>
    </label>
  );
}

export function Field({ label, hint, children, htmlFor }: { label: ReactNode; hint?: ReactNode; children: ReactNode; htmlFor?: string }) {
  return (
    <div className="field">
      <div className="field-head">{htmlFor ? <label htmlFor={htmlFor}>{label}</label> : <span className="field-label">{label}</span>}{hint && <span className="field-hint">{hint}</span>}</div>
      {children}
    </div>
  );
}

export function Notice({ tone = 'info', children }: { tone?: 'info' | 'warn' | 'error' | 'success'; children: ReactNode }) {
  const icon = tone === 'success' ? 'check' : tone === 'info' ? 'info' : 'alert';
  return (
    <div className={`notice ${tone}`} role={tone === 'error' ? 'alert' : 'status'}>
      <Icon name={icon} size={16} />
      <div>{children}</div>
    </div>
  );
}

export function Spinner() {
  return <span className="spinner" aria-hidden="true" />;
}

export function Card({ title, step, actions, children, className = '' }: { title?: ReactNode; step?: string; actions?: ReactNode; children: ReactNode; className?: string }) {
  return (
    <section className={`card ${className}`}>
      {(title || actions) && (
        <header className="card-head">
          <h3>{step && <span className="step">{step}</span>}{title}</h3>
          {actions}
        </header>
      )}
      {children}
    </section>
  );
}

export function Dropzone({ file, onFile, accept = 'audio/*', hint }: { file: File | null; onFile: (file: File | null) => void; accept?: string; hint: ReactNode }) {
  const id = useId();
  const input = useRef<HTMLInputElement>(null);
  const [over, setOver] = useState(false);
  return (
    <div
      className={`dropzone${over ? ' over' : ''}${file ? ' filled' : ''}`}
      onDragOver={e => { e.preventDefault(); setOver(true); }}
      onDragLeave={() => setOver(false)}
      onDrop={e => { e.preventDefault(); setOver(false); onFile(e.dataTransfer.files?.[0] || null); }}
    >
      <input ref={input} id={id} type="file" accept={accept} onChange={e => onFile(e.target.files?.[0] || null)} />
      <label htmlFor={id}>
        <span className="dropzone-icon"><Icon name={file ? 'file' : 'upload'} size={22} /></span>
        {file ? <span><b>{file.name}</b><small>{(file.size / 1024 / 1024).toFixed(1)} MB · bấm để đổi tệp</small></span> : <span><b>Kéo thả hoặc bấm để chọn tệp</b><small>{hint}</small></span>}
      </label>
    </div>
  );
}

export function DownloadLinks({ links }: { links: { label: string; href: string; primary?: boolean }[] }) {
  return (
    <div className="downloads">
      {links.map(link => (
        <a key={link.href} className={link.primary ? 'button primary small' : 'button ghost small'} href={link.href} download>
          <Icon name="download" size={15} /> {link.label}
        </a>
      ))}
    </div>
  );
}
