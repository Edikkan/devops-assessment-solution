import http from 'k6/http';
import { check, sleep } from 'k6';

// TARGET THE POD IP (Get this from the deployment step below)
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

  // 2.0s sleep = 5,000 Requests Per Second at 10k VUs.
  // This ensures the Docker bridge doesn't drop connections.
  sleep(2.0); 
}
