"""
paper_plane_3d.py  --  Aviao de papel 3D (flat shading) com "trava 2D" exata.

PREMISSA CENTRAL
----------------
Sob projecao ORTOGRAFICA ao longo de -Z, o ponto (x, y, z) vira (x, y).
O deslocamento em Z e invisivel. Logo, existe uma orientacao unica do modelo
em que a silhueta projetada reproduz EXATAMENTE o vetor 2D de referencia.
Basta que (a) a camera seja ortografica, (b) o modelo esteja na pose "hero",
(c) o shading seja emissivo/flat (qualquer gradiente de luz quebra a igualdade).

USO
---
    blender --background --python paper_plane_3d.py
    blender --background --python paper_plane_3d.py -- --render-hero out.png
    # ou cole no Scripting workspace do Blender e rode (F5 / Alt+P)
"""

import bpy, bmesh, math, os, sys, json
from mathutils import Vector, Matrix, Euler

# ----------------------------------------------------------------------------
# 1. PARAMETROS
# ----------------------------------------------------------------------------

# --- modo de construcao -----------------------------------------------------
#   "exact" : geometria derivada do POLIGONO 2D. Atribui apenas Z; como a camera
#             e ortografica, a projecao no frame de lock e o proprio vetor.
#             IoU = 1.000 por construcao. Custo: as faces nao sao congruentes a
#             um papel dobrado de verdade (esticam), o que ninguem mede.
#   "dart"  : aviao de papel rigido, ajustado numericamente a referencia.
#             Fisicamente consistente; teto de IoU ~0.90 porque o glifo nao e a
#             projecao exata de nenhum solido rigido.
MODE = "exact"

# --- poligono da silhueta (px da referencia, Y para CIMA) -------------------
# Tracado da propria referencia; A' e B' estendem a cauda para fora do canvas
# (invisivel no lock, necessario para o aviao nao ter corte ao girar).
SIL_PX = [
    (   -0.190,   879.721),   # 0  H  nariz            <- vinco
    ( 1900.000,  1745.297),   # 1  A' cauda sup (extensao da aresta H-A, fora do canvas)
    ( 1900.000,  -185.594),   # 2  B' cauda inf (extensao da aresta C-B, fora do canvas)
    ( 1064.015,   283.699),   # 3  C
    (  629.946,    87.378),   # 4  D  ponta inferior
    (  921.271,   600.472),   # 5  E
    ( 1056.567,   817.841),   # 6  F  apice do entalhe  <- vinco
    (  536.745,   582.929),   # 7  G
]
CREASE = (0, 6)          # indices de SIL_PX que definem a linha de vinco (H-F)
DEPTH  = 0.55            # profundidade da dobra, relativa a distancia ao vinco
PX_PER_UNIT = 2185.0176  # px da referencia por unidade de mundo

# --- forma do dart (unidades locais: +X = re, +Y = estibordo, +Z = cima) -----
SHAPE = dict(
    Ls = 1.000,   # comprimento da quilha/vinco (nariz -> popa)
    Lw = 1.000,   # posicao longitudinal das pontas de asa
    b  = 0.620,   # meia-envergadura
    hw = 0.160,   # quanto a ponta de asa cai abaixo do vinco (anedro)
    Lk = 0.950,   # posicao longitudinal da quina inferior da quilha
    hk = 0.420,   # profundidade da quilha
)

# --- pose "hero": rotacao que reproduz o vetor 2D sob camera ortografica ----
# (sobrescrita por hero_pose.py, gerado pelo fit contra a referencia)
HERO_EULER_XYZ = (math.radians(-104.0), math.radians(0.0), math.radians(-152.0))

# --- cores flat: edite os HEX (sRGB). A conversao p/ linear e automatica. ---
HEX_TOP    = "#F4F7FB"   # dorso da asa  -> face clara
HEX_BOTTOM = "#A9B8CE"   # ventre da asa -> face media
HEX_KEEL   = "#7486A3"   # quilha        -> face escura
HEX_LOCK   = "#FFFFFF"   # cor do vetor: para onde TUDO converge no frame de lock
BG_HEX     = None        # None = fundo transparente (alpha)

