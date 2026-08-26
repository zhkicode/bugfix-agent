<script setup lang="ts">
import { computed, onMounted, onUnmounted, ref } from 'vue'
import { useRoute } from 'vue-router'
import { ElMessage } from 'element-plus'
import api from '../api'
import type { DashboardStats, Task } from '../types'
import StatusTag from '../components/StatusTag.vue'
import TaskTimeline from '../components/TaskTimeline.vue'

const route = useRoute()

const stats = ref<DashboardStats | null>(null)
const tasks = ref<Task[]>([])
const total = ref(0)
const page = ref(1)
const statusFilter = ref('')
const loading = ref(false)

const detail = ref<Task | null>(null)
const detailVisible = ref(false)

let timer: number | undefined

async function refresh() {
  const [s, t] = await Promise.all([
    api.stats(),
    api.listTasks({
      page: page.value,
      page_size: 20,
      status: statusFilter.value || undefined,
    }),
  ])
  stats.value = s
  tasks.value = t.items
  total.value = t.total
}

async function load() {
  loading.value = true
  try {
    await refresh()
  } finally {
    loading.value = false
  }
}

async function openDetail(id: number) {
  detail.value = await api.getTask(id)
  detailVisible.value = true
}

async function retry(id: number) {
  try {
    await api.retryTask(id)
    ElMessage.success('已重新触发修复')
    await refresh()
    if (detail.value?.id === id) detail.value = await api.getTask(id)
  } catch (e: any) {
    ElMessage.error(e.response?.data?.detail || '重试失败')
  }
}

function fmtTime(v?: string | null): string {
  if (!v) return '-'
  return new Date(v).toLocaleString('zh-CN', { hour12: false })
}

const statusOptions = computed(() => [
  { value: '', label: '全部' },
  { value: 'active', label: '进行中' },
  { value: 'detected', label: '已识别' },
  { value: 'fixing', label: 'AI 修复中' },
  { value: 'mr_created', label: 'MR/PR 已建' },
  { value: 'done', label: '完成' },
  { value: 'failed', label: '失败' },
])

onMounted(() => {
  load()
  // 深链接：/?task=N 直接打开任务详情抽屉
  const taskParam = Number(route.query.task)
  if (taskParam > 0) openDetail(taskParam)
  timer = window.setInterval(refresh, 5000)
})
onUnmounted(() => window.clearInterval(timer))
</script>

