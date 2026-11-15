# Python mirror of the Küte plaan logic, used to sanity-check rules on real prices.
import json, sys, urllib.request, math, datetime as dt
from zoneinfo import ZoneInfo
TZ=ZoneInfo('Europe/Tallinn')
S=dict(off_above=15,hi_below=5,vat=24,net_day=4.58,net_night=2.60,
       holidays="01-01,02-24,05-01,06-23,06-24,08-20,12-24,12-25,12-26",
       quiet_start=0,quiet_end=6,preheat_hours=2,preheat_min_gap=7,preheat_min_block=2,preheat_max_price=12,delay_min_gap=8,
       t_on=22,t_hi=24,t_floor=19,loss_factor=32,ask_above=25,ask_never_below=-15,kwh_per_hour=5)
def plan(start_local, end_local, tmin):
    u=lambda d:d.astimezone(dt.timezone.utc).strftime('%Y-%m-%dT%H:%M:%S.000Z')
    url=f"https://dashboard.elering.ee/api/nps/price?start={u(start_local)}&end={u(end_local)}"
    items=json.load(urllib.request.urlopen(url))['data']['ee']
    ts0=items[0]['timestamp']; avg=[]; cur=None; s=c=0
    for it in items:
        h=math.floor((it['timestamp']-ts0)/3600)+1
        if h!=cur and c>0: avg.append(s/c); s=c=0
        cur=h; s+=it['price']; c+=1
    avg.append(s/c)
    mult=S['vat']/1000+0.1
    H=len(avg); P=[];T=[];HR=[];D=[];K=[];M={};W={}
    for i in range(H):
        d=dt.datetime.fromtimestamp(ts0+i*3600,TZ)
        p=round(avg[i]*mult,2); hr=d.hour
        summer=d.utcoffset().total_seconds()==10800
        hol=(','+S['holidays']+',').find(','+d.strftime('%m-%d')+',')>=0
        day=d.weekday()<=4 and not hol and (7+summer)<=hr<(22+summer)
        t=p+(S['net_day'] if day else S['net_night'])
        quiet=S['quiet_start']<=hr<S['quiet_end']
        if p>S['off_above']: m,w='OFF','tipp'
        elif p<S['hi_below']: m,w=('ON','öö') if quiet else ('HI','odav')
        else: m,w='ON','tava'
        P.append(p);T.append(t);HR.append(hr);D.append(d.strftime('%Y-%m-%d'));K.append(d.strftime('%Y-%m-%dT%H'));M[i]=m;W[i]=w
    # delay
    for i in range(H-1):
        if M[i]=='ON' and (i==0 or M[i-1]!='OFF') and M[i+1]!='OFF' and T[i]-T[i+1]>=S['delay_min_gap']:
            M[i],W[i]='OFF','ootan'
    # blocks
    blocks=[]; inb=False
    for i in range(H):
        if M[i]=='OFF' and W[i]=='tipp':
            if not inb: blocks.append([i,0,0.0])
            blocks[-1][1]+=1; blocks[-1][2]+=T[i]; inb=True
        else: inb=False
    for s0,L,sm in blocks:
        a=sm/L
        for k in range(1,S['preheat_hours']+1 if L>=S['preheat_min_block'] else 1):
            j=s0-k
            if j>=0 and M[j] not in ('OFF','ASK') and not (S['quiet_start']<=HR[j]<S['quiet_end']) and P[j]<=S['preheat_max_price'] and a-T[j]>=S['preheat_min_gap']:
                M[j],W[j]='HI','eelküte'
        pre= s0>0 and M[s0-1]=='HI'
        tout=tmin.get(D[s0],0)
        lossc=max((S['t_on']-tout)*100/S['loss_factor'],5)  # hundredths of a degree per hour
        m1=max(math.floor(((S['t_hi'] if pre else S['t_on'])-S['t_floor'])*100/lossc),1)
        mon=max(math.floor((S['t_on']-S['t_floor'])*100/lossc),1)
        pos=s0; e=s0+L-1; m=m1
        while e-pos+1>m:
            c=min(range(pos,pos+m+1),key=lambda x:T[x])
            if T[c]>S['ask_above'] and tout>S['ask_never_below']: M[c],W[c]='ASK','küsin'
            else: M[c],W[c]='ON','mugavus'
            pos=c+1; m=mon
    for i in range(H):
        print(K[i],f"{P[i]:6.2f} {T[i]:6.2f}",M[i],W[i])
if __name__=='__main__':
    day=dt.date.fromisoformat(sys.argv[1]); tm=float(sys.argv[2])
    st=dt.datetime(day.year,day.month,day.day,tzinfo=TZ)
    plan(st, st+dt.timedelta(days=1)-dt.timedelta(seconds=1), {str(day):tm})
