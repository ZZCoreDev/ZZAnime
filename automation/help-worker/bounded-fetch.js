// Bounded public-provider inspection. No credentials or headers from the client are forwarded.
export class InspectionPolicyError extends Error {}
export const INSPECTION_TIMEOUT_MS=8000,PAGE_BYTES=262144,MEGA_BYTES=16384;
function cancel(body){try{body?.cancel().catch(()=>{});}catch{}}
function abortable(task,signal){
 if(signal.aborted)return Promise.reject(signal.reason);
 return new Promise((resolve,reject)=>{
  const abort=()=>{signal.removeEventListener('abort',abort);reject(signal.reason);};
  signal.addEventListener('abort',abort,{once:true});
  Promise.resolve(task).then(value=>{signal.removeEventListener('abort',abort);resolve(value);},error=>{signal.removeEventListener('abort',abort);reject(error);});
 });
}
async function readText(response,maxBytes,signal){
 const size=response.headers.get('content-length');
 if(size!==null&&Number(size)>maxBytes){cancel(response.body);throw new InspectionPolicyError('response-size');}
 if(!response.body)return '';
 const reader=response.body.getReader(),decoder=new TextDecoder();let total=0,text='';
 try{
  for(;;){
   const {value,done}=await abortable(reader.read(),signal);if(done)break;
   total+=value.byteLength;if(total>maxBytes)throw new InspectionPolicyError('response-size');
   text+=decoder.decode(value,{stream:true});
  }
  return text+decoder.decode();
 }finally{
  // Do not wait indefinitely for a remote stream's cancellation implementation.
  try{reader.cancel().catch(()=>{});}catch{}
  try{reader.releaseLock();}catch{}
 }
}
export async function boundedText(url,init,fetcher,allowed,{maxBytes=PAGE_BYTES,maxRedirects=3,timeoutMs=INSPECTION_TIMEOUT_MS}={}){
 const controller=new AbortController(),timer=setTimeout(()=>controller.abort(new Error('inspection-timeout')),timeoutMs);
 let current=url;
 try{
  for(let hops=0;;hops++){
   if(!allowed(current))throw new InspectionPolicyError('destination');
   const pending=Promise.resolve().then(()=>fetcher(current,{...init,redirect:'manual',signal:controller.signal}));
   // Also close a late response if the timeout won the race before headers arrived.
   pending.then(r=>{if(controller.signal.aborted)cancel(r.body);},()=>{});
   const response=await abortable(pending,controller.signal);
   if(response.redirected){cancel(response.body);throw new InspectionPolicyError('automatic-redirect');}
   if([301,302,303,307,308].includes(response.status)){
    const location=response.headers.get('location');cancel(response.body);
    if(!location||hops>=maxRedirects||/[\x00-\x20\x7f\\]/.test(location))throw new InspectionPolicyError('redirect');
    try{current=new URL(location,current).href;}catch{throw new InspectionPolicyError('redirect');}
    // Validate the original absolute authority too: URL would erase an explicit :443.
    const absolute=/^\/\//.test(location)?new URL(current).protocol+location:location;
    if(/^https?:\/\//i.test(absolute)&&!allowed(absolute))throw new InspectionPolicyError('destination');
    continue;
   }
   if(!response.ok){cancel(response.body);return null;}
   return await readText(response,maxBytes,controller.signal);
  }
 }finally{clearTimeout(timer);controller.abort(new Error('inspection-finished'));}
}
