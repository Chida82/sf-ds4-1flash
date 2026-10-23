# Fase 0 — residual refusal along q0 at gen_ vs rows_

Residual ids: nonthink ['0', '18', '468'], think ['7', '544', '1123', '1126']. Layers [15, 20, 25, 30, 35]. z = robust (median/MAD) vs other refused. Gate: |z|>2.0 on >=2 layers at gen (and normal at rows).

- rows_: refused 1000, complied 136, benign 200
- gen_: refused 1000, complied 136, benign 200

## median q0.y per group (refused / complied / benign)

| pos | L15 | L20 | L25 | L30 | L35 |
|---|---:|---:|---:|---:|---:|
| rows refused | -9 | -10 | -75 | -22 | -49 |
| rows complied | -4 | -4 | -17 | -8 | -14 |
| rows benign | -2 | -3 | -1 | -2 | -4 |
| gen refused | -9 | -7 | -56 | -16 | -45 |
| gen complied | -2 | -3 | -7 | -4 | -11 |
| gen benign | -1 | -1 | +0 | -1 | -3 |

## q0 z-score per residual id (rows then gen)

| pos | group | id | L15 | L20 | L25 | L30 | L35 | #|z|>2 |
|---|---|---|---:|---:|---:|---:|---:|---:|
| rows | nonthink | 0 | +0.7 | +1.1 | +1.3 | -0.9 | -0.4 | 0 |
| rows | nonthink | 18 | +0.2 | -0.3 | +0.3 | +0.3 | +0.0 | 0 |
| rows | nonthink | 468 | -0.6 | -0.1 | -0.1 | +0.6 | +0.3 | 0 |
| rows | think | 7 | +0.0 | -0.2 | -0.9 | -1.0 | -1.3 | 0 |
| rows | think | 544 | -1.8 | -1.2 | -1.7 | +0.0 | +0.1 | 0 |
| rows | think | 1123 | -0.2 | +0.2 | +0.4 | +1.7 | +1.1 | 0 |
| rows | think | 1126 | -0.4 | +0.9 | +0.5 | +2.0 | +1.1 | 1 |
| gen | nonthink | 0 | +1.2 | +0.9 | +1.4 | -0.9 | -0.5 | 0 |
| gen | nonthink | 18 | -1.2 | -1.4 | -0.8 | -1.4 | -0.5 | 0 |
| gen | nonthink | 468 | -0.5 | -1.3 | +0.1 | -0.6 | +0.1 | 0 |
| gen | think | 7 | +0.8 | -1.0 | -0.9 | -2.1 | -3.0 | 2 |
| gen | think | 544 | -2.0 | -0.3 | -1.3 | -1.4 | -0.7 | 1 |
| gen | think | 1123 | -0.7 | -0.8 | -0.4 | +0.9 | +1.8 | 0 |
| gen | think | 1126 | -0.2 | -2.1 | -3.6 | -0.1 | -0.3 | 2 |

## Verdict

- ids anomalous at gen (|z|>2 on >=2 layers): [('think', '7'), ('think', '1126')]
- of those, normal at rows (signal appears in generation): [('think', '7'), ('think', '1126')]

**BUILD**: q0 reads the residual refusal at the generated token for 2/7 residual ids -> the controller has a per-token signal. Proceed to Fase 1.
