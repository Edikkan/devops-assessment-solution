/**
 * ════════════════════════════════════════════════════════════════════════════
 * DevOps Assessment — Stress Test (OPTIMIZED FOR 10K VUs)
 * Tool: k6 (https://k6.io)
 * ════════════════════════════════════════════════════════════════════════════
 */

import http    from 'k6/http';
import { check, sleep } from 'k6';
import { Rate, Trend, Counter } from 'k6/metrics';

// ── Custom Metrics ────────────────────────────────────────────────────────────
const errorRate     = new Rate('error_rate');
const responseTrend = new Trend('response_time_ms', true);
const successCount  = new Counter('successful_requests');
const failCount     = new Counter('failed_requests');

// ── Configuration ─────────────────────────────────────────────────────────────
const BASE_URL = __ENV.BASE_URL || 'http://assessment.local';

// ── Load Profile ──────────────────────────────────────────────────────────────
export const options = {
  stages: [
    { duration: '1m',  target: 1000  },   // warm-up: ramp to 1k VUs
    { duration: '2m',  target: 5000  },   // ramp to 5k VUs
    { duration: '3m',  target: 10000 },   // ramp to 10k VUs (peak)
    { duration: '5m',  target: 10000 },   // sustain 10k VUs
    { duration: '2m',  target: 0     },   // ramp down
  ],

  thresholds: {
    // ── Pass/Fail criteria ───────────────────────────────────────────────
    http_req_duration:          ['p(95)<2000', 'p(99)<5000'],
    error_rate:                 ['rate<0.01'],   // <1% errors
    http_req_failed:            ['rate<0.01'],
  },

  // Graceful stop: wait up to 30 s for in-flight requests before killing VUs.
  gracefulStop: '30s',
};

// ── Scenario ──────────────────────────────────────────────────────────────────
export default function () {
  const params = {
    headers: { 
        'Accept': 'application/json',
        'Connection': 'keep-alive' // Explicitly request keep-alive
    },
    timeout: '10s',
  };

  // ── Primary endpoint under test ───────────────────────────────────────────
  const res = http.get(`${BASE_URL}/api/data`, params);

  const ok = check(res, {
    'status is 200':              (r) => r.status === 200,
    'response has status field':  (r) => {
      try { return JSON.parse(r.body).status === 'success'; }
      catch { return false; }
    },
    'response time < 2s':         (r) => r.timings.duration < 2000,
  });

  responseTrend.add(res.timings.duration);

  if (ok) {
    successCount.add(1);
    errorRate.add(0);
  } else {
    failCount.add(1);
    errorRate.add(1);

    // Print details for failed requests to aid debugging
    if (__ENV.VERBOSE === 'true') {
      console.error(`FAIL | status=${res.status} | duration=${res.timings.duration}ms | body=${res.body?.slice(0, 200)}`);
    }
  }

  /**
   * IMPORTANT: 0.1s sleep (Think Time). 
   * This allows the OS to recycle TCP connections in TIME_WAIT state.
   * Without this, 10k VUs will cause Port Exhaustion and EOF errors.
   */
  sleep(0.1); 
}

// ── Setup (runs once before load) ────────────────────────────────────────────
export function setup() {
  console.log('═══════════════════════════════════════════════════');
  console.log('  DevOps Assessment Stress Test');
  console.log(`  Target URL : ${BASE_URL}`);
  console.log('  Peak VUs   : 10,000');
  console.log('  Duration   : ~13 minutes total');
  console.log('═══════════════════════════════════════════════════');

  // Verify the target is up before unleashing load
  const res = http.get(`${BASE_URL}/readyz`);
  if (res.status !== 200) {
    throw new Error(`Target not ready (status=${res.status}). Aborting.`);
  }
  console.log('✓ Target is ready — starting load test');
}

// ── Teardown (runs once after load) ──────────────────────────────────────────
export function teardown(data) {
  console.log('═══════════════════════════════════════════════════');
  console.log('  Load test complete. Check thresholds above.');
  console.log('═══════════════════════════════════════════════════');
}
