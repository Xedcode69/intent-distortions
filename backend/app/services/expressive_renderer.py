"""Renderer 4: data-driven family controls and deterministic layered materials."""
import colorsys
import hashlib
import html
import math
from io import BytesIO
from decimal import Decimal
from PIL import Image, ImageDraw, ImageFilter
from .art_seed import random_value
from .asset_networks import network_label, mapping_commitment
from .canonical_data import canonical,sha
from .visual_features import RENDERER_VERSION

SIZE=1440
TAU=math.tau
MATERIALS=("glass","ink","grain","iridescent","luminous")


def clamp(value,low=0,high=1):
    return max(low,min(high,value))


def rgb(color):
    return tuple(bytes.fromhex(color[1:]))


def hex_color(values):
    return '#'+''.join(f'{round(clamp(value,0,255)):02X}' for value in values)


def mix(a,b,weight):
    return hex_color([x*(1-weight)+y*weight for x,y in zip(rgb(a),rgb(b))])


def profile(text,choices,keywords):
    value=text.lower()
    for key,words in keywords:
        if any(word in value for word in words):return key
    return choices[int.from_bytes(hashlib.sha256(value.encode()).digest()[:4],'big')%len(choices)]


def style_controls(seed,features,direction):
    complexity=clamp(direction['complexity'])
    material=profile(direction['material'],MATERIALS,(
        ('glass',('glass','crystal','transluc','transparent')),('ink',('ink','graphite','charcoal')),
        ('iridescent',('irides','metal','foil')),('grain',('grain','paper','stipple','mineral')),
        ('luminous',('lumin','neon','light','plasma'))))
    theme=profile(direction['theme'],('celestial','tidal','botanical','ember','electric'),(
        ('ember',('sunset','ember','fire','warm')),('tidal',('ocean','tide','water','river')),
        ('botanical',('forest','organic','growth','earth')),('electric',('electric','cyber','neon')),
        ('celestial',('orbit','cosmic','celestial','galax','constellation'))))
    dark=not(material in ('ink','grain') and random_value(seed,'paper',0)>.45)
    bases={'celestial':('#080D1B','#1D1735'),'tidal':('#071B22','#14393E'),
           'botanical':('#0A1712','#253B29'),'ember':('#21101A','#492A22'),'electric':('#100E25','#14313B')}
    top,bottom=bases[theme] if dark else ('#F1EADB','#D4D6CA')
    palette=[]
    for color in direction['palette']:
        hue,light,saturation=colorsys.rgb_to_hls(*(value/255 for value in rgb(color)))
        light=clamp(light,.48,.74) if dark else clamp(light,.22,.40)
        palette.append(hex_color([value*255 for value in colorsys.hls_to_rgb(hue,light,clamp(saturation,.35,.78))]))
    return {'material':material,'theme':theme,'complexity':round(complexity,6),'dark':dark,
            'palette':palette,'background_top':top,'background_bottom':bottom,
            'perspective':round(.08+.25*features['flow_imbalance']+.12*complexity,6),
            'light_angle':round(TAU*random_value(seed,'lighting',0),6),
            'light_intensity':round(.25+.45*features['asset_diversity'],6),
            'texture_density':round(.2+.65*complexity,6)}


