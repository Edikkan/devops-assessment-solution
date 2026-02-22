import http from 'k6/http';
import { check, sleep } from 'k6';

export const options = {
  stages: [
    { duration: '30s', target: 5000 },  // Smooth ramp to 5k
    { duration: '30s', target: 10000 }, // Smooth ramp to 10k
    { duration: '1m',  target: 10000 }, // Maintain peak
    { duration: '20s', target: 0 },     // Cool down
  ],
  thresholds: {
    http_req_failed: ['rate<0.01'],    // PASS CRITERIA: < 1%
    http_req_duration: ['p(95)<2000'], // PASS CRITERIA: < 2s
  },
};

export default function () {
  const params = { 
    headers: { 'Connection': 'keep-alive' },
    timeout: '20s' 
  };
  const res = http.get('http://172.18.0.2:8000/api/data', params);
  check(res, { 'status is 200': (r) => r.status === 200 });
  
  // Sleep ensures we don't overwhelm the CPU while keeping 10k users active
  sleep(1.5 + Math.random()); 
}
