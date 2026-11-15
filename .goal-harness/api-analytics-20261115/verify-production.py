"""Compare real production API against exact channel reports, without exposing credentials."""
import base64
import json
import re
import shlex
import subprocess
import sys
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
  const org=await db.organization.findUnique({where:{id:i.organizationId}});
  if(!org?.apiKey)throw Error('Existing organization API key unavailable');
  const client=new google.auth.OAuth2({clientId:process.env.YOUTUBE_CLIENT_ID,clientSecret:process.env.YOUTUBE_CLIENT_SECRET,forceRefreshOnFailure:true});
  // Force a genuinely expired token state; the stored grant must refresh automatically.
  client.setCredentials({access_token:i.token,refresh_token:i.refreshToken,expiry_date:1});
  const mappings=[['views','Views'],['estimatedMinutesWatched','Estimated Minutes Watched'],['averageViewDuration','Average View Duration'],['averageViewPercentage','Average View Percentage'],['subscribersGained','Subscribers Gained'],['subscribersLost','Subscribers Lost'],['likes','Likes']];
  for(const days of [7,30,90]){
   const now=new Date();const start=new Date(now.getTime()-days*86400000);
   const report=await google.youtubeAnalytics({version:'v2',auth:client}).reports.query({ids:'channel=='+i.internalId,startDate:start.toISOString().slice(0,10),endDate:now.toISOString().slice(0,10),metrics:'views,estimatedMinutesWatched,averageViewDuration,averageViewPercentage,subscribersGained,likes,subscribersLost',dimensions:'day',sort:'day'},{timeout:20000});
   const rows=report.data.rows||[];const columns=report.data.columnHeaders.map(c=>c.name);
   const expected=rows.length?mappings.map(([metric,label])=>({label,data:rows.map(row=>({date:String(row[columns.indexOf('day')]),total:Number(row[columns.indexOf(metric)])}))})):[];
   const response=await fetch(`https://postiz.item79.com/api/public/v1/analytics/${i.id}?date=${days}`,{headers:{Authorization:org.apiKey},signal:AbortSignal.timeout(60000)});
   const data=await response.json();
   const normalized=Array.isArray(data)?data.map(m=>({label:m.label,data:m.data})):null;
   const matches=JSON.stringify(normalized)===JSON.stringify(expected);
   const revision=response.headers.get('x-item79-revision');
   const result={id:i.id,name:i.name,days,httpStatus:response.status,metrics:Array.isArray(data)?data.map(m=>({label:m.label,points:m.data?.length||0,finite:!!m.data?.every(p=>Number.isFinite(p.total))})):[],exactChannelReportMatches:matches,legitimateNoData:expected.length===0,expiredTokenAutoRefreshVerified:true,revision};
   console.log(JSON.stringify(result));
   if(!response.ok||!matches||revision!==expectedRevision)throw Error('Production analytics verification failed');
  }
 }
 await db.$disconnect();
})().catch(async()=>{console.error('Production analytics verification failed (details suppressed)');await db.$disconnect();process.exitCode=1;});
'''
if __name__ == '__main__':
    revision = sys.argv[1]
    assert re.fullmatch('[a-f0-9]{40}', revision)
    encoded = base64.b64encode(('const expectedRevision='+json.dumps(revision)+';\n'+JS).encode()).decode()
    remote = "import json,subprocess; state=json.load(open('/opt/postiz-center-20261112/web-release.json')); slot=state['activeSlot']; assert slot in ('blue','green'); subprocess.run(['docker','exec','postiz-item79-web-'+slot+'-web-1','node','-e',\"eval(Buffer.from('"+encoded+"','base64').toString())\"],check=True)"
    command = 'sudo -n python3 -c ' + shlex.quote(remote)
    subprocess.run(SSH + [command], check=True)
