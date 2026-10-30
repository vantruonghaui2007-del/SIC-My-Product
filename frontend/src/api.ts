export class ApiError extends Error {}

function messageFrom(data: unknown, fallback: string): string {
  if (data && typeof data === 'object' && 'detail' in data) {
    const detail = (data as { detail: unknown }).detail;
    if (typeof detail === 'string') return detail;
    if (detail && typeof detail === 'object' && 'detail' in detail && typeof (detail as { detail: unknown }).detail === 'string') {
      return (detail as { detail: string }).detail;
    }
  }
  return fallback;
}

async function parse<T>(response: Response, fallback: string): Promise<T> {
  let data: unknown = null;
  try {
    data = await response.json();
  } catch {
    // Non-JSON bodies only matter when the request failed.
  }
  if (!response.ok) throw new ApiError(messageFrom(data, fallback));
  return data as T;
}

export async function getJSON<T>(url: string, fallback = 'Không tải được dữ liệu.'): Promise<T> {
  return parse<T>(await fetch(url), fallback);
}

export async function postJSON<T>(url: string, body: unknown, fallback = 'Yêu cầu không thành công.'): Promise<T> {
  const response = await fetch(url, { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(body) });
  return parse<T>(response, fallback);
}

export async function patchJSON<T>(url: string, body: unknown, fallback = 'Yêu cầu không thành công.'): Promise<T> {
  const response = await fetch(url, { method: 'PATCH', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(body) });
  return parse<T>(response, fallback);
}

export async function upload<T>(url: string, form: FormData, fallback = 'Không tải được tệp.'): Promise<T> {
  return parse<T>(await fetch(url, { method: 'POST', body: form }), fallback);
}

export async function createProject(mode: 'create' | 'remix' | 'mashup'): Promise<string> {
  const project = await postJSON<{ id: string }>('/api/projects', { mode }, 'Không tạo được dự án.');
  return project.id;
}

export function errorText(error: unknown): string {
  return error instanceof Error ? error.message : 'Có lỗi xảy ra.';
}
