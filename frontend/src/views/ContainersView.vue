<script setup lang="ts">
import { onMounted, reactive, ref } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import api from '../api'
import type { Container, DockerContainerInfo, Server } from '../types'

const containers = ref<Container[]>([])
const servers = ref<Server[]>([])
const loading = ref(false)
const dialogVisible = ref(false)
const editing = ref<Container | null>(null)
const busyId = ref(0)

const dockerList = ref<DockerContainerInfo[]>([])
const dockerLoading = ref(false)
const dockerError = ref('')

const form = reactive({
  server_id: undefined as number | undefined,
  name: '',
  repo_provider: 'gitlab' as 'gitlab' | 'github',
  repo_url: '',
  repo_token: '',
  repo_default_branch: 'main',
  poll_interval_sec: 60,
  enabled: true,
})

async function load() {
  loading.value = true
  try {
    ;[containers.value, servers.value] = await Promise.all([
      api.listContainers(),
      api.listServers(),
    ])
  } finally {
    loading.value = false
  }
}

async function loadDockerList() {
  dockerList.value = []
  dockerError.value = ''
  if (!form.server_id) return
  dockerLoading.value = true
  try {
    const r = await api.dockerContainers(form.server_id)
    if (r.ok) {
      dockerList.value = r.items
    } else {
      dockerError.value = r.output || '获取容器列表失败'
    }
  } catch (e: any) {
    dockerError.value = e.response?.data?.detail || '获取容器列表失败'
  } finally {
    dockerLoading.value = false
  }
}

function isMonitored(name: string): boolean {
  // 正在编辑的容器自身不算重复
  return containers.value.some(c => c.name === name && c.id !== editing.value?.id)
}

function openCreate() {
  editing.value = null
  Object.assign(form, {
    server_id: servers.value[0]?.id, name: '', repo_provider: 'gitlab',
    repo_url: '', repo_token: '', repo_default_branch: 'main',
    poll_interval_sec: 60, enabled: true,
  })
  dialogVisible.value = true
  loadDockerList()
}

function openEdit(c: Container) {
  editing.value = c
  Object.assign(form, {
    server_id: c.server_id, name: c.name, repo_provider: c.repo_provider,
    repo_url: c.repo_url, repo_token: '', repo_default_branch: c.repo_default_branch,
    poll_interval_sec: c.poll_interval_sec, enabled: c.enabled,
  })
  dialogVisible.value = true
  loadDockerList()
}

async function save() {
  if (!form.server_id) {
    ElMessage.warning('请选择所属服务器')
    return
  }
  try {
    if (editing.value) {
      await api.updateContainer(editing.value.id, form)
    } else {
      await api.createContainer(form)
    }
    dialogVisible.value = false
    ElMessage.success('已保存')
    await load()
  } catch (e: any) {
    ElMessage.error(e.response?.data?.detail || '保存失败')
  }
}

async function remove(c: Container) {
  try {
    await ElMessageBox.confirm(
      `确认删除容器「${c.name}」？其历史任务也会一并删除。`, '提示', { type: 'warning' }
    )
  } catch {
    return
  }
  await api.deleteContainer(c.id)
  ElMessage.success('已删除')
  await load()
}

async function pollNow(c: Container) {
  busyId.value = c.id
  try {
    const r = await api.pollNow(c.id)
    if (r.error) {
      ElMessage.error(String(r.error))
    } else {
      const map: Record<string, string> = {
        no_new_logs: '无新增日志',
        no_error: '有新日志，但未发现需修复的错误',
        duplicate_skipped: '发现错误，但命中去重规则，已跳过（防止重复修复）',
        busy: '该容器已有进行中的任务，已暂缓',
        task_created: `已创建修复任务 #${r.task_id}`,
      }
      ElMessage.info(map[String(r.status)] || JSON.stringify(r))
    }
  } finally {
    busyId.value = 0
  }
}

async function testRepo(c: Container) {
  busyId.value = c.id
  try {
    const r = await api.testRepo(c.id)
    r.ok ? ElMessage.success('仓库凭据有效') : ElMessage.error(`仓库访问失败: ${r.output}`)
  } finally {
    busyId.value = 0
  }
}

async function toggle(c: Container) {
  await api.updateContainer(c.id, { enabled: c.enabled })
  await load()
}

onMounted(load)
</script>

