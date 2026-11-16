# Compare Quackle superleaves (binary: len, tiles, frac byte, int byte; value = v/256 - 128;
# letters coded blank=1, A=5..) with a wolges/MAGPIE .klv2 (u32 node count, KWG nodes, u32 n, f32 values;
# value index = word rank in DAWG order). Written for this repo; no engine code copied.
# Usage: python3 -I compare_quackle_magpie_leaves.py <quackle superleaves> <CSW24.klv2>
import struct, sys, math
def quackle(path):
    d=open(path,'rb').read(); i=0; out={}
    while i < len(d):
        n=d[i]; i+=1
        if i+n+2>len(d): break
        lv=d[i:i+n]; i+=n
        frac=d[i]; ip=d[i+1]; i+=2
        s=''.join('?' if c==1 else chr(ord('A')+c-5) for c in lv)
        out[s]=(ip*256+frac)/256.0-128.0
    return out
def klv(path):
    d=open(path,'rb').read()
    n=struct.unpack_from('<I',d,0)[0]
    nodes=struct.unpack_from('<%dI'%n,d,4)
    off=4+4*n; m=struct.unpack_from('<I',d,off)[0]
    vals=struct.unpack_from('<%df'%m,d,off+4)
    words=[]
    def walk(p,pre):
        while True:
            x=nodes[p]; t=x>>24; acc=(x>>23)&1; end=(x>>22)&1; arc=x&0x3fffff
            ch='?' if t==0 else chr(ord('A')+t-1)
            if acc: words.append(pre+ch)
            if arc: walk(arc,pre+ch)
            if end: break
            p+=1
    walk(nodes[0]&0x3fffff,'')
    assert len(words)==m,(len(words),m)
    return dict(zip(words,vals))
q=quackle(sys.argv[1]); k=klv(sys.argv[2])
print('quackle entries',len(q),'klv entries',len(k))
common=[w for w in k if w in q]
print('common',len(common), 'q only',len([w for w in q if w not in k]))
xs=[q[w] for w in common]; ys=[k[w] for w in common]
mx=sum(xs)/len(xs); my=sum(ys)/len(ys)
cov=sum((a-mx)*(b-my) for a,b in zip(xs,ys)); vx=sum((a-mx)**2 for a in xs); vy=sum((b-my)**2 for b in ys)
print('pearson %.3f mean q %.2f mean k %.2f'%(cov/math.sqrt(vx*vy),mx,my))
for L in range(1,7):
    c=[w for w in common if len(w)==L]
    d=[q[w]-k[w] for w in c]
    print('len',L,'n',len(c),'mean(q-k) %.2f'%(sum(d)/len(d)),'rms %.2f'%math.sqrt(sum(x*x for x in d)/len(d)))
for w in ['?','S','Z','Q','V','U','QU','ERS','?S','AEINST','EIIOU','?ERS']:
    print(w, round(q.get(w,float('nan')),2), round(k.get(w,float('nan')),2))
