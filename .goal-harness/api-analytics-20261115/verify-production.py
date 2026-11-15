"""Verify production analytics using the existing org API key, kept inside server memory.

Only known empty analytics cache keys for the three verified channels may be removed.
No token, post, queue or other Redis key is changed.
"""
import base64
import subprocess
from diagnose import SSH

JS = r'''
const {PrismaClient}=require('@prisma/client');
const Redis=require('ioredis');
const db=new PrismaClient();
const redis=new Redis(process.env.REDIS_URL);
(async()=>{
 const ids=['cmweat59e0001o47f4n3hb7x3','cmwef8i230001pd7wcv85jj3i','cmwece9dg0004o47fzk35186s'];
 const rows=await db.integration.findMany({where:{id:{in:ids},providerIdentifier:'youtube',deletedAt:null}});
 if(rows.length!==3)throw Error('Channel inventory changed');
 for(const i of rows){
  const org=await db.organization.findUnique({where:{id:i.organizationId}});
  if(!org?.apiKey)throw Error('Existing organization API key unavailable');
  for(const days of [7,30,90]){
   const key=`integration:${org.id}:${i.id}:${days}`;
   const cached=await redis.get(key);
   // Compare-and-delete: never delete data concurrently filled by another request.
   const removed=cached==='[]'?await redis.eval("if redis.call('GET', KEYS[1]) == '[]' then return redis.call('DEL', KEYS[1]) else return 0 end",1,key):0;
   const response=await fetch(`https://postiz.item79.com/api/public/v1/analytics/${i.id}?date=${days}`,{headers:{Authorization:org.apiKey},signal:AbortSignal.timeout(60000)});
   const data=await response.json();
   const result={id:i.id,name:i.name,days,httpStatus:response.status,emptyCacheRemoved:!!removed,metrics:Array.isArray(data)?data.map(m=>({label:m.label,points:m.data?.length||0,finite:!!m.data?.every(p=>Number.isFinite(p.total))})):[],revision:response.headers.get('x-item79-revision')};
   console.log(JSON.stringify(result));
   if(!response.ok||!Array.isArray(data)||data.length<6||data.some(m=>!Array.isArray(m.data)||m.data.some(p=>!Number.isFinite(p.total))))throw Error('Production analytics verification failed');
  }
 }
 await redis.quit();await db.$disconnect();
})().catch(async()=>{console.error('Production analytics verification failed (details suppressed)');await redis.quit();await db.$disconnect();process.exitCode=1;});
'''
if __name__ == '__main__':
    encoded = base64.b64encode(JS.encode()).decode()
    command = "sudo -n docker exec postiz-item79-web-blue-web-1 node -e \"eval(Buffer.from('" + encoded + "','base64').toString())\""
    subprocess.run(SSH + [command], check=True)