<template>
  <el-card shadow="never">
    <div class="toolbar">
      <h2 class="title">容器监控</h2>
      <el-button type="primary" @click="openCreate">新增容器</el-button>
    </div>
    <el-table :data="containers" v-loading="loading">
      <el-table-column prop="id" label="ID" width="60" />
      <el-table-column prop="name" label="容器名" width="160" />
      <el-table-column prop="server_name" label="服务器" width="130" />
      <el-table-column label="仓库" min-width="240" show-overflow-tooltip>
        <template #default="{ row }">
          <el-tag size="small" :type="row.repo_provider === 'github' ? 'warning' : 'primary'" class="tag">
            {{ row.repo_provider }}
          </el-tag>
          {{ row.repo_url || '未配置' }}
        </template>
      </el-table-column>
      <el-table-column prop="repo_default_branch" label="默认分支" width="100" />
      <el-table-column label="轮询(秒)" width="90" prop="poll_interval_sec" />
      <el-table-column label="监控" width="80">
        <template #default="{ row }">
          <el-switch v-model="row.enabled" @change="toggle(row)" />
        </template>
      </el-table-column>
      <el-table-column label="操作" width="300" fixed="right">
        <template #default="{ row }">
          <el-button size="small" type="primary" :loading="busyId === row.id" @click="pollNow(row)">
            立即轮询
          </el-button>
          <el-button size="small" :loading="busyId === row.id" @click="testRepo(row)">测试仓库</el-button>
          <el-button size="small" @click="openEdit(row)">编辑</el-button>
          <el-button size="small" type="danger" @click="remove(row)">删除</el-button>
        </template>
      </el-table-column>
    </el-table>

    <el-dialog v-model="dialogVisible" :title="editing ? '编辑容器' : '新增容器'" width="560">
      <el-form label-width="100px">
        <el-form-item label="所属服务器" required>
          <el-select
            v-model="form.server_id"
            placeholder="选择服务器"
            style="width: 100%"
            @change="loadDockerList"
          >
            <el-option v-for="s in servers" :key="s.id" :value="s.id" :label="`${s.name} (${s.host})`" />
          </el-select>
        </el-form-item>
        <el-form-item label="容器" required>
          <el-select
            v-model="form.name"
            :loading="dockerLoading"
            filterable
            allow-create
            default-first-option
            placeholder="选择正在运行的容器，或手动输入名称"
            style="width: 100%"
          >
            <el-option
              v-for="d in dockerList"
              :key="d.name"
              :value="d.name"
              :label="d.name"
              :disabled="isMonitored(d.name)"
            >
              <span class="docker-name">{{ d.name }}</span>
              <span class="docker-meta">{{ d.image }}</span>
              <span class="docker-meta">{{ d.status }}</span>
              <el-tag v-if="isMonitored(d.name)" size="small" type="info" class="docker-tag">已监控</el-tag>
            </el-option>
          </el-select>
          <div v-if="dockerError" class="docker-error">
            获取容器列表失败：{{ dockerError }}（仍可手动输入容器名）
          </div>
          <div v-else-if="!dockerLoading && !dockerList.length && form.server_id" class="docker-error">
            该服务器上没有正在运行的容器
          </div>
        </el-form-item>
        <el-form-item label="代码托管">
          <el-radio-group v-model="form.repo_provider">
            <el-radio value="gitlab">极狐 GitLab / GitLab</el-radio>
            <el-radio value="github">GitHub</el-radio>
          </el-radio-group>
        </el-form-item>
        <el-form-item label="仓库 URL" required>
          <el-input v-model="form.repo_url" placeholder="https://jihulab.com/group/repo.git" />
        </el-form-item>
        <el-form-item label="访问 Token" required>
          <el-input
            v-model="form.repo_token"
            type="password"
            show-password
            :placeholder="editing ? '留空表示不修改' : '仓库访问令牌（需 api / repo 权限）'"
          />
        </el-form-item>
        <el-form-item label="默认分支">
          <el-input v-model="form.repo_default_branch" placeholder="main" />
        </el-form-item>
        <el-form-item label="轮询间隔">
          <el-input-number v-model="form.poll_interval_sec" :min="10" :max="86400" :step="10" />
          <span class="unit">秒</span>
        </el-form-item>
        <el-form-item label="启用监控">
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
.tag {
  margin-right: 6px;
}
.unit {
  margin-left: 8px;
  color: #909399;
}
.docker-name {
  font-weight: 500;
}
.docker-meta {
  margin-left: 10px;
  font-size: 12px;
  color: #909399;
}
.docker-tag {
  margin-left: 8px;
}
.docker-error {
  font-size: 12px;
  color: #e6a23c;
  line-height: 1.6;
  margin-top: 4px;
}
</style>
