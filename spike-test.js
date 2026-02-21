import http from 'k6/http';
import { check, sleep } from 'k6';

export const options = {
  stages: [
    { duration: '30s', target: 5000 },  // Initial climb
    { duration: '30s', target: 10000 }, // Slower climb to 10k
    { duration: '1m',  target: 10000 }, // Hold peak
    { duration: '30s', target: 0 },     // Graceful exit
  ],
  thresholds: {
    http_req_failed: ['rate<0.01'],   // The Pass Criteria: < 1%
    http_req_duration: ['p(95)<2000'], // The Pass Criteria: < 2s
  },
};

export default function () {
  const params = { 
    headers: { 'Connection': 'keep-alive' },
    timeout: '20s' // Essential for high-concurrency scheduling delays
  };
  const res = http.get('http://172.18.0.2:8000/api/data', params);
  check(res, { 'status is 200': (r) => r.status === 200 });
  
  // Adding a jittered sleep of 1-2 seconds
  // This keeps 10k users "connected" but spreads the RPS
  sleep(1 + Math.random());
}
