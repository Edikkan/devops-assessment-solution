import http from 'k6/http';
import { check, sleep } from 'k6';

export const options = {
  stages: [
    { duration: '20s', target: 2000 },
    { duration: '40s', target: 10000 }, 
    { duration: '1m',  target: 10000 }, 
    { duration: '20s', target: 0 },
  ],
  thresholds: {
    http_req_failed: ['rate<0.10'], // 10% tolerance for single-node extreme load
  },
};

export default function () {
  const params = { 
    headers: { 'Connection': 'keep-alive' },
    timeout: '15s' 
  };
  const res = http.get('http://172.18.0.2:8000/api/data', params);
  check(res, { 'status is 200': (r) => r.status === 200 });
  sleep(Math.random() * 2 + 1);
}
