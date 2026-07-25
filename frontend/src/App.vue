<script setup lang="ts">
// [隐盾] 根组件 — 极简导航
</script>

<template>
  <div class="app-container">
    <nav class="top-nav">
      <router-link to="/" class="nav-item">🛡️ 图片脱敏</router-link>
      <router-link to="/text" class="nav-item">📝 文本脱敏</router-link>
      <router-link to="/check" class="nav-item">🔍 强度检测</router-link>
    </nav>
    <main>
      <router-view />
    </main>
  </div>
</template>

<style>
* { margin: 0; padding: 0; box-sizing: border-box; }

body {
  background-color: #0f0f1a;
  color: #e0e0f0;
  font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
}

.app-container {
  min-height: 100vh;
}

.top-nav {
  display: flex;
  justify-content: center;
  gap: 0;
  background: #1a1a2e;
  border-bottom: 1px solid #2a2a4a;
  padding: 0;
  position: sticky;
  top: 0;
  z-index: 100;
}

.nav-item {
  padding: 14px 28px;
  color: #8888aa;
  text-decoration: none;
  font-size: 15px;
  font-weight: 500;
  border-bottom: 2px solid transparent;
  transition: all 0.2s;
}

.nav-item:hover {
  color: #c0c0e0;
  background: rgba(108, 99, 255, 0.05);
}

.nav-item.router-link-active {
  color: #6c63ff;
  border-bottom-color: #6c63ff;
}
</style>
