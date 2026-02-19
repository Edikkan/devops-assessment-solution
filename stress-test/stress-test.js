/**
 * ════════════════════════════════════════════════════════════════════════════
 * DevOps Assessment — Stress Test (DNS-BYPASS VERSION)
 * ════════════════════════════════════════════════════════════════════════════
 */

import http    from 'k6/http';
import { check, sleep } from 'k6';
import { Rate, Trend } from 'k6/metrics';

// ── Custom Metrics ────────────────────────────────────────────────────────────
const errorRate = new Rate('error_rate');

// ── Configuration ─────────────────────────────────────────────────────────────
// Target the local IP directly to bypass DNS lookup failures
const BASE_URL = __ENV.BASE_URL || 'http://127.0.0.1';

// ── Load Profile ──────────────────────────────────────────────────────────────
export const options = {
  stages: [
    { duration: '2m',  target: 5000  },   // ramp to 5k VUs
    { duration: '3m',  target: 10000 },   // ramp to 10k VUs (peak)
    { duration: '5m',  target: 10000 },   // sustain 10k VUs
    { duration: '2m',  target: 0     },   // ramp down
  ],

  thresholds: {
    http_req_duration: ['p(95)<2000', 'p(99)<5000'],
    http_req_failed:   ['rate<0.01'], // Fail if errors > 1%
  },

  gracefulStop: '30s',
};

// ── Scenario ──────────────────────────────────────────────────────────────────
export default function () {
  const params = {
    headers: { 
      'Accept': 'application/json',
      'Connection': 'keep-alive',
      'Host': 'assessment.local' 
    },
    timeout: '10s', 
  };

  const res = http.get('http://127.0.0.1/api/data', params);

  const ok = check(res, {
    'status is 200': (r) => r.status === 200,
  });

  if (!ok) errorRate.add(1);

  // Back to high-intensity 0.1s sleep
  sleep(0.1); 
}
