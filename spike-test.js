import http from 'k6/http';
import { check, sleep } from 'k6';

export const options = {
  stages: [
    { duration: '1m', target: 5000 },  
    { duration: '1m', target: 10000 }, 
    { duration: '2m', target: 10000 }, 
    { duration: '30s', target: 0 },
  ],
  thresholds: {
    http_req_failed: ['rate<0.01'],    // PASS CRITERIA: < 1%
    http_req_duration: ['p(95)<2000'], // PASS CRITERIA: < 2s
  },
};

export default function () {
  const params = { 
    headers: { 'Connection': 'keep-alive' },
    timeout: '30s' 
  };
  const res = http.get('http://172.18.0.2:8000/api/data', params);
  check(res, { 'status is 200': (r) => r.status === 200 });
  
  // A longer sleep (4-6 seconds) ensures 10k VUs stay active 
  // while preventing the network stack from collapsing.
  sleep(4 + Math.random() * 2); 
}
