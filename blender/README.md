# Avião de papel: 3D flat que termina exatamente em cima do vetor 2D

A animação gira um avião de papel 3D de faces planas e **fecha no último frame
sobre a silhueta do vetor de referência** — mesma pose, mesmo enquadramento,
mesma cor chapada. É o handoff que um morph 3D→2D exige.

---

## 1. O princípio

Sob projeção **ortográfica** ao longo de `-Z`, o ponto `(x, y, z)` vira `(x, y)`:
a profundidade é descartada. Duas consequências, e o projeto inteiro sai delas:

* **Existe uma orientação** do modelo cuja projeção coincide com o contorno 2D.
  Achá-la é otimização em 3 ângulos, não modelagem no viewport (`MODE="dart"`).
* **Melhor ainda:** dado o polígono 2D, dá para atribuir um `Z` arbitrário a cada
  vértice. A projeção continua sendo o polígono original, *exatamente*, qualquer
  que seja o `Z`. Logo, a geometria 3D pode ser **derivada do vetor** em vez de
  ajustada a ele (`MODE="exact"`).

## 2. Os dois modos, e por que o padrão é `exact`

| | `exact` (padrão) | `dart` |
|---|---|---|
| Geometria | derivada do polígono 2D; só o `Z` é inventado | avião rígido parametrizado, ajustado por IoU |
| IoU do frame de lock | **0.9980** (o resto é antialiasing) | **0.9007** |
| Papel fisicamente consistente | não (as faces esticam) | sim |
| Serve para morph | sim | não — 0.90 dá pop visível |

O teto de 0.90 do modo `dart` **não é falta de graus de liberdade**: testei um
modelo bem mais rico (asas como quad, quilha com âncora livre, 15 parâmetros
contra 11) e deu 0.9004 — estatisticamente idêntico. A conclusão é outra: o
glifo não é a projeção ortográfica de *nenhum* avião rígido. É arte estilizada.
Enquanto o modelo for um sólido real, 0.90 é o limite; a única forma de chegar
a 1.0 é construir a partir do polígono e aceitar que as faces não são
congruentes a um papel dobrado de verdade — coisa que ninguém mede olhando.

## 3. As condições que não podem ser quebradas

1. **Câmera ortográfica.** Em perspectiva a projeção depende de `Z` e a silhueta
   escorrega. Se precisar de perspectiva nos frames 3D, use lente longa
   (250mm → 2000mm), que converge assintoticamente para ortográfica.
2. **`ortho_scale` mede o MAIOR lado do frame, não a largura.** Tratar como
   largura em 1568×1594 introduz 1,7% de erro de escala: invisível a olho,
   fatal para morph. (Era um bug real aqui — custou 0,011 de IoU.)
3. **Shading emissivo, `max_bounces = 0`.** Difusa, specular ou AO criam
   gradiente dentro da face e ela deixa de ser preenchimento chapado.
4. **View transform `Standard`.** Filmic/AgX remapeiam cor: `#FFFFFF` sai outro.
5. **Rotação identidade no último frame.** Garantido por construção: em `exact`
   a malha já nasce na pose de lock.

## 4. Cor: por que o lock é obrigatoriamente monocromático

O vetor de referência é uma silhueta chapada única, sem linha de vinco interna.
Como no frame de lock todas as faces aparecem, elas **têm que sair na mesma
cor** — qualquer separação tonal ali quebraria a igualdade com o vetor.

A saída não é abrir mão do 3D, é animar o contraste. O material mistura
(a) tons chapados por orientação da face — `ColorRamp` com interpolação
`CONSTANT`, bandas duras, sem gradiente — com (b) a cor de lock `HEX_LOCK`,
através de um `Value` chamado `LockMix` que vai a 1.0 exatamente no lock.
Medido no render: frame 70 tem três tons; **frame 120 tem 148.193 px de
`(255,255,255)` puro** e 101 px de antialiasing. A cor converge junto com a
forma, que é o comportamento certo para um morph.

## 5. Arquivos e uso

```
paper_plane_3d.py    malha, materiais, câmera, animação, render
hero_pose.py         saída do ajuste (só usado em MODE="dart")   [gerado]
fit_silhouette.py    acha a pose hero para MODE="dart"
```

```bash
blender -b -P paper_plane_3d.py -- --render-anim              # sequência PNG RGBA
blender -b -P paper_plane_3d.py -- --render-hero --match-ref  # só o lock
blender -b -P paper_plane_3d.py -- --render-proof             # 5 frames de prova
```

Sem Blender instalado: `pip install "bpy==4.2.23"` (Python 3.11) e
`python3 paper_plane_3d.py --engine CYCLES --render-proof`.

| Onde | O quê |
|---|---|
| `SIL_PX` | o polígono do vetor (px, Y para cima). Trocou de arte? troque aqui |
| `CREASE` | os dois índices de `SIL_PX` que definem a linha de vinco |
| `DEPTH` | profundidade da dobra. **Não afeta o lock** — só como o 3D lê girando |
| `HEX_LOCK` | a cor do vetor; é para onde tudo converge |
| `POSE_A` | pose 3D inicial |
| `HOLD` | frames finais congelados no lock |
| `CAM_WIDE` | `1.0` = câmera fixa no enquadramento do vetor; `>1` = abre e fecha |

## 6. Handoff para o After Effects

Duas rotas, e a escolha é sobre quem carrega a matemática:

**Rota A — renderizar no canvas do vetor** (`REF_FRAMING` ativo, o padrão).
O render sai em 1568×1594 e o último frame cai pixel sobre pixel no
`Vector.png`. Zero transformada no AE. Custo: como a arte sangra para fora da
tela, o enquadramento é um close extremo, e sem um `CAM_WIDE > 1` o avião sai
do quadro nos frames girados.

**Rota B — renderizar folgado e casar depois.** Como a projeção é ortográfica e
a rotação final é a identidade, a relação entre render e vetor é exatamente uma
**similaridade**: escala uniforme + translação, sem distorção. O script grava
`transformada_para_o_vetor.json` com `escala_percent` e `position_x/y_px`
prontos para colar em Scale e Position da camada.

Regra: se ninguém vai mexer no enquadramento depois, use A. Se o avião precisa
de liberdade de movimento antes do lock, use B — é uma transformada só, fixa.
