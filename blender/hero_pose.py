"""Gerado pelo ajuste numerico contra a referencia 2D (IoU ~0.90 na area visivel).
Nao editar a mao: rode fit_silhouette.py de novo se trocar a referencia."""
import math
SHAPE = dict(Ls=1.0, Lw=1.079818, b=0.535964, hw=-0.020723, Lk=1.081257, hk=0.531185)
# rotation_euler XYZ do objeto na pose hero = (roll, pitch, yaw) do ajuste
HERO_EULER_XYZ = (0.108741, -0.215946, -0.045330)
HERO_DEG = (6.230, -12.373, -2.597)

REF_FRAMING = dict(px_per_unit=2185.0176, tx=0.7999, ty=880.1368)
REF_RESOLUTION = (1568, 1594)
