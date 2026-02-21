import http from 'k6/http';
import { check, sleep } from 'k6';

export const options = {
  scenarios: {
    constant_request_rate: {
      executor: 'constant-arrival-rate',
      rate: 1500, 
      timeUnit: '1s',
      duration: '3m',
      preAllocatedVUs: 2000,
      maxVUs: 10000,
    },
  },
  thresholds: {
    http_req_failed: ['rate<0.05'], // 5% failure tolerance for 10k spike
    http_req_duration: ['p(95)<2000'],
  },
};

export default function () {
  const params = { headers: { 'Connection': 'keep-alive' } };
  // setup.sh will replace this IP automatically
  const res = http.get('http://172.18.0.4:8000/api/data', params);
  check(res, { 'status is 200': (r) => r.status === 200 });
}

