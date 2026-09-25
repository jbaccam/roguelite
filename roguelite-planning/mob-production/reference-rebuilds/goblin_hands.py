"""Sculpted Goblin fists with a transverse grip and integrated finger pads."""
from meshlib import *

GRIP_CENTER = Vector((1.50, -.22, 2.04))
GRIP_AXIS = Vector((.90, -.30, -.31)).normalized()

def finish_skin(body):
    """Budget the final joined skin after the contact/toe booleans."""
    body.data.calc_loop_triangles()
    count=len(body.data.loop_triangles)
    if count>19500:
        bpy.context.view_layer.objects.active=body
        mod=body.modifiers.new('Final continuous skin budget','DECIMATE')
        mod.ratio=19500/count
        bpy.ops.object.modifier_apply(modifier=mod.name)
    # Collapsing coplanar boolean faces can leave loose edges without faces.
    bm=bmesh.new();bm.from_mesh(body.data)
    bmesh.ops.delete(bm,geom=[e for e in bm.edges if e.is_wire],context='EDGES')
    bmesh.ops.delete(bm,geom=[v for v in bm.verts if not v.link_faces],context='VERTS')
    bm.to_mesh(body.data);bm.free()

def goblin_hand(side, material):
    c = Vector((side * GRIP_CENTER.x, GRIP_CENTER.y, GRIP_CENTER.z))
    a = Vector((side * GRIP_AXIS.x, GRIP_AXIS.y, GRIP_AXIS.z))
    b = Vector((0, -1, 0)); b = (b - a * a.dot(b)).normalized()
    d = a.cross(b) * side
    def at(x, y, z): return c + a*x + b*y + d*z
    pieces = []
    def pad(name, p, scale):
        o = ell(name, (0,0,0), scale, material, 28, 18)
        for v in o.data.vertices:
            x,y,z = v.co; v.co = at(p[0]+x,p[1]+y,p[2]+z)
        pieces.append(o)
    # One loft from wrist through metacarpals. It has no intersecting primitive
    # end caps, so the back of the hand cannot acquire a false horizontal slit.
    sections=[(-.52,-.15,-.025,.18,.18),(-.36,-.105,.05,.20,.195),
              (-.22,-.04,.145,.255,.18),(-.06,0,.175,.291,.157),
              (.08,0,.171,.298,.145),(.19,-.01,.095,.274,.128),
              (.235,-.01,.07,.20,.085)]
    vertices=[];n=28
    for z,x,y,rx,ry in sections:
        for k in range(n):
            t=k*math.tau/n;cs=math.cos(t);sn=math.sin(t)
            vertices.append(at(x+math.copysign(abs(cs)**.80,cs)*rx,
                               y+math.copysign(abs(sn)**.80,sn)*ry,z))
    faces=[tuple(range(n-1,-1,-1))]
    faces += [(j*n+k,j*n+(k+1)%n,(j+1)*n+(k+1)%n,(j+1)*n+k) for j in range(len(sections)-1) for k in range(n)]
    faces.append(tuple(range((len(sections)-1)*n,len(sections)*n)))
    pieces.append(mesh('Continuous wrist and metacarpals',vertices,faces,material))
    # Four fingers turn down and back toward the palm. Their roots overlap and
    # are remeshed into the palm; staggered knuckles avoid a stack of bars.
    finger_x = [-.219,-.074,.073,.211]
    for j, x in enumerate(finger_x):
        drop = [0,.013,-.006,-.044][j]
        rr = [.083,.087,.084,.076][j]
        path = [at(x,.192,-.014), at(x,.190,.125+drop),
                at(x,.112,.211+drop), at(x,-.033,.222+drop),
                at(x,-.150,.143+drop), at(x,-.167,.044+drop)]
        pieces.append(tube('Curled finger pad '+str(j+1),path,[rr,rr,rr,rr*.95,rr*.92,rr*.84],material,14))
        pad('Rounded fingertip '+str(j+1),(x,-.166,.044+drop),(rr*.83,rr*.84,rr*.86))
    # Thenar web and two thumb phalanges cross the inward face of the fist.
    pad('Thumb web',(-.236,.074,-.159),(.128,.159,.153))
    thumb = [at(-.247,.09,-.189),at(-.334,-.026,-.127),
             at(-.325,-.147,-.042),at(-.227,-.221,.044),at(-.123,-.222,.065)]
    pieces.append(tube('Opposing thumb',thumb,[.114,.115,.104,.089,.073],material,16))
    pad('Thumb pad',(-.127,-.223,.066),(.079,.081,.078))
    hand = fuse(pieces, ('Right' if side==1 else 'Left')+' sculpted fist', material, .011, 4800, 4)
    if side==1:
        # A real channel through the grasp, fitted to the leather wrapping.
        cut(hand,tube('Handle contact channel',[c-a*.48,c+a*.48],.136, None,32))
    # Very shallow separations only on the folded underside, not across the
    # palm or wrist. Each finger remains part of the continuous hand surface.
    for x in [-.147,0,.143]:
        pts=[at(x,.112,.282),at(x,.016,.289),at(x,-.085,.251),at(x,-.176,.181)]
        cut(hand,tube('Fold separation',pts,.012,None,8))
    rigid(hand,'RightHand' if side==1 else 'LeftHand')
    return hand
