import http from 'k6/http';
import { check, sleep } from 'k6';

// TARGET THE POD IP DIRECTLY
const POD_IP = '172.18.0.4'; 
const BASE_URL = `http://${POD_IP}:8000`;

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
  const params = {
    headers: { 'Connection': 'keep-alive' },
    timeout: '10s'
  };

  const res = http.get(`${BASE_URL}/api/data`, params);

  check(res, { 'status is 200': (r) => r.status === 200 });
  
  // 1.0s sleep = 10,000 RPS at peak. 
  // Perfect for stability and the 1,000 req/s goal.
  sleep(1.0); 
}
