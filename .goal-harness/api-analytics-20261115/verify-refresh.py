"""Exercise saved refresh grants in memory without printing or replacing credentials."""
import base64
import subprocess
from diagnose import SSH

JS = r'''
const {PrismaClient}=require('@prisma/client');
const {google}=require('googleapis');
const db=new PrismaClient();
(async()=>{
 const ids=['cmweat59e0001o47f4n3hb7x3','cmwef8i230001pd7wcv85jj3i','cmwece9dg0004o47fzk35186s'];
 const rows=await db.integration.findMany({where:{id:{in:ids},providerIdentifier:'youtube',deletedAt:null}});
 if(rows.length!==3)throw Error('Channel inventory changed');
 for(const i of rows){
  const client=new google.auth.OAuth2(process.env.YOUTUBE_CLIENT_ID,process.env.YOUTUBE_CLIENT_SECRET);
  client.setCredentials({refresh_token:i.refreshToken});
  const {credentials}=await client.refreshAccessToken();
  if(!credentials.access_token)throw Error('No refreshed token');
  // Same userinfo operation used by the existing production refresh provider.
  await google.oauth2({version:'v2',auth:client}).userinfo.get();
  const response=await google.youtubeAnalytics({version:'v2',auth:client}).reports.query({ids:'channel=='+i.internalId,startDate:'2026-11-01',endDate:'2026-11-14',metrics:'views',dimensions:'day'});
  console.log(JSON.stringify({id:i.id,name:i.name,refreshGrantValid:true,userinfoOk:true,refreshedAnalyticsOk:response.status===200,points:response.data.rows?.length||0,persistedCredentialChanges:false}));
 }
 await db.$disconnect();
})().catch(async()=>{console.error('Refresh verification failed (details suppressed)');await db.$disconnect();process.exitCode=1;});
'''
if __name__ == '__main__':
    encoded = base64.b64encode(JS.encode()).decode()
    command = "sudo -n docker exec postiz-item79-web-blue-web-1 node -e \"eval(Buffer.from('" + encoded + "','base64').toString())\""
    subprocess.run(SSH + [command], check=True)