# --- animacao ---------------------------------------------------------------
# O LOCK 2D E O ULTIMO FRAME. A animacao termina exatamente em cima do vetor,
# em pose E em enquadramento, para o morph 3D->2D nao ter salto.
F_START, F_END = 1, 120
HOLD = 10                  # frames finais congelados na pose de lock (F_END-HOLD .. F_END)
POSE_A = (math.radians(-58), math.radians( 30), math.radians(-46))  # pose 3D inicial
CAM_WIDE = 1.90            # 1.0 = camera fixa no enquadramento do vetor (sem dolly)
                           # >1 = comeca mais aberto e fecha ate o enquadramento do vetor

RES = (1568, 1594)
ORTHO_SCALE_PAD = 1.18

# Enquadramento que reproduz o CROP exato da referencia (vindo do ajuste).
# px_per_unit / offset em pixels da imagem de referencia, com Y para cima.
REF_FRAMING = None   # ex.: dict(px_per_unit=2181.4, tx=0.80, ty=880.14)
REF_RESOLUTION = None

_here = os.path.dirname(os.path.abspath(__file__ if "__file__" in dir() else "."))
_hero = os.path.join(_here, "hero_pose.py")
if os.path.exists(_hero):
    ns = {}
    exec(open(_hero).read(), ns)
    SHAPE.update(ns.get("SHAPE", {}))
    HERO_EULER_XYZ = ns.get("HERO_EULER_XYZ", HERO_EULER_XYZ)
    REF_FRAMING = ns.get("REF_FRAMING", REF_FRAMING)
    REF_RESOLUTION = ns.get("REF_RESOLUTION", REF_RESOLUTION)

# ----------------------------------------------------------------------------
# 2. CENA LIMPA
# ----------------------------------------------------------------------------

def wipe():
    bpy.ops.wm.read_factory_settings(use_empty=True)
    for coll in (bpy.data.meshes, bpy.data.materials, bpy.data.objects,
                 bpy.data.cameras, bpy.data.actions):
        for d in list(coll):
            coll.remove(d)

# ----------------------------------------------------------------------------
# 3. MALHA: dart de papel real (3 faces planas, sem espessura)
# ----------------------------------------------------------------------------

PIVOT_SHIFT = Vector((0.0, 0.0, 0.0))


def build_from_silhouette():
    """Constroi a malha a partir do poligono 2D. Todo vertice mantem (x, y) e
    recebe um Z proporcional a distancia ate a linha de vinco -> dobra em V.
    Como Z e invisivel sob projecao ortografica, a silhueta projetada e
    identica ao vetor, qualquer que seja DEPTH."""
    global PIVOT_SHIFT, REF_FRAMING, HERO_EULER_XYZ
    HERO_EULER_XYZ = (0.0, 0.0, 0.0)       # a malha ja nasce na pose de lock

    P = [Vector(p) for p in SIL_PX]
    a, b = (P[CREASE[0]], P[CREASE[1]])
    d = (b - a); L = d.length; d = d / L

    me = bpy.data.meshes.new("PaperPlane")
    bm = bmesh.new()
    vs = [bm.verts.new((p.x, p.y, 0.0)) for p in P]
    bm.verts.ensure_lookup_table()
    bm.faces.new(vs)                        # n-gon plano: triangulacao segura
    bmesh.ops.triangulate(bm, faces=bm.faces[:])

    for v in bm.verts:                      # so agora sai do plano
        off = Vector((v.co.x, v.co.y)) - a
        dist = abs(d.x * off.y - d.y * off.x)      # distancia ao vinco
        v.co.z = -DEPTH * dist

    for v in bm.verts:                      # px da referencia -> unidades de mundo
        v.co /= PX_PER_UNIT
    bm.normal_update()
    for f in bm.faces:
        f.material_index = 0
        if f.normal.z < 0.0: f.normal_flip()
    bm.normal_update()
    bm.to_mesh(me); bm.free()
    me.shade_flat()

    PIVOT_SHIFT = Vector((0.0, 0.0, 0.0))   # sem recentragem: px = mundo*PPU
    REF_FRAMING = dict(px_per_unit=PX_PER_UNIT, tx=0.0, ty=0.0)
    ob = bpy.data.objects.new("PaperPlane", me)
    bpy.context.collection.objects.link(ob)
    # pivo de rotacao no meio do vinco, para o giro nao arrastar a composicao
    ob.data.transform(Matrix.Translation(-((a + b) * 0.5).to_3d() / PX_PER_UNIT))
    ob.location = ((a + b) * 0.5).to_3d() / PX_PER_UNIT
    return ob


