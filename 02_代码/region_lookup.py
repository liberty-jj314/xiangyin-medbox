"""浏览器WGS84坐标临时转换为GCJ02，匹配已有高德县界；坐标不落盘。"""
import json
import math
import os
from functools import lru_cache

def gcj(lng,lat):
    x=lng-105;y=lat-35;p=math.pi
    a=-100+2*x+3*y+.2*y*y+.1*x*y+.2*math.sqrt(abs(x))
    a+=(20*math.sin(6*x*p)+20*math.sin(2*x*p))*2/3
    a+=(20*math.sin(y*p)+40*math.sin(y*p/3))*2/3
    a+=(160*math.sin(y*p/12)+320*math.sin(y*p/30))*2/3
    b=300+x+2*y+.1*x*x+.1*x*y+.1*math.sqrt(abs(x))
    b+=(20*math.sin(6*x*p)+20*math.sin(2*x*p))*2/3
    b+=(20*math.sin(x*p)+40*math.sin(x*p/3))*2/3
    b+=(150*math.sin(x*p/12)+300*math.sin(x*p/30))*2/3
    r=lat*p/180;magic=1-.006693421622965943*math.sin(r)**2
    return (lng+b*180/(6378245/math.sqrt(magic)*math.cos(r)*p),
            lat+a*180/((6378245*(1-.006693421622965943))/(magic*math.sqrt(magic))*p))

@lru_cache(maxsize=1)
def boundaries():
    with open(os.path.join(os.path.dirname(__file__),'gx_counties.json'),encoding='utf-8') as f:
        return json.load(f)['counties']

def inside(x,y,ring):
    hit=False;j=len(ring)-1
    for i in range(len(ring)):
        ax,ay=ring[i];bx,by=ring[j]
        if ((ay>y)!=(by>y)) and x<(bx-ax)*(y-ay)/(by-ay)+ax:hit=not hit
        j=i
    return hit

def distance_to_ring(x,y,ring):
    """县界折线最近距离（局部等距近似，米）；用于保守的跨界误差检查。"""
    scale_x=111320*math.cos(math.radians(y));scale_y=111320
    best=float('inf')
    for i in range(len(ring)):
        a=ring[i-1];b=ring[i]
        ax=(a[0]-x)*scale_x;ay=(a[1]-y)*scale_y
        bx=(b[0]-x)*scale_x;by=(b[1]-y)*scale_y
        dx=bx-ax;dy=by-ay;length=dx*dx+dy*dy
        t=max(0,min(1,-(ax*dx+ay*dy)/length)) if length else 0
        best=min(best,math.hypot(ax+t*dx,ay+t*dy))
    return best

def locate(lng,lat,accuracy):
    if any(isinstance(v,bool) or not isinstance(v,(int,float)) or not math.isfinite(v) for v in (lng,lat,accuracy)):
        raise ValueError('定位坐标格式不正确')
    if not (-180<=lng<=180 and -90<=lat<=90 and 0<=accuracy<=10000000):raise ValueError('定位坐标超出范围')
    # 一公里已是县区统计的上限，不把城市级/网络出口位置当作县区。
    if accuracy>1000:return '', 'low_accuracy'
    if not (104<lng<113 and 20<lat<27):return '', 'outside'
    x,y=gcj(lng,lat)
    matches=[]
    for code,rings in boundaries().items():
        # 奇偶规则同时支持不相连的地块和被围住的孔洞，不取“第一个命中”。
        if sum(inside(x,y,ring) for ring in rings)%2:matches.append((code,rings))
    if not matches:return '', 'outside'
    if len(matches)!=1:return '', 'boundary_uncertain'
    code,rings=matches[0]
    # 留出县界简化和坐标换算余量；误差圆跨界时暂不归县。
    margin=max(150,accuracy+100)
    if min(distance_to_ring(x,y,ring) for ring in rings)<=margin:
        return '', 'boundary_uncertain'
    return code,'granted'
