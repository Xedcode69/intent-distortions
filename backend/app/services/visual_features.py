"""Versioned, bounded visual measurements derived only from the frozen swap snapshot."""
import math
from collections import Counter
from decimal import Decimal
from .art_statistics import chain, statistics

FEATURE_VERSION = "echo-visual-features-v1"
RENDERER_VERSION = "echo-renderer-4"


def rounded(value):
    return round(float(value),8)


def communities(names, routes):
    """Deterministic greedy weighted modularity, bounded to the 64 busiest nodes."""
    degree=Counter()
    for (a,b),count in routes.items():
        if a!=b and a!="Unmapped" and b!="Unmapped":
            degree[a]+=count;degree[b]+=count
    selected=sorted(sorted(names,key=lambda name:(-degree[name],name))[:64])
    ids={name:i for i,name in enumerate(selected)}
    groups={i:[name] for name,i in ids.items()};weights=Counter();degrees=Counter()
    for (a,b),count in routes.items():
        if a!=b and a in ids and b in ids and "Unmapped" not in (a,b):
            i,j=sorted((ids[a],ids[b]));weights[i,j]+=count;degrees[i]+=count;degrees[j]+=count
    mass=sum(weights.values())
    while mass and len(groups)>1:
        best=None;score=0
        for (a,b),weight in sorted(weights.items()):
            candidate=2*mass*weight-degrees[a]*degrees[b]
            if candidate>score:
                best=(a,b);score=candidate
        if best is None:break
        a,b=best
        for other in sorted(groups):
            if other in best:continue
            ka=tuple(sorted((a,other)));kb=tuple(sorted((b,other)))
            combined=weights.get(ka,0)+weights.pop(kb,0)
            if combined:weights[ka]=combined
        weights.pop((a,b),None);degrees[a]+=degrees.pop(b,0)
        groups[a]+=groups.pop(b)
    clusters=sorted([sorted(group) for group in groups.values()]+[[name] for name in names if name not in ids],key=lambda group:group[0])
    return {name:i for i,group in enumerate(clusters) for name in group}


def visual_features(records,start,end,asset_mapping):
    resolve=lambda asset:chain(asset,asset_mapping)
    outgoing=Counter();incoming=Counter();routes=Counter();assets=Counter();first={};last={};bins=[0]*48
    n=len(records);span=max(1,end-start)
    for row in records:
        a,b=resolve(row["origin_asset"]),resolve(row["destination_asset"])
        outgoing[a]+=1;incoming[b]+=1;routes[a,b]+=1
        assets[row["origin_asset"]]+=1;assets[row["destination_asset"]]+=1
        position=max(0,min(1,(row["created_at_unix"]-start)/span))
        bins[min(47,int(position*48))]+=1
        pair=(a,b);first[pair]=min(first.get(pair,1),position);last[pair]=max(last.get(pair,0),position)
    names=sorted(outgoing.keys()|incoming.keys());partition=communities(names,routes)
    cross=sum(count for (a,b),count in routes.items() if a!=b)
    reciprocity=sum(min(count,routes.get((b,a),0)) for (a,b),count in routes.items() if a!=b)/max(1,cross)
    mean=n/48;variance=sum((count-mean)**2 for count in bins)/48
    cv=math.sqrt(variance)/mean if mean else 0
    peak=max(bins,default=0);peaks=sum(bins[i]>bins[i-1] and bins[i]>=bins[(i+1)%48] for i in range(48))
    amounts=sorted(Decimal(row["amount_in_usd"]) for row in records if row["amount_in_usd"] is not None)
    total=sum(amounts,Decimal(0));size=len(amounts)
    inequality=(sum((2*i-size+1)*amount for i,amount in enumerate(amounts))/(size*total)) if total else Decimal(0)
    top_share=sum(amounts[max(0,size-max(1,math.ceil(size*.01))):],Decimal(0))/total if total else Decimal(0)
    quantile=lambda fraction:format(amounts[min(size-1,int((size-1)*fraction))],"f") if size else None
    entropy=-sum((count/max(1,2*n))*math.log(count/max(1,2*n)) for count in assets.values())/math.log(len(assets)) if len(assets)>1 else 0
    max_hub=max((outgoing[name]+incoming[name] for name in names),default=1)
    concentration=max(outgoing.values(),default=0)/max(1,n)
    return {"version":FEATURE_VERSION,"record_count":n,"asset_count":len(assets),
        "asset_diversity":rounded(entropy),"route_count":len(routes),
        "route_diversity":rounded(-sum((count/max(n,1))*math.log(count/max(n,1)) for count in routes.values())/math.log(len(routes))) if len(routes)>1 else 0,
        "reciprocity":rounded(reciprocity),"cross_network_share":rounded(cross/max(1,n)),
        "flow_imbalance":rounded(sum(abs(outgoing[name]-incoming[name]) for name in names)/max(1,2*n)),
        "hub_concentration":rounded(concentration),"burstiness":rounded(cv/(1+cv)),
        "quiet_share":rounded(sum(count==0 for count in bins)/48),"rhythm_peaks":peaks,
        "activity_profile":[rounded(count/max(1,peak)) for count in bins],
        "size_inequality":rounded(inequality),"top_one_percent_volume_share":rounded(top_share),
        "volume_coverage":size,"median_usd":quantile(.5),"p90_usd":quantile(.9),
        "community_count":len(set(partition.values())),
        "nodes":[{"network":name,"outgoing":outgoing[name],"incoming":incoming[name],
            "flow":rounded((outgoing[name]-incoming[name])/max(1,outgoing[name]+incoming[name])),
            "hub":rounded((outgoing[name]+incoming[name])/max(1,max_hub)),"community":partition[name]} for name in names],
        "routes":[{"origin":a,"destination":b,"count":count,
            "weight":rounded(math.log1p(count)/math.log1p(max(routes.values()))),
            "first":rounded(first[a,b]),"last":rounded(last[a,b])} for (a,b),count in sorted(routes.items())]}


def expressive_statistics(records,start,end,asset_mapping):
    value=statistics(records,start,end,asset_mapping)
    value["visual_features"]=visual_features(records,start,end,asset_mapping)
    return value
