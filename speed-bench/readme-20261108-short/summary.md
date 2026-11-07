floor 39.4 C, target 41.4 C, runs 3

| Metric | ds4 | sf | vs ds4 |
|---|---:|---:|---:|
| ttft 512 | 15.0 | 12.0 | +25.1% |
| first token 512 ms | 2739.6 | 115.7 | +2268.6% |
| append +512 at 512 | 20.4 | 6.9 | +196.0% |
| first token 1024 ms | 36.6 | 120.3 | -69.6% |
| append +512 at 1024 | 20.0 | 6.7 | +197.4% |
| first token 1536 ms | 37.4 | 106.6 | -64.9% |

Spread (max-min)/median per column, worst metric:
- ds4: 5.7% (first token 1024 ms)
- sf: 16.6% (first token 1024 ms)
