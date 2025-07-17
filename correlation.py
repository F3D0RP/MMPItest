import numpy as np

filename = 'testres2.txt'

t_scores2 = []

with open(filename, 'r', encoding='utf-8') as file:
    for line in file:
        parts = line.strip().split()
        if parts:
            t_scores2.append(float(parts[-1]))

t_scores1 = []

with open('testres1', 'r', encoding='utf-8') as file:
    for line in file:
        parts = line.strip().split()
        if parts:
            t_scores1.append(float(parts[-1]))

correlation = np.corrcoef(t_scores1, t_scores2)[0, 1]
print(f"Коэффициент корреляции: {correlation:.3f}")
