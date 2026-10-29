import { afterEach, describe, expect, it, vi } from 'vitest';
import { cleanup, render, screen, waitFor } from '@testing-library/react';
import App from './App';

afterEach(() => { cleanup(); vi.unstubAllGlobals(); });

describe('Creator shell', () => {
  it('shows all creator modes and explicit unavailable status', async () => {
    vi.stubGlobal('fetch', vi.fn().mockImplementation((url: string) => Promise.resolve({json:()=>Promise.resolve(url.includes('capabilities') ? {modes:{text_music:{enabled:false,reason:'Catalog loop chưa sẵn sàng.'}}} : {ok:true})})));
    render(<App/>);
    expect(screen.getAllByText('Text to Music').length).toBeGreaterThan(0);
    expect(screen.getByText('Rap to Beat')).toBeInTheDocument();
    await waitFor(()=>expect(screen.getByText(/Catalog loop chưa sẵn sàng/)).toBeInTheDocument());
    expect(screen.getByRole('button',{name:/Tạo bản nghe thử/})).toBeDisabled();
  });

  it('offers provider selection but keeps paid generation disabled without provider config', async () => {
    vi.stubGlobal('fetch', vi.fn().mockImplementation((url: string) => Promise.resolve({json:()=>Promise.resolve(url.includes('capabilities') ? {modes:{text_music:{enabled:true,provider_enabled:false,reason:'Local only'}}} : {ok:true})})));
    render(<App />);
    await screen.findByText(/Backend sẵn sàng/);
    expect(screen.getByLabelText(/CÁCH TẠO/)).toBeInTheDocument();
    expect(screen.getByRole('option', {name:/AI Music Provider.*chưa cấu hình/})).toBeDisabled();
    expect(screen.getByText(/không phải AI/)).toBeInTheDocument();
  });
});
