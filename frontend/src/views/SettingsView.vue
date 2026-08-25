<script setup lang="ts">
import { onMounted, reactive, ref } from 'vue'
import { ElMessage } from 'element-plus'
import api from '../api'

const loading = ref(false)
const saving = ref(false)
const testing = ref(false)

const form = reactive<Record<string, string>>({})

interface Field {
  key: string
  label: string
  type: 'str' | 'bool' | 'select' | 'password'
  options?: string[]
}

interface Group {
  title: string
  fields: Field[]
  hint?: string
}

const groups: Group[] = [
  {
    title: '通知',
    fields: [
      { key: 'notify.enabled', label: '启用邮件通知', type: 'bool' },
      { key: 'notify.recipients', label: '收件人（逗号分隔）', type: 'str' },
    ],
  },
  {
    title: 'SMTP 配置',
    fields: [
      { key: 'smtp.host', label: 'SMTP 服务器', type: 'str' },
      { key: 'smtp.port', label: '端口', type: 'str' },
      { key: 'smtp.secure', label: '加密方式', type: 'select', options: ['ssl', 'starttls', 'none'] },
      { key: 'smtp.user', label: '账号', type: 'str' },
      { key: 'smtp.pass', label: '授权码', type: 'password' },
      { key: 'smtp.from', label: '发件人（留空同账号）', type: 'str' },
    ],
  },
  {
    title: '轮询与去重',
    fields: [
      { key: 'poll.default_interval_sec', label: '默认轮询间隔（秒）', type: 'str' },
      { key: 'poll.initial_lookback_sec', label: '首次回看时长（秒）', type: 'str' },
      { key: 'dedup.cooldown_hours', label: '去重冷却时间（小时）', type: 'str' },
    ],
  },
  {
    title: 'Claude CLI 认证',
    fields: [
      { key: 'claude.auth_token', label: '认证令牌 (ANTHROPIC_AUTH_TOKEN)', type: 'password' },
      { key: 'claude.base_url', label: 'API 网关 (ANTHROPIC_BASE_URL)', type: 'str' },
      { key: 'claude.model', label: '模型 (ANTHROPIC_MODEL)', type: 'str' },
    ],
    hint: '留空则使用容器内已有环境认证。配置后点上方「测试 Claude」验证。',
  },
  {
    title: 'multica CLI',
    fields: [
      { key: 'multica.create_cmd', label: '创建任务命令', type: 'str' },
      { key: 'multica.id_regex', label: '任务 ID 提取正则', type: 'str' },
      { key: 'multica.status_cmd', label: '查询状态命令', type: 'str' },
    ],
    hint: '占位符：{title} {desc} {task_id}。认证：服务器 .env 中配置 MULTICA_TOKEN 后重启容器。',
  },
  {
    title: 'Claude CLI',
    fields: [
      { key: 'claude.path', label: 'claude 可执行文件路径', type: 'str' },
      { key: 'claude.timeout_sec', label: '超时（秒）', type: 'str' },
    ],
  },
]

async function load() {
  loading.value = true
  try {
    const { values } = await api.getSettings()
    Object.assign(form, values)
  } finally {
    loading.value = false
  }
}

async function save() {
  saving.value = true
  try {
    await api.updateSettings({ ...form })
    ElMessage.success('已保存')
  } catch (e: any) {
    ElMessage.error('保存失败')
  } finally {
    saving.value = false
  }
}

async function testSmtp() {
  testing.value = true
  try {
    await save()
    const r = await api.testSmtp(form['notify.recipients'] || '')
    r.ok ? ElMessage.success(r.message) : ElMessage.error(r.message)
  } finally {
    testing.value = false
  }
}

async function testTool(key: 'claude' | 'multica') {
  testing.value = true
  try {
    await save()
    const r = key === 'claude' ? await api.testClaude() : await api.testMultica()
    r.ok ? ElMessage.success(r.message) : ElMessage.error(r.message)
  } catch (e: any) {
    ElMessage.error(e.response?.data?.detail || '测试失败')
  } finally {
    testing.value = false
  }
}

onMounted(load)
</script>

<template>
  <el-card shadow="never" v-loading="loading">
    <div class="toolbar">
      <h2 class="title">系统设置</h2>
      <div>
        <el-button :loading="testing" @click="testSmtp">测试邮件</el-button>
        <el-button :loading="testing" @click="testTool('claude')">测试 Claude</el-button>
        <el-button :loading="testing" @click="testTool('multica')">测试 multica</el-button>
        <el-button type="primary" :loading="saving" @click="save">保存全部</el-button>
      </div>
    </div>

    <el-form label-width="200px" class="settings-form">
      <template v-for="g in groups" :key="g.title">
        <el-divider content-position="left">{{ g.title }}</el-divider>
        <div v-if="g.hint" class="hint">{{ g.hint }}</div>
        <el-form-item v-for="f in g.fields" :key="f.key" :label="f.label">
          <el-switch v-if="f.type === 'bool'" :model-value="form[f.key] === 'true'"
            @update:model-value="form[f.key] = $event ? 'true' : 'false'" />
          <el-select v-else-if="f.type === 'select'" v-model="form[f.key]" style="width: 200px">
            <el-option v-for="o in f.options" :key="o" :value="o" :label="o" />
          </el-select>
          <el-input v-else-if="f.type === 'password'" v-model="form[f.key]" type="password" show-password
            style="width: 420px" />
          <el-input v-else v-model="form[f.key]" style="width: 420px" />
        </el-form-item>
      </template>
    </el-form>
  </el-card>
</template>

<style scoped>
.toolbar {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 4px;
}
.title {
  margin: 0;
  font-size: 18px;
}
.hint {
  color: #909399;
  font-size: 13px;
  margin: 0 0 8px 12px;
}
.settings-form {
  max-width: 720px;
}
</style>