def build_plane(shape):
    Ls, Lw, b, hw, Lk, hk = (shape[k] for k in ("Ls","Lw","b","hw","Lk","hk"))
    N  = Vector(( 0.0,  0.0,  0.0))   # nariz
    S  = Vector(( Ls,   0.0,  0.0))   # popa do vinco
    WL = Vector(( Lw,  -b,   -hw))    # ponta de asa bombordo
    WR = Vector(( Lw,   b,   -hw))    # ponta de asa estibordo
    K  = Vector(( Lk,   0.0, -hk))    # quina inferior da quilha

    me = bpy.data.meshes.new("PaperPlane")
    bm = bmesh.new()
    vN, vS, vWL, vWR, vK = (bm.verts.new(p) for p in (N, S, WL, WR, K))
    bm.verts.ensure_lookup_table()
    f_wl = bm.faces.new((vN, vS, vWL))    # asa bombordo
    f_wr = bm.faces.new((vN, vWR, vS))    # asa estibordo
    f_k  = bm.faces.new((vN, vK, vS))     # quilha (fin central)
    for f in (f_wl, f_wr): f.material_index = 0
    f_k.material_index = 1
    bm.normal_update()

    # centraliza no centroide projetado para a rotacao nao arrastar a silhueta
    c = sum((v.co for v in bm.verts), Vector()) / len(bm.verts)
    for v in bm.verts: v.co -= c

    # assa a pose hero na malha => rotacao do objeto = identidade no frame hero
    R = Euler(HERO_EULER_XYZ, 'XYZ').to_matrix()
    global PIVOT_SHIFT
    PIVOT_SHIFT = R @ c          # de quanto a silhueta andou ao recentrar
    bm.transform(R.to_4x4())

    # Na pose hero a camera olha ao longo de -Z: toda face com normal.z < 0
    # estaria mostrando o VERSO. Vira essas faces para que o frame de lock saia
    # na cor "frente" (HEX_TOP), que e a do vetor 2D.
    bm.normal_update()
    for f in bm.faces:
        if f.normal.z < 0.0:
            f.normal_flip()
    bm.normal_update()

    bm.to_mesh(me); bm.free()
    me.shade_flat()
    ob = bpy.data.objects.new("PaperPlane", me)
    bpy.context.collection.objects.link(ob)
    return ob

# ----------------------------------------------------------------------------
# 4. MATERIAIS FLAT (emissao pura; frente/verso por Backfacing)
# ----------------------------------------------------------------------------

def srgb_to_linear(c):
    return c/12.92 if c <= 0.04045 else ((c + 0.055)/1.055) ** 2.4

def hexcol(h):
    h = h.lstrip("#")
    r, g, b = (int(h[i:i+2], 16)/255.0 for i in (0, 2, 4))
    return tuple(srgb_to_linear(v) for v in (r, g, b)) + (1.0,)

