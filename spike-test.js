import http from 'k6/http';
import { check, sleep } from 'k6';

export const options = {
  stages: [
    { duration: '1m', target: 5000 },  
    { duration: '1m', target: 10000 }, // Meet the 10,000 VU requirement
    { duration: '2m', target: 10000 }, 
    { duration: '30s', target: 0 },
  ],
  thresholds: {
    'http_req_failed': ['rate<0.01'],    // Pass Criteria: < 1%
    'http_req_duration': ['p(95)<2000'], // Pass Criteria: < 2s
  },
};

export default function () {
  const params = { 
    headers: { 'Connection': 'close' }, // Prevent socket lingering
    timeout: '30s' 
  };
  
  const res = http.get('http://172.18.0.2:8000/api/data', params);
  
  check(res, { 'status is 200': (r) => r.status === 200 });

  // 15s sleep ensures 10k users stay "active" while allowing the OS to recycle ports
  sleep(15 + Math.random() * 5); 
}
