"""Read-only owned Postiz files/references and YouTube publication evidence.

Private raw reports go to E:. Credentials remain in the production container.
"""
import base64
import importlib.util
import json
from pathlib import Path
import shlex
import subprocess

dependency = Path(__file__).parents[1] / 'api-analytics-20261115' / 'diagnose.py'
spec = importlib.util.spec_from_file_location('item79_diagnostic_ssh', dependency)
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)
SSH = module.SSH
DEST = Path('E:/codex-build/postiz-item79/published-video-cleanup-20261115/reports/server-inventory.json')

JS = r'''
const {PrismaClient}=require('@prisma/client');
const {google}=require('googleapis');
const db=new PrismaClient();
const ids=['cmweat59e0001o47f4n3hb7x3','cmwef8i230001pd7wcv85jj3i','cmwece9dg0004o47fzk35186s'];
function safePath(value){
 if(typeof value!=='string')return null;
 try{const u=new URL(value,'https://postiz.item79.com');if(u.origin!=='https://postiz.item79.com'||!u.pathname.startsWith('/uploads/'))return null;return decodeURIComponent(u.pathname);}catch{return null;}
}
function references(value){
 const paths=new Set(),mediaIds=new Set();
 function walk(v){if(typeof v==='string'){const p=safePath(v);if(p)paths.add(p);}else if(Array.isArray(v)){v.forEach(walk);}else if(v&&typeof v==='object'){if(typeof v.id==='string')mediaIds.add(v.id);Object.values(v).forEach(walk);}}
 walk(value);return {paths:[...paths],mediaIds:[...mediaIds]};
}
(async()=>{
 const integrations=await db.integration.findMany({where:{id:{in:ids},providerIdentifier:'youtube',deletedAt:null}});
 if(integrations.length!==3)throw Error('Owned channel inventory changed');
 const orgIds=[...new Set(integrations.map(i=>i.organizationId))];
 const posts=await db.post.findMany({where:{organizationId:{in:orgIds}},select:{id:true,state:true,publishDate:true,organizationId:true,integrationId:true,group:true,parentPostId:true,releaseId:true,releaseURL:true,image:true,settings:true,error:true,createdAt:true,updatedAt:true,deletedAt:true}});
 const media=await db.media.findMany({where:{organizationId:{in:orgIds}},select:{id:true,name:true,originalName:true,path:true,createdAt:true,updatedAt:true,deletedAt:true,status:true,type:true,fileSize:true}});
 const safePosts=posts.map(p=>{
  let images=[],settings={},parseError=false;
  try{images=p.image?JSON.parse(p.image):[];}catch{parseError=true;}
  try{settings=p.settings?JSON.parse(p.settings):{};}catch{parseError=true;}
  const refs=references([images,settings]);
  return {id:p.id,state:p.state,publishDate:p.publishDate,organizationId:p.organizationId,integrationId:p.integrationId,group:p.group,parentPostId:p.parentPostId,releaseId:p.releaseId,releaseURL:p.releaseURL,createdAt:p.createdAt,updatedAt:p.updatedAt,deletedAt:p.deletedAt,hasError:!!p.error,parseError,...refs};
 });
 const provider=[];
 for(const i of integrations){
  const videoIds=[...new Set(safePosts.filter(p=>p.integrationId===i.id&&p.state==='PUBLISHED'&&!p.deletedAt).map(p=>p.releaseId).filter(id=>/^[A-Za-z0-9_-]{11}$/.test(id||'')))];
  const client=new google.auth.OAuth2({clientId:process.env.YOUTUBE_CLIENT_ID,clientSecret:process.env.YOUTUBE_CLIENT_SECRET,forceRefreshOnFailure:true});
  client.setCredentials({access_token:i.token,refresh_token:i.refreshToken,expiry_date:i.tokenExpiration?.getTime()});
  const yt=google.youtube({version:'v3',auth:client});
  for(let offset=0;offset<videoIds.length;offset+=50){
   const batch=videoIds.slice(offset,offset+50);
   try{
    const result=await yt.videos.list({id:batch,part:['snippet','status','processingDetails','contentDetails']},{timeout:20000});
    const found=new Set();
    for(const v of result.data.items||[]){found.add(v.id);provider.push({integrationId:i.id,requestedChannelId:i.internalId,videoId:v.id,channelId:v.snippet?.channelId,publishedAt:v.snippet?.publishedAt,privacyStatus:v.status?.privacyStatus,uploadStatus:v.status?.uploadStatus,scheduledPublishAt:v.status?.publishAt,processingStatus:v.processingDetails?.processingStatus,duration:v.contentDetails?.duration,regionRestriction:v.contentDetails?.regionRestriction,verifiedAt:new Date().toISOString()});}
    for(const id of batch)if(!found.has(id))provider.push({integrationId:i.id,videoId:id,missing:true});
   }catch(e){provider.push({integrationId:i.id,verificationFailed:true,httpStatus:e.response?.status});}
  }
 }
 console.log(JSON.stringify({capturedAt:new Date().toISOString(),integrations:integrations.map(i=>({id:i.id,channelId:i.internalId,name:i.name,organizationId:i.organizationId})),posts:safePosts,media:media.map(m=>({...m,path:safePath(m.path)})),provider}));
 await db.$disconnect();
})().catch(async()=>{console.error('Inventory failed; details suppressed');await db.$disconnect();process.exitCode=1;});
'''

