import http from 'k6/http';
import { check, sleep } from 'k6';

const POD_IP = '172.18.0.3'; // ENSURE THIS IS STILL YOUR CURRENT POD IP
const BASE_URL = `http://${POD_IP}:8000`;

export const options = {
  stages: [
    { duration: '1m', target: 1000 },
    { duration: '2m', target: 3000 }, // Peak at 3k VUs
    { duration: '5m', target: 3000 },
    { duration: '1m', target: 0 },
  ],
  thresholds: {
    http_req_duration: ['p(95)<500'], // Tighten performance
    http_req_failed: ['rate<0.01'],   // 1% failure limit
  },
  discardResponseBodies: true,
};

export default function () {
  const params = {
    headers: { 'Connection': 'keep-alive' },
    timeout: '5s'
  };

  const res = http.get(`${BASE_URL}/api/data`, params);
  check(res, { 'status is 200': (r) => r.status === 200 });

  // Randomized sleep between 0.5s and 1.5s to prevent "Thundering Herd"
  sleep(Math.random() * 1 + 0.5); 
}