def family_controls(features,direction):
    f=features;c=clamp(direction['complexity']);symmetry=direction['symmetry']
    return {
      'orbital_network':{'eccentricity':round(.08+.54*f['flow_imbalance'],6),
        'tilt':round((f['reciprocity']-.5)*1.3,6),'nested_rings':2+round(4*f['reciprocity']),
        'anchor_layout':'hub-weighted ellipses','rotation_direction':-1 if f['flow_imbalance']>.25 else 1},
      'fractal_branches':{'depth':3+round(4*c),'branching_ratio':3 if f['route_diversity']>.7 and c>.6 else 2,
        'taper':round(.58+.19*f['hub_concentration'],6),'curvature':round(.1+.65*f['burstiness'],6),
        'leaf_density':round(.25+.7*f['asset_diversity'],6),'arms':max(2,min(8,round(symmetry*.5+2*f['route_diversity'])))},
      'crystalline':{'facets':max(5,min(24,symmetry+5+round(7*f['asset_diversity']))),
        'irregularity':round(.02+.16*f['burstiness'],6),'growth_direction':round((f['flow_imbalance']-.5)*math.pi,6),
        'subdivisions':2+round(4*c),'translucency':round(.22+.53*f['reciprocity'],6)},
      'flow_field':{'vortex_count':max(1,min(8,f['community_count'])),'turbulence':round(.12+.85*f['burstiness'],6),
        'stream_thickness':round(.6+2.6*f['size_inequality'],6),'interacting_current_strength':round(.2+.7*f['cross_network_share'],6),
        'steps':35+round(45*c),'streams':120+round(360*c)},
      'spiral_constellation':{'arms':2+min(6,round(f['rhythm_peaks']/3)),
        'winding':round(1.25+3.1*f['burstiness']+c,6),'asymmetry':round(.04+.4*f['flow_imbalance'],6),
        'temporal_bands':3+min(9,round(f['rhythm_peaks']/2)),'pitch':round(.65+.65*f['asset_diversity'],6)},
      'particle_nebula':{'cluster_count':max(1,min(16,f['community_count'])),
        'density':round(.35+.6*f['hub_concentration'],6),'elongation':round(1+2*f['size_inequality'],6),
        'overlap':round(.15+.65*f['reciprocity'],6),'diffusion':round(55+110*f['size_inequality'],6),
        'dust':100+round(500*c)}}[direction['composition']]


