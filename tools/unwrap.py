import sys, struct, plistlib, subprocess, os, tempfile
src, outdir = sys.argv[1], sys.argv[2]
d=open(src,'rb').read()
n=struct.unpack('<I',d[8:12])[0]
cert=plistlib.loads(d[12:12+n])['SigningCertificateChain'][0]
os.makedirs(outdir, exist_ok=True)
open(outdir+'/leaf.der','wb').write(cert)
pem=subprocess.run(['openssl','x509','-inform','der','-in',outdir+'/leaf.der','-pubkey','-noout'],capture_output=True,check=True).stdout
open(outdir+'/pub.pem','wb').write(pem)
subprocess.run(['aea','decrypt','-i',src,'-o',outdir+'/out.aar','-sign-pub',outdir+'/pub.pem'],check=True)
subprocess.run(['aa','extract','-i',outdir+'/out.aar','-d',outdir],check=True)
