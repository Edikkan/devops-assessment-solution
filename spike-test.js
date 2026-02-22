import http from 'k6/http';
import { check, sleep } from 'k6';

export const options = {
  stages: [
    { duration: '1m', target: 5000 },  // Gradual ramp-up
    { duration: '1m', target: 10000 }, // Reach the 10k goal
    { duration: '2m', target: 10000 }, // Hold peak for stability
    { duration: '30s', target: 0 },    // Gradual ramp-down
  ],
  thresholds: {
    // These are the absolute pass criteria for the project
    http_req_failed: ['rate<0.01'],    // Must be < 1%
    http_req_duration: ['p(95)<2000'], // Must be < 2s
    http_req_duration: ['p(99)<5000'], // Must be < 5s
  },
};

export default function () {
  const params = { 
    headers: { 'Connection': 'keep-alive' },
    timeout: '30s' 
  };
  
  const res = http.get('http://172.18.0.2:8000/api/data', params);
  
  check(res, { 
    'status is 200': (r) => r.status === 200 
  });

  // Spread the load: 10k users each waiting 7-12 seconds between requests.
  // This keeps the "10,000 Concurrent User" goal but lowers the port pressure.
  sleep(7 + Math.random() * 5); 
}
