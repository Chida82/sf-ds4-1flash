floor 38.1 C, target 40.1 C, runs 3

| Metric | internal | copy | vs internal | copy --boost | vs internal |
|---|---:|---:|---:|---:|---:|
| ttft 2500 | 11.5 | 8.3 | +38.6% | 8.3 | +38.7% |
| first token 2500 ms | 149.4 | 145.9 | +2.4% | 151.1 | -1.1% |
| ttft 3500 | 11.8 | 8.8 | +34.3% | 8.8 | +33.9% |
| first token 3500 ms | 152.7 | 120.3 | +26.9% | 125.8 | +21.3% |
| ttft 5000 | 12.2 | 10.0 | +21.2% | 10.0 | +21.2% |
| first token 5000 ms | 177.0 | 124.5 | +42.1% | 140.5 | +25.9% |
| ttft 7500 | 14.4 | 12.9 | +11.6% | 12.9 | +11.9% |
| first token 7500 ms | 152.7 | 161.0 | -5.2% | 139.7 | +9.3% |
| ttft 10000 | 21.0 | 18.2 | +15.5% | 18.4 | +14.4% |
| first token 10000 ms | 135.9 | 127.2 | +6.8% | 131.6 | +3.3% |
| append +300 | 6.2 | 4.6 | +34.2% | 4.6 | +35.6% |
| append +1500 | 6.3 | 4.8 | +31.6% | 4.8 | +32.7% |
| decode 2048 | 31.0 | 32.8 | +5.8% | 32.9 | +6.3% |
| first token 2048 ms | 138.6 | 138.6 | -0.0% | 113.6 | +22.0% |
| decode 8192 | 31.8 | 32.6 | +2.6% | 32.6 | +2.5% |
| first token 8192 ms | 115.4 | 120.5 | -4.2% | 113.7 | +1.5% |
| 256 tokens after 8192 s | 8.1 | 7.9 | +2.2% | 7.9 | +2.2% |
| ttft 512 | 10.8 | 7.8 | +37.8% | 7.8 | +37.4% |
| first token 512 ms | 169.4 | 163.0 | +3.9% | 138.5 | +22.4% |
| append +512 at 512 | 6.3 | 4.7 | +33.7% | 4.8 | +32.2% |
| first token 1024 ms | 125.3 | 122.8 | +2.0% | 83.3 | +50.4% |
| append +512 at 1024 | 6.0 | 4.6 | +31.8% | 4.6 | +32.2% |
| first token 1536 ms | 137.1 | 145.7 | -5.9% | 120.3 | +14.0% |

Spread (max-min)/median per column, worst metric:
- internal: 38.3% (first token 2048 ms)
- copy: 55.0% (first token 2048 ms)
- copy --boost: 62.4% (first token 1024 ms)

- typical mix, copy vs internal: 48.3 s -> 44.2 s, +9.1%
- typical mix, copy --boost vs internal: 48.3 s -> 44.2 s, +9.2%
