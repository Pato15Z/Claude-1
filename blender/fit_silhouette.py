"""
fit_silhouette.py -- acha a POSE HERO: a orientacao 3D cuja projecao ortografica
reproduz a silhueta do vetor 2D de referencia.

    python3 fit_silhouette.py referencia.png [--out hero_pose.py] [--quick]

Requer: numpy, scipy, pillow.  Nao requer Blender.

Como funciona
-------------
Parametriza um dart de papel (nariz, popa do vinco, 2 pontas de asa, quilha) e
uma camera ortografica (3 angulos + escala + 2 translacoes). Rasteriza a uniao
das faces projetadas e maximiza o IoU contra a mascara da referencia via
evolucao diferencial + Nelder-Mead. Grava SHAPE, HERO_EULER_XYZ e REF_FRAMING
num hero_pose.py que paper_plane_3d.py le automaticamente.

Limites conhecidos
------------------
* Se a referencia estiver CROPADA, so a area visivel entra no IoU: o resto da
  forma fica determinado pelo modelo, nao pela imagem.
* Um glifo estilizado nao e, em geral, a projecao exata de um solido real.
  IoU ~0.95+ = casamento visualmente perfeito; ~0.85-0.95 = silhueta dominante
  bate e sobram detalhes (tipicamente a quilha).
"""
import sys, os, math, json
import numpy as np
from PIL import Image
from scipy.optimize import differential_evolution, minimize

def load_mask(path):
    im = Image.open(path).convert("RGBA")
    a = np.array(im)
    if (a[..., 3] < 250).any():           # tem alpha -> usa alpha
        return a[..., 3] > 128
    lum = a[..., :3].mean(2)              # senao: tinta escura sobre claro
    return lum < 128

def rot(yaw, pitch, roll):
    cy, sy = math.cos(yaw), math.sin(yaw)
    cp, sp = math.cos(pitch), math.sin(pitch)
    cr, sr = math.cos(roll), math.sin(roll)
    Rz = np.array([[cy, -sy, 0], [sy, cy, 0], [0, 0, 1]])
    Ry = np.array([[cp, 0, sp], [0, 1, 0], [-sp, 0, cp]])
    Rx = np.array([[1, 0, 0], [0, cr, -sr], [0, sr, cr]])
    return Rz @ Ry @ Rx

def dart(Lw, b, hw, Lk, hk):
    """Nariz na origem, +X para a popa, +Y estibordo, +Z cima."""
    V = np.array([[0, 0, 0], [1., 0, 0], [Lw, -b, -hw], [Lw, b, -hw], [Lk, 0, -hk]])
    F = [(0, 1, 2), (0, 1, 3), (0, 4, 1)]        # asa bb, asa eb, quilha
    return V, F

def main():
    ref_path = sys.argv[1]
    out = sys.argv[sys.argv.index("--out") + 1] if "--out" in sys.argv else \
          os.path.join(os.path.dirname(os.path.abspath(__file__)), "hero_pose.py")
    quick = "--quick" in sys.argv

    mask = load_mask(ref_path)
    H_PX, W_PX = mask.shape
    GW = 157 if not quick else 100
    GH = max(4, int(round(GW * H_PX / W_PX)))
    ref = np.array(Image.fromarray((mask * 255).astype(np.uint8))
                   .resize((GW, GH), Image.BILINEAR)) > 127
    gx = (np.arange(GW) + .5) * (W_PX / GW)
    gy = (np.arange(GH) + .5) * (H_PX / GH)
    GX, GYd = np.meshgrid(gx, gy)
    GYu = H_PX - GYd                                     # geometria em Y-para-cima

    def tri(p0, p1, p2):
        d = (p1[1]-p2[1])*(p0[0]-p2[0]) + (p2[0]-p1[0])*(p0[1]-p2[1])
        if abs(d) < 1e-9: return np.zeros_like(GX, bool)
        a  = ((p1[1]-p2[1])*(GX-p2[0]) + (p2[0]-p1[0])*(GYu-p2[1])) / d
        bb = ((p2[1]-p0[1])*(GX-p2[0]) + (p0[0]-p2[0])*(GYu-p2[1])) / d
        return (a >= 0) & (bb >= 0) & (1-a-bb >= 0)

    def render(p):
        yaw, pit, rol, ls, tx, ty, Lw, b, hw, Lk, hk = p
        P = (rot(yaw, pit, rol) @ dart(Lw, b, hw, Lk, hk)[0].T).T
        s = math.exp(ls)
        scr = np.stack([P[:, 0]*s + tx, P[:, 1]*s + ty], 1)
        m = np.zeros_like(GX, bool)
        for f in dart(Lw, b, hw, Lk, hk)[1]:
            m |= tri(scr[f[0]], scr[f[1]], scr[f[2]])
        return m

    def loss(p):
        m = render(p); u = (m | ref).sum()
        return 1.0 - ((m & ref).sum() / u if u else 0.0)

    D = max(W_PX, H_PX)
    bounds = [(-math.pi, math.pi), (-1.4, 1.4), (-math.pi, math.pi),
              (math.log(D*0.12), math.log(D*4.0)),
              (-D, 2*D), (-D, 2*D),
              (0.6, 1.15), (0.25, 1.10), (-0.35, 0.60), (0.5, 1.10), (0.05, 0.90)]
    r = differential_evolution(loss, bounds, seed=3, tol=1e-8, workers=-1, polish=True,
                               maxiter=200 if quick else 600, popsize=20 if quick else 40)
    r2 = minimize(loss, r.x, method="Nelder-Mead",
                  options=dict(maxiter=20000, xatol=1e-8, fatol=1e-10))
    p = r2.x if r2.fun < r.fun else r.x
    iou = 1 - min(r.fun, r2.fun)
    yaw, pit, rol, ls, tx, ty, Lw, b, hw, Lk, hk = map(float, p)

    with open(out, "w") as f:
        f.write(f'''"""Gerado por fit_silhouette.py a partir de {os.path.basename(ref_path)}.
IoU da silhueta projetada vs referencia (area visivel): {iou:.4f}
Nao editar a mao -- rode fit_silhouette.py de novo."""
SHAPE = dict(Ls=1.0, Lw={Lw:.6f}, b={b:.6f}, hw={hw:.6f}, Lk={Lk:.6f}, hk={hk:.6f})
# rotation_euler XYZ do objeto na pose hero = (roll, pitch, yaw)
HERO_EULER_XYZ = ({rol:.6f}, {pit:.6f}, {yaw:.6f})
HERO_DEG = ({math.degrees(rol):.3f}, {math.degrees(pit):.3f}, {math.degrees(yaw):.3f})
# enquadramento que reproduz o crop da referencia
REF_FRAMING = dict(px_per_unit={math.exp(ls):.4f}, tx={tx:.4f}, ty={ty:.4f})
REF_RESOLUTION = ({W_PX}, {H_PX})
''')
    print(f"IoU = {iou:.4f}   -> {out}")

    m = render(p)
    o = np.full((GH, GW, 3), 255, np.uint8)
    o[ref] = (198, 206, 255); o[m] = (35, 35, 35); o[m & ref] = (200, 45, 45)
    prev = os.path.splitext(out)[0] + "_preview.png"
    Image.fromarray(o).resize((GW*4, GH*4), Image.NEAREST).save(prev)
    print("preview:", prev, "(vermelho=acerto, preto=sobra, azul=falta)")

if __name__ == "__main__":
    main()
