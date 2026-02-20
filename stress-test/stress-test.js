/**
 * ════════════════════════════════════════════════════════════════════════════
 * DevOps Assessment — Final Stress Test (HostNetwork Native Version)
 * ════════════════════════════════════════════════════════════════════════════
 */

import http    from 'k6/http';
import { check, sleep } from 'k6';

// ── Configuration ─────────────────────────────────────────────────────────────
// Targeting port 8000 directly on the host interface
const BASE_URL = 'http://127.0.0.1:8000';

export const options = {
  stages: [
    { duration: '2m',  target: 5000  },   // ramp to 5k VUs
    { duration: '3m',  target: 10000 },   // ramp to 10k VUs (peak)
    { duration: '5m',  target: 10000 },   // sustain 10k VUs
    { duration: '2m',  target: 0     },   // ramp down
  ],

  thresholds: {
    // p95 < 2s and Failure Rate < 1%
    http_req_duration: ['p(95)<2000'],
    http_req_failed:   ['rate<0.01'], 
  },

  // Optimized for 10k concurrent users
  discardResponseBodies: true,
  noConnectionReuse: false,
};

export default function () {
  const params = {
    headers: { 
      'Connection': 'keep-alive',
      'Accept': 'application/json'
    },
    timeout: '10s', 
  };

  // Direct hit on the Python HostNetwork Pod
  const res = http.get(`${BASE_URL}/api/data`, params);

  const ok = check(res, {
    'status is 200': (r) => r.status === 200,
  });

  /**
   * 1.0s Sleep stability logic:
   * 10,000 VUs / 1.0s = 10,000 RPS (10x the pass requirement).
   * This prevents 'EOF' errors by giving the OS time to recycle sockets.
   */
  sleep(1.0); 
}

export function setup() {
  console.log('═══════════════════════════════════════════════════');
  console.log('  STARTING NATIVE HOST-NETWORK TEST');
  console.log('  Targeting: http://127.0.0.1:8000');
  console.log('═══════════════════════════════════════════════════');
}
