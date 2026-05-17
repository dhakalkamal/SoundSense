// ─── Backend configuration ────────────────────────────────────────────────────
// Single source of truth for the host. Change API_HOST to re-target the backend.
const API_HOST = '10.250.254.2:8000';

export const BASE_URL = `http://${API_HOST}/api/v1`;
export const WS_URL   = `ws://${API_HOST}/ws/audio`;
