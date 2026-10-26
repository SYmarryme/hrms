<script setup lang="ts">
import { useFeedback } from '../feedback';
import { formatBeijing } from '../presentation';
import { onMounted,toRef } from 'vue';
import { useDepartmentPage } from '../department-page';

const page = useDepartmentPage();
const { state, canManage } = page;
useFeedback(toRef(state,'notice'),toRef(state,'error'),'/departments');
onMounted(page.initialize);
</script>

<template>
  <div class="business-page">
    <main>
      <div class="section-heading"><div><p class="eyebrow">组织基础资料</p><h1>部门管理</h1><p class="muted">查询部门及层级；由授权 HR 维护基础信息和启停状态。</p></div>
        <button v-if="canManage" :disabled="state.busy" @click="page.beginCreate">新增部门</button></div>
      <p v-if="!canManage" class="muted">当前账号可查看部门；新增与编辑需要有效 HR 权限。</p>
      <p v-if="state.notice" class="success feedback" role="status">{{ state.notice }}</p>
      <div v-if="state.error" class="error feedback" role="alert">{{ state.error }} <button class="secondary" :disabled="state.loading" @click="page.initialize">重新加载列表</button></div>
      <section class="card department-list" aria-label="部门列表">
        <form class="search-row" @submit.prevent="page.search">
          <div><label for="department-query">部门名称或编号</label><input id="department-query" v-model="state.q" maxlength="128" placeholder="输入名称或编号"></div>
          <button type="submit" :disabled="state.loading">查询</button>
          <div><label for="department-page-size">每页条数</label><select id="department-page-size" v-model.number="state.pageSize" @change="page.search"><option :value="20">20</option><option :value="50">50</option><option :value="100">100</option></select></div>
        </form>
        <p v-if="state.loading" role="status">正在加载部门…</p>
        <p v-else-if="!state.items.length" class="muted">暂无符合条件的部门。</p>
        <div v-else class="table-scroll">
          <table><caption class="sr-only">部门查询结果</caption><thead><tr><th>编号</th><th>名称</th><th>上级部门</th><th>状态</th><th>直属 / 子树在职人数</th><th>操作</th></tr></thead>
            <tbody><tr v-for="item in state.items" :key="item.id"><td>{{ item.code }}</td><td>{{ item.name }}</td><td>{{ item.parent_name || '根部门' }}</td>
              <td><span :class="['status-badge', item.status === 'ACTIVE' ? 'active' : 'disabled']">{{ item.status === 'ACTIVE' ? '启用' : '停用' }}</span></td>
              <td>{{ item.direct_employee_count }} / {{ item.subtree_employee_count }}</td><td class="table-actions">
                <button class="text-button" :disabled="state.busy" @click="page.open(item.id)">详情</button>
                <button v-if="canManage" class="text-button" :disabled="state.busy" @click="page.open(item.id, true)">编辑</button><button v-if="canManage" class="text-button" :disabled="state.busy||state.mode==='edit'||state.mode==='new'" @click="page.toggle(item)">{{item.status==='ACTIVE'?'停用':'恢复'}}</button></td></tr></tbody></table>
        </div>
        <nav class="pagination" aria-label="部门分页"><span>共 {{ state.total }} 条 · 第 {{ state.page }} 页</span>
          <button class="secondary" :disabled="state.loading || state.page <= 1" @click="page.go(state.page - 1)">上一页</button>
          <button class="secondary" :disabled="state.loading || state.page * state.pageSize >= state.total" @click="page.go(state.page + 1)">下一页</button></nav>
      </section>

      <section v-if="state.mode" class="card department-editor" aria-labelledby="department-editor-title">
        <div class="section-heading"><h2 id="department-editor-title">{{ state.mode === 'new' ? '新增部门' : state.mode === 'edit' ? '编辑部门' : '部门详情' }}</h2><button class="secondary" data-clear-dirty :disabled="state.busy" @click="page.close">关闭</button></div>
        <template v-if="state.mode === 'detail' && state.detail">
          <dl><dt>部门编号</dt><dd>{{ state.detail.code }}</dd><dt>名称</dt><dd>{{ state.detail.name }}</dd>
            <dt>上级部门（列表快照）</dt><dd>{{ state.summary?.parent_name || (state.detail.parent_id ? '请刷新列表查看名称' : '根部门') }}</dd><dt>状态</dt><dd>{{ state.detail.status === 'ACTIVE' ? '启用' : '停用' }}</dd>
            <dt>直属在职人数（列表快照）</dt><dd>{{ state.summary?.direct_employee_count ?? '—' }}</dd><dt>子树在职人数（列表快照）</dt><dd>{{ state.summary?.subtree_employee_count ?? '—' }}</dd>
            <dt>版本</dt><dd>{{ state.detail.version_no }}</dd><dt>更新时间（北京时间）</dt><dd>{{ formatBeijing(state.detail.updated_at) }}</dd></dl>
          <button v-if="canManage" @click="page.open(state.detail.id, true)">编辑此部门</button>
        </template>
        <form v-else @submit.prevent="page.save">
          <fieldset :disabled="state.busy"><legend class="sr-only">部门基础信息</legend>
            <div class="form-columns"><div><label for="department-code">部门编号</label><input id="department-code" v-model="state.form.code" required maxlength="64"></div>
              <div><label for="department-name">部门名称</label><input id="department-name" v-model="state.form.name" required maxlength="128"></div></div>
            <label for="department-status">部门状态</label><select id="department-status" v-model="state.form.status"><option value="ACTIVE">启用</option><option value="DISABLED">停用</option></select>
            <p class="muted">停用前须处理仍启用的下级部门、在职归属和有效授权引用；系统不删除部门历史。</p>
            <div class="parent-picker"><label for="parent-query">查找上级部门</label><div class="search-row"><input id="parent-query" v-model="state.parentQ" maxlength="128" placeholder="上级名称或编号"><button type="button" class="secondary" :disabled="state.parentLoading" @click="page.parents(1)">查找</button></div>
              <label for="department-parent">上级部门</label><select id="department-parent" v-model="state.form.parent_id">
                <option :value="null">无上级（根部门）</option>
                <option v-if="state.form.parent_id && !state.parentOptions.some(item => item.id === state.form.parent_id)" :value="state.form.parent_id">当前选中的上级部门（不在本页）</option>
                <option v-for="parent in state.parentOptions.filter(item => item.id !== state.detail?.id)" :key="parent.id" :value="parent.id">{{ parent.code }} · {{ parent.name }}{{ parent.status === 'DISABLED' ? '（停用）' : '' }}</option>
              </select><div class="pagination"><span>候选第 {{ state.parentPage }} 页</span><button type="button" class="text-button" :disabled="state.parentLoading || state.parentPage <= 1" @click="page.parents(state.parentPage - 1)">上一页</button><button type="button" class="text-button" :disabled="state.parentLoading || state.parentPage * 20 >= state.parentTotal" @click="page.parents(state.parentPage + 1)">下一页</button></div>
            </div>
            <div class="form-actions"><button type="submit">{{ state.busy ? '正在保存…' : '保存部门' }}</button><button v-if="state.mode === 'edit' && state.detail" type="button" class="secondary" @click="page.open(state.detail.id, true)">重新读取详情（放弃当前输入）</button></div>
          </fieldset>
        </form>
      </section>
    </main>
  </div>
</template>
