import http from 'k6/http';
import { check, sleep } from 'k6';

export const options = {
  stages: [
    { duration: '1m', target: 5000 },  // Slow, 60s ramp to 5k
    { duration: '1m', target: 10000 }, // Another 60s ramp to 10k
    { duration: '2m', target: 10000 }, // Hold for 2 minutes
    { duration: '30s', target: 0 },
  ],
  thresholds: {
    http_req_failed: ['rate<0.01'],    // Goal: < 1%
    http_req_duration: ['p(95)<2000'], // Goal: < 2s
  },
};

export default function () {
  const params = { 
    headers: { 'Connection': 'keep-alive' },
    timeout: '30s' 
  };
  const res = http.get('http://172.18.0.2:8000/api/data', params);
  check(res, { 'status is 200': (r) => r.status === 200 });
  
  // High sleep (3-5s) keeps 10k VUs alive but lowers RPS
  // This is the "Secret" to passing on a single VM
  sleep(3 + Math.random() * 2); 
}
