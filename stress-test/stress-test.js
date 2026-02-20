import http from 'k6/http';
import { check, sleep } from 'k6';

export const options = {
  stages: [
    { duration: '2m', target: 5000 },
    { duration: '3m', target: 10000 },
    { duration: '5m', target: 10000 },
    { duration: '2m', target: 0 },
  ],
  thresholds: {
    http_req_duration: ['p(95)<2000'],
    http_req_failed: ['rate<0.01'], 
  },
  discardResponseBodies: true,
};

export default function () {
  // Directly hit the host port
  const res = http.get('http://127.0.0.1:8000/api/data', {
    headers: { 'Connection': 'keep-alive' },
    timeout: '10s'
  });

  check(res, { 'status is 200': (r) => r.status === 200 });
  sleep(1.0); 
}
