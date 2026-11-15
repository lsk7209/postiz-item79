"""Read-only provider diagnostics. Print only whitelisted status fields, never tokens."""
import base64
import subprocess

SSH = ['ssh', '-i', 'C:/Users/dlatj/.ssh/im-cloud-contabo-admin', '-o', 'BatchMode=yes', '-o', 'IdentitiesOnly=yes', '-o', 'StrictHostKeyChecking=yes', '-o', 'UserKnownHostsFile=D:/server-contabo/connection-20261028/known_hosts', 'imadmin@13.140.77.84']
JS = r'''
const {PrismaClient}=require('@prisma/client');
const {google}=require('googleapis');
const db=new PrismaClient();
(async()=>{
 const rows=await db.integration.findMany({where:{providerIdentifier:'youtube',deletedAt:null}});
 for(const i of rows){
  const result={id:i.id,name:i.name,disabled:i.disabled,refreshNeeded:i.refreshNeeded,hasRefreshToken:!!i.refreshToken,expired:!!i.tokenExpiration&&new Date(i.tokenExpiration)<new Date()};
  const client=new google.auth.OAuth2(process.env.YOUTUBE_CLIENT_ID,process.env.YOUTUBE_CLIENT_SECRET);
  client.setCredentials({access_token:i.token});
  try {
   const r=await google.youtubeAnalytics({version:'v2',auth:client}).reports.query({ids:'channel==MINE',startDate:'2026-11-01',endDate:'2026-11-14',metrics:'views,estimatedMinutesWatched,averageViewDuration,averageViewPercentage,subscribersGained,likes,subscribersLost',dimensions:'day',sort:'day'});
   result.analytics={ok:true,rows:r.data.rows?.length||0,metrics:r.data.columnHeaders?.map(c=>c.name)};
  }catch(e){result.analytics={status:e.response?.status,reason:e.response?.data?.error?.errors?.[0]?.reason,googleStatus:e.response?.data?.error?.status,service:e.response?.data?.error?.details?.find(d=>d.metadata?.service)?.metadata?.service,consumer:e.response?.data?.error?.details?.find(d=>d.metadata?.consumer)?.metadata?.consumer};}
  try {
   const r=await google.youtube({version:'v3',auth:client}).channels.list({id:[i.internalId],part:['statistics']});
   result.publicStats={ok:true,channels:r.data.items?.length||0};
  }catch(e){result.publicStats={status:e.response?.status,reason:e.response?.data?.error?.errors?.[0]?.reason};}
  console.log(JSON.stringify(result));
 }
 await db.$disconnect();
})().catch(()=>{console.error('Diagnostic failed');process.exitCode=1});
'''
if __name__ == '__main__':
    encoded = base64.b64encode(JS.encode()).decode()
    command = "sudo -n docker exec postiz-item79-web-blue-web-1 node -e \"eval(Buffer.from('" + encoded + "','base64').toString())\""
    subprocess.run(SSH + [command], check=True)
