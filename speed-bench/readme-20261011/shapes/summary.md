floor 41.2 C, target 43.2 C, runs 3

| Metric | internal | copy | vs internal | copy --boost | vs internal |
|---|---:|---:|---:|---:|---:|
| ttft 2500 | 26.5 | 23.9 | +11.0% | 23.7 | +11.6% |
| first token 2500 ms | 59.5 | 59.4 | +0.2% | 57.6 | +3.3% |
| ttft 3500 | 11.9 | 10.5 | +12.9% | 10.5 | +13.8% |
| first token 3500 ms | 238.4 | 217.5 | +9.6% | 208.4 | +14.4% |
| ttft 5000 | 42.0 | 40.5 | +3.7% | 40.4 | +4.1% |
| first token 5000 ms | 39.8 | 40.3 | -1.2% | 39.9 | -0.3% |
| ttft 7500 | 15.7 | 14.8 | +6.3% | 14.8 | +6.5% |
| first token 7500 ms | 269.6 | 217.9 | +23.7% | 203.6 | +32.4% |
| ttft 10000 | 23.5 | 19.7 | +19.2% | 20.1 | +16.9% |
| first token 10000 ms | 117.6 | 118.6 | -0.8% | 127.3 | -7.6% |
| append +300 | 10.1 | 10.1 | -0.3% | 9.9 | +1.3% |
| append +1500 | 7.3 | 5.7 | +27.8% | 5.4 | +34.4% |
| decode 2048 | 29.8 | 29.4 | -1.2% | 29.4 | -1.2% |
| first token 2048 ms | 123.1 | 202.0 | -39.1% | 203.7 | -39.6% |
| decode 8192 | 29.4 | 29.4 | -0.0% | 29.7 | +0.7% |
| first token 8192 ms | 136.8 | 128.4 | +6.6% | 114.8 | +19.2% |
| 256 tokens after 8192 s | 8.8 | 8.8 | +0.0% | 8.7 | +0.9% |

Spread (max-min)/median per column, worst metric:
- internal: 76.0% (first token 2048 ms)
- copy: 33.8% (first token 8192 ms)
- copy --boost: 50.6% (first token 10000 ms)

- typical mix, copy vs internal: 59.9 s -> 58.1 s, +3.1%
- typical mix, copy --boost vs internal: 59.9 s -> 58.0 s, +3.3%
