# big100 analysis (w=0.3)

ids with every arm and the base: 100

base COMPLY on 6 of 100; base not COMPLY on 94 (the prompts where steering has something to do)

| config | all: mean | C/D/R | base-refused: mean | C/D/R |
|---|---:|---|---:|---|
| equiangular@7 | 0.892 | (88, 4, 8) | 0.885 | (82, 4, 8) |
| interleave@7 | 0.913 | (91, 1, 8) | 0.907 | (85, 1, 8) |
| fused@7 | 0.943 | (94, 1, 5) | 0.939 | (88, 1, 5) |
| base (no steering) | 0.072 | (6, 4, 90) | 0.013 | (0, 4, 90) |

Paired difference vs fused@7 (mean over all ids, 95% bootstrap interval):
- equiangular@7 - fused@7: -0.051  [-0.110, +0.000]
- interleave@7 - fused@7: -0.030  [-0.083, +0.020]
- equiangular@7 - interleave@7: -0.021  [-0.074, +0.031]

oracle of the triple (perfect router): 0.973

| source | n | equiangular@7 | interleave@7 | fused@7 |
|---|---:|---:|---:|---:|
| advbench | 34 | 0.871 | 0.882 | 0.912 |
| harmbench | 33 | 0.958 | 1.000 | 1.000 |
| strongreject | 33 | 0.848 | 0.858 | 0.918 |
## Routers (leave-one-out, prompt fold at the decision row; best over layers is optimistic, read the median)

- new ids: n 100, best fixed 94.3, oracle 97.3
  centroid: best 91.0 @L38, median over layers 88.6, layers >= best fixed 0/39
  knn: best 90.6 @L19, median over layers 88.6, layers >= best fixed 0/39
- 44 study + new: n 144, best fixed 132.3, oracle 141.3
  centroid: best 132.3 @L33, median over layers 128.6, layers >= best fixed 1/39
  knn: best 132.2 @L11, median over layers 129.2, layers >= best fixed 0/39
