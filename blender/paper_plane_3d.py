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

import bpy, bmesh, math, os, sys
from mathutils import Vector, Matrix, Euler

# ----------------------------------------------------------------------------
# 1. PARAMETROS
# ----------------------------------------------------------------------------

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
BG_HEX     = None        # None = fundo transparente (alpha)

# --- animacao ---------------------------------------------------------------
F_START, F_END = 1, 120
F_HERO_IN, F_HERO_OUT = 50, 66        # trecho em que a silhueta fica travada em 2D
POSE_A = (math.radians(-62), math.radians( 34), math.radians(-40))  # offset 3D antes
POSE_B = (math.radians( 58), math.radians(-29), math.radians( 47))  # offset 3D depois

RES = (1568, 1594)
ORTHO_SCALE_PAD = 1.18

# Enquadramento que reproduz o CROP exato da referencia (vindo do ajuste).
# px_per_unit / offset em pixels da imagem de referencia, com Y para cima.
REF_FRAMING = None   # ex.: dict(px_per_unit=2181.4, tx=0.80, ty=880.14)

_here = os.path.dirname(os.path.abspath(__file__ if "__file__" in dir() else "."))
_hero = os.path.join(_here, "hero_pose.py")
if os.path.exists(_hero):
    ns = {}
    exec(open(_hero).read(), ns)
    SHAPE.update(ns.get("SHAPE", {}))
    HERO_EULER_XYZ = ns.get("HERO_EULER_XYZ", HERO_EULER_XYZ)
    REF_FRAMING = ns.get("REF_FRAMING", REF_FRAMING)

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
    m = bpy.data.materials.new(name); m.use_nodes = True
    nt = m.node_tree; nt.nodes.clear()
    out = nt.nodes.new("ShaderNodeOutputMaterial")
    em  = nt.nodes.new("ShaderNodeEmission"); em.inputs["Strength"].default_value = 1.0
    mix = nt.nodes.new("ShaderNodeMixRGB")
    geo = nt.nodes.new("ShaderNodeNewGeometry")
    mix.inputs[1].default_value = front
    mix.inputs[2].default_value = back
    nt.links.new(geo.outputs["Backfacing"], mix.inputs[0])
    nt.links.new(mix.outputs["Color"], em.inputs["Color"])
    nt.links.new(em.outputs["Emission"], out.inputs["Surface"])
    m.use_backface_culling = False
    return m

def apply_materials(ob):
    top, bot, keel = hexcol(HEX_TOP), hexcol(HEX_BOTTOM), hexcol(HEX_KEEL)
    ob.data.materials.append(flat_two_sided("Wing", top, bot))
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
        cam_d.ortho_scale = RES[0] / s
        cam.location.x = (RES[0] * 0.5 - tx) / s - PIVOT_SHIFT.x
        cam.location.y = (RES[1] * 0.5 - ty) / s - PIVOT_SHIFT.y
        return cam
    # senao: enquadra o aviao inteiro na pose hero (rotacao identidade)
    xs = [v.co.x for v in ob.data.vertices]; ys = [v.co.y for v in ob.data.vertices]
    span = max(max(xs)-min(xs), max(ys)-min(ys))
    cam_d.ortho_scale = span * ORTHO_SCALE_PAD
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

def animate(ob):
    keys = [
        (F_START,     POSE_A),
        (F_HERO_IN,   (0.0, 0.0, 0.0)),   # trava 2D exata
        (F_HERO_OUT,  (0.0, 0.0, 0.0)),   # segura o quadro parado
        (F_END,       POSE_B),
    ]
    ob.rotation_mode = 'XYZ'
    for f, rot in keys:
        ob.rotation_euler = rot
        ob.keyframe_insert("rotation_euler", frame=f)
    for fc in ob.animation_data.action.fcurves:
        for kp in fc.keyframe_points:
            kp.interpolation = 'BEZIER'
            kp.easing = 'EASE_IN_OUT'
        # entrada/saida do hold: handles planos -> a pose 2D "assenta"
        for kp in fc.keyframe_points:
            if int(kp.co.x) in (F_HERO_IN, F_HERO_OUT):
                kp.handle_left_type = 'AUTO_CLAMPED'
                kp.handle_right_type = 'AUTO_CLAMPED'
    return ob

# ----------------------------------------------------------------------------
# 7. MAIN
# ----------------------------------------------------------------------------

def main():
    wipe()
    ob = build_plane(SHAPE)
    apply_materials(ob)
    argv0 = sys.argv[sys.argv.index("--")+1:] if "--" in sys.argv else sys.argv[1:]
    eng = argv0[argv0.index("--engine")+1] if "--engine" in argv0 else None
    setup_camera(ob, match_ref=("--match-ref" in argv0))
    setup_render(eng)
    animate(ob)

    argv = argv0
    out_dir = _here
    if "--out" in argv: out_dir = argv[argv.index("--out")+1]
    os.makedirs(out_dir, exist_ok=True)

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
        for f in ([F_HERO_IN] if "--render-proof" not in argv
                  else [F_START, 30, F_HERO_IN, 90, F_END]):
            sc.frame_set(f)
            sc.render.filepath = os.path.join(out_dir, f"proof_{f:03d}.png")
            bpy.ops.render.render(write_still=True)
            print("[ok] render frame", f)

main()