REMOTE = r'''
import datetime,json,os,stat,subprocess
from pathlib import Path
root=Path('/opt/postiz-center-20261112')
state=json.loads((root/'web-release.json').read_text());slot=state['activeSlot'];assert slot in ('blue','green')
data=json.loads(subprocess.check_output(['docker','exec','postiz-item79-web-'+slot+'-web-1','node','-e',"eval(Buffer.from('ENCODED_JS','base64').toString())"]))
uploads=root/'uploads';assert uploads.is_dir() and not uploads.is_symlink() and uploads.resolve()==uploads
files=[];suspicious=[]
for parent,dirs,names in os.walk(uploads,followlinks=False):
 for name in list(dirs):
  if (Path(parent)/name).is_symlink(): suspicious.append(str((Path(parent)/name).relative_to(uploads)));dirs.remove(name)
 for name in names:
  path=Path(parent)/name
  if path.suffix.lower() not in {'.mp4','.mov','.webm','.m4v'}:continue
  st=path.lstat()
  if not stat.S_ISREG(st.st_mode) or path.is_symlink():suspicious.append(str(path.relative_to(uploads)));continue
  assert path.resolve().is_relative_to(uploads)
  files.append({'relativePath':str(path.relative_to(uploads)),'urlPath':'/uploads/'+str(path.relative_to(uploads)),'bytes':st.st_size,'mtime':datetime.datetime.fromtimestamp(st.st_mtime,datetime.timezone.utc).isoformat(),'links':st.st_nlink})
data.update({'host':'vmi3690013','uploadsRoot':str(uploads),'liveRevision':state['revision'],'files':files,'suspiciousPaths':suspicious})
print(json.dumps(data))
'''

if __name__ == '__main__':
    encoded = base64.b64encode(JS.encode()).decode()
    remote = REMOTE.replace('ENCODED_JS', encoded)
    result = subprocess.run(SSH + ['sudo -n python3 -c ' + shlex.quote(remote)], stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=False)
    if result.returncode:
        raise SystemExit('Read-only inventory failed; private diagnostics suppressed')
    data = json.loads(result.stdout)
    DEST.parent.mkdir(parents=True, exist_ok=True)
    DEST.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding='utf-8')
    states = {}
    for p in data['posts']: states[p['state']] = states.get(p['state'], 0) + 1
    cutoff = __import__('datetime').datetime.now(__import__('datetime').timezone.utc) - __import__('datetime').timedelta(days=7)
    mature = [v for v in data['provider'] if v.get('publishedAt') and __import__('datetime').datetime.fromisoformat(v['publishedAt'].replace('Z','+00:00')) <= cutoff and v.get('privacyStatus') == 'public' and v.get('uploadStatus') == 'processed' and v.get('channelId') == v.get('requestedChannelId')]
    print(json.dumps({'report':str(DEST),'channels':len(data['integrations']),'postsByState':states,'videoFiles':len(data['files']),'videoBytes':sum(f['bytes'] for f in data['files']),'verifiedPublicVideoCount':sum(v.get('privacyStatus')=='public' for v in data['provider']),'publicAtLeast7Days':len(mature),'suspiciousPathCount':len(data['suspiciousPaths']),'mutationPerformed':False},ensure_ascii=False))
