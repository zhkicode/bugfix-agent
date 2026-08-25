export interface Server {
  id: number
  name: string
  host: string
  port: number
  username: string
  password: string
  enabled: boolean
  created_at: string
}

export interface DockerContainerInfo {
  name: string
  image: string
  status: string
}

export interface Container {
  id: number
  server_id: number
  server_name: string
  name: string
  repo_provider: 'gitlab' | 'github'
  repo_url: string
  repo_token: string
  repo_default_branch: string
  poll_interval_sec: number
  enabled: boolean
  last_log_ts: number | null
  created_at: string
}

export interface FixLog {
  id: number
  stage: string
  level: string
  message: string
  created_at: string
}

export interface Task {
  id: number
  container_id: number
  container_name: string
  error_type: string
  message: string
  status: string
  multica_task_id: string
  branch_name: string
  mr_url: string
  retry_count: number
  fingerprint: string
  created_at: string
  updated_at: string
  // 详情字段
  stack_summary?: string
  suspect_files?: string[]
  log_excerpt?: string
  error_detail?: string
  claude_output?: string
  ts_detected?: string
  ts_multica?: string | null
  ts_cloned?: string | null
  ts_fixed?: string | null
  ts_pushed?: string | null
  ts_mr?: string | null
  ts_notified?: string | null
  logs?: FixLog[]
}

export interface TaskPage {
  total: number
  items: Task[]
}

export interface DashboardStats {
  servers: number
  containers: number
  tasks_total: number
  tasks_active: number
  tasks_done: number
  tasks_failed: number
  by_status: Record<string, number>
}

export const STATUS_TEXT: Record<string, string> = {
  detected: '已识别',
  multica_created: 'multica 已建',
  cloning: '克隆仓库',
  fixing: 'AI 修复中',
  pushing: '推送分支',
  mr_created: 'MR/PR 已建',
  notified: '已通知',
  done: '完成',
  failed: '失败',
}

export const STATUS_TAG: Record<string, string> = {
  detected: 'info',
  multica_created: 'info',
  cloning: 'primary',
  fixing: 'warning',
  pushing: 'primary',
  mr_created: 'success',
  notified: 'success',
  done: 'success',
  failed: 'danger',
}
