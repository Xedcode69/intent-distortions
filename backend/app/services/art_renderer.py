"""Shared scene primitives generate both PNG and inspectable layered SVG."""
import math
import html
from decimal import Decimal
from PIL import Image, ImageDraw, ImageFilter
from .art_seed import random_value
from .art_statistics import chain

VERSION = "echo-renderer-2"
SIZE = 1440

def scene_v1(seed, records, stats, direction, start, end, previous_hash, epoch):
    rand = lambda label, i: random_value(seed, label, i)
    colors = direction["palette"]
    shapes = []
    def line(layer, points, color, width=1, alpha=120):
        shapes.append(dict(kind="line", layer=layer, points=[[round(x,3), round(y,3)] for x,y in points], color=color, width=width, alpha=alpha))
    def dot(layer, x, y, radius, color, alpha=180):
        shapes.append(dict(kind="dot", layer=layer, center=[round(x,3),round(y,3)], radius=round(radius,3), color=color, alpha=alpha))
    n = max(len(records), 1)
    chain_names = sorted({chain(r["origin_asset"]) for r in records} | {chain(r["destination_asset"]) for r in records}) or ["Unmapped"]
    anchors = {c: (720+490*math.cos(i*math.tau/len(chain_names)), 720+490*math.sin(i*math.tau/len(chain_names))) for i,c in enumerate(chain_names)}
    max_volume = max([float(Decimal(r["amount_in_usd"] or "0")) for r in records] or [0])
    family = direction["composition"]
    complexity = stats["chain_diversity_score"]
    # Every record contributes through seed + aggregate features. Each route is drawn.
    for i, r in enumerate(records):
        a, b = anchors[chain(r["origin_asset"])], anchors[chain(r["destination_asset"])]
        control = (720+(rand("geometry",i)-0.5)*440,720+(rand("geometry",i+n)-0.5)*440)
        curve = [((1-t)**2*a[0]+2*(1-t)*t*control[0]+t*t*b[0],(1-t)**2*a[1]+2*(1-t)*t*control[1]+t*t*b[1]) for t in [j/64 for j in range(65)]]
        line("routes", curve, colors[i%len(colors)], 1, 45)
    count = stats["particle_count"]
    for i in range(count):
        r = records[i % len(records)] if records else None
        theta = math.tau*((r["created_at_unix"]-start)/(end-start)) if r else 0
        theta += (rand("particles", i)-0.5)*0.55
        u, v = rand("layout", i+2), rand("noise",i)
        radius = 90+490*math.sqrt(u)
        twist = direction["symmetry"]
        if family == "spiral_constellation":
            theta += radius/85
        elif family == "flow_field":
            theta += math.sin(radius/110)*1.8
        elif family == "crystalline":
            theta = round(theta/(math.tau/twist))*(math.tau/twist)+(v-.5)*.28
            radius = round(radius/75)*75 + v*12
        elif family == "fractal_branches":
            theta = round(theta/(math.tau/twist))*(math.tau/twist) + math.sin(radius/90)*.32
        elif family == "particle_nebula":
            theta += v*math.tau
            radius *= .5+.5*math.sin(theta*3)**2
        x = 720+radius*math.cos(theta)
        y = 720+radius*math.sin(theta)*(.70+.24*complexity)
        volume = float(Decimal(r["amount_in_usd"] or "0")) if r else 0
        prominence = math.log1p(volume)/math.log1p(max_volume) if max_volume else .5
        color = colors[chain_names.index(chain(r["origin_asset"]))%len(colors)] if r else colors[0]
        dot("particles",x,y,.5+2*prominence+v*1.4,color,65+int(150*v))
        if i % 3 == 0:
            da = .04+rand("geometry",i+2*n)*(.25+.3*complexity)
            points = [(720+radius*math.cos(theta+da*t),720+radius*math.sin(theta+da*t)*(.70+.24*complexity)) for t in [j/16 for j in range(17)]]
            line("geometry", points, color, 1, 30+int(prominence*75))
        if i % 23 == 0:
            dot("particles",x,y,5+6*prominence,color,18)
    # Previous image hash drives an observable inherited orbit.
    inherited_radius = 150+int(previous_hash[:8],16)/2**32*190
    inherited_angle = int(previous_hash[8:16],16)/2**32*math.tau
    line("inheritance",[(720+inherited_radius*math.cos(t/180*math.tau+inherited_angle),720+inherited_radius*.63*math.sin(t/180*math.tau)) for t in range(181)],colors[-1],2,120)
    # Visible 64-bit edition + 128-bit seed signature, with fixed point slots.
    signature_bits = f'{epoch:064b}'+f'{int(seed[:32],16):0128b}'
    for i, bit in enumerate(signature_bits):
        angle = math.tau*i/len(signature_bits)
        radius = 640 if bit == "1" else 631
        dot("signature",720+radius*math.cos(angle),720+radius*math.sin(angle),2 if bit == "1" else .7,colors[i%len(colors)],170)
    return {"version": "echo-renderer-1", "width": SIZE, "height": SIZE, "background": "#080C13", "family": family,
            "shapes": shapes, "mapping": {"palette": "source-chain index → persisted creative palette", "particles": "createdAtTimestamp → angle; log USD → radius and light", "geometry": "chain entropy → deformation; composition → trajectory", "inheritance": {"previous_hash": previous_hash, "radius": inherited_radius}, "signature": "64-bit epoch + 128-bit seed constellation"}}

