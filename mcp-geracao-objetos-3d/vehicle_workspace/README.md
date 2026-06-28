# Vehicle Workspace

Workspace procedural para gerar veiculos no Blender a partir de specs
estruturadas, blueprints e arquetipos. A regra principal e: prompt/imagem viram
`VehicleSpec`; o Blender recebe parametros normalizados e gera uma cena
auditavel.

## MVP atual

O primeiro corte implementa:

- normalizacao de `VehicleSpec`;
- arquetipos `supercar`, `suv` e `pickup`;
- rig dimensional;
- blockout automotivo;
- rodas/pneus simples;
- renders ortograficos;
- auditoria basica de dimensoes, simetria e rodas.

## Sistema de coordenadas

- unidade interna: metros;
- entrada humana: milimetros;
- X: comprimento, frente positiva;
- Y: largura;
- Z: altura;
- origem: centro do entre-eixos no chao;
- simetria: plano X/Z.

## Saidas

As execucoes headless gravam por padrao em `C:\tmp\mcp-ultra-vehicle-runs`,
porque processos externos do Blender podem ter restricoes para criar PNGs dentro
do workspace sandboxado. O destino pode ser sobrescrito por `VEHICLE_OUTPUT_ROOT`
ou pelo argumento `--output-dir` do runner.

```text
C:\tmp\mcp-ultra-vehicle-runs\<run_id>/
  scene.blend
  report.json
  renders/
    perspectiva.png
    frente.png
    traseira.png
    lado.png
    topo.png
```
