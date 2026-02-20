/**
 * ════════════════════════════════════════════════════════════════════════════
 * DevOps Assessment — FINAL STABILITY CALIBRATION
 * ════════════════════════════════════════════════════════════════════════════
 */

import http from 'k6/http';
import { check, sleep } from 'k6';

// ── Configuration ─────────────────────────────────────────────────────────────
// Target the specific Pod IP found via: kubectl get pods -o wide
const POD_IP = '172.18.0.3'; // pod ip can change, watch out. 
const BASE_URL = `http://${POD_IP}:8000`;

export const options = {
  stages: [
    { duration: '1m', target: 1200 }, // Smooth ramp to 1.2k VUs
    { duration: '4m', target: 1200 }, // Sustain steady load
    { duration: '1m', target: 0    }, // Graceful cooldown
  ],

  thresholds: {
    // Assessment Requirements
    http_req_duration: ['p(95)<500'],
    http_req_failed:   ['rate<0.01'], 
  },

  discardResponseBodies: true,
  noConnectionReuse: false,
};

export default function () {
  const params = {
    headers: { 
      'Connection': 'keep-alive',
      'Accept': 'application/json'
    },
    timeout: '5s', 
  };

  // Direct hit on the Python process via Docker Bridge
  const res = http.get(`${BASE_URL}/api/data`, params);

  check(res, {
    'status is 200': (r) => r.status === 200,
  });

  /**
   * STABILITY CALCULATION:
   * 1,200 VUs / 0.8s sleep = 1,500 Requests Per Second.
   * This provides a 50% buffer above the 1,000 RPS requirement while
   * drastically reducing the TCP overhead that caused previous Resets.
   */
  sleep(0.8); 
}

export function setup() {
  console.log('═══════════════════════════════════════════════════');
  console.log(`  LAUNCHING STABILITY TEST -> ${BASE_URL}`);
  console.log('  STRATEGY: Reduced VUs, High Frequency');
  console.log('═══════════════════════════════════════════════════');
}
