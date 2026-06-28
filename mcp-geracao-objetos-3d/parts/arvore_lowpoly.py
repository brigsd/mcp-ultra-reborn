import bpy
import math
import mathutils
from api.validators import validar_objeto, relatorio_para_texto

# Parâmetros de proporção da árvore
TAPER = 0.7        # Razão de raio (pai -> filho)
ENCURTA = 0.75     # Razão de comprimento (pai -> filho)
ABRE = math.radians(35) # Ângulo de inclinação para fora
OURO = math.radians(137.5) # Ângulo de rotação de Fibonacci

def criar_cilindro_simples(base, topo, raio_base, raio_topo, lados=5, nome="Galho"):
    mesh = bpy.data.meshes.new(nome)
    obj = bpy.data.objects.new(nome, mesh)
    bpy.context.collection.objects.link(obj)
    
    import bmesh
    bm = bmesh.new()
    
    dir_vec = topo - base
    comprimento = dir_vec.length
    dir_vec.normalize()
    
    up = mathutils.Vector((0, 0, 1))
    rot = up.rotation_difference(dir_vec)
    
    verts_base = []
    verts_topo = []
    for i in range(lados):
        ang = i * (2 * math.pi / lados)
        x = math.cos(ang)
        y = math.sin(ang)
        
        # Rotaciona e translada
        v_b = rot @ mathutils.Vector((x * raio_base, y * raio_base, 0)) + base
        v_t = rot @ mathutils.Vector((x * raio_topo, y * raio_topo, comprimento)) + base
        
        verts_base.append(bm.verts.new(v_b))
        verts_topo.append(bm.verts.new(v_t))
        
    for i in range(lados):
        next_i = (i + 1) % lados
        bm.faces.new((verts_base[i], verts_base[next_i], verts_topo[next_i], verts_topo[i]))
        
    bm.faces.new(verts_base)
    bm.faces.new(verts_topo)
    
    bm.to_mesh(mesh)
    bm.free()
    return obj

def criar_folhagem(pos, raio, nome="Folha"):
    mesh = bpy.data.meshes.new(nome)
    obj = bpy.data.objects.new(nome, mesh)
    bpy.context.collection.objects.link(obj)
    
    import bmesh
    bm = bmesh.new()
    bmesh.ops.create_icosphere(bm, subdivisions=1, radius=raio)
    
    for v in bm.verts:
        v.co += pos
        
    bm.to_mesh(mesh)
    bm.free()
    return obj

def _crescer_galhos(base, dir_vec, comp, raio, prof, max_prof, objects):
    topo = base + dir_vec * comp
    
    raio_topo = raio * TAPER
    galho = criar_cilindro_simples(base, topo, raio, raio_topo, lados=5)
    objects.append(galho)
    
    if prof >= max_prof:
        folha = criar_folhagem(topo, comp * 1.5)
        objects.append(folha)
        return
        
    # Eixos perpendiculares para rotação
    up = mathutils.Vector((0, 0, 1))
    if abs(dir_vec.z) < 0.9:
        perp = dir_vec.cross(up).normalized()
    else:
        perp = dir_vec.cross(mathutils.Vector((1, 0, 0))).normalized()
        
    for i in range(2):
        ang_radial = i * OURO + prof
        dir_rot = dir_vec.copy()
        
        # Inclina o galho para fora
        m_inclina = mathutils.Matrix.Rotation(ABRE, 4, perp)
        dir_rot = m_inclina @ dir_rot
        
        # Rotaciona ao redor do galho pai
        m_radial = mathutils.Matrix.Rotation(ang_radial, 4, dir_vec)
        dir_rot = m_radial @ dir_rot
        dir_rot.normalize()
        
        _crescer_galhos(topo, dir_rot, comp * ENCURTA, raio_topo, prof + 1, max_prof, objects)

def gerar(profundidade=4, raio_tronco=0.15, nome="ArvoreLowPoly"):
    objects = []
    _crescer_galhos(
        base=mathutils.Vector((0, 0, 0)),
        dir_vec=mathutils.Vector((0, 0, 1)),
        comp=1.2,
        raio=raio_tronco,
        prof=1,
        max_prof=profundidade,
        objects=objects
    )
    
    # Faz o Join de todas as partes em um único objeto mesh
    bpy.ops.object.select_all(action='DESELECT')
    for obj in objects:
        obj.select_set(True)
        
    bpy.context.view_layer.objects.active = objects[0]
    bpy.ops.object.join()
    
    arvore = objects[0]
    arvore.name = nome
    return arvore

def gerar_e_validar(profundidade=4, raio_tronco=0.15):
    obj = gerar(profundidade=profundidade, raio_tronco=raio_tronco)
    rel = validar_objeto(obj)
    txt = relatorio_para_texto(rel)
    return obj, txt