<template>
  <div>
    <el-row :gutter="16" class="cards">
      <el-col :span="6" v-for="card in [
        { label: '任务总数', value: stats?.tasks_total ?? 0, color: '#409eff' },
        { label: '进行中', value: stats?.tasks_active ?? 0, color: '#e6a23c' },
        { label: '已完成', value: stats?.tasks_done ?? 0, color: '#67c23a' },
        { label: '失败', value: stats?.tasks_failed ?? 0, color: '#f56c6c' },
      ]" :key="card.label">
        <el-card shadow="never">
          <div class="stat-label">{{ card.label }}</div>
          <div class="stat-value" :style="{ color: card.color }">{{ card.value }}</div>
        </el-card>
      </el-col>
    </el-row>

    <el-card shadow="never">
      <div class="toolbar">
        <el-select v-model="statusFilter" style="width: 140px" @change="page = 1; load()">
          <el-option v-for="o in statusOptions" :key="o.value" :value="o.value" :label="o.label" />
        </el-select>
        <el-button :loading="loading" @click="load">刷新</el-button>
        <span class="hint">每 5 秒自动刷新 · 监控 {{ stats?.containers ?? 0 }} 个容器</span>
      </div>

      <el-table :data="tasks" v-loading="loading" @row-click="(r: Task) => openDetail(r.id)" style="cursor: pointer">
        <el-table-column prop="id" label="ID" width="70" />
        <el-table-column prop="container_name" label="容器" width="140" />
        <el-table-column prop="error_type" label="错误类型" width="180" show-overflow-tooltip />
        <el-table-column prop="message" label="错误信息" min-width="220" show-overflow-tooltip />
        <el-table-column label="状态" width="110">
          <template #default="{ row }">
            <StatusTag :status="row.status" />
          </template>
        </el-table-column>
        <el-table-column label="MR/PR" width="100">
          <template #default="{ row }">
            <el-link v-if="row.mr_url" :href="row.mr_url" target="_blank" type="primary" @click.stop>
              查看
            </el-link>
            <span v-else>-</span>
          </template>
        </el-table-column>
        <el-table-column label="重试" width="80">
          <template #default="{ row }">
            <el-button v-if="row.status === 'failed'" size="small" type="warning" @click.stop="retry(row.id)">
              重试
            </el-button>
          </template>
        </el-table-column>
        <el-table-column label="更新时间" width="170">
          <template #default="{ row }">{{ fmtTime(row.updated_at) }}</template>
        </el-table-column>
      </el-table>

      <el-pagination
        v-model:current-page="page"
        :page-size="20"
        :total="total"
        layout="total, prev, pager, next"
        style="margin-top: 12px; justify-content: flex-end"
        @current-change="load"
      />
    </el-card>

    <el-drawer v-model="detailVisible" :title="detail ? `任务 #${detail.id}` : ''" size="50%">
      <template v-if="detail">
        <el-descriptions :column="2" border size="small" class="detail-desc">
          <el-descriptions-item label="容器">{{ detail.container_name }}</el-descriptions-item>
          <el-descriptions-item label="状态"><StatusTag :status="detail.status" /></el-descriptions-item>
          <el-descriptions-item label="错误类型" :span="2">{{ detail.error_type }}</el-descriptions-item>
          <el-descriptions-item label="错误信息" :span="2">{{ detail.message }}</el-descriptions-item>
          <el-descriptions-item label="重试次数">{{ detail.retry_count }}</el-descriptions-item>
          <el-descriptions-item label="修复分支" :span="2">
            <code v-if="detail.branch_name">{{ detail.branch_name }}</code>
            <span v-else>-</span>
          </el-descriptions-item>
          <el-descriptions-item label="MR/PR" :span="2">
            <el-link v-if="detail.mr_url" :href="detail.mr_url" target="_blank" type="primary">
              {{ detail.mr_url }}
            </el-link>
            <span v-else>-</span>
          </el-descriptions-item>
          <el-descriptions-item label="指纹" :span="2">
            <code class="fp">{{ detail.fingerprint }}</code>
          </el-descriptions-item>
        </el-descriptions>

        <el-divider content-position="left">执行进度</el-divider>
        <TaskTimeline :task="detail" />
        <div v-if="detail.status === 'failed'" class="retry-row">
          <el-button type="warning" @click="retry(detail.id)">重试修复</el-button>
        </div>

        <template v-if="detail.error_detail">
          <el-divider content-position="left">失败原因</el-divider>
          <pre class="pre">{{ detail.error_detail }}</pre>
        </template>

        <template v-if="detail.stack_summary">
          <el-divider content-position="left">堆栈摘要</el-divider>
          <pre class="pre">{{ detail.stack_summary }}</pre>
        </template>

        <template v-if="detail.claude_output">
          <el-divider content-position="left">AI 修复说明</el-divider>
          <pre class="pre">{{ detail.claude_output }}</pre>
        </template>

        <template v-if="detail.logs && detail.logs.length">
          <el-divider content-position="left">执行日志</el-divider>
          <el-timeline>
            <el-timeline-item
              v-for="l in detail.logs"
              :key="l.id"
              :type="l.level === 'error' ? 'danger' : l.level === 'warn' ? 'warning' : 'primary'"
              :timestamp="fmtTime(l.created_at)"
            >
              <b>{{ l.stage }}</b> — {{ l.message }}
            </el-timeline-item>
          </el-timeline>
        </template>
      </template>
    </el-drawer>
  </div>
</template>

<style scoped>
.cards {
  margin-bottom: 16px;
}
.stat-label {
  color: #909399;
  font-size: 13px;
}
.stat-value {
  font-size: 28px;
  font-weight: 600;
  margin-top: 4px;
}
.toolbar {
  display: flex;
  align-items: center;
  gap: 12px;
  margin-bottom: 12px;
}
.hint {
  color: #909399;
  font-size: 13px;
}
.detail-desc {
  margin-bottom: 8px;
}
.fp {
  font-size: 12px;
  word-break: break-all;
}
.pre {
  background: #f5f7fa;
  border: 1px solid #e4e7ed;
  border-radius: 4px;
  padding: 10px;
  font-size: 12px;
  white-space: pre-wrap;
  word-break: break-all;
  max-height: 260px;
  overflow: auto;
}
.retry-row {
  margin: 8px 0;
}
</style>