def flat_two_sided(name, front, back):
    """Tons chapados por ORIENTACAO da face (ColorRamp com interpolacao CONSTANT
    -> bandas duras, sem gradiente), cruzados com a cor de lock por um Value
    keyframado. No frame de lock o Value vale 1 e tudo vira a cor do vetor --
    e por isso que a silhueta chapada bate exatamente."""
    m = bpy.data.materials.new(name); m.use_nodes = True
    nt = m.node_tree; nt.nodes.clear()
    out = nt.nodes.new("ShaderNodeOutputMaterial")
    em  = nt.nodes.new("ShaderNodeEmission"); em.inputs["Strength"].default_value = 1.0

    geo = nt.nodes.new("ShaderNodeNewGeometry")
    sep = nt.nodes.new("ShaderNodeSeparateXYZ")
    nt.links.new(geo.outputs["Normal"], sep.inputs["Vector"])

    ramp = nt.nodes.new("ShaderNodeValToRGB")
    ramp.color_ramp.interpolation = 'CONSTANT'
    e = ramp.color_ramp.elements
    e[0].position, e[0].color = 0.00, back                 # face de perfil / virada
    e[1].position, e[1].color = 0.42, hexcol(HEX_KEEL)     # face intermediaria
    e.new(0.78).color = front                              # face de frente
    nt.links.new(sep.outputs["Z"], ramp.inputs["Fac"])

    lock = nt.nodes.new("ShaderNodeValue"); lock.label = "LockMix"; lock.name = "LockMix"
    lock.outputs[0].default_value = 0.0
    mix = nt.nodes.new("ShaderNodeMixRGB")
    mix.inputs[2].default_value = hexcol(HEX_LOCK)
    nt.links.new(ramp.outputs["Color"], mix.inputs[1])
    nt.links.new(lock.outputs[0], mix.inputs[0])
    nt.links.new(mix.outputs["Color"], em.inputs["Color"])
    nt.links.new(em.outputs["Emission"], out.inputs["Surface"])
    m.use_backface_culling = False
    return m

def apply_materials(ob):
    """No lock TODAS as faces aparecem de frente, entao o frame sai chapado na
    cor de frente -- que e o que o vetor exige (ele e monocromatico). O relevo
    3D vem do VERSO, que so aparece quando o aviao gira."""
    top, bot, keel = hexcol(HEX_TOP), hexcol(HEX_BOTTOM), hexcol(HEX_KEEL)
    ob.data.materials.append(flat_two_sided("Wing", top, bot))
    if MODE != "exact":
        ob.data.materials.append(flat_two_sided("Keel", keel, keel))

# ----------------------------------------------------------------------------
# 5. CAMERA ORTOGRAFICA (olhando -Z) + render flat
# ----------------------------------------------------------------------------

def setup_camera(ob, match_ref=False):
    cam_d = bpy.data.cameras.new("Cam"); cam_d.type = 'ORTHO'
    cam = bpy.data.objects.new("Cam", cam_d)
    bpy.context.collection.objects.link(cam)
    cam.location = (0.0, 0.0, 10.0)
    cam.rotation_euler = (0.0, 0.0, 0.0)          # olha ao longo de -Z
    bpy.context.scene.camera = cam

    if match_ref and REF_FRAMING:
        # reproduz pixel a pixel o enquadramento (cropado) da referencia
        s  = REF_FRAMING["px_per_unit"]
        tx = REF_FRAMING["tx"]; ty = REF_FRAMING["ty"]
        # ortho_scale mede o MAIOR lado do frame, nao a largura.
        cam_d.ortho_scale = max(RES) / s
        cam.location.x = (RES[0] * 0.5 - tx) / s - PIVOT_SHIFT.x
        cam.location.y = (RES[1] * 0.5 - ty) / s - PIVOT_SHIFT.y
        return cam
    # senao: enquadra o aviao inteiro na pose hero (rotacao identidade)
    xs = [v.co.x for v in ob.data.vertices]; ys = [v.co.y for v in ob.data.vertices]
    # ortho_scale mede o maior lado do frame; converte o span do eixo dominante
    span_x = (max(xs)-min(xs)) * (max(RES) / RES[0])
    span_y = (max(ys)-min(ys)) * (max(RES) / RES[1])
    cam_d.ortho_scale = max(span_x, span_y) * ORTHO_SCALE_PAD
    cam.location.x = (max(xs)+min(xs)) / 2.0
    cam.location.y = (max(ys)+min(ys)) / 2.0
    return cam

