<script setup lang="ts">
import { STATUS_TAG, STATUS_TEXT } from '../types'

defineProps<{ status: string }>()
</script>

<template>
  <el-tag :type="(STATUS_TAG[status] || 'info') as any" size="small">
    {{ STATUS_TEXT[status] || status }}
  </el-tag>
</template>
