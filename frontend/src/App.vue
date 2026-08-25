<script setup lang="ts">
import { useRoute } from 'vue-router'
import { computed } from 'vue'

const route = useRoute()
const active = computed(() => '/' + (route.path.split('/')[1] || ''))
</script>

<template>
  <el-container class="layout">
    <el-aside width="200px" class="aside">
      <div class="logo">🐞 BugfixAgent</div>
      <el-menu router :default-active="active" class="menu">
        <el-menu-item index="/">
          <span>任务面板</span>
        </el-menu-item>
        <el-menu-item index="/servers">
          <span>服务器</span>
        </el-menu-item>
        <el-menu-item index="/containers">
          <span>容器监控</span>
        </el-menu-item>
        <el-menu-item index="/settings">
          <span>系统设置</span>
        </el-menu-item>
      </el-menu>
    </el-aside>
    <el-main class="main">
      <router-view />
    </el-main>
  </el-container>
</template>

<style>
body {
  margin: 0;
  background: #f5f7fa;
}
.layout {
  min-height: 100vh;
}
.aside {
  background: #fff;
  border-right: 1px solid #e4e7ed;
}
.logo {
  font-size: 18px;
  font-weight: 600;
  padding: 20px 16px;
  color: #303133;
}
.menu {
  border-right: none;
}
.main {
  padding: 20px;
}
</style>
