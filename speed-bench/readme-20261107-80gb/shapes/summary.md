floor 38.5 C, target 40.5 C, runs 3

| Metric | internal | copy | vs internal | copy --boost | vs internal |
|---|---:|---:|---:|---:|---:|
| ttft 2500 | 11.5 | 8.6 | +34.8% | 8.5 | +34.9% |
| first token 2500 ms | 206.4 | 213.2 | -3.2% | 220.0 | -6.2% |
| ttft 3500 | 11.9 | 8.9 | +33.2% | 8.9 | +33.2% |
| first token 3500 ms | 212.2 | 215.7 | -1.6% | 220.8 | -3.9% |
| ttft 5000 | 12.2 | 10.1 | +20.8% | 10.1 | +20.7% |
| first token 5000 ms | 240.5 | 215.6 | +11.5% | 212.2 | +13.3% |
| ttft 7500 | 14.4 | 13.1 | +10.5% | 13.0 | +11.2% |
| first token 7500 ms | 228.1 | 203.8 | +11.9% | 196.9 | +15.8% |
| ttft 10000 | 21.2 | 18.5 | +14.9% | 18.4 | +15.2% |
| first token 10000 ms | 216.8 | 172.8 | +25.5% | 171.3 | +26.5% |
| append +300 | 9.7 | 8.9 | +9.7% | 8.9 | +9.7% |
| append +1500 | 7.8 | 5.7 | +37.1% | 5.6 | +37.7% |
| decode 2048 | 30.9 | 32.3 | +4.6% | 32.4 | +4.7% |
| first token 2048 ms | 211.7 | 215.8 | -1.9% | 206.3 | +2.6% |
| decode 8192 | 31.7 | 32.3 | +1.9% | 32.1 | +1.3% |
| first token 8192 ms | 206.1 | 201.2 | +2.5% | 164.6 | +25.3% |
| 256 tokens after 8192 s | 8.3 | 8.1 | +1.7% | 8.1 | +1.8% |

Spread (max-min)/median per column, worst metric:
- internal: 32.0% (first token 10000 ms)
- copy: 35.4% (first token 8192 ms)
- copy --boost: 40.4% (first token 8192 ms)

- typical mix, copy vs internal: 48.4 s -> 44.8 s, +8.0%
- typical mix, copy --boost vs internal: 48.4 s -> 44.9 s, +7.9%
