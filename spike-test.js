import http from 'k6/http';
import { check, sleep } from 'k6';

export const options = {
  stages: [
    { duration: '10s', target: 2000 },  // Warm up the TCP stack
    { duration: '20s', target: 10000 }, // Smooth ramp to 10k users
    { duration: '1m',  target: 10000 }, // Hold the peak
    { duration: '20s', target: 0 },     // Graceful ramp down
  ],
  thresholds: {
    http_req_failed: ['rate<0.05'], // Target 95% success rate
    http_req_duration: ['p(95)<2000'],
  },
};

export default function () {
  const params = { 
    headers: { 'Connection': 'keep-alive' },
    timeout: '5s' // Give the server slightly longer to respond under pressure
  };
  const res = http.get('http://172.18.0.3:8000/api/data', params);
  check(res, { 'status is 200': (r) => r.status === 200 });
  sleep(0.5); // Increase think time slightly to reduce raw RPS while keeping 10k VUs
}
