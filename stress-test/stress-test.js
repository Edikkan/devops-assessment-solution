import http from 'k6/http';
import { check, sleep } from 'k6';
import { Rate } from 'k6/metrics';

const errorRate = new Rate('error_rate');
const BASE_URL = __ENV.BASE_URL || 'http://assessment.local';

export const options = {
  stages: [
    { duration: '2m', target: 5000 },
    { duration: '3m', target: 10000 },
    { duration: '5m', target: 10000 },
    { duration: '2m', target: 0 },
  ],
  thresholds: {
    http_req_duration: ['p(95)<2000', 'p(99)<5000'],
    http_req_failed: ['rate<0.01'],
  },
};

export default function () {
  const params = {
    headers: { 
      'Accept': 'application/json',
      'Connection': 'keep-alive' 
    },
    timeout: '15s', // Increased for p99 safety
  };

  const res = http.get(`${BASE_URL}/api/data`, params);

  const ok = check(res, {
    'status is 200': (r) => r.status === 200,
  });

  if (!ok) {
    errorRate.add(1);
  }

  // CRITICAL: 0.2s sleep to balance CPU load on a single VM
  sleep(0.2);
}