def scene(seed,records,stats,direction,start,end,previous_hash,epoch):
    """Bounded v2 scene: route aggregation + six distinct geometry systems."""
    from collections import Counter
    rand=lambda label,i:random_value(seed,label,i)
    colors=direction["palette"];family=direction["composition"];diversity=stats["chain_diversity_score"]
    names=sorted({chain(r["origin_asset"]) for r in records}|{chain(r["destination_asset"]) for r in records}) or ["Unmapped"]
    shapes=[]
    def line(layer,points,color,width=1,alpha=90):
        shapes.append({"kind":"line","layer":layer,"points":[[round(x,3),round(y,3)] for x,y in points],"color":color,"width":width,"alpha":alpha})
    def dot(layer,x,y,r,color,alpha=180):shapes.append({"kind":"dot","layer":layer,"center":[round(x,3),round(y,3)],"radius":round(r,3),"color":color,"alpha":alpha})
    def point(radius,angle,ratio=.82):return (720+radius*math.cos(angle),720+radius*math.sin(angle)*ratio)
    anchors={c:point(500,math.tau*i/len(names),1) for i,c in enumerate(names)}
    routes=Counter((chain(r["origin_asset"]),chain(r["destination_asset"])) for r in records)
    for i,((origin,dest),frequency) in enumerate(sorted(routes.items())):
        a,b=anchors[origin],anchors[dest];control=(720+(rand("routes",i)-.5)*520,720+(rand("routes",i+len(routes))-.5)*520)
        points=[((1-t)**2*a[0]+2*(1-t)*t*control[0]+t*t*b[0],(1-t)**2*a[1]+2*(1-t)*t*control[1]+t*t*b[1]) for t in [j/48 for j in range(49)]]
        line("routes",points,colors[names.index(origin)%len(colors)],1,35+int(90*math.log1p(frequency)/math.log1p(max(routes.values()))))
    symmetry=direction["symmetry"];phase=rand("geometry",0)*math.tau
    if family=="fractal_branches":
        def branch(x,y,length,angle,depth,index):
            if not depth:return
            end=(x+length*math.cos(angle),y+length*math.sin(angle))
            line("geometry",[(x,y),end],colors[index%len(colors)],max(1,depth//2),25+depth*20)
            alpha=.60+.10*rand("branches",index);beta=.28+.4*diversity+.1*rand("branches",index+10000)
            branch(*end,length*alpha,angle-beta,depth-1,index*2+1)
            branch(*end,length*alpha,angle+beta,depth-1,index*2+2)
        for arm in range(symmetry):branch(720,720,155,phase+arm*math.tau/symmetry,6,arm+1)
    if family=="crystalline":
        vertices=[[point(80+ring*80,phase+i*math.tau/symmetry+(ring%2)*math.pi/symmetry) for i in range(symmetry)] for ring in range(7)]
        for ring in range(6):
            for i in range(symmetry):
                line("geometry",[vertices[ring][i],vertices[ring+1][i],vertices[ring+1][(i+1)%symmetry],vertices[ring][i]],colors[(ring+i)%len(colors)],1,80)
    max_volume=max((float(Decimal(r["amount_in_usd"] or "0")) for r in records),default=0)
    count=stats["particle_count"]
    for i in range(count):
        record=records[min(len(records)-1,i*len(records)//max(count,1))] if records else None
        theta=math.tau*(record["created_at_unix"]-start)/(end-start) if record else 0
        theta+=(rand("particles",i)-.5)*.25
        radius=75+475*math.sqrt(rand("layout",i));color=colors[names.index(chain(record["origin_asset"]))%len(colors)] if record else colors[0]
        if family=="spiral_constellation":theta+=radius/80+phase
        elif family=="crystalline":theta=phase+round((theta-phase)*symmetry/math.tau)*math.tau/symmetry+(rand("geometry",i)-.5)*.14;radius=round(radius/80)*80
        elif family=="fractal_branches":theta=phase+round((theta-phase)*symmetry/math.tau)*math.tau/symmetry+math.sin(radius/70)*.24
        if family=="particle_nebula":
            cluster=names.index(chain(record["origin_asset"])) if record else 0
            cx,cy=point(230,phase+math.tau*cluster/len(names),.8)
            spread=math.sqrt(-2*math.log(max(rand("nebula",i),1e-10)))*110
            x=cx+spread*math.cos(theta+rand("nebula",i+count)*math.tau);y=cy+spread*math.sin(theta)
        elif family=="flow_field":
            x,y=point(radius,theta)
            path=[(x,y)]
            for j in range(28):
                angle=math.sin(x/185+phase)*1.7+math.cos(y/170-phase)*1.1+theta*.15
                x+=5.5*math.cos(angle);y+=5.5*math.sin(angle);path.append((x,y))
            if i%3==0:line("geometry",path,color,1,55)
        else:x,y=point(radius,theta,.72+.22*diversity)
        volume=float(Decimal(record["amount_in_usd"] or "0")) if record else 0
        prominence=math.log1p(volume)/math.log1p(max_volume) if max_volume else .5
        if 45<x<1395 and 45<y<1395:
            dot("particles",x,y,.6+2.4*prominence+rand("noise",i),color,90+int(150*rand("light",i)))
            if i%17==0:dot("particles",x,y,5+5*prominence,color,20)
        if family in ("orbital_network","spiral_constellation") and i%4==0:
            arc=.10+.35*rand("geometry",i+count)
            line("geometry",[point(radius,theta+arc*j/24,.72+.22*diversity) for j in range(25)],color,1,50+int(80*prominence))
    inherited=150+int(previous_hash[:8],16)/2**32*190
    line("inheritance",[point(inherited,j*math.tau/180,.63) for j in range(181)],colors[-1],2,120)
    bits=f"{epoch:064b}"+f"{int(seed[:32],16):0128b}"
    for i,bit in enumerate(bits):
        x,y=point(640 if bit=="1" else 631,math.tau*i/192,1);dot("signature",x,y,2 if bit=="1" else .7,colors[i%len(colors)],180)
    return {"version":VERSION,"width":SIZE,"height":SIZE,"background":"#080C13","family":family,"shapes":shapes,
        "mapping":{"routes":"aggregated chain pairs; frequency controls intensity","particles":"even temporal sample; log public USD controls prominence","palette":"source-chain index into persisted direction palette","geometry":"seeded family-specific math; entropy deforms symmetry","inheritance":{"previous_hash":previous_hash,"radius":inherited},"signature":"64-bit edition + 128-bit seed constellation"}}

def render(manifest):
    from io import BytesIO
    size = manifest["width"]
    canvas = Image.new("RGB",(size,size),manifest["background"])
    layer = Image.new("RGBA",(size,size))
    draw = ImageDraw.Draw(layer)
    groups = {}
    for s in manifest["shapes"]:
        color = tuple(bytes.fromhex(s["color"][1:]))+(s["alpha"],)
        opacity = round(s["alpha"]/255,4)
        if s["kind"] == "dot":
            x,y = s["center"]; r = s["radius"]
            draw.ellipse((x-r,y-r,x+r,y+r),fill=color)
            tag = f'<circle cx="{x}" cy="{y}" r="{r}" fill="{s["color"]}" opacity="{opacity}"/>'
        else:
            pts = [tuple(p) for p in s["points"]]
            draw.line(pts,fill=color,width=s["width"])
            points = " ".join(f"{x},{y}" for x,y in pts)
            tag = f'<polyline points="{points}" fill="none" stroke="{s["color"]}" stroke-width="{s["width"]}" opacity="{opacity}"/>'
        groups.setdefault(s["layer"],[]).append(tag)
    # Raster glow is deterministic within pinned Pillow; canonical bytes are frozen once.
    canvas = Image.alpha_composite(canvas.convert("RGBA"),layer.filter(ImageFilter.GaussianBlur(6)))
    canvas = Image.alpha_composite(canvas, layer).convert("RGB")
    png = BytesIO(); canvas.save(png,format="PNG",compress_level=9)
    thumb = canvas.copy(); thumb.thumbnail((640,640))
    webp = BytesIO(); thumb.save(webp,format="WEBP",quality=88,method=6)
    svg = f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {size} {size}" role="img" aria-label="Transaction-derived artwork"><rect width="{size}" height="{size}" fill="{manifest["background"]}"/>'
    svg += "".join(f'<g id="{html.escape(k)}">'+"".join(v)+"</g>" for k,v in groups.items())+"</svg>"
    return {"artwork.png": png.getvalue(), "artwork.svg": svg.encode(), "thumbnail.webp": webp.getvalue()}
