import http from 'k6/http';
import { check } from 'k6';

export const options = {
  vus: 1,
  iterations: 20,
};

export default function () {
  const res = http.get('http://ats-lb:8080/');
  check(res, {
    'status is 200': (r) => r.status === 200,
    'contains appId': (r) => r.body.includes('appId'),
  });
}

