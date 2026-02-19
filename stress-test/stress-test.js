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
      // MANDATORY: Manually set the host header so the Ingress knows where to route
      'Host': 'assessment.local' 
    },
    timeout: '15s',
  };

  // ── Primary endpoint under test ───────────────────────────────────────────
  const res = http.get(`${BASE_URL}/api/data`, params);

  const ok = check(res, {
    'status is 200': (r) => r.status === 200,
    'body is valid': (r) => r.body && r.body.includes('success'),
  });

  if (!ok) {
    errorRate.add(1);
  }

  /**
   * 0.2s Sleep: Balanced for a single-node VM.
   * This prevents the "Flood" effect that causes EOF errors on Traefik.
   */
  sleep(0.2);
}

// ── Setup ────────────────────────────────────────────────────────────────────
export function setup() {
  console.log('═══════════════════════════════════════════════════');
  console.log('  DNS-Bypass Stress Test Starting');
  console.log(`  Targeting  : ${BASE_URL} (Host: assessment.local)`);
  console.log('═══════════════════════════════════════════════════');

  const res = http.get(`${BASE_URL}/readyz`, { headers: { 'Host': 'assessment.local' } });
  if (res.status !== 200) {
    throw new Error(`Target not ready (status=${res.status}). Aborting.`);
  }
}
