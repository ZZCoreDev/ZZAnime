'use strict';
function failure(stage,error){
 const message=String(error?.message||error).slice(0,160),status=Number(/(?:Source HTTP |HTTP_)([0-9]{3})/.exec(message)?.[1])||null;
 const cause=status===404?'address-not-found':status===302?'redirect':status===429?'rate-limit':status===403?'access-denied':status?'source-http':/ambiguous|identity|title|year/i.test(message)?'identity-mismatch':/unobserved|missing source chapter/i.test(message)?'unlisted-episode':/no .*provider|no .*option/i.test(message)?'no-approved-provider':/options key/i.test(message)?'options-missing':/budget|bounded|limit/i.test(message)?'budget-limit':'parser-or-network';
 return {stage,status,cause,message};
}
module.exports={failure};
