import axios from 'axios'
import type { Container, DashboardStats, DockerContainerInfo, Server, Task, TaskPage } from '../types'

const http = axios.create({ baseURL: '/api', timeout: 120000 })

export default {
  // servers
  listServers: () => http.get<Server[]>('/servers').then(r => r.data),
  createServer: (data: Partial<Server>) => http.post<Server>('/servers', data).then(r => r.data),
  updateServer: (id: number, data: Partial<Server>) =>
    http.put<Server>(`/servers/${id}`, data).then(r => r.data),
  deleteServer: (id: number) => http.delete(`/servers/${id}`).then(r => r.data),
  testServer: (id: number) => http.post<{ ok: boolean; output: string }>(`/servers/${id}/test`).then(r => r.data),
  dockerContainers: (id: number) =>
    http.get<{ ok: boolean; output: string; items: DockerContainerInfo[] }>(`/servers/${id}/docker-containers`).then(r => r.data),

  // containers
  listContainers: () => http.get<Container[]>('/containers').then(r => r.data),
  createContainer: (data: Partial<Container>) =>
    http.post<Container>('/containers', data).then(r => r.data),
  updateContainer: (id: number, data: Partial<Container>) =>
    http.put<Container>(`/containers/${id}`, data).then(r => r.data),
  deleteContainer: (id: number) => http.delete(`/containers/${id}`).then(r => r.data),
  pollNow: (id: number) => http.post<Record<string, unknown>>(`/containers/${id}/poll-now`).then(r => r.data),
  testRepo: (id: number) => http.post<{ ok: boolean; output: string }>(`/containers/${id}/test-repo`).then(r => r.data),

  // tasks
  listTasks: (params: Record<string, unknown>) =>
    http.get<TaskPage>('/tasks', { params }).then(r => r.data),
  getTask: (id: number) => http.get<Task>(`/tasks/${id}`).then(r => r.data),
  retryTask: (id: number) => http.post(`/tasks/${id}/retry`).then(r => r.data),

  // settings
  getSettings: () => http.get<{ values: Record<string, string> }>('/settings').then(r => r.data),
  updateSettings: (values: Record<string, string>) =>
    http.put('/settings', { values }).then(r => r.data),
  testSmtp: (recipient: string) =>
    http.post<{ ok: boolean; message: string }>('/settings/test-smtp', { recipient }).then(r => r.data),
  testClaude: () =>
    http.post<{ ok: boolean; message: string }>('/settings/test-claude').then(r => r.data),
  testMultica: () =>
    http.post<{ ok: boolean; message: string }>('/settings/test-multica').then(r => r.data),

  // dashboard
  stats: () => http.get<DashboardStats>('/dashboard/stats').then(r => r.data),
}