def setup_render(engine=None):
    sc = bpy.context.scene
    avail = {i.identifier for i in
             bpy.types.RenderSettings.bl_rna.properties['engine'].enum_items}
    if engine and engine in avail:
        sc.render.engine = engine
    else:
        sc.render.engine = ('BLENDER_EEVEE_NEXT' if 'BLENDER_EEVEE_NEXT' in avail
                            else 'BLENDER_EEVEE')
    if sc.render.engine == 'CYCLES':
        sc.cycles.samples = 16
        sc.cycles.max_bounces = 0          # emissao pura: zero bounce = cor exata
        sc.cycles.use_denoising = False
    sc.render.resolution_x, sc.render.resolution_y = RES
    sc.render.resolution_percentage = int(os.environ.get("PP_RES_PCT", "100"))
    sc.render.film_transparent = BG_HEX is None
    if BG_HEX is not None:
        w = bpy.data.worlds.new("W"); w.use_nodes = True
        w.node_tree.nodes["Background"].inputs[0].default_value = hexcol(BG_HEX)
        sc.world = w
    sc.render.filter_size = 1.5
    sc.view_settings.view_transform = 'Standard'   # sem Filmic/AgX: cor flat = cor exata
    sc.frame_start, sc.frame_end = F_START, F_END
    sc.frame_step = int(os.environ.get("PP_FRAME_STEP", "1"))
    for attr, val in (("use_gtao", False), ("use_bloom", False), ("use_ssr", False)):
        if hasattr(sc.eevee, attr): setattr(sc.eevee, attr, val)
    if hasattr(sc.eevee, "use_raytracing"): sc.eevee.use_raytracing = False
    if hasattr(sc.eevee, "taa_render_samples"): sc.eevee.taa_render_samples = 32

# ----------------------------------------------------------------------------
# 6. ANIMACAO: offset 3D -> pose hero (identidade) -> offset 3D
# ----------------------------------------------------------------------------

def animate(ob, cam):
    """Rotacao: POSE_A -> POSE_MID -> identidade (lock) no ULTIMO frame.
    Camera: enquadramento aberto -> enquadramento exato do vetor, no mesmo frame."""
    f_lock_in = max(F_START + 1, F_END - HOLD)

    ob.rotation_mode = 'XYZ'
    for f, r in ((F_START, POSE_A), (f_lock_in, (0., 0., 0.)), (F_END, (0., 0., 0.))):
        ob.rotation_euler = r
        ob.keyframe_insert("rotation_euler", frame=f)

    # camera: so anima se sabemos qual e o enquadramento do vetor
    if REF_FRAMING:
        s0  = REF_FRAMING["px_per_unit"]
        oc  = max(RES) / s0
        cx  = (RES[0] * 0.5 - REF_FRAMING["tx"]) / s0 - PIVOT_SHIFT.x
        cy  = (RES[1] * 0.5 - REF_FRAMING["ty"]) / s0 - PIVOT_SHIFT.y
        for f, k in ((F_START, CAM_WIDE), (f_lock_in, 1.0), (F_END, 1.0)):
            cam.data.ortho_scale = oc * k
            cam.location.x, cam.location.y = cx, cy
            cam.data.keyframe_insert("ortho_scale", frame=f)
            cam.keyframe_insert("location", frame=f)

    # contraste 3D -> 0 exatamente no lock (sem isso o ultimo frame nao e chapado)
    for mat in ob.data.materials:
        nd = mat.node_tree.nodes.get("LockMix")
        if not nd: continue
        for f, v in ((F_START, 0.0),
                     (int(F_START + (f_lock_in - F_START) * 0.72), 0.0),
                     (f_lock_in, 1.0), (F_END, 1.0)):
            nd.outputs[0].default_value = v
            nd.outputs[0].keyframe_insert("default_value", frame=f)

    for holder in (ob, cam, cam.data):
        ad = holder.animation_data
        if not ad or not ad.action: continue
        for fc in ad.action.fcurves:
            for kp in fc.keyframe_points:
                kp.interpolation = 'BEZIER'
                kp.easing = 'EASE_OUT'     # desacelera entrando no lock
                if int(kp.co.x) in (f_lock_in, F_END):
                    kp.handle_left_type = 'AUTO_CLAMPED'
                    kp.handle_right_type = 'AUTO_CLAMPED'
    return ob


