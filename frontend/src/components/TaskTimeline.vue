<script setup lang="ts">
import type { Task } from '../types'

const props = defineProps<{ task: Task }>()

interface Stage {
  key: keyof Task
  label: string
}

const stages: Stage[] = [
  { key: 'ts_detected', label: '识别到错误' },
  { key: 'ts_cloned', label: '克隆仓库' },
  { key: 'ts_fixed', label: 'AI 修复' },
  { key: 'ts_pushed', label: '推送分支' },
  { key: 'ts_mr', label: '创建 MR/PR' },
  { key: 'ts_notified', label: '邮件通知' },
]

function fmt(v: unknown): string {
  if (!v) return ''
  const d = new Date(String(v))
  return d.toLocaleString('zh-CN', { hour12: false })
}
</script>

<template>
  <el-timeline>
    <el-timeline-item
      v-for="s in stages"
      :key="s.key"
      :timestamp="fmt(task[s.key])"
      :type="(task[s.key] ? 'success' : 'info') as any"
      :hollow="!task[s.key]"
    >
      {{ s.label }}
    </el-timeline-item>
    <el-timeline-item
      v-if="task.status === 'failed'"
      type="danger"
      :timestamp="fmt(task.updated_at)"
    >
      任务失败
    </el-timeline-item>
  </el-timeline>
</template>
