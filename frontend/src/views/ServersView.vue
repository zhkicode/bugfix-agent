<script setup lang="ts">
import { onMounted, reactive, ref } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import api from '../api'
import type { Server } from '../types'

const servers = ref<Server[]>([])
const loading = ref(false)
const dialogVisible = ref(false)
const editing = ref<Server | null>(null)
const testing = ref(0)

const form = reactive({
  name: '',
  host: '',
  port: 22,
  username: 'root',
  password: '',
  enabled: true,
})

async function load() {
  loading.value = true
  try {
    servers.value = await api.listServers()
  } finally {
    loading.value = false
  }
}

function openCreate() {
  editing.value = null
  Object.assign(form, { name: '', host: '', port: 22, username: 'root', password: '', enabled: true })
  dialogVisible.value = true
}

function openEdit(s: Server) {
  editing.value = s
  Object.assign(form, {
    name: s.name, host: s.host, port: s.port, username: s.username,
    password: '', enabled: s.enabled,
  })
  dialogVisible.value = true
}

async function save() {
  try {
    if (editing.value) {
      await api.updateServer(editing.value.id, form)
    } else {
      await api.createServer(form)
    }
    dialogVisible.value = false
    ElMessage.success('已保存')
    await load()
  } catch (e: any) {
    ElMessage.error(e.response?.data?.detail || '保存失败')
  }
}

async function remove(s: Server) {
  try {
    await ElMessageBox.confirm(`确认删除服务器「${s.name}」？`, '提示', { type: 'warning' })
  } catch {
    return
  }
  try {
    await api.deleteServer(s.id)
    ElMessage.success('已删除')
    await load()
  } catch (e: any) {
    ElMessage.error(e.response?.data?.detail || '删除失败')
  }
}

async function test(s: Server) {
  testing.value = s.id
  try {
    const r = await api.testServer(s.id)
    r.ok ? ElMessage.success('连接成功') : ElMessage.error(`连接失败: ${r.output}`)
  } finally {
    testing.value = 0
  }
}

async function toggle(s: Server) {
  await api.updateServer(s.id, { enabled: s.enabled })
  await load()
}

onMounted(load)
</script>

<template>
  <el-card shadow="never">
    <div class="toolbar">
      <h2 class="title">服务器管理</h2>
      <el-button type="primary" @click="openCreate">新增服务器</el-button>
    </div>
    <el-table :data="servers" v-loading="loading">
      <el-table-column prop="id" label="ID" width="60" />
      <el-table-column prop="name" label="名称" width="160" />
      <el-table-column prop="host" label="主机" min-width="160" />
      <el-table-column prop="port" label="端口" width="80" />
      <el-table-column prop="username" label="用户名" width="110" />
      <el-table-column label="启用" width="90">
        <template #default="{ row }">
          <el-switch v-model="row.enabled" @change="toggle(row)" />
        </template>
      </el-table-column>
      <el-table-column label="操作" width="230">
        <template #default="{ row }">
          <el-button size="small" :loading="testing === row.id" @click="test(row)">测试连接</el-button>
          <el-button size="small" @click="openEdit(row)">编辑</el-button>
          <el-button size="small" type="danger" @click="remove(row)">删除</el-button>
        </template>
      </el-table-column>
    </el-table>

    <el-dialog v-model="dialogVisible" :title="editing ? '编辑服务器' : '新增服务器'" width="480">
      <el-form label-width="90px">
        <el-form-item label="名称" required>
          <el-input v-model="form.name" placeholder="如：生产环境-01" />
        </el-form-item>
        <el-form-item label="主机" required>
          <el-input v-model="form.host" placeholder="IP 或域名" />
        </el-form-item>
        <el-form-item label="SSH 端口">
          <el-input-number v-model="form.port" :min="1" :max="65535" />
        </el-form-item>
        <el-form-item label="用户名">
          <el-input v-model="form.username" />
        </el-form-item>
        <el-form-item label="密码">
          <el-input
            v-model="form.password"
            type="password"
            show-password
            :placeholder="editing ? '留空表示不修改' : 'SSH 登录密码'"
          />
        </el-form-item>
        <el-form-item label="启用">
          <el-switch v-model="form.enabled" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="dialogVisible = false">取消</el-button>
        <el-button type="primary" @click="save">保存</el-button>
      </template>
    </el-dialog>
  </el-card>
</template>

<style scoped>
.toolbar {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 12px;
}
.title {
  margin: 0;
  font-size: 18px;
}
</style>