def scene_v4(seed,records,stats,direction,start,end,previous_hash,epoch,asset_mapping):
    f=stats['visual_features'];style=style_controls(seed,f,direction);controls=family_controls(f,direction)
    family=direction['composition'];rand=lambda label,i:random_value(seed,label,i)
    palette=style['palette'];shapes=[];nodes=f['nodes'];names=[node['network'] for node in nodes]
    by_name={node['network']:node for node in nodes}
    phase=rand('composition',0)*TAU
    network_colors={}
    for name in names:
        hue=int.from_bytes(hashlib.sha256(('NETWORK_HUE_V1:'+name).encode()).digest()[:4],'big')/2**32
        color=hex_color([value*255 for value in colorsys.hls_to_rgb(hue,.65 if style['dark'] else .32,.62)])
        # Each network retains its identity hue; the AI palette supplies a bounded tint.
        network_colors[name]=mix(color,palette[int(hue*len(palette))%len(palette)],.24)

    def project(x,y,z=0):
        scale=1/(1+style['perspective']*z)
        return [round(clamp(720+(x-720)*scale,12,1428),3),round(clamp(720+(y-720)*scale,12,1428),3)]

    def add(kind,layer,color,alpha=120,z=0,time=None,**values):
        shape={'kind':kind,'layer':layer,'color':color,'alpha':round(clamp(alpha,0,255)),'depth':round(z,4),**values}
        if time is not None:shape['time']=round(clamp(time),6)
        shapes.append(shape)
        return shape

    def line(layer,points,color,width=1,alpha=100,z=0,time=None):
        return add('line',layer,color,alpha,z,time,points=[project(x,y,z) for x,y in points],width=round(width,3))

    def dot(layer,x,y,r,color,alpha=160,z=0,time=None):
        return add('dot',layer,color,alpha,z,time,center=project(x,y,z),radius=round(max(.2,r/(1+style['perspective']*z)),3))

    def curve(layer,points,color,width=1,alpha=100,z=0,time=None):
        return add('curve',layer,color,alpha,z,time,points=[project(x,y,z) for x,y in points],width=round(width,3))

    def surface(points,color,z=0,alpha=70,time=None):
        mat=style['material'];opacity=alpha*(.6 if mat=='glass' else 1)
        shade=(.5+.5*math.cos(style['light_angle']+z*3))*style['light_intensity']
        face=mix(color,'#FFFFFF' if style['dark'] else '#17252B',shade*.32)
        if mat=='iridescent':
            hue,light,saturation=colorsys.rgb_to_hls(*(value/255 for value in rgb(face)))
            face=hex_color([value*255 for value in colorsys.hls_to_rgb((hue+.13*math.sin(z*5+style['light_angle']))%1,light,saturation)])
        if mat=='luminous':opacity*=.8
        add('polygon','surfaces',face,opacity,z,time,points=[project(x,y,z) for x,y in points],
            stroke=mix(face,'#FFFFFF' if style['dark'] else '#101920',.42),width=.6+shade,
            glow=mat in ('glass','iridescent','luminous'))

    def ellipse(cx,cy,r,angle,eccentricity=0,z=0):
        result=[]
        for j in range(81):
            t=j*TAU/80;x=r*math.cos(t);y=r*(1-eccentricity)*math.sin(t)
            result.append((cx+x*math.cos(angle)-y*math.sin(angle),cy+x*math.sin(angle)+y*math.cos(angle)))
        return result

    communities=sorted(set(node['community'] for node in nodes)) or [0]
    centers={community:(720+350*math.sqrt((i+.4)/len(communities))*math.cos(phase+i*2.399963),
                        720+320*math.sqrt((i+.4)/len(communities))*math.sin(phase+i*2.399963))
             for i,community in enumerate(communities)}
    anchors={}
    for i,node in enumerate(nodes):
        angle=phase+i*TAU/max(1,len(nodes))
        if family=='orbital_network':
            r=350+170*node['hub']+40*node['flow'];tilt=controls['tilt']
            x=r*math.cos(angle);y=r*(1-controls['eccentricity'])*math.sin(angle)
            anchors[node['network']]=(720+x*math.cos(tilt)-y*math.sin(tilt),720+x*math.sin(tilt)+y*math.cos(tilt))
        elif family=='flow_field':anchors[node['network']]=(180+1080*(i/max(1,len(nodes)-1)),720+330*math.sin(angle))
        elif family=='fractal_branches':anchors[node['network']]=(160+1120*(i/max(1,len(nodes)-1)),280+400*(1-node['hub']))
        elif family=='particle_nebula':
            cx,cy=centers[node['community']];anchors[node['network']]=(cx+65*math.cos(angle),cy+65*math.sin(angle))
        else:anchors[node['network']]=(720+490*math.cos(angle),720+490*math.sin(angle))

    # Actual route paths remain complete; the strongest paths also receive filled ribbons.
    for i,route in enumerate(f['routes']):
        a=anchors[route['origin']];b=anchors[route['destination']];w=route['weight']
        bend=(1-f['reciprocity'])*190;mid=((a[0]+b[0])/2,(a[1]+b[1])/2)
        points=[a,(mid[0]+(rand('route-bend',i)-.5)*bend,mid[1]-150*w),
                (mid[0]+(rand('route-bend',i+10000)-.5)*bend,mid[1]+100*(1-w)),b]
        path=curve('routes',points,network_colors[route['origin']],.4+1.3*w,8+48*w**3,-.15,route['first'])
        path.update(weight=w,motion_rate=round(.018+.12*w,6))
        if route['count']>=max(1,len(records)*.005):
            samples=cubic_points(points,24);surface(ribbon(samples,1+3*w),network_colors[route['origin']],-.3,12+25*w,route['first'])

    if family=='orbital_network':
        for ring in range(controls['nested_rings']):
            r=160+ring*75;z=(ring-controls['nested_rings']/2)*.13
            pts=ellipse(720,720,r,controls['tilt']+ring*.11,controls['eccentricity'],z)
            line('geometry',pts,palette[ring%len(palette)],1.2+ring*.3,115,z)
            surface(ribbon(pts,2+3*f['reciprocity']),palette[ring%len(palette)],z+.05,25)
        for i,name in enumerate(names):
            x,y=anchors[name];node=by_name[name]
            dot('lighting',x,y,10+22*node['hub'],network_colors[name],20,-.05)
            dot('geometry',x,y,2+5*node['hub'],network_colors[name],210,-.1)
    elif family=='fractal_branches':
        budget=[0]
        per_arm=max(1,850//controls['arms'])
        def branch(x,y,length,angle,depth,index,origin):
            if depth<=0 or budget[0]>=per_arm:return
            budget[0]+=1;z=(depth-controls['depth'])*.04
            curve_amount=controls['curvature']*(rand('branch-curl',index)-.5)
            end_point=(x+length*math.cos(angle),y+length*math.sin(angle))
            points=[(x,y),(x+length*.3*math.cos(angle+curve_amount),y+length*.3*math.sin(angle+curve_amount)),
                    (x+length*.7*math.cos(angle-curve_amount),y+length*.7*math.sin(angle-curve_amount)),end_point]
            color=palette[origin%len(palette)];width=.6+depth**1.4*.45
            curve('geometry',points,color,width,160,z,1-depth/max(1,controls['depth']))
            if depth>2:surface(ribbon(cubic_points(points,12),width*.65),color,z+.03,35)
            if depth<=2:
                for leaf in range(round(4*controls['leaf_density'])):
                    offset=(rand('leaf',index*4+leaf)-.5)*23
                    dot('particles',end_point[0]+offset,end_point[1]+offset*.5,1.5+3*rand('leaf-size',index+leaf),color,160,z)
            for child in range(controls['branching_ratio']):
                spread=(child-(controls['branching_ratio']-1)/2)*(.35+.4*f['route_diversity'])
                branch(*end_point,length*controls['taper'],angle+spread+curve_amount,depth-1,index*3+child+1,origin)
        for arm in range(controls['arms']):
            budget[0]=0
            branch(720,1200,210,-math.pi/2+(arm-(controls['arms']-1)/2)*.48,controls['depth'],arm+1,arm)
    elif family=='crystalline':
        facets=controls['facets'];rings=controls['subdivisions'];vertices=[]
        for ring in range(rings+1):
            vertices.append([(720+(55+ring*480/rings)*(1+(rand('facet-jitter',ring*facets+i)-.5)*controls['irregularity'])*math.cos(phase+controls['growth_direction']+i*TAU/facets+(ring%2)*math.pi/facets),
                              720+(55+ring*480/rings)*math.sin(phase+controls['growth_direction']+i*TAU/facets+(ring%2)*math.pi/facets)*(.7+.2*f['reciprocity'])) for i in range(facets)])
        for ring in range(rings):
            for i in range(facets):
                z=(rand('facet-depth',ring*facets+i)-.5)*.9;color=palette[(i+ring)%len(palette)]
                surface([vertices[ring][i],vertices[ring+1][i],vertices[ring+1][(i+1)%facets]],color,z,45+100*(1-controls['translucency']),ring/max(1,rings))
                surface([vertices[ring][i],vertices[ring+1][(i+1)%facets],vertices[ring][(i+1)%facets]],color,z+.04,35+75*(1-controls['translucency']),ring/max(1,rings))
    elif family=='flow_field':
        vortex=list(centers.values())[:controls['vortex_count']]
        for i in range(controls['streams']):
            x=140+1160*rand('stream-x',i);y=150+1140*rand('stream-y',i);path=[(x,y)]
            for j in range(controls['steps']):
                vx=1.2;vy=(f['flow_imbalance']-.25)*1.1
                for k,(cx,cy) in enumerate(vortex):
                    dx=x-cx;dy=y-cy;den=max(120,math.hypot(dx,dy));sign=-1 if k%2 else 1
                    vx-=sign*dy/den*controls['interacting_current_strength'];vy+=sign*dx/den*controls['interacting_current_strength']
                angle=math.atan2(vy,vx)+controls['turbulence']*.7*math.sin(x/130+y/180+phase)
                x+=5*math.cos(angle);y+=5*math.sin(angle);path.append((x,y))
            color=palette[i%len(palette)];z=(rand('stream-z',i)-.5)*.8
            if i%7==0:surface(ribbon(path,controls['stream_thickness']*2),color,z,50,i/max(1,controls['streams']))
            curve('geometry',[path[0],path[len(path)//3],path[2*len(path)//3],path[-1]],color,controls['stream_thickness'],80+80*rand('stream-light',i),z,i/max(1,controls['streams']))
    elif family=='spiral_constellation':
        for arm in range(controls['arms']):
            path=[]
            for j in range(181):
                t=j/180;r=30+500*t**controls['pitch'];theta=phase+arm*TAU/controls['arms']+controls['winding']*TAU*t
                path.append((720+r*math.cos(theta)*(1+controls['asymmetry']*math.sin(theta)),720+r*math.sin(theta)*.82))
            color=palette[arm%len(palette)];surface(ribbon(path,3+7*f['route_diversity']),color,arm*.04,60)
            line('geometry',path,color,1.6,160,arm*.04)
            for band in range(controls['temporal_bands']):
                index=round((band+1)*180/(controls['temporal_bands']+1));x,y=path[index]
                dot('geometry',x,y,3+5*f['activity_profile'][min(47,int(band/controls['temporal_bands']*48))],color,160,arm*.04,band/controls['temporal_bands'])

    count=min(2400,round(stats['particle_count']*(.45+.55*style['complexity'])))
    max_log=math.log1p(max((float(Decimal(row['amount_in_usd'] or '0')) for row in records),default=0))
    for i in range(count):
        record=records[min(len(records)-1,i*len(records)//max(1,count))]
        name=network_label(record['origin_asset'],asset_mapping);node=by_name[name]
        t=clamp((record['created_at_unix']-start)/max(1,end-start));theta=phase+t*TAU
        z=(rand('particle-depth',i)-.5)*1.1;color=network_colors[name]
        radius=70+470*math.sqrt(rand('particle-radius',i))
        if family=='particle_nebula':
            cx,cy=centers[communities[node['community']%controls['cluster_count']]]
            spread=math.sqrt(-2*math.log(max(1e-10,rand('nebula-spread',i))))*controls['diffusion']
            spread*=.65+controls['overlap']
            angle=rand('nebula-angle',i)*TAU;elongation=controls['elongation']
            x=cx+spread*math.cos(angle)*math.sqrt(elongation);y=cy+spread*math.sin(angle)/math.sqrt(elongation)
            # Density increases occupancy around the community center, without changing membership.
            x=cx+(x-cx)*(1-.35*controls['density']);y=cy+(y-cy)*(1-.35*controls['density'])
        elif family=='flow_field':x=160+1120*t;y=720+360*math.sin(theta+radius/240)+100*(rand('flow-particle',i)-.5)
        elif family=='spiral_constellation':
            arm=i%controls['arms'];band=round(t*controls['temporal_bands'])/controls['temporal_bands'];radius=55+480*band**controls['pitch']
            theta=phase+arm*TAU/controls['arms']+controls['winding']*TAU*t
            x=720+radius*math.cos(theta)*(1+controls['asymmetry']*math.sin(theta));y=720+radius*math.sin(theta)*.82
        elif family=='fractal_branches':x=180+1080*rand('branch-particle-x',i);y=230+830*t
        elif family=='crystalline':
            theta=phase+controls['growth_direction']+round(t*controls['facets'])*TAU/controls['facets']
            radius=60+round(radius/100)*95;x=720+radius*math.cos(theta);y=720+radius*math.sin(theta)*.8
        else:
            theta*=controls['rotation_direction'];radius=100+round(radius/75)*75
            x=720+radius*math.cos(theta);y=720+radius*(1-controls['eccentricity'])*math.sin(theta)
            dx=x-720;dy=y-720;x=720+dx*math.cos(controls['tilt'])-dy*math.sin(controls['tilt']);y=720+dx*math.sin(controls['tilt'])+dy*math.cos(controls['tilt'])
        prominence=math.log1p(float(Decimal(record['amount_in_usd'] or '0')))/max_log if max_log else .3
        size=.7+3*prominence+rand('particle-size',i)
        if 45<x<1395 and 45<y<1395:
            dot('particles',x,y,size,color,120+100*rand('particle-light',i),z,t)
            if i%23==0:dot('lighting',x,y,5+8*prominence,color,15+20*prominence,z+.02,t)

    dust=controls.get('dust',0)
    for i in range(dust):
        cx,cy=list(centers.values())[i%len(centers)];angle=rand('dust-angle',i)*TAU;radius=100+300*rand('dust-radius',i)
        dot('textures',cx+radius*math.cos(angle),cy+radius*math.sin(angle),.3+rand('dust-size',i),palette[i%len(palette)],25,-.5)
    texture_count=round(250+1000*style['texture_density'])
    for i in range(texture_count):
        x=50+1340*rand('grain-x',i);y=50+1340*rand('grain-y',i);color=palette[i%len(palette)]
        alpha=(22+round(35*style['texture_density'])) if style['material']=='grain' else 12+round(20*style['texture_density'])
        if style['material']=='ink':
            length=2+8*rand('hatch-length',i);angle=style['light_angle']+.4
            line('textures',[(x,y),(x+length*math.cos(angle),y+length*math.sin(angle))],color,.5,alpha,-.8)
        else:dot('textures',x,y,.25+.75*rand('grain-size',i),color,alpha,-.8)

    inherited=160+int(previous_hash[:8],16)/2**32*160
    line('inheritance',ellipse(720,720,inherited,phase,.35),palette[-1],1.2,80,.7)
    bits=f'{epoch:064b}'+f'{int(seed[:32],16):0128b}'
    for i,bit in enumerate(bits):
        edge=i//48;fraction=(i%48+.5)/48
        x,y=((60+1320*fraction,60),(1380,60+1320*fraction),(1380-1320*fraction,1380),(60,1380-1320*fraction))[edge]
        dot('signature',x,y,1.7 if bit=='1' else .65,palette[i%len(palette)],180,.9)
    shapes.sort(key=lambda shape:shape['depth'])
    from .family_selection import select_family
    return {'version':RENDERER_VERSION,'family_selection':select_family(seed),'width':SIZE,'height':SIZE,'background':style['background_top'],
        'background_style':{'top':style['background_top'],'bottom':style['background_bottom'],
            'light':[round(720+500*math.cos(style['light_angle']),3),round(720+500*math.sin(style['light_angle']),3)],
            'intensity':style['light_intensity']},'family':family,'shapes':shapes,'network_colors':network_colors,
        'controls':{'family':controls,'style':style},'visual_features_sha256':sha(canonical(f)).hex(),
        'animation':{'version':'data-motion-v2','period_seconds':32,'reveal_seconds':24,
            'pulse_hz':round(.08+.3*f['burstiness'],6),'activity_profile':f['activity_profile'],
            'direction':controls.get('rotation_direction',1),'meaning':'Activity and route-frequency encodings; not settlement speed'},
        'mapping':{'asset_networks_commitment':mapping_commitment(asset_mapping),
            'routes':'exact network pairs; frequency controls ribbon width, intensity and motion rate',
            'geometry':'versioned family controls derived from frozen flow, rhythm, communities and distributions',
            'surfaces':'material opacity, lit edges and perspective depth',
            'textures':'seeded stippling, grain or ink hatching','particles':'bounded temporal sample; input USD controls prominence',
            'inheritance':{'previous_hash':previous_hash,'radius':inherited},'signature':'64-bit edition and 128-bit seed border'}}


def cubic_points(points,steps=40):
    a,b,c,d=points
    return [tuple((1-t)**3*a[k]+3*(1-t)**2*t*b[k]+3*(1-t)*t*t*c[k]+t**3*d[k] for k in (0,1)) for t in (i/steps for i in range(steps+1))]


def ribbon(points,width):
    left=[];right=[]
    for i,(x,y) in enumerate(points):
        a=points[max(0,i-1)];b=points[min(len(points)-1,i+1)];dx=b[0]-a[0];dy=b[1]-a[1];length=max(1,math.hypot(dx,dy))
        taper=.25+.75*math.sin(math.pi*i/max(1,len(points)-1))
        left.append((x-dy/length*width*taper,y+dx/length*width*taper));right.append((x+dy/length*width*taper,y-dx/length*width*taper))
    return left+right[::-1]


def render_v4(manifest):
    width,height=manifest['width'],manifest['height'];background=manifest['background_style']
    canvas=Image.new('RGB',(width,height));painter=ImageDraw.Draw(canvas)
    top,bottom=rgb(background['top']),rgb(background['bottom'])
    for y in range(height):
        t=y/max(1,height-1);painter.line([(0,y),(width,y)],fill=tuple(round(a*(1-t)+b*t) for a,b in zip(top,bottom)))
    # Soft directional illumination is a fixed surface, not an external image asset.
    light=Image.new('RGBA',(width,height));light_draw=ImageDraw.Draw(light);lx,ly=background['light']
    for ring in range(35,0,-1):
        radius=ring*23;alpha=round((1-ring/36)*background['intensity']*2)
        light_draw.ellipse((lx-radius,ly-radius,lx+radius,ly+radius),fill=(180,205,220,alpha))
    canvas=Image.alpha_composite(canvas.convert('RGBA'),light).convert('RGB')
    glow=Image.new('RGBA',(width,height));glow_draw=ImageDraw.Draw(glow)
    svg=[]
    for shape in manifest['shapes']:
        color=rgb(shape['color'])+(shape['alpha'],);opacity=round(shape['alpha']/255,5)
        draw=ImageDraw.Draw(canvas,'RGBA');kind=shape['kind'];stroke=shape.get('stroke',shape['color'])
        attrs=f' data-layer="{html.escape(shape["layer"])}"'
        if kind=='dot':
            x,y=shape['center'];r=shape['radius'];draw.ellipse((x-r,y-r,x+r,y+r),fill=color)
            if shape['layer'] in ('lighting','particles'):glow_draw.ellipse((x-r,y-r,x+r,y+r),fill=color)
            tag=f'<circle{attrs} cx="{x}" cy="{y}" r="{r}" fill="{shape["color"]}" opacity="{opacity}"/>'
        else:
            points=[tuple(point) for point in shape['points']];line_width=max(1,round(shape.get('width',1)))
            if kind=='polygon':
                draw.polygon(points,fill=color);draw.line(points+[points[0]],fill=rgb(stroke)+(min(240,shape['alpha']+35),),width=line_width)
                if shape.get('glow'):glow_draw.line(points+[points[0]],fill=rgb(stroke)+(shape['alpha'],),width=line_width+1)
                tag=f'<polygon{attrs} points="'+" ".join(f'{x},{y}' for x,y in points)+f'" fill="{shape["color"]}" stroke="{stroke}" stroke-width="{shape.get("width",1)}" opacity="{opacity}"/>'
            elif kind=='curve':
                sampled=cubic_points(points);draw.line(sampled,fill=color,width=line_width)
                a,b,c,d=points;path=f'M {a[0]} {a[1]} C {b[0]} {b[1]} {c[0]} {c[1]} {d[0]} {d[1]}'
                tag=f'<path{attrs} d="{path}" fill="none" stroke="{shape["color"]}" stroke-width="{shape.get("width",1)}" opacity="{opacity}"/>'
            else:
                draw.line(points,fill=color,width=line_width)
                tag=f'<polyline{attrs} points="'+" ".join(f'{x},{y}' for x,y in points)+f'" fill="none" stroke="{shape["color"]}" stroke-width="{shape.get("width",1)}" opacity="{opacity}"/>'
        svg.append(tag)
    if manifest['controls']['style']['dark']:
        canvas=Image.alpha_composite(canvas.convert('RGBA'),glow.filter(ImageFilter.GaussianBlur(5))).convert('RGB')
    png=BytesIO();canvas.save(png,format='PNG',compress_level=9)
    thumb=canvas.copy();thumb.thumbnail((640,640));webp=BytesIO();thumb.save(webp,format='WEBP',quality=88,method=6)
    document=f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {width} {height}" role="img" aria-label="Transaction-derived artwork"><defs><linearGradient id="bg" x2="0" y2="1"><stop stop-color="{background["top"]}"/><stop offset="1" stop-color="{background["bottom"]}"/></linearGradient></defs><rect width="{width}" height="{height}" fill="url(#bg)"/>'+''.join(svg)+'</svg>'
    return {'artwork.png':png.getvalue(),'artwork.svg':document.encode(),'thumbnail.webp':webp.getvalue()}
