import http from 'k6/http';
import { check, sleep } from 'k6';

export const options = {
  stages: [
    { duration: '15s', target: 2000 },  // Gradual warmup
    { duration: '30s', target: 10000 }, // Slower ramp to stabilize sockets
    { duration: '1m',  target: 10000 }, // Peak load
    { duration: '20s', target: 0 },
  ],
  thresholds: {
    http_req_failed: ['rate<0.10'], // 10% tolerance for single-node 10k test
  },
};

export default function () {
  const params = { 
    headers: { 'Connection': 'keep-alive' },
    timeout: '10s' // Essential for avoiding the "Request Timeout" error
  };
  const res = http.get('http://172.18.0.2:8000/api/data', params);
  check(res, { 'status is 200': (r) => r.status === 200 });
  sleep(1); // Think time helps stabilize RPS while keeping high VU count
}
