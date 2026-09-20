# Avião de papel: 3D flat com "trava 2D" exata

Transforma o vetor 2D de referência num avião de papel 3D de verdade (faces
planas, dobras reais, cores flat) e anima a rotação de forma que, **num frame
específico, a silhueta projetada volta a ser exatamente o vetor 2D original**.

---

## 1. O princípio que faz isso funcionar

Sob projeção **ortográfica** ao longo de `-Z`, o ponto `(x, y, z)` vira `(x, y)`.
A coordenada `Z` é literalmente invisível. Consequência direta:

> Existe uma orientação `R` do modelo em que a projeção da malha 3D coincide com
> o contorno 2D. Achar essa orientação é um problema de otimização em 3 ângulos
> (+ escala + translação), não um problema de modelagem.

Isso separa o trabalho em duas metades independentes:

| Metade | Ferramenta | Critério de sucesso |
|---|---|---|
| Achar a pose hero | `fit_silhouette.py` (numpy/scipy, sem Blender) | IoU entre silhueta projetada e referência |
| Construir/animar/renderizar | `paper_plane_3d.py` (Blender) | a pose hero é a rotação identidade |

A pose hero é **assada na malha**: no frame do lock, `rotation_euler == (0,0,0)`.
Não há deriva numérica possível — a exatidão é estrutural, não ajustada a olho.

---

## 2. As quatro condições. Quebrou uma, o frame 2D deixa de ser exato

1. **Câmera ortográfica.** Em perspectiva a projeção depende de `Z`, então a
   silhueta muda com a profundidade. `cam.data.type = 'ORTHO'`.
   (Se você *precisa* de perspectiva nos frames 3D, a saída é lente longa —
   250mm → 2000mm — que converge assintoticamente para ortográfica.)
2. **Shading emissivo/flat.** Qualquer difusa, specular, AO ou sombra cria
   gradiente dentro da face, e a face deixa de ser um preenchimento chapado.
   Aqui: `Emission` puro, `max_bounces = 0`.
3. **View transform `Standard`.** Filmic/AgX remapeiam a cor: `#F4F7FB` sai como
   outra coisa. `scene.view_settings.view_transform = 'Standard'`.
4. **Rotação identidade no frame hero.** Garantido por construção (ver acima).

---

## 3. Arquivos

```
fit_silhouette.py    acha a pose hero a partir de uma imagem de referência
hero_pose.py         saída do fit: SHAPE, HERO_EULER_XYZ, REF_FRAMING  (gerado)
paper_plane_3d.py    constrói a malha, materiais, câmera, animação e renderiza
```

## 4. Uso

```bash
# 1) (opcional) reajustar contra a SUA referência — de preferência não cropada
python3 fit_silhouette.py referencia.png          # grava hero_pose.py + preview

# 2) gerar o .blend
blender --background --python paper_plane_3d.py

# 3) provas de render
blender -b -P paper_plane_3d.py -- --render-proof            # 5 frames
blender -b -P paper_plane_3d.py -- --render-hero --match-ref # só o lock, no crop da ref
blender -b -P paper_plane_3d.py -- --render-anim             # sequência PNG RGBA
```

Sem Blender instalado, o mesmo script roda com o Blender como módulo Python:

```bash
pip install "bpy==4.2.23"        # precisa de Python 3.11
python3 paper_plane_3d.py --engine CYCLES --render-proof
```

`--match-ref` usa `REF_FRAMING` para reproduzir o **crop** exato da referência —
é assim que se mede a qualidade do lock. Sem ele, a câmera enquadra o avião
inteiro (o que você quer para a animação de verdade).

## 5. O que você mexe

| Onde | O quê |
|---|---|
| `HEX_TOP / HEX_BOTTOM / HEX_KEEL` | as três cores flat (hex sRGB; conversão p/ linear é automática) |
| `POSE_A / POSE_B` | quanto o avião gira antes e depois do lock |
| `F_HERO_IN / F_HERO_OUT` | início e fim do *hold* na pose 2D |
| `SHAPE` | proporções do dart — **mexer aqui invalida o fit**, refaça o ajuste |

O *hold* entre `F_HERO_IN` e `F_HERO_OUT` não é decorativo: sem alguns frames
parados, o olho não registra que a forma "virou o logo". 8–16 frames a 24fps.

---

## 6. Limitação do ajuste atual

A referência fornecida está **cropada** — a cauda sai do quadro à direita.
O fit só pode medir a área visível, então:

* IoU medido do render contra a referência: **0.889** (medido, não estimado).
* O que casa: nariz, ambas as bordas de ataque, a massa dominante do corpo.
* O que não casa: a posição da quilha — o modelo a coloca no entalhe, a
  referência a coloca mais abaixo e à esquerda (~5% da área).

Com o SVG/PNG **inteiro** da referência, `fit_silhouette.py` converge bem mais
alto. É a primeira coisa a fazer se quiser o lock perfeito.

---

## 7. Alternativa no After Effects

Dá para fazer, com uma diferença estrutural: **no AE você não modela, você
articula planos**.

Caminho viável (sem plugin pago):

1. No Illustrator, quebre o vetor nas faces que o avião tem (asa bombordo, asa
   estibordo, quilha) — cada face em uma camada, **cada uma já na cor flat final**.
2. Importe como composição com camadas, ligue `3D Layer` em todas.
3. Ancore cada face no vinco (`Anchor Point` sobre a linha de dobra) e faça o
   parent das asas numa `Null 3D` que representa o vinco.
4. Câmera: AE **não tem câmera ortográfica**. Use `Zoom` muito alto (10000+) com
   a câmera muito distante — a perspectiva vira desprezível na prática.
5. A pose 2D é a pose em que todos os `Orientation` das faces voltam a zero.
   Anime só a Null pai: `Y Rotation` / `X Rotation` saindo de zero e voltando.

O que você **ganha**: iteração instantânea, integração com o resto do motion.
O que você **perde**: o vinco é uma dobradiça de camadas planas, então em
ângulos extremos aparecem intersecções e z-fighting nas bordas compartilhadas;
e a face não tem verso próprio (precisa duplicar a camada e usar `Back Face` no
Cinema 4D renderer, ou duas camadas espelhadas).

**Regra de decisão:** se o avião gira pouco (até ~45° fora do plano) e a
animação é curta, AE é mais rápido e o resultado é indistinguível. Se ele
capota, dá voltas, ou você precisa de várias silhuetas-lock diferentes,
Blender paga o custo de setup na primeira hora.
