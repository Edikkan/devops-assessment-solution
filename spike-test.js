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
    http_req_failed: ['rate<0.01'],
    http_req_duration: ['p(95)<2000'],
  },
};

export default function () {
  const params = { 
    headers: { 'Connection': 'close' },
    timeout: '30s' 
  };
  
  // Hit the VM port 8000 which routes to the 3-node cluster
  const res = http.get('http://localhost:8000/api/data', params);
  
  check(res, { 'status is 200': (r) => r.status === 200 });

  sleep(10 + Math.random() * 5); 
}
