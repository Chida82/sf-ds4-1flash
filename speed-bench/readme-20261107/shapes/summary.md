floor 38.6 C, target 40.6 C, runs 3

| Metric | internal | copy | vs internal | copy --boost | vs internal |
|---|---:|---:|---:|---:|---:|
| ttft 2500 | 13.3 | 10.1 | +31.0% | 9.9 | +34.1% |
| first token 2500 ms | 202.5 | 191.6 | +5.7% | 176.4 | +14.9% |
| ttft 3500 | 12.8 | 10.5 | +21.6% | 9.0 | +41.7% |
| first token 3500 ms | 164.5 | 174.4 | -5.7% | 145.9 | +12.8% |
| ttft 5000 | 13.0 | 12.7 | +2.7% | 10.3 | +27.1% |
| first token 5000 ms | 200.3 | 185.0 | +8.3% | 164.3 | +21.9% |
| ttft 7500 | 14.9 | 15.4 | -3.2% | 13.1 | +13.7% |
| first token 7500 ms | 170.8 | 174.5 | -2.1% | 150.2 | +13.7% |
| ttft 10000 | 21.8 | 19.8 | +10.1% | 18.5 | +17.7% |
| first token 10000 ms | 153.7 | 165.9 | -7.4% | 130.0 | +18.3% |
| append +300 | 9.6 | 8.8 | +9.4% | 8.8 | +9.2% |
| append +1500 | 7.6 | 5.5 | +37.7% | 5.5 | +38.2% |
| decode 2048 | 31.2 | 32.5 | +4.4% | 32.7 | +4.9% |
| first token 2048 ms | 163.8 | 137.4 | +19.2% | 157.9 | +3.7% |
| decode 8192 | 31.8 | 32.5 | +2.0% | 32.3 | +1.5% |
| first token 8192 ms | 155.5 | 124.0 | +25.3% | 172.3 | -9.8% |
| 256 tokens after 8192 s | 8.1 | 8.0 | +1.6% | 8.1 | +0.4% |

Spread (max-min)/median per column, worst metric:
- internal: 72.3% (first token 8192 ms)
- copy: 40.1% (first token 7500 ms)
- copy --boost: 49.9% (first token 5000 ms)

- typical mix, copy vs internal: 49.1 s -> 46.5 s, +5.5%
- typical mix, copy --boost vs internal: 49.1 s -> 44.9 s, +9.3%
