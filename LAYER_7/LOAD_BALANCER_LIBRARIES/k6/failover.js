import http from 'k6/http';
import { check, sleep } from 'k6';

export const options = {
  vus: 40,
  duration: '60s',
  thresholds: {
    http_req_failed: ['rate<0.05'],
    http_req_duration: ['p(95)<800'],
  },
};

export default function () {
  const res = http.get('http://lb:8080/');
  check(res, {
    'status is 200': (r) => r.status === 200,
  });
  sleep(0.1);
}

