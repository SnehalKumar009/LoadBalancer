import http from 'k6/http';
import { check, sleep } from 'k6';
import { Counter } from 'k6/metrics';

const app1Hits = new Counter('app1_hits');
const app2Hits = new Counter('app2_hits');
const app3Hits = new Counter('app3_hits');
const app4Hits = new Counter('app4_hits');

export const options = {
  stages: [
    { duration: '30s', target: 20 },
    { duration: '1m', target: 80 },
    { duration: '30s', target: 0 },
  ],
  thresholds: {
    http_req_failed: ['rate<0.02'],
    http_req_duration: ['p(95)<600'],
  },
};

export default function () {
  const res = http.get('http://ats-lb:8080/');
  check(res, {
    'status is 200': (r) => r.status === 200,
  });

  if (res.body.includes('app1')) app1Hits.add(1);
  if (res.body.includes('app2')) app2Hits.add(1);
  if (res.body.includes('app3')) app3Hits.add(1);
  if (res.body.includes('app4')) app4Hits.add(1);

  sleep(0.1);
}

