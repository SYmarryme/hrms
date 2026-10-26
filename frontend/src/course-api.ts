import { ApiError, courseRequest, employeeFile, type CoursePath } from './api';

export interface Page<T> { items: T[]; total: number; page: number; page_size: number }
export interface Position { id: string; department_id: string; code: string; name: string; grade_code: string; status: string; version_no: number; employee_count?: number }
export interface Employee { id: string; employee_no: string; full_name: string; current_department_id: string; current_position_id: string; hire_date: string; employment_status: string; version_no: number; history?: {event_type: string; created_at: string}[] }
export interface Leave { id: string; employee_id: string; department_id: string; start_date: string; end_date: string; leave_type: string; reason: string; status: string; opinion: string | null; decided_at: string | null; version_no: number }
export interface Salary { id: string; employee_id: string; month: string; amount: string; version_no: number }
export interface User { id: string; username: string; employee_id: string | null; roles: string[]; department_ids: string[]; status: string; version_no: number }
export interface ImportResult { valid: boolean; errors: {row: number; code: string}[]; imported: number; count?: number }
export function courseApi<T>(path: CoursePath, method = 'GET', body?: unknown, etag?: string): Promise<T> {
  return courseRequest<T>(path, { method, ...(body === undefined ? {} : { body: JSON.stringify(body) }) }, etag);
}
export const tag = (row: {version_no: number}) => `"v${row.version_no}"`;
export async function all<T>(path: '/positions' | '/employees' | '/users'): Promise<T[]> {
  const items: T[] = [];
  let page = 1;
  for (;;) {
    const result = await courseApi<Page<T>>(`${path}?page=${page}&page_size=100`);
    items.push(...result.items);
    if (items.length >= result.total || result.items.length === 0) return items;
    page += 1;
  }
}
export async function importEmployees(file: Blob, format: 'csv' | 'xlsx', mode: 'preflight' | 'commit'): Promise<ImportResult> {
  if (file.size > 2 * 1024 * 1024) throw new ApiError(413, 'FILE_TOO_LARGE', '文件不能超过2 MiB');
  return courseRequest(`/employees/import?format=${format}&mode=${mode}`, { method: 'POST', body: await file.arrayBuffer() });
}
export function downloadEmployees(format: 'csv' | 'xlsx', template: boolean, q = ''): Promise<Blob> {
  return template ? employeeFile(`/employees/template?format=${format}`) : employeeFile(`/employees/export?format=${format}&q=${encodeURIComponent(q)}`);
}
export function saveFile(blob: Blob, name: string) {
  const url = URL.createObjectURL(blob); const link = document.createElement('a');
  link.href = url; link.download = name; link.click(); setTimeout(() => URL.revokeObjectURL(url), 1000);
}
export const errorText = (failure: unknown) => failure instanceof Error ? failure.message : '操作失败，请重试';
