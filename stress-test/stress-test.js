/**
 * ════════════════════════════════════════════════════════════════════════════
 * DevOps Assessment — Final Stress Test (Port-Forward Bridge Version)
 * ════════════════════════════════════════════════════════════════════════════
 */

import http    from 'k6/http';
import { check, sleep } from 'k6';
import { Rate } from 'k6/metrics';

// ── Configuration ─────────────────────────────────────────────────────────────
// We use 8080 which will be mapped via 'kubectl port-forward'
const BASE_URL = 'http://127.0.0.1:8080';

export const options = {
  stages: [
    { duration: '2m',  target: 5000  },   // ramp to 5k VUs
    { duration: '3m',  target: 10000 },   // ramp to 10k VUs (peak)
    { duration: '5m',  target: 10000 },   // sustain 10k VUs
    { duration: '2m',  target: 0     },   // ramp down
  ],

  thresholds: {
    // Target: p95 < 2s and Failure Rate < 1%
    http_req_duration: ['p(95)<2000'],
    http_req_failed:   ['rate<0.01'], 
  },

  // Performance optimizations for high-concurrency tunneling
  discardResponseBodies: true,
  noConnectionReuse: false,
  gracefulStop: '30s',
};

export default function () {
  const params = {
    headers: { 
      'Connection': 'keep-alive',
      'Accept': 'application/json'
    },
    timeout: '15s', 
  };

  // Hit the port-forward tunnel
  const res = http.get(`${BASE_URL}/api/data`, params);

  const ok = check(res, {
    'status is 200': (r) => r.status === 200,
  });

  /**
   * 1.0s Sleep is the stability anchor.
   * Total RPS Capacity = 10,000 VUs / 1.0s = 10,000 RPS.
   * This is 10x the assessment requirement and protects the tunnel from EOFs.
   */
  sleep(1.0); 
}

export function setup() {
  console.log('═══════════════════════════════════════════════════');
  console.log('  STARTING TEST VIA PORT-FORWARD TUNNEL (8080)');
  console.log('  Ensure: kubectl port-forward svc/app-python-nodeport 8080:8000');
  console.log('═══════════════════════════════════════════════════');
}
