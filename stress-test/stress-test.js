/**
 * ════════════════════════════════════════════════════════════════════════════
 * DevOps Assessment — Final Stress Test (F8s_v2 Optimized)
 * ════════════════════════════════════════════════════════════════════════════
 */

import http    from 'k6/http';
import { check, sleep } from 'k6';
import { Rate } from 'k6/metrics';

// ── Custom Metrics ────────────────────────────────────────────────────────────
const errorRate = new Rate('error_rate');

// ── Configuration ─────────────────────────────────────────────────────────────
// Target the local IP directly to bypass DNS lookup bottlenecks
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
    // Assessment Criteria: p95 < 2s, p99 < 5s, Failure < 1%
    http_req_duration: ['p(95)<2000', 'p(99)<5000'],
    http_req_failed:   ['rate<0.01'], 
  },

  // Optimization: Allow k6 to reuse connections aggressively
  discardResponseBodies: true,
  noConnectionReuse: false,
  gracefulStop: '30s',
};

// ── Scenario ──────────────────────────────────────────────────────────────────
export default function () {
  const params = {
    headers: { 
      'Accept': 'application/json',
      'Connection': 'keep-alive',
      'Host': 'assessment.local' // Mandatory for Ingress routing
    },
    timeout: '15s', // High timeout to capture slow requests rather than EOFs
  };

  // ── Primary endpoint under test ───────────────────────────────────────────
  const res = http.get(`${BASE_URL}/api/data`, params);

  const ok = check(res, {
    'status is 200': (r) => r.status === 200,
  });

  if (!ok) {
    errorRate.add(1);
  }

  /**
   * STABILITY FIX: 1.0s sleep
   * Logic: 10,000 VUs / 1.0s = 10,000 Potential Requests Per Second.
   * This provides a massive buffer to prevent TCP port exhaustion while 
   * still smashing the 1,000 req/s assessment target.
   */
  sleep(1.0); 
}

// ── Setup (runs once before load) ────────────────────────────────────────────
export function setup() {
  console.log('═══════════════════════════════════════════════════');
  console.log('  FINAL SUBMISSION RUN — F8s_v2 Optimized');
  console.log(`  Target URL : ${BASE_URL} (Host: assessment.local)`);
  console.log('  Peak Load  : 10,000 Concurrent Users');
  console.log('═══════════════════════════════════════════════════');

  const res = http.get(`${BASE_URL}/readyz`, { headers: { 'Host': 'assessment.local' } });
  if (res.status !== 200) {
    throw new Error(`Target not ready (status=${res.status}). Aborting.`);
  }
}
