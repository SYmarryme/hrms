import { computed, reactive, ref } from 'vue';
import { ApiError, createDepartment, getDepartment, listDepartments, me, updateDepartment,
  type Department, type DepartmentRecord, type DepartmentInput, type Profile } from './api';

const emptyForm = (): DepartmentInput => ({ code: '', name: '', parent_id: null, status: 'ACTIVE' });
const safeError = (error: unknown) => error instanceof ApiError ? error.message : '操作未完成，请重试';

export function useDepartmentPage() {
  const profile = ref<Profile | null>(null);
  const canManage = computed(() => !!profile.value?.roles.includes('HR') && !!profile.value.employee_id);
  const state = reactive({ items: [] as Department[], q: '', page: 1, pageSize: 20, total: 0,
    loading: false, busy: false, error: '', notice: '', mode: null as 'new' | 'edit' | 'detail' | null,
    detail: null as DepartmentRecord | null, summary: null as Department | null, etag: '', form: emptyForm(),
    parentOptions: [] as Department[], parentQ: '', parentPage: 1, parentTotal: 0, parentLoading: false });
  let generation = 0;
  let parentGeneration = 0;

  async function load() {
    const mine = ++generation;
    state.loading = true; state.error = '';
    try {
      const result = await listDepartments(state.q.trim(), state.page, state.pageSize);
      if (mine === generation) { state.items = result.items; state.total = result.total; }
    } catch (error) { if (mine === generation) { state.items = []; state.total = 0; state.error = safeError(error); } }
    finally { if (mine === generation) state.loading = false; }
  }
  async function initialize() {
    state.loading = true;
    try { profile.value = await me(); await load(); }
    catch (error) { state.error = safeError(error); state.loading = false; }
  }
  async function search() { state.page = 1; state.notice = ''; await load(); }
  async function go(page: number) { state.page = Math.max(1, page); await load(); }
  async function parents(page = 1) {
    const mine = ++parentGeneration;
    state.parentLoading = true;
    try {
      const result = await listDepartments(state.parentQ.trim(), page, 20);
      if (mine === parentGeneration) { state.parentPage = page; state.parentOptions = result.items; state.parentTotal = result.total; }
    } catch (error) { if (mine === parentGeneration) state.error = safeError(error); }
    finally { if (mine === parentGeneration) state.parentLoading = false; }
  }
  async function beginCreate() {
    if (!canManage.value || state.busy) return;
    state.mode = 'new'; state.detail = null; state.summary = null; state.etag = ''; state.form = emptyForm(); state.error = ''; state.notice = '';
    state.parentQ = ''; await parents();
  }
  async function open(id: string, edit = false) {
    if (state.busy || (edit && !canManage.value)) return;
    state.busy = true; state.error = ''; state.notice = '';
    try {
      const result = await getDepartment(id);
      state.detail = result.item; state.etag = result.etag; state.mode = edit ? 'edit' : 'detail';
      state.summary = state.items.find(item => item.id === id) || null;
      state.form = { code: result.item.code, name: result.item.name, parent_id: result.item.parent_id, status: result.item.status };
      if (edit) { state.parentQ = ''; await parents(); }
    } catch (error) { state.error = safeError(error); }
    finally { state.busy = false; }
  }
  async function save() {
    if (!canManage.value || state.busy || !['new', 'edit'].includes(state.mode || '')) return;
    const input: DepartmentInput = { ...state.form, code: state.form.code.trim(), name: state.form.name.trim() };
    if (!input.code || !input.name) { state.error = '部门编号和名称不能为空'; return; }
    state.busy = true; state.error = ''; state.notice = '';
    try {
      if (state.mode === 'new') { await createDepartment(input); state.notice = '部门新增成功'; }
      else { await updateDepartment(state.detail!.id, input, state.etag); state.notice = '部门更新成功'; }
      state.mode = null; state.detail = null; state.summary = null; await load();
    } catch (error) { state.error = safeError(error); }
    finally { state.busy = false; }
  }
  function close() { if (!state.busy) { state.mode = null; state.detail = null; state.summary = null; } }
  return { state, canManage, initialize, load, search, go, parents, beginCreate, open, save, close };
}
