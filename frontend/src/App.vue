<template>
  <div class="app-shell">
    <header class="topbar">
      <router-link class="brand" to="/" aria-label="FieldMoist dashboard">
        <span class="brand-mark"><i class="fa-solid fa-droplet" /></span>
        <span>
          <strong>FieldMoist</strong>
          <small>Daily farmland soil moisture products</small>
        </span>
      </router-link>
      <div class="topbar-actions">
        <nav class="primary-nav" aria-label="Primary navigation">
          <router-link to="/"><i class="fa-solid fa-map" /> Explore</router-link>
          <router-link to="/generate"><i class="fa-solid fa-gears" /> Generate</router-link>
        </nav>
        <div class="system-status">
          <span class="status-dot" :class="{ offline: !apiOnline }" />
          {{ apiOnline ? 'API connected' : 'API unavailable' }}
        </div>
      </div>
    </header>
    <main>
      <router-view @api-status="apiOnline = $event" />
    </main>
  </div>
</template>

<script setup>
import { ref } from 'vue';

const apiOnline = ref(true);
</script>