# ----------------------------------------------------------------------------
# 6b. TRANSFORMADA DE ENTREGA (para quem NAO renderiza no canvas do vetor)
# ----------------------------------------------------------------------------

def delivery_transform(cam):
    """Como a projecao e ortografica e a rotacao no lock e a identidade, a relacao
    entre o render e o vetor e uma SIMILARIDADE: escala uniforme + translacao.
    Devolve os numeros para casar a camada do render em cima do vetor no AE."""
    if not REF_FRAMING:
        return None
    W, H = RES
    ppu = max(W, H) / cam.data.ortho_scale          # px por unidade no render
    s   = REF_FRAMING["px_per_unit"]                # px por unidade no vetor
    k   = s / ppu                                   # escala uniforme render -> vetor
    ox    = (cam.location.x + PIVOT_SHIFT.x - W / (2*ppu)) * s + REF_FRAMING["tx"]
    oy_up = (cam.location.y + PIVOT_SHIFT.y - H / (2*ppu)) * s + REF_FRAMING["ty"]
    Wr, Hr = REF_RESOLUTION or (W, H)
    return dict(
        escala_percent = round(k * 100, 4),
        offset_x_px    = round(ox, 3),
        offset_y_px    = round(Hr - (oy_up + H * k), 3),
        position_x_px  = round(ox + W * k / 2.0, 3),
        position_y_px  = round(Hr - (oy_up + H * k / 2.0), 3),
        canvas_do_vetor  = [Wr, Hr],
        canvas_do_render = [W, H],
    )


def main():
    wipe()
    ob = build_from_silhouette() if MODE == "exact" else build_plane(SHAPE)
    apply_materials(ob)
    argv0 = sys.argv[sys.argv.index("--")+1:] if "--" in sys.argv else sys.argv[1:]
    eng = argv0[argv0.index("--engine")+1] if "--engine" in argv0 else None
    cam = setup_camera(ob, match_ref=("--match-ref" in argv0))
    setup_render(eng)
    animate(ob, cam)

    argv = argv0
    out_dir = _here
    if "--out" in argv: out_dir = argv[argv.index("--out")+1]
    os.makedirs(out_dir, exist_ok=True)

    if REF_FRAMING:
        t = delivery_transform(cam)
        with open(os.path.join(out_dir, "transformada_para_o_vetor.json"), "w") as fh:
            json.dump(t, fh, indent=2, ensure_ascii=False)
        print("[ok] transformada render->vetor:", json.dumps(t, ensure_ascii=False))

    blend = os.path.join(out_dir, "paper_plane_3d.blend")
    bpy.ops.wm.save_as_mainfile(filepath=blend)
    print("[ok] blend salvo:", blend)

    if "--render-anim" in argv:
        sc = bpy.context.scene
        sc.render.image_settings.file_format = 'PNG'
        sc.render.image_settings.color_mode = 'RGBA'
        sc.render.filepath = os.path.join(out_dir, "anim", "f_")
        bpy.ops.render.render(animation=True)
        print("[ok] sequencia renderizada em", os.path.join(out_dir, "anim"))

    if "--render-hero" in argv or "--render-proof" in argv:
        sc = bpy.context.scene
        lock = F_END
        for f in ([lock] if "--render-proof" not in argv
                  else [F_START, 35, 70, 95, lock]):
            sc.frame_set(f)
            sc.render.filepath = os.path.join(out_dir, f"proof_{f:03d}.png")
            bpy.ops.render.render(write_still=True)
            print("[ok] render frame", f)

main()
