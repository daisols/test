import { createApp } from 'vue'
import './styles/index.css'
import App from './App.vue'
import router from './router'
createApp(App)
    .use(router)
    .mount('#app')

if ('serviceWorker' in navigator) {
    window.addEventListener('load', () => {
        navigator.serviceWorker.register(`${import.meta.env.BASE_URL}map-cache-sw.js`).catch(() => {
            // Map caching is an enhancement; the application remains usable without it.
        })
    })
}
