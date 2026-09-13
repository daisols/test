import axios from 'axios';

const configuredBaseURL = import.meta.env.VITE_API_BASE_URL?.trim();
const browserHost = typeof window !== 'undefined' ? window.location.hostname : '127.0.0.1';

// An explicit environment value is authoritative. Rewriting 127.0.0.1 to
// the browser hostname breaks a backend started on the loopback interface
// whenever the UI is opened through a LAN URL.
const baseURL = configuredBaseURL || `http://${browserHost}:8000/`;

const instance = axios.create({ baseURL });
export default instance;
